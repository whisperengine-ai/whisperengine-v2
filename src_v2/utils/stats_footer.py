"""
Stats Footer Generator

Generates a detailed stats footer for Discord messages, showing:
- Relationship metrics (trust, level, interactions)
- Memory context (memories retrieved)
- Performance metrics (response time)
- Active goals
- Recent insights

Can be toggled on/off via user preferences.
"""

from typing import Dict, Optional, List
from loguru import logger
from src_v2.core.database import db_manager
from src_v2.evolution.trust import trust_manager
from src_v2.config.settings import settings


class StatsFooter:
    """
    Generates detailed stats footers for Discord messages.
    """
    
    def __init__(self):
        # Global toggle from settings, can be overridden per-user via /stats_footer command
        self.enabled = settings.STATS_FOOTER_DEFAULT_ENABLED
        
    async def is_enabled_for_user(self, user_id: str, character_name: str) -> bool:
        """
        Check if stats footer is enabled for this user.
        Checks user preferences first, falls back to global setting.
        """
        try:
            relationship = await trust_manager.get_relationship_level(user_id, character_name)
            preferences = relationship.get("preferences", {})
            
            # Check user preference, default to global setting
            return preferences.get("show_stats_footer", self.enabled)
        except Exception as e:
            logger.error(f"Failed to check stats footer preference: {e}")
            return self.enabled
    
    async def toggle_for_user(self, user_id: str, character_name: str, enabled: bool):
        """
        Toggle stats footer for a specific user.
        """
        try:
            await trust_manager.update_preference(user_id, character_name, "show_stats_footer", enabled)
            logger.info(f"Stats footer {'enabled' if enabled else 'disabled'} for {user_id}")
        except Exception as e:
            logger.error(f"Failed to toggle stats footer: {e}")
    
    async def generate_footer(
        self,
        user_id: str,
        character_name: str,
        memory_count: int = 0,
        processing_time_ms: float = 0,
        llm_time_ms: Optional[float] = None
    ) -> str:
        """
        Generates a compact stats footer with relevant metrics.
        
        Args:
            user_id: Discord user ID
            character_name: Character name
            memory_count: Number of memories retrieved
            processing_time_ms: Total processing time in milliseconds
            llm_time_ms: LLM-specific processing time (optional)
            
        Returns:
            Formatted footer string
        """
        try:
            # BUGFIX: Log user_id to help trace context confusion
            logger.debug(f"Generating footer for user_id={user_id}, character={character_name}")
            
            # 1. Get Relationship Metrics
            relationship = await trust_manager.get_relationship_level(user_id, character_name)
            logger.debug(f"Retrieved relationship for {user_id}: trust={relationship.get('trust_score')}, level={relationship.get('level_label')}")
            trust_score = relationship.get("trust_score", 0)
            level_label = relationship.get("level_label", "Stranger")
            unlocked_traits = relationship.get("unlocked_traits", [])
            insights = relationship.get("insights", [])
            
            # 2. Get Interaction Count
            interaction_count = await self._get_interaction_count(user_id, character_name)
            
            # 3. Get Active Goals
            active_goals = await self._get_active_goals(user_id, character_name)
            
            # 4. Get Latest Insight
            latest_insight = insights[-1] if insights else None
            
            # Build Footer
            lines = ["──────────────────────────────────────────────────"]
            
            # Relationship Line
            traits_text = f" [{', '.join(unlocked_traits[:2])}]" if unlocked_traits else ""
            lines.append(
                f"💙 **Relationship**: {level_label} (Trust: {trust_score}/100{traits_text}) • {interaction_count} interactions"
            )
            
            # Goals Line (if any active)
            if active_goals:
                goal_names = [g['name'] for g in active_goals[:2]]
                goals_text = ", ".join(goal_names)
                lines.append(f"🎯 **Active Goals**: {goals_text}")
            
            # Memory Line
            lines.append(f"🧠 **Memory**: Retrieved {memory_count} relevant memories")
            
            # Insight Line (if available)
            if latest_insight:
                insight_text = latest_insight if isinstance(latest_insight, str) else latest_insight.get("text", "")
                if len(insight_text) > 60:
                    insight_text = insight_text[:57] + "..."
                lines.append(f"💡 **Recent Insight**: {insight_text}")
            
            # Performance Line
            overhead_ms = processing_time_ms - (llm_time_ms or 0)
            if llm_time_ms:
                lines.append(
                    f"⚡ **Performance**: Total: {processing_time_ms:.0f}ms | LLM: {llm_time_ms:.0f}ms | Overhead: {overhead_ms:.0f}ms"
                )
            else:
                lines.append(f"⚡ **Performance**: {processing_time_ms:.0f}ms")
            
            lines.append("──────────────────────────────────────────────────")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.error(f"Failed to generate stats footer: {e}")
            return ""
    
    async def generate_compact_footer(
        self,
        user_id: str,
        character_name: str,
        memory_count: int = 0,
        processing_time_ms: float = 0
    ) -> str:
        """
        Generates a single-line compact footer.
        Useful for less intrusive stats display.
        """
        try:
            relationship = await trust_manager.get_relationship_level(user_id, character_name)
            trust_score = relationship.get("trust_score", 0)
            level_label = relationship.get("level_label", "Stranger")
            
            return (
                f"💙 {level_label} (Trust: {trust_score}/100) | "
                f"🧠 {memory_count} memories | "
                f"⚡ {processing_time_ms:.0f}ms"
            )
        except Exception as e:
            logger.error(f"Failed to generate compact footer: {e}")
            return ""
    
    async def _get_interaction_count(self, user_id: str, character_name: str) -> int:
        """
        Get total number of interactions between user and character.
        """
        if not db_manager.postgres_pool:
            return 0
        
        try:
            async with db_manager.postgres_pool.acquire() as conn:
                # Count messages from the user (human messages only)
                count = await conn.fetchval("""
                    SELECT COUNT(*) 
                    FROM v2_chat_history 
                    WHERE user_id = $1 AND character_name = $2 AND role = 'human'
                """, user_id, character_name)
                return count or 0
        except Exception as e:
            logger.error(f"Failed to get interaction count: {e}")
            return 0
    
    async def _get_active_goals(self, user_id: str, character_name: str) -> List[Dict]:
        """
        Get list of active (in_progress) goals for this user.
        """
        if not db_manager.postgres_pool:
            return []
        
        try:
            async with db_manager.postgres_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT g.slug as name, g.slug, p.progress_score
                    FROM v2_user_goal_progress p
                    JOIN v2_goals g ON p.goal_id = g.id
                    WHERE p.user_id = $1 
                    AND g.character_name = $2 
                    AND p.status = 'in_progress'
                    ORDER BY p.updated_at DESC
                    LIMIT 3
                """, user_id, character_name)
                
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get active goals: {e}")
            return []


# Global singleton
stats_footer = StatsFooter()
