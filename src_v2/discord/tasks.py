import asyncio
import discord
from loguru import logger
from typing import List
from src_v2.config.settings import settings
from src_v2.core.database import db_manager

class BotTasks:
    def __init__(self, bot):
        self.bot = bot
        self._background_tasks: List[asyncio.Task] = []

    async def setup_hook(self) -> None:
        """Start background tasks with proper tracking."""
        self._background_tasks = [
            self.bot.loop.create_task(self.process_broadcast_queue_loop(), name="broadcast_queue"),
            self.bot.loop.create_task(self.refresh_endpoint_registration_loop(), name="endpoint_registration"),
            self.bot.loop.create_task(self.update_status_loop(), name="status_update"),
            self.bot.loop.create_task(self.bot_registry_heartbeat_loop(), name="bot_registry_heartbeat"),
            # graph_pruning moved to worker cron task (run_weekly_graph_pruning)
        ]
        logger.info(f"Started {len(self._background_tasks)} background tasks")

    async def cancel_all_tasks(self) -> None:
        """Cancel all background tasks gracefully."""
        if not self._background_tasks:
            return
        
        logger.info(f"Cancelling {len(self._background_tasks)} background tasks...")
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
        
        # Wait for all tasks to complete cancellation
        results = await asyncio.gather(*self._background_tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, asyncio.CancelledError):
                logger.debug(f"Task {self._background_tasks[i].get_name()} cancelled")
            elif isinstance(result, Exception):
                logger.error(f"Task {self._background_tasks[i].get_name()} error: {result}")
        
        self._background_tasks.clear()
        logger.info("All background tasks cancelled")

    async def process_broadcast_queue_loop(self) -> None:
        """
        Background task to process queued broadcasts from workers (Phase E8).
        
        This is a FALLBACK mechanism. Workers should prefer calling the HTTP
        callback endpoints directly for faster delivery. This loop catches any
        queued items that failed HTTP delivery or were queued when the bot was down.
        """
        await self.bot.wait_until_ready()
        
        # Give things time to initialize
        await asyncio.sleep(10)
        
        while not self.bot.is_closed():
            try:
                from src_v2.broadcast.manager import broadcast_manager
                
                posted = await broadcast_manager.process_queued_broadcasts()
                if posted > 0:
                    logger.info(f"Processed {posted} queued broadcasts (fallback)")
                    
            except Exception as e:
                logger.debug(f"Broadcast queue check failed: {e}")
            
            # Check every 5 seconds to ensure interactive media is delivered quickly
            await asyncio.sleep(5)

    async def refresh_endpoint_registration_loop(self) -> None:
        """Background task to refresh internal API endpoint registration in Redis."""
        await self.bot.wait_until_ready()
        
        while not self.bot.is_closed():
            try:
                from src_v2.api.internal_routes import register_bot_endpoint
                await register_bot_endpoint()
            except Exception as e:
                logger.debug(f"Endpoint registration refresh failed: {e}")
            
            # Refresh every 30 minutes (TTL is 1 hour)
            await asyncio.sleep(1800)

    async def update_status_loop(self) -> None:
        """Background task to periodically update bot status with statistics."""
        await self.bot.wait_until_ready()
        # Initial status set
        await self.bot.change_presence(status=discord.Status.online)
        
        status_index: int = 0
        while not self.bot.is_closed():
            try:
                if db_manager.postgres_pool:
                    async with db_manager.postgres_pool.acquire() as conn:
                        if status_index % 2 == 0:
                            # Status 1: Friends & Memories
                            friends_count = await conn.fetchval("""
                                SELECT COUNT(*) FROM v2_user_relationships 
                                WHERE character_name = $1 AND trust_score >= 20
                            """, settings.DISCORD_BOT_NAME)
                            
                            activity = discord.Activity(
                                type=discord.ActivityType.watching,
                                name=f"{friends_count} friends"
                            )
                        else:
                            # Status 2: Memories
                            # This is just an estimate/fun stat
                            activity = discord.Activity(
                                type=discord.ActivityType.listening,
                                name="your stories"
                            )
                            
                        await self.bot.change_presence(activity=activity)
                        status_index += 1
                        
            except Exception as e:
                logger.debug(f"Status update failed: {e}")
            
            await asyncio.sleep(settings.STATUS_UPDATE_INTERVAL_SECONDS)

    async def bot_registry_heartbeat_loop(self) -> None:
        """Background task to keep bot registered in the Universe Registry."""
        await self.bot.wait_until_ready()
        
        from src_v2.universe.registry import bot_registry
        
        # Start the heartbeat loop
        # Note: start_heartbeat is an infinite loop, so we wrap it
        try:
            await bot_registry.start_heartbeat(self.bot)
        except asyncio.CancelledError:
            logger.info("Bot registry heartbeat cancelled")
        except Exception as e:
            logger.error(f"Bot registry heartbeat failed: {e}")

    # weekly_graph_pruning_loop removed - now handled by worker cron task
    # See src_v2/workers/tasks/cron_tasks.py::run_weekly_graph_pruning
