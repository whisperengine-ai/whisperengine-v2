from typing import List, Dict, Any, Optional
import json
from loguru import logger
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

from src_v2.core.database import db_manager
from src_v2.core.behavior import load_behavior_profile
from src_v2.agents.llm_factory import create_llm
from src_v2.config.settings import settings


class InferredGoal(BaseModel):
    slug: str = Field(description="Unique snake_case identifier for the goal")
    description: str = Field(description="What the character should work towards with this user")
    success_criteria: str = Field(description="How to know when the goal is achieved")
    priority: int = Field(default=5, description="Priority 1-10")
    reasoning: str = Field(description="Why this goal was inferred from patterns")


class ReflectionResult(BaseModel):
    insights: List[str] = Field(description="List of high-level insights about the user (e.g., 'Values honesty', 'Stressed about work').")
    updated_traits: List[str] = Field(description="List of personality traits the user has revealed.")
    inferred_goals: List[InferredGoal] = Field(default_factory=list, description="Goals inferred from conversation patterns")

class ReflectionEngine:
    def __init__(self):
        self.base_llm = create_llm(temperature=0.4)
        self.parser = JsonOutputParser(pydantic_object=ReflectionResult)
        
        # Prompt template with character identity placeholder
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert psychologist AI analyzing conversation patterns for {character_name}.

CHARACTER IDENTITY:
{character_identity}

Your goal is to extract high-level insights about the user AND infer goals that align with this character's identity.

INPUT:
A list of recent conversation summaries.

OUTPUT:
1. Insights: Deep observations about the user's personality, values, struggles, or preferences.
2. Traits: Specific personality traits observed.
3. Inferred Goals: Goals the character should pursue with THIS user based on patterns.

GOAL INFERENCE RULES:
- Only infer goals if there's a CLEAR pattern (user mentions topic 3+ times, expresses repeated need)
- Goals MUST align with the character's purpose and drives (see CHARACTER IDENTITY above)
- Goals should be user-specific (not generic like "learn their name")
- Frame goals in the character's voice/style
- Examples:
  * High chaos/playfulness character + user stressed → "inject_levity_into_stress": "Bring chaotic joy to lighten their work burden"
  * High connection drive + lonely user → "be_consistent_presence": "Show up regularly with genuine warmth"
  * High curiosity drive + creative user → "explore_creativity_together": "Dive deep into their creative interests"
- If no clear patterns, return empty list for inferred_goals

{format_instructions}
"""),
            ("human", "Recent Summaries:\n{summaries_text}")
        ])

    async def analyze_user_patterns(self, user_id: str, character_name: str) -> Optional[ReflectionResult]:
        """
        Analyzes recent summaries for a user and updates their insights profile.
        """
        if not db_manager.postgres_pool:
            return None

        try:
            # 0. Load character identity
            character_identity = "A helpful AI assistant."
            try:
                character_dir = f"characters/{character_name}"
                behavior = load_behavior_profile(character_dir)
                if behavior:
                    character_identity = behavior.to_prompt_section()
            except Exception:
                pass
            
            # 1. Fetch recent summaries (last 5)
            async with db_manager.postgres_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT s.content, s.meaningfulness_score, sess.start_time
                    FROM v2_summaries s
                    JOIN v2_conversation_sessions sess ON s.session_id = sess.id
                    WHERE sess.user_id = $1 AND sess.character_name = $2
                    ORDER BY sess.start_time DESC
                    LIMIT 5
                """, user_id, character_name)
                
                if not rows:
                    logger.info("No summaries found for reflection.")
                    return None
                
                summaries_text = ""
                for row in rows:
                    summaries_text += f"- [{row['start_time']}] (Score: {row['meaningfulness_score']}): {row['content']}\n"

            # 2. Build chain with character context
            chain = self.prompt.partial(
                format_instructions=self.parser.get_format_instructions()
            ) | self.base_llm | self.parser
            
            # 3. Generate Reflection
            result_dict = await chain.ainvoke({
                "character_name": character_name,
                "character_identity": character_identity,
                "summaries_text": summaries_text
            })
            result = ReflectionResult(**result_dict)
            
            # 3. Update Database (insights)
            await self._update_user_insights(user_id, character_name, result)
            
            # 4. Save Inferred Goals (if any)
            if result.inferred_goals:
                await self._save_inferred_goals(user_id, character_name, result.inferred_goals)
            
            return result

        except Exception as e:
            logger.error(f"Reflection failed: {e}")
            return None

    async def _save_inferred_goals(self, user_id: str, character_name: str, goals: List[InferredGoal]):
        """
        Saves inferred goals to the v2_goals table with source='inferred'.
        
        These are user-specific goals detected from conversation patterns.
        Inferred goals expire after 14 days (patterns may shift).
        """
        from datetime import datetime, timedelta
        
        if not db_manager.postgres_pool:
            return
        
        # Inferred goals expire after 14 days
        expires_at = datetime.now() + timedelta(days=14)
        
        try:
            async with db_manager.postgres_pool.acquire() as conn:
                for goal in goals:
                    # Check if goal with this slug already exists for this character
                    exists = await conn.fetchval("""
                        SELECT id FROM v2_goals 
                        WHERE character_name = $1 AND slug = $2
                    """, character_name, goal.slug)
                    
                    if not exists:
                        await conn.execute("""
                            INSERT INTO v2_goals (
                                character_name, slug, description, success_criteria, 
                                priority, source, category, current_strategy,
                                target_user_id, expires_at
                            )
                            VALUES ($1, $2, $3, $4, $5, 'inferred', 'user_specific', $6, $7, $8)
                        """, 
                            character_name, 
                            goal.slug, 
                            goal.description, 
                            goal.success_criteria,
                            goal.priority,
                            goal.reasoning,  # Store reasoning as initial strategy
                            user_id,  # Track which user this goal is for
                            expires_at
                        )
                        logger.info(f"Created inferred goal '{goal.slug}' for {character_name}/{user_id} (expires: {expires_at.date()})")
                    else:
                        logger.debug(f"Inferred goal '{goal.slug}' already exists, skipping")
                        
        except Exception as e:
            logger.error(f"Failed to save inferred goals: {e}")

    async def _update_user_insights(self, user_id: str, character_name: str, result: ReflectionResult):
        """
        Updates the v2_user_relationships table with new insights.
        """
        if not db_manager.postgres_pool:
            return

        try:
            async with db_manager.postgres_pool.acquire() as conn:
                # Fetch existing insights
                current_data = await conn.fetchval("""
                    SELECT insights 
                    FROM v2_user_relationships 
                    WHERE user_id = $1 AND character_name = $2
                """, user_id, character_name)
                
                existing_insights = []
                if current_data:
                    # If it's already a dict/list (jsonb), use it. 
                    # If it's a string, parse it.
                    if isinstance(current_data, str):
                        existing_insights = json.loads(current_data)
                    else:
                        existing_insights = current_data
                
                # Merge new insights (simple append for now, could be smarter)
                # We'll store it as a list of strings for simplicity
                if not isinstance(existing_insights, list):
                    existing_insights = []
                
                # Add new unique insights
                for insight in result.insights:
                    if insight not in existing_insights:
                        existing_insights.append(insight)
                
                # Update DB
                await conn.execute("""
                    UPDATE v2_user_relationships
                    SET insights = $1, updated_at = NOW()
                    WHERE user_id = $2 AND character_name = $3
                """, json.dumps(existing_insights), user_id, character_name)
                
                logger.info(f"Updated insights for user {user_id}: {len(result.insights)} new insights.")

        except Exception as e:
            logger.error(f"Failed to update user insights: {e}")

# Global instance
reflection_engine = ReflectionEngine()
