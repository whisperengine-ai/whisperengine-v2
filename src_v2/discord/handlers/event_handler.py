import asyncio
import discord
from loguru import logger
from typing import Any, Optional
from src_v2.config.settings import settings
from src_v2.core.character import character_manager
from src_v2.evolution.trust import trust_manager

class EventHandler:
    def __init__(self, bot):
        self.bot = bot

    async def on_ready(self) -> None:
        """Called when the bot has successfully connected to Discord."""
        if self.bot.user:
            logger.info(f"Logged in as {self.bot.user} (ID: {self.bot.user.id})")
        else:
            logger.warning("Bot connected but user is not set")
        await self.bot.change_presence(status=discord.Status.online)
        
        # Preload character
        char: Optional[Any] = character_manager.get_character(self.bot.character_name)
        if char:
            logger.info(f"Character '{self.bot.character_name}' loaded successfully.")
        else:
            logger.error(f"Could not load character '{self.bot.character_name}'!")

        logger.info("WhisperEngine is ready and listening.")

        # Register with internal API for worker callbacks
        try:
            from src_v2.api.internal_routes import set_discord_bot, register_bot_endpoint
            set_discord_bot(self.bot)
            # Register endpoint immediately
            await register_bot_endpoint()
            # Start background refresh loop
            # Note: This task is now started in setup_hook via BotTasks, but we register here to be safe
            logger.info("Registered with internal API for worker callbacks")
        except Exception as e:
            logger.warning(f"Failed to register with internal API: {e}")

        # Initialize broadcast manager with bot instance (Phase E8)
        if settings.ENABLE_BOT_BROADCAST:
            try:
                from src_v2.broadcast.manager import broadcast_manager
                broadcast_manager.set_bot(self.bot)
                logger.info("Broadcast manager initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize broadcast manager: {e}")

        # Initialize cross-bot manager (Phase E6)
        if settings.ENABLE_CROSS_BOT_CHAT:
            try:
                from src_v2.broadcast.cross_bot import cross_bot_manager
                cross_bot_manager.set_bot(self.bot)
                await cross_bot_manager.load_known_bots()
                # Start background registration refresh (task managed by cross_bot_manager)
                asyncio.create_task(
                    cross_bot_manager.start_registration_loop(),
                    name="cross_bot_registration"
                )
                logger.info("Cross-bot manager initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize cross-bot manager: {e}")

        # Check Permissions
        await self._check_permissions()

        # Universe Discovery: Register existing planets
        try:
            from src_v2.universe.manager import universe_manager
            for guild in self.bot.guilds:
                await universe_manager.register_planet(str(guild.id), guild.name)
                for channel in guild.channels:
                    if isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
                        await universe_manager.register_channel(
                            str(guild.id), 
                            str(channel.id), 
                            channel.name, 
                            str(channel.type)
                        )
                logger.info(f"Discovered planet: {guild.name}")
        except Exception as e:
            logger.error(f"Failed to register planets during startup: {e}")

    async def _check_permissions(self) -> None:
        """Checks if the bot has necessary permissions in connected guilds."""
        required_permissions = [
            ("view_channel", "View Channels"),
            ("send_messages", "Send Messages"),
            ("read_message_history", "Read Message History"),
            ("embed_links", "Embed Links"),
            ("attach_files", "Attach Files"),
            ("add_reactions", "Add Reactions"),
        ]
        
        # Optional permissions (feature-dependent)
        optional_permissions = [
            ("manage_messages", "Manage Messages (Spam Deletion)"),
            ("connect", "Connect (Voice)"),
            ("speak", "Speak (Voice)"),
        ]
        
        logger.info("--- Checking Permissions ---")
        
        # 1. Check Invite Scopes (Best Effort Warning)
        logger.info("NOTE: Ensure the bot was invited with 'applications.commands' scope for Slash Commands to work.")
        
        for guild in self.bot.guilds:
            permissions = guild.me.guild_permissions
            missing = []
            
            # Check Administrator
            if permissions.administrator:
                logger.info(f"✅ Guild '{guild.name}': Administrator (All permissions granted)")
                continue
                
            # Check individual permissions
            for perm_code, perm_name in required_permissions:
                if not getattr(permissions, perm_code):
                    missing.append(perm_name)
            
            if missing:
                logger.warning(f"⚠️  Guild '{guild.name}': Missing Permissions: {', '.join(missing)}")
                logger.warning(f"    -> Some features may not work correctly in '{guild.name}'.")
            else:
                logger.info(f"✅ Guild '{guild.name}': All required permissions granted.")
                
        logger.info("----------------------------")

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Called when the bot joins a new guild (Planet)."""
        logger.info(f"Joined new planet: {guild.name} ({guild.id})")
        try:
            from src_v2.universe.manager import universe_manager
            await universe_manager.register_planet(str(guild.id), guild.name)
            for channel in guild.channels:
                if isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
                    await universe_manager.register_channel(
                        str(guild.id), 
                        str(channel.id), 
                        channel.name, 
                        str(channel.type)
                    )
        except Exception as e:
            logger.error(f"Failed to register new planet {guild.name}: {e}")

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """Called when the bot is removed from a guild (Planet)."""
        logger.info(f"Left planet: {guild.name} ({guild.id})")
        try:
            from src_v2.universe.manager import universe_manager
            await universe_manager.mark_planet_inactive(str(guild.id))
        except Exception as e:
            logger.error(f"Failed to mark planet inactive {guild.name}: {e}")

    async def on_member_join(self, member: discord.Member) -> None:
        """Called when a member joins a guild."""
        if member.bot: return
        try:
            from src_v2.universe.manager import universe_manager
            await universe_manager.record_presence(str(member.id), str(member.guild.id))
        except Exception as e:
            logger.error(f"Failed to record member join: {e}")

    async def on_member_remove(self, member: discord.Member) -> None:
        """Called when a member leaves a guild."""
        if member.bot: return
        try:
            from src_v2.universe.manager import universe_manager
            await universe_manager.remove_inhabitant(str(member.id), str(member.guild.id))
        except Exception as e:
            logger.error(f"Failed to record member leave: {e}")

    async def on_reaction_add(self, reaction: discord.Reaction, user: Any) -> None:
        """Handle reaction additions (Feedback System)."""
        if user.bot: return
        
        # Only track reactions on the bot's own messages
        if reaction.message.author.id != self.bot.user.id:
            return

        try:
            # Map emoji to feedback type
            feedback_type = None
            emoji_str = str(reaction.emoji)
            
            if emoji_str in ["👍", "❤️", "🔥", "✨"]:
                feedback_type = "positive"
            elif emoji_str in ["👎", "😠", "💩"]:
                feedback_type = "negative"
            
            if feedback_type:
                # 1. Update Trust
                change = 1 if feedback_type == "positive" else -1
                milestone = await trust_manager.update_trust(str(user.id), self.bot.character_name, change)
                
                # 2. Record Feedback in Memory (Metadata update)
                # We need to find the memory ID associated with this message ID
                # This is tricky because we don't have a direct mapping here without querying
                # For now, we'll just log it and maybe update trust
                logger.info(f"Received {feedback_type} feedback from user {user.id} on message {reaction.message.id}")
                
                # If milestone reached, DM the user (don't spam channel)
                if milestone:
                    try:
                        await user.send(milestone)
                    except:
                        pass # DM might be blocked

        except Exception as e:
            logger.error(f"Error handling reaction add: {e}")

    async def on_reaction_remove(self, reaction: discord.Reaction, user: Any) -> None:
        """Handle reaction removals (Undo Feedback)."""
        if user.bot: return
        
        if reaction.message.author.id != self.bot.user.id:
            return

        try:
            emoji_str = str(reaction.emoji)
            if emoji_str in ["👍", "❤️", "🔥", "✨", "👎", "😠", "💩"]:
                # Revert trust change (approximate)
                change = -1 if emoji_str in ["👍", "❤️", "🔥", "✨"] else 1
                await trust_manager.update_trust(str(user.id), self.bot.character_name, change)
                logger.info(f"Reverted feedback from user {user.id} on message {reaction.message.id}")

        except Exception as e:
            logger.error(f"Error handling reaction remove: {e}")
