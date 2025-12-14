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
from src_v2.agents.daily_life.models import SensorySnapshot, ChannelSnapshot, MessageSnapshot, ActionCommand, MentionSnapshot
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
        if not settings.ENABLE_AUTONOMOUS_ACTIVITY:
            logger.info("DailyLifeScheduler disabled (ENABLE_AUTONOMOUS_ACTIVITY=false)")
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
                    # Pick up to 3 random channels for exploration (increased from 1)
                    # This ensures the bot discovers new channels faster
                    sample_size = min(3, len(all_candidates))
                    exploration_channels = random.sample(all_candidates, sample_size)
                    for ch in exploration_channels:
                        channels_to_poll.add(str(ch.id))
                        logger.debug(f"Exploration: Added channel {ch.name} ({ch.id}) to snapshot")
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
                        mentioned_users=[
                            MentionSnapshot(id=str(m.id), is_bot=m.bot, name=m.name) 
                            for m in msg.mentions
                            if m.id != self.bot.user.id  # Exclude self, tracked via mentions_bot
                        ],
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
            mentions=[],
            watch_channels=settings.discord_check_watch_channels_list
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
        # Safety check - flag might have changed at runtime
        if not settings.ENABLE_AUTONOMOUS_ACTIVITY:
            return
            
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
                logger.info("Silence threshold exceeded. Triggering Reverie Cycle (Active Idle).")
                await self.task_queue.enqueue(
                    "run_reverie_cycle",
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
                
                # --- PHASE E31.1: Full Message Processing ---
                # Save the INCOMING message first (what we're replying to)
                if cmd.action_type == "reply" and cmd.target_author_id and cmd.target_content:
                    try:
                        # ADR-014: Include author fields - the target is the actual author
                        # Determine if target is a bot (check cmd metadata or name patterns)
                        target_is_bot = cmd.target_is_bot if hasattr(cmd, 'target_is_bot') else False
                        
                        await memory_manager.add_message(
                            user_id=cmd.target_author_id,
                            character_name=self.bot.character_name,
                            role="human",  # From bot's perspective, incoming is "human"
                            content=cmd.target_content,
                            user_name=cmd.target_author_name or "Unknown",
                            channel_id=str(channel.id),
                            message_id=cmd.target_message_id,
                            source_type=MemorySourceType.BOT_OBSERVATION,  # Mark as bot-observed
                            # ADR-014: Author tracking
                            author_id=cmd.target_author_id,
                            author_is_bot=target_is_bot,
                            author_name=cmd.target_author_name
                        )
                        logger.debug(f"Saved incoming message {cmd.target_message_id} from {cmd.target_author_name}")
                        
                        # Enqueue background learning for the incoming message
                        from src_v2.discord.handlers.message_handler import enqueue_background_learning
                        await enqueue_background_learning(
                            user_id=cmd.target_author_id,
                            message_content=cmd.target_content,
                            character_name=self.bot.character_name,
                            context="autonomous"
                        )
                        
                        # --- FIRST-CLASS CITIZENSHIP: Update Trust for Bot-to-Bot ---
                        # This ensures autonomous interactions build relationships just like direct ones
                        from src_v2.evolution.trust import trust_manager
                        try:
                            milestone = await trust_manager.update_trust(
                                cmd.target_author_id, 
                                self.bot.character_name, 
                                1  # +1 for interaction
                            )
                            if milestone:
                                logger.info(f"🎉 Trust milestone with {cmd.target_author_name}: {milestone}")
                            else:
                                logger.debug(f"Updated trust with {cmd.target_author_name} (+1)")
                        except Exception as e:
                            logger.warning(f"Failed to update trust for bot-to-bot: {e}")
                    except Exception as e:
                        logger.warning(f"Failed to save incoming message: {e}")
                    
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
                    # Mention author if it's a reply to a user, but maybe not if it's a bot?
                    # For now, default to mention=True for visibility, or False if we want to be subtle.
                    # Let's default to True for replies to ensure they see it.
                    kwargs["mention_author"] = True
                
                sent_msg = await channel.send(**kwargs)
                
                # Save to memory (Postgres + Qdrant) with rich metadata for diary
                if self.bot.user:
                    # Build metadata for diary generation
                    action_metadata = {
                        "action_type": cmd.action_type,  # "reply" or "post"
                        "channel_name": channel.name if hasattr(channel, 'name') else "unknown",
                        "context": cmd.target_content or "",  # What we were replying to
                    }
                    
                    # --- FIX: Use proper user_id for channel context ---
                    # For channel posts, we use the channel_id as the "conversation partner"
                    # rather than bot.user.id which incorrectly implies "bot talking to self".
                    # For replies, use the target author (who we're replying to).
                    if cmd.action_type == "reply" and cmd.target_author_id:
                        context_user_id = cmd.target_author_id
                    else:
                        # Channel post: use channel ID as context (not bot ID)
                        context_user_id = f"channel_{channel.id}"
                    
                    # ADR-014: Bot is the author of this autonomous message
                    await memory_manager.add_message(
                        user_id=context_user_id,
                        character_name=self.bot.character_name,
                        role="ai",
                        content=cmd.content,
                        user_name=self.bot.user.display_name,
                        channel_id=str(channel.id),
                        message_id=str(sent_msg.id),
                        metadata=action_metadata,
                        source_type=MemorySourceType.INFERENCE,
                        # ADR-014: Author tracking - bot is author
                        author_id=settings.DISCORD_BOT_NAME,
                        author_is_bot=True,
                        author_name=self.bot.character_name,
                        reply_to_msg_id=cmd.target_message_id if cmd.action_type == "reply" else None
                    )
                    logger.info(f"Saved autonomous action to memory: {sent_msg.id} (context: {context_user_id})")
                
                # --- FIRST-CLASS CITIZENSHIP: Update trust for ALL context users ---
                # Even if we're just posting (not replying to anyone specific),
                # we're participating in the channel and that builds relationships
                if cmd.context_user_ids:
                    from src_v2.evolution.trust import trust_manager
                    updated_count = 0
                    for context_user_id in cmd.context_user_ids:
                        # Skip target author - already updated above in the reply handler
                        if context_user_id == cmd.target_author_id:
                            continue
                        try:
                            await trust_manager.update_trust(
                                context_user_id,
                                self.bot.character_name,
                                1  # +1 for participating in their presence
                            )
                            updated_count += 1
                        except Exception as e:
                            logger.debug(f"Failed to update context trust for {context_user_id}: {e}")
                    if updated_count > 0:
                        logger.debug(f"Updated trust for {updated_count} context users (excluding target)")
                
                # --- FIRST-CLASS LEARNING: Multi-party knowledge extraction ---
                # Channel interactions should be learned from, with proper attribution!
                # Each participant's messages get attributed to THEIR user_id
                if cmd.context_messages or cmd.target_content:
                    try:
                        from src_v2.discord.handlers.message_handler import enqueue_post_conversation_tasks
                        from src_v2.workers.task_queue import task_queue
                        import uuid
                        
                        # Group messages by author for proper attribution
                        # Each author gets their own learning session
                        messages_by_author = {}
                        
                        # Add context messages (from other participants)
                        if cmd.context_messages:
                            for ctx_msg in cmd.context_messages:
                                author_id = ctx_msg.get("user_id")
                                if author_id:
                                    if author_id not in messages_by_author:
                                        messages_by_author[author_id] = {
                                            "user_name": ctx_msg.get("user_name", "Unknown"),
                                            "messages": [],
                                            "is_bot": ctx_msg.get("is_bot", False)
                                        }
                                    messages_by_author[author_id]["messages"].append({
                                        "role": "human",
                                        "content": ctx_msg.get("content", "")
                                    })
                        
                        # Add the target message (who we're replying to)
                        if cmd.target_author_id and cmd.target_content:
                            if cmd.target_author_id not in messages_by_author:
                                messages_by_author[cmd.target_author_id] = {
                                    "user_name": cmd.target_author_name or "Unknown",
                                    "messages": [],
                                    "is_bot": False
                                }
                            messages_by_author[cmd.target_author_id]["messages"].append({
                                "role": "human",
                                "content": cmd.target_content
                            })
                        
                        # Enqueue learning for each participant (humans only)
                        for author_id, author_data in messages_by_author.items():
                            if not author_data["messages"]:
                                continue
                            # Skip bots - don't extract "facts" from bot messages
                            if author_data.get("is_bot", False):
                                continue
                                
                            # Add our response to their "conversation"
                            conversation = author_data["messages"] + [{
                                "role": "ai",
                                "content": cmd.content
                            }]
                            
                            session_id = f"daily_life_{uuid.uuid4().hex[:8]}"
                            
                            await enqueue_post_conversation_tasks(
                                user_id=author_id,
                                character_name=self.bot.character_name,
                                session_id=session_id,
                                messages=conversation,
                                user_name=author_data["user_name"],
                                trigger="daily_life_multiparty"
                            )
                            logger.debug(f"Enqueued multi-party learning for {author_data['user_name']} ({author_id})")
                        
                    except Exception as e:
                        logger.warning(f"Failed to enqueue multi-party learning: {e}")
                
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
