import asyncio
import json
import aiohttp
from typing import Optional, List, Dict, Any
from loguru import logger
from redis.asyncio import Redis

from src_v2.config.settings import settings
from src_v2.core.database import db_manager
from src_v2.workers.task_queue import TaskQueue
from src_v2.agents.daily_life.models import SensorySnapshot, ChannelSnapshot, MessageSnapshot, MentionSnapshot

class StreamConsumer:
    """
    Consumes events from the Redis Stream (The Nervous System) and triggers
    cognitive processes (The Brain) when appropriate.
    
    This implements the "Inbox" pattern:
    1. Read event (cheap)
    2. Decide if interesting (cheap)
    3. Fetch context (expensive)
    4. Trigger brain (expensive)
    """
    
    def __init__(self):
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self.redis: Optional[Redis] = None
        self.last_id = "$"  # Start reading from new messages
        self.group_name = "whisper_brain"
        self.consumer_name = f"worker_{settings.DISCORD_BOT_NAME}"
        
        # Inbox Filters
        self.watch_channels = set(settings.discord_check_watch_channels_list)
        
    async def start(self):
        """Start the consumer loop."""
        if self.is_running:
            return
            
        self.is_running = True
        self.redis = db_manager.redis_client
        
        if not self.redis:
            logger.warning("Redis not available, StreamConsumer cannot start.")
            return

        # Create consumer group if not exists
        try:
            await self.redis.xgroup_create(
                settings.REDIS_STREAM_KEY, 
                self.group_name, 
                id="$", 
                mkstream=True
            )
        except Exception as e:
            if "BUSYGROUP" not in str(e):
                logger.error(f"Failed to create Redis Stream group: {e}")

        self._task = asyncio.create_task(self._consume_loop(), name="stream_consumer")
        logger.info(f"StreamConsumer started (Group: {self.group_name})")

    async def stop(self):
        """Stop the consumer loop."""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("StreamConsumer stopped")

    async def _consume_loop(self):
        """Main loop for reading from Redis Stream."""
        while self.is_running:
            try:
                # Block for 5 seconds waiting for new messages
                streams = await self.redis.xreadgroup(
                    groupname=self.group_name,
                    consumername=self.consumer_name,
                    streams={settings.REDIS_STREAM_KEY: ">"},
                    count=10,
                    block=5000
                )
                
                if not streams:
                    continue
                    
                for stream_name, messages in streams:
                    for message_id, data in messages:
                        try:
                            await self._process_event(message_id, data)
                            # Acknowledge processing
                            await self.redis.xack(
                                settings.REDIS_STREAM_KEY, 
                                self.group_name, 
                                message_id
                            )
                        except Exception as e:
                            logger.error(f"Error processing event {message_id}: {e}")
                            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in StreamConsumer loop: {e}")
                await asyncio.sleep(5)  # Backoff

    async def _process_event(self, message_id: str, data: Dict[Any, Any]):
        """
        Decide if an event is worth waking up for.
        """
        # Decode bytes to strings if necessary (Redis client might have decode_responses=True)
        event = {}
        for k, v in data.items():
            key = k.decode('utf-8') if isinstance(k, bytes) else k
            value = v.decode('utf-8') if isinstance(v, bytes) else v
            event[key] = value
        
        event_type = event.get("type")
        
        if event_type == "message":
            await self._handle_message_event(event)

    async def _handle_message_event(self, event: Dict[str, Any]):
        """
        Handle a message event.
        """
        channel_id = event.get("channel_id")
        author_id = event.get("author_id")
        is_bot = event.get("is_bot") == "1"
        mentions = json.loads(event.get("mentions", "[]"))
        
        # 1. Ignore own messages (already handled in capture, but safety first)
        # We don't have self ID here easily, but is_bot=1 is a clue.
        # Actually, we might want to listen to other bots.
        
        should_engage = False
        trigger_reason = ""
        
        # A. Direct Mention (High Priority)
        # We need to know our own ID. 
        # For now, let's assume if we are mentioned, it's important.
        # But wait, the capture logic puts ALL mentions in the list.
        # We need to check if *we* are mentioned.
        # Since we don't have our ID handy in the worker config easily (unless we fetch it),
        # we can rely on the fact that `on_message` usually handles mentions directly.
        #
        # WAIT. `on_message` handles mentions via the Real-Time Path.
        # The Stream is for *Autonomous* behavior (things we *didn't* reply to immediately).
        #
        # So if `on_message` already replied, we shouldn't reply again.
        # But `on_message` only replies to DMs and Mentions.
        #
        # So the Stream is primarily for:
        # 1. Lurking (Channel activity)
        # 2. Cross-bot interactions (if not handled by on_message)
        
        # B. Watchlist Channels
        if channel_id in self.watch_channels:
            should_engage = True
            trigger_reason = "watchlist_activity"
            
        # C. Reply to us (without ping)
        # We'd need to check if the reference is to us.
        
        if should_engage:
            # --- Debouncing (Phase 2) ---
            # Check if we are in a cooldown period
            last_action_key = f"{settings.REDIS_KEY_PREFIX}bot:{settings.DISCORD_BOT_NAME}:last_autonomous_action"
            last_action_ts = await self.redis.get(last_action_key)
            
            if last_action_ts:
                import time
                now = time.time()
                if now - float(last_action_ts) < 60:  # 60s cooldown
                    logger.info(f"StreamConsumer: Cooling down (last action {int(now - float(last_action_ts))}s ago). Ignoring {trigger_reason}.")
                    return

            logger.info(f"StreamConsumer: Engaging for {trigger_reason} in {channel_id}")
            
            # Fetch Context from Discord
            snapshot = await self._fetch_context(channel_id)
            
            if snapshot:
                # Enqueue Daily Life Job
                # We use the existing process_daily_life task
                from src_v2.workers.task_queue import TaskQueue
                await TaskQueue().enqueue(
                    "process_daily_life",
                    snapshot_data=snapshot.model_dump(),
                    _queue_name=TaskQueue.QUEUE_COGNITION
                )

    async def _fetch_context(self, channel_id: str) -> Optional[SensorySnapshot]:
        """
        Fetch recent messages from Discord API and build a SensorySnapshot.
        """
        if not settings.DISCORD_TOKEN:
            logger.error("DISCORD_TOKEN not set, cannot fetch context.")
            return None
            
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=10"
        headers = {
            "Authorization": f"Bot {settings.DISCORD_TOKEN.get_secret_value()}",
            "Content-Type": "application/json"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"Failed to fetch messages: {response.status} {await response.text()}")
                        return None
                        
                    messages_data = await response.json()
                    
                    # Convert to MessageSnapshot objects
                    # Discord API returns newest first, we want oldest first for context
                    messages_data.reverse()
                    
                    snapshots = []
                    for msg in messages_data:
                        snapshots.append(MessageSnapshot(
                            id=msg["id"],
                            author_id=msg["author"]["id"],
                            author_name=msg["author"]["username"],
                            content=msg["content"],
                            timestamp=datetime.fromisoformat(msg["timestamp"]),
                            channel_id=channel_id,
                            mentions=[MentionSnapshot(id=u["id"], name=u["username"]) for u in msg.get("mentions", [])],
                            is_bot=msg["author"].get("bot", False)
                        ))
                        
                    # Build Channel Snapshot
                    # We need guild_id, but message object usually doesn't have it in the list endpoint?
                    # Actually it might not. We can get it from the first message if available, or make a separate call.
                    # For now, let's assume we can get it or it's optional.
                    # Wait, SensorySnapshot needs a list of ChannelSnapshots.
                    
                    channel_snapshot = ChannelSnapshot(
                        id=channel_id,
                        name="unknown", # We'd need another call to get channel details
                        guild_id="unknown",
                        messages=snapshots
                    )
                    
                    return SensorySnapshot(
                        bot_name=settings.DISCORD_BOT_NAME,
                        channels=[channel_snapshot]
                    )
                    
        except Exception as e:
            logger.error(f"Error fetching context from Discord: {e}")
            return None

from datetime import datetime
