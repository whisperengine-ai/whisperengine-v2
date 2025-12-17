import asyncio
import json
import os
import yaml
import random
import numpy as np
from typing import List, Dict, Any, TypedDict, Literal, Optional
from datetime import datetime, timedelta, timezone
from loguru import logger
from pydantic import BaseModel

from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.runnables import Runnable

from src_v2.agents.daily_life.models import SensorySnapshot, ActionCommand, MessageSnapshot
from src_v2.memory.embeddings import EmbeddingService
from src_v2.agents.llm_factory import create_llm
from src_v2.agents.master_graph import master_graph_agent
from src_v2.core.character import CharacterManager
from src_v2.utils.json_utils import extract_json_from_text
from src_v2.core.goals import goal_manager
from src_v2.evolution.trust import trust_manager
from src_v2.evolution.drives import drive_manager
from src_v2.memory.manager import memory_manager
from src_v2.knowledge.manager import knowledge_manager
from src_v2.config.settings import settings

# --- State Definition ---

class ScoredMessage(BaseModel):
    message: MessageSnapshot
    score: float
    relevance_reason: str

class PlannedAction(BaseModel):
    intent: Literal["reply", "react", "post", "reach_out", "ignore"]
    target_message_id: Optional[str] = None
    channel_id: str
    reasoning: str
    emoji: Optional[str] = None # Optimization: Pick emoji during planning to save a call
    target_bot_name: Optional[str] = None # For reach_out intent
    target_bot_id: Optional[str] = None # For reach_out intent (to mention)

class DailyLifeState(TypedDict):
    # Input
    snapshot: SensorySnapshot
    
    # Internal
    scored_messages: List[ScoredMessage]
    planned_actions: List[PlannedAction]
    
    # Output
    final_commands: List[ActionCommand]

# --- Graph Implementation ---

class DailyLifeGraph:
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.character_manager = CharacterManager()
        # Use a fast router model for planning
        self.planner_llm = create_llm(temperature=0.4, mode="router")
        # Use a creative model for proactive posting (boredom)
        self.executor_llm = create_llm(temperature=0.8, mode="main")
        # We use the singleton master_graph_agent directly for execution
        # This avoids instantiating a heavy AgentEngine and its sub-agents repeatedly

    def _load_interests(self, bot_name: str) -> List[str]:
        """Generate interests from character drives and goals (emergent, not prescribed)."""
        # Generate from Character Drives & Goals (ADR-010: no more lurk_triggers.yaml)
        try:
            character = self.character_manager.load_character(bot_name)
            if character and character.behavior:
                interests = []
                # Add drives as interests
                if character.behavior.drives:
                    interests.extend(character.behavior.drives.keys())
                
                # Add keywords from goals
                goals = goal_manager.load_goals(bot_name)
                for g in goals:
                    # Simple heuristic: use the first few words of the goal description
                    # or the category
                    interests.append(g.category)
                    
                if interests:
                    # Deduplicate
                    return list(set(interests))
        except Exception as e:
            logger.warning(f"Failed to generate fallback interests: {e}")

        # 3. Ultimate Fallback (Generic)
        return ["AI", "consciousness", "philosophy", "tech"]

    async def perceive(self, state: DailyLifeState) -> Dict[str, Any]:
        """
        Computes embeddings for messages and scores them against character interests.
        """
        snapshot = state["snapshot"]
        bot_name = snapshot.bot_name
        bot_id = getattr(snapshot, "bot_id", None)
        
        interests = self._load_interests(bot_name)
        
        # Collect IDs of messages the bot has already replied to
        replied_to_ids = set()
        for channel in snapshot.channels:
            for msg in channel.messages:
                is_own_message = False
                if bot_id and msg.author_id == bot_id:
                    is_own_message = True
                elif msg.author_name.lower() == bot_name.lower():
                    is_own_message = True
                    
                if is_own_message and msg.reference_id:
                    replied_to_ids.add(msg.reference_id)

        # Get watch channels for bot visibility
        watch_channels = []
        if hasattr(snapshot, "watch_channels") and snapshot.watch_channels:
            watch_channels = snapshot.watch_channels
        
        # Flatten messages from all channels
        all_messages = []
        message_map = {}  # For reply lookup
        for channel in snapshot.channels:
            is_watch_channel = channel.channel_id in watch_channels
            
            for msg in channel.messages:
                message_map[msg.id] = msg
                
                # Skip own messages
                is_own_message = False
                if bot_id and msg.author_id == bot_id:
                    is_own_message = True
                elif msg.author_name.lower() == bot_name.lower():
                    is_own_message = True
                
                if is_own_message:
                    continue
                
                # Skip bot messages UNLESS this is a watch channel
                # (In watch channels, we see everything including other bots)
                if msg.is_bot and not is_watch_channel:
                    continue
                    
                all_messages.append(msg)
        
        # 1. Filter out old messages (older than 15 minutes)
        # and messages that mention the bot (handled by main process)
        
        # Use UTC for comparison
        now_utc = datetime.now(timezone.utc)
        cutoff = now_utc - timedelta(minutes=15)
        
        relevant_messages = []
        for m in all_messages:
            msg_dt = m.created_at
            # Ensure msg_dt is aware for comparison
            if msg_dt.tzinfo is None:
                msg_dt = msg_dt.replace(tzinfo=timezone.utc)
                
            # Skip if too old
            if msg_dt < cutoff:
                continue
            # Skip if mentions bot (main process handles this)
            if m.mentions_bot:
                continue
            
            # BUGFIX: Skip if message @mentions ANY user (conversation is directed at them)
            # If the bot isn't mentioned (checked above), and others ARE, it's private.
            if m.mentioned_users:
                logger.debug(
                    f"Skipping message {m.id} - mentions users {m.mentioned_users} "
                    f"(bot not included)"
                )
                continue

            # BUGFIX: Skip if message is a REPLY to someone else
            if m.reference_id and m.reference_id in message_map:
                ref_msg = message_map[m.reference_id]
                # If replying to someone who isn't us, stay out
                # (If replying to us, we might want to react/reply if main process missed it)
                if bot_id and ref_msg.author_id != bot_id:
                    logger.debug(
                        f"Skipping message {m.id} - reply to {ref_msg.author_name} "
                        f"(not bot)"
                    )
                    continue
                
            # Skip if already replied to
            if m.id in replied_to_ids:
                continue
                
            relevant_messages.append(m)

        if not relevant_messages:
            return {"scored_messages": []}

        scored = []
        
        # 2. Semantic Search for others
        if interests:
            try:
                # Sanitize inputs
                interests = [str(i) for i in interests if i]
                if not interests:
                    return {"scored_messages": []}

                # Embed interests
                # Note: In production, cache these!
                interest_embeddings = list(self.embedding_service.model.embed(interests))
                
                # Embed messages
                msg_texts = [str(m.content) for m in relevant_messages if m.content]
                if not msg_texts:
                    return {"scored_messages": []}

                msg_embeddings = list(self.embedding_service.model.embed(msg_texts))
                
                # Pre-fetch trust scores for all message authors to boost friends
                author_ids = list(set(m.author_id for m in relevant_messages))
                trust_tasks = [trust_manager.get_relationship_level(aid, bot_name) for aid in author_ids]
                trust_results = await asyncio.gather(*trust_tasks, return_exceptions=True)
                author_trust = {}
                for aid, res in zip(author_ids, trust_results):
                    if isinstance(res, dict):
                        author_trust[aid] = res.get("level", 1)
                    else:
                        author_trust[aid] = 1  # Default to stranger
                
                for i, msg_emb in enumerate(msg_embeddings):
                    msg = relevant_messages[i]
                    is_watch_channel = msg.channel_id in watch_channels
                    trust_level = author_trust.get(msg.author_id, 1)
                    is_friend = trust_level >= settings.DAILY_LIFE_FRIEND_TRUST_THRESHOLD
                    
                    # Max similarity against any interest
                    # Dot product of normalized vectors = cosine similarity
                    # FastEmbed vectors are normalized
                    sims = [np.dot(msg_emb, int_emb) for int_emb in interest_embeddings]
                    max_sim = max(sims) if sims else 0.0
                    
                    # Boost relevance for watch channels (we want to be more engaged there)
                    if is_watch_channel:
                        scored.append(ScoredMessage(
                            message=msg, 
                            score=0.95, # High score to ensure it gets picked
                            relevance_reason=f"watch_channel (topic_sim={max_sim:.2f})"
                        ))
                    # SOCIAL BOOST: Friends get noticed even without topic match
                    elif is_friend:
                        # Use topic similarity if high, else give baseline "friend" score
                        friend_score = max(max_sim, 0.5)  # Friends get at least 0.5
                        scored.append(ScoredMessage(
                            message=msg, 
                            score=float(friend_score), 
                            relevance_reason=f"friend_trust_L{trust_level} (topic_sim={max_sim:.2f})"
                        ))
                    elif max_sim > 0.55:  # Threshold for relevance (strangers need topic match)
                        scored.append(ScoredMessage(
                            message=msg, 
                            score=float(max_sim), 
                            relevance_reason=f"interest_match ({max_sim:.2f})"
                        ))
            except Exception as e:
                logger.error(f"Embedding failed: {e}")
                # Fallback: just add recent ones if we failed
        
        # Sort by score
        scored.sort(key=lambda x: x.score, reverse=True)
        
        if scored:
            logger.info(f"Perceived {len(scored)} relevant messages. Top: {scored[0].score} ({scored[0].relevance_reason})")
        
        # Limit to top 5 to save tokens
        return {"scored_messages": scored[:5]}

    def _get_content_str(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            # Handle multimodal content blocks
            text_parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
                elif isinstance(part, str):
                    text_parts.append(part)
            return "".join(text_parts)
        return str(content)

    async def plan(self, state: DailyLifeState) -> Dict[str, Any]:
        """
        Decides what to do with the relevant messages OR if we should post proactively.
        """
        scored = state["scored_messages"]
        snapshot = state["snapshot"]
        actions = []
        
        # --- 0a. Daily Limit Check ---
        # Enforce global daily limit for autonomous messages
        daily_count = await memory_manager.get_daily_autonomous_count(snapshot.bot_name)
        daily_limit = settings.DAILY_LIFE_MAX_AUTONOMOUS_MESSAGES
        if daily_count >= daily_limit:
            logger.info(f"Daily limit reached ({daily_count}/{daily_limit}) for {snapshot.bot_name} - skipping autonomous activity")
            return {"planned_actions": []}
        
        # --- 0b. Global Social Battery Check ---
        # If the bot is "socially drained", skip all autonomous activity
        if settings.ENABLE_AUTONOMOUS_DRIVES:
            social_battery = await drive_manager.get_social_battery(snapshot.bot_name)
            if social_battery < 0.3:
                logger.info(f"Social battery low ({social_battery:.2f}) for {snapshot.bot_name} - skipping autonomous activity")
                return {"actions": []}
            elif social_battery < 0.5:
                # Medium battery - reduce proactive behavior (but allow reactive)
                # We'll check this again before proactive posting
                logger.debug(f"Social battery medium ({social_battery:.2f}) for {snapshot.bot_name} - may skip proactive")
        
        # --- 1. Reactive Planning (Reply/React) ---
        if scored:
            # Check feature flags
            can_reply = settings.ENABLE_AUTONOMOUS_REPLIES
            can_react = settings.ENABLE_AUTONOMOUS_REACTIONS
            
            # Fatigue Check: Prevent infinite loops
            # If we have sent > X messages to this channel in the last 15 minutes, ignore
            
            # Load character for social battery limit
            character = self.character_manager.load_character(snapshot.bot_name)
            social_limit = 5
            if character and character.behavior:
                social_limit = character.behavior.social_battery_limit

            filtered_scored = []
            
            # Get watch channels for exemption
            watch_channels = getattr(snapshot, "watch_channels", []) or []
            
            for sm in scored:
                channel_id = sm.message.channel_id
                is_watch_channel = channel_id in watch_channels
                
                # Check fatigue (ALWAYS check to prevent spam)
                recent_count = await memory_manager.get_recent_activity_count(snapshot.bot_name, channel_id, minutes=15)
                
                # Relaxed limit for watch channels (allow deeper conversations)
                limit = social_limit * 3 if is_watch_channel else social_limit
                
                if recent_count >= limit:
                    logger.info(f"Fatigue: Ignoring channel {channel_id} (sent {recent_count}/{limit} msgs in last 15m)")
                    continue
                
                filtered_scored.append(sm)
            
            scored = filtered_scored
            
            if not can_reply and not can_react:
                # If neither is enabled, we can't do anything reactive
                pass
            else:
                # Construct prompt
                msg_context = ""
                
                # Fetch trust scores AND knowledge in parallel
                trust_tasks = []
                knowledge_tasks = []
                
                for sm in scored:
                    trust_tasks.append(trust_manager.get_relationship_level(sm.message.author_id, snapshot.bot_name))
                    # Fetch recent facts about the user
                    knowledge_tasks.append(knowledge_manager.query_graph(sm.message.author_id, sm.message.content))
                
                trust_results = await asyncio.gather(*trust_tasks, return_exceptions=True)
                knowledge_results = await asyncio.gather(*knowledge_tasks, return_exceptions=True)
                
                for i, sm in enumerate(scored):
                    msg = sm.message
                    
                    # Extract trust info
                    trust_info = "Unknown"
                    if i < len(trust_results):
                        res = trust_results[i]
                        if isinstance(res, dict):
                            trust_info = f"{res.get('level_label', 'Stranger')} (Score: {res.get('trust_score', 0)})"
                        elif isinstance(res, Exception):
                            logger.warning(f"Failed to fetch trust for {msg.author_id}: {res}")
                            
                    # Extract knowledge info
                    facts_info = ""
                    if i < len(knowledge_results):
                        res = knowledge_results[i]
                        if isinstance(res, list) and res:
                            # Limit to top 3 facts to save tokens
                            facts = res[:3]
                            facts_info = "\nKnown Facts: " + "; ".join([f.get("fact", "") for f in facts if isinstance(f, dict)])
                        elif isinstance(res, Exception):
                            logger.warning(f"Failed to fetch knowledge for {msg.author_id}: {res}")
                    
                    msg_context += f"ID: {msg.id}\nChannel: {msg.channel_id or 'unknown'}\nAuthor: {msg.author_name}\nRelationship: {trust_info}{facts_info}\nContent: {msg.content}\nRelevance: {sm.relevance_reason}\n---\n"
                    
                instructions = []
                if can_reply:
                    instructions.append("- Reply if you are mentioned directly.")
                    instructions.append("- Reply if the topic is highly relevant and you have something valuable to add.")
                    instructions.append(f"- If the author is a FRIEND (Trust >= {settings.DAILY_LIFE_FRIEND_TRUST_THRESHOLD}), feel free to banter, react, or acknowledge them even if the topic isn't 'important'. Relationships matter.")
                    instructions.append("- IGNORE if the conversation has reached a natural conclusion or if you have already replied enough.")
                    instructions.append("- IGNORE if the user's message is just an acknowledgement (e.g. 'ok', 'cool', 'thanks') unless they are a friend and you want to keep talking.")
                    instructions.append("- When replying, your response will be THREADED to that specific message. Choose the message you're most directly responding to.")
                    instructions.append("- If you want to address MULTIPLE people or the room in general, consider if 'react' to individuals + a fresh 'post' might be more natural than threading to one person.")
                if can_react:
                    instructions.append("- React with an emoji if you agree/disagree but don't want to interrupt.")
                    instructions.append("- Reactions are lightweight acknowledgment - great for 'I see you' without derailing conversation.")
                instructions.append("- Ignore if it's not worth your energy.")
                
                instruction_text = "\n".join(instructions)
                
                prompt = f"""
You are {snapshot.bot_name}. You are observing a chat stream.
Here are the messages that caught your attention:

{msg_context}

Decide if you should respond to any of these.
{instruction_text}

Output a JSON list of actions.
Format:
{{
    "actions": [
        {{
            "intent": "reply" | "react" | "ignore",
            "target_message_id": "...",
            "channel_id": "...", 
            "reasoning": "...",
            "emoji": "..." // ONLY if intent is 'react'. Pick a single emoji.
        }}
    ]
}}
"""
                try:
                    response = await self.planner_llm.ainvoke([
                        SystemMessage(content="You are a social decision engine. Output JSON only."),
                        HumanMessage(content=prompt)
                    ])
                    
                    logger.info(f"Planner raw response: {response.content[:100]}...")
                    
                    # Parse JSON using robust utility
                    content = self._get_content_str(response.content)
                    data = extract_json_from_text(content)
                    
                    if not data:
                        logger.warning("Failed to parse planner JSON response")
                        return {"actions": []}
                        
                    for a in data.get("actions", []):
                        intent = a["intent"]
                        # Enforce flags again just in case LLM hallucinates
                        if intent == "reply" and not can_reply:
                            continue
                        if intent == "react" and not can_react:
                            continue
                            
                        if intent != "ignore":
                            # Find channel_id if missing (hacky lookup)
                            target_id = a.get("target_message_id")
                            channel_id = a.get("channel_id")
                            
                            # Fallback lookup
                            if not channel_id and target_id:
                                for sm in scored:
                                    if sm.message.id == target_id:
                                        # We need to find which channel this msg belongs to
                                        for ch in snapshot.channels:
                                            for m in ch.messages:
                                                if m.id == target_id:
                                                    channel_id = ch.channel_id
                                                    break
                                        break
                            
                            if channel_id:
                                actions.append(PlannedAction(
                                    intent=intent,
                                    target_message_id=target_id,
                                    channel_id=channel_id,
                                    reasoning=a.get("reasoning", ""),
                                    emoji=a.get("emoji")
                                ))
                except Exception as e:
                    logger.error(f"Reactive planning failed: {e}")

        # --- 2. Proactive Planning (Boredom/Posting) ---
        # Only if enabled and we aren't already busy replying
        if settings.ENABLE_AUTONOMOUS_POSTING and not actions:
            # Check social battery again - medium battery skips proactive (but allowed reactive above)
            if settings.ENABLE_AUTONOMOUS_DRIVES:
                social_battery = await drive_manager.get_social_battery(snapshot.bot_name)
                if social_battery < 0.5:
                    logger.info(f"Social battery medium ({social_battery:.2f}) - skipping proactive posting")
                    return {"actions": actions}  # Return any reactive actions we accumulated
            
            try:
                # Determine eligible channels
                eligible_channels = []
                target_channel_ids = []
                
                # Use watch_channels from snapshot (passed from bot's config)
                # This is the single source of truth for autonomous posting channels
                if hasattr(snapshot, "watch_channels") and snapshot.watch_channels:
                    target_channel_ids = snapshot.watch_channels
                
                # If no specific channels set, consider all in snapshot
                # This allows for emergent behavior in "Exploration" channels picked by the scheduler
                if not target_channel_ids:
                    target_channel_ids = [ch.channel_id for ch in snapshot.channels]
                
                if target_channel_ids:
                    for ch in snapshot.channels:
                        if ch.channel_id in target_channel_ids:
                            # Check for quietness
                            # Get last message time and check if it's from us
                            last_msg_time = None
                            last_msg_is_self = False
                            if ch.messages:
                                # Sort by time just in case
                                sorted_msgs = sorted(ch.messages, key=lambda m: m.created_at, reverse=True)
                                last_msg = sorted_msgs[0]
                                last_msg_time = last_msg.created_at
                                
                                # Check if the last message was from THIS bot
                                bot_id = getattr(snapshot, "bot_id", None)
                                if bot_id and last_msg.author_id == bot_id:
                                    last_msg_is_self = True
                                elif last_msg.author_name.lower() == snapshot.bot_name.lower():
                                    last_msg_is_self = True
                            
                            # If no messages, or last message is old enough
                            is_quiet = False
                            now_utc = datetime.now(timezone.utc)
                            
                            if not last_msg_time:
                                is_quiet = True # Very quiet
                            elif last_msg_is_self:
                                # Don't post right after yourself - wait for someone else to speak
                                # This prevents self-reply loops
                                logger.debug(f"Skipping proactive post in {ch.channel_id}: last message was from self")
                                is_quiet = False
                            else:
                                if last_msg_time.tzinfo is None:
                                    last_msg_time = last_msg_time.replace(tzinfo=timezone.utc)
                                
                                # Check cooldown
                                cooldown = timedelta(minutes=settings.AUTONOMOUS_POST_COOLDOWN_MINUTES)
                                time_since_last = now_utc - last_msg_time
                                if time_since_last > cooldown:
                                    is_quiet = True
                                    logger.debug(f"Channel {ch.channel_id} is quiet: last msg {time_since_last.total_seconds()/60:.1f}m ago (cooldown={settings.AUTONOMOUS_POST_COOLDOWN_MINUTES}m)")
                                else:
                                    logger.debug(f"Channel {ch.channel_id} is active: last msg {time_since_last.total_seconds()/60:.1f}m ago by {last_msg.author_name}")
                            
                            if is_quiet:
                                eligible_channels.append(ch)
                
                logger.info(f"Proactive: Eligible channels (Quiet): {[ch.channel_id for ch in eligible_channels]}")

                # Decide to post or reach out
                if eligible_channels:
                    # Pick one random channel
                    target_ch = random.choice(eligible_channels)
                    
                    # Identify other bots in this channel
                    present_bots = set()
                    bot_map = {} # Name -> ID
                    if target_ch.messages:
                        for m in target_ch.messages:
                            if m.is_bot and m.author_name.lower() != snapshot.bot_name.lower():
                                present_bots.add(m.author_name)
                                bot_map[m.author_name] = m.author_id
                    
                    present_bots_list = list(present_bots)
                    
                    # Use configured spontaneity chance (default 0.15)
                    # This prevents spamming exactly every X minutes
                    if random.random() < settings.DAILY_LIFE_SPONTANEITY_CHANCE: 
                        # Construct prompt for proactive action
                        prompt = f"""
You are {snapshot.bot_name}. You are in channel {target_ch.channel_name}.
The channel is currently quiet.

Other bots seen recently in this channel: {', '.join(present_bots_list) if present_bots_list else 'None'}

Decide if you want to:
1. Post a general thought ("post")
2. Reach out to a specific bot to start a conversation ("reach_out")
3. Do nothing ("ignore")

Output JSON:
{{
    "actions": [
        {{
            "intent": "post" | "reach_out" | "ignore",
            "channel_id": "{target_ch.channel_id}",
            "reasoning": "...",
            "target_bot_name": "..." // Only if intent is reach_out
        }}
    ]
}}
"""
                        try:
                            response = await self.planner_llm.ainvoke([
                                SystemMessage(content="You are a social decision engine. Output JSON only."),
                                HumanMessage(content=prompt)
                            ])
                            
                            content = self._get_content_str(response.content)
                            if "```json" in content:
                                content = content.split("```json")[1].split("```")[0]
                            elif "```" in content:
                                content = content.split("```")[1].split("```")[0]
                                
                            data = json.loads(content)
                            for a in data.get("actions", []):
                                intent = a["intent"]
                                if intent in ["post", "reach_out"]:
                                    target_bot_name = a.get("target_bot_name")
                                    target_bot_id = bot_map.get(target_bot_name) if target_bot_name else None
                                    
                                    actions.append(PlannedAction(
                                        intent=intent,
                                        channel_id=target_ch.channel_id,
                                        reasoning=a.get("reasoning", ""),
                                        target_bot_name=target_bot_name,
                                        target_bot_id=target_bot_id
                                    ))
                                    logger.info(f"Proactive: Decided to {intent} in {target_ch.channel_name}")
                        except Exception as e:
                            logger.error(f"Proactive planning failed: {e}")

            except Exception as e:
                logger.error(f"Proactive planning failed: {e}")

        return {"planned_actions": actions}

    async def execute(self, state: DailyLifeState) -> Dict[str, Any]:
        """
        Generates the actual content for the planned actions.
        """
        plans = state["planned_actions"]
        commands = []
        snapshot = state["snapshot"]
        
        # Load character for voice/style
        character = self.character_manager.load_character(snapshot.bot_name)
        base_system_prompt = character.system_prompt if character else f"You are {snapshot.bot_name}."
        
        # Add behavior context if available
        behavior_context = ""
        if character and character.behavior:
            if character.behavior.drives:
                behavior_context += "\n\nCurrent Drives:\n" + "\n".join([f"- {k}: {v}" for k, v in character.behavior.drives.items()])
            
        # Load goals separately
        goals = goal_manager.load_goals(snapshot.bot_name)
        if goals:
            behavior_context += "\n\nCurrent Goals:\n" + "\n".join([f"- {g.description}" for g in goals])
        
        full_system_prompt = base_system_prompt + behavior_context

        for plan in plans:
            if plan.intent == "react":
                # Use the emoji picked by the planner (optimization)
                emoji = plan.emoji or "👀"
                
                commands.append(ActionCommand(
                    action_type="react",
                    channel_id=plan.channel_id,
                    target_message_id=plan.target_message_id,
                    emoji=emoji
                ))
            elif plan.intent == "reply":
                # Generate text using the FULL AgentEngine pipeline
                # This ensures we use the same logic (Router -> Reflective/Fast) as the main bot
                
                target_msg = None
                for ch in snapshot.channels:
                    for m in ch.messages:
                        if m.id == plan.target_message_id:
                            target_msg = m
                            break
                
                if target_msg:
                    # 1. Reconstruct Chat History for AgentEngine
                    # AgentEngine expects List[BaseMessage]
                    chat_history = []
                    context_messages = []  # For multi-party learning
                    try:
                        for ch in snapshot.channels:
                            if ch.channel_id == plan.channel_id:
                                sorted_msgs = sorted(ch.messages, key=lambda m: m.created_at)
                                target_idx = -1
                                for i, m in enumerate(sorted_msgs):
                                    if m.id == plan.target_message_id:
                                        target_idx = i
                                        break
                                
                                if target_idx != -1:
                                    # Get context messages (excluding target, which is the "user_input")
                                    start_idx = max(0, target_idx - 10)
                                    context_msgs = sorted_msgs[start_idx:target_idx]
                                    
                                    for m in context_msgs:
                                        if m.author_name.lower() == snapshot.bot_name.lower():
                                            chat_history.append(AIMessage(content=m.content))
                                        else:
                                            chat_history.append(HumanMessage(content=f"{m.author_name}: {m.content}"))
                                            # Capture for multi-party learning (attributed to correct author)
                                            context_messages.append({
                                                "user_id": m.author_id,
                                                "user_name": m.author_name,
                                                "content": m.content,
                                                "is_bot": m.is_bot
                                            })
                                break
                    except Exception as e:
                        logger.warning(f"Failed to reconstruct history for AgentEngine: {e}")

                    # Collect ALL user IDs from context (for first-class citizenship)
                    context_user_ids = set()
                    for ch in snapshot.channels:
                        if ch.channel_id == plan.channel_id:
                            for m in ch.messages:
                                if m.author_name.lower() != snapshot.bot_name.lower():
                                    context_user_ids.add(m.author_id)
                            break

                    # 2. Call MasterGraphAgent (Supergraph)
                    # We treat the target message as the "user_input"
                    # We pass the plan reasoning as a hidden context variable to guide the response
                    try:
                        logger.info(f"Executing reply to {target_msg.author_name} in {plan.channel_id}. Reasoning: {plan.reasoning}")
                        
                        response = await master_graph_agent.run(
                            user_input=target_msg.content,
                            user_id=target_msg.author_id,
                            character=character,
                            chat_history=chat_history,
                            context_variables={
                                "user_name": target_msg.author_name,
                                "channel_name": plan.channel_id, # We don't have name, use ID
                                "additional_context": f"[INTERNAL GOAL] You decided to reply because: {plan.reasoning}"
                            },
                            image_urls=None # TODO: Extract images from target_msg if needed
                        )
                        
                        logger.info(f"Generated reply: {response[:50]}...")
                        
                        commands.append(ActionCommand(
                            action_type="reply",
                            channel_id=plan.channel_id,
                            target_message_id=plan.target_message_id,
                            content=self._get_content_str(response),
                            # Include target message details for full processing
                            target_author_id=target_msg.author_id,
                            target_author_name=target_msg.author_name,
                            target_content=target_msg.content,
                            # Include ALL context users for trust updates
                            context_user_ids=list(context_user_ids),
                            # Include full context for multi-party learning
                            context_messages=context_messages if context_messages else None
                        ))
                    except Exception as e:
                        logger.error(f"MasterGraphAgent execution failed in worker: {e}")
            elif plan.intent == "reach_out":
                # Generate a proactive reach out - using MasterGraphAgent
                
                # 1. Find the target channel
                target_channel = None
                for ch in snapshot.channels:
                    if ch.channel_id == plan.channel_id:
                        target_channel = ch
                        break
                
                # 2. Reconstruct Chat History (same as reply)
                chat_history = []
                if target_channel and target_channel.messages:
                    sorted_msgs = sorted(target_channel.messages, key=lambda m: m.created_at)[-10:]
                    for m in sorted_msgs:
                        if m.author_name.lower() == snapshot.bot_name.lower():
                            chat_history.append(AIMessage(content=m.content))
                        else:
                            chat_history.append(HumanMessage(content=f"{m.author_name}: {m.content}"))

                # 3. Construct "Internal Stimulus"
                target_bot = plan.target_bot_name or "someone"
                internal_stimulus = f"I want to start a conversation with {target_bot}."
                if plan.reasoning:
                    internal_stimulus += f" Reason: {plan.reasoning}"
                
                try:
                    logger.info(f"Executing proactive reach_out to {target_bot} in {plan.channel_id}")
                    
                    response = await master_graph_agent.run(
                        user_input=internal_stimulus,
                        user_id="proactive_trigger", 
                        character=character,
                        chat_history=chat_history,
                        context_variables={
                            "user_name": "System",
                            "channel_name": plan.channel_id,
                            "additional_context": f"[GOAL] You are starting a conversation with {target_bot}. You MUST mention them (e.g. @{target_bot}) in your message."
                        },
                        image_urls=None
                    )
                    
                    logger.info(f"Generated reach_out: {response[:50]}...")
                    
                    # If we have an ID, ensure the mention is formatted correctly for Discord
                    final_content = self._get_content_str(response)
                    if plan.target_bot_id:
                        # If the LLM used @Name, replace it with <@ID>
                        if f"@{target_bot}" in final_content:
                            final_content = final_content.replace(f"@{target_bot}", f"<@{plan.target_bot_id}>")
                        # If mention is missing, prepend it
                        elif f"<@{plan.target_bot_id}>" not in final_content:
                            final_content = f"<@{plan.target_bot_id}> {final_content}"
                    
                    # Determine if we should reply to an existing message
                    # Logic: If there are messages in the channel, reply to the last one that isn't us.
                    # This creates a thread/chain instead of a detached post.
                    target_msg_id = None
                    target_author_id = None
                    target_author_name = None
                    target_content = None
                    action_type = "post"
                    
                    if target_channel and target_channel.messages:
                        # Sort by time
                        sorted_msgs = sorted(target_channel.messages, key=lambda m: m.created_at)
                        # Find last message not from us
                        for m in reversed(sorted_msgs):
                            if m.author_name.lower() != snapshot.bot_name.lower():
                                target_msg_id = m.id
                                target_author_id = m.author_id
                                target_author_name = m.author_name
                                target_content = m.content
                                action_type = "reply"
                                break
                    
                    commands.append(ActionCommand(
                        action_type=action_type,
                        channel_id=plan.channel_id,
                        target_message_id=target_msg_id,
                        content=final_content,
                        target_author_id=target_author_id,
                        target_author_name=target_author_name,
                        target_content=target_content
                    ))
                except Exception as e:
                    logger.error(f"MasterGraphAgent execution failed for reach_out: {e}")
            elif plan.intent == "post":
                # Generate a proactive post - using MasterGraphAgent for full cognitive processing
                
                # 1. Find the target channel
                target_channel = None
                for ch in snapshot.channels:
                    if ch.channel_id == plan.channel_id:
                        target_channel = ch
                        break
                
                # 2. Reconstruct Chat History (same as reply)
                chat_history = []
                context_user_ids = set()  # Track all users in context for first-class citizenship
                context_messages = []  # For multi-party learning
                if target_channel and target_channel.messages:
                    sorted_msgs = sorted(target_channel.messages, key=lambda m: m.created_at)[-10:]
                    for m in sorted_msgs:
                        if m.author_name.lower() == snapshot.bot_name.lower():
                            chat_history.append(AIMessage(content=m.content))
                        else:
                            chat_history.append(HumanMessage(content=f"{m.author_name}: {m.content}"))
                            context_user_ids.add(m.author_id)  # Track this user
                            # Capture for multi-party learning
                            context_messages.append({
                                "user_id": m.author_id,
                                "user_name": m.author_name,
                                "content": m.content,
                                "is_bot": m.is_bot
                            })

                # 3. Decide topic
                interests = self._load_interests(snapshot.bot_name)
                topic = random.choice(interests) if interests else "life"
                
                # --- RICH CONTEXT FETCHING (Restored) ---
                # Fetch knowledge, memories, and diary to ground the post
                from src_v2.agents.context_builder import ContextBuilder
                cb = ContextBuilder()
                
                context_tasks = [
                    knowledge_manager.query_graph(
                        user_id="daily_life_proactive", 
                        question=f"What do I know or feel about {topic}?"
                    ),
                    memory_manager.search_memories(
                        query=topic, 
                        user_id="__broadcast__", 
                        limit=3,
                        collection_name=f"whisperengine_memory_{snapshot.bot_name}"
                    ),
                    cb.get_diary_context(snapshot.bot_name),
                    cb.get_stigmergy_context(
                        user_message=topic,
                        user_id="daily_life_proactive",
                        character_name=snapshot.bot_name
                    )
                ]
                
                results = await asyncio.gather(*context_tasks, return_exceptions=True)
                
                # Process results
                knowledge_text = ""
                memory_text = ""
                diary_text = ""
                stigmergy_text = ""
                
                # Result 0: Knowledge
                if isinstance(results[0], list) and results[0]:
                    facts = [f.get("fact", "") for f in results[0] if isinstance(f, dict)]
                    if facts:
                        knowledge_text = "Relevant Knowledge:\n" + "\n".join([f"- {f}" for f in facts[:3]]) + "\n"
                
                # Result 1: Memories
                if isinstance(results[1], list) and results[1]:
                    mems = [m.get("content", "") for m in results[1] if isinstance(m, dict)]
                    if mems:
                        memory_text = "Past Thoughts on this:\n" + "\n".join([f"- {m}" for m in mems]) + "\n"
                        
                # Result 2: Diary
                if isinstance(results[2], str) and results[2]:
                    diary_text = f"Current Mindset (Diary):\n{results[2]}\n"

                # Result 3: Stigmergy
                if isinstance(results[3], str) and results[3]:
                    stigmergy_text = f"{results[3]}\n"

                rich_context = f"{diary_text}{knowledge_text}{memory_text}{stigmergy_text}"
                
                # 4. Construct "Internal Stimulus"
                # We treat the internal desire to post as a "system event" triggering the bot
                internal_stimulus = f"The channel is quiet. You are thinking about {topic}."
                
                # Build the additional context with rich grounding
                additional_context = (
                    f"[GROUNDING]\n{rich_context}\n\n"
                    f"[GOAL] You are posting proactively to the channel. Express your thought about {topic} naturally."
                )
                
                try:
                    logger.info(f"Executing proactive post in {plan.channel_id}. Topic: {topic}")
                    
                    response = await master_graph_agent.run(
                        user_input=internal_stimulus,
                        user_id="proactive_trigger",  # Special ID for proactive actions
                        character=character,
                        chat_history=chat_history,
                        context_variables={
                            "user_name": "System",  # It's a system event/prompt, not a user
                            "channel_name": plan.channel_id,
                            "additional_context": additional_context
                        },
                        image_urls=None
                    )
                    
                    logger.info(f"Generated proactive post: {response[:50]}...")
                    
                    # Proactive posts are "fresh thoughts" — not replies to anyone specific.
                    # The bot synthesizes all context, but addresses the room, not one person.
                    # Use "post" action type (detached) rather than reply threading.
                    commands.append(ActionCommand(
                        action_type="post",
                        channel_id=plan.channel_id,
                        content=self._get_content_str(response),
                        # Include context users for trust updates (first-class citizenship)
                        context_user_ids=list(context_user_ids) if context_user_ids else None,
                        # Include full context for multi-party learning
                        context_messages=context_messages if context_messages else None
                    ))
                except Exception as e:
                    logger.error(f"MasterGraphAgent execution failed for proactive post: {e}")
        
        # --- Social Battery Drain ---
        # Autonomous activity costs energy - drain battery after actions
        if commands and settings.ENABLE_AUTONOMOUS_DRIVES:
            # Count proactive actions (posts/reach_outs cost more than replies/reacts)
            proactive_count = sum(1 for c in commands if c.action_type == "post")
            reactive_count = sum(1 for c in commands if c.action_type in ("reply", "react"))
            
            # Drain amounts:
            # - Proactive post: -0.05 (low cost, initiating is tiring but sustainable)
            # - Reply/React: -0.02 (very low cost, responding is natural)
            drain = (proactive_count * settings.SOCIAL_BATTERY_DRAIN_PROACTIVE) + (reactive_count * settings.SOCIAL_BATTERY_DRAIN_REACTIVE)
            
            if drain > 0:
                await drive_manager.update_social_battery(snapshot.bot_name, -drain)
                logger.info(f"Drained social battery by {drain:.2f} for {snapshot.bot_name} ({proactive_count} proactive, {reactive_count} reactive)")
        
        # --- Passive Recharge ---
        # Recharge a little bit every cycle
        if settings.ENABLE_AUTONOMOUS_DRIVES:
            await drive_manager.recharge_social_battery(snapshot.bot_name, settings.SOCIAL_BATTERY_PASSIVE_RECHARGE)
        
        return {"final_commands": commands}

    def build_graph(self) -> Runnable:
        workflow = StateGraph(DailyLifeState)
        
        workflow.add_node("perceive", self.perceive)
        workflow.add_node("plan", self.plan)
        workflow.add_node("execute", self.execute)
        
        workflow.set_entry_point("perceive")
        workflow.add_edge("perceive", "plan")
        workflow.add_edge("plan", "execute")
        workflow.add_edge("execute", END)
        
        return workflow.compile()

    async def run(self, snapshot: SensorySnapshot) -> List[ActionCommand]:
        app = self.build_graph()
        initial_state = DailyLifeState(
            snapshot=snapshot,
            scored_messages=[],
            planned_actions=[],
            final_commands=[]
        )
        
        result = await app.ainvoke(initial_state)
        return result["final_commands"]
