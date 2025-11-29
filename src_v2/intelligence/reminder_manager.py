import datetime
from typing import List, Optional, Dict, Any
from loguru import logger
from src_v2.core.database import db_manager, retry_db_operation
from src_v2.config.settings import settings

class ReminderManager:
    """
    Manages scheduling and retrieval of user reminders.
    """
    
    @retry_db_operation(max_retries=3)
    async def create_reminder(
        self, 
        user_id: str, 
        channel_id: str, 
        character_name: str, 
        content: str, 
        deliver_at: datetime.datetime
    ) -> int:
        """Create a new reminder."""
        if not db_manager.postgres_pool:
            raise RuntimeError("Database not connected")
            
        async with db_manager.postgres_pool.acquire() as conn:
            reminder_id = await conn.fetchval("""
                INSERT INTO v2_reminders (user_id, channel_id, character_name, content, deliver_at, status)
                VALUES ($1, $2, $3, $4, $5, 'pending')
                RETURNING id
            """, user_id, channel_id, character_name, content, deliver_at)
            
            logger.info(f"Created reminder {reminder_id} for user {user_id} at {deliver_at}")
            return reminder_id

    @retry_db_operation(max_retries=3)
    async def get_due_reminders(self, character_name: str) -> List[Dict[str, Any]]:
        """Get all pending reminders that are due for a specific character."""
        if not db_manager.postgres_pool:
            return []
            
        now = datetime.datetime.now(datetime.timezone.utc)
        
        async with db_manager.postgres_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, user_id, channel_id, content, deliver_at
                FROM v2_reminders
                WHERE character_name = $1 
                  AND status = 'pending'
                  AND deliver_at <= $2
            """, character_name, now)
            
            return [dict(row) for row in rows]

    @retry_db_operation(max_retries=3)
    async def mark_as_delivered(self, reminder_id: int) -> None:
        """Mark a reminder as delivered."""
        if not db_manager.postgres_pool:
            return
            
        async with db_manager.postgres_pool.acquire() as conn:
            await conn.execute("""
                UPDATE v2_reminders
                SET status = 'delivered'
                WHERE id = $1
            """, reminder_id)
            logger.debug(f"Marked reminder {reminder_id} as delivered")

# Global instance
reminder_manager = ReminderManager()
