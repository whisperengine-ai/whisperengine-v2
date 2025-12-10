import discord
from discord.ext import commands
from loguru import logger
from typing import Optional

from src_v2.config.settings import settings
from src_v2.agents.engine import AgentEngine
from src_v2.discord.scheduler import ProactiveScheduler
from src_v2.discord.daily_life_scheduler import DailyLifeScheduler
from src_v2.discord.handlers.event_handler import EventHandler
from src_v2.discord.handlers.message_handler import MessageHandler
from src_v2.discord.tasks import BotTasks

class WhisperBot(commands.Bot):
    """Discord bot with AI character personality and memory systems."""
    
    agent_engine: AgentEngine
    scheduler: ProactiveScheduler
    character_name: str
    
    def __init__(self) -> None:
        """Initialize the WhisperBot with Discord intents and AI systems."""
        intents: discord.Intents = discord.Intents.default()
        intents.message_content = True  # Required to read messages
        intents.members = True          # Required to see members
        intents.voice_states = True     # Required for voice
        intents.presences = True        # Required for status updates to be seen reliably
        
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )
        
        self.agent_engine = AgentEngine()
        self.scheduler = ProactiveScheduler(self)
        self.daily_life_scheduler = DailyLifeScheduler(self)
        
        # Validate Bot Identity
        if not settings.DISCORD_BOT_NAME:
            raise ValueError("DISCORD_BOT_NAME must be set in environment variables")
        self.character_name = settings.DISCORD_BOT_NAME
        
        # Initialize Handlers
        self.event_handler = EventHandler(self)
        self.message_handler = MessageHandler(self)
        self.tasks = BotTasks(self)

    async def setup_hook(self) -> None:
        """Async setup hook called before the bot starts."""
        # Start Daily Life Scheduler (E31 - unified autonomous behavior)
        self.daily_life_scheduler.start()

        # Load slash commands
        from src_v2.discord.commands import setup as setup_commands
        await setup_commands(self)
        logger.info("Slash commands loaded")
        
        # Sync commands with Discord
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} slash commands")
        except Exception as e:
            logger.error(f"Failed to sync slash commands: {e}")
            
        # Delegate to BotTasks
        await self.tasks.setup_hook()

    async def on_ready(self) -> None:
        """Called when the bot has successfully connected to Discord."""
        await self.event_handler.on_ready()

    async def on_message(self, message: discord.Message) -> None:
        """Handles incoming Discord messages."""
        await self.message_handler.on_message(message)

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Called when the bot joins a new guild."""
        await self.event_handler.on_guild_join(guild)

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """Called when the bot is removed from a guild."""
        await self.event_handler.on_guild_remove(guild)

    async def on_member_join(self, member: discord.Member) -> None:
        """Called when a member joins a guild."""
        await self.event_handler.on_member_join(member)

    async def on_member_remove(self, member: discord.Member) -> None:
        """Called when a member leaves a guild."""
        await self.event_handler.on_member_remove(member)

    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User) -> None:
        """Handle reaction additions."""
        await self.event_handler.on_reaction_add(reaction, user)

    async def on_reaction_remove(self, reaction: discord.Reaction, user: discord.User) -> None:
        """Handle reaction removals."""
        await self.event_handler.on_reaction_remove(reaction, user)

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """Handle command errors silently for CommandNotFound (user typos/unavailable commands)."""
        # Silently ignore CommandNotFound errors (users typing unavailable commands)
        if isinstance(error, commands.CommandNotFound):
            return  # Don't log or respond - just ignore
        
        # Log other command errors for debugging
        logger.warning(f"Command error in {ctx.command}: {error}")

    async def close(self) -> None:
        """Override close to cancel background tasks first."""
        logger.info("Closing WhisperBot...")
        
        # Cancel background tasks
        if hasattr(self, 'tasks') and self.tasks:
            await self.tasks.cancel_all_tasks()
        
        # Stop scheduler if running
        if hasattr(self, 'scheduler') and self.scheduler:
            try:
                await self.scheduler.stop()
            except Exception as e:
                logger.debug(f"Error stopping scheduler: {e}")
        
        # Stop orchestrator if running
        if hasattr(self, 'orchestrator') and self.orchestrator:
            try:
                await self.orchestrator.stop()
            except Exception as e:
                logger.debug(f"Error stopping orchestrator: {e}")
        
        # Stop daily life scheduler if running
        if hasattr(self, 'daily_life_scheduler') and self.daily_life_scheduler:
            try:
                await self.daily_life_scheduler.stop()
            except Exception as e:
                logger.debug(f"Error stopping daily life scheduler: {e}")
        
        # Call parent close
        await super().close()
        logger.info("WhisperBot closed")

# Create global bot instance
bot = WhisperBot()

