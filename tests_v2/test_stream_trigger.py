import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from src_v2.discord.daily_life import DailyLifeScheduler
from src_v2.config.settings import settings

@pytest.mark.asyncio
async def test_trigger_immediate_debounce():
    """
    Verify that trigger_immediate respects Redis debounce.
    """
    # Mock Bot
    mock_bot = MagicMock()
    mock_bot.character_name = "test_bot"
    mock_bot.user.id = 12345
    
    # Mock Message
    mock_message = MagicMock()
    mock_message.channel.id = "999"
    mock_message.mentions = [] # No mention
    
    # Mock Redis
    mock_redis = AsyncMock()
    
    # Mock TaskQueue
    mock_task_queue = AsyncMock()
    
    # Initialize Scheduler
    scheduler = DailyLifeScheduler(mock_bot)
    scheduler.task_queue = mock_task_queue
    
    # Patch settings
    with patch.object(settings, "ENABLE_AUTONOMOUS_ACTIVITY", True):
        # Patch db_manager.redis_client
        with patch("src_v2.core.database.db_manager.redis_client", mock_redis):
            # Patch _create_snapshot to return a dummy snapshot
            with patch.object(scheduler, "_create_snapshot", new_callable=AsyncMock) as mock_snapshot:
                mock_snapshot.return_value = MagicMock()
                mock_snapshot.return_value.model_dump.return_value = {"test": "data"}
                
                # Scenario 1: First Trigger (Should pass)
                mock_redis.get.return_value = None # No debounce key
                
                await scheduler.trigger_immediate(mock_message, "test_reason")
                
                # Verify Redis check
                mock_redis.get.assert_called_with(f"{settings.REDIS_KEY_PREFIX}bot:test_bot:trigger_debounce")
                # Verify Redis set
                mock_redis.setex.assert_called_with(f"{settings.REDIS_KEY_PREFIX}bot:test_bot:trigger_debounce", 60, "1")
                # Verify Snapshot created
                mock_snapshot.assert_called_with(focus_channel_id="999")
                # Verify Task Enqueued
                mock_task_queue.enqueue.assert_called_once()
                
                # Reset mocks
                mock_redis.reset_mock()
                mock_task_queue.reset_mock()
                mock_snapshot.reset_mock()
                
                # Scenario 2: Debounced Trigger (Should fail)
                mock_redis.get.return_value = "1" # Key exists
                
                await scheduler.trigger_immediate(mock_message, "test_reason")
                
                # Verify Redis check
                mock_redis.get.assert_called()
                # Verify NO Redis set
                mock_redis.setex.assert_not_called()
                # Verify NO Snapshot
                mock_snapshot.assert_not_called()
                # Verify NO Task
                mock_task_queue.enqueue.assert_not_called()

@pytest.mark.asyncio
async def test_trigger_immediate_mention_bypass():
    """
    Verify that mentions bypass debounce.
    """
    # Mock Bot
    mock_bot = MagicMock()
    mock_bot.character_name = "test_bot"
    mock_bot.user.id = 12345
    
    # Mock Message WITH Mention
    mock_message = MagicMock()
    mock_message.channel.id = "999"
    mock_message.mentions = [mock_bot.user]
    
    # Mock Redis
    mock_redis = AsyncMock()
    mock_task_queue = AsyncMock()
    
    scheduler = DailyLifeScheduler(mock_bot)
    scheduler.task_queue = mock_task_queue
    
    with patch.object(settings, "ENABLE_AUTONOMOUS_ACTIVITY", True):
        with patch("src_v2.core.database.db_manager.redis_client", mock_redis):
            with patch.object(scheduler, "_create_snapshot", new_callable=AsyncMock) as mock_snapshot:
                mock_snapshot.return_value = MagicMock()
                mock_snapshot.return_value.model_dump.return_value = {"test": "data"}
                
                # Even if debounce key exists
                mock_redis.get.return_value = "1" 
                
                await scheduler.trigger_immediate(mock_message, "mention")
                
                # Verify Task Enqueued (Bypassed debounce)
                mock_task_queue.enqueue.assert_called_once()
