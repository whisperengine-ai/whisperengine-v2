"""Tests for the manipulation timeout manager."""

import pytest
import sys
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch, MagicMock

# Mock settings before importing modules that use it
with patch.dict(os.environ, {
    "DISCORD_TOKEN": "mock_token",
    "DISCORD_BOT_NAME": "testbot",
    "LLM_API_KEY": "mock_key",
    "NEO4J_PASSWORD": "mock_pass",
    "INFLUXDB_TOKEN": "mock_token"
}):
    from src_v2.moderation.timeout_manager import TimeoutManager
    from src_v2.moderation.models import UserTimeoutStatus


class TestUserTimeoutStatus:
    """Tests for UserTimeoutStatus dataclass."""
    
    def test_is_restricted_when_active(self):
        status = UserTimeoutStatus(
            status="active",
            remaining_seconds=0,
            violation_count=0
        )
        assert status.is_restricted() is False
    
    def test_is_restricted_when_timeout(self):
        status = UserTimeoutStatus(
            status="timeout",
            remaining_seconds=120,
            violation_count=1,
            escalation_level=1
        )
        assert status.is_restricted() is True
    
    def test_format_remaining_none(self):
        status = UserTimeoutStatus(
            status="active",
            remaining_seconds=0,
            violation_count=0
        )
        assert status.format_remaining() == "none"
    
    def test_format_remaining_seconds(self):
        status = UserTimeoutStatus(
            status="timeout",
            remaining_seconds=45,
            violation_count=1
        )
        assert status.format_remaining() == "45s"
    
    def test_format_remaining_minutes(self):
        status = UserTimeoutStatus(
            status="timeout",
            remaining_seconds=300,
            violation_count=1
        )
        assert status.format_remaining() == "5m"
    
    def test_format_remaining_hours(self):
        status = UserTimeoutStatus(
            status="timeout",
            remaining_seconds=7500,  # 2h 5m
            violation_count=1
        )
        assert status.format_remaining() == "2h 5m"


class TestTimeoutManager:
    """Tests for TimeoutManager class."""
    
    @pytest.fixture
    def manager(self):
        """Create a fresh TimeoutManager instance."""
        return TimeoutManager()
    
    @pytest.fixture
    def mock_cache(self):
        """Create a mock CacheManager."""
        cache = MagicMock()
        cache.get_json = AsyncMock(return_value=None)
        cache.set_json = AsyncMock(return_value=True)
        cache.delete = AsyncMock(return_value=True)
        return cache
    
    @pytest.mark.asyncio
    async def test_fresh_user_is_active(self, manager, mock_cache):
        """A user with no timeout data should be active."""
        manager._cache = mock_cache
        mock_cache.get_json.return_value = None
        
        status = await manager.check_user_status("user123")
        
        assert status.status == "active"
        assert status.remaining_seconds == 0
        assert status.violation_count == 0
        assert status.escalation_level == 0
    
    @pytest.mark.asyncio
    async def test_first_violation_sets_timeout(self, manager, mock_cache):
        """First violation should set escalation level 1 (2 min timeout)."""
        manager._cache = mock_cache
        mock_cache.get_json.return_value = None
        
        status = await manager.record_violation("user123")
        
        assert status.status == "timeout"
        assert status.violation_count == 1
        assert status.escalation_level == 1
        assert status.remaining_seconds == 120  # 2 minutes
        
        # Verify Redis was called with correct data
        mock_cache.set_json.assert_called_once()
        call_args = mock_cache.set_json.call_args
        key = call_args[0][0]
        data = call_args[0][1]
        
        assert key == "manipulation:timeout:user123"
        assert data["violation_count"] == 1
        assert data["escalation_level"] == 1
    
    @pytest.mark.asyncio
    async def test_escalation_increases_on_repeat(self, manager, mock_cache):
        """Repeated violations should increase escalation level."""
        manager._cache = mock_cache
        
        # Simulate existing violation data
        existing_data = {
            "violation_count": 1,
            "first_violation_at": "2025-11-27T10:00:00+00:00",
            "last_violation_at": "2025-11-27T10:00:00+00:00",
            "timeout_until": "2025-11-27T10:02:00+00:00",  # Expired
            "escalation_level": 1
        }
        mock_cache.get_json.return_value = existing_data
        
        status = await manager.record_violation("user123")
        
        assert status.violation_count == 2
        assert status.escalation_level == 2
        assert status.remaining_seconds == 600  # 10 minutes
    
    @pytest.mark.asyncio
    async def test_escalation_caps_at_level_5(self, manager, mock_cache):
        """Escalation should cap at level 5 (24 hours)."""
        manager._cache = mock_cache
        
        existing_data = {
            "violation_count": 5,
            "first_violation_at": "2025-11-27T10:00:00+00:00",
            "last_violation_at": "2025-11-27T10:00:00+00:00",
            "timeout_until": "2025-11-27T10:02:00+00:00",
            "escalation_level": 5  # Already at max
        }
        mock_cache.get_json.return_value = existing_data
        
        status = await manager.record_violation("user123")
        
        assert status.escalation_level == 5  # Still capped at 5
        assert status.remaining_seconds == 1440 * 60  # 24 hours
    
    @pytest.mark.asyncio
    async def test_timeout_expires_returns_active(self, manager, mock_cache):
        """User should be active after timeout expires."""
        manager._cache = mock_cache
        
        # Timeout expired 5 minutes ago
        past_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        existing_data = {
            "violation_count": 1,
            "first_violation_at": "2025-11-27T10:00:00+00:00",
            "last_violation_at": "2025-11-27T10:00:00+00:00",
            "timeout_until": past_time,
            "escalation_level": 1
        }
        mock_cache.get_json.return_value = existing_data
        
        status = await manager.check_user_status("user123")
        
        assert status.status == "active"
        assert status.remaining_seconds == 0
    
    @pytest.mark.asyncio
    async def test_user_in_timeout_returns_timeout(self, manager, mock_cache):
        """User should be in timeout if timeout_until is in the future."""
        manager._cache = mock_cache
        
        # Timeout in 5 minutes
        future_time = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        existing_data = {
            "violation_count": 1,
            "first_violation_at": "2025-11-27T10:00:00+00:00",
            "last_violation_at": "2025-11-27T10:00:00+00:00",
            "timeout_until": future_time,
            "escalation_level": 1
        }
        mock_cache.get_json.return_value = existing_data
        
        status = await manager.check_user_status("user123")
        
        assert status.status == "timeout"
        assert 290 <= status.remaining_seconds <= 300  # ~5 minutes (allow for test timing)
    
    @pytest.mark.asyncio
    async def test_clear_user_resets_status(self, manager, mock_cache):
        """Clearing a user should remove their timeout data."""
        manager._cache = mock_cache
        
        result = await manager.clear_user("user123")
        
        assert result is True
        mock_cache.delete.assert_called_once_with("manipulation:timeout:user123")
    
    @pytest.mark.asyncio
    async def test_redis_failure_fails_open(self, manager, mock_cache):
        """If Redis fails, user should be allowed through (fail-open)."""
        manager._cache = mock_cache
        mock_cache.get_json.side_effect = Exception("Redis connection failed")
        
        status = await manager.check_user_status("user123")
        
        assert status.status == "active"
        assert status.remaining_seconds == 0
    
    @pytest.mark.asyncio
    async def test_feature_flag_disabled(self, manager, mock_cache):
        """If feature flag is disabled, always return active."""
        manager._cache = mock_cache
        
        with patch('src_v2.moderation.timeout_manager.settings') as mock_settings:
            mock_settings.ENABLE_MANIPULATION_TIMEOUTS = False
            
            status = await manager.check_user_status("user123")
            
            assert status.status == "active"
            mock_cache.get_json.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_decay_reduces_escalation(self, manager, mock_cache):
        """Escalation should decay after 2x timeout of clean time."""
        manager._cache = mock_cache
        
        # Level 2 timeout (10 min) requires 20 min clean time to decay
        # Simulate 25 minutes since last violation (past decay threshold)
        last_violation = (datetime.now(timezone.utc) - timedelta(minutes=25)).isoformat()
        timeout_expired = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
        
        existing_data = {
            "violation_count": 2,
            "first_violation_at": "2025-11-27T10:00:00+00:00",
            "last_violation_at": last_violation,
            "timeout_until": timeout_expired,
            "escalation_level": 2
        }
        mock_cache.get_json.return_value = existing_data
        
        status = await manager.check_user_status("user123")
        
        assert status.status == "active"
        # Verify decay was written back
        mock_cache.set_json.assert_called_once()
        call_args = mock_cache.set_json.call_args
        data = call_args[0][1]
        assert data["escalation_level"] == 1  # Decayed from 2 to 1


class TestEscalationDurations:
    """Tests for escalation duration constants."""
    
    def test_escalation_durations(self):
        """Verify escalation durations match spec."""
        manager = TimeoutManager()
        
        assert manager.ESCALATION_DURATIONS[0] == 0     # No timeout
        assert manager.ESCALATION_DURATIONS[1] == 2     # 2 minutes
        assert manager.ESCALATION_DURATIONS[2] == 10    # 10 minutes
        assert manager.ESCALATION_DURATIONS[3] == 30    # 30 minutes
        assert manager.ESCALATION_DURATIONS[4] == 120   # 2 hours
        assert manager.ESCALATION_DURATIONS[5] == 1440  # 24 hours
    
    def test_decay_multiplier(self):
        """Verify decay multiplier is 2x."""
        manager = TimeoutManager()
        assert manager.DECAY_MULTIPLIER == 2
