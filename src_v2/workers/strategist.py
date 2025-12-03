"""
Goal Strategist Worker

Runs nightly to analyze goal progress and generate strategies.
Part of Autonomous Agents Phase 3.1.
"""
from typing import Dict, Any, List, Optional
from loguru import logger
from src_v2.core.database import db_manager
from src_v2.evolution.goals import goal_manager
from src_v2.memory.manager import memory_manager
from src_v2.core.character import character_manager
from src_v2.agents.llm_factory import create_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser


class GoalStrategist:
    """
    Analyzes goal progress and generates strategies for achieving them.
    Also generates NEW goals based on community trends and character purpose.
    
    Design Principles:
    - Queries Neo4j first for verification (facts about user)
    - Falls back to chat logs only if Neo4j is inconclusive
    - Generates strategies as "internal desires" not commands
    - Generates new goals that align with character identity
    """
    
    def __init__(self):
        # Use reflective LLM for strategy generation (utility task, not character response)
        self.llm = create_llm(temperature=0.7, mode="reflective")
        self.parser = JsonOutputParser()
        
        # 1. Strategy Prompt (for existing goals)
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
        
        # 2. Goal Generation Prompt (for NEW goals)
        self.generation_prompt = ChatPromptTemplate.from_template("""
You are the "Ambition Engine" for {character_name}.
Your task is to generate NEW goals for this character based on their identity and recent community events.

CHARACTER IDENTITY:
{system_prompt}

RECENT COMMUNITY THEMES (what users are talking about):
{community_themes}

EXISTING GOALS:
{existing_goals}

Generate 1-2 NEW goals that:
1. Align with the character's core purpose and personality
2. React to recent community themes or gaps in knowledge
3. Are distinct from existing goals
4. Are actionable and measurable

Return JSON list of objects:
[
    {{
        "slug": "unique_snake_case_id",
        "description": "What the character wants to accomplish",
        "success_criteria": "Specific observable outcome",
        "priority": 1-10 (integer),
        "category": "community_growth" or "personal_growth" or "investigation",
        "reasoning": "Why this goal fits now"
    }}
]
""")
        
        self.strategy_chain = self.strategy_prompt | self.llm | self.parser
        self.generation_chain = self.generation_prompt | self.llm | self.parser

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
            result = await self.strategy_chain.ainvoke({
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
                    ORDER BY timestamp DESC 
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

    async def generate_new_goals(self, character_name: str) -> List[Dict[str, Any]]:
        """
        Generates NEW goals for the character based on community trends.
        """
        try:
            logger.info(f"Generating new strategic goals for {character_name}")
            
            # 1. Get Character Context
            character = character_manager.load_character(character_name)
            if not character:
                logger.warning(f"Character {character_name} not found for goal generation")
                return []
            
            # 2. Get Community Themes (last 48 hours)
            collection = f"whisperengine_memory_{character_name}"
            summaries = await memory_manager.get_summaries_since(
                hours=48,
                limit=20,
                collection_name=collection
            )
            
            community_themes = "No recent community activity."
            if summaries:
                topics = []
                for s in summaries:
                    topics.extend(s.get("topics", []))
                if topics:
                    # Simple frequency count
                    from collections import Counter
                    common = Counter(topics).most_common(5)
                    community_themes = ", ".join([f"{t} ({c})" for t, c in common])
            
            # 3. Get Existing Goals (to avoid duplicates)
            # We need a dummy user_id to fetch goals, or we can query DB directly.
            # Let's query DB directly for all active goals for this character
            existing_goals_text = "None"
            if db_manager.postgres_pool:
                async with db_manager.postgres_pool.acquire() as conn:
                    rows = await conn.fetch("""
                        SELECT slug, description FROM v2_goals 
                        WHERE character_name = $1
                        AND (expires_at IS NULL OR expires_at > NOW())
                    """, character_name)
                    if rows:
                        existing_goals_text = "\n".join([f"- {r['slug']}: {r['description']}" for r in rows])

            # 4. Generate Goals
            result = await self.generation_chain.ainvoke({
                "character_name": character_name,
                "system_prompt": character.system_prompt[:2000], # Truncate to save tokens
                "community_themes": community_themes,
                "existing_goals": existing_goals_text
            })
            
            # Strategic goals expire after 30 days (community trends change)
            from datetime import datetime, timedelta
            expires_at = datetime.now() + timedelta(days=30)
            
            new_goals = []
            if isinstance(result, list):
                for goal_data in result:
                    # Validate required fields
                    if "slug" in goal_data and "description" in goal_data:
                        # Insert into DB
                        if db_manager.postgres_pool:
                            async with db_manager.postgres_pool.acquire() as conn:
                                # Check existence again to be safe
                                exists = await conn.fetchval("""
                                    SELECT id FROM v2_goals 
                                    WHERE character_name = $1 AND slug = $2
                                """, character_name, goal_data["slug"])
                                
                                if not exists:
                                    await conn.execute("""
                                        INSERT INTO v2_goals (character_name, slug, description, success_criteria, priority, source, category, expires_at)
                                        VALUES ($1, $2, $3, $4, $5, 'strategic', $6, $7)
                                    """, character_name, goal_data["slug"], goal_data["description"], 
                                       goal_data.get("success_criteria", "Manual verification"),
                                       int(goal_data.get("priority", 5)),
                                       goal_data.get("category", "strategic"),
                                       expires_at)
                                    
                                    logger.info(f"Created new strategic goal: {goal_data['slug']} (expires: {expires_at.date()})")
                                    new_goals.append(goal_data)
            
            return new_goals

        except Exception as e:
            logger.error(f"Failed to generate new goals for {character_name}: {e}")
            return []

    async def run_nightly_analysis(self, character_name: str):
        """
        Runs the nightly goal analysis for a character.
        
        Called by the insight worker on a schedule.
        """
        logger.info(f"Starting nightly goal analysis for {character_name}")
        
        # 1. Generate NEW goals based on community status
        await self.generate_new_goals(character_name)
        
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
        return {"success": False, "reason": "disabled"}
    
    # Use the new LangGraph-based strategist agent
    logger.info(f"Using LangGraph Strategist Agent for {bot_name}")
    from src_v2.agents.strategist_graph import strategist_graph_agent, save_strategist_output
    
    try:
        output = await strategist_graph_agent.run(bot_name)
        
        if output:
            results = await save_strategist_output(bot_name, output)
            logger.info(f"Strategist complete for {bot_name}: {results['strategies_applied']} strategies, {results['goals_created']} new goals")
            return {
                "success": True,
                "strategies_applied": results["strategies_applied"],
                "goals_created": results["goals_created"],
                "summary": output.summary,
                "character_name": bot_name
            }
        else:
            return {
                "success": True,
                "skipped": True,
                "reason": "no_output",
                "character_name": bot_name
            }
    except Exception as e:
        logger.error(f"LangGraph strategist failed for {bot_name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "character_name": bot_name
        }
