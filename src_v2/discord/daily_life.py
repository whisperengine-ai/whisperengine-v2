import asyncio
import random
import json
from datetime import datetime
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

    async def _snapshot_and_send(self):
        """Capture environment and enqueue task."""
        logger.info("Taking sensory snapshot...")
        
        # 1. Identify channels to watch
        # If DISCORD_CHECK_WATCH_CHANNELS is set, only watch those.
        # Otherwise, watch all text channels where we have permissions.
        
        watch_list = settings.discord_check_watch_channels_list
        channels_data = []
        
        for guild in self.bot.guilds:
            for channel in guild.text_channels:
                # Filter by watch list if configured
                if watch_list and str(channel.id) not in watch_list:
                    continue

                if not channel.permissions_for(guild.me).read_messages:
                    continue
                if not channel.permissions_for(guild.me).send_messages:
                    continue
                    
                # Skip channels with "ignore" in topic or name?
                # For now, just grab them.
                
                try:
                    # Fetch last 20 messages
                    messages = []
                    async for msg in channel.history(limit=20):
                        # Skip empty content (images only) unless we handle vision later
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
        
        if not channels_data:
            logger.info("No channels to snapshot.")
            return

        # 2. Create Snapshot
        bot_name = settings.DISCORD_BOT_NAME or "unknown_bot"
        snapshot = SensorySnapshot(
            bot_name=bot_name,
            timestamp=datetime.now(),
            channels=channels_data,
            mentions=[] # We could explicitly fetch mentions here if we wanted
        )
        
        # 3. Enqueue
        # We use the 'process_daily_life' task name we defined in worker.py
        await self.task_queue.enqueue(
            "process_daily_life", 
            snapshot_data=snapshot.model_dump(mode="json")
        )
        logger.info(f"Sent snapshot with {len(channels_data)} channels to Remote Brain.")


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
