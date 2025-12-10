import asyncio
import operator
import os
import yaml
import random
import numpy as np
from typing import List, Dict, Any, TypedDict, Annotated, Literal, Optional
from datetime import datetime, timedelta, timezone
from loguru import logger
from pydantic import BaseModel

from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage, AIMessage
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
                with open(path, "r") as f:
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
        
        interests = self._load_interests(bot_name)
        
        # Flatten messages from all channels
        all_messages = []
        for channel in snapshot.channels:
            for msg in channel.messages:
                # Skip own messages
                if msg.author_name.lower() == bot_name.lower():
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
                    # Max similarity against any interest
                    # Dot product of normalized vectors = cosine similarity
                    # FastEmbed vectors are normalized
                    sims = [np.dot(msg_emb, int_emb) for int_emb in interest_embeddings]
                    max_sim = max(sims) if sims else 0.0
                    
                    if max_sim > 0.55:  # Threshold for relevance
                        scored.append(ScoredMessage(
                            message=relevant_messages[i], 
                            score=float(max_sim), 
                            relevance_reason=f"interest_match ({max_sim:.2f})"
                        ))
            except Exception as e:
                logger.error(f"Embedding failed: {e}")
                # Fallback: just add recent ones if we failed
                pass
        
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
                    import json
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
                    import random
                    target_ch = random.choice(eligible_channels)
                    
                    # 10% chance to post if quiet (don't post EVERY time we check)
                    # This prevents spamming exactly every X minutes
                    if random.random() < 0.1: 
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
                # Pick an emoji
                commands.append(ActionCommand(
                    action_type="react",
                    channel_id=plan.channel_id,
                    target_message_id=plan.target_message_id,
                    emoji="👀" # Placeholder, should ask LLM
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
                # Generate a proactive post
                interests = self._load_interests(snapshot.bot_name)
                import random
                topic = random.choice(interests) if interests else "life"
                
                prompt = f"""
You are posting in a quiet channel.
Topic: {topic}
Reasoning: {plan.reasoning}

Write a short, engaging thought or observation to spark conversation.
Do not be generic. Be specific to your character.
"""
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
