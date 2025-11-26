from typing import Dict, Any, Optional
from loguru import logger
from src_v2.core.database import db_manager, retry_db_operation

class PrivacyManager:
    """
    Manages user privacy settings for the Emergent Universe.
    Controls what data is shared across bots and planets.
    """
    
    @retry_db_operation()
    async def get_settings(self, user_id: str) -> Dict[str, Any]:
        """
        Get privacy settings for a user. Returns defaults if not found.
        """
        if not db_manager.postgres_pool:
            logger.warning("PostgreSQL not available. Returning default privacy settings.")
            return self._get_defaults()

        query = """
            SELECT share_with_other_bots, share_across_planets, allow_bot_introductions, invisible_mode
            FROM v2_user_privacy_settings
            WHERE user_id = $1
        """
        
        async with db_manager.postgres_pool.acquire() as conn:
            row = await conn.fetchrow(query, str(user_id))
            
            if row:
                return dict(row)
            else:
                # Create default entry
                return await self._create_default_settings(user_id)

    @retry_db_operation()
    async def update_settings(self, user_id: str, **kwargs) -> Dict[str, Any]:
        """
        Update specific privacy settings for a user.
        """
        if not db_manager.postgres_pool:
            raise RuntimeError("PostgreSQL not available")

        # Validate keys
        valid_keys = {'share_with_other_bots', 'share_across_planets', 'allow_bot_introductions', 'invisible_mode'}
        updates = {k: v for k, v in kwargs.items() if k in valid_keys}
        
        if not updates:
            return await self.get_settings(user_id)

        # Build dynamic update query
        set_clauses = [f"{k} = ${i+2}" for i, k in enumerate(updates.keys())]
        query = f"""
            UPDATE v2_user_privacy_settings
            SET {', '.join(set_clauses)}, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = $1
            RETURNING share_with_other_bots, share_across_planets, allow_bot_introductions, invisible_mode
        """
        
        async with db_manager.postgres_pool.acquire() as conn:
            # Ensure record exists first
            await self.get_settings(user_id)
            
            row = await conn.fetchrow(query, str(user_id), *updates.values())
            if row:
                logger.info(f"Updated privacy settings for user {user_id}: {updates}")
                return dict(row)
            raise RuntimeError(f"Failed to update settings for user {user_id}")

    async def _create_default_settings(self, user_id: str) -> Dict[str, Any]:
        """Create default settings record for a new user."""
        query = """
            INSERT INTO v2_user_privacy_settings (user_id)
            VALUES ($1)
            ON CONFLICT (user_id) DO NOTHING
            RETURNING share_with_other_bots, share_across_planets, allow_bot_introductions, invisible_mode
        """
        
        async with db_manager.postgres_pool.acquire() as conn:
            row = await conn.fetchrow(query, str(user_id))
            if row:
                return dict(row)
            # If insert failed (race condition), fetch again
            return await self.get_settings(user_id)

    def _get_defaults(self) -> Dict[str, Any]:
        return {
            "share_with_other_bots": True,
            "share_across_planets": True,
            "allow_bot_introductions": False,
            "invisible_mode": False
        }

privacy_manager = PrivacyManager()
