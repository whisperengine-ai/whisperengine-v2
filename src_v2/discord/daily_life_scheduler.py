"""
Daily Life Scheduler - Runs the Daily Life Graph in the bot process.

This scheduler replaces the worker-based cron approach because
the Daily Life Graph needs access to the Discord bot instance.
"""

import asyncio
from typing import TYPE_CHECKING, Optional

from loguru import logger

from src_v2.config.settings import settings

if TYPE_CHECKING:
    from discord.ext import commands
    from src_v2.core.character import Character


class DailyLifeScheduler:
    """
    Runs the Daily Life Graph periodically within the bot process.
    
    Unlike worker crons, this has direct access to the Discord bot
    for sending messages, adding reactions, etc.
    """
    
    def __init__(self, bot: "commands.Bot") -> None:
        self.bot = bot
        self._character: Optional["Character"] = None
        self.check_interval_minutes: int = settings.DISCORD_CHECK_INTERVAL_MINUTES
        self.is_running: bool = False
        self._task: asyncio.Task | None = None
    
    @property
    def character(self) -> "Character":
        """Lazy-load character from character_manager."""
        if self._character is None:
            from src_v2.core.character import character_manager
            self._character = character_manager.characters.get(settings.DISCORD_BOT_NAME)
            if self._character is None:
                # Load if not already cached
                self._character = character_manager.load_character(settings.DISCORD_BOT_NAME)
        if self._character is None:
            raise RuntimeError(f"Character {settings.DISCORD_BOT_NAME} not loaded")
        return self._character
    
    def start(self) -> None:
        """Starts the daily life scheduler loop."""
        if not settings.ENABLE_DAILY_LIFE_GRAPH:
            logger.info("[DailyLife] ENABLE_DAILY_LIFE_GRAPH is False, not starting scheduler")
            return
        
        if not settings.ENABLE_AUTONOMOUS_ACTIVITY:
            logger.info("[DailyLife] ENABLE_AUTONOMOUS_ACTIVITY is False, not starting scheduler")
            return
        
        if self.is_running:
            return
        
        self.is_running = True
        self._task = self.bot.loop.create_task(self._loop(), name="daily_life_scheduler")
        logger.info(f"[DailyLife] Scheduler started (interval: {self.check_interval_minutes} min)")
    
    async def stop(self) -> None:
        """Stops the daily life scheduler gracefully."""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        self._task = None
        logger.info("[DailyLife] Scheduler stopped")
    
    async def _loop(self) -> None:
        """Main scheduler loop that runs periodically."""
        await self.bot.wait_until_ready()
        
        # Wait a bit before first check to let everything initialize
        initial_delay = 60  # 1 minute
        logger.info(f"[DailyLife] Waiting {initial_delay}s before first check...")
        await asyncio.sleep(initial_delay)
        
        while self.is_running:
            try:
                await self._run_daily_life_check()
            except Exception as e:
                logger.error(f"[DailyLife] Error in scheduler loop: {e}")
            
            # Sleep until next check
            await asyncio.sleep(self.check_interval_minutes * 60)
    
    async def _run_daily_life_check(self) -> None:
        """Run a single daily life check."""
        from src_v2.agents.daily_life.graph import DailyLifeGraph
        
        logger.info(f"[DailyLife] Starting check for {self.character.name}...")
        
        try:
            graph = DailyLifeGraph(self.bot, self.character)
            result = await graph.run()
            
            if result.get("success"):
                actions = result.get("actions_taken", 0)
                if result.get("skipped"):
                    logger.info(f"[DailyLife] {self.character.name}: Skipped (nothing to do)")
                else:
                    logger.info(f"[DailyLife] {self.character.name}: Completed with {actions} action(s)")
            else:
                logger.error(f"[DailyLife] {self.character.name}: Failed - {result.get('error')}")
                
        except Exception as e:
            logger.error(f"[DailyLife] {self.character.name}: Exception - {e}")
    
    async def trigger_manual_check(self) -> dict:
        """Manually trigger a daily life check (for testing/debugging)."""
        logger.info(f"[DailyLife] Manual check triggered for {self.character.name}")
        
        from src_v2.agents.daily_life.graph import DailyLifeGraph
        
        graph = DailyLifeGraph(self.bot, self.character)
        return await graph.run()
