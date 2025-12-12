import asyncio
import random
import json
from datetime import datetime, timezone
from typing import Optional
from loguru import logger
import discord
from discord.ext import commands

from src_v2.config.settings import settings
from src_v2.core.database import db_manager
from src_v2.workers.task_queue import TaskQueue
from src_v2.agents.daily_life.models import SensorySnapshot, ChannelSnapshot, MessageSnapshot, ActionCommand
from src_v2.memory.manager import memory_manager
from src_v2.memory.models import MemorySourceType
from src_v2.intelligence.activity import server_monitor

class DailyLifeScheduler:
    """
    Periodically snapshots the bot's environment and sends it to the Remote Brain (Worker).
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.task_queue = TaskQueue()
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        
        # Config
        self.min_interval = 300  # 5 mins
        self.max_interval = 600  # 10 mins
        
        # Silence Tracking (Phase E34)
        self.last_activity_timestamp = datetime.now(timezone.utc)
        self.dream_threshold_seconds = 7200 # 2 hours
        
    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._task = self.bot.loop.create_task(self._loop(), name="daily_life_scheduler")
        logger.info("DailyLifeScheduler started.")
        
    async def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("DailyLifeScheduler stopped.")
        
    async def _loop(self):
        await self.bot.wait_until_ready()
        
        # Initial delay to let things settle
        await asyncio.sleep(30)
        
        while self.is_running:
            try:
                await self._snapshot_and_send()
            except Exception as e:
                logger.error(f"Error in DailyLifeScheduler: {e}")
            
            # Random interval
            delay = random.randint(self.min_interval, self.max_interval)
            logger.info(f"DailyLifeScheduler sleeping for {delay}s")
            await asyncio.sleep(delay)

    async def _create_snapshot(self, focus_channel_id: Optional[str] = None) -> Optional[SensorySnapshot]:
        """Capture environment snapshot."""
        logger.info("Taking sensory snapshot...")
        
        # 1. Identify channels to watch
        channels_to_poll = set()
        
        # If focus channel provided, prioritize it
        if focus_channel_id:
            channels_to_poll.add(focus_channel_id)
        
        # A. Configured Watchlist (Always check these)
        if settings.discord_check_watch_channels_list:
            channels_to_poll.update(settings.discord_check_watch_channels_list)
            
        # B. Activity-Driven Polling
        try:
            signals = await server_monitor.get_activity_signals(since_minutes=15)
            # Take top 10 active channels
            for signal in signals[:10]:
                channels_to_poll.add(signal.channel_id)
        except Exception as e:
            logger.warning(f"Failed to get activity signals: {e}")

        # C. Exploration (Only if not focused)
        if not focus_channel_id:
            try:
                all_candidates = []
                for guild in self.bot.guilds:
                    for channel in guild.text_channels:
                        perms = channel.permissions_for(guild.me)
                        if perms.read_messages and perms.send_messages:
                            if str(channel.id) not in channels_to_poll:
                                all_candidates.append(channel)
                
                if all_candidates:
                    exploration_channel = random.choice(all_candidates)
                    channels_to_poll.add(str(exploration_channel.id))
            except Exception as e:
                logger.warning(f"Failed to select exploration channel: {e}")
            
        channels_data = []
        
        # Helper to process a channel
        async def process_channel(channel):
            if not channel.permissions_for(channel.guild.me).read_messages:
                return
            if not channel.permissions_for(channel.guild.me).send_messages:
                return
            
            try:
                messages = []
                async for msg in channel.history(limit=20):
                    if not msg.content and not msg.attachments:
                        continue
                    messages.append(MessageSnapshot(
                        id=str(msg.id),
                        content=msg.content,
                        author_id=str(msg.author.id),
                        author_name=msg.author.display_name,
                        is_bot=msg.author.bot,
                        created_at=msg.created_at,
                        mentions_bot=self.bot.user in msg.mentions,
                        reference_id=str(msg.reference.message_id) if msg.reference else None,
                        channel_id=str(channel.id)
                    ))
                
                if messages:
                    channels_data.append(ChannelSnapshot(
                        channel_id=str(channel.id),
                        channel_name=channel.name,
                        messages=messages
                    ))
            except Exception as e:
                logger.warning(f"Failed to snapshot channel {channel.name}: {e}")

        # If no channels selected (no watchlist, no activity), fallback to ALL (legacy)
        if not channels_to_poll and not settings.discord_check_watch_channels_list and not focus_channel_id:
            for guild in self.bot.guilds:
                for channel in guild.text_channels:
                    await process_channel(channel)
        else:
            # Targeted polling
            for channel_id in channels_to_poll:
                try:
                    channel = self.bot.get_channel(int(channel_id))
                    if channel and isinstance(channel, discord.TextChannel):
                        await process_channel(channel)
                except Exception as e:
                    logger.warning(f"Failed to process channel {channel_id}: {e}")
        
        if not channels_data:
            return None

        bot_name = settings.DISCORD_BOT_NAME or "unknown_bot"
        bot_id = str(self.bot.user.id) if self.bot.user else None
        
        return SensorySnapshot(
            bot_name=bot_name,
            bot_id=bot_id,
            timestamp=datetime.now(),
            channels=channels_data,
            mentions=[]
        )

    async def trigger_immediate(self, message: discord.Message, reason: str):
        """
        Manually triggers a Daily Life cycle for high-signal events.
        Implements debouncing to prevent spam.
        """
        if not settings.ENABLE_AUTONOMOUS_ACTIVITY:
            return

        bot_name = self.bot.character_name
        redis = db_manager.redis_client
        if not redis:
            return

        # Debounce Check (unless direct mention)
        is_mention = self.bot.user in message.mentions
        
        if not is_mention:
            trigger_debounce_key = f"{settings.REDIS_KEY_PREFIX}bot:{bot_name}:trigger_debounce"
            if await redis.get(trigger_debounce_key):
                logger.debug(f"Trigger debounced for {bot_name} ({reason})")
                return
            
            # Set debounce for 60s
            await redis.setex(trigger_debounce_key, 60, "1")

        logger.info(f"⚡ Immediate Daily Life Trigger for {bot_name}: {reason}")
        
        # Reset silence timer since we have activity
        self.last_activity_timestamp = datetime.now(timezone.utc)

        # Create Snapshot (Focused)
        snapshot = await self._create_snapshot(focus_channel_id=str(message.channel.id))
        
        if snapshot:
            # Enqueue Task
            await self.task_queue.enqueue(
                "process_daily_life",
                snapshot_data=snapshot.model_dump(mode="json"),
                _queue_name=TaskQueue.QUEUE_COGNITION
            )

    async def _snapshot_and_send(self):
        """Capture environment and enqueue task (Periodic)."""
        snapshot = await self._create_snapshot()
        
        # --- Silence Tracking (Phase E34) ---
        bot_name = settings.DISCORD_BOT_NAME or "unknown_bot"
        now = datetime.now(timezone.utc)
        has_recent_activity = False
        
        if snapshot and snapshot.channels:
            for ch in snapshot.channels:
                for msg in ch.messages:
                    # Check if message is recent (last 15 mins)
                    if (now - msg.created_at).total_seconds() < 900:
                        has_recent_activity = True
                        break
                if has_recent_activity:
                    break
        
        if has_recent_activity:
            self.last_activity_timestamp = now
            logger.debug("Activity detected, resetting silence timer.")
        else:
            silence_duration = (now - self.last_activity_timestamp).total_seconds()
            logger.info(f"No recent activity. Silence duration: {silence_duration:.0f}s")
            
            if silence_duration > self.dream_threshold_seconds:
                logger.info("Silence threshold exceeded. Triggering Active Dream Cycle.")
                await self.task_queue.enqueue(
                    "run_active_dream_cycle",
                    character_name=bot_name
                )
                self.last_activity_timestamp = now # Reset to avoid spam

        if not snapshot:
            logger.info("No channels to snapshot.")
            return

        # 3. Enqueue
        await self.task_queue.enqueue(
            "process_daily_life", 
            snapshot_data=snapshot.model_dump(mode="json"),
            _queue_name=TaskQueue.QUEUE_COGNITION
        )
        logger.info(f"Sent snapshot with {len(snapshot.channels)} channels to Remote Brain.")


class ActionPoller:
    """
    Polls Redis for actions generated by the Remote Brain and executes them.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self.poll_interval = 5.0 # 5 seconds
        
    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._task = self.bot.loop.create_task(self._loop(), name="action_poller")
        logger.info("ActionPoller started.")
        
    async def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("ActionPoller stopped.")
        
    @property
    def redis(self):
        return db_manager.redis_client
        
    async def _loop(self):
        await self.bot.wait_until_ready()
        
        key = f"{settings.REDIS_KEY_PREFIX}pending_actions:{settings.DISCORD_BOT_NAME}"
        
        while self.is_running:
            try:
                if not self.redis:
                    await asyncio.sleep(5)
                    continue
                    
                # Pop one action at a time
                # lpop returns None if empty
                data = await self.redis.lpop(key) # type: ignore
                
                if data:
                    if isinstance(data, bytes):
                        data = data.decode('utf-8')
                    await self._execute_action(data)
                    # Be nice to Discord rate limits
                    await asyncio.sleep(1.0)
                    # If we found one, check again immediately
                    continue
                    
            except Exception as e:
                logger.error(f"Error in ActionPoller: {e}")
                
            await asyncio.sleep(self.poll_interval)

    async def _execute_action(self, data: str):
        try:
            cmd_dict = json.loads(data)
            cmd = ActionCommand(**cmd_dict)
            
            logger.info(f"Executing action: {cmd.action_type} in {cmd.channel_id}")
            
            channel = self.bot.get_channel(int(cmd.channel_id))
            if not channel:
                # Try fetching if not in cache
                try:
                    channel = await self.bot.fetch_channel(int(cmd.channel_id))
                except (discord.NotFound, discord.Forbidden):
                    logger.warning(f"Channel {cmd.channel_id} not found.")
                    return
            
            # Ensure channel supports sending messages
            if not isinstance(channel, (discord.TextChannel, discord.Thread, discord.VoiceChannel)):
                logger.warning(f"Channel {cmd.channel_id} is not a messageable channel type: {type(channel)}")
                return
            
            if cmd.action_type == "reply" or cmd.action_type == "post":
                if not cmd.content:
                    return
                    
                # Check if target message exists for reply
                ref = None
                if cmd.target_message_id:
                    try:
                        ref = discord.MessageReference(
                            message_id=int(cmd.target_message_id),
                            channel_id=channel.id
                        )
                    except ValueError:
                        pass
                
                kwargs = {"content": cmd.content}
                if ref:
                    kwargs["reference"] = ref
                
                sent_msg = await channel.send(**kwargs)
                
                # Save to memory (Postgres + Qdrant)
                if self.bot.user:
                    await memory_manager.add_message(
                        user_id=str(self.bot.user.id),
                        character_name=self.bot.character_name,
                        role="ai",
                        content=cmd.content,
                        user_name=self.bot.user.display_name,
                        channel_id=str(channel.id),
                        message_id=str(sent_msg.id),
                        source_type=MemorySourceType.INFERENCE
                    )
                    logger.info(f"Saved autonomous action to memory: {sent_msg.id}")
                
            elif cmd.action_type == "react":
                if not cmd.emoji or not cmd.target_message_id:
                    return
                    
                try:
                    msg = await channel.fetch_message(int(cmd.target_message_id))
                    await msg.add_reaction(cmd.emoji)
                except Exception as e:
                    logger.warning(f"Failed to react: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to execute action: {e}")
