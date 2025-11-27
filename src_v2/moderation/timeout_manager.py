"""
Timeout manager for handling manipulation detection and user timeouts.

Tracks user violations in Redis with exponential backoff timeouts.
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
    
    Uses Redis to track violations with exponential backoff:
    - Level 1: 2 minutes
    - Level 2: 10 minutes  
    - Level 3: 30 minutes
    - Level 4: 2 hours
    - Level 5: 24 hours
    
    Timeouts auto-expire via Redis TTL. Escalation decays over time
    if user behaves (2x the timeout duration of clean time).
    """
    
    REDIS_PREFIX = "manipulation:timeout:"
    
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
            "violation_count": 0,
            "first_violation_at": None,
            "last_violation_at": None,
            "timeout_until": None,
            "escalation_level": 0
        }
    
    async def check_user_status(self, user_id: str) -> UserTimeoutStatus:
        """
        Check if a user is currently in timeout.
        
        Args:
            user_id: Discord user ID
            
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
        
        key = f"{self.REDIS_PREFIX}{user_id}"
        
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
        
        # Check if timeout has expired
        timeout_until_str = data.get("timeout_until")
        if not timeout_until_str:
            return UserTimeoutStatus(
                status="active",
                remaining_seconds=0,
                violation_count=data.get("violation_count", 0),
                escalation_level=data.get("escalation_level", 0)
            )
        
        timeout_until = self._parse_datetime(timeout_until_str)
        now = self._utc_now()
        
        if now >= timeout_until:
            # Timeout expired - check if we should decay escalation
            await self._maybe_decay_escalation(user_id, data)
            return UserTimeoutStatus(
                status="active",
                remaining_seconds=0,
                violation_count=data.get("violation_count", 0),
                escalation_level=data.get("escalation_level", 0)
            )
        
        # Still in timeout
        remaining = int((timeout_until - now).total_seconds())
        
        return UserTimeoutStatus(
            status="timeout",
            remaining_seconds=remaining,
            violation_count=data.get("violation_count", 0),
            escalation_level=data.get("escalation_level", 0)
        )
    
    async def record_violation(self, user_id: str) -> UserTimeoutStatus:
        """
        Record a manipulation violation for a user.
        
        Increments violation count and escalation level,
        sets timeout with exponential backoff.
        
        Args:
            user_id: Discord user ID
            
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
        
        key = f"{self.REDIS_PREFIX}{user_id}"
        now = self._utc_now()
        
        try:
            data = await self._cache.get_json(key) or self._default_timeout_data()
        except Exception as e:
            logger.warning(f"Redis get failed for user {user_id}: {e}")
            data = self._default_timeout_data()
        
        # Increment counts
        data["violation_count"] = data.get("violation_count", 0) + 1
        data["last_violation_at"] = now.isoformat()
        
        if not data.get("first_violation_at"):
            data["first_violation_at"] = now.isoformat()
        
        # Calculate new escalation level (cap at 5)
        current_level = data.get("escalation_level", 0)
        data["escalation_level"] = min(current_level + 1, 5)
        
        # Calculate timeout duration
        timeout_minutes = self.ESCALATION_DURATIONS[data["escalation_level"]]
        timeout_until = now + timedelta(minutes=timeout_minutes)
        data["timeout_until"] = timeout_until.isoformat()
        
        # Set with appropriate TTL (at least 1 hour to track history)
        ttl_seconds = max(timeout_minutes * 60, 3600)
        
        try:
            await self._cache.set_json(key, data, ttl=ttl_seconds)
        except Exception as e:
            logger.error(f"Redis set failed for user {user_id}: {e}")
        
        logger.warning(
            f"Manipulation timeout: user={user_id} "
            f"violation=#{data['violation_count']} "
            f"level={data['escalation_level']} "
            f"timeout={timeout_minutes}m"
        )
        
        return UserTimeoutStatus(
            status="timeout",
            remaining_seconds=timeout_minutes * 60,
            violation_count=data["violation_count"],
            escalation_level=data["escalation_level"]
        )
    
    async def _maybe_decay_escalation(self, user_id: str, data: Dict[str, Any]) -> None:
        """
        Decay escalation level if enough clean time has passed.
        
        Clean time needed = 2x the last timeout duration.
        """
        escalation_level = data.get("escalation_level", 0)
        if escalation_level == 0:
            return
        
        last_violation_str = data.get("last_violation_at")
        if not last_violation_str:
            return
        
        last_violation = self._parse_datetime(last_violation_str)
        now = self._utc_now()
        
        # Calculate decay threshold
        last_timeout_minutes = self.ESCALATION_DURATIONS[escalation_level]
        decay_threshold_minutes = last_timeout_minutes * self.DECAY_MULTIPLIER
        
        clean_time = now - last_violation
        clean_time_minutes = clean_time.total_seconds() / 60
        
        if clean_time_minutes >= decay_threshold_minutes:
            # Decay by 1 level
            data["escalation_level"] = max(0, escalation_level - 1)
            
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
