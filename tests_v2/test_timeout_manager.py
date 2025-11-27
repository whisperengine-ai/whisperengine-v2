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
    
    def test_is_restricted_when_warning(self):
        status = UserTimeoutStatus(
            status="warning",
            remaining_seconds=0,
            violation_count=2,
            escalation_level=0,
            warning_score=1.5
        )
        assert status.is_restricted() is False
        assert status.is_warned() is True
    
    def test_is_restricted_when_timeout(self):
        status = UserTimeoutStatus(
            status="timeout",
            remaining_seconds=120,
            violation_count=4,
            escalation_level=1,
            warning_score=3.5
        )
        assert status.is_restricted() is True
        assert status.is_warned() is False
    
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
            violation_count=4
        )
        assert status.format_remaining() == "45s"
    
    def test_format_remaining_minutes(self):
        status = UserTimeoutStatus(
            status="timeout",
            remaining_seconds=300,
            violation_count=4
        )
        assert status.format_remaining() == "5m"
    
    def test_format_remaining_hours(self):
        status = UserTimeoutStatus(
            status="timeout",
            remaining_seconds=7500,  # 2h 5m
            violation_count=6
        )
        assert status.format_remaining() == "2h 5m"
    
    def test_format_score_clean(self):
        status = UserTimeoutStatus(
            status="active",
            remaining_seconds=0,
            violation_count=0,
            warning_score=0.0
        )
        assert status.format_score() == "clean"
    
    def test_format_score_low(self):
        status = UserTimeoutStatus(
            status="warning",
            remaining_seconds=0,
            violation_count=1,
            warning_score=0.8
        )
        assert "low" in status.format_score()
    
    def test_format_score_critical(self):
        status = UserTimeoutStatus(
            status="timeout",
            remaining_seconds=120,
            violation_count=3,
            warning_score=3.5
        )
        assert "critical" in status.format_score()


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
    
    @pytest.fixture
    def enable_feature(self):
        """Enable the manipulation timeout feature flag for tests."""
        with patch('src_v2.moderation.timeout_manager.settings') as mock_settings:
            mock_settings.ENABLE_MANIPULATION_TIMEOUTS = True
            yield mock_settings
    
    @pytest.mark.asyncio
    async def test_fresh_user_is_active(self, manager, mock_cache, enable_feature):
        """A user with no timeout data should be active."""
        manager._cache = mock_cache
        mock_cache.get_json.return_value = None
        
        status = await manager.check_user_status("user123")
        
        assert status.status == "active"
        assert status.remaining_seconds == 0
        assert status.violation_count == 0
        assert status.escalation_level == 0
        assert status.warning_score == 0.0
    
    @pytest.mark.asyncio
    async def test_first_violation_returns_warning(self, manager, mock_cache, enable_feature):
        """First violation should return warning with score ~1.0."""
        manager._cache = mock_cache
        mock_cache.get_json.return_value = None
        
        status = await manager.record_violation("user123")
        
        assert status.status == "warning"
        assert status.violation_count == 1
        assert status.escalation_level == 0
        assert 0.9 <= status.warning_score <= 1.0  # Fresh violation = ~1.0

    @pytest.mark.asyncio
    async def test_second_rapid_violation_still_warning(self, manager, mock_cache, enable_feature):
        """Two rapid violations should still be warning (score ~2.0)."""
        manager._cache = mock_cache
        now = datetime.now(timezone.utc)
        
        # Simulate 1 existing violation from 1 minute ago
        existing_data = {
            "violation_timestamps": [(now - timedelta(minutes=1)).isoformat()],
            "timeout_until": None,
            "escalation_level": 0,
            "timeout_count": 0
        }
        mock_cache.get_json.return_value = existing_data
        
        status = await manager.record_violation("user123")
        
        assert status.status == "warning"
        assert status.violation_count == 2
        assert 1.9 <= status.warning_score <= 2.1  # Two recent = ~2.0

    @pytest.mark.asyncio
    async def test_third_rapid_violation_triggers_timeout(self, manager, mock_cache, enable_feature):
        """Three rapid violations should trigger timeout (score >= 3.0)."""
        manager._cache = mock_cache
        now = datetime.now(timezone.utc)
        
        # Simulate 2 existing violations from very recent times (just seconds ago)
        existing_data = {
            "violation_timestamps": [
                (now - timedelta(seconds=5)).isoformat(),
                (now - timedelta(seconds=2)).isoformat()
            ],
            "timeout_until": None,
            "escalation_level": 0,
            "timeout_count": 0
        }
        mock_cache.get_json.return_value = existing_data
        
        status = await manager.record_violation("user123")
        
        assert status.status == "timeout"
        assert status.violation_count == 3
        assert status.escalation_level == 1
        assert status.warning_score >= 3.0
        assert status.remaining_seconds == 120  # 2 minutes

    @pytest.mark.asyncio
    async def test_decayed_violations_dont_trigger_timeout(self, manager, mock_cache, enable_feature):
        """Violations that have decayed should not trigger timeout."""
        manager._cache = mock_cache
        now = datetime.now(timezone.utc)
        
        # 2 old violations (45 mins ago, decayed) + 1 new
        # Each old one contributes: 0.5^(45/30) ≈ 0.35
        # So total before new: ~0.7, after new: ~1.7
        existing_data = {
            "violation_timestamps": [
                (now - timedelta(minutes=50)).isoformat(),
                (now - timedelta(minutes=45)).isoformat()
            ],
            "timeout_until": None,
            "escalation_level": 0,
            "timeout_count": 0
        }
        mock_cache.get_json.return_value = existing_data
        
        status = await manager.record_violation("user123")
        
        assert status.status == "warning"
        assert status.warning_score < 3.0  # Not enough to trigger timeout

    @pytest.mark.asyncio
    async def test_escalation_increases_on_repeat_timeout(self, manager, mock_cache, enable_feature):
        """Repeated timeouts should increase escalation level."""
        manager._cache = mock_cache
        now = datetime.now(timezone.utc)
        
        # Already timed out once before, now fresh violations (just seconds ago)
        existing_data = {
            "violation_timestamps": [
                (now - timedelta(seconds=5)).isoformat(),
                (now - timedelta(seconds=2)).isoformat()
            ],
            "timeout_until": None,
            "escalation_level": 1,
            "timeout_count": 1
        }
        mock_cache.get_json.return_value = existing_data
        
        status = await manager.record_violation("user123")
        
        assert status.status == "timeout"
        assert status.escalation_level == 2
        assert status.remaining_seconds == 600  # 10 minutes

    @pytest.mark.asyncio
    async def test_escalation_caps_at_level_5(self, manager, mock_cache, enable_feature):
        """Escalation should cap at level 5 (24 hours)."""
        manager._cache = mock_cache
        now = datetime.now(timezone.utc)
        
        existing_data = {
            "violation_timestamps": [
                (now - timedelta(seconds=5)).isoformat(),
                (now - timedelta(seconds=2)).isoformat()
            ],
            "timeout_until": None,
            "escalation_level": 5,
            "timeout_count": 10  # Many timeouts
        }
        mock_cache.get_json.return_value = existing_data
        
        status = await manager.record_violation("user123")
        
        assert status.escalation_level == 5  # Still capped at 5
        assert status.remaining_seconds == 1440 * 60  # 24 hours

    @pytest.mark.asyncio
    async def test_timeout_expires_returns_active(self, manager, mock_cache, enable_feature):
        """User should be active after timeout expires."""
        manager._cache = mock_cache
        now = datetime.now(timezone.utc)
        
        # Timeout expired 5 minutes ago
        past_time = (now - timedelta(minutes=5)).isoformat()
        existing_data = {
            "violation_timestamps": [(now - timedelta(hours=1)).isoformat()],
            "timeout_until": past_time,
            "escalation_level": 1,
            "timeout_count": 1
        }
        mock_cache.get_json.return_value = existing_data
        
        status = await manager.check_user_status("user123")
        
        assert status.status == "active"
        assert status.remaining_seconds == 0

    @pytest.mark.asyncio
    async def test_user_in_timeout_returns_timeout(self, manager, mock_cache, enable_feature):
        """User should be in timeout if timeout_until is in the future."""
        manager._cache = mock_cache
        now = datetime.now(timezone.utc)
        
        # Timeout in 5 minutes
        future_time = (now + timedelta(minutes=5)).isoformat()
        existing_data = {
            "violation_timestamps": [now.isoformat()],
            "timeout_until": future_time,
            "escalation_level": 1,
            "timeout_count": 1
        }
        mock_cache.get_json.return_value = existing_data
        
        status = await manager.check_user_status("user123")
        
        assert status.status == "timeout"
        assert 290 <= status.remaining_seconds <= 300  # ~5 minutes

    @pytest.mark.asyncio
    async def test_clear_user_resets_status(self, manager, mock_cache, enable_feature):
        """Clearing a user should remove their timeout data."""
        manager._cache = mock_cache
        
        result = await manager.clear_user("user123")
        
        assert result is True
        mock_cache.delete.assert_called_once_with("manipulation:timeout:user123")

    @pytest.mark.asyncio
    async def test_redis_failure_fails_open(self, manager, mock_cache, enable_feature):
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
    async def test_check_status_returns_warning(self, manager, mock_cache, enable_feature):
        """User with violations below threshold should be in warning status."""
        manager._cache = mock_cache
        now = datetime.now(timezone.utc)
        
        existing_data = {
            "violation_timestamps": [
                (now - timedelta(minutes=10)).isoformat()
            ],
            "timeout_until": None,
            "escalation_level": 0,
            "timeout_count": 0
        }
        mock_cache.get_json.return_value = existing_data
        
        status = await manager.check_user_status("user123")
        
        assert status.status == "warning"
        assert status.violation_count == 1
        assert status.is_restricted() is False
        assert status.is_warned() is True
        assert 0 < status.warning_score < 1.0  # Decayed but still present

    @pytest.mark.asyncio
    async def test_old_violations_pruned(self, manager, mock_cache, enable_feature):
        """Violations older than MAX_VIOLATION_AGE_MINUTES should be pruned."""
        manager._cache = mock_cache
        now = datetime.now(timezone.utc)
        
        # Mix of old and new violations
        existing_data = {
            "violation_timestamps": [
                (now - timedelta(hours=3)).isoformat(),  # Old, should be pruned
                (now - timedelta(minutes=10)).isoformat()  # Recent
            ],
            "timeout_until": None,
            "escalation_level": 0,
            "timeout_count": 0
        }
        mock_cache.get_json.return_value = existing_data
        
        status = await manager.record_violation("user123")
        
        # Should only count the recent one + new one = 2
        assert status.violation_count == 2

    @pytest.mark.asyncio
    async def test_per_bot_isolation(self, manager, mock_cache, enable_feature):
        """Violations on one bot should not affect another when scope is per_bot."""
        manager._cache = mock_cache
        
        # Mock settings to per_bot
        with patch('src_v2.moderation.timeout_manager.settings.MANIPULATION_TIMEOUT_SCOPE', 'per_bot'):
            # Bot A has violations
            def side_effect(key):
                if "botA" in key:
                    return {
                        "violation_timestamps": [datetime.now(timezone.utc).isoformat()] * 3,
                        "timeout_until": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
                        "escalation_level": 2
                    }
                return None
            
            mock_cache.get_json.side_effect = side_effect
            
            # Check Bot A (should be timeout)
            status_a = await manager.check_user_status("user123", bot_name="botA")
            assert status_a.status == "timeout"
            
            # Check Bot B (should be active)
            status_b = await manager.check_user_status("user123", bot_name="botB")
            assert status_b.status == "active"

    @pytest.mark.asyncio
    async def test_global_scope(self, manager, mock_cache, enable_feature):
        """Violations should be shared when scope is global."""
        manager._cache = mock_cache
        
        # Mock settings to global
        with patch('src_v2.moderation.timeout_manager.settings.MANIPULATION_TIMEOUT_SCOPE', 'global'):
            # Global key has violations
            def side_effect(key):
                if "global" in key:
                    return {
                        "violation_timestamps": [datetime.now(timezone.utc).isoformat()] * 3,
                        "timeout_until": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
                        "escalation_level": 2
                    }
                return None
            
            mock_cache.get_json.side_effect = side_effect
            
            # Check Bot A (should be timeout)
            status_a = await manager.check_user_status("user123", bot_name="botA")
            assert status_a.status == "timeout"
            
            # Check Bot B (should be timeout)
            status_b = await manager.check_user_status("user123", bot_name="botB")
            assert status_b.status == "timeout"


class TestScoreCalculation:
    """Tests for score decay calculation."""
    
    def test_fresh_violation_has_full_weight(self):
        """A violation that just happened should contribute 1.0."""
        manager = TimeoutManager()
        now = datetime.now(timezone.utc)
        timestamps = [now.isoformat()]
        
        score = manager._calculate_warning_score(timestamps, now)
        
        assert 0.99 <= score <= 1.0
    
    def test_half_life_decay(self):
        """A violation at half-life should contribute 0.5."""
        manager = TimeoutManager()
        now = datetime.now(timezone.utc)
        half_life = manager.SCORE_DECAY_HALF_LIFE_MINUTES
        timestamps = [(now - timedelta(minutes=half_life)).isoformat()]
        
        score = manager._calculate_warning_score(timestamps, now)
        
        assert 0.49 <= score <= 0.51
    
    def test_double_half_life_decay(self):
        """A violation at 2x half-life should contribute 0.25."""
        manager = TimeoutManager()
        now = datetime.now(timezone.utc)
        half_life = manager.SCORE_DECAY_HALF_LIFE_MINUTES
        timestamps = [(now - timedelta(minutes=half_life * 2)).isoformat()]
        
        score = manager._calculate_warning_score(timestamps, now)
        
        assert 0.24 <= score <= 0.26
    
    def test_old_violations_fully_decayed(self):
        """Violations older than MAX_VIOLATION_AGE should contribute 0."""
        manager = TimeoutManager()
        now = datetime.now(timezone.utc)
        max_age = manager.MAX_VIOLATION_AGE_MINUTES
        timestamps = [(now - timedelta(minutes=max_age + 10)).isoformat()]
        
        score = manager._calculate_warning_score(timestamps, now)
        
        assert score == 0.0


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
    
    def test_warning_score_threshold(self):
        """Verify warning threshold is 3.0."""
        manager = TimeoutManager()
        assert manager.WARNING_SCORE_THRESHOLD == 3.0
    
    def test_half_life(self):
        """Verify half-life is 30 minutes."""
        manager = TimeoutManager()
        assert manager.SCORE_DECAY_HALF_LIFE_MINUTES == 30



