from langchain_core.messages import HumanMessage
import discord
import asyncio
import re
import time
from typing import Union, List, Tuple, Any, Optional
from datetime import datetime
from discord.ext import commands
from loguru import logger
from src_v2.config.settings import settings
from src_v2.agents.engine import AgentEngine
from src_v2.core.character import character_manager
from src_v2.memory.manager import memory_manager
from src_v2.memory.session import session_manager
from src_v2.knowledge.manager import knowledge_manager
from src_v2.knowledge.documents import document_processor
from src_v2.knowledge.document_context import DocumentContext
from src_v2.voice.player import play_text
from src_v2.core.database import db_manager
from src_v2.evolution.feedback import feedback_analyzer
from src_v2.evolution.goals import goal_analyzer
from src_v2.evolution.trust import trust_manager
from src_v2.evolution.extractor import preference_extractor
from src_v2.evolution.emoji_taxonomy import emoji_taxonomy
from src_v2.vision.manager import vision_manager
from src_v2.discord.scheduler import ProactiveScheduler
from src_v2.discord.lurk_detector import get_lurk_detector, LurkDetector
from src_v2.workers.task_queue import task_queue
from src_v2.image_gen.service import pending_images
from influxdb_client.client.write.point import Point
from src_v2.utils.validation import ValidationError, validator, smart_truncate
import random

# Regex pattern for BFL image URLs (to strip them out if LLM includes them)
BFL_IMAGE_URL_PATTERN = re.compile(
    r'https://bfldelivery\S+\.blob\.core\.windows\.net/results/\S+\.(jpeg|jpg|png)'
)


async def extract_pending_images(text: str, user_id: str) -> Tuple[str, List[discord.File]]:
    """
    Retrieve any pending images for the user from Redis.
    Also strips out any BFL URLs that the LLM might have included.
    
    Args:
        text: The response text
        user_id: The user ID to check for pending images
        
    Returns:
        Tuple of (cleaned_text, list_of_discord_files)
    """
    files: List[discord.File] = []
    
    # Retrieve all pending images for this user from Redis
    results = await pending_images.pop_all(user_id)
    
    for result in results:
        files.append(result.to_discord_file())
        logger.info(f"Retrieved pending image for user {user_id} for Discord upload")
    
    # Strip out any BFL URLs that the LLM might have included
    cleaned_text = BFL_IMAGE_URL_PATTERN.sub("", text)
    
    # Clean up any double spaces or newlines left behind
    cleaned_text = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned_text)
    
    return cleaned_text.strip(), files


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
        self.lurk_detector: Optional[LurkDetector] = None
        
        # Validate Bot Identity
        if not settings.DISCORD_BOT_NAME:
            raise ValueError("DISCORD_BOT_NAME is not set. Please set it in your .env file or environment variables.")
            
        self.character_name = settings.DISCORD_BOT_NAME

    def _chunk_message(self, text: str, max_length: int = 2000) -> List[str]:
        """
        Splits a long message into chunks that fit Discord's character limit.
        Tries to split on sentence boundaries when possible.
        
        Args:
            text: The text to split into chunks
            max_length: Maximum length per chunk (Discord limit is 2000)
            
        Returns:
            List of text chunks
        """
        if len(text) <= max_length:
            return [text]
        
        chunks: List[str] = []
        current_chunk: str = ""
        
        # Split by sentences (basic approach)
        sentences = text.replace("\n\n", "\n\n<BREAK>").replace(". ", ".<BREAK>").split("<BREAK>")
        
        for sentence in sentences:
            # If adding this sentence would exceed the limit
            if len(current_chunk) + len(sentence) > max_length:
                # If current chunk has content, save it
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                
                # If the sentence itself is too long, force split by words
                if len(sentence) > max_length:
                    words = sentence.split()
                    for word in words:
                        if len(current_chunk) + len(word) + 1 > max_length:
                            chunks.append(current_chunk.strip())
                            current_chunk = word + " "
                        else:
                            current_chunk += word + " "
                else:
                    current_chunk = sentence
            else:
                current_chunk += sentence
        
        # Add the last chunk
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks

    def _is_image(self, attachment: discord.Attachment) -> bool:
        """
        Determines if an attachment is an image based on content_type or filename extension.
        
        Args:
            attachment: Discord attachment object
            
        Returns:
            True if the attachment is an image, False otherwise
        """
        # 1. Check Content-Type (Reliable if present)
        if attachment.content_type and attachment.content_type.startswith("image/"):
            return True
            
        # 2. Fallback: Check Extension
        valid_extensions: set[str] = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.tiff'}
        import os
        _: str
        ext: str
        _, ext = os.path.splitext(attachment.filename)
        if ext.lower() in valid_extensions:
            return True
            
        return False

    async def update_status_loop(self) -> None:
        """Background task to periodically update bot status with statistics."""
        await self.wait_until_ready()
        # Initial status set
        await self.change_presence(status=discord.Status.online)
        
        status_index: int = 0
        while not self.is_closed():
            try:
                if db_manager.postgres_pool:
                    async with db_manager.postgres_pool.acquire() as conn:
                        if status_index % 2 == 0:
                            # Status 1: Friends & Memories
                            friends_count = await conn.fetchval("""
                                SELECT COUNT(*) FROM v2_user_relationships 
                                WHERE character_name = $1 AND trust_score >= 20
                            """, self.character_name)
                            
                            memories_count = await conn.fetchval("""
                                SELECT COUNT(*) FROM v2_chat_history 
                                WHERE character_name = $1
                            """, self.character_name)
                            
                            status_text = f"with {friends_count} friends | {memories_count} memories"
                        else:
                            # Status 2: Goal Progress
                            goal_stats = await conn.fetchrow("""
                                SELECT 
                                    COUNT(*) FILTER (WHERE p.status = 'completed') as completed,
                                    COUNT(*) as total
                                FROM v2_user_goal_progress p
                                JOIN v2_goals g ON p.goal_id = g.id
                                WHERE g.character_name = $1
                            """, self.character_name)
                            
                            completed = goal_stats['completed'] or 0
                            total = goal_stats['total'] or 0
                            percentage = int((completed / total * 100)) if total > 0 else 0
                            
                            status_text = f"Goal Progress: {percentage}% ({completed}/{total})"
                        
                        await self.change_presence(
                            activity=discord.Activity(
                                type=discord.ActivityType.playing, 
                                name=status_text
                            ),
                            status=discord.Status.online
                        )
                        logger.debug(f"Updated status to: {status_text}")
                        status_index += 1
            except Exception as e:
                logger.error(f"Failed to update status: {e}")
            
            await asyncio.sleep(settings.STATUS_UPDATE_INTERVAL_SECONDS)

    async def setup_hook(self) -> None:
        """Called during bot startup to load extensions and sync commands."""
        # Load extensions
        try:
            await self.load_extension("src_v2.discord.commands")
            logger.info("Loaded extension: src_v2.discord.commands")
        except Exception as e:
            logger.error(f"Failed to load extension: {e}")

        # Sync commands
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} command(s)")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

        # Start Proactive Scheduler
        if settings.ENABLE_PROACTIVE_MESSAGING:
            self.scheduler.start()
            logger.info("Proactive Scheduler enabled and started.")
        else:
            logger.info("Proactive Scheduler disabled in settings.")

        # Initialize Lurk Detector
        if settings.ENABLE_CHANNEL_LURKING:
            self.lurk_detector = get_lurk_detector(self.character_name)
            logger.info(f"Channel Lurking enabled for {self.character_name}.")
        else:
            logger.info("Channel Lurking disabled in settings.")

        # Start status update loop
        self.loop.create_task(self.update_status_loop())

    async def on_ready(self) -> None:
        """Called when the bot has successfully connected to Discord."""
        if self.user:
            logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        else:
            logger.warning("Bot connected but user is not set")
        await self.change_presence(status=discord.Status.online)
        
        # Preload character
        char: Optional[Any] = character_manager.get_character(self.character_name)
        if char:
            logger.info(f"Character '{self.character_name}' loaded successfully.")
        else:
            logger.error(f"Could not load character '{self.character_name}'!")

        logger.info("WhisperEngine is ready and listening.")

        # Check Permissions
        await self._check_permissions()

        # Universe Discovery: Register existing planets
        try:
            from src_v2.universe.manager import universe_manager
            for guild in self.guilds:
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

        # Check permissions
        await self._check_permissions()

    async def _check_permissions(self) -> None:
        """Checks if the bot has necessary permissions in connected guilds."""
        required_permissions = [
            ("view_channel", "View Channels"),
            ("send_messages", "Send Messages"),
            ("read_message_history", "Read Message History"),
            ("embed_links", "Embed Links"),
            ("attach_files", "Attach Files"),
            ("add_reactions", "Use External Emojis"),
            ("manage_messages", "Manage Messages (Delete Spam)"),
            ("connect", "Connect (Voice)"),
            ("speak", "Speak (Voice)"),
        ]
        
        logger.info("--- Checking Permissions ---")
        
        # 1. Check Invite Scopes (Best Effort Warning)
        logger.info("NOTE: Ensure the bot was invited with 'applications.commands' scope for Slash Commands to work.")
        
        for guild in self.guilds:
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

    async def on_message(self, message: discord.Message) -> None:
        """Handles incoming Discord messages and generates AI responses.
        
        Args:
            message: Discord message object
        """
        # Ignore messages from bots to prevent loops
        if message.author.bot:
            return

        # Ignore messages from blocked users
        if str(message.author.id) in settings.blocked_user_ids_list:
            logger.debug(f"Ignoring message from blocked user: {message.author.id}")
            return

        # Universe Presence & Observation
        if message.guild:
            try:
                from src_v2.universe.manager import universe_manager
                # task_queue is already imported globally
                
                # Fire and forget presence update (lightweight, keep in-process)
                asyncio.create_task(universe_manager.record_presence(str(message.author.id), str(message.guild.id)))
                
                # Enqueue message observation to background worker (Phase 2: Learning to Listen)
                # This extracts topics, tracks interactions, and learns peak hours
                mentioned_ids = [str(m.id) for m in message.mentions if not m.bot]
                reply_to_id = None
                if message.reference and message.reference.resolved:
                    if isinstance(message.reference.resolved, discord.Message) and not message.reference.resolved.author.bot:
                        reply_to_id = str(message.reference.resolved.author.id)
                
                # Only enqueue if there's meaningful content to observe
                if message.content and len(message.content.strip()) >= 10:
                    # Use message ID as job ID to prevent duplicate processing
                    # if multiple bots observe the same message
                    await task_queue.enqueue(
                        "run_universe_observation",
                        _job_id=f"universe_obs_{message.id}",
                        guild_id=str(message.guild.id),
                        channel_id=str(message.channel.id),
                        user_id=str(message.author.id),
                        message_content=message.content,
                        mentioned_user_ids=mentioned_ids,
                        reply_to_user_id=reply_to_id,
                        user_display_name=message.author.display_name
                    )
            except Exception as e:
                logger.debug(f"Failed to enqueue universe observation: {e}")

        # --- Spam Detection (Cross-posting) ---
        if message.guild and settings.ENABLE_CROSSPOST_DETECTION:
            try:
                from src_v2.discord.spam_detector import spam_detector
                
                # Check whitelist
                is_whitelisted = await spam_detector.is_whitelisted(message.author.roles, str(message.guild.id))
                
                if not is_whitelisted:
                    is_spam = False
                    should_warn = False
                    
                    # Check text spam
                    if message.content:
                        is_spam, should_warn = await spam_detector.check_crosspost(
                            user_id=str(message.author.id),
                            channel_id=str(message.channel.id),
                            content=message.content
                        )
                    
                    # Check file spam
                    if not is_spam and message.attachments:
                        is_spam, should_warn = await spam_detector.check_file_crosspost(
                            user_id=str(message.author.id),
                            channel_id=str(message.channel.id),
                            attachments=message.attachments
                        )
                    
                    if is_spam:
                        # Action: Delete or Warn
                        if spam_detector.action == "delete":
                            try:
                                await message.delete()
                                if should_warn:
                                    warning = f"{message.author.mention} ⚠️ Message deleted for cross-posting spam."
                                    await message.channel.send(warning)
                            except Exception as e:
                                logger.error(f"Failed to delete spam message: {e}")
                        else:
                            # Warn the user (only if new detection)
                            if should_warn:
                                # Try to get character-specific warning
                                warning_msg = settings.CROSSPOST_WARNING_MESSAGE
                                if self.lurk_detector and self.lurk_detector.triggers.spam_warnings:
                                    warning_msg = random.choice(self.lurk_detector.triggers.spam_warnings)
                                
                                warning = f"{message.author.mention} {warning_msg}"
                                await message.channel.send(warning)
                            
                        logger.warning(f"Actioned user {message.author.id} for cross-posting spam.")
                        return
            except Exception as e:
                logger.error(f"Spam detection failed: {e}")

        # Process commands first
        await self.process_commands(message)
        
        # Handle Stickers (Convert to text context)
        sticker_text: str = ""
        if message.stickers:
            sticker_names = [sticker.name for sticker in message.stickers]
            sticker_text = f"\n[User sent sticker(s): {', '.join(sticker_names)}]"
            logger.info(f"Detected stickers: {sticker_names}")
        
        # Ignore empty messages (unless they have stickers/attachments) or system messages
        if (not message.content and not sticker_text and not message.attachments) or message.is_system():
            return

        # Determine if we should respond
        # 1. Direct Message (DM)
        # 2. Mentioned in a server
        # 3. Replying to the bot (even without ping)
        is_dm = isinstance(message.channel, discord.DMChannel)
        is_mentioned = self.user in message.mentions
        
        # Check for Reply without Ping
        if not is_mentioned and message.reference:
            try:
                # Check resolved reference first
                if message.reference.resolved and isinstance(message.reference.resolved, discord.Message):
                    if message.reference.resolved.author.id == (self.user.id if self.user else None):
                        is_mentioned = True
                        logger.info("Detected reply to bot without ping.")
                # Fallback: Fetch message if not resolved
                elif message.reference.message_id:
                    try:
                        ref_msg = await message.channel.fetch_message(message.reference.message_id)
                        if ref_msg.author.id == (self.user.id if self.user else None):
                            is_mentioned = True
                            logger.info("Detected reply to bot without ping (fetched).")
                    except:
                        pass
            except Exception as e:
                logger.warning(f"Failed to check reply reference: {e}")

        # Check for Thread Context (Thread started on bot message)
        # If the thread was started on a message sent by the bot, we should reply in it
        if not is_mentioned and isinstance(message.channel, discord.Thread):
            try:
                # The ID of the thread is the ID of the starter message
                # We need to check if that starter message was sent by us
                # Try to get from cache first
                starter_msg = message.channel.starter_message
                
                # If not in cache, try to fetch from parent channel
                if not starter_msg and message.channel.parent:
                    try:
                        starter_msg = await message.channel.parent.fetch_message(message.channel.id)
                    except (discord.NotFound, discord.Forbidden):
                        pass # Message might be deleted or we lack permissions
                
                if starter_msg and starter_msg.author.id == (self.user.id if self.user else None):
                    is_mentioned = True
                    logger.info("Detected message in thread started on bot message.")
            except Exception as e:
                logger.warning(f"Failed to check thread starter: {e}")
        
        # Privacy: Block DMs if enabled and user is not allowlisted
        if is_dm and settings.ENABLE_DM_BLOCK:
            user_id = str(message.author.id)
            if user_id not in settings.dm_allowed_user_ids_list:
                logger.info(f"Blocked DM from user {user_id} (not in allowlist)")
                embed = discord.Embed(
                    title="🚫 Direct Messages Disabled",
                    description=(
                        "For privacy reasons, I do not accept Direct Messages.\n\n"
                        "This ensures all interactions happen in visible server contexts "
                        "and prevents accidental sharing of sensitive information.\n\n"
                        "Please interact with me in a server channel instead."
                    ),
                    color=discord.Color.red()
                )
                await message.channel.send(embed=embed)
                return

        if is_dm or is_mentioned:
            # Typing indicator delayed to mimic natural reading time
            processing_start = time.time()
            try:
                    # Get the character
                    character = character_manager.get_character(self.character_name)
                    
                    if not character:
                        logger.error(f"Character '{self.character_name}' not loaded.")
                        await message.channel.send("Error: Character not loaded.")
                        return

                    # 0. Session Management
                    user_id = str(message.author.id)
                    session_id = await session_manager.get_active_session(user_id, self.character_name)
                    if not session_id:
                        session_id = await session_manager.create_session(user_id, self.character_name)

                    # Clean the message (remove mention)
                    user_message = message.content.replace(f"<@{self.user.id}>", "").strip()
                    
                    # Append sticker text if present
                    if sticker_text:
                        user_message += sticker_text
                    
                    # Early validation: Check if message is empty after cleaning
                    # Allow empty messages if they have attachments, replies, or forwards
                    has_forward = hasattr(message, 'snapshots') and message.snapshots
                    if not user_message and not message.attachments and not message.reference and not has_forward:
                        # Only send "I didn't catch that" if it's a DM or explicit mention
                        # If it's just a random empty message in a channel (rare but possible via bots/glitches), ignore it
                        if is_dm or is_mentioned:
                            await message.channel.send("I didn't catch that. Could you say that again?")
                        return
                    
                    # Check for Forced Reflective Mode
                    force_reflective = False
                    if user_message.startswith("!reflect"):
                        if settings.ENABLE_REFLECTIVE_MODE:
                            cleaned_content = user_message.replace("!reflect", "", 1).strip()
                            
                            # Edge Case: User typed "!reflect" but no message and no reply
                            if not cleaned_content and not message.reference:
                                await message.channel.send("ℹ️ Usage: `!reflect <your question>` or reply to a message with `!reflect`.")
                                return
                                
                            user_message = cleaned_content
                            force_reflective = True
                            logger.info(f"User {user_id} forced Reflective Mode")
                        else:
                            await message.channel.send("⚠️ Reflective Mode is currently disabled in settings.")
                            return
                    
                    # Early validation: Check message length (Discord limit)
                    if user_message:
                        try:
                            validator.validate_for_discord(user_message)
                        except ValidationError as e:
                            await message.channel.send(e.user_message)
                            return

                    # Capture raw message for fact extraction (before context injection)
                    # This prevents the bot from extracting facts from replied-to messages or forwarded content
                    raw_user_message = user_message

                    # Initialize attachment containers
                    image_urls: List[str] = []
                    processed_files: List[str] = []

                    # Handle Replies (Context Injection)
                    if message.reference:
                        try:
                            ref_msg = None
                            if message.reference.resolved and isinstance(message.reference.resolved, discord.Message):
                                ref_msg = message.reference.resolved
                            elif message.reference.message_id:
                                try:
                                    ref_msg = await message.channel.fetch_message(message.reference.message_id)
                                except:
                                    pass # Message might be deleted or inaccessible

                            if ref_msg:
                                # 1. Text & Sticker Context
                                content = ref_msg.content or ""
                                
                                # Handle Stickers in reply
                                if ref_msg.stickers:
                                    sticker_names = [s.name for s in ref_msg.stickers]
                                    content += f"\n[Sent Sticker(s): {', '.join(sticker_names)}]"

                                if content:
                                    ref_text = smart_truncate(content, 500)
                                        
                                    ref_author = ref_msg.author.display_name
                                    user_message = f"[Replying to {ref_author}: \"{ref_text}\"]\n{user_message}"
                                    logger.info(f"Injected reply context: {user_message}")
                                
                                # 2. Attachments (Images & Documents)
                                if ref_msg.attachments:
                                    ref_images, ref_texts = await self._process_attachments(
                                        attachments=ref_msg.attachments,
                                        channel=message.channel,
                                        user_id=user_id,
                                        silent=True,
                                        trigger_vision=True
                                    )
                                    image_urls.extend(ref_images)
                                    processed_files.extend(ref_texts)

                        except Exception as e:
                            logger.warning(f"Failed to resolve reply reference: {e}")

                    # Handle Forwarded Messages (Context Injection)
                    if hasattr(message, 'snapshots') and message.snapshots:
                        try:
                            for snapshot in message.snapshots:
                                # 1. Text Context
                                fwd_content = snapshot.content or ""
                                
                                # Handle Stickers in forward
                                if snapshot.stickers:
                                    sticker_names = [s.name for s in snapshot.stickers]
                                    fwd_content += f"\n[Forwarded Sticker(s): {', '.join(sticker_names)}]"

                                if fwd_content:
                                    fwd_text = smart_truncate(fwd_content, 500)
                                    
                                    user_message = f"[Forwarded Message: \"{fwd_text}\"]\n{user_message}"
                                    logger.info(f"Injected forwarded context: {user_message}")
                                
                                # 2. Attachments
                                if snapshot.attachments:
                                    # Note: We enable trigger_vision=True because users often forward images to ask about them
                                    fwd_images, fwd_texts = await self._process_attachments(
                                        attachments=snapshot.attachments,
                                        channel=message.channel,
                                        user_id=user_id,
                                        silent=True,
                                        trigger_vision=True
                                    )
                                    image_urls.extend(fwd_images)
                                    processed_files.extend(fwd_texts)
                        except Exception as e:
                            logger.warning(f"Failed to process forwarded message: {e}")

                    channel_id = str(message.channel.id)
                    
                    # Check for attachments in CURRENT message
                    if message.attachments:
                        curr_images, curr_texts = await self._process_attachments(
                            attachments=message.attachments,
                            channel=message.channel,
                            user_id=user_id,
                            silent=False,
                            trigger_vision=True
                        )
                        image_urls.extend(curr_images)
                        processed_files.extend(curr_texts)
                    
                    # Create document context from processed files
                    doc_context = DocumentContext.from_processed_files(processed_files)
                    
                    # Validate image URLs early
                    if image_urls:
                        valid_urls, invalid_urls = validator.validate_image_urls(image_urls)
                        if invalid_urls:
                            logger.warning(f"Removed {len(invalid_urls)} invalid image URLs")
                        image_urls = valid_urls if valid_urls else None
                    
                    # 1. Retrieve Context (RAG & History) BEFORE saving current message
                    # This prevents "Echo Chamber" (finding current msg in vector search)
                    # and "Double Speak" (finding current msg in chat history)
                    
                    # Parallel Context Retrieval
                    async def get_memories():
                        try:
                            mems = await memory_manager.search_memories(user_message, user_id)
                            if mems:
                                # Format with relative time AND absolute date for clarity
                                def format_mem(m):
                                    rel = m.get('relative_time', 'unknown time')
                                    ts = m.get('timestamp', '')
                                    date_str = ts.split('T')[0] if ts else 'unknown date'
                                    return f"- {m['content']} ({rel}, {date_str})"
                                
                                fmt = "\n".join([format_mem(m) for m in mems])
                            else:
                                fmt = "No relevant memories found."
                            return mems, fmt
                        except Exception as e:
                            logger.error(f"Failed to search memories: {e}")
                            return [], "No relevant memories found."

                    async def get_history():
                        try:
                            return await memory_manager.get_recent_history(user_id, character.name, channel_id=channel_id)
                        except Exception as e:
                            logger.error(f"Failed to retrieve chat history: {e}")
                            return []

                    async def get_knowledge():
                        try:
                            facts = await knowledge_manager.get_user_knowledge(user_id)
                            # Fallback: If name is not in knowledge graph, use Discord display name
                            if "name" not in facts.lower():
                                display_name = message.author.display_name
                                facts += f"\n- User's Discord Display Name: {display_name}"
                            return facts
                        except Exception as e:
                            logger.error(f"Failed to retrieve knowledge facts: {e}")
                            return ""

                    async def get_summaries():
                        try:
                            sums = await memory_manager.search_summaries(user_message, user_id, limit=3)
                            if sums:
                                return "\n".join([f"- {s['content']} (Meaningfulness: {s['meaningfulness']}, {s.get('relative_time', 'unknown time')})" for s in sums])
                            return ""
                        except Exception as e:
                            logger.error(f"Failed to retrieve summaries: {e}")
                            return ""

                    async def get_universe_context():
                        try:
                            from src_v2.universe.context_builder import universe_context_builder
                            guild_id = str(message.guild.id) if message.guild else None
                            channel_id = str(message.channel.id)
                            char_name = settings.DISCORD_BOT_NAME
                            return await universe_context_builder.build_context(user_id, guild_id, channel_id, char_name)
                        except Exception as e:
                            logger.error(f"Failed to retrieve universe context: {e}")
                            return "Location: Unknown"

                    async def get_channel_context():
                        """Fetch recent channel messages for multi-bot awareness."""
                        if is_dm or not message.guild:
                            return ""
                        try:
                            # Fetch last 10 messages from Discord API (includes bot messages)
                            recent_msgs = []
                            async for msg in message.channel.history(limit=10, before=message):
                                # Skip the current message and empty messages
                                if msg.id == message.id or not msg.content:
                                    continue
                                
                                author_name = msg.author.display_name
                                is_bot = msg.author.bot
                                
                                content = smart_truncate(msg.content, 300)
                                
                                # Format: [Author (Bot)]: content or [Author]: content
                                if is_bot:
                                    recent_msgs.append(f"[{author_name} (Bot)]: {content}")
                                else:
                                    recent_msgs.append(f"[{author_name}]: {content}")
                            
                            if not recent_msgs:
                                return ""
                            
                            # Reverse to chronological order
                            recent_msgs.reverse()
                            return "\n".join(recent_msgs)
                        except Exception as e:
                            logger.debug(f"Failed to fetch channel context: {e}")
                            return ""

                    # Execute all context retrieval tasks in parallel
                    (memories, formatted_memories), chat_history, knowledge_facts, past_summaries, universe_context, channel_context = await asyncio.gather(
                        get_memories(),
                        get_history(),
                        get_knowledge(),
                        get_summaries(),
                        get_universe_context(),
                        get_channel_context()
                    )

                    # 2. Save User Message & Extract Knowledge
                    try:
                        # Save to memory with full document content for RAG retrieval
                        memory_content = doc_context.format_for_memory(user_message)
                        metadata = doc_context.get_memory_metadata()

                        await memory_manager.add_message(
                            user_id, 
                            character.name, 
                            'human', 
                            memory_content, 
                            channel_id=channel_id, 
                            message_id=str(message.id),
                            user_name=message.author.display_name,
                            metadata=metadata
                        )
                        
                        # Log Message Event to InfluxDB
                        if db_manager.influxdb_write_api:
                            point = Point("message_event") \
                                .tag("user_id", user_id) \
                                .tag("bot_name", self.character_name) \
                                .tag("channel_type", "dm" if is_dm else "guild") \
                                .field("length", len(user_message)) \
                                .time(datetime.utcnow())
                            db_manager.influxdb_write_api.write(
                                bucket=settings.INFLUXDB_BUCKET,
                                org=settings.INFLUXDB_ORG,
                                record=point
                            )

                    except Exception as e:
                        logger.error(f"Failed to save user message to memory: {e}")

                    # Fire-and-forget knowledge extraction via background worker
                    # (offloaded from response pipeline for lower latency)
                    if settings.ENABLE_RUNTIME_FACT_EXTRACTION:
                        try:
                            await task_queue.enqueue_knowledge_extraction(
                                user_id=user_id,
                                message=raw_user_message,
                                character_name=self.character_name
                            )
                        except Exception as e:
                            logger.error(f"Failed to enqueue knowledge extraction: {e}")

                    # Fire-and-forget Preference Extraction
                    if settings.ENABLE_PREFERENCE_EXTRACTION:
                        async def process_preferences(uid, msg, char_name):
                            prefs = await preference_extractor.extract_preferences(msg)
                            if prefs:
                                logger.info(f"Detected preferences for {uid}: {prefs}")
                                for key, value in prefs.items():
                                    await trust_manager.update_preference(uid, char_name, key, value)
                                    
                        self.loop.create_task(process_preferences(user_id, raw_user_message, self.character_name))

                    # 2.5 Check for Summarization
                    if session_id:
                        self.loop.create_task(self._check_and_summarize(session_id, user_id))

                    # 3. Generate response
                    now = datetime.now()
                    
                    # Determine channel context
                    channel_name = "DM"
                    parent_channel_name = None
                    is_thread = False
                    
                    if isinstance(message.channel, discord.Thread):
                        is_thread = True
                        channel_name = message.channel.name
                        if message.channel.parent:
                            parent_channel_name = message.channel.parent.name
                    elif hasattr(message.channel, 'name'):
                        channel_name = message.channel.name

                    context_vars = {
                        "user_name": message.author.display_name,
                        "current_datetime": now.strftime("%A, %B %d, %Y at %H:%M"),
                        "universe_context": universe_context,
                        "recent_memories": formatted_memories,
                        "knowledge_context": knowledge_facts,
                        "past_summaries": past_summaries,
                        "channel_context": channel_context,  # Multi-bot awareness
                        "guild_id": str(message.guild.id) if message.guild else None,
                        "channel_name": channel_name,
                        "parent_channel_name": parent_channel_name,
                        "is_thread": is_thread,
                        "has_documents": doc_context.has_documents
                    }
                    
                    # Append document preview to user message for LLM
                    if doc_context.has_documents:
                        user_message += doc_context.format_for_llm()

                    # Track timing for stats footer
                    start_time = time.time()
                    
                    # Prepare callback for Reflective Mode
                    status_message: Optional[discord.Message] = None
                    status_header: str = "🧠 **Reflective Mode Activated**"
                    status_body: str = ""
                    status_lock = asyncio.Lock()
                    
                    async def reflective_callback(text: str):
                        nonlocal status_message, status_header, status_body
                        async with status_lock:
                            # Check for header update
                            if text.startswith("HEADER:"):
                                status_header = text.replace("HEADER:", "").strip()
                                # If we have a message, update it immediately to reflect header change
                                if status_message:
                                    full_content = f"{status_header}\n{status_body}"
                                    if len(full_content) > 1900:
                                        full_content = full_content[:1900] + "\n... (truncated)"
                                    try:
                                        await status_message.edit(content=full_content)
                                    except Exception as e:
                                        logger.error(f"Failed to update status header: {e}")
                                return

                            # Clean up text slightly
                            clean_text = text.strip()
                            if not clean_text:
                                return
                                
                            # Format: Quote block for thoughts
                            formatted_text = "\n".join([f"> {line}" for line in clean_text.split("\n")])
                            
                            status_body += f"\n{formatted_text}"
                            
                            # Construct full content
                            full_content = f"{status_header}\n{status_body}"
                            
                            # Truncate if too long for Discord (2000 chars)
                            if len(full_content) > 1900:
                                full_content = full_content[:1900] + "\n... (truncated)"
                            
                            try:
                                if status_message:
                                    await status_message.edit(content=full_content)
                                else:
                                    status_message = await message.channel.send(full_content)
                            except Exception as e:
                                logger.error(f"Failed to update reflective status: {e}")

                    # Streaming Response Logic
                    full_response_text = ""
                    active_message: Optional[discord.Message] = None
                    last_update_time = 0
                    update_interval = 0.7  # Seconds between edits to avoid rate limits
                    
                    # Start typing indicator only when generation begins
                    # Humanize: Wait for "reading" time (approx 0.05s per char, capped at 4s)
                    reading_delay = min(len(user_message) * settings.TYPING_SPEED_CHAR_PER_SEC, settings.TYPING_MAX_DELAY_SECONDS)
                    reading_delay += random.uniform(0, 1.0) # Add jitter
                    
                    elapsed = time.time() - processing_start
                    if elapsed < reading_delay:
                        await asyncio.sleep(reading_delay - elapsed)
                        
                    async with message.channel.typing():
                        async for chunk in self.agent_engine.generate_response_stream(
                            character=character,
                            user_message=user_message,
                            chat_history=chat_history,
                            context_variables=context_vars,
                            user_id=user_id,
                            image_urls=image_urls,
                            callback=reflective_callback,
                            force_reflective=force_reflective
                        ):
                            # Safety Net: Strip timestamp if it leaks into the stream
                            # Regex matches [12 mins ago] or [just now] at start of chunk/string
                            chunk = re.sub(r'^\[.*?ago\]\s*', '', chunk)
                            chunk = re.sub(r'^\[just now\]\s*', '', chunk)
                            
                            full_response_text += chunk
                            
                            # Rate limit updates
                            now = time.time()
                            if now - last_update_time > update_interval:
                                # Only stream if length is safe
                                if len(full_response_text) < 1950:
                                    try:
                                        if not active_message:
                                            active_message = await message.channel.send(full_response_text)
                                        else:
                                            await active_message.edit(content=full_response_text)
                                    except Exception as e:
                                        logger.warning(f"Failed to stream update: {e}")
                                last_update_time = now
                    
                    response = full_response_text
                    
                    processing_time_ms: float = (time.time() - start_time) * 1000
                    
                    # 3.5 Generate Stats Footer (if enabled for user)
                    from src_v2.utils.stats_footer import stats_footer
                    should_show_footer = await stats_footer.is_enabled_for_user(user_id, self.character_name)
                    footer_text = ""
                    
                    if should_show_footer:
                        footer_text = await stats_footer.generate_footer(
                            user_id=user_id,
                            character_name=self.character_name,
                            memory_count=len(memories) if memories else 0,
                            processing_time_ms=processing_time_ms
                        )
                    
                    # 4. Save AI Response
                    try:
                        # Append footer if enabled
                        final_text = response
                        if footer_text:
                            final_text = f"{response}\n\n{footer_text}"
                        
                        # Extract any generated images from the response
                        cleaned_text, image_files = await extract_pending_images(final_text, user_id)
                        
                        # Split response into chunks if it's too long
                        message_chunks = self._chunk_message(cleaned_text)
                        
                        # Handle the first chunk (Edit existing or Send new)
                        sent_messages = []
                        
                        if active_message:
                            # We already have a streaming message
                            # Just edit the text (files can't be attached to edited messages in discord.py)
                            await active_message.edit(content=message_chunks[0])
                            sent_messages.append(active_message)
                            
                            # Send remaining chunks
                            for chunk in message_chunks[1:]:
                                sent_msg = await message.channel.send(chunk)
                                sent_messages.append(sent_msg)
                            
                            # Send images as a separate message if present
                            if image_files:
                                try:
                                    image_msg = await message.channel.send(files=image_files)
                                    sent_messages.append(image_msg)
                                except Exception as e:
                                    logger.error(f"Failed to send image message: {e}")
                        else:
                            # No streaming happened, send all chunks
                            # Attach images to the first message only
                            for i, chunk in enumerate(message_chunks):
                                if i == 0 and image_files:
                                    try:
                                        sent_msg = await message.channel.send(content=chunk, files=image_files)
                                    except discord.Forbidden as e:
                                        logger.error(f"Permission denied when sending images: {e}")
                                        sent_msg = await message.channel.send(content=chunk)
                                    except Exception as e:
                                        logger.error(f"Failed to send message with images: {e}")
                                        sent_msg = await message.channel.send(content=chunk)
                                else:
                                    sent_msg = await message.channel.send(chunk)
                                sent_messages.append(sent_msg)
                        
                        # Save the full response to memory (not chunked)
                        # Use the last message ID as the primary reference
                        if sent_messages:
                            await memory_manager.add_message(
                                user_id, 
                                character.name, 
                                'ai', 
                                response, 
                                channel_id=channel_id, 
                                message_id=str(sent_messages[-1].id)
                            )
                        
                        # 4.5 Goal Analysis (Fire-and-forget)
                        # Analyze the interaction (User Message + AI Response)
                        interaction_text = f"User: {user_message}\nAI: {response}"
                        self.loop.create_task(
                            goal_analyzer.check_goals(user_id, character.name, interaction_text)
                        )
                        
                        # 4.6 Trust Update (Engagement Reward)
                        # Small trust increase for every positive interaction
                        async def handle_trust_update():
                            try:
                                milestone = await trust_manager.update_trust(user_id, character.name, 1)
                                if milestone:
                                    await message.channel.send(milestone)
                            except Exception as e:
                                logger.error(f"Failed to handle trust update: {e}")

                        self.loop.create_task(handle_trust_update())
                        
                        # 4.7 Universe Relationship Update (Phase B8)
                        # Build familiarity between character and user after each conversation
                        try:
                            guild_id = str(message.guild.id) if message.guild else None
                            await task_queue.enqueue_relationship_update(
                                character_name=self.character_name,
                                user_id=user_id,
                                guild_id=guild_id,
                                interaction_quality=1
                            )
                        except Exception as e:
                            logger.debug(f"Failed to enqueue relationship update: {e}")
                        
                        # 5. Voice Playback (use full response, not chunked)
                        if message.guild and message.guild.voice_client:
                            vc = message.guild.voice_client
                            # Check if voice client is connected
                            if hasattr(vc, 'is_connected') and vc.is_connected():
                                logger.info(f"Voice connected in {message.guild.name}. Attempting to speak response...")
                                try:
                                    await play_text(vc, response)  # type: ignore[arg-type]
                                except Exception as e:
                                    logger.error(f"Failed to play voice: {e}")
                            else:
                                logger.warning("Voice client exists but is not connected.")
                        else:
                            logger.debug("No active voice client found for this guild.")
                            
                    except Exception as e:
                        logger.error(f"Failed to send/save AI response: {e}")

            except Exception as e:
                logger.exception(f"Critical error in on_message: {e}")
                # Use character-specific error message if available
                error_msg = "I'm having a bit of trouble processing that right now. Please try again later."
                try:
                    char = character_manager.get_character(self.character_name)
                    if char and char.error_messages:
                        error_msg = random.choice(char.error_messages)
                except Exception:
                    pass
                await message.channel.send(error_msg)

        # Channel Lurking: Respond to relevant messages without being mentioned
        elif settings.ENABLE_CHANNEL_LURKING and self.lurk_detector and message.guild:
            await self._handle_lurk_response(message, sticker_text)

    async def _handle_lurk_response(self, message: discord.Message, sticker_text: str = "") -> None:
        """Handle potential lurk response for a channel message.
        
        This is called for guild messages where the bot was NOT mentioned.
        We analyze the message for relevance and decide whether to jump in.
        
        Args:
            message: Discord message object
            sticker_text: Processed sticker text if any
        """
        if not self.lurk_detector:
            return
            
        channel_id = str(message.channel.id)
        user_id = str(message.author.id)
        
        # Check if lurking is enabled for this channel
        channel_enabled = await self.lurk_detector.is_channel_enabled(channel_id)
        if not channel_enabled:
            return
        
        # Combine message content with sticker text
        message_content = message.content
        if sticker_text:
            message_content += sticker_text
            
        if not message_content.strip():
            return
            
        try:
            # Get channel-specific threshold
            channel_threshold = await self.lurk_detector.get_channel_threshold(channel_id)
            
            # Analyze message for relevance
            lurk_result = await self.lurk_detector.analyze(
                message=message_content,
                channel_id=channel_id,
                user_id=user_id,
                author_is_bot=message.author.bot,
                has_mentions=bool(message.mentions),
                channel_lurk_enabled=True,  # Already checked above
                custom_threshold=channel_threshold
            )
            
            if not lurk_result.should_respond:
                logger.debug(f"Lurk: Not responding to message (score={lurk_result.confidence:.2f}, reason={lurk_result.trigger_reason})")
                return
                
            logger.info(f"Lurk: Responding to message (score={lurk_result.confidence:.2f}, trigger={lurk_result.trigger_reason})")
            
            # Typing indicator delayed
            if True:
                # Get the character
                character = character_manager.get_character(self.character_name)
                if not character:
                    logger.error(f"Character '{self.character_name}' not loaded for lurk response.")
                    return
                    
                # Session management
                session_id = await session_manager.get_active_session(user_id, self.character_name)
                if not session_id:
                    session_id = await session_manager.create_session(user_id, self.character_name)
                
                # Context retrieval (simplified for lurk - less aggressive)
                async def get_memories():
                    try:
                        mems = await memory_manager.search_memories(message_content, user_id)
                        if mems:
                            return "\n".join([f"- {m['content']} ({m.get('relative_time', 'unknown time')})" for m in mems[:3]])
                        return "No relevant memories found."
                    except Exception as e:
                        logger.error(f"Failed to search memories for lurk: {e}")
                        return "No relevant memories found."
                        
                async def get_knowledge():
                    try:
                        facts = await knowledge_manager.get_user_knowledge(user_id)
                        if "name" not in facts.lower():
                            facts += f"\n- User's Discord Display Name: {message.author.display_name}"
                        return facts
                    except Exception as e:
                        logger.error(f"Failed to retrieve knowledge for lurk: {e}")
                        return ""
                        
                async def get_history():
                    try:
                        return await memory_manager.get_recent_history(user_id, character.name, channel_id=channel_id, limit=5)
                    except Exception as e:
                        logger.error(f"Failed to retrieve history for lurk: {e}")
                        return []
                        
                formatted_memories, knowledge_facts, chat_history = await asyncio.gather(
                    get_memories(),
                    get_knowledge(),
                    get_history()
                )
                
                # Build context for lurk response
                # Add special lurk instruction to guide the response style
                lurk_instruction = (
                    "\n\n[LURK MODE]: You're jumping into an ongoing conversation organically. "
                    "The user did NOT mention you directly - you noticed something relevant to your expertise/interests. "
                    "Be natural, helpful, and non-intrusive. Don't over-explain your presence. "
                    f"You're responding because: {lurk_result.trigger_reason}."
                )
                
                context_vars = {
                    "user_name": message.author.display_name,
                    "recent_memories": formatted_memories,
                    "knowledge_facts": knowledge_facts,
                    "lurk_instruction": lurk_instruction,
                    "guild_id": str(message.guild.id) if message.guild else None
                }
                
                # Generate response (use simpler path, no reflective mode for lurk)
                start_time = time.time()
                
                # Humanize Lurk: Wait for "reading" time
                reading_delay = min(len(message_content) * 0.05, 3.0)
                reading_delay += random.uniform(0, 1.0)
                await asyncio.sleep(reading_delay)
                
                async with message.channel.typing():
                    response = await self.agent_engine.generate_response(
                        character=character,
                        user_message=message_content + lurk_instruction,
                        chat_history=chat_history,
                        context_variables=context_vars,
                        user_id=user_id
                    )
                
                processing_time_ms = (time.time() - start_time) * 1000
                
                # Send response (chunked if needed)
                message_chunks = self._chunk_message(response)
                sent_messages = []
                for chunk in message_chunks:
                    sent_msg = await message.channel.send(chunk)
                    sent_messages.append(sent_msg)
                    
                # Record the lurk response
                await self.lurk_detector.record_response(
                    channel_id=channel_id,
                    user_id=user_id,
                    message_id=str(message.id),
                    confidence=lurk_result.confidence,
                    trigger_type=lurk_result.trigger_reason
                )
                
                # Save messages to memory
                await memory_manager.add_message(
                    user_id,
                    character.name,
                    'human',
                    message_content,
                    channel_id=channel_id,
                    message_id=str(message.id),
                    user_name=message.author.display_name
                )
                
                if sent_messages:
                    await memory_manager.add_message(
                        user_id,
                        character.name,
                        'ai',
                        response,
                        channel_id=channel_id,
                        message_id=str(sent_messages[-1].id)
                    )
                    
                # Trust update (smaller for lurk responses)
                async def handle_lurk_trust():
                    try:
                        # Use integer 1 for trust update to avoid type conflicts in DBs
                        await trust_manager.update_trust(user_id, character.name, 1)
                    except Exception as e:
                        logger.error(f"Failed to update trust for lurk: {e}")
                        
                self.loop.create_task(handle_lurk_trust())
                
                logger.info(f"Lurk response sent in {processing_time_ms:.0f}ms (confidence={lurk_result.confidence:.2f})")
                
        except Exception as e:
            logger.error(f"Error in lurk handler: {e}")

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """
        Global error handler for commands.
        """
        # Ignore CommandNotFound errors (e.g. !reflect which is handled manually)
        if isinstance(error, commands.CommandNotFound):
            return
            
        # Log other errors
        logger.error(f"Ignoring exception in command {ctx.command}: {error}")

    async def on_reaction_add(self, reaction: discord.Reaction, user: Union[discord.Member, discord.User]) -> None:
        """
        Handles reactions added to messages.
        Used for user feedback (e.g., thumbs up/down) to adjust memory importance.
        
        Args:
            reaction: Discord reaction object
            user: User or Member who added the reaction
        """
        if user.bot:
            return

        # Only care if the reaction is on a message sent by THIS bot
        if reaction.message.author.id != self.user.id:
            return

        try:
            message_id: str = str(reaction.message.id)
            user_id: str = str(user.id)
            emoji: str = str(reaction.emoji)
            message_length: int = len(reaction.message.content)
            
            logger.info(f"User {user.name} reacted with {emoji} to message {message_id}")

            # Log to InfluxDB via FeedbackAnalyzer
            await feedback_analyzer.log_reaction_to_influx(
                user_id=user_id,
                message_id=message_id,
                reaction=emoji,
                bot_name=self.character_name,
                message_length=message_length,
                action="add"
            )
            
            # Get feedback score and adjust memory importance
            feedback = await feedback_analyzer.get_feedback_score(message_id, user_id)
            if feedback:
                # Adjust memory importance in Qdrant
                collection_name = f"whisperengine_memory_{self.character_name}"
                
                # Use weighted score of the specific emoji added for more granular control
                emoji_weight = emoji_taxonomy.get_score(emoji)
                score_delta = emoji_weight * 0.2  # Scale to ±0.2 adjustment (Heart=0.24, ThumbsUp=0.2)
                
                await feedback_analyzer.adjust_memory_score_by_message_id(
                    message_id=message_id,
                    collection_name=collection_name,
                    score_delta=score_delta
                )
                
                # Update Trust based on feedback
                # Positive feedback increases trust, negative decreases
                # Use weighted score: Heart (+1.2) -> +6 trust, ThumbsUp (+1.0) -> +5 trust
                if emoji_weight != 0:
                    trust_delta = int(emoji_weight * 5)
                else:
                    trust_delta = 0  # Neutral/unrecognized reactions
                
                async def handle_reaction_trust():
                    try:
                        milestone = await trust_manager.update_trust(user_id, self.character_name, trust_delta)
                        if milestone:
                            await reaction.message.channel.send(milestone)
                    except Exception as e:
                        logger.error(f"Failed to handle reaction trust update: {e}")

                self.loop.create_task(handle_reaction_trust())
                
                logger.info(f"Feedback score for message: {feedback['score']} (adjusted memory importance by {score_delta:.2f})")
                
                # Trigger Insight Agent analysis after positive feedback
                if emoji_weight > 0:
                    try:
                        await task_queue.enqueue_insight_analysis(
                            user_id=user_id,
                            character_name=self.character_name,
                            trigger="feedback",
                            priority=3  # Higher priority for feedback triggers
                        )
                    except Exception as insight_err:
                        logger.debug(f"Could not enqueue insight analysis: {insight_err}")

        except Exception as e:
            logger.error(f"Error handling reaction add: {e}")

    async def on_reaction_remove(self, reaction: discord.Reaction, user: Union[discord.Member, discord.User]) -> None:
        """
        Handles reactions removed from messages.
        Updates feedback score and memory importance accordingly.
        
        Args:
            reaction: Discord reaction object
            user: User or Member who removed the reaction
        """
        if user.bot:
            return

        # Only care if the reaction is on a message sent by THIS bot
        if reaction.message.author.id != self.user.id:
            return

        try:
            message_id: str = str(reaction.message.id)
            user_id: str = str(user.id)
            emoji: str = str(reaction.emoji)
            message_length: int = len(reaction.message.content)
            
            logger.info(f"User {user.name} removed reaction {emoji} from message {message_id}")

            # Log to InfluxDB via FeedbackAnalyzer
            await feedback_analyzer.log_reaction_to_influx(
                user_id=user_id,
                message_id=message_id,
                reaction=emoji,
                bot_name=self.character_name,
                message_length=message_length,
                action="remove"
            )
            
            # Get feedback score and adjust memory importance
            feedback = await feedback_analyzer.get_feedback_score(message_id, user_id)
            if feedback:
                # Adjust memory importance in Qdrant
                # Since we removed a reaction, we need to recalculate the impact.
                # We apply the INVERSE of what adding this reaction would do.
                
                emoji_weight = emoji_taxonomy.get_score(emoji)
                
                # Inverse of add: -1 * weight * 0.2
                score_delta = -1 * emoji_weight * 0.2
                
                # Trust delta for removal is smaller than addition to avoid "gaming"
                # But we still use the weight to determine direction
                trust_delta = 0
                if emoji_weight > 0:
                    trust_delta = -1   # Minimal penalty for removing positive reaction
                elif emoji_weight < 0:
                    trust_delta = 1    # Minimal bonus for removing negative reaction
                
                if score_delta != 0:
                    collection_name = f"whisperengine_memory_{self.character_name}"
                    await feedback_analyzer.adjust_memory_score_by_message_id(
                        message_id=message_id,
                        collection_name=collection_name,
                        score_delta=score_delta
                    )
                    
                    async def handle_reaction_remove_trust():
                        try:
                            milestone = await trust_manager.update_trust(user_id, self.character_name, trust_delta)
                            if milestone:
                                await reaction.message.channel.send(milestone)
                        except Exception as e:
                            logger.error(f"Failed to handle reaction remove trust update: {e}")

                    self.loop.create_task(handle_reaction_remove_trust())
                    
                    logger.info(f"Reaction removed. Adjusted memory importance by {score_delta}")

        except Exception as e:
            logger.error(f"Error handling reaction remove: {e}")

    async def _check_and_summarize(self, session_id: str, user_id: str):
        """
        Checks if summarization is needed and enqueues it to background worker.
        """
        try:
            # 1. Get session start time
            start_time = await session_manager.get_session_start_time(session_id)
            if not start_time:
                return

            # 2. Count messages
            message_count = await memory_manager.count_messages_since(user_id, self.character_name, start_time)
            
            # 3. Check threshold (e.g., 20 messages)
            SUMMARY_THRESHOLD = 20
            if message_count >= SUMMARY_THRESHOLD:
                logger.info(f"Session {session_id} reached {message_count} messages. Enqueueing summarization.")
                
                # Fetch messages
                messages = await memory_manager.get_recent_history(user_id, self.character_name, limit=message_count)
                # Convert to dict format expected by SummaryManager
                msg_dicts = [{"role": "human" if isinstance(m, HumanMessage) else "ai", "content": m.content} for m in messages]
                
                # Enqueue summarization to background worker
                try:
                    await task_queue.enqueue_summarization(
                        user_id=user_id,
                        character_name=self.character_name,
                        session_id=session_id,
                        messages=msg_dicts
                    )
                except Exception as e:
                    logger.error(f"Failed to enqueue summarization: {e}")
                    return
                
                # Enqueue reflection (runs after summarization completes)
                try:
                    await task_queue.enqueue_reflection(
                        user_id=user_id,
                        character_name=self.character_name
                    )
                except Exception as e:
                    logger.debug(f"Could not enqueue reflection: {e}")
                    
                # Enqueue Insight Agent analysis
                try:
                    await task_queue.enqueue_insight_analysis(
                        user_id=user_id,
                        character_name=self.character_name,
                        trigger="session_end",
                        priority=5
                    )
                except Exception as e:
                    logger.debug(f"Could not enqueue insight analysis: {e}")
                    
        except Exception as e:
            logger.error(f"Error in _check_and_summarize: {e}")

    async def on_disconnect(self):
        logger.warning("Bot disconnected from Discord! Attempting to reconnect...")

    async def on_resumed(self):
        logger.info("Bot session resumed successfully.")

    async def on_error(self, event_method: str, *args: Any, **kwargs: Any) -> None:
        """Handles errors that occur during event processing.
        
        Args:
            event_method: Name of the event method that caused the error
            *args: Unused positional arguments
            **kwargs: Unused keyword arguments
        """
        logger.exception(f"Error in event {event_method}")

    async def _process_attachments(
        self, 
        attachments: List[discord.Attachment], 
        channel: Any, 
        user_id: str, 
        silent: bool = False,
        trigger_vision: bool = False
    ) -> Tuple[List[str], List[str]]:
        """
        Helper to process a list of attachments (images & documents).
        Returns (image_urls, processed_text_content).
        """
        image_urls = []
        processed_texts = []
        
        MAX_FILES = 10
        MAX_SIZE_MB = 25
        MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024
        
        # Early Notification for File Count
        if len(attachments) > MAX_FILES and not silent:
            await channel.send(f"⚠️ Too many files! I can only process the first {MAX_FILES} attachments.")

        # Early Notification for File Sizes
        oversized_files = [a.filename for a in attachments if a.size > MAX_SIZE_BYTES]
        if oversized_files and not silent:
            file_list = ", ".join(oversized_files)
            await channel.send(f"⚠️ Skipping oversized files (> {MAX_SIZE_MB}MB): {file_list}")

        file_count = 0
        
        for attachment in attachments:
            # 1. Global Limit Checks (Count & Size)
            if file_count >= MAX_FILES:
                logger.warning(f"Skipping attachment {attachment.filename}: Max file limit reached.")
                continue
            
            if attachment.size > MAX_SIZE_BYTES:
                if silent:
                    logger.info(f"Skipping oversized {'image' if self._is_image(attachment) else 'document'}: {attachment.filename} ({attachment.size / 1024 / 1024:.1f}MB)")
                continue # Skip silently as we already warned user upfront

            # 2. Image Handling
            if self._is_image(attachment):
                image_urls.append(attachment.url)
                file_count += 1
                
                if not silent:
                    logger.info(f"Detected image attachment: {attachment.url}")
                else:
                    logger.info(f"Included image from referenced message: {attachment.url}")
                
                if trigger_vision and settings.LLM_SUPPORTS_VISION:
                    asyncio.create_task(
                        vision_manager.analyze_and_store(
                            image_url=attachment.url,
                            user_id=user_id,
                            channel_id=str(channel.id)
                        )
                    )
            
            # 3. Document Handling
            else:
                file_count += 1
                
                if not silent:
                    await channel.send(f"📄 Reading {attachment.filename}...")
                else:
                    logger.info(f"Detected referenced document: {attachment.filename}")
                
                try:
                    extracted_text = await document_processor.process_attachment(attachment.url, attachment.filename)
                    if extracted_text:
                        # No truncation here - we let DocumentContext handle the preview generation
                        # and store the full content in memory for RAG.
                        
                        prefix = "Referenced File" if silent else "File"
                        processed_texts.append(f"--- {prefix}: {attachment.filename} ---\n{extracted_text}")
                        
                        if silent:
                            logger.info(f"Processed referenced document content: {len(extracted_text)} chars")
                        else:
                            logger.info(f"Processed document content: {len(extracted_text)} chars")
                            
                except Exception as e:
                    logger.error(f"Failed to process {attachment.filename}: {e}")
                    if not silent:
                        await channel.send(f"❌ Failed to read {attachment.filename}.")
                        
        return image_urls, processed_texts

# Global bot instance
bot = WhisperBot()
