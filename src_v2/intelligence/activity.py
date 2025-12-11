from typing import Dict, Tuple, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass
from loguru import logger
from src_v2.config.settings import settings
from src_v2.core.database import db_manager

# Redis key prefixes for activity tracking
REDIS_PREFIX_ACTIVITY = "whisper:activity:"
REDIS_PREFIX_AUTONOMOUS = "whisper:autonomous:"

# TTL constants
ACTIVITY_WINDOW_SECONDS = 30 * 60  # 30 minutes for activity tracking
AUTONOMOUS_POST_LOCK_SECONDS = 30  # Lock held while generating post
CONVERSATION_LOCK_SECONDS = 120    # Lock held during conversation initiation


@dataclass
class ActivitySignal:
    channel_id: str
    guild_id: Optional[str]
    message_count: int
    last_active: float  # timestamp


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
        
    async def record_message(self, guild_id: str, channel_id: Optional[str] = None) -> None:
        """
        Record a message event for the guild and optionally the channel.
        Uses sorted sets with auto-expiry.
        """
        if not db_manager.redis_client:
            return
            
        try:
            now = datetime.now(timezone.utc).timestamp()
            pipeline = db_manager.redis_client.pipeline()
            
            # 1. Record Guild Activity
            guild_key = f"{REDIS_PREFIX_ACTIVITY}guild:{guild_id}:messages"
            pipeline.zadd(guild_key, {str(now): now})
            cutoff = now - ACTIVITY_WINDOW_SECONDS
            pipeline.zremrangebyscore(guild_key, min="-inf", max=cutoff)
            pipeline.expire(guild_key, ACTIVITY_WINDOW_SECONDS + 300)
            
            # 2. Record Channel Activity (if provided)
            if channel_id:
                # Channel messages
                channel_key = f"{REDIS_PREFIX_ACTIVITY}channel:{channel_id}:messages"
                pipeline.zadd(channel_key, {str(now): now})
                pipeline.zremrangebyscore(channel_key, min="-inf", max=cutoff)
                pipeline.expire(channel_key, ACTIVITY_WINDOW_SECONDS + 300)
                
                # Global active channels list (score = last active timestamp)
                # This allows us to find WHICH channels are active without scanning keys
                global_key = f"{REDIS_PREFIX_ACTIVITY}global_channels"
                pipeline.zadd(global_key, {channel_id: now})
                # Also trim global list of very old channels (older than window)
                pipeline.zremrangebyscore(global_key, min="-inf", max=cutoff)
                
                # Store guild mapping for the channel (so we know which guild it belongs to)
                mapping_key = f"{REDIS_PREFIX_ACTIVITY}channel_map:{channel_id}"
                pipeline.set(mapping_key, guild_id, ex=86400) # 24h expiry
            
            await pipeline.execute()
            
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

    async def get_activity_signals(self, since_minutes: int = 15) -> List[ActivitySignal]:
        """
        Returns channels with activity in the last N minutes.
        Sorted by activity density (messages / minute).
        """
        if not db_manager.redis_client:
            return []
            
        try:
            now = datetime.now(timezone.utc).timestamp()
            cutoff = now - (since_minutes * 60)
            
            # 1. Get all channels active in the window
            global_key = f"{REDIS_PREFIX_ACTIVITY}global_channels"
            # Returns list of (channel_id, score)
            active_channels = await db_manager.redis_client.zrangebyscore(
                global_key, min=cutoff, max="+inf", withscores=True
            )
            
            if not active_channels:
                return []
                
            signals = []
            
            # 2. For each channel, get message count and guild ID
            # We can pipeline this for performance
            pipeline = db_manager.redis_client.pipeline()
            
            for channel_id, last_active in active_channels:
                # Count messages in the window
                channel_key = f"{REDIS_PREFIX_ACTIVITY}channel:{channel_id}:messages"
                pipeline.zcount(channel_key, min=cutoff, max="+inf")
                
                # Get guild ID
                mapping_key = f"{REDIS_PREFIX_ACTIVITY}channel_map:{channel_id}"
                pipeline.get(mapping_key)
                
            results = await pipeline.execute()
            
            # Results are interleaved: [count1, guild1, count2, guild2, ...]
            for i, (channel_id, last_active) in enumerate(active_channels):
                count = results[i * 2]
                guild_id_bytes = results[i * 2 + 1]
                guild_id = guild_id_bytes.decode() if guild_id_bytes else None
                
                if count > 0:
                    signals.append(ActivitySignal(
                        channel_id=channel_id,
                        guild_id=guild_id,
                        message_count=count,
                        last_active=last_active
                    ))
            
            # Sort by message count descending
            signals.sort(key=lambda x: x.message_count, reverse=True)
            return signals
            
        except Exception as e:
            logger.warning(f"Failed to get activity signals: {e}")
            return []

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
        """Release conversation lock (only if we own it).
        
        Uses atomic check-and-delete via Lua script to prevent race conditions.
        """
        if not db_manager.redis_client:
            return
            
        lock_key = f"{REDIS_PREFIX_AUTONOMOUS}guild:{guild_id}:conversation_lock"
        
        try:
            # Atomic check-and-delete using Lua script
            # Only deletes if the value starts with our bot name
            lua_script = """
            local current = redis.call('GET', KEYS[1])
            if current and string.find(current, ARGV[1]) == 1 then
                return redis.call('DEL', KEYS[1])
            end
            return 0
            """
            result = await db_manager.redis_client.eval(lua_script, 1, lock_key, f"{bot_name}:")
            if result:
                logger.debug(f"[Activity] Released conversation lock for guild {guild_id}")
        except Exception as e:
            logger.debug(f"Failed to release conversation lock: {e}")

    async def clear_post_cooldown(self, guild_id: str) -> None:
        """Clear the post cooldown for a guild (used when post generation fails)."""
        if not db_manager.redis_client:
            return
            
        cooldown_key = f"{REDIS_PREFIX_AUTONOMOUS}guild:{guild_id}:post_cooldown"
        
        try:
            await db_manager.redis_client.delete(cooldown_key)
            logger.debug(f"[Activity] Cleared post cooldown for guild {guild_id}")
        except Exception as e:
            logger.debug(f"Failed to clear post cooldown: {e}")

    # ========== Legacy methods for backwards compatibility ==========
    # These wrap the new atomic methods
    
    async def record_autonomous_post(self, guild_id: str, bot_name: str, cooldown_minutes: int = 10) -> None:
        """Legacy: Force-set a post cooldown (overwrites any existing)."""
        if not db_manager.redis_client:
            return
            
        cooldown_seconds = cooldown_minutes * 60
        cooldown_key = f"{REDIS_PREFIX_AUTONOMOUS}guild:{guild_id}:post_cooldown"
        
        try:
            # Force set (no NX) - overwrites any existing cooldown
            await db_manager.redis_client.set(
                cooldown_key,
                f"{bot_name}:{datetime.now(timezone.utc).isoformat()}",
                ex=cooldown_seconds
            )
        except Exception as e:
            logger.warning(f"Failed to record autonomous post: {e}")
    
    async def check_autonomous_post_cooldown(self, guild_id: str, cooldown_minutes: int = 10) -> tuple[bool, str | None]:
        """Legacy: Check if on cooldown. Returns (is_on_cooldown, bot_name)."""
        is_on_cooldown, bot_name, _ = await self.check_post_cooldown(guild_id)
        return is_on_cooldown, bot_name


activity_modeler = ActivityModeler()
server_monitor = ServerActivityMonitor()
