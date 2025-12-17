import discord
import asyncio
import time
import random
import re
from typing import List, Tuple, Optional, Any, Dict
from datetime import datetime, timezone, timedelta
from loguru import logger
from zoneinfo import ZoneInfo

from src_v2.config.settings import settings
from src_v2.memory.context_builder import context_builder
from src_v2.core.character import character_manager
from src_v2.memory.manager import memory_manager
from src_v2.memory.session import session_manager
from src_v2.knowledge.manager import knowledge_manager
from src_v2.knowledge.documents import document_processor
from src_v2.knowledge.document_context import DocumentContext
from src_v2.voice.player import play_text
from src_v2.core.database import db_manager
from src_v2.intelligence.activity import server_monitor
from src_v2.core.quota import QuotaExceededError
from src_v2.evolution.trust import trust_manager
from src_v2.evolution.drives import drive_manager
from src_v2.memory.models import MemorySourceType
from src_v2.voice.response import voice_response_manager
from src_v2.workers.task_queue import task_queue
from src_v2.moderation.timeout_manager import timeout_manager
from src_v2.utils.validation import ValidationError, validator, smart_truncate
from src_v2.discord.utils.message_utils import chunk_message, is_image, extract_pending_images
from src_v2.discord.utils.status_manager import ReflectiveStatusManager
from src_v2.core.behavior import get_character_timezone
from influxdb_client.client.write.point import Point
from src_v2.core.goals import goal_manager


async def enqueue_post_conversation_tasks(
    user_id: str,
    character_name: str,
    session_id: str,
    messages: list,
    user_name: str,
    trigger: str = "session_end"
) -> None:
    """
    Unified post-conversation processing pipeline.
    
    Handles summarization, reflection, insight analysis, and batch knowledge extraction
    for ALL conversation types. A user ID is a user ID - human or bot, same pipeline!
    
    Note: No arbitrary message thresholds here. Worker-level filters (100 char minimum,
    meaningfulness score ≥3) provide better quality control than message counts.
    
    Args:
        user_id: Discord user ID (human or bot)
        character_name: Bot's character name
        session_id: Session identifier
        messages: List of message dicts with role/content
        user_name: Display name for diary provenance
        trigger: What triggered this (session_end, cross_bot_session, etc.)
    """
    message_count = len(messages) if messages else 0
    
    logger.info(
        f"Enqueueing post-conversation tasks for session {session_id}: "
        f"{message_count} messages (trigger: {trigger})"
    )
    
    # Enqueue batch knowledge extraction (session-level, more efficient than per-message)
    if settings.ENABLE_RUNTIME_FACT_EXTRACTION:
        try:
            await task_queue.enqueue_batch_knowledge_extraction(
                user_id=user_id,
                character_name=character_name,
                session_id=session_id
            )
        except Exception as e:
            logger.debug(f"Failed to enqueue {trigger} batch knowledge extraction: {e}")
    
    # Enqueue batch preference extraction (session-level, deduplicates preferences)
    if settings.ENABLE_PREFERENCE_EXTRACTION:
        try:
            await task_queue.enqueue_batch_preference_extraction(
                user_id=user_id,
                character_name=character_name,
                session_id=session_id
            )
        except Exception as e:
            logger.debug(f"Failed to enqueue {trigger} batch preference extraction: {e}")
    
    # Enqueue batch goal analysis (session-level, more efficient than per-response)
    try:
        await task_queue.enqueue_batch_goal_analysis(
            user_id=user_id,
            character_name=character_name,
            session_id=session_id
        )
    except Exception as e:
        logger.debug(f"Failed to enqueue {trigger} batch goal analysis: {e}")
    
    # Enqueue summarization
    try:
        await task_queue.enqueue_summarization(
            user_id=user_id,
            character_name=character_name,
            session_id=session_id,
            user_name=user_name
        )
    except Exception as e:
        logger.debug(f"Failed to enqueue {trigger} summarization: {e}")
        return
    
    # Enqueue reflection (runs after summarization)
    try:
        await task_queue.enqueue_reflection(
            user_id=user_id,
            character_name=character_name
        )
    except Exception as e:
        logger.debug(f"Could not enqueue {trigger} reflection: {e}")
    
    # Enqueue insight analysis
    try:
        await task_queue.enqueue_insight_analysis(
            user_id=user_id,
            character_name=character_name,
            trigger=trigger,
            priority=5
        )
    except Exception as e:
        logger.debug(f"Could not enqueue {trigger} insight analysis: {e}")


class MessageHandler:
    def __init__(self, bot):
        self.bot = bot

    def _should_enqueue_enrichment(self, message_count: int) -> bool:
        return (
            settings.ENABLE_GRAPH_ENRICHMENT
            and message_count >= settings.ENRICHMENT_MIN_MESSAGES
        )

    async def _enqueue_graph_enrichment_job(
        self,
        session_id: str,
        user_id: str,
        channel_id: Optional[str],
        server_id: Optional[str]
    ) -> None:
        channel_ref = channel_id or f"dm:{user_id}"
        server_ref = server_id or ("dm" if channel_id is None else None)

        try:
            await task_queue.enqueue_graph_enrichment(
                session_id=session_id,
                user_id=user_id,
                channel_id=channel_ref,
                server_id=server_ref,
                bot_name=self.bot.character_name
            )
        except Exception as exc:  # pragma: no cover - background queue failures are non-blocking
            logger.debug(f"Could not enqueue graph enrichment for {session_id}: {exc}")

    async def _handle_universe_observation(self, message: discord.Message) -> None:
        """Records presence and enqueues universe observation tasks."""
        if not message.guild:
            return

        try:
            # Record activity for autonomous scaling (Phase E15)
            asyncio.create_task(server_monitor.record_message(
                guild_id=str(message.guild.id),
                channel_id=str(message.channel.id)
            ))

            from src_v2.universe.manager import universe_manager
            
            # Fire and forget presence update (lightweight, keep in-process)
            asyncio.create_task(universe_manager.record_presence(str(message.author.id), str(message.guild.id)))
            
            # Enqueue message observation to background worker (Phase 2: Learning to Listen)
            mentioned_ids = [str(m.id) for m in message.mentions]
            reply_to_id = None
            if message.reference and message.reference.resolved:
                if isinstance(message.reference.resolved, discord.Message):
                    reply_to_id = str(message.reference.resolved.author.id)
            
            # Only enqueue if there's meaningful content to observe
            if message.content and len(message.content.strip()) >= 10:
                from src_v2.workers.task_queue import TaskQueue
                await task_queue.enqueue(
                    "run_universe_observation",
                    _job_id=f"universe_obs_{message.id}",
                    _queue_name=TaskQueue.QUEUE_SENSORY,
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

    async def _handle_spam_detection(self, message: discord.Message) -> bool:
        """
        Checks for spam/cross-posting. Returns True if message was handled (deleted/warned) and should stop processing.
        """
        if not message.guild or not settings.ENABLE_CROSSPOST_DETECTION:
            return False

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
                            warning_msg = settings.CROSSPOST_WARNING_MESSAGE
                            warning = f"{message.author.mention} {warning_msg}"
                            await message.channel.send(warning)
                        
                    logger.warning(f"Actioned user {message.author.id} for cross-posting spam.")
                    return True
        except Exception as e:
            logger.error(f"Spam detection failed: {e}")
            
        return False

    async def _check_reply_context(self, message: discord.Message) -> bool:
        """
        Checks if the message is a reply to the bot or in a thread started by the bot.
        Returns True if the bot is effectively mentioned.
        """
        is_mentioned = self.bot.user in message.mentions
        
        if is_mentioned:
            return True

        # Check for Reply without Ping
        if message.reference:
            try:
                # Check resolved reference first
                if message.reference.resolved and isinstance(message.reference.resolved, discord.Message):
                    if message.reference.resolved.author.id == (self.bot.user.id if self.bot.user else None):
                        logger.info("Detected reply to bot without ping.")
                        return True
                # Fallback: Fetch message if not resolved
                elif message.reference.message_id:
                    try:
                        ref_msg = await message.channel.fetch_message(message.reference.message_id)
                        if ref_msg.author.id == (self.bot.user.id if self.bot.user else None):
                            logger.info("Detected reply to bot without ping (fetched).")
                            return True
                    except:
                        pass
            except Exception as e:
                logger.warning(f"Failed to check reply reference: {e}")

        # Check for Thread Context (Thread started on bot message)
        if isinstance(message.channel, discord.Thread):
            try:
                starter_msg = message.channel.starter_message
                
                if not starter_msg and message.channel.parent and not isinstance(message.channel.parent, discord.ForumChannel):
                    try:
                        starter_msg = await message.channel.parent.fetch_message(message.channel.id)
                    except (discord.NotFound, discord.Forbidden):
                        pass 
                
                if starter_msg and starter_msg.author.id == (self.bot.user.id if self.bot.user else None):
                    logger.info("Detected message in thread started on bot message.")
                    return True
            except Exception as e:
                logger.warning(f"Failed to check thread starter: {e}")
        
        return False

    async def _handle_autonomous_trigger(self, message: discord.Message) -> None:
        """Checks and triggers autonomous responses (Daily Life Graph)."""
        if not settings.ENABLE_AUTONOMOUS_ACTIVITY:
            return

        should_trigger = False
        trigger_reason = ""
        
        # 1. Watchlist Channel Activity
        if str(message.channel.id) in settings.discord_check_watch_channels_list:
            should_trigger = True
            trigger_reason = "watchlist_activity"
        
        # 2. Trusted User (Level >= 4)
        if not should_trigger:
            try:
                rel = await trust_manager.get_relationship_level(str(message.author.id), self.bot.character_name)
                if rel.get("level", 1) >= 4 and random.random() < 0.4:
                    should_trigger = True
                    trigger_reason = f"trusted_user_level_{rel.get('level')}"
            except Exception as e:
                logger.debug(f"Failed to check trust for stream trigger: {e}")

        if should_trigger:
            asyncio.create_task(self.bot.daily_scheduler.trigger_immediate(message, trigger_reason))

    async def _check_dm_block(self, message: discord.Message) -> bool:
        """Returns True if DM is blocked."""
        if isinstance(message.channel, discord.DMChannel) and settings.ENABLE_DM_BLOCK:
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
                return True
        return False

    async def _inject_message_context(
        self, 
        message: discord.Message, 
        user_message: str, 
        user_id: str
    ) -> Tuple[str, List[str], List[str]]:
        """
        Injects context from Discord links, replies, and forwarded messages.
        Returns updated user_message, image_urls, and processed_files.
        """
        image_urls: List[str] = []
        processed_files: List[str] = []

        # Handle Discord Message Links (Context Injection)
        discord_link_pattern = re.compile(
            r'https?://(?:ptb\.|canary\.)?discord(?:app)?\.com/channels/(\d+)/(\d+)/(\d+)'
        )
        link_matches = discord_link_pattern.findall(user_message)
        
        for server_id_str, channel_id_str, message_id_str in link_matches:
            try:
                # Only fetch if it's from the same channel (we have access)
                if channel_id_str == str(message.channel.id):
                    linked_msg = await message.channel.fetch_message(int(message_id_str))
                    if linked_msg and linked_msg.content:
                        linked_author = linked_msg.author.display_name
                        linked_content = smart_truncate(linked_msg.content, 2000)
                        
                        user_message = f"[User shared a link to an earlier message from {linked_author}: \"{linked_content}\"]\n{user_message}"
                        logger.info(f"Injected Discord message link context from message {message_id_str}")
                        
                        if linked_msg.attachments:
                            for att in linked_msg.attachments:
                                if att.content_type and att.content_type.startswith("image/"):
                                    image_urls.append(att.url)
                                    logger.info(f"Included image from linked message: {att.url}")
                else:
                    # Different channel - try to fetch from guild
                    if message.guild:
                        try:
                            linked_channel = message.guild.get_channel(int(channel_id_str))
                            if linked_channel and isinstance(linked_channel, discord.TextChannel):
                                linked_msg = await linked_channel.fetch_message(int(message_id_str))
                                if linked_msg and linked_msg.content:
                                    linked_author = linked_msg.author.display_name
                                    linked_content = smart_truncate(linked_msg.content, 2000)
                                    channel_name = linked_channel.name
                                    user_message = f"[User shared a link to a message from #{channel_name} by {linked_author}: \"{linked_content}\"]\n{user_message}"
                                    logger.info(f"Injected cross-channel Discord message link context from #{channel_name}")
                        except (discord.Forbidden, discord.NotFound) as e:
                            logger.debug(f"Cannot access linked message in channel {channel_id_str}: {e}")
            except (discord.NotFound, discord.Forbidden) as e:
                logger.debug(f"Failed to fetch linked message {message_id_str}: {e}")
            except Exception as e:
                logger.warning(f"Error processing Discord message link: {e}")

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
                        pass 

                if ref_msg:
                    # 1. Text & Sticker Context
                    content = ref_msg.content or ""
                    
                    if ref_msg.stickers:
                        sticker_names = [s.name for s in ref_msg.stickers]
                        content += f"\n[Sent Sticker(s): {', '.join(sticker_names)}]"

                    ref_has_images = bool(ref_msg.attachments and any(
                        att.content_type and att.content_type.startswith("image/") 
                        for att in ref_msg.attachments
                    ))

                    if content or ref_has_images:
                        ref_text = smart_truncate(content, 2000) if content else ""
                        ref_author = ref_msg.author.display_name
                        
                        image_marker = " [with image]" if ref_has_images else ""
                        
                        is_reply_to_bot = ref_msg.author.id == (self.bot.user.id if self.bot.user else None)
                        current_user_name = message.author.display_name
                        
                        if is_reply_to_bot:
                            if ref_text:
                                user_message = f"[CONTEXT: {current_user_name} is replying to YOUR previous message. They are commenting on what YOU wrote.]\n[Your original message was{image_marker}: \"{ref_text}\"]\n[{current_user_name}'s response]: {user_message}"
                            else:
                                user_message = f"[CONTEXT: {current_user_name} is replying to YOUR previous image/post. They are commenting on what YOU shared.]\n[{current_user_name}'s response]: {user_message}"
                            logger.info(f"Injected self-reply context (user commenting on bot's message)")
                        else:
                            if ref_text:
                                user_message = f"[Replying to {ref_author}{image_marker}: \"{ref_text}\"]\n{user_message}"
                            else:
                                user_message = f"[Replying to {ref_author}'s image{image_marker}]\n{user_message}"
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
                    fwd_content = snapshot.content or ""
                    
                    if snapshot.stickers:
                        sticker_names = [s.name for s in snapshot.stickers]
                        fwd_content += f"\n[Forwarded Sticker(s): {', '.join(sticker_names)}]"

                    if fwd_content:
                        fwd_text = smart_truncate(fwd_content, 2000)
                        user_message = f"[Forwarded Message: \"{fwd_text}\"]\n{user_message}"
                        logger.info(f"Injected forwarded context: {user_message}")
                    
                    if snapshot.attachments:
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
                
        return user_message, image_urls, processed_files

    async def _build_context(
        self, 
        user_id: str, 
        message: discord.Message, 
        user_message: str, 
        character: Any
    ) -> Tuple[Any, Any, Any, Any, Any, Any]:
        """
        Retrieves context from memory, history, knowledge, summaries, universe, and nickname.
        Returns (memories, chat_history, knowledge_facts, past_summaries, universe_context, preferred_nickname).
        """
        # BUGFIX: Validate user_id parameter matches message author
        expected_user_id = str(message.author.id)
        if user_id != expected_user_id:
            logger.error(
                f"CRITICAL BUG in _build_context: user_id mismatch! "
                f"Expected: {expected_user_id} (message.author.id), "
                f"Got: {user_id}, "
                f"Author: {message.author.display_name}"
            )
            user_id = expected_user_id  # Force correction
        else:
            logger.debug(f"_build_context: user_id validated={user_id}")
        
        channel_id = str(message.channel.id)
        
        async def get_memories():
            try:
                mems = await memory_manager.search_memories(user_message, user_id)
                if mems:
                    def format_mem(m):
                        rel = m.get('relative_time', 'unknown time')
                        content = m.get('content', '')
                        user_name = m.get('user_name')
                        
                        if len(content) > 500:
                            content = content[:500] + "..."
                        
                        if m.get('is_chunk'):
                            idx = m.get('chunk_index', 0) + 1
                            total = m.get('chunk_total', '?')
                            content = f"[Fragment {idx}/{total}] {content}"
                            
                        if user_name:
                            return f"- [With {user_name}]: {content} ({rel})"
                        return f"- {content} ({rel})"
                    
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
                # BUGFIX: Log user_id to trace knowledge retrieval
                logger.debug(f"[KNOWLEDGE_CALL] get_user_knowledge with user_id={user_id}, author={message.author.display_name}")
                facts = await knowledge_manager.get_user_knowledge(user_id)
                logger.debug(f"[KNOWLEDGE_CALL] Retrieved facts for user_id={user_id}: {facts[:150] if facts else 'NONE'}...")
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

        async def get_user_nickname():
            try:
                trust_data = await trust_manager.get_relationship_level(user_id, self.bot.character_name)
                preferences = trust_data.get('preferences', {})
                return preferences.get('nickname') 
            except Exception as e:
                logger.debug(f"Failed to fetch user nickname: {e}")
                return None

        return await asyncio.gather(
            get_memories(),
            get_history(),
            get_knowledge(),
            get_summaries(),
            get_universe_context(),
            get_user_nickname()
        )

    async def _generate_and_stream_response(
        self,
        message: discord.Message,
        user_message: str,
        character: Any,
        chat_history: List[Any],
        context_vars: Dict[str, Any],
        user_id: str,
        image_urls: List[str],
        force_reflective: bool,
        complexity: str,
        detected_intents: List[str],
        processing_start: float,
        use_reply: bool
    ) -> Tuple[str, Optional[discord.Message], Optional[discord.Message]]:
        """
        Generates response via LLM and streams it to Discord.
        Returns (full_response_text, active_message, status_message).
        """
        # Prepare callback for Reflective Mode
        status_manager = ReflectiveStatusManager(message, use_reply)
        
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
            async for chunk in self.bot.agent_engine.generate_response_stream(
                character=character,
                user_message=user_message,
                chat_history=chat_history,
                context_variables=context_vars,
                user_id=user_id,
                image_urls=image_urls,
                callback=status_manager.update,
                force_reflective=force_reflective,
                preclassified_complexity=complexity,
                preclassified_intents=detected_intents
            ):
                full_response_text += chunk
                
                # Rate limit updates
                now = time.time()
                if now - last_update_time > update_interval:
                    # Only stream if length is safe and content is non-empty
                    if len(full_response_text) < 1950 and full_response_text.strip():
                        try:
                            if not active_message:
                                # Check if we have a status message to take over
                                should_append = False
                                prefix = ""
                                if status_manager.status_message:
                                    # Check if appending fits in one message
                                    current_status = status_manager.get_current_content()
                                    combined_len = len(current_status) + len(full_response_text) + 4 # +4 for \n\n
                                    if combined_len < 1950: # Leave some buffer
                                        should_append = True
                                        prefix = current_status + "\n\n"
                                
                                if should_append:
                                    active_message = status_manager.status_message
                                    await active_message.edit(content=f"{prefix}{full_response_text}")
                                # First message: use reply in guild channels
                                elif use_reply:
                                    active_message = await message.reply(full_response_text, mention_author=False)
                                else:
                                    active_message = await message.channel.send(full_response_text)
                            else:
                                # We already have an active message
                                if active_message == status_manager.status_message:
                                    # We are appending to status message
                                    current_status = status_manager.get_current_content()
                                    combined_text = f"{current_status}\n\n{full_response_text}"
                                    if len(combined_text) < 1950:
                                        await active_message.edit(content=combined_text)
                                    else:
                                        # Overflowed! Stop updating this message to avoid error.
                                        pass
                                else:
                                    await active_message.edit(content=full_response_text)
                        except Exception as e:
                            logger.warning(f"Failed to stream update: {e}")
                    last_update_time = now
        
        return full_response_text, active_message, status_manager.status_message

    async def on_message(self, message: discord.Message) -> None:
        """Handles incoming Discord messages and generates AI responses.
        
        Args:
            message: Discord message object
        """
        # Prevent self-reply loops
        if self.bot.user and message.author.id == self.bot.user.id:
            return

        # Cross-bot detection (Phase E6) - Handle bot messages differently
        if message.author.bot:
            # EXCEPTION: Allow broadcast channel posts from OTHER bots to flow through
            # This enables bots to "pounce" on each other's dreams/diaries via lurk detector
            is_broadcast_from_other_bot = (
                message.guild and 
                str(message.channel.id) in settings.bot_broadcast_channel_ids_list
            )
            
            if not is_broadcast_from_other_bot:
                # Normal bot handling: only respond to explicit mentions
                return
            
            # Fall through to lurk detector below for broadcast channel messages

        # Ignore messages from blocked users (including blocked bots)
        if str(message.author.id) in settings.blocked_user_ids_list:
            logger.debug(f"Ignoring message from blocked user/bot: {message.author.id}")
            return

        # Universe Presence & Observation
        await self._handle_universe_observation(message)

        # --- Spam Detection (Cross-posting) ---
        if await self._handle_spam_detection(message):
            return

        # Process commands first
        await self.bot.process_commands(message)
        
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
        is_dm = isinstance(message.channel, discord.DMChannel)
        is_mentioned = await self._check_reply_context(message)
        
        # Privacy: Block DMs if enabled and user is not allowlisted
        if await self._check_dm_block(message):
            return

        # Phase 4: Autonomous Replies (Occasional replies without mention)
        if not is_dm and not is_mentioned and message.guild:
            await self._handle_autonomous_trigger(message)

        if is_dm or is_mentioned:
            # Typing indicator delayed to mimic natural reading time
            processing_start = time.time()
            try:
                # Get the character
                character = character_manager.get_character(self.bot.character_name)
                
                if not character:
                    logger.error(f"Character '{self.bot.character_name}' not loaded.")
                    await message.channel.send("Error: Character not loaded.")
                    return

                # Check manipulation timeout before any processing
                if settings.ENABLE_MANIPULATION_TIMEOUTS:
                    user_id = str(message.author.id)
                    timeout_status = await timeout_manager.check_user_status(user_id, bot_name=self.bot.character_name)
                    if timeout_status.is_restricted():
                        # User is in timeout - return cold response only
                        if character.cold_responses:
                            response = random.choice(character.cold_responses)
                        else:
                            response = "..."
                        await message.channel.send(response)
                        logger.debug(f"User {user_id} in timeout ({timeout_status.format_remaining()} remaining), served cold response")
                        return

                # 0. Session Management
                # CRITICAL: Bind user_id early to prevent context confusion
                user_id = str(message.author.id)
                logger.debug(f"Processing message from user_id={user_id}, display_name={message.author.display_name}")
                
                session_id = await session_manager.get_active_session(user_id, self.bot.character_name)
                if not session_id:
                    session_id = await session_manager.create_session(user_id, self.bot.character_name)

                # Clean the message (remove mention)
                user_message = message.content.replace(f"<@{self.bot.user.id}>", "").strip()
                
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
                
                # Check for Forced Reflective Mode via bang command
                force_reflective = False
                if user_message.startswith("!reflect"):
                    if settings.ENABLE_REFLECTIVE_MODE:
                        cleaned_content = user_message.replace("!reflect", "", 1).strip()
                        
                        # Edge Case: User typed "!reflect" but no message and no reply
                        if not cleaned_content and not message.reference:
                            await message.channel.send("ℹ️ Usage: `!reflect <your question>` or reply to a message with `!reflect`.")
                            return
                            
                        user_message = cleaned_content or user_message
                        force_reflective = True
                        logger.info(f"User {user_id} forced Reflective Mode via !reflect")
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

                # Inject context from links, replies, and forwards
                user_message, image_urls, processed_files = await self._inject_message_context(
                    message, user_message, user_id
                )

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

                # Check for Voice Trigger (Phase A10)
                # Now handled by LLM intent detection, but we initialize it here
                should_trigger_voice = False
                detected_intents = []
                
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
                (memories, formatted_memories), chat_history, knowledge_facts, past_summaries, universe_context, preferred_nickname = await self._build_context(
                    user_id, message, user_message, character
                )

                # 2. Save User Message & Extract Knowledge
                try:
                    # Save to memory with full document content for RAG retrieval
                    memory_content = doc_context.format_for_memory(user_message)
                    metadata = doc_context.get_memory_metadata()

                    # ADR-014: Include author fields for proper attribution
                    await memory_manager.add_message(
                        user_id, 
                        character.name, 
                        'human', 
                        memory_content, 
                        channel_id=channel_id, 
                        message_id=str(message.id),
                        user_name=message.author.display_name,
                        metadata=metadata,
                        # ADR-014: Author tracking
                        author_id=str(message.author.id),
                        author_is_bot=message.author.bot,
                        author_name=message.author.display_name,
                        reply_to_msg_id=str(message.reference.message_id) if message.reference else None,
                        session_id=session_id
                    )
                    
                    # Log Message Event to InfluxDB
                    if db_manager.influxdb_write_api:
                        point = Point("message_event") \
                            .tag("user_id", user_id) \
                            .tag("bot_name", self.bot.character_name) \
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

                # 2.5 Check for Summarization
                if session_id:
                    self.bot.loop.create_task(
                        self._check_and_summarize(
                            session_id,
                            user_id,
                            message.author.display_name,
                            channel_id=channel_id,
                            server_id=str(message.guild.id) if message.guild else None
                        )
                    )

                # 3. Generate response
                # Get character's timezone for context-aware datetime
                # The character experiences time in their own timezone (where they "live")
                
                char_timezone_str = get_character_timezone(character.name)
                try:
                    char_tz = ZoneInfo(char_timezone_str)
                    char_now = datetime.now(char_tz)
                    datetime_display = char_now.strftime("%A, %B %d, %Y at %I:%M %p") + f" ({char_timezone_str})"
                except Exception as e:
                    logger.debug(f"Invalid character timezone '{char_timezone_str}': {e}, using local time")
                    now = datetime.now()
                    datetime_display = now.strftime("%A, %B %d, %Y at %I:%M %p")
                
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

                # Use preferred nickname if set, otherwise fall back to Discord display name
                effective_user_name = preferred_nickname or message.author.display_name
                
                # BUGFIX: Validate user_id hasn't been corrupted
                expected_user_id = str(message.author.id)
                if user_id != expected_user_id:
                    logger.error(
                        f"CRITICAL BUG: user_id mismatch! "
                        f"Expected: {expected_user_id} (from message.author.id), "
                        f"Actual: {user_id}, "
                        f"Author name: {message.author.display_name}"
                    )
                    user_id = expected_user_id  # Force correction
                else:
                    logger.debug(f"user_id validation passed: {user_id}")
                
                context_vars = {
                    "user_name": effective_user_name,
                    "discord_display_name": message.author.display_name,  # Keep original for reference
                    "current_datetime": datetime_display,
                    "universe_context": universe_context,
                    "recent_memories": formatted_memories,
                    "knowledge_context": knowledge_facts,
                    "past_summaries": past_summaries,
                    "guild_id": str(message.guild.id) if message.guild else None,
                    "channel_name": channel_name,
                    "parent_channel_name": parent_channel_name,
                    "is_thread": is_thread,
                    "has_documents": doc_context.has_documents,
                    "channel": message.channel,  # For Discord search tools
                    # OPTIMIZATION: Pass raw data to avoid re-fetching in MasterGraphAgent
                    "prefetched_memories": memories,
                    "prefetched_knowledge": knowledge_facts
                }
                
                # Append document preview to user message for LLM
                if doc_context.has_documents:
                    user_message += doc_context.format_for_llm()

                # 3. Complexity Analysis & Intent Detection
                complexity = False
                detected_intents = []
                
                try:
                    complexity, detected_intents = await self.bot.agent_engine.classify_complexity(
                        user_message, 
                        chat_history, 
                        user_id=user_id,
                        character_name=self.bot.character_name
                    )
                    
                    # Check for Voice Intent
                    if settings.ENABLE_VOICE_RESPONSES and "voice" in detected_intents:
                        should_trigger_voice = True
                        logger.info(f"Voice intent detected for user {user_id}")

                    # Handle image complexity:
                    # - If user UPLOADED an image (image_urls exists) → keep at COMPLEX_LOW for viewing
                    # - If user wants to GENERATE an image (no upload, but image intent) → COMPLEX_MID for tools
                    # - If documents are present → don't cap, need reflective agent for read_document tool
                    image_intents = {"image_self", "image_other", "image_refine"}
                    if image_urls and not doc_context.has_documents:
                        # User uploaded an image (no documents) - CharacterAgent can handle viewing
                        # Cap at COMPLEX_LOW if classifier over-promoted
                        if complexity in ["COMPLEX_MID", "COMPLEX_HIGH"]:
                            logger.info(f"Capping complexity to COMPLEX_LOW for image upload (was {complexity})")
                            complexity = "COMPLEX_LOW"
                    elif image_intents.intersection(set(detected_intents)):
                        # User wants to generate an image (no upload) - needs tools
                        if not complexity or complexity == "COMPLEX_LOW":
                            complexity = "COMPLEX_MID"
                            logger.info(f"Upgraded complexity to COMPLEX_MID due to image generation intent for user {user_id}")
                        
                except Exception as e:
                    logger.error(f"Complexity analysis failed: {e}")
                    complexity = False

                # Track timing for stats footer
                start_time = time.time()
                
                # Use reply for guild channels (not DMs) to maintain conversation threading
                use_reply = not is_dm
                
                # Generate and stream response
                response, active_message, status_message = await self._generate_and_stream_response(
                    message=message,
                    user_message=user_message,
                    character=character,
                    chat_history=chat_history,
                    context_vars=context_vars,
                    user_id=user_id,
                    image_urls=image_urls,
                    force_reflective=force_reflective,
                    complexity=complexity,
                    detected_intents=detected_intents,
                    processing_start=processing_start,
                    use_reply=use_reply
                )
                
                # Guard against empty responses
                if not response or not response.strip():
                    logger.warning(f"LLM returned empty response for user {user_id}")
                    if character.error_messages:
                        response = random.choice(character.error_messages)
                    else:
                        response = "I got a bit distracted there. What were we talking about?"
                
                processing_time_ms: float = (time.time() - start_time) * 1000
                
                # 3.5 Generate Stats Footer (if enabled for user)
                from src_v2.utils.stats_footer import stats_footer
                
                logger.debug(f"Generating stats footer for user_id={user_id}, user_name={effective_user_name}")
                should_show_footer = await stats_footer.is_enabled_for_user(user_id, self.bot.character_name)
                footer_text = ""
                
                if should_show_footer:
                    footer_text = await stats_footer.generate_footer(
                        user_id=user_id,
                        character_name=self.bot.character_name,
                        memory_count=len(memories) if memories else 0,
                        processing_time_ms=processing_time_ms
                    )
                
                # 4. Save AI Response
                try:
                    # Append footer if enabled
                    final_text = response
                    if footer_text:
                        final_text = f"{response}\n\n{footer_text}"
                    
                    # Generate Voice Response if triggered (Phase A10)
                    # Do this BEFORE extracting artifacts so the audio file is included
                    if should_trigger_voice:
                        try:
                            # Use the clean response text (without footer)
                            await voice_response_manager.generate_voice_response(response, character, user_id)
                            
                            # Add intro text if configured (to the main message, indicating voice is coming)
                            if character.voice_config and character.voice_config.intro_template:
                                intro = character.voice_config.intro_template.format(name=character.name)
                                final_text = f"{intro}\n\n{final_text}"
                                
                        except QuotaExceededError as e:
                            logger.info(f"Voice quota exceeded for user {user_id}")
                            final_text += f"\n\n⚠️ **Voice generation failed:** Daily audio quota exceeded ({e.usage}/{e.limit})."
                        except Exception as e:
                            logger.error(f"Failed to generate voice response: {e}")

                    # Extract any generated images/artifacts from the response
                    # NOTE: extract_pending_images now wraps the unified artifact registry
                    # This will now pick up the voice file we just generated
                    cleaned_text, image_files = await extract_pending_images(final_text, user_id)

                    # Split response into chunks if it's too long
                    message_chunks = chunk_message(cleaned_text)
                    
                    # Handle the first chunk (Edit existing or Send new)
                    sent_messages = []
                    
                    # use_reply is already defined before streaming
                    
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
                            if i == 0:
                                # First chunk: reply in guild, send in DM
                                if image_files:
                                    try:
                                        if use_reply:
                                            sent_msg = await message.reply(content=chunk, files=image_files, mention_author=False)
                                        else:
                                            sent_msg = await message.channel.send(content=chunk, files=image_files)
                                    except discord.Forbidden as e:
                                        logger.error(f"Permission denied when sending images: {e}")
                                        if use_reply:
                                            sent_msg = await message.reply(content=chunk, mention_author=False)
                                        else:
                                            sent_msg = await message.channel.send(content=chunk)
                                    except Exception as e:
                                        logger.error(f"Failed to send message with images: {e}")
                                        if use_reply:
                                            sent_msg = await message.reply(content=chunk, mention_author=False)
                                        else:
                                            sent_msg = await message.channel.send(content=chunk)
                                else:
                                    if use_reply:
                                        sent_msg = await message.reply(content=chunk, mention_author=False)
                                    else:
                                        sent_msg = await message.channel.send(chunk)
                            else:
                                # Subsequent chunks: always use channel.send
                                sent_msg = await message.channel.send(chunk)
                            sent_messages.append(sent_msg)
                    
                    # Save the full response to memory (not chunked)
                    # Use the last message ID as the primary reference
                    if sent_messages:
                        # ADR-014: Bot is the author of this response
                        await memory_manager.add_message(
                            user_id, 
                            character.name, 
                            'ai', 
                            response, 
                            channel_id=channel_id, 
                            message_id=str(sent_messages[-1].id),
                            user_name=message.author.display_name,
                            # ADR-014: Author tracking - bot is author
                            author_id=settings.DISCORD_BOT_NAME,
                            author_is_bot=True,
                            author_name=character.name,
                            reply_to_msg_id=str(message.id),  # Bot is replying to user's message
                            session_id=session_id
                        )
                    
                    # NOTE: Goal analysis is now handled at session end via batch goal analysis.
                    # This provides better context (full conversation arc) and reduces LLM costs.
                    # See enqueue_post_conversation_tasks() for the batch goal analysis call.
                    
                    # 4.6 Trust Update (Engagement Reward)
                    # Small trust increase for every positive interaction
                    async def handle_trust_update():
                        try:
                            milestone = await trust_manager.update_trust(user_id, character.name, 1)
                            if milestone:
                                await message.channel.send(milestone)
                        except Exception as e:
                            logger.error(f"Failed to handle trust update: {e}")

                    self.bot.loop.create_task(handle_trust_update())
                    
                    # 4.6.1 Social Battery Recharge (Phase E15)
                    # Interaction with users recharges the bot's social energy
                    if settings.ENABLE_AUTONOMOUS_DRIVES:
                        try:
                            # Recharge amount: +0.08 per interaction
                            # This means ~12 conversations fully recharge from empty
                            await drive_manager.update_social_battery(self.bot.character_name, 0.08)
                        except Exception as e:
                            logger.debug(f"Failed to recharge social battery: {e}")
                    
                    # 4.7 Universe Relationship Update (Phase B8)
                    # Build familiarity between character and user after each conversation
                    try:
                        guild_id = str(message.guild.id) if message.guild else None
                        await task_queue.enqueue_relationship_update(
                            character_name=self.bot.character_name,
                            user_id=user_id,
                            guild_id=guild_id,
                            interaction_quality=1
                        )
                    except Exception as e:
                        logger.debug(f"Failed to enqueue relationship update: {e}")
                    
                    # 4.8 Universe Event Detection (Phase 3.4)
                    # Detect significant events and publish to the event bus
                    # Pass detected_intents for LLM-based detection (falls back to regex if not available)
                    if settings.ENABLE_UNIVERSE_EVENTS:
                        try:
                            from src_v2.universe.detector import event_detector
                            await event_detector.analyze_and_publish(
                                user_id=user_id,
                                user_message=raw_user_message,
                                character_name=self.bot.character_name,
                                detected_intents=detected_intents,
                                user_name=message.author.display_name
                            )
                        except Exception as e:
                            logger.debug(f"Failed to detect universe event: {e}")
                    
                    # 5. Voice Playback (use full response, not chunked)
                    if message.guild and message.guild.voice_client:
                        vc = message.guild.voice_client
                        # Check if voice client is connected
                        if hasattr(vc, 'is_connected') and vc.is_connected():
                            # Only speak if the message was sent in the Voice Channel's text chat
                            # (message.channel.id matches the voice channel ID)
                            if vc.channel and message.channel.id == vc.channel.id:
                                logger.info(f"Voice connected in {message.guild.name} and message from VC text chat. Speaking...")
                                try:
                                    voice_id = character.voice_config.voice_id if character.voice_config else None
                                    await play_text(vc, response, voice_id=voice_id)  # type: ignore[arg-type]
                                except Exception as e:
                                    logger.error(f"Failed to play voice: {e}")
                            else:
                                logger.debug("Message not from VC text chat. Skipping voice playback.")
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
                    char = character_manager.get_character(self.bot.character_name)
                    if char and char.error_messages:
                        error_msg = random.choice(char.error_messages)
                except Exception:
                    pass
                await message.channel.send(error_msg)



        # Autonomous Reactions: Maybe react with emoji to the message (Phase E12)
        # This runs independently of lurk/respond - just adds reactions
        if settings.ENABLE_AUTONOMOUS_ACTIVITY and settings.ENABLE_AUTONOMOUS_REACTIONS and message.guild:
            # Fire and forget - don't block message handling
            asyncio.create_task(self._maybe_react_to_message(message))

    async def _maybe_react_to_message(self, message: discord.Message) -> None:
        """
        Potentially add an emoji reaction to a message (Phase E12).
        
        This creates organic bot presence without requiring direct interaction.
        Uses the ReactionAgent to decide whether to react and what emoji.
        
        Args:
            message: Discord message to potentially react to
        """
        try:
            from src_v2.agents.reaction_agent import get_reaction_agent
            
            agent = get_reaction_agent(self.bot.character_name)
            
            # Check if message looks like a command
            is_command = message.content.startswith(("/", "!", "."))
            
            # Decide whether to react
            decision = await agent.decide_reaction(
                message_content=message.content,
                message_author_id=str(message.author.id),
                message_author_is_bot=message.author.bot,
                channel_id=str(message.channel.id),
                is_command=is_command
            )
            
            if not decision.should_react:
                logger.debug(f"Reaction skipped: {decision.reason}")
                return
            
            # Wait for the delay (makes reactions feel more natural)
            await asyncio.sleep(decision.delay_seconds)
            
            # Add reactions
            for emoji in decision.emojis:
                try:
                    await message.add_reaction(emoji)
                    logger.info(f"Added reaction {emoji} to message {message.id} ({decision.reason})")
                except discord.Forbidden:
                    logger.warning(f"Missing permission to add reaction in channel {message.channel.id}")
                    break
                except discord.HTTPException as e:
                    logger.warning(f"Failed to add reaction {emoji}: {e}")
                    break
            
            # Record for rate limiting
            await agent.record_reaction(str(message.channel.id), str(message.author.id))
            
        except Exception as e:
            logger.error(f"Error in autonomous reaction: {e}")

    async def _check_and_summarize(
        self,
        session_id: str,
        user_id: str,
        user_name: str,
        channel_id: Optional[str] = None,
        server_id: Optional[str] = None
    ):
        """
        Enqueues post-conversation processing when conversation activity occurs.
        
        No arbitrary thresholds - let worker filters decide if conversation is worth processing.
        
        Args:
            session_id: Session ID
            user_id: Discord user ID
            user_name: User's display name (for diary provenance)
            channel_id: Discord channel identifier for this conversation
            server_id: Discord server identifier (or None for DM)
        """
        try:
            # 1. Get session start time
            start_time = await session_manager.get_session_start_time(session_id)
            if not start_time:
                return

            # 2. Count messages
            message_count = await memory_manager.count_messages_since(user_id, self.bot.character_name, start_time)

            if self._should_enqueue_enrichment(message_count):
                await self._enqueue_graph_enrichment_job(
                    session_id=session_id,
                    user_id=user_id,
                    channel_id=channel_id,
                    server_id=server_id
                )
            
            # 3. Enqueue post-conversation processing
            # Worker-level filters (100 char min, meaningfulness ≥3) provide better
            # quality control than arbitrary message counts.
            if message_count >= 2:  # At least a back-and-forth
                logger.info(
                    f"Session {session_id}: Enqueueing batch analysis "
                    f"({message_count} messages)"
                )
                
                # Fetch messages
                messages = await memory_manager.get_recent_history(
                    user_id,
                    self.bot.character_name,
                    limit=message_count,
                    channel_id=channel_id
                )
                # Convert to dict format expected by SummaryManager
                from langchain_core.messages import HumanMessage
                msg_dicts = [
                    {
                        "role": "human" if isinstance(m, HumanMessage) else "ai",
                        "content": m.content
                    }
                    for m in messages
                ]

                # Unified post-conversation processing
                await enqueue_post_conversation_tasks(
                    user_id=user_id,
                    character_name=self.bot.character_name,
                    session_id=session_id,
                    messages=msg_dicts,
                    user_name=user_name,
                    trigger="session_activity"
                )
                    
        except Exception as e:
            logger.error(f"Error in _check_and_summarize: {e}")

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
        
        MAX_FILES = settings.MAX_ATTACHMENTS_PER_MESSAGE
        MAX_SIZE_MB = settings.MAX_ATTACHMENT_SIZE_MB
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
                    logger.info(f"Skipping oversized {'image' if is_image(attachment) else 'document'}: {attachment.filename} ({attachment.size / 1024 / 1024:.1f}MB)")
                continue # Skip silently as we already warned user upfront

            # 2. Image Handling
            if is_image(attachment):
                image_urls.append(attachment.url)
                file_count += 1
                
                if not silent:
                    logger.info(f"Detected image attachment: {attachment.url}")
                else:
                    logger.info(f"Included image from referenced message: {attachment.url}")
                
                if trigger_vision and settings.LLM_SUPPORTS_VISION:
                    try:
                        await task_queue.enqueue_vision_analysis(
                            image_url=attachment.url,
                            user_id=user_id,
                            channel_id=str(channel.id)
                        )
                    except Exception as e:
                        logger.error(f"Failed to enqueue vision analysis: {e}")
            
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
