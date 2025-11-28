"""
Goal Strategist Worker

Runs nightly to analyze goal progress and generate strategies.
Part of Autonomous Agents Phase 3.1.
"""
from typing import Dict, Any, List, Optional
from loguru import logger
from src_v2.core.database import db_manager
from src_v2.evolution.goals import goal_manager, GOAL_SOURCE_PRIORITY
from src_v2.agents.llm_factory import create_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser


class GoalStrategist:
    """
    Analyzes goal progress and generates strategies for achieving them.
    
    Design Principles:
    - Queries Neo4j first for verification (facts about user)
    - Falls back to chat logs only if Neo4j is inconclusive
    - Generates strategies as "internal desires" not commands
    """
    
    def __init__(self):
        self.llm = create_llm(temperature=0.3)  # Slightly creative but focused
        self.parser = JsonOutputParser()
        
        self.strategy_prompt = ChatPromptTemplate.from_template("""
You are helping {character_name} develop a natural strategy for a personal goal.

GOAL:
- Description: {goal_description}
- Success Criteria: {goal_criteria}
- Current Progress: {progress_percent}%

WHAT WE KNOW ABOUT THIS USER (from knowledge graph):
{user_facts}

RECENT INTERACTION HISTORY (if available):
{recent_history}

Generate a STRATEGY that {character_name} can use in their next conversation.

The strategy should be:
1. Framed as an internal desire/curiosity (not a command)
2. Natural to the character's personality
3. Based on what we know about the user
4. Achievable in a single conversation

Example good strategy: "I'm curious to learn more about their hobbies since they mentioned liking music"
Example bad strategy: "Ask the user about their hobbies" (too robotic)

Return JSON:
{{
    "strategy": "The natural strategy as an internal desire",
    "reasoning": "Why this approach makes sense",
    "confidence": 0.0 to 1.0
}}
""")
        
        self.chain = self.strategy_prompt | self.llm | self.parser

    async def analyze_goal(
        self, 
        character_name: str, 
        user_id: str, 
        goal: Dict[str, Any]
    ) -> Optional[str]:
        """
        Analyzes a single goal and generates a strategy.
        
        Returns the strategy string or None if no strategy needed.
        """
        try:
            # 1. Query Neo4j for user facts (primary source)
            user_facts = await self._get_user_facts_from_neo4j(user_id, character_name)
            
            # 2. Get recent chat history (fallback context)
            recent_history = await self._get_recent_history(user_id, character_name)
            
            # 3. Calculate progress
            progress = goal.get("progress", 0.0)
            progress_percent = int(progress * 100)
            
            # 4. Generate strategy
            result = await self.chain.ainvoke({
                "character_name": character_name,
                "goal_description": goal["description"],
                "goal_criteria": goal["success_criteria"],
                "progress_percent": progress_percent,
                "user_facts": user_facts or "No facts known yet.",
                "recent_history": recent_history or "No recent interactions.",
            })
            
            strategy = result.get("strategy")
            confidence = result.get("confidence", 0.5)
            
            # Only use strategy if confidence is reasonable
            if confidence >= 0.4 and strategy:
                logger.info(f"Generated strategy for goal '{goal['slug']}': {strategy[:50]}...")
                return strategy
            
            return None
            
        except Exception as e:
            logger.error(f"Strategy generation failed for goal '{goal['slug']}': {e}")
            return None

    async def _get_user_facts_from_neo4j(self, user_id: str, character_name: str) -> Optional[str]:
        """
        Queries Neo4j for facts about this user.
        Primary source for strategy generation.
        """
        try:
            # Query Neo4j directly for user facts
            if not db_manager.neo4j_driver:
                return None
            
            async with db_manager.neo4j_driver.session() as session:
                result = await session.run("""
                    MATCH (u:User {id: $user_id})-[r:FACT]->(e:Entity)
                    RETURN r.predicate as predicate, e.name as entity
                    ORDER BY r.confidence DESC
                    LIMIT 10
                """, user_id=user_id)
                
                records = await result.data()
                
                if not records:
                    return None
                
                # Format facts for prompt
                fact_lines = []
                for record in records:
                    fact_lines.append(f"- User {record['predicate']} {record['entity']}")
                
                return "\n".join(fact_lines)
            
        except Exception as e:
            logger.warning(f"Failed to get Neo4j facts for user {user_id}: {e}")
            return None

    async def _get_recent_history(self, user_id: str, character_name: str) -> Optional[str]:
        """
        Gets recent chat history as fallback context.
        Only used if Neo4j facts are insufficient.
        """
        try:
            if not db_manager.postgres_pool:
                return None
            
            async with db_manager.postgres_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT role, content 
                    FROM v2_chat_history 
                    WHERE user_id = $1 AND character_name = $2
                    ORDER BY created_at DESC 
                    LIMIT 10
                """, user_id, character_name)
                
                if not rows:
                    return None
                
                # Format as conversation snippet
                lines = []
                for row in reversed(rows):  # Chronological order
                    role = "User" if row["role"] == "user" else character_name
                    content = row["content"][:100]  # Truncate for brevity
                    lines.append(f"{role}: {content}")
                
                return "\n".join(lines)
                
        except Exception as e:
            logger.warning(f"Failed to get chat history for user {user_id}: {e}")
            return None

    async def run_nightly_analysis(self, character_name: str):
        """
        Runs the nightly goal analysis for a character.
        
        Called by the insight worker on a schedule.
        """
        logger.info(f"Starting nightly goal analysis for {character_name}")
        
        if not db_manager.postgres_pool:
            logger.warning("Database not available, skipping goal analysis")
            return
        
        try:
            async with db_manager.postgres_pool.acquire() as conn:
                # Get all unique users who have interacted with this character
                users = await conn.fetch("""
                    SELECT DISTINCT user_id 
                    FROM v2_user_relationships 
                    WHERE character_name = $1
                """, character_name)
                
                for user_row in users:
                    user_id = user_row["user_id"]
                    
                    # Get active goals for this user
                    goals = await goal_manager.get_active_goals(user_id, character_name)
                    
                    for goal in goals:
                        # Skip if already has a strategy
                        if goal.get("current_strategy"):
                            continue
                        
                        # Generate strategy
                        strategy = await self.analyze_goal(character_name, user_id, goal)
                        
                        if strategy:
                            await goal_manager.update_goal_strategy(
                                character_name=character_name,
                                goal_slug=goal["slug"],
                                strategy=strategy
                            )
            
            logger.info(f"Completed nightly goal analysis for {character_name}")
            
        except Exception as e:
            logger.error(f"Nightly goal analysis failed for {character_name}: {e}")


# Singleton instance
goal_strategist = GoalStrategist()


async def run_goal_strategist(ctx: Dict[str, Any], bot_name: str):
    """
    Worker task entry point for goal strategist.
    
    Called by arq worker on schedule or manually.
    """
    from src_v2.config.settings import settings
    
    if not settings.ENABLE_GOAL_STRATEGIST:
        logger.debug("Goal strategist is disabled, skipping")
        return
    
    await goal_strategist.run_nightly_analysis(bot_name)
