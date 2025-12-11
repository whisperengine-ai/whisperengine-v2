import asyncio
import random
from typing import Optional, List
from loguru import logger
import discord
from discord.ext import commands

from src_v2.config.settings import settings
from src_v2.intelligence.activity import server_monitor
from src_v2.agents.posting_agent import PostingAgent
from src_v2.agents.conversation_agent import conversation_agent
from src_v2.broadcast.cross_bot import cross_bot_manager

class ActivityOrchestrator:
    """
    Coordinates autonomous server activity based on engagement levels.
    Scales bot activity inversely to human activity.
    
    Activity probabilities are kept LOW to avoid spam:
    - Dead quiet: 15% conversation, 10% post (prioritize conversations)
    - Quiet: 5% post only
    - Active: No autonomous posts (let humans lead)
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.is_running = False
        self.check_interval_minutes = settings.ACTIVITY_CHECK_INTERVAL_MINUTES  # Default 30 min
        self.posting_agent = PostingAgent()
        self._task: Optional[asyncio.Task] = None

    def start(self) -> None:
        """Start the orchestration loop."""
        if self.is_running:
            return
        self.is_running = True
        self._task = self.bot.loop.create_task(self._loop(), name="activity_orchestrator")
        logger.info("ActivityOrchestrator started.")

    async def stop(self) -> None:
        """Stop the orchestration loop."""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("ActivityOrchestrator stopped.")

    async def _loop(self) -> None:
        """Main orchestration loop."""
        await self.bot.wait_until_ready()
        
        # Initial delay to let things settle
        await asyncio.sleep(60)
        
        while self.is_running:
            try:
                await self.check_and_act()
            except Exception as e:
                logger.error(f"Error in ActivityOrchestrator loop: {e}")
            
            # Wait for next interval (with some jitter)
            jitter = random.randint(-60, 60)
            wait_time = (self.check_interval_minutes * 60) + jitter
            await asyncio.sleep(wait_time)

    async def check_and_act(self) -> None:
        """Check activity levels and trigger actions if needed."""
        # Master switch must be enabled for any autonomous activity
        if not settings.ENABLE_AUTONOMOUS_ACTIVITY:
            return
        
        # Skip if neither posting nor conversations are enabled
        if not settings.ENABLE_AUTONOMOUS_POSTING and not settings.ENABLE_BOT_CONVERSATIONS:
            return

        # We iterate over guilds the bot is in
        for guild in self.bot.guilds:
            await self.manage_guild_activity(guild)

    async def manage_guild_activity(self, guild: discord.Guild) -> None:
        """Decide on actions for a specific guild.
        
        Probability design:
        - Dead Quiet: 15% conversation, 10% post (conversations preferred)
        - Quiet: 5% post only
        - Active: No autonomous posting (let humans lead)
        
        These low probabilities prevent spam when multiple bots are in a server.
        With 10 bots at 15% each, ~1-2 will act per check cycle.
        """
        # 1. Get Activity Level (msgs/min over last 30 mins)
        rate = await server_monitor.get_activity_level(str(guild.id))
        
        # 2. Determine State
        # Dead Quiet: < 0.1 msg/min (approx < 3 msgs in 30 mins)
        # Quiet: 0.1 - 0.5 msg/min
        # Active: > 0.5 msg/min
        
        is_dead_quiet = rate < 0.1
        is_quiet = rate < 0.5
        
        logger.info(
            f"[Orchestrator] Guild={guild.name} rate={rate:.3f} msg/min "
            f"dead_quiet={is_dead_quiet} quiet={is_quiet} conversations={settings.ENABLE_BOT_CONVERSATIONS}"
        )

        # 3. Decide Action
        # Use low probabilities to prevent spam with multiple bots
        if is_dead_quiet:
            roll = random.random()
            logger.debug(f"[Orchestrator] Dead quiet roll={roll:.2f}")
            
            # Prioritize bot-to-bot conversations over solo posts
            if roll < settings.BOT_CONVERSATION_CHANCE and settings.ENABLE_BOT_CONVERSATIONS:
                # Chance to start a bot-to-bot conversation
                # Add random delay (0-120 sec) to stagger bots
                delay = random.uniform(0, 120)
                logger.debug(f"[Orchestrator] Conversation delay: {delay:.1f}s")
                await asyncio.sleep(delay)
                await self.trigger_conversation(guild, activity_rate=rate, roll_value=roll)
            elif roll < 0.25 and settings.ENABLE_AUTONOMOUS_POSTING:
                # 10% chance to post (if conversation wasn't triggered)
                # Add delay to stagger posts too
                delay = random.uniform(0, 60)
                await asyncio.sleep(delay)
                await self.trigger_post(guild)
        elif is_quiet:
            # Very low chance to post when somewhat active
            if random.random() < 0.05 and settings.ENABLE_AUTONOMOUS_POSTING:
                await self.trigger_post(guild)
        else:
            # Active - do nothing, let ReactionAgent handle reactions
            pass

    async def trigger_post(self, guild: discord.Guild) -> None:
        """Trigger the PostingAgent to generate a post."""
        character_name = settings.DISCORD_BOT_NAME
        if not character_name:
            return

        # Find a suitable channel to post in FIRST (before acquiring lock)
        # Requires explicit channel config - no auto-detect to prevent posting in random channels
        target_channel = None
        posting_channel_id = settings.AUTONOMOUS_POSTING_CHANNEL_ID or settings.BOT_CONVERSATION_CHANNEL_ID
        
        if posting_channel_id:
            try:
                target_channel = self.bot.get_channel(int(posting_channel_id))
                if not target_channel:
                    logger.warning(f"Configured posting channel {posting_channel_id} not found")
            except ValueError:
                logger.error(f"Invalid posting channel ID: {posting_channel_id}")
        
        if not target_channel:
            logger.debug(f"No posting channel configured for {character_name} - skipping autonomous post")
            return

        # ATOMIC: Try to acquire the post slot using Redis SET NX EX
        # This combines check + record into one atomic operation with TTL
        # If another bot already has the slot, we skip immediately
        cooldown_seconds = settings.AUTONOMOUS_POST_COOLDOWN_MINUTES * 60
        acquired = await server_monitor.try_acquire_post_slot(
            str(guild.id),
            character_name,
            cooldown_seconds
        )
        
        if not acquired:
            logger.info(
                f"[Orchestrator] Skipping autonomous post for {character_name} - "
                f"another bot has the slot in {guild.name}"
            )
            return

        logger.info(f"Triggering autonomous post for {character_name} in {guild.name} (#{target_channel.name})")
        
        # Run generation (this puts it in the broadcast queue)
        # The cooldown is already set via try_acquire_post_slot with TTL
        success = await self.posting_agent.generate_and_schedule_post(
            character_name, 
            target_channel_id=str(target_channel.id)
        )
        
        if success:
            logger.info(f"Successfully scheduled autonomous post for {character_name}")
        else:
            # Clear the cooldown since we didn't actually post
            # This allows another bot to try, or this bot to retry next cycle
            await server_monitor.clear_post_cooldown(str(guild.id))
            logger.warning(f"Post generation failed for {character_name}, cleared cooldown for retry")

    async def trigger_conversation(
        self, 
        guild: discord.Guild, 
        activity_rate: float = 0.0, 
        roll_value: float = 0.0
    ) -> None:
        """Trigger a bot-to-bot conversation in a quiet guild."""
        character_name = settings.DISCORD_BOT_NAME
        if not character_name:
            return

        # Find target channel - requires explicit config, no auto-detect
        target_channel = None
        if settings.BOT_CONVERSATION_CHANNEL_ID:
            try:
                target_channel = self.bot.get_channel(int(settings.BOT_CONVERSATION_CHANNEL_ID))
                if not target_channel:
                    logger.warning(f"Configured BOT_CONVERSATION_CHANNEL_ID {settings.BOT_CONVERSATION_CHANNEL_ID} not found")
            except ValueError:
                logger.error(f"Invalid BOT_CONVERSATION_CHANNEL_ID: {settings.BOT_CONVERSATION_CHANNEL_ID}")
        
        if not target_channel:
            logger.debug(f"No conversation channel configured for {character_name} - skipping bot conversation")
            return

        # ATOMIC: Acquire distributed lock for conversation initiation
        # This prevents multiple bots from trying to start conversations at the same time
        if not await server_monitor.acquire_conversation_lock(str(guild.id), character_name):
            logger.info(f"[Orchestrator] Another bot is initiating conversation in {guild.name} - skipping")
            return
        
        try:
            # Check cooldown for this channel (use cross_bot_manager with async Redis check)
            if await cross_bot_manager.is_on_cooldown_async(str(target_channel.id)):
                logger.info(f"Channel {target_channel.name} is on cooldown for cross-bot chat")
                return
            
            # Check if there's already an active conversation in this channel (Redis-backed)
            if await cross_bot_manager.has_active_conversation_async(str(target_channel.id)):
                logger.info(f"Channel {target_channel.name} already has active bot conversation - skipping")
                return

            # Get list of known bots in this guild
            available_bots = self._get_available_bots_in_guild(guild)
            if len(available_bots) < 2:
                logger.debug(f"Not enough bots in {guild.name} for conversation (found {len(available_bots)})")
                return

            # Select a conversation partner and topic WITH DECISION TRACE
            pair, trace = await conversation_agent.select_conversation_pair_with_trace(
                available_bots=available_bots,
                initiator_name=character_name,
                guild_name=guild.name,
                channel_name=target_channel.name,
                activity_rate=activity_rate,
                roll_value=roll_value
            )
            
            # Log the decision trace
            trace.log()
            
            if not pair:
                logger.debug(f"No suitable conversation pair found for {character_name}")
                return

            target_bot, topic = pair

            # Generate the opening message
            opener = await conversation_agent.generate_opener(character_name, target_bot, topic)
            if not opener:
                logger.warning(f"Failed to generate conversation opener for {character_name} -> {target_bot}")
                return

            # Send the opener to the channel
            try:
                sent_message = await target_channel.send(opener.content)
                
                # Record this as the start of a conversation chain
                await cross_bot_manager.record_response(
                    str(target_channel.id), 
                    str(sent_message.id)
                )
                
                logger.info(
                    f"Started bot conversation: {character_name} -> {target_bot} "
                    f"in {guild.name} (#{target_channel.name})"
                )
            except discord.Forbidden:
                logger.warning(f"Permission denied to send message in {target_channel.name}")
            except discord.HTTPException as e:
                logger.error(f"Failed to send conversation opener: {e}")
        finally:
            # Always release the conversation lock when done
            await server_monitor.release_conversation_lock(str(guild.id), character_name)

    def _get_available_bots_in_guild(self, guild: discord.Guild) -> List[str]:
        """Get list of known bots that are members of this guild."""
        available = []
        known_bots = cross_bot_manager.known_bots
        
        for bot_name, discord_id in known_bots.items():
            member = guild.get_member(discord_id)
            if member and member.status != discord.Status.offline:
                available.append(bot_name)
        
        return available

    def _get_target_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        """Find the best channel to post in."""
        # 1. Try System Channel (often "general" or "welcome")
        if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
            return guild.system_channel
            
        # 2. Try channels with common names
        common_names = ["general", "chat", "lounge", "main", "discussion"]
        for name in common_names:
            for channel in guild.text_channels:
                if name in channel.name.lower() and channel.permissions_for(guild.me).send_messages:
                    return channel
                    
        # 3. Fallback: First text channel we can speak in
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                return channel
                
        return None
