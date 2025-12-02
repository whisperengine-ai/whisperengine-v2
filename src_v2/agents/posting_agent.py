import os
import random
from typing import List, Optional, Dict, Any
from loguru import logger
from langchain_core.messages import SystemMessage, HumanMessage

from src_v2.core.goals import goal_manager, Goal
from src_v2.core.behavior import load_behavior_profile
from src_v2.core.character import CharacterManager
from src_v2.agents.llm_factory import create_llm
from src_v2.discord.bot import bot  # We might need to send message via bot, or return it
# Note: In a worker context, we can't use the discord.Client directly if it's not running in the same process.
# The worker should probably just generate the content and put it in a "broadcast" queue or similar.
# But for now, let's assume the worker generates it and we have a mechanism to send it.
# Actually, the roadmap says: "ActivityExecutor (per-bot process) - Executes queued actions via Discord API"
# So the worker (PostingAgent) should probably just DECIDE to post and GENERATE the content, 
# then enqueue it to the bot's specific broadcast queue.

from src_v2.broadcast.manager import broadcast_manager, PostType
from src_v2.tools.web_search import web_search_tool

class GoalDrivenTopicSelector:
    """
    Selects topics for autonomous posts based on character identity and goals.
    """
    def __init__(self, characters_dir: str = "characters"):
        self.characters_dir = characters_dir

    def select_topic(self, character_name: str) -> Optional[tuple[str, str]]:
        """
        Selects a topic string based on weighted goals and drives.
        Returns (topic_description, category)
        """
        # 1. Load goals and behavior
        goals = goal_manager.load_goals(character_name)
        profile = load_behavior_profile(os.path.join(self.characters_dir, character_name))
        
        if not goals or not profile:
            logger.warning(f"Could not load goals or profile for {character_name}")
            return None

        # 2. Weight categories by drive intensity
        # Map goal categories to drives if possible, or just use goal priority
        # For simplicity V1: Just use goal priority
        
        if not goals:
            return ("life in general", "general")

        # Weighted random selection based on priority
        total_priority = sum(g.priority for g in goals)
        if total_priority == 0:
            g = random.choice(goals)
            return (g.description, g.category)

        pick = random.uniform(0, total_priority)
        current = 0
        selected_goal = goals[0]
        
        for goal in goals:
            current += goal.priority
            if current > pick:
                selected_goal = goal
                break
        
        return (selected_goal.description, selected_goal.category)

class PostingAgent:
    """
    Agent responsible for generating autonomous posts.
    """
    def __init__(self):
        self.selector = GoalDrivenTopicSelector()
        self.char_manager = CharacterManager()

    async def generate_and_schedule_post(self, character_name: str) -> bool:
        """
        Generates a post and schedules it via BroadcastManager.
        """
        logger.info(f"PostingAgent: Generating post for {character_name}")
        
        # 1. Select Topic
        selection = self.selector.select_topic(character_name)
        if not selection:
            logger.warning(f"No topic selected for {character_name}")
            return False
            
        topic, category = selection
        
        # 2. Load Character Context
        character = self.char_manager.load_character(character_name)
        if not character:
            return False

        # 3. Perform Web Search (if needed)
        search_context = ""
        if category in ["expertise", "current_events", "mission"]:
            try:
                # Construct a search query based on the topic
                # For now, just use the topic description as the query
                # In the future, we could use an LLM to generate a better query
                logger.info(f"Performing web search for topic: {topic}")
                search_results = await web_search_tool._arun(topic, max_results=3)
                search_context = f"\n\nSEARCH RESULTS (Use these to add factual depth):\n{search_results}\n"
            except Exception as e:
                logger.error(f"Web search failed: {e}")

        # 4. Generate Content using LLM
        # We use the 'main' model (the character's primary voice) to ensure the personality is correct.
        # We also use the character's specific temperature and model if defined.
        temp = character.behavior.temperature if character.behavior else 0.7
        model = character.behavior.model_name if character.behavior else None
        llm = create_llm(mode="main", temperature=temp, model_name=model) 
        
        system_prompt = character.system_prompt
        
        prompt = f"""
You are posting a message to a public Discord channel where your friends hang out.
The server has been quiet, so you want to share a thought to spark conversation.

Your current goal/topic is: {topic}
Category: {category}
{search_context}

Instructions:
1. Write a short, engaging message (1-3 sentences).
2. Stay in character.
3. Do NOT use hashtags.
4. Do NOT act like a robot or assistant. Be casual.
5. If you have search results, use them to share a cool fact or news item, but keep it conversational.
6. If the topic is "relationship", ask a question to the group.

Write ONLY the message content.
"""
        
        try:
            response = await llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ])
            content = response.content.strip()
            
            # Remove quotes if present
            if content.startswith('"') and content.endswith('"'):
                content = content[1:-1]
                
            logger.info(f"Generated post for {character_name}: {content}")
            
            # 4. Schedule via BroadcastManager
            # This puts it into the bot's specific queue (whisper:broadcast:queue:{bot_name})
            # The bot instance (running in a separate container) will pick it up and send it to Discord.
            await broadcast_manager.queue_broadcast(
                content=content,
                post_type=PostType.MUSING, 
                character_name=character_name
            )
            return True
            
        except Exception as e:
            logger.error(f"Error generating post for {character_name}: {e}")
            return False

# Worker Entry Point
async def run_posting_agent(ctx: Dict[str, Any], bot_name: str) -> None:
    """
    Worker task to run the posting agent.
    """
    agent = PostingAgent()
    await agent.generate_and_schedule_post(bot_name)

