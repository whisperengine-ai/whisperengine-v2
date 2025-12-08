import asyncio
from datetime import datetime
from typing import Optional, Union
from loguru import logger
import discord
from discord.ext import commands
from discord import abc
from src_v2.config.settings import settings
from src_v2.core.database import db_manager
from src_v2.intelligence.activity import activity_modeler
from src_v2.intelligence.timezone import timezone_manager
from src_v2.agents.proactive import proactive_agent
from src_v2.memory.manager import memory_manager
from src_v2.memory.session import session_manager
from src_v2.evolution.drives import drive_manager, Drive

class ProactiveScheduler:
    """Manages proactive engagement scheduling for the bot."""
    
    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self.check_interval_minutes: int = settings.PROACTIVE_CHECK_INTERVAL_MINUTES
        self.min_trust_score: int = settings.PROACTIVE_MIN_TRUST_SCORE
        self.silence_threshold_hours: int = settings.PROACTIVE_SILENCE_THRESHOLD_HOURS
        self.is_running: bool = False
        self._tasks: list = []

    def start(self) -> None:
        """Starts the proactive scheduler loop."""
        if self.is_running:
            return
        self.is_running = True
        self._tasks = [
            self.bot.loop.create_task(self._loop(), name="proactive_scheduler"),
        ]
        logger.info("ProactiveScheduler started.")

    async def stop(self) -> None:
        """Stops the proactive scheduler gracefully."""
        if not self.is_running:
            return
        self.is_running = False
        for task in self._tasks:
            if not task.done():
                task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("ProactiveScheduler stopped.")

    async def _loop(self) -> None:
        """Main scheduler loop that runs periodically."""
        await self.bot.wait_until_ready()
        
        # Wait for the interval BEFORE the first check to prevent immediate triggers on restart
        logger.info(f"ProactiveScheduler waiting {self.check_interval_minutes} minutes before first check...")
        await asyncio.sleep(self.check_interval_minutes * 60)
        
        while self.is_running:
            try:
                await self.check_all_users()
            except Exception as e:
                logger.error(f"Error in proactive scheduler loop: {e}")
            
            await asyncio.sleep(self.check_interval_minutes * 60)



    async def check_all_users(self) -> None:
        """Checks all users with relationships to determine if proactive engagement is needed."""
        if not db_manager.postgres_pool:
            return

        character_name: Optional[str] = settings.DISCORD_BOT_NAME
        if not character_name:
            return

        logger.info("Running proactive engagement check...")

        # Get all users who have a relationship with this bot
        # Join with sessions to get last interaction time
        async with db_manager.postgres_pool.acquire() as conn:
            users = await conn.fetch("""
                SELECT 
                    r.user_id, 
                    r.trust_score,
                    MAX(s.updated_at) as last_interaction
                FROM v2_user_relationships r
                LEFT JOIN v2_conversation_sessions s 
                    ON r.user_id = s.user_id 
                    AND r.character_name = s.character_name
                WHERE r.character_name = $1
                GROUP BY r.user_id, r.trust_score
            """, character_name)

        for row in users:
            user_id = row['user_id']
            trust_score = row['trust_score']
            last_interaction = row['last_interaction']

            await self.check_user(user_id, trust_score, last_interaction)

    async def check_user(self, user_id: str, trust_score: int, last_interaction: Optional[datetime]) -> None:
        """Checks if we should message a specific user based on drives and activity patterns."""
        
        # 1. Check Feature Flags (master switch + proactive messaging)
        if not settings.ENABLE_AUTONOMOUS_ACTIVITY:
            return
        if not settings.ENABLE_PROACTIVE_MESSAGING:
            return

        # Check for Autonomous Drives flag
        if not settings.ENABLE_AUTONOMOUS_DRIVES:
            # Fallback or disable if drives are not enabled
            return

        # 2. Evaluate Drives (Internal Motivation)
        # This replaces the simple "time since last message" check
        character_name = settings.DISCORD_BOT_NAME or "default"
        
        # 2.5 Check Quiet Hours (S4: Timezone Awareness)
        # Don't message users during their local night time
        user_time_settings = await timezone_manager.get_user_time_settings(user_id, character_name)
        if timezone_manager.is_quiet_hours(user_time_settings):
            logger.debug(f"User {user_id}: Skipping proactive message - quiet hours ({user_time_settings.timezone})")
            return
        
        active_drives = await drive_manager.evaluate_drives(user_id, character_name, trust_score, last_interaction)
        
        # Filter for drives strong enough to act on
        actionable_drives = []
        for drive in active_drives:
            if await drive_manager.should_initiate(user_id, character_name, drive):
                actionable_drives.append(drive)
        
        if not actionable_drives:
            # No internal motivation to talk
            return

        # Pick the strongest drive
        primary_drive = max(actionable_drives, key=lambda d: d.value)
        logger.info(f"User {user_id}: Strongest drive is {primary_drive.name} ({primary_drive.value:.2f})")

        # 3. Check Activity Model (Is it a good time for the USER?)
        # We still respect the user's schedule even if we want to talk
        is_good_time, confidence = await activity_modeler.is_good_time_to_message(user_id)
        if not is_good_time:
            logger.debug(f"User {user_id}: High drive but bad time (confidence {confidence:.2f})")
            return

        # 4. Trigger Engagement
        logger.info(f"Triggering proactive message for User {user_id} driven by {primary_drive.name}")
        await self.trigger_proactive_message(user_id, drive=primary_drive)

    async def trigger_proactive_message(self, user_id: str, drive: Optional[Drive] = None) -> None:
        """Generates and sends a proactive message to a user.
        
        Args:
            user_id: Discord user ID to message
            drive: The internal drive motivating this message
        """
        try:
            user: discord.User = await self.bot.fetch_user(int(user_id))
            if not user:
                logger.warning(f"Could not fetch user {user_id} for proactive message.")
                return

            character_name: str = settings.DISCORD_BOT_NAME or "default"
            
            # 1. Determine Target Channel
            # Can be a guild channel, DM channel, or User object
            target_channel: Optional[Union[discord.abc.GuildChannel, discord.DMChannel, discord.User]] = None
            is_dm: bool = False
            
            # Try to find last channel from history
            if db_manager.postgres_pool:
                async with db_manager.postgres_pool.acquire() as conn:
                    last_channel_id: Optional[str] = await conn.fetchval("""
                        SELECT channel_id 
                        FROM v2_chat_history 
                        WHERE user_id = $1 AND character_name = $2 
                        ORDER BY timestamp DESC 
                        LIMIT 1
                    """, user_id, character_name)
                    
                    if last_channel_id:
                        try:
                            target_channel = await self.bot.fetch_channel(int(last_channel_id))  # type: ignore[assignment]
                        except Exception as e:
                            logger.warning(f"Could not fetch last channel {last_channel_id}: {e}")

            # Fallback to DM if no channel found
            if not target_channel:
                target_channel = user
                is_dm = True
            else:
                # Check if the found channel is actually a DM channel
                # Use getattr to safely check for guild attribute
                is_dm = getattr(target_channel, 'guild', None) is None

            # 2. Check Privacy if DM
            if is_dm and settings.ENABLE_DM_BLOCK:
                if user_id not in settings.dm_allowed_user_ids_list:
                    logger.info(f"Skipping proactive message to {user.name}: DMs blocked and no public channel found.")
                    return

            # 3. Generate Opener
            opener: Optional[str] = await proactive_agent.generate_opener(
                user_id, 
                user.name,
                character_name, 
                is_public=not is_dm,
                channel_id=str(target_channel.id) if target_channel and hasattr(target_channel, 'id') else None,
                drive=drive
            )
            
            if opener:
                # 4. Send Message
                sent_msg: discord.Message
                if not is_dm:
                    # Ping user in public channel
                    content: str = f"<@{user_id}> {opener}"
                    channel_name: str = getattr(target_channel, 'name', 'unknown')
                    logger.info(f"Sending proactive ping to {user.name} in #{channel_name}: {opener}")
                    # Type assertion: we know it's messageable if we got here
                    sent_msg = await target_channel.send(content)  # type: ignore[union-attr]
                else:
                    # DM
                    logger.info(f"Sending proactive DM to {user.name}: {opener}")
                    sent_msg = await target_channel.send(opener)  # type: ignore[union-attr]
                
                # 5. Log to Memory
                await memory_manager.add_message(
                    user_id=user_id,
                    character_name=character_name,
                    role='ai',
                    content=opener,
                    channel_id=str(sent_msg.channel.id),
                    message_id=str(sent_msg.id),
                    user_name=user.name
                )
                
                # 6. Update Session Activity (Prevent duplicate triggers)
                await session_manager.get_active_session(user_id, character_name)
                
            else:
                logger.warning(f"Failed to generate opener for {user.name}")

        except Exception as e:
            logger.error(f"Failed to send proactive message to {user_id}: {e}")
