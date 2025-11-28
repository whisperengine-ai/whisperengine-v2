"""
Trust & Relationship Manager

Tracks the evolving relationship between user and character, including
trust scores, relationship levels, and unlocked personality traits.
"""

from typing import Dict, Optional, Any
from loguru import logger
from influxdb_client import Point
from datetime import datetime, timezone
from src_v2.core.database import db_manager, require_db
from src_v2.config.settings import settings
from src_v2.evolution.manager import get_evolution_manager
from src_v2.core.cache import cache_manager
import json


class TrustManager:
    """
    Manages relationship depth and trust scores between users and characters.
    """
    
    def __init__(self):
        logger.info("TrustManager initialized")

    @require_db("postgres", default_return={"trust_score": 0, "level": 1, "level_label": "Stranger", "unlocked_traits": [], "preferences": {}})
    async def get_relationship_level(self, user_id: str, character_name: str) -> Dict:
        """
        Retrieves the current relationship level and trust score.
        
        Returns:
            Dict with {trust_score: int, level: str, unlocked_traits: List[str], preferences: Dict}
        """
        cache_key = f"trust:{character_name}:{user_id}"
        cached_data = await cache_manager.get_json(cache_key)
        if cached_data:
            return cached_data

        try:
            async with db_manager.postgres_pool.acquire() as conn:
                # Check if relationship exists
                row = await conn.fetchrow("""
                    SELECT trust_score, unlocked_traits, insights, preferences, mood, mood_intensity
                    FROM v2_user_relationships
                    WHERE user_id = $1 AND character_name = $2
                """, user_id, character_name)
                
                if not row:
                    # Create default relationship
                    await conn.execute("""
                        INSERT INTO v2_user_relationships (user_id, character_name, trust_score, unlocked_traits, insights, preferences)
                        VALUES ($1, $2, 0, '[]'::jsonb, '[]'::jsonb, '{}'::jsonb)
                    """, user_id, character_name)
                    result = {
                        "trust_score": 0, 
                        "level": 1, 
                        "level_label": "Stranger", 
                        "unlocked_traits": [], 
                        "insights": [], 
                        "preferences": {},
                        "mood": "neutral",
                        "mood_intensity": 0.5
                    }
                    await cache_manager.set_json(cache_key, result)
                    return result
                
                trust_score = row['trust_score']
                
                # Get Evolution Manager for this character
                evo_manager = get_evolution_manager(character_name)
                stage = evo_manager.get_current_stage(trust_score)
                
                # Get traits from config (dynamic) rather than DB (static)
                # We can merge them if we want to support manual unlocks, but for now dynamic is better
                active_traits = evo_manager.get_active_traits(trust_score)
                trait_names = [t['name'] for t in active_traits]

                insights = row['insights']
                if isinstance(insights, str):
                    try:
                        insights = json.loads(insights)
                    except Exception:
                        insights = []
                elif insights is None:
                    insights = []
                
                preferences = row['preferences']
                if isinstance(preferences, str):
                    try:
                        preferences = json.loads(preferences)
                    except Exception:
                        preferences = {}
                elif preferences is None:
                    preferences = {}
                
                # Determine level (integer 1-8 roughly mapping to stages)
                # This is a bit arbitrary now that we have named stages, but useful for simple logic
                level_int = 1
                if trust_score >= 80: level_int = 5
                elif trust_score >= 60: level_int = 4
                elif trust_score >= 40: level_int = 3
                elif trust_score >= 20: level_int = 2
                        
                result = {
                    "trust_score": trust_score, 
                    "level": level_int,
                    "level_label": stage['name'],
                    "unlocked_traits": trait_names,
                    "insights": insights,
                    "preferences": preferences,
                    "mood": row.get('mood', 'neutral'),
                    "mood_intensity": row.get('mood_intensity', 0.5)
                }
                
                await cache_manager.set_json(cache_key, result)
                return result
                
        except Exception as e:
            logger.error(f"Failed to get relationship level: {e}")
            return {"trust_score": 0, "level": 1, "level_label": "Stranger", "unlocked_traits": [], "preferences": {}}

    @require_db("postgres")
    async def update_preference(self, user_id: str, character_name: str, key: str, value: Any):
        """
        Updates a specific preference setting.
        """
        try:
            async with db_manager.postgres_pool.acquire() as conn:
                await self.get_relationship_level(user_id, character_name)
                
                # Update jsonb field
                # We use jsonb_set to update a specific key
                # value needs to be a valid JSON value
                json_value = json.dumps(value)
                
                await conn.execute("""
                    UPDATE v2_user_relationships
                    SET preferences = jsonb_set(COALESCE(preferences, '{}'::jsonb), $3::text[], $4::jsonb),
                        updated_at = NOW()
                    WHERE user_id = $1 AND character_name = $2
                """, user_id, character_name, [key], json_value)
                
                logger.info(f"Updated preference '{key}' to '{value}' for {user_id}")
                
                # Invalidate cache
                await cache_manager.delete(f"trust:{character_name}:{user_id}")
        except Exception as e:
            logger.error(f"Failed to update preference: {e}")

    @require_db("postgres")
    async def delete_preference(self, user_id: str, character_name: str, key: str):
        """
        Deletes a specific preference setting.
        """
        try:
            async with db_manager.postgres_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE v2_user_relationships
                    SET preferences = preferences - $3,
                        updated_at = NOW()
                    WHERE user_id = $1 AND character_name = $2
                """, user_id, character_name, key)
                
                logger.info(f"Deleted preference '{key}' for {user_id}")
                
                # Invalidate cache
                await cache_manager.delete(f"trust:{character_name}:{user_id}")
        except Exception as e:
            logger.error(f"Failed to delete preference: {e}")

    @require_db("postgres")
    async def clear_user_preferences(self, user_id: str, character_name: str):
        """
        Clears user preferences and resets trust score.
        """
        try:
            async with db_manager.postgres_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE v2_user_relationships
                    SET preferences = '{}'::jsonb, trust_score = 0, unlocked_traits = '[]'::jsonb, insights = '[]'::jsonb
                    WHERE user_id = $1 AND character_name = $2
                """, user_id, character_name)
                
                # Invalidate cache
                await cache_manager.delete(f"trust:{character_name}:{user_id}")
                logger.info(f"Cleared preferences for {user_id}")
        except Exception as e:
            logger.error(f"Failed to clear preferences: {e}")

    @require_db("postgres", default_return=None)
    async def update_trust(self, user_id: str, character_name: str, delta: int) -> Optional[str]:
        """
        Adjusts trust score by delta amount.
        Returns a milestone message if a threshold was crossed, else None.
        
        Args:
            user_id: User ID
            character_name: Character name
            delta: Amount to change trust by (can be negative)
        """
        try:
            async with db_manager.postgres_pool.acquire() as conn:
                # Ensure relationship exists and get current score
                row = await conn.fetchrow("""
                    SELECT trust_score FROM v2_user_relationships
                    WHERE user_id = $1 AND character_name = $2
                """, user_id, character_name)
                
                if not row:
                    # Should have been created by get_relationship_level, but just in case
                    await self.get_relationship_level(user_id, character_name)
                    old_trust = 0
                else:
                    old_trust = row['trust_score']
                
                # Calculate new trust (clamp between -100 and 100)
                # Note: Design changed to -100 to 100 range
                new_trust = max(-100, min(100, old_trust + delta))
                
                if new_trust != old_trust:
                    await conn.execute("""
                        UPDATE v2_user_relationships
                        SET trust_score = $3,
                            updated_at = NOW()
                        WHERE user_id = $1 AND character_name = $2
                    """, user_id, character_name, new_trust)
                    
                    logger.info(f"Updated trust for {user_id} with {character_name}: {old_trust} -> {new_trust} (delta: {delta})")
                    
                    # Check for milestones
                    evo_manager = get_evolution_manager(character_name)
                    milestone_msg = evo_manager.check_milestone(old_trust, new_trust)
                    
                    if milestone_msg:
                        # Update last_milestone_date
                        await conn.execute("""
                            UPDATE v2_user_relationships
                            SET last_milestone_date = NOW()
                            WHERE user_id = $1 AND character_name = $2
                        """, user_id, character_name)
                    
                    # Invalidate cache
                    await cache_manager.delete(f"trust:{character_name}:{user_id}")

                    # Log to InfluxDB
                    if db_manager.influxdb_write_api:
                        try:
                            point = Point("trust_update") \
                                .tag("user_id", user_id) \
                                .tag("bot_name", character_name) \
                                .field("trust_score", new_trust) \
                                .field("delta", delta) \
                                .time(datetime.utcnow())
                            
                            db_manager.influxdb_write_api.write(
                                bucket=settings.INFLUXDB_BUCKET,
                                org=settings.INFLUXDB_ORG,
                                record=point
                            )
                        except Exception as e:
                            logger.error(f"Failed to log trust update to InfluxDB: {e}")
                    
                    if milestone_msg:
                        return milestone_msg
                        
            return None
                
        except Exception as e:
            logger.error(f"Failed to update trust: {e}")
            return None

    @require_db("postgres")
    async def unlock_trait(self, user_id: str, character_name: str, trait: str):
        """
        Unlocks a new personality trait for this relationship.
        
        Args:
            trait: Name of the trait (e.g., "vulnerable", "protective")
        """
        try:
            async with db_manager.postgres_pool.acquire() as conn:
                # Append trait to unlocked_traits array
                await conn.execute("""
                    UPDATE v2_user_relationships
                    SET unlocked_traits = unlocked_traits || $3::jsonb
                    WHERE user_id = $1 AND character_name = $2
                    AND NOT (unlocked_traits @> $3::jsonb)
                """, user_id, character_name, f'["{trait}"]')
                
                logger.info(f"Unlocked trait '{trait}' for {user_id} with {character_name}")
                
                # Invalidate cache
                await cache_manager.delete(f"trust:{character_name}:{user_id}")
        except Exception as e:
            logger.error(f"Failed to unlock trait: {e}")

    @require_db("postgres", default_return=None)
    async def get_last_interaction(self, user_id: str, character_name: str) -> Optional[datetime]:
        """
        Gets the timestamp of the last interaction between user and character.
        
        This is used by the Dream Sequences feature (Phase E3) to determine
        if the user has been away long enough to trigger a dream.
        
        Args:
            user_id: Discord user ID
            character_name: Character/bot name
            
        Returns:
            datetime of last interaction, or None if no relationship exists
        """
        try:
            async with db_manager.postgres_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT updated_at
                    FROM v2_user_relationships
                    WHERE user_id = $1 AND character_name = $2
                """, user_id, character_name)
                
                if row and row['updated_at']:
                    # Ensure timezone-aware
                    updated_at = row['updated_at']
                    if updated_at.tzinfo is None:
                        updated_at = updated_at.replace(tzinfo=timezone.utc)
                    return updated_at
                
                return None
                
        except Exception as e:
            logger.error(f"Failed to get last interaction: {e}")
            return None


# Global singleton
trust_manager = TrustManager()
