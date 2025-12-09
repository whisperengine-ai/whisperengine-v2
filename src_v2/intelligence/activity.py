from typing import Dict, Tuple
from datetime import datetime, timezone
from loguru import logger
from src_v2.core.database import db_manager

# Redis key prefixes for activity tracking
REDIS_PREFIX_ACTIVITY = "whisper:activity:"
REDIS_PREFIX_AUTONOMOUS = "whisper:autonomous:"

# TTL constants
ACTIVITY_WINDOW_SECONDS = 30 * 60  # 30 minutes for activity tracking
AUTONOMOUS_POST_LOCK_SECONDS = 30  # Lock held while generating post
CONVERSATION_LOCK_SECONDS = 120    # Lock held during conversation initiation


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
    Tracks server activity levels and coordinates autonomous bot activity.
    
    All state is stored in Redis with proper TTLs:
    - Activity levels: Sliding window of message timestamps (auto-expires)
    - Post cooldowns: Simple TTL keys (no timestamp checking needed)
    - Distributed locks: Atomic SET NX EX for race condition prevention
    
    Redis Keys:
    - whisper:activity:guild:{guild_id}:messages - Sorted set of message timestamps
    - whisper:autonomous:guild:{guild_id}:post_cooldown - TTL-based cooldown (exists = on cooldown)
    - whisper:autonomous:guild:{guild_id}:post_lock - Distributed lock for posting
    - whisper:autonomous:guild:{guild_id}:conversation_lock - Distributed lock for conversations
    """
    
    def __init__(self, window_minutes: int = 30):
        self.window_minutes = window_minutes
        
    # ========== Activity Level Tracking ==========
        
    async def record_message(self, guild_id: str) -> None:
        """Record a message event for the guild. Uses sorted set with auto-expiry."""
        if not db_manager.redis_client:
            return
            
        try:
            key = f"{REDIS_PREFIX_ACTIVITY}guild:{guild_id}:messages"
            now = datetime.now(timezone.utc).timestamp()
            
            # Add timestamp to sorted set (score = timestamp for range queries)
            await db_manager.redis_client.zadd(key, {str(now): now})
            
            # Trim old entries (older than window) - keeps set bounded
            cutoff = now - ACTIVITY_WINDOW_SECONDS
            await db_manager.redis_client.zremrangebyscore(key, min="-inf", max=cutoff)
            
            # Set TTL so key auto-cleans if guild goes inactive
            await db_manager.redis_client.expire(key, ACTIVITY_WINDOW_SECONDS + 300)
            
        except Exception as e:
            logger.warning(f"Failed to record activity: {e}")

    async def get_activity_level(self, guild_id: str) -> float:
        """Get messages per minute over the configured window."""
        if not db_manager.redis_client:
            return 0.0
            
        try:
            key = f"{REDIS_PREFIX_ACTIVITY}guild:{guild_id}:messages"
            count = await db_manager.redis_client.zcard(key)
            rate = count / self.window_minutes
            return rate
            
        except Exception as e:
            logger.warning(f"Failed to get activity level: {e}")
            return 0.0

    # ========== Autonomous Post Cooldown (TTL-based) ==========
    # Instead of storing timestamps and checking elapsed time,
    # we use Redis TTL: if the key exists, we're on cooldown.
    
    async def try_acquire_post_slot(self, guild_id: str, bot_name: str, cooldown_seconds: int) -> bool:
        """
        Atomically try to acquire the right to post autonomously.
        
        Uses SET NX EX pattern:
        - If key doesn't exist: Sets it with TTL and returns True (we can post)
        - If key exists: Another bot recently posted, returns False (skip)
        
        This replaces both check_cooldown AND record_post with a single atomic operation.
        The TTL automatically expires the cooldown - no manual cleanup needed.
        
        Args:
            guild_id: The guild to post in
            bot_name: The bot trying to post (stored for debugging)
            cooldown_seconds: How long the cooldown lasts
            
        Returns:
            True if this bot acquired the slot and should post
            False if another bot is on cooldown - skip posting
        """
        if not db_manager.redis_client:
            # No Redis = no coordination, allow (but risky)
            return True
            
        cooldown_key = f"{REDIS_PREFIX_AUTONOMOUS}guild:{guild_id}:post_cooldown"
        
        try:
            # Atomic: SET key value NX EX seconds
            # NX = only set if key doesn't exist
            # EX = auto-expire after cooldown_seconds
            was_set = await db_manager.redis_client.set(
                cooldown_key,
                f"{bot_name}:{datetime.now(timezone.utc).isoformat()}",
                nx=True,
                ex=cooldown_seconds
            )
            
            if was_set:
                logger.info(f"[Activity] {bot_name} acquired autonomous post slot for guild {guild_id} (TTL={cooldown_seconds}s)")
                return True
            else:
                # Key exists - another bot is on cooldown
                existing = await db_manager.redis_client.get(cooldown_key)
                ttl = await db_manager.redis_client.ttl(cooldown_key)
                if isinstance(existing, bytes):
                    existing = existing.decode()
                logger.info(f"[Activity] Post cooldown active in guild {guild_id}: {existing} (TTL={ttl}s remaining)")
                return False
                
        except Exception as e:
            logger.warning(f"Failed to acquire post slot: {e}")
            # On error, be conservative and skip
            return False
    
    async def check_post_cooldown(self, guild_id: str) -> tuple[bool, str | None, int]:
        """
        Check if autonomous posting is on cooldown (read-only check).
        
        Returns:
            (is_on_cooldown, last_bot_name, seconds_remaining)
        """
        if not db_manager.redis_client:
            return False, None, 0
            
        cooldown_key = f"{REDIS_PREFIX_AUTONOMOUS}guild:{guild_id}:post_cooldown"
        
        try:
            existing = await db_manager.redis_client.get(cooldown_key)
            if not existing:
                return False, None, 0
                
            ttl = await db_manager.redis_client.ttl(cooldown_key)
            
            if isinstance(existing, bytes):
                existing = existing.decode()
            
            # Parse bot name from stored value "botname:timestamp"
            bot_name = existing.split(":")[0] if ":" in existing else existing
            
            return True, bot_name, max(0, ttl)
            
        except Exception as e:
            logger.warning(f"Failed to check post cooldown: {e}")
            return False, None, 0

    # ========== Distributed Locks for Conversation Initiation ==========
    # Prevents multiple bots from trying to start conversations simultaneously
    
    async def acquire_conversation_lock(self, guild_id: str, bot_name: str) -> bool:
        """
        Acquire distributed lock for starting a conversation in a guild.
        
        Only one bot can hold this lock at a time. Lock auto-expires after
        CONVERSATION_LOCK_SECONDS to prevent deadlocks.
        
        Returns:
            True if lock acquired (proceed with conversation)
            False if another bot is initiating (skip)
        """
        if not db_manager.redis_client:
            return True
            
        lock_key = f"{REDIS_PREFIX_AUTONOMOUS}guild:{guild_id}:conversation_lock"
        lock_value = f"{bot_name}:{datetime.now(timezone.utc).isoformat()}"
        
        try:
            was_set = await db_manager.redis_client.set(
                lock_key,
                lock_value,
                nx=True,
                ex=CONVERSATION_LOCK_SECONDS
            )
            
            if was_set:
                logger.debug(f"[Activity] {bot_name} acquired conversation lock for guild {guild_id}")
                return True
            else:
                existing = await db_manager.redis_client.get(lock_key)
                if isinstance(existing, bytes):
                    existing = existing.decode()
                logger.info(f"[Activity] Conversation lock held: {existing}")
                return False
                
        except Exception as e:
            logger.warning(f"Failed to acquire conversation lock: {e}")
            return False
    
    async def release_conversation_lock(self, guild_id: str, bot_name: str) -> None:
        """Release conversation lock (only if we own it)."""
        if not db_manager.redis_client:
            return
            
        lock_key = f"{REDIS_PREFIX_AUTONOMOUS}guild:{guild_id}:conversation_lock"
        
        try:
            current = await db_manager.redis_client.get(lock_key)
            if current:
                if isinstance(current, bytes):
                    current = current.decode()
                if current.startswith(f"{bot_name}:"):
                    await db_manager.redis_client.delete(lock_key)
                    logger.debug(f"[Activity] Released conversation lock for guild {guild_id}")
        except Exception as e:
            logger.debug(f"Failed to release conversation lock: {e}")

    # ========== Legacy methods for backwards compatibility ==========
    # These wrap the new atomic methods
    
    async def record_autonomous_post(self, guild_id: str, bot_name: str, cooldown_minutes: int = 10) -> None:
        """Legacy: Record a post. Now just sets the cooldown key if not already set."""
        cooldown_seconds = cooldown_minutes * 60
        await self.try_acquire_post_slot(guild_id, bot_name, cooldown_seconds)
    
    async def check_autonomous_post_cooldown(self, guild_id: str, cooldown_minutes: int = 10) -> tuple[bool, str | None]:
        """Legacy: Check if on cooldown. Returns (is_on_cooldown, bot_name)."""
        is_on_cooldown, bot_name, _ = await self.check_post_cooldown(guild_id)
        return is_on_cooldown, bot_name


activity_modeler = ActivityModeler()
server_monitor = ServerActivityMonitor()
