from langchain_core.messages import HumanMessage
import discord
import asyncio
from typing import Union
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

class WhisperBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
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

    def _chunk_message(self, text: str, max_length: int = 2000) -> list[str]:
        """
        Splits a long message into chunks that fit Discord's character limit.
        Tries to split on sentence boundaries when possible.
        """
        if len(text) <= max_length:
            return [text]
        
        chunks = []
        current_chunk = ""
        
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

    async def update_status_loop(self):
        await self.wait_until_ready()
        # Initial status set
        await self.change_presence(status=discord.Status.online)
        
        status_index = 0
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

    async def setup_hook(self):
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

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        await self.change_presence(status=discord.Status.online)
        
        # Preload character
        char = character_manager.get_character(self.character_name)
        if char:
            logger.info(f"Character '{self.character_name}' loaded successfully.")
        else:
            logger.error(f"Could not load character '{self.character_name}'!")

        logger.info("WhisperEngine is ready and listening.")

    async def on_message(self, message: discord.Message):
        # Ignore messages from self and other bots to prevent loops
        if message.author.bot:
            return

        # Process commands first
        await self.process_commands(message)
        
        # Ignore empty messages or system messages
        if not message.content or message.is_system():
            return

        # Determine if we should respond
        # 1. Direct Message (DM)
        # 2. Mentioned in a server
        is_dm = isinstance(message.channel, discord.DMChannel)
        is_mentioned = self.user in message.mentions
        
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

                            if ref_msg and ref_msg.content:
                                ref_text = ref_msg.content[:100] + "..." if len(ref_msg.content) > 100 else ref_msg.content
                                ref_author = ref_msg.author.display_name
                                user_message = f"[Replying to {ref_author}: \"{ref_text}\"]\n{user_message}"
                                logger.info(f"Injected reply context: {user_message}")
                        except Exception as e:
                            logger.warning(f"Failed to resolve reply reference: {e}")

                    user_id = str(message.author.id)
                    channel_id = str(message.channel.id)
                    
                    # Check for attachments (Images & Documents)
                    image_urls = []
                    file_content = None
                    
                    if message.attachments:
                        processed_files = []
                        file_count = 0
                        MAX_FILES = 5
                        MAX_SIZE_MB = 5
                        MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024

                        for attachment in message.attachments:
                            # Image Handling (Collect all images)
                            if attachment.content_type and attachment.content_type.startswith("image/"):
                                image_urls.append(attachment.url)
                                logger.info(f"Detected image attachment: {attachment.url}")
                                
                                # Trigger Vision Analysis (Background Task)
                                if settings.LLM_SUPPORTS_VISION:
                                    asyncio.create_task(
                                        vision_manager.analyze_and_store(
                                            image_url=attachment.url,
                                            user_id=user_id,
                                            channel_id=channel_id
                                        )
                                    )
                            
                            # Document Handling (PDF, Txt, etc.)
                            else:
                                if file_count >= MAX_FILES:
                                    logger.warning(f"Skipping attachment {attachment.filename}: Max file limit ({MAX_FILES}) reached.")
                                    continue
                                
                                if attachment.size > MAX_SIZE_BYTES:
                                    logger.warning(f"Skipping attachment {attachment.filename}: Size ({attachment.size} bytes) exceeds limit ({MAX_SIZE_MB}MB).")
                                    await message.channel.send(f"⚠️ Skipping {attachment.filename}: File too large (Max {MAX_SIZE_MB}MB).")
                                    continue

                                logger.info(f"Detected document attachment: {attachment.filename}")
                                await message.channel.send(f"📄 Reading {attachment.filename}...")
                                
                                try:
                                    extracted_text = await document_processor.process_attachment(attachment.url, attachment.filename)
                                    if extracted_text:
                                        # Truncate individual file content if too massive
                                        if len(extracted_text) > 10000:
                                            extracted_text = extracted_text[:10000] + "\n...[Content Truncated]..."
                                        
                                        processed_files.append(f"--- File: {attachment.filename} ---\n{extracted_text}")
                                        file_count += 1
                                        logger.info(f"Processed document content: {len(extracted_text)} chars")
                                except Exception as e:
                                    logger.error(f"Failed to process {attachment.filename}: {e}")
                                    await message.channel.send(f"❌ Failed to read {attachment.filename}.")

                        if processed_files:
                            file_content = "\n\n".join(processed_files)
                    
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
                    
                    response = await self.agent_engine.generate_response(
                        character=character,
                        user_message=user_message,
                        chat_history=chat_history,
                        context_variables=context_vars,
                        user_id=user_id,
                        image_urls=image_urls
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

    async def on_reaction_add(self, reaction: discord.Reaction, user: Union[discord.Member, discord.User]):
        """
        Handles reactions added to messages.
        Used for user feedback (e.g., thumbs up/down) to adjust memory importance.
        """
        if user.bot:
            return

        # Only care if the reaction is on a message sent by THIS bot
        if reaction.message.author.id != self.user.id:
            return

        try:
            message_id = str(reaction.message.id)
            user_id = str(user.id)
            emoji = str(reaction.emoji)
            message_length = len(reaction.message.content)
            
            logger.info(f"User {user.name} reacted with {emoji} to message {message_id}")

            # Log to InfluxDB via FeedbackAnalyzer
            await feedback_analyzer.log_reaction_to_influx(
                user_id=user_id,
                message_id=message_id,
                reaction=emoji,
                bot_name=self.character_name,
                message_length=message_length
            )
            
            # Get feedback score and adjust memory importance
            feedback = await feedback_analyzer.get_feedback_score(message_id, user_id)
            if feedback and feedback["score"] != 0:
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
            logger.error(f"Error handling reaction: {e}")

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

    async def on_error(self, event_method: str, *args, **kwargs):
        logger.exception(f"Error in event {event_method}")


# Global bot instance
bot = WhisperBot()
