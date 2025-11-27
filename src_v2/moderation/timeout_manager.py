"""
Timeout manager for handling manipulation detection and user timeouts.

Tracks user violations in Redis with a decay-based warning score system.
Violations accumulate as a score that decays over time, providing a
forgiving experience for occasional slip-ups while being strict on
rapid-fire abuse.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from loguru import logger

from src_v2.core.cache import CacheManager
from src_v2.config.settings import settings
from src_v2.moderation.models import UserTimeoutStatus


class TimeoutManager:
    """
    Manages user timeouts for manipulation attempts.
    
    Uses a decay-based warning score system:
    - Each violation adds 1.0 to the warning score
    - Score decays over time (30-minute half-life)
    - When score >= 3.0, timeout begins
    
    This is more forgiving than simple strike counting:
    - 3 rapid strikes → immediate timeout
    - 2 strikes, wait 30 min, 1 strike → score ~1.5, still in warning
    - Occasional slip-ups decay away naturally
    
    After timeout threshold reached, exponential backoff applies:
    - Level 1: 2 minutes
    - Level 2: 10 minutes  
    - Level 3: 30 minutes
    - Level 4: 2 hours
    - Level 5: 24 hours
    """
    
    REDIS_PREFIX = "manipulation:timeout:"
    
    # Warning score threshold before timeout kicks in
    WARNING_SCORE_THRESHOLD = 3.0
    
    # Half-life for score decay in minutes
    # After this time, a violation's contribution is halved
    SCORE_DECAY_HALF_LIFE_MINUTES = 30
    
    # Maximum time to track violations (after this, they're fully decayed)
    MAX_VIOLATION_AGE_MINUTES = 120  # 2 hours
    
    # Escalation durations in minutes: [level 0, 1, 2, 3, 4, 5]
    ESCALATION_DURATIONS = [0, 2, 10, 30, 120, 1440]
    
    # Clean time multiplier for decay (2x timeout = drop 1 level)
    DECAY_MULTIPLIER = 2
    
    def __init__(self) -> None:
        self._cache = CacheManager()
    
    def _utc_now(self) -> datetime:
        """Get current UTC time."""
        return datetime.now(timezone.utc)
    
    def _parse_datetime(self, iso_string: str) -> datetime:
        """Parse ISO datetime string to datetime object."""
        # Handle both with and without timezone
        if iso_string.endswith('Z'):
            iso_string = iso_string[:-1] + '+00:00'
        return datetime.fromisoformat(iso_string)
    
    def _default_timeout_data(self) -> Dict[str, Any]:
        """Create default timeout data for a new user."""
        return {
            "violation_timestamps": [],  # List of ISO timestamps
            "timeout_until": None,
            "escalation_level": 0,
            "timeout_count": 0  # How many times they've been timed out
        }
    
    def _get_redis_key(self, user_id: str, bot_name: Optional[str] = None) -> str:
        """Get Redis key based on scope setting."""
        scope = getattr(settings, "MANIPULATION_TIMEOUT_SCOPE", "per_bot")
        
        if scope == "global":
            return f"{self.REDIS_PREFIX}global:{user_id}"
        
        # Default to per_bot
        name = bot_name or settings.DISCORD_BOT_NAME
        return f"{self.REDIS_PREFIX}{name}:{user_id}"

    def _calculate_warning_score(self, violation_timestamps: list, now: datetime) -> float:
        """
        Calculate the current warning score based on decayed violations.
        
        Each violation contributes: 1.0 * decay_factor
        where decay_factor = 0.5 ^ (minutes_elapsed / half_life)
        
        Args:
            violation_timestamps: List of ISO timestamp strings
            now: Current UTC time
            
        Returns:
            Current warning score (0.0 to unbounded, typically 0-5)
        """
        score = 0.0
        half_life = self.SCORE_DECAY_HALF_LIFE_MINUTES
        max_age = self.MAX_VIOLATION_AGE_MINUTES
        
        for ts_str in violation_timestamps:
            ts = self._parse_datetime(ts_str)
            minutes_elapsed = (now - ts).total_seconds() / 60
            
            # Skip violations older than max age
            if minutes_elapsed > max_age:
                continue
            
            # Very recent violations (within 10 seconds) count as full 1.0
            if minutes_elapsed < 10/60:  # Less than 10 seconds
                decay_factor = 1.0
            else:
                # Calculate decay factor using half-life formula
                # decay = 0.5 ^ (t / half_life)
                decay_factor = 0.5 ** (minutes_elapsed / half_life)
            
            score += decay_factor
        
        return score
    
    def _prune_old_violations(self, violation_timestamps: list, now: datetime) -> list:
        """Remove violations older than MAX_VIOLATION_AGE_MINUTES."""
        max_age = self.MAX_VIOLATION_AGE_MINUTES
        pruned = []
        
        for ts_str in violation_timestamps:
            ts = self._parse_datetime(ts_str)
            minutes_elapsed = (now - ts).total_seconds() / 60
            if minutes_elapsed <= max_age:
                pruned.append(ts_str)
        
        return pruned
    
    async def check_user_status(self, user_id: str, bot_name: Optional[str] = None) -> UserTimeoutStatus:
        """
        Check if a user is currently in timeout.
        
        Args:
            user_id: Discord user ID
            bot_name: Optional bot name for per-bot scoping
            
        Returns:
            UserTimeoutStatus with current status
        """
        # Feature flag check
        if not getattr(settings, 'ENABLE_MANIPULATION_TIMEOUTS', True):
            return UserTimeoutStatus(
                status="active",
                remaining_seconds=0,
                violation_count=0,
                escalation_level=0
            )
        
        key = self._get_redis_key(user_id, bot_name)
        
        try:
            data = await self._cache.get_json(key)
        except Exception as e:
            # Fail-open: if Redis is down, allow the message
            logger.warning(f"Redis check failed for user {user_id}, failing open: {e}")
            return UserTimeoutStatus(
                status="active",
                remaining_seconds=0,
                violation_count=0,
                escalation_level=0
            )
        
        if not data:
            return UserTimeoutStatus(
                status="active",
                remaining_seconds=0,
                violation_count=0,
                escalation_level=0
            )
        
        now = self._utc_now()
        violation_timestamps = data.get("violation_timestamps", [])
        escalation_level = data.get("escalation_level", 0)
        
        # Calculate current warning score
        warning_score = self._calculate_warning_score(violation_timestamps, now)
        violation_count = len(violation_timestamps)
        
        # Check if timeout has expired
        timeout_until_str = data.get("timeout_until")
        if not timeout_until_str:
            # No active timeout - check if in warning period
            if warning_score > 0 and warning_score < self.WARNING_SCORE_THRESHOLD:
                return UserTimeoutStatus(
                    status="warning",
                    remaining_seconds=0,
                    violation_count=violation_count,
                    escalation_level=escalation_level,
                    warning_score=round(warning_score, 2)
                )
            return UserTimeoutStatus(
                status="active",
                remaining_seconds=0,
                violation_count=violation_count,
                escalation_level=escalation_level,
                warning_score=round(warning_score, 2)
            )
        
        timeout_until = self._parse_datetime(timeout_until_str)
        
        if now >= timeout_until:
            # Timeout expired - check if we should decay escalation
            await self._maybe_decay_escalation(user_id, data)
            return UserTimeoutStatus(
                status="active",
                remaining_seconds=0,
                violation_count=violation_count,
                escalation_level=escalation_level,
                warning_score=round(warning_score, 2)
            )
        
        # Still in timeout
        remaining = int((timeout_until - now).total_seconds())
        
        return UserTimeoutStatus(
            status="timeout",
            remaining_seconds=remaining,
            violation_count=violation_count,
            escalation_level=escalation_level,
            warning_score=round(warning_score, 2)
        )
    
    async def record_violation(self, user_id: str, bot_name: Optional[str] = None) -> UserTimeoutStatus:
        """
        Record a manipulation violation for a user.
        
        Adds violation to timestamps, calculates warning score,
        and applies timeout if score exceeds threshold.
        
        Args:
            user_id: Discord user ID
            bot_name: Optional bot name for per-bot scoping
            
        Returns:
            Updated UserTimeoutStatus
        """
        # Feature flag check
        if not getattr(settings, 'ENABLE_MANIPULATION_TIMEOUTS', True):
            return UserTimeoutStatus(
                status="active",
                remaining_seconds=0,
                violation_count=0,
                escalation_level=0
            )
        
        key = self._get_redis_key(user_id, bot_name)
        now = self._utc_now()
        
        try:
            data = await self._cache.get_json(key) or self._default_timeout_data()
        except Exception as e:
            logger.warning(f"Redis get failed for user {user_id}: {e}")
            data = self._default_timeout_data()
        
        # Get and prune old violations
        violation_timestamps = data.get("violation_timestamps", [])
        violation_timestamps = self._prune_old_violations(violation_timestamps, now)
        
        # Add new violation
        violation_timestamps.append(now.isoformat())
        data["violation_timestamps"] = violation_timestamps
        
        # Calculate new warning score
        warning_score = self._calculate_warning_score(violation_timestamps, now)
        violation_count = len(violation_timestamps)
        
        # Check if still in warning period (use small epsilon for float comparison)
        if warning_score < self.WARNING_SCORE_THRESHOLD - 0.001:
            # Still in warning period - no timeout yet
            try:
                # TTL = max violation age to keep history
                await self._cache.set_json(key, data, ttl=self.MAX_VIOLATION_AGE_MINUTES * 60)
            except Exception as e:
                logger.error(f"Redis set failed for user {user_id}: {e}")
            
            logger.warning(
                f"Manipulation warning: user={user_id} "
                f"score={warning_score:.2f}/{self.WARNING_SCORE_THRESHOLD} "
                f"violations={violation_count}"
            )
            
            return UserTimeoutStatus(
                status="warning",
                remaining_seconds=0,
                violation_count=violation_count,
                escalation_level=0,
                warning_score=round(warning_score, 2)
            )
        
        # Exceeded warning threshold - apply timeout
        # Increment timeout count and calculate escalation level
        data["timeout_count"] = data.get("timeout_count", 0) + 1
        data["escalation_level"] = min(data["timeout_count"], 5)
        
        # Calculate timeout duration
        timeout_minutes = self.ESCALATION_DURATIONS[data["escalation_level"]]
        timeout_until = now + timedelta(minutes=timeout_minutes)
        data["timeout_until"] = timeout_until.isoformat()
        
        # Set with appropriate TTL (at least 2 hours to track history)
        ttl_seconds = max(timeout_minutes * 60, 7200)
        
        try:
            await self._cache.set_json(key, data, ttl=ttl_seconds)
        except Exception as e:
            logger.error(f"Redis set failed for user {user_id}: {e}")
        
        logger.warning(
            f"Manipulation timeout: user={user_id} "
            f"score={warning_score:.2f} "
            f"level={data['escalation_level']} "
            f"timeout={timeout_minutes}m"
        )
        
        return UserTimeoutStatus(
            status="timeout",
            remaining_seconds=timeout_minutes * 60,
            violation_count=violation_count,
            escalation_level=data["escalation_level"],
            warning_score=round(warning_score, 2)
        )
    
    async def _maybe_decay_escalation(self, user_id: str, data: Dict[str, Any]) -> None:
        """
        Decay escalation level if enough clean time has passed.
        
        Clean time needed = 2x the last timeout duration.
        """
        escalation_level = data.get("escalation_level", 0)
        if escalation_level == 0:
            return
        
        # Check last violation time
        violation_timestamps = data.get("violation_timestamps", [])
        if not violation_timestamps:
            return
        
        # Get most recent violation
        last_violation = self._parse_datetime(violation_timestamps[-1])
        now = self._utc_now()
        
        # Calculate decay threshold
        last_timeout_minutes = self.ESCALATION_DURATIONS[escalation_level]
        decay_threshold_minutes = last_timeout_minutes * self.DECAY_MULTIPLIER
        
        clean_time = now - last_violation
        clean_time_minutes = clean_time.total_seconds() / 60
        
        if clean_time_minutes >= decay_threshold_minutes:
            # Decay by 1 level
            data["escalation_level"] = max(0, escalation_level - 1)
            data["timeout_count"] = max(0, data.get("timeout_count", 1) - 1)
            
            key = f"{self.REDIS_PREFIX}{user_id}"
            try:
                await self._cache.set_json(key, data, ttl=3600)
                logger.info(
                    f"Manipulation timeout decay: user={user_id} "
                    f"level={escalation_level}->{data['escalation_level']}"
                )
            except Exception as e:
                logger.warning(f"Redis set failed during decay for user {user_id}: {e}")
    
    async def clear_user(self, user_id: str) -> bool:
        """
        Clear a user's timeout status (admin function).
        
        Args:
            user_id: Discord user ID
            
        Returns:
            True if cleared successfully
        """
        key = f"{self.REDIS_PREFIX}{user_id}"
        try:
            await self._cache.delete(key)
            logger.info(f"Manipulation timeout cleared for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear timeout for user {user_id}: {e}")
            return False
    
    async def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed timeout info for a user (for admin/debugging).
        
        Args:
            user_id: Discord user ID
            
        Returns:
            Raw timeout data dict or None
        """
        key = f"{self.REDIS_PREFIX}{user_id}"
        try:
            return await self._cache.get_json(key)
        except Exception as e:
            logger.warning(f"Failed to get timeout info for user {user_id}: {e}")
            return None


# Global singleton instance
timeout_manager = TimeoutManager()
