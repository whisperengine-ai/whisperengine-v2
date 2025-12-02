from typing import Dict, Tuple
from datetime import datetime, timezone
from loguru import logger
from src_v2.core.database import db_manager


class ActivityModeler:
    """
    Analyzes user activity patterns to determine the best time to engage.
    """
    
    def __init__(self) -> None:
        pass

    async def get_user_activity_heatmap(self, user_id: str) -> Dict[str, float]:
        """
        Generates a heatmap of user activity probability for each hour of the week.
        Returns a dictionary where keys are "{weekday}_{hour}" (e.g., "0_14" for Monday 2 PM)
        and values are probabilities (0.0 to 1.0).
        
        Weekday: 0=Monday, 6=Sunday
        Hour: 0-23
        """
        if not db_manager.postgres_pool:
            logger.warning("Database not available for activity modeling.")
            return {}

        try:
            async with db_manager.postgres_pool.acquire() as conn:
                # Fetch all session start times for the user
                # We look back up to 30 days to keep it relevant
                rows = await conn.fetch("""
                    SELECT start_time 
                    FROM v2_conversation_sessions 
                    WHERE user_id = $1 
                    AND start_time > NOW() - INTERVAL '30 days'
                """, user_id)

                if not rows:
                    return {}

                # Initialize grid (7 days * 24 hours)
                activity_counts: Dict[str, int] = {}
                total_sessions: int = len(rows)

                for row in rows:
                    start_time: datetime = row['start_time']
                    # Ensure UTC
                    if start_time.tzinfo is None:
                        start_time = start_time.replace(tzinfo=timezone.utc)
                    
                    # Convert to user's local time? 
                    # Ideally yes, but we don't store user timezone yet.
                    # We will assume the bot operates in UTC or server time for now.
                    
                    weekday: int = start_time.weekday() # 0-6
                    hour: int = start_time.hour # 0-23
                    key: str = f"{weekday}_{hour}"
                    
                    activity_counts[key] = activity_counts.get(key, 0) + 1

                # Normalize to probabilities
                heatmap: Dict[str, float] = {k: v / total_sessions for k, v in activity_counts.items()}
                return heatmap

        except Exception as e:
            logger.error(f"Failed to generate activity heatmap: {e}")
            return {}

    async def is_good_time_to_message(self, user_id: str, threshold: float = 0.1) -> Tuple[bool, float]:
        """
        Determines if now is a good time to message the user.
        Returns (is_good_time, confidence_score).
        """
        heatmap = await self.get_user_activity_heatmap(user_id)
        if not heatmap:
            # No data, assume it's NOT a good time to avoid spamming new users
            return False, 0.0

        now: datetime = datetime.now(timezone.utc)
        weekday: int = now.weekday()
        hour: int = now.hour
        key: str = f"{weekday}_{hour}"
        
        probability: float = heatmap.get(key, 0.0)
        
        # Also check adjacent hours (smoothing)
        # If user is usually active at 5 PM, 4 PM might also be okay.
        prev_hour: int = (hour - 1) % 24
        next_hour: int = (hour + 1) % 24
        
        prob_prev: float = heatmap.get(f"{weekday}_{prev_hour}", 0.0)
        prob_next: float = heatmap.get(f"{weekday}_{next_hour}", 0.0)
        
        # Weighted score
        score: float = (probability * 0.6) + (prob_prev * 0.2) + (prob_next * 0.2)
        
        is_good: bool = score >= threshold
        return is_good, score

class ServerActivityMonitor:
    """
    Tracks server activity levels (messages per minute) to detect quiet periods.
    Used by ActivityOrchestrator to scale bot autonomy.
    """
    def __init__(self, window_minutes: int = 30):
        self.window_minutes = window_minutes
        # We'll use Redis to store message timestamps for a sliding window
        # Key: whisper:activity:guild:{guild_id}:timestamps
        
    async def record_message(self, guild_id: str) -> None:
        """Record a message event for the guild."""
        if not db_manager.redis_client:
            return
            
        try:
            key = f"whisper:activity:guild:{guild_id}:timestamps"
            now = datetime.now(timezone.utc).timestamp()
            
            # Add timestamp to sorted set
            await db_manager.redis_client.zadd(key, {str(now): now})
            
            # Trim old entries (older than window)
            cutoff = now - (self.window_minutes * 60)
            await db_manager.redis_client.zremrangebyscore(key, min="-inf", max=cutoff)
            
            # Set expiry on the key so it cleans up if unused
            await db_manager.redis_client.expire(key, self.window_minutes * 60 + 60)
            
        except Exception as e:
            logger.warning(f"Failed to record activity: {e}")

    async def get_activity_level(self, guild_id: str) -> float:
        """
        Get messages per minute over the configured window.
        """
        if not db_manager.redis_client:
            return 0.0
            
        try:
            key = f"whisper:activity:guild:{guild_id}:timestamps"
            
            # Count items in set
            count = await db_manager.redis_client.zcard(key)
            
            # Calculate rate
            rate = count / self.window_minutes
            return rate
            
        except Exception as e:
            logger.warning(f"Failed to get activity level: {e}")
            return 0.0

activity_modeler = ActivityModeler()
server_monitor = ServerActivityMonitor()
