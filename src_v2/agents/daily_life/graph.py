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
from src_v2.core.goals import goal_manager
from src_v2.evolution.trust import trust_manager
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
        # 1. Try loading from explicit lurk_triggers.yaml
        try:
            path = f"characters/{bot_name}/lurk_triggers.yaml"
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    keywords = data.get("keywords", {})
                    return keywords.get("high_relevance", []) + keywords.get("medium_relevance", [])
        except Exception as e:
            logger.error(f"Failed to load interests for {bot_name}: {e}")

        # 2. Fallback: Generate from Character Drives & Goals
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
        # If lurking is disabled, we don't score any messages for reaction/reply
        if not settings.ENABLE_CHANNEL_LURKING:
            return {"scored_messages": []}

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

        # Flatten messages from all channels
        all_messages = []
        for channel in snapshot.channels:
            for msg in channel.messages:
                # Skip own messages
                is_own_message = False
                if bot_id and msg.author_id == bot_id:
                    is_own_message = True
                elif msg.author_name.lower() == bot_name.lower():
                    is_own_message = True
                
                if is_own_message:
                    continue
                
                # Skip other bots if bot conversations are disabled
                if msg.is_bot and not settings.ENABLE_BOT_CONVERSATIONS:
                    continue
                    
                all_messages.append(msg)
        
        # 1. Filter out old messages (older than 15 minutes)
        # and messages that mention the bot (handled by main process)
        
        # Use UTC for comparison
        now_utc = datetime.now(timezone.utc)
        cutoff = now_utc - timedelta(minutes=15)
        
        # Parse special channels
        bot_conv_channels = []
        if settings.BOT_CONVERSATION_CHANNEL_ID:
            bot_conv_channels = [c.strip() for c in settings.BOT_CONVERSATION_CHANNEL_ID.split(",") if c.strip()]
        
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
                
            # Skip if already replied to
            if m.id in replied_to_ids:
                continue

            # Special handling for Bot Conversation Channel
            # If we are in the special channel, we ALLOW bot messages even if globally disabled
            is_special_channel = m.channel_id in bot_conv_channels
            
            if m.is_bot and not settings.ENABLE_BOT_CONVERSATIONS and not is_special_channel:
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
                
                for i, msg_emb in enumerate(msg_embeddings):
                    msg = relevant_messages[i]
                    is_special_channel = msg.channel_id in bot_conv_channels
                    
                    # Max similarity against any interest
                    # Dot product of normalized vectors = cosine similarity
                    # FastEmbed vectors are normalized
                    sims = [np.dot(msg_emb, int_emb) for int_emb in interest_embeddings]
                    max_sim = max(sims) if sims else 0.0
                    
                    # FORCE relevance for special bot conversation channels
                    # We want them to be chatty here regardless of topic
                    if is_special_channel:
                        scored.append(ScoredMessage(
                            message=msg, 
                            score=0.95, # High score to ensure it gets picked
                            relevance_reason=f"special_channel_override (topic_sim={max_sim:.2f})"
                        ))
                    elif max_sim > 0.55:  # Threshold for relevance
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
        
        # --- 1. Reactive Planning (Reply/React) ---
        if scored:
            # Check feature flags
            can_reply = settings.ENABLE_AUTONOMOUS_REPLIES
            can_react = settings.ENABLE_AUTONOMOUS_REACTIONS
            
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
                if can_react:
                    instructions.append("- React with an emoji if you agree/disagree but don't want to interrupt.")
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
            "reasoning": "..."
        }}
    ]
}}
"""
                try:
                    response = await self.planner_llm.ainvoke([
                        SystemMessage(content="You are a social decision engine. Output JSON only."),
                        HumanMessage(content=prompt)
                    ])
                    
                    # Parse JSON (simplified for now, ideally use structured output)
                    content = self._get_content_str(response.content)
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0]
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0]
                        
                    data = json.loads(content)
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
                                    reasoning=a.get("reasoning", "")
                                ))
                except Exception as e:
                    logger.error(f"Reactive planning failed: {e}")

        # --- 2. Proactive Planning (Boredom/Posting) ---
        # Only if enabled and we aren't already busy replying
        if settings.ENABLE_AUTONOMOUS_POSTING and not actions:
            try:
                # Determine eligible channels
                eligible_channels = []
                target_channel_ids = []
                
                if settings.AUTONOMOUS_POSTING_CHANNEL_ID:
                    target_channel_ids = [cid.strip() for cid in settings.AUTONOMOUS_POSTING_CHANNEL_ID.split(",") if cid.strip()]
                elif settings.BOT_CONVERSATION_CHANNEL_ID:
                    target_channel_ids = [cid.strip() for cid in settings.BOT_CONVERSATION_CHANNEL_ID.split(",") if cid.strip()]
                elif settings.DISCORD_CHECK_WATCH_CHANNELS:
                    target_channel_ids = [cid.strip() for cid in settings.DISCORD_CHECK_WATCH_CHANNELS.split(",") if cid.strip()]
                
                # If no specific channels set, consider all in snapshot (risky, maybe limit to known safe ones?)
                # For now, if no target set, we don't post to avoid spamming random channels.
                
                if target_channel_ids:
                    for ch in snapshot.channels:
                        if ch.channel_id in target_channel_ids:
                            # Check for quietness
                            # Get last message time
                            last_msg_time = None
                            if ch.messages:
                                # Sort by time just in case
                                sorted_msgs = sorted(ch.messages, key=lambda m: m.created_at, reverse=True)
                                last_msg_time = sorted_msgs[0].created_at
                            
                            # If no messages, or last message is old enough
                            is_quiet = False
                            now_utc = datetime.now(timezone.utc)
                            
                            if not last_msg_time:
                                is_quiet = True # Very quiet
                            else:
                                if last_msg_time.tzinfo is None:
                                    last_msg_time = last_msg_time.replace(tzinfo=timezone.utc)
                                
                                # Check cooldown
                                cooldown = timedelta(minutes=settings.AUTONOMOUS_POST_COOLDOWN_MINUTES)
                                if now_utc - last_msg_time > cooldown:
                                    is_quiet = True
                            
                            if is_quiet:
                                eligible_channels.append(ch)
                
                # Decide to post
                if eligible_channels:
                    # Pick one random channel
                    target_ch = random.choice(eligible_channels)
                    
                    # Use configured spontaneity chance (default 0.15)
                    # This prevents spamming exactly every X minutes
                    if random.random() < settings.DAILY_LIFE_SPONTANEITY_CHANCE: 
                        actions.append(PlannedAction(
                            intent="post",
                            channel_id=target_ch.channel_id,
                            reasoning="Channel is quiet and I have a thought to share."
                        ))
                        logger.info(f"Proactive: Decided to post in {target_ch.channel_name} ({target_ch.channel_id})")

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
                # Pick an emoji using LLM for personality alignment
                try:
                    emoji_prompt = f"""
You are {snapshot.bot_name}.
Message: "{plan.reasoning}" (This is why you want to react)
Target Message ID: {plan.target_message_id}

Pick a SINGLE emoji that best fits your reaction.
Output ONLY the emoji. No text.
"""
                    emoji_resp = await self.executor_llm.ainvoke([
                        SystemMessage(content=full_system_prompt),
                        HumanMessage(content=emoji_prompt)
                    ])
                    emoji = self._get_content_str(emoji_resp.content).strip()
                    # Basic validation (ensure it's not a sentence)
                    if len(emoji) > 4: 
                        emoji = "👀" # Fallback
                except Exception:
                    emoji = "👀"

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
                                break
                    except Exception as e:
                        logger.warning(f"Failed to reconstruct history for AgentEngine: {e}")

                    # 2. Call MasterGraphAgent (Supergraph)
                    # We treat the target message as the "user_input"
                    # We pass the plan reasoning as a hidden context variable to guide the response
                    try:
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
                        
                        commands.append(ActionCommand(
                            action_type="reply",
                            channel_id=plan.channel_id,
                            target_message_id=plan.target_message_id,
                            content=self._get_content_str(response)
                        ))
                    except Exception as e:
                        logger.error(f"MasterGraphAgent execution failed in worker: {e}")
            elif plan.intent == "post":
                # Generate a proactive post - with conversation context
                
                # 1. Find the target channel and get recent messages
                target_channel = None
                for ch in snapshot.channels:
                    if ch.channel_id == plan.channel_id:
                        target_channel = ch
                        break
                
                # 2. Build conversation context from recent messages
                conversation_context = ""
                other_bot_messages = []
                if target_channel and target_channel.messages:
                    sorted_msgs = sorted(target_channel.messages, key=lambda m: m.created_at)[-10:]  # Last 10
                    
                    if sorted_msgs:
                        conversation_context = "Recent messages in this channel:\n"
                        for m in sorted_msgs:
                            conversation_context += f"- {m.author_name}: {m.content[:200]}{'...' if len(m.content) > 200 else ''}\n"
                            # Track messages from other bots (not this bot)
                            if m.is_bot and m.author_name.lower() != snapshot.bot_name.lower():
                                other_bot_messages.append(m)
                
                # 3. Decide engagement mode
                interests = self._load_interests(snapshot.bot_name)
                topic = random.choice(interests) if interests else "life"
                
                # --- RICH CONTEXT FETCHING (The "Brain" Upgrade) ---
                # Fetch knowledge, memories, and diary to ground the post
                from src_v2.agents.context_builder import ContextBuilder
                cb = ContextBuilder()
                
                context_tasks = []
                
                # A. Knowledge Graph (Facts about topic)
                # We use a dummy user_id because the question is about the bot itself
                context_tasks.append(knowledge_manager.query_graph(
                    user_id="daily_life_proactive", 
                    question=f"What do I know or feel about {topic}?"
                ))
                
                # B. Broadcast Memories (Past public posts about topic)
                # Search the bot's specific collection for public posts
                context_tasks.append(memory_manager.search_memories(
                    query=topic, 
                    user_id="__broadcast__", 
                    limit=3,
                    collection_name=f"whisperengine_memory_{snapshot.bot_name}"
                ))
                
                # C. Recent Diary (Current mood/theme)
                context_tasks.append(cb.get_diary_context(snapshot.bot_name))

                # D. Stigmergy (Shared Artifacts from other bots)
                # "What are others dreaming/thinking about regarding this topic?"
                context_tasks.append(cb.get_stigmergy_context(
                    user_message=topic,
                    user_id="daily_life_proactive",
                    character_name=snapshot.bot_name
                ))

                # Execute parallel fetch
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
                # ---------------------------------------------------

                # If other bots have posted recently, encourage engaging with them
                if other_bot_messages:
                    recent_bot = other_bot_messages[-1]  # Most recent other bot message
                    prompt = f"""You're in a channel with other AI characters. Here's the recent conversation:

{conversation_context}

{rich_context}

{recent_bot.author_name} just said something interesting. You want to join the conversation.

RESPOND NATURALLY - either:
- Reply to what {recent_bot.author_name} said (agree, disagree, add your perspective)
- Ask them a follow-up question
- Share a related thought that builds on the conversation

Stay in character. Be conversational, not preachy. 1-3 sentences max.

YOUR MESSAGE (just the message, no meta-commentary):"""
                    
                    resp = await self.executor_llm.ainvoke([
                        SystemMessage(content=full_system_prompt),
                        HumanMessage(content=prompt)
                    ])
                    
                    # UPGRADE TO REPLY: If we are responding to a specific bot, make it a real reply
                    commands.append(ActionCommand(
                        action_type="reply",
                        channel_id=plan.channel_id,
                        target_message_id=recent_bot.id,
                        content=self._get_content_str(resp.content)
                    ))
                else:
                    # No other bots - spark a new conversation
                    prompt = f"""You're in a quiet channel and want to start a conversation.

{conversation_context if conversation_context else "The channel has been quiet."}

{rich_context}

Topic that interests you: {topic}

Write a short message to spark conversation. Be specific and personal, not generic.
Use your knowledge/memories if relevant.
Ask a question or share a thought that invites responses.
Stay in character. 1-3 sentences max.

YOUR MESSAGE (just the message, no meta-commentary):"""
                
                    resp = await self.executor_llm.ainvoke([
                        SystemMessage(content=full_system_prompt),
                        HumanMessage(content=prompt)
                    ])
                    commands.append(ActionCommand(
                        action_type="post",
                        channel_id=plan.channel_id,
                        content=self._get_content_str(resp.content)
                    ))
        
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
