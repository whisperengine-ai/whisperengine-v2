import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src_v2.workers.task_queue import task_queue, TaskQueue
from src_v2.tools.insight_tools import TriggerProactiveActionTool
from src_v2.broadcast.manager import BroadcastManager
from src_v2.universe.bus import UniverseEvent, EventType
from src_v2.config.settings import settings

class TestQueueRouting:
    """Test routing logic for new queues."""

    @pytest.mark.asyncio
    async def test_gossip_routing(self):
        """Verify gossip is routed to SOCIAL queue."""
        with patch.object(task_queue, 'enqueue', new_callable=AsyncMock) as mock_enqueue:
            # Create real event
            event = UniverseEvent(
                event_type=EventType.USER_UPDATE,
                user_id="u1",
                source_bot="b1",
                summary="User updated something",
                topic="general"
            )
    
            await task_queue.enqueue_gossip(event)
    
            # Check queue name
            mock_enqueue.assert_called_once()
            
            # Check arguments
            args, kwargs = mock_enqueue.call_args
            assert args[0] == "run_gossip_dispatch"
            assert kwargs['_queue_name'] == TaskQueue.QUEUE_SOCIAL
            assert kwargs['event_data'] == event.to_dict()

class TestInterAgentTrigger:
    """Test Insight Agent triggering Action Worker."""

    @pytest.mark.asyncio
    async def test_trigger_proactive_action_tool(self):
        """Verify tool enqueues to ACTION queue."""
        tool = TriggerProactiveActionTool(bot_name="elena")
        valid_user_id = "123456789012345678"
    
        with patch('src_v2.workers.task_queue.task_queue.enqueue', new_callable=AsyncMock) as mock_enqueue:
            mock_enqueue.return_value = "job_123"
    
            result = await tool._arun(user_id=valid_user_id, reason="test reason")
    
            assert "job_123" in result
    
            # Check queue name
            mock_enqueue.assert_called_once()
            
            # Check arguments
            args, kwargs = mock_enqueue.call_args
            assert args[0] == "run_proactive_message"
            assert kwargs['_queue_name'] == TaskQueue.QUEUE_ACTION
            assert kwargs['user_id'] == valid_user_id
            assert kwargs['character_name'] == "elena"

class TestBroadcastManager:
    """Test BroadcastManager updates for background DMs."""

    @pytest.mark.asyncio
    async def test_queue_broadcast_dm(self):
        """Verify queuing a DM broadcast."""
        manager = BroadcastManager()
        valid_user_id = "123456789012345678"
        
        # Mock redis
        # We need to mock db_manager.redis_client because queue_broadcast uses it directly
        with patch('src_v2.broadcast.manager.db_manager') as mock_db:
            mock_db.redis_client = AsyncMock()
            
            # We also need to patch settings for _redis_key
            with patch('src_v2.broadcast.manager.settings') as mock_settings:
                mock_settings.REDIS_KEY_PREFIX = "whisper:"
                mock_settings.DISCORD_BOT_NAME = "elena"
            
                await manager.queue_broadcast(
                    content="Hello",
                    post_type=MagicMock(value="diary"),
                    character_name="elena",
                    target_user_id=valid_user_id
                )
                
                # Verify pushed to redis list
                mock_db.redis_client.rpush.assert_called_once()
                call_args = mock_db.redis_client.rpush.call_args
                assert "broadcast:queue:elena" in call_args[0][0]
                
                # Check payload
                import json
                payload = json.loads(call_args[0][1])
                assert payload['target_user_id'] == valid_user_id
                assert payload['content'] == "Hello"

    @pytest.mark.asyncio
    async def test_process_queued_broadcasts_dm(self):
        """Verify processing a DM broadcast."""
        manager = BroadcastManager()
        manager._bot = AsyncMock()
        valid_user_id = "123456789012345678"
        
        # Mock user fetch
        mock_user = AsyncMock()
        manager._bot.fetch_user.return_value = mock_user
        
        # Mock redis pop returning one item then None
        import json
        item = json.dumps({
            "id": "test-id",
            "content": "Hello",
            "post_type": "diary",
            "character_name": "elena",
            "target_user_id": valid_user_id
        })
        
        with patch('src_v2.broadcast.manager.db_manager') as mock_db:
            mock_db.redis_client = AsyncMock()
            mock_db.redis_client.lpop.side_effect = [item, None]
            
            # Ensure settings.DISCORD_BOT_NAME matches and REDIS_KEY_PREFIX is set
            with patch('src_v2.broadcast.manager.settings') as mock_settings:
                mock_settings.DISCORD_BOT_NAME = "elena"
                mock_settings.REDIS_KEY_PREFIX = "whisper:"
                
                await manager.process_queued_broadcasts()
            
            # Verify user fetched and message sent
            manager._bot.fetch_user.assert_called_with(int(valid_user_id))
            mock_user.send.assert_called_once()
            assert mock_user.send.call_args[0][0] == "Hello"
