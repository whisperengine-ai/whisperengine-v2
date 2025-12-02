import asyncio
import random
from typing import Optional
from loguru import logger
import discord
from discord.ext import commands

from src_v2.config.settings import settings
from src_v2.intelligence.activity import server_monitor
from src_v2.agents.posting_agent import PostingAgent

class ActivityOrchestrator:
    """
    Coordinates autonomous server activity based on engagement levels.
    Scales bot activity inversely to human activity.
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.is_running = False
        self.check_interval_minutes = 15  # Check every 15 minutes
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
        if not settings.ENABLE_AUTONOMOUS_POSTING:
            return

        # We iterate over guilds the bot is in
        for guild in self.bot.guilds:
            await self.manage_guild_activity(guild)

    async def manage_guild_activity(self, guild: discord.Guild) -> None:
        """Decide on actions for a specific guild."""
        # 1. Get Activity Level (msgs/min over last 30 mins)
        rate = await server_monitor.get_activity_level(str(guild.id))
        
        # 2. Determine State
        # Dead Quiet: < 0.1 msg/min (approx < 3 msgs in 30 mins)
        # Quiet: 0.1 - 0.5 msg/min
        # Active: > 0.5 msg/min
        
        is_dead_quiet = rate < 0.1
        is_quiet = rate < 0.5
        
        logger.debug(f"Guild {guild.name} activity rate: {rate:.3f} msg/min. DeadQuiet={is_dead_quiet}")

        # 3. Decide Action
        if is_dead_quiet:
            # High chance to post to spark conversation
            if random.random() < 0.7:  # 70% chance if dead quiet
                await self.trigger_post(guild)
        elif is_quiet:
            # Low chance to post
            if random.random() < 0.3:  # 30% chance if just quiet
                await self.trigger_post(guild)
        else:
            # Active - do nothing, let ReactionAgent handle reactions (which runs on_message)
            pass

    async def trigger_post(self, guild: discord.Guild) -> None:
        """Trigger the PostingAgent to generate a post."""
        character_name = settings.DISCORD_BOT_NAME
        if not character_name:
            return

        # Find a suitable channel to post in
        target_channel = self._get_target_channel(guild)
        if not target_channel:
            logger.warning(f"No suitable channel found in {guild.name} for autonomous post")
            return

        logger.info(f"Triggering autonomous post for {character_name} in {guild.name} (#{target_channel.name})")
        
        # Run generation (this puts it in the broadcast queue)
        success = await self.posting_agent.generate_and_schedule_post(
            character_name, 
            target_channel_id=str(target_channel.id)
        )
        
        if success:
            logger.info(f"Successfully scheduled autonomous post for {character_name}")

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
