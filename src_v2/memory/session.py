from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
from loguru import logger
from src_v2.core.database import db_manager

class SessionManager:
    """
    Manages conversation sessions.
    A session is a continuous period of conversation.
    Sessions are closed after a period of inactivity (e.g., 30 minutes).
    """
    
    SESSION_TIMEOUT_MINUTES = 30

    def __init__(self):
        logger.info("SessionManager initialized")

    async def get_active_session(self, user_id: str, character_name: str) -> str:
        """
        Retrieves the active session ID for a user/character pair.
        If the active session is stale (timed out), it closes it and creates a new one.
        If no active session exists, creates a new one.
        
        Returns:
            session_id (str): UUID of the active session.
        """
        if not db_manager.postgres_pool:
            logger.warning("Database not available, cannot manage sessions.")
            return "00000000-0000-0000-0000-000000000000" # Dummy UUID

        try:
            async with db_manager.postgres_pool.acquire() as conn:
                # 1. Find currently active session
                row = await conn.fetchrow("""
                    SELECT id, updated_at 
                    FROM v2_conversation_sessions 
                    WHERE user_id = $1 AND character_name = $2 AND is_active = TRUE
                    ORDER BY start_time DESC
                    LIMIT 1
                """, user_id, character_name)

                if row:
                    session_id = str(row['id'])
                    last_activity = row['updated_at']
                    
                    # Check for timeout
                    # Ensure last_activity is timezone-aware or naive as needed. 
                    # Postgres usually returns timezone-aware if column is timestamptz.
                    now = datetime.now(timezone.utc)
                    
                    if (now - last_activity) > timedelta(minutes=self.SESSION_TIMEOUT_MINUTES):
                        logger.info(f"Session {session_id} timed out. Closing and creating new one.")
                        await self.close_session(session_id)
                        return await self.create_session(user_id, character_name)
                    else:
                        # Update activity timestamp
                        await self.update_session_activity(session_id)
                        return session_id
                else:
                    # No active session, create new
                    return await self.create_session(user_id, character_name)

        except Exception as e:
            logger.error(f"Failed to get active session: {e}")
            return "00000000-0000-0000-0000-000000000000"

    async def create_session(self, user_id: str, character_name: str) -> str:
        """Creates a new active session."""
        if not db_manager.postgres_pool:
            return "00000000-0000-0000-0000-000000000000"

        try:
            async with db_manager.postgres_pool.acquire() as conn:
                # Close any existing active sessions just in case
                await conn.execute("""
                    UPDATE v2_conversation_sessions
                    SET is_active = FALSE, end_time = NOW()
                    WHERE user_id = $1 AND character_name = $2 AND is_active = TRUE
                """, user_id, character_name)

                session_id = await conn.fetchval("""
                    INSERT INTO v2_conversation_sessions (user_id, character_name, is_active)
                    VALUES ($1, $2, TRUE)
                    RETURNING id
                """, user_id, character_name)
                
                logger.info(f"Created new session {session_id} for {user_id} with {character_name}")
                return str(session_id)
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            return "00000000-0000-0000-0000-000000000000"

    async def close_session(self, session_id: str):
        """Marks a session as inactive."""
        if not db_manager.postgres_pool:
            return

        try:
            async with db_manager.postgres_pool.acquire() as conn:
                # Ensure session_id is a string (asyncpg expects str for UUID columns)
                session_id_str = str(session_id)
                await conn.execute("""
                    UPDATE v2_conversation_sessions
                    SET is_active = FALSE, end_time = NOW()
                    WHERE id = $1
                """, session_id_str)
                logger.debug(f"Closed session {session_id}")
        except Exception as e:
            logger.error(f"Failed to close session: {e}")

    async def update_session_activity(self, session_id: str):
        """Updates the updated_at timestamp of a session."""
        if not db_manager.postgres_pool:
            return

        try:
            async with db_manager.postgres_pool.acquire() as conn:
                session_id_str = str(session_id)
                await conn.execute("""
                    UPDATE v2_conversation_sessions
                    SET updated_at = NOW()
                    WHERE id = $1
                """, session_id_str)
        except Exception as e:
            logger.error(f"Failed to update session activity: {e}")

    async def get_session_start_time(self, session_id: str) -> Optional[datetime]:
        """Retrieves the start time of a session."""
        if not db_manager.postgres_pool:
            return None

        try:
            async with db_manager.postgres_pool.acquire() as conn:
                session_id_str = str(session_id)
                start_time = await conn.fetchval("""
                    SELECT start_time 
                    FROM v2_conversation_sessions 
                    WHERE id = $1
                """, session_id_str)
                return start_time
        except Exception as e:
            logger.error(f"Failed to get session start time: {e}")
            return None

    async def get_stale_sessions(self, timeout_minutes: int = 30) -> List[Dict[str, Any]]:
        """
        Finds active sessions that have been inactive for longer than timeout_minutes.
        """
        if not db_manager.postgres_pool:
            return []

        try:
            async with db_manager.postgres_pool.acquire() as conn:
                # Calculate cutoff time
                # Use UTC now
                cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
                
                rows = await conn.fetch("""
                    SELECT id, user_id, character_name, start_time, updated_at
                    FROM v2_conversation_sessions 
                    WHERE is_active = TRUE AND updated_at < $1
                """, cutoff)
                
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get stale sessions: {e}")
            return []

    async def get_session_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves messages belonging to a session based on time range.
        Returns list of dicts with role, content, timestamp, user_name.
        """
        if not db_manager.postgres_pool:
            return []

        try:
            async with db_manager.postgres_pool.acquire() as conn:
                # Ensure session_id is a string (asyncpg expects str for UUID columns)
                session_id_str = str(session_id)
                
                # Get session details
                session = await conn.fetchrow("""
                    SELECT user_id, character_name, start_time, updated_at, end_time, is_active
                    FROM v2_conversation_sessions 
                    WHERE id = $1
                """, session_id_str)
                
                if not session:
                    return []
                
                # Determine time range
                start_time = session['start_time']
                end_time = session['end_time'] if not session['is_active'] else session['updated_at']
                
                # Add a small buffer to end_time to ensure we catch the last message
                # if timestamps are slightly off or if updated_at was set before message insert committed
                if end_time:
                    end_time_buffer = end_time + timedelta(seconds=5)
                else:
                    end_time_buffer = datetime.now(timezone.utc)

                rows = await conn.fetch("""
                    SELECT role, content, timestamp, user_name
                    FROM v2_chat_history 
                    WHERE user_id = $1 
                    AND character_name = $2
                    AND timestamp >= $3
                    AND timestamp <= $4
                    ORDER BY timestamp ASC
                """, session['user_id'], session['character_name'], start_time, end_time_buffer)
                
                return [
                    {
                        "role": row['role'], 
                        "content": row['content'],
                        "timestamp": row['timestamp'].isoformat() if row['timestamp'] else None,
                        "user_name": row['user_name']
                    } 
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get session messages: {e}")
            return []

# Global instance
session_manager = SessionManager()
