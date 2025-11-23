from langchain_core.messages import HumanMessage
import discord
import asyncio
from typing import Union, List, Tuple, Any, Optional
from datetime import datetime
from discord.ext import commands
from loguru import logger
from src_v2.config.settings import settings
from src_v2.agents.engine import AgentEngine
from src_v2.core.character import character_manager
from src_v2.memory.manager import memory_manager
from src_v2.memory.session import session_manager
from src_v2.memory.summarizer import SummaryManager
from src_v2.knowledge.manager import knowledge_manager
from src_v2.knowledge.documents import document_processor
from src_v2.voice.player import play_text
from src_v2.core.database import db_manager
from src_v2.evolution.feedback import feedback_analyzer
from src_v2.evolution.goals import goal_analyzer
from src_v2.evolution.trust import trust_manager
from src_v2.evolution.extractor import preference_extractor
from src_v2.intelligence.reflection import reflection_engine
from src_v2.vision.manager import vision_manager
from src_v2.discord.scheduler import ProactiveScheduler
from influxdb_client.client.write.point import Point
from src_v2.utils.validation import ValidationError, validator

class WhisperBot(commands.Bot):
    """Discord bot with AI character personality and memory systems."""
    
    agent_engine: AgentEngine
    summary_manager: SummaryManager
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
        self.summary_manager = SummaryManager()
        self.scheduler = ProactiveScheduler(self)
        
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
            
            await asyncio.sleep(300) # Update every 5 minutes

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

        # Start status update loop
        self.loop.create_task(self.update_status_loop())

    async def on_ready(self) -> None:
        """Called when the bot has successfully connected to Discord."""
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        await self.change_presence(status=discord.Status.online)
        
        # Preload character
        char: Optional[Any] = character_manager.get_character(self.character_name)
        if char:
            logger.info(f"Character '{self.character_name}' loaded successfully.")
        else:
            logger.error(f"Could not load character '{self.character_name}'!")

        logger.info("WhisperEngine is ready and listening.")

    async def on_message(self, message: discord.Message) -> None:
        """Handles incoming Discord messages and generates AI responses.
        
        Args:
            message: Discord message object
        """
        # Ignore messages from self and other bots to prevent loops
        if message.author.bot:
            return

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
                    if message.reference.resolved.author.id == self.user.id:
                        is_mentioned = True
                        logger.info("Detected reply to bot without ping.")
                # Fallback: Fetch message if not resolved
                elif message.reference.message_id:
                    try:
                        ref_msg = await message.channel.fetch_message(message.reference.message_id)
                        if ref_msg.author.id == self.user.id:
                            is_mentioned = True
                            logger.info("Detected reply to bot without ping (fetched).")
                    except:
                        pass
            except Exception as e:
                logger.warning(f"Failed to check reply reference: {e}")
        
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
            async with message.channel.typing():
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
                    try:
                        validator.validate_for_discord(user_message)
                    except ValidationError as e:
                        await message.channel.send(e.user_message)
                        return

                    # Initialize attachment containers
                    image_urls = []
                    file_content = None
                    processed_files = []

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
                                    # Smart Truncation: Keep start and end if too long
                                    if len(content) > 500:
                                        ref_text = content[:225] + " ... [middle truncated] ... " + content[-225:]
                                    else:
                                        ref_text = content
                                        
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
                                    # Smart Truncation
                                    if len(fwd_content) > 500:
                                        fwd_text = fwd_content[:225] + " ... [middle truncated] ... " + fwd_content[-225:]
                                    else:
                                        fwd_text = fwd_content
                                    
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
                        
                        if processed_files:
                            file_content = "\n\n".join(processed_files)
                    
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
                            fmt = "\n".join([f"- {m['content']}" for m in mems]) if mems else "No relevant memories found."
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
                                return "\n".join([f"- {s['content']} (Meaningfulness: {s['meaningfulness']})" for s in sums])
                            return ""
                        except Exception as e:
                            logger.error(f"Failed to retrieve summaries: {e}")
                            return ""

                    # Execute all context retrieval tasks in parallel
                    (memories, formatted_memories), chat_history, knowledge_facts, past_summaries = await asyncio.gather(
                        get_memories(),
                        get_history(),
                        get_knowledge(),
                        get_summaries()
                    )

                    # 2. Save User Message & Extract Knowledge
                    try:
                        await memory_manager.add_message(user_id, character.name, 'human', user_message, channel_id=channel_id, message_id=str(message.id))
                        
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

                    # Store original message for fact extraction (before appending file content)
                    original_message = user_message

                    # Fire-and-forget knowledge extraction (only from user's actual message, not file content)
                    if settings.ENABLE_RUNTIME_FACT_EXTRACTION:
                        try:
                            await knowledge_manager.process_user_message(user_id, original_message)
                        except Exception as e:
                            logger.error(f"Failed to process knowledge extraction: {e}")

                    # Fire-and-forget Preference Extraction
                    if settings.ENABLE_PREFERENCE_EXTRACTION:
                        async def process_preferences(uid, msg, char_name):
                            prefs = await preference_extractor.extract_preferences(msg)
                            if prefs:
                                logger.info(f"Detected preferences for {uid}: {prefs}")
                                for key, value in prefs.items():
                                    await trust_manager.update_preference(uid, char_name, key, value)
                                    
                        self.loop.create_task(process_preferences(user_id, original_message, self.character_name))

                    # 2.5 Check for Summarization
                    if session_id:
                        self.loop.create_task(self._check_and_summarize(session_id, user_id))

                    # Determine Location Context
                    location_context = "Direct Message"
                    if message.guild:
                        if isinstance(message.channel, discord.Thread):
                            parent_name = message.channel.parent.name if message.channel.parent else "unknown"
                            location_context = f"Thread '{message.channel.name}' (in #{parent_name})"
                        else:
                            location_context = f"Channel #{message.channel.name}"

                    # 3. Generate response
                    context_vars = {
                        "user_name": message.author.display_name,
                        "time_of_day": datetime.now().strftime("%H:%M"),
                        "location": location_context,
                        "recent_memories": formatted_memories,
                        "knowledge_context": knowledge_facts,
                        "past_summaries": past_summaries
                    }
                    
                    # Inject file content if present
                    if file_content:
                        context_vars["file_content"] = file_content
                        user_message += f"\n\n[Attached File Content]:\n{file_content}"

                    # Track timing for stats footer
                    import time
                    start_time = time.time()
                    
                    # Prepare callback for Reflective Mode
                    status_message = None
                    status_content = "🧠 **Reflective Mode Activated**\n"
                    
                    async def reflective_callback(text: str):
                        nonlocal status_message, status_content
                        # Clean up text slightly
                        clean_text = text.strip()
                        if not clean_text:
                            return
                            
                        # Format: Quote block for thoughts
                        formatted_text = "\n".join([f"> {line}" for line in clean_text.split("\n")])
                        
                        status_content += f"\n{formatted_text}"
                        
                        # Truncate if too long for Discord (2000 chars)
                        if len(status_content) > 1900:
                            status_content = status_content[:1900] + "\n... (truncated)"
                        
                        try:
                            if status_message:
                                await status_message.edit(content=status_content)
                            else:
                                status_message = await message.channel.send(status_content)
                        except Exception as e:
                            logger.error(f"Failed to update reflective status: {e}")

                    response = await self.agent_engine.generate_response(
                        character=character,
                        user_message=user_message,
                        chat_history=chat_history,
                        context_variables=context_vars,
                        user_id=user_id,
                        image_urls=image_urls,
                        callback=reflective_callback,
                        force_reflective=force_reflective
                    )
                    
                    processing_time_ms = (time.time() - start_time) * 1000
                    
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
                        full_response = response
                        if footer_text:
                            full_response = f"{response}\n\n{footer_text}"
                        
                        # Split response into chunks if it's too long
                        message_chunks = self._chunk_message(full_response)
                        
                        # Send all chunks
                        sent_messages = []
                        for chunk in message_chunks:
                            sent_msg = await message.channel.send(chunk)
                            sent_messages.append(sent_msg)
                        
                        # Save the full response to memory (not chunked)
                        # Use the last message ID as the primary reference
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
                        self.loop.create_task(
                            trust_manager.update_trust(user_id, character.name, 1)
                        )
                        
                        # 5. Voice Playback (use full response, not chunked)
                        if message.guild and message.guild.voice_client:
                            vc = message.guild.voice_client
                            if vc.is_connected():
                                logger.info(f"Voice connected in {message.guild.name}. Attempting to speak response...")
                                try:
                                    await play_text(vc, response)
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
                    await message.channel.send("I'm having a bit of trouble processing that right now. Please try again later.")

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
                score_delta = feedback["score"] * 0.2  # Scale to ±0.2 adjustment
                
                await feedback_analyzer.adjust_memory_score_by_message_id(
                    message_id=message_id,
                    collection_name=collection_name,
                    score_delta=score_delta
                )
                
                # Update Trust based on feedback
                # Positive feedback increases trust significantly
                # Negative feedback decreases trust
                trust_delta = 5 if feedback["score"] > 0 else -5
                self.loop.create_task(
                    trust_manager.update_trust(user_id, self.character_name, trust_delta)
                )
                
                logger.info(f"Feedback score for message: {feedback['score']} (adjusted memory importance)")

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
                # The simplest way is to just use the new score to set a "target" importance,
                # but our system uses deltas. 
                # So we should apply the INVERSE of what adding this reaction would do.
                
                # However, get_feedback_score returns the CURRENT total score.
                # If we just use the current score, we might drift.
                # A better approach for "remove" is to calculate the delta this specific reaction removal caused.
                
                # But since we don't know the exact previous state easily without querying,
                # let's just use the new score to guide the adjustment.
                # Actually, if we removed a positive reaction, score goes down.
                # If we removed a negative reaction, score goes up.
                
                # Let's trust the feedback score from InfluxDB which is now accurate (replayed events).
                # But wait, adjust_memory_score_by_message_id takes a DELTA.
                # If I just pass the new score * 0.2, I am applying the whole score again!
                # That is WRONG.
                
                # Correct logic:
                # If removed reaction was POSITIVE: Delta should be NEGATIVE.
                # If removed reaction was NEGATIVE: Delta should be POSITIVE.
                
                is_positive = emoji in feedback_analyzer.POSITIVE_REACTIONS
                is_negative = emoji in feedback_analyzer.NEGATIVE_REACTIONS
                
                score_delta = 0
                trust_delta = 0
                
                if is_positive:
                    score_delta = -0.2 # Remove positive boost
                    trust_delta = -5
                elif is_negative:
                    score_delta = 0.2 # Remove negative penalty
                    trust_delta = 5
                
                if score_delta != 0:
                    collection_name = f"whisperengine_memory_{self.character_name}"
                    await feedback_analyzer.adjust_memory_score_by_message_id(
                        message_id=message_id,
                        collection_name=collection_name,
                        score_delta=score_delta
                    )
                    
                    self.loop.create_task(
                        trust_manager.update_trust(user_id, self.character_name, trust_delta)
                    )
                    
                    logger.info(f"Reaction removed. Adjusted memory importance by {score_delta}")

        except Exception as e:
            logger.error(f"Error handling reaction remove: {e}")

    async def _check_and_summarize(self, session_id: str, user_id: str):
        """
        Checks if summarization is needed and runs it.
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
                logger.info(f"Session {session_id} reached {message_count} messages. Triggering summarization.")
                
                # Fetch messages
                messages = await memory_manager.get_recent_history(user_id, self.character_name, limit=message_count)
                # Convert to dict format expected by SummaryManager
                msg_dicts = [{"role": "human" if isinstance(m, HumanMessage) else "ai", "content": m.content} for m in messages]
                
                # Generate Summary
                summary_manager = SummaryManager() 
                result = await summary_manager.generate_summary(msg_dicts)
                
                if result:
                    await summary_manager.save_summary(session_id, user_id, result)
                    logger.info(f"Session {session_id} summarized successfully.")
                    
                    # Trigger Reflection
                    logger.info("Triggering reflection analysis...")
                    await reflection_engine.analyze_user_patterns(user_id, self.character_name)
                    
                    # Ideally we should mark these messages as summarized or close the session to start a fresh one.
                    # For now, we just log it.
                    
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
        
        MAX_FILES = 5
        MAX_SIZE_MB = 5
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
                        # Truncate
                        limit = 5000 if silent else 10000
                        if len(extracted_text) > limit:
                            extracted_text = extracted_text[:limit] + "\n...[Content Truncated]..."
                        
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
