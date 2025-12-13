"""
Bot Broadcast Manager (Phase E8)

Posts character thoughts, dreams, and observations to a public Discord channel.
Enables cross-bot discovery and reactions for emergent character awareness.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from dataclasses import dataclass
from enum import Enum
import json
import uuid
import discord
from loguru import logger

from src_v2.config.settings import settings
from src_v2.core.database import db_manager
from src_v2.core.cache import CacheManager
from src_v2.safety.content_review import content_safety_checker
from src_v2.discord.utils.message_utils import chunk_message
from src_v2.intelligence.activity import server_monitor
from src_v2.utils.time_utils import get_configured_timezone
from src_v2.artifacts.discord_utils import extract_pending_artifacts


class PostType(str, Enum):
    DIARY = "diary"
    DREAM = "dream"
    OBSERVATION = "observation"
    MUSING = "musing"
    REACTION = "reaction"


# Emoji prefixes for different post types
POST_PREFIXES = {
    PostType.DIARY: "📓",
    PostType.DREAM: "🌙",
    PostType.OBSERVATION: "👁️",
    PostType.MUSING: "💭",
    PostType.REACTION: "↩️",
}

# Provenance footer divider (box drawings light quadruple dash)
PROVENANCE_DIVIDER = "\n┈┈ grounded in ┈┈"


@dataclass
class BroadcastPost:
    """A broadcast post from a character."""
    message_id: str
    channel_id: str
    character_name: str
    post_type: PostType
    content: str
    timestamp: datetime
    provenance: Optional[List[Dict[str, Any]]] = None


class BroadcastManager:
    """
    Manages posting character thoughts to the broadcast channel.
    """
    
    def __init__(self, bot: Optional[discord.Client] = None):
        self._bot = bot
        self._last_post_times: Dict[str, datetime] = {}  # character_name -> last post time
        self._cache = CacheManager()
    
    def set_bot(self, bot: discord.Client) -> None:
        """Set the Discord bot instance (called after bot is ready)."""
        self._bot = bot
    
    async def post_to_channel(
        self,
        content: str,
        post_type: PostType,
        character_name: str,
        provenance: Optional[List[Dict[str, Any]]] = None,
        reply_to: Optional[discord.Message] = None,
        files: Optional[List[discord.File]] = None,
        target_channel_id: Optional[str] = None
    ) -> List[discord.Message]:
        """
        Posts content to the bot broadcast channel(s).
        
        Args:
            content: The text content to post
            post_type: Type of post (diary, dream, observation, etc.)
            character_name: Name of the character posting
            provenance: Optional list of source data for grounding
            reply_to: Optional message to reply to (only works if in same channel)
            files: Optional list of files to attach
            target_channel_id: Optional specific channel to post to (overrides global broadcast channels)
            
        Returns:
            List of sent messages
        """
        if not settings.ENABLE_BOT_BROADCAST and not target_channel_id:
            logger.debug("Bot broadcast is disabled")
            return []
        
        # Determine target channels
        channel_ids = []
        if target_channel_id:
            channel_ids = [target_channel_id]
        else:
            channel_ids = settings.bot_broadcast_channel_ids_list
            
        if not channel_ids:
            logger.debug("No broadcast channel IDs configured")
            return []
        
        if not self._bot:
            logger.warning("Bot instance not set for broadcast manager")
            return []
        
        # Check rate limit (skip for targeted posts and scheduled posts like diary/dream)
        # Diary and dream posts are scheduled (once per day) so they shouldn't be rate-limited
        scheduled_post_types = {PostType.DIARY, PostType.DREAM}
        if not target_channel_id and post_type not in scheduled_post_types and not await self._can_post(character_name):
            logger.debug(f"Rate limit active for {character_name}")
            return []
        
        # Content safety check
        try:
            review = await content_safety_checker.review_content(content, post_type.value)
            if not review.safe:
                logger.warning(f"Broadcast blocked by safety review: {review.concerns}")
                return []
        except Exception as e:
            logger.warning(f"Safety review failed, blocking broadcast: {e}")
            return []
        
        # Format message with provenance footer
        formatted = self._format_broadcast(content, post_type, character_name, provenance)
        
        sent_messages = []
        
        for channel_id_str in channel_ids:
            try:
                channel_id = int(channel_id_str)
                channel = self._bot.get_channel(channel_id)
                if not channel:
                    try:
                        channel = await self._bot.fetch_channel(channel_id)
                    except discord.NotFound:
                        logger.error(f"Broadcast channel not found: {channel_id}")
                        continue
                    except discord.Forbidden:
                        logger.error(f"No permission to fetch broadcast channel {channel_id}")
                        continue
                
                if not channel or not isinstance(channel, discord.TextChannel):
                    logger.error(f"Broadcast channel not found or not a text channel: {channel_id}")
                    continue
                
                # Chunk message if over Discord's 2000 char limit
                message_chunks = chunk_message(formatted)
                
                # Send message(s)
                first_message = None
                for i, chunk in enumerate(message_chunks):
                    # Only attach files to the LAST chunk to ensure they appear at the bottom
                    chunk_files = files if (i == len(message_chunks) - 1) else None
                    
                    if i == 0 and reply_to and reply_to.channel.id == channel_id:
                        message = await reply_to.reply(chunk, files=chunk_files)
                    else:
                        message = await channel.send(chunk, files=chunk_files)
                    
                    if i == 0:
                        first_message = message
                
                if first_message:
                    sent_messages.append(first_message)
                    # Store broadcast record (use first message for reference)
                    await self._store_broadcast(first_message, post_type, character_name, content, provenance)
                    # Store as conversation memory so bot remembers posting it
                    await self._store_broadcast_memory(first_message, post_type, character_name, content)
                    
                    # Record activity for autonomous posting scaling (Phase E15)
                    # This ensures bot posts count toward channel activity levels
                    if hasattr(first_message, 'guild') and first_message.guild:
                        try:
                            await server_monitor.record_message(
                                guild_id=str(first_message.guild.id),
                                channel_id=str(first_message.channel.id)
                            )
                            logger.debug(f"Recorded activity for autonomous post in guild {first_message.guild.id}")
                        except Exception as e:
                            logger.debug(f"Failed to record activity for broadcast: {e}")
                
            except discord.Forbidden:
                logger.error(f"No permission to post in broadcast channel {channel_id_str}")
            except discord.HTTPException as e:
                logger.error(f"Failed to post broadcast to {channel_id_str}: {e}")
            except ValueError:
                logger.error(f"Invalid channel ID: {channel_id_str}")
        
        if sent_messages:
            # Update rate limit tracker
            self._last_post_times[character_name] = datetime.now(timezone.utc)
            
            # Update Redis for persistence across restarts
            try:
                key = f"broadcast:last_post:{character_name}"
                await self._cache.setex(
                    key,
                    settings.BOT_BROADCAST_MIN_INTERVAL_MINUTES * 60,
                    datetime.now(timezone.utc).isoformat()
                )
            except Exception as e:
                logger.warning(f"Failed to update broadcast rate limit in Redis: {e}")
            
            if len(sent_messages) < len(channel_ids):
                logger.warning(f"Broadcast partially failed for {character_name}: posted to {len(sent_messages)}/{len(channel_ids)} channels")
            else:
                logger.info(f"Broadcast posted by {character_name}: {post_type.value} to {len(sent_messages)} channels")
            
        return sent_messages
    
    async def _can_post(self, character_name: str) -> bool:
        """Check if character can post (respects rate limit)."""
        # Use Redis via cache manager
        try:
            key = f"broadcast:last_post:{character_name}"
            # Check if key exists (has TTL remaining)
            value = await self._cache.get(key)
            if value:
                return False
            return True
        except Exception as e:
            logger.warning(f"Redis rate limit check failed: {e}")
        
        # Fallback to in-memory
        last_post = self._last_post_times.get(character_name)
        if not last_post:
            return True
        
        min_interval = timedelta(minutes=settings.BOT_BROADCAST_MIN_INTERVAL_MINUTES)
        return datetime.now(timezone.utc) - last_post >= min_interval
    
    def _format_provenance_footer(
        self,
        provenance: Optional[List[Dict[str, Any]]]
    ) -> str:
        """
        Format provenance sources as a "grounded in" footer.
        
        Args:
            provenance: List of source dictionaries with 'type' and 'description'
            
        Returns:
            Formatted footer string, or empty string if no provenance
        """
        if not provenance or not settings.PROVENANCE_DISPLAY_ENABLED:
            return ""
        
        # Emoji mapping for source types
        source_emojis = {
            "conversation": "💬",
            "memory": "💭",
            "knowledge": "🔗",
            "channel": "🌐",
            "other_bot": "🤖",
            "community": "🌟",
            "observation": "👁️",
        }
        
        # Limit sources to avoid clutter
        sources_to_show = provenance[:settings.PROVENANCE_MAX_SOURCES]
        
        lines = []
        seen_descriptions = set()  # Deduplication
        
        for source in sources_to_show:
            source_type = source.get("type", "conversation")
            description = source.get("description", "")
            if not description:
                continue
            
            # Skip duplicates
            if description in seen_descriptions:
                continue
            seen_descriptions.add(description)
            
            # Log unknown source types for debugging
            if source_type not in source_emojis:
                logger.debug(f"Unknown provenance source type: {source_type}")
            
            emoji = source_emojis.get(source_type, "💬")
            
            # Add temporal context if available
            when = source.get("when", "")
            if when:
                lines.append(f"{emoji} {description} ({when})")
            else:
                lines.append(f"{emoji} {description}")
        
        if not lines:
            return ""
        
        # Build the footer
        footer_lines = [PROVENANCE_DIVIDER]
        footer_lines.extend(lines)
        
        return "\n".join(footer_lines)

    def _format_broadcast(
        self,
        content: str,
        post_type: PostType,
        character_name: str,
        provenance: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """Format the broadcast message with character name, header, and provenance footer."""
        
        # Check if content already has a header (e.g., "📝 DIARY ENTRY — December 03, 2025")
        has_header = any(marker in content[:50] for marker in ["📝", "🌙", "🌑", "✨", "☀️", "🌧️", "💭", "👁️"])
        
        if has_header:
            # Content already formatted with header
            main_content = f"**{character_name.title()}**\n{content}"
        else:
            # Add header based on post type
            tz = get_configured_timezone()
            now = datetime.now(tz)
            date_str = now.strftime("%B %d, %Y")
            time_str = now.strftime("%I:%M %p %Z")
            
            headers = {
                PostType.DIARY: "📝 DIARY ENTRY",
                PostType.DREAM: "🌙 DREAM JOURNAL",
                PostType.OBSERVATION: "👁️ OBSERVATION",
                PostType.MUSING: "💭 MUSING",
            }
            header = headers.get(post_type, "📝 ENTRY")
            
            main_content = f"**{character_name.title()}**\n{header} — {date_str}, {time_str}\n\n{content}"
        
        # Add provenance footer if available
        footer = self._format_provenance_footer(provenance)
        if footer:
            return f"{main_content}\n{footer}"
        
        return main_content
    
    async def _store_broadcast_memory(
        self,
        message: discord.Message,
        post_type: PostType,
        character_name: str,
        content: str
    ) -> None:
        """
        Store broadcast as a conversation memory so the bot remembers posting it.
        
        This creates a memory like: "I shared my dream journal in the broadcast channel"
        so when users reference "your dream post yesterday", the bot has context.
        """
        try:
            from src_v2.memory.manager import memory_manager
            from src_v2.memory.models import MemorySourceType
            
            # Create a concise summary of what was posted
            post_type_labels = {
                PostType.DIARY: "diary entry",
                PostType.DREAM: "dream journal",
                PostType.OBSERVATION: "observation",
                PostType.MUSING: "thought",
            }
            post_label = post_type_labels.get(post_type, "post")
            
            # Truncate content for the memory (first ~200 chars)
            content_preview = content[:200] + "..." if len(content) > 200 else content
            
            # Memory content: What I posted and a preview
            memory_content = f"I shared my {post_label} in the broadcast channel: {content_preview}"
            
            # Store as AI message (role="ai") with no user_id (broadcast, not to specific user)
            # Use a special "broadcast" user_id so it can be retrieved
            await memory_manager.add_message(
                user_id="__broadcast__",  # Special ID for broadcast memories
                character_name=character_name,
                role="ai",
                content=memory_content,
                channel_id=str(message.channel.id),
                message_id=str(message.id),
                source_type=MemorySourceType.INFERENCE,
                importance_score=4,  # Slightly above average importance
                metadata={
                    "post_type": post_type.value,
                    "is_broadcast": True
                }
            )
            
            logger.debug(f"Stored broadcast memory for {character_name}: {post_label}")
            
            # Broadcast posts are first-class data for learning!
            # The bot's own posts might contain insights worth extracting
            from src_v2.workers.task_queue import task_queue
            
            # Enqueue insight analysis to detect patterns in what the bot chooses to share
            try:
                await task_queue.enqueue_insight_analysis(
                    user_id="__broadcast__",
                    character_name=character_name,
                    trigger=f"broadcast_{post_type.value}",
                    priority=6  # Lower priority than user conversations
                )
            except Exception as e:
                logger.debug(f"Failed to enqueue broadcast insight analysis: {e}")
            
        except Exception as e:
            logger.warning(f"Failed to store broadcast memory: {e}")
    
    async def _store_broadcast(
        self,
        message: discord.Message,
        post_type: PostType,
        character_name: str,
        content: str,
        provenance: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """Store broadcast record in Redis for cross-bot discovery."""
        try:
            broadcast_data = {
                "message_id": str(message.id),
                "channel_id": str(message.channel.id),
                "character_name": character_name,
                "post_type": post_type.value,
                "content": content,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "provenance": provenance or []
            }
            
            # Store with 24h TTL
            key = f"broadcast:{character_name}:{message.id}"
            await self._cache.set_json(key, broadcast_data, ttl=86400)
            
            # Also add to a sorted set for chronological retrieval
            await self._cache.zadd(
                "broadcasts:recent",
                {key: datetime.now(timezone.utc).timestamp()}
            )
            
            # Trim old entries
            await self._cache.zremrangebyscore(
                "broadcasts:recent",
                "-inf",
                (datetime.now(timezone.utc) - timedelta(hours=24)).timestamp()
            )
            
        except Exception as e:
            logger.warning(f"Failed to store broadcast: {e}")
    
    async def get_recent_broadcasts(
        self,
        exclude_character: Optional[str] = None,
        hours: int = 24,
        limit: int = 20
    ) -> List[BroadcastPost]:
        """
        Get recent broadcasts for cross-bot discovery.
        
        Args:
            exclude_character: Exclude posts from this character
            hours: Look back this many hours
            limit: Maximum number of posts to return
            
        Returns:
            List of BroadcastPost objects, newest first
        """
        try:
            # Get recent broadcast keys
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp()
            keys = await self._cache.zrangebyscore(
                "broadcasts:recent",
                cutoff,
                "+inf"
            )
            
            posts = []
            for key in keys[-limit:]:  # Take most recent
                # Key stored in zset might be prefixed or not depending on how it was stored
                # But CacheManager handles prefixing for us.
                # Wait, the key stored IN the zset is the full key (e.g. "whisperengine:broadcast:...")?
                # In _store_broadcast, we stored `key` which was `f"broadcast:{character_name}:{message.id}"`
                # passed to `set_json`. `set_json` prefixes it.
                # But we passed `key` to `zadd` as the member.
                # So the member in zset is "broadcast:..." (unprefixed).
                # So we can just pass it to `get_json`.
                
                # However, if the old code stored it with `_redis_key`, it stored the PREFIXED key in the zset.
                # Old code: `key = _redis_key(...)` -> `zadd(..., {key: ...})`.
                # So the zset contains "whisperengine:broadcast:...".
                # If we pass "whisperengine:broadcast:..." to `self._cache.get_json`, it will double prefix!
                # "whisperengine:whisperengine:broadcast:..."
                
                # We need to handle this migration or just strip prefix.
                # Since this is a refactor, we should assume keys might be mixed or we just strip prefix.
                
                # Let's strip the prefix if present before passing to get_json
                clean_key = key
                if key.startswith(settings.REDIS_KEY_PREFIX):
                    clean_key = key[len(settings.REDIS_KEY_PREFIX):]
                
                data = await self._cache.get_json(clean_key)
                if data:
                    # data is already a dict from get_json
                    broadcast = data
                    
                    # Skip if from excluded character
                    if exclude_character and broadcast["character_name"] == exclude_character:
                        continue
                    
                    posts.append(BroadcastPost(
                        message_id=broadcast["message_id"],
                        channel_id=broadcast["channel_id"],
                        character_name=broadcast["character_name"],
                        post_type=PostType(broadcast["post_type"]),
                        content=broadcast["content"],
                        timestamp=datetime.fromisoformat(broadcast["timestamp"]),
                        provenance=broadcast.get("provenance")
                    ))
            
            # Sort newest first
            posts.sort(key=lambda p: p.timestamp, reverse=True)
            return posts
            
        except Exception as e:
            logger.warning(f"Failed to get recent broadcasts: {e}")
            return []
    
    async def post_dream(
        self,
        dream_content: str,
        character_name: str,
        provenance: Optional[List[Dict[str, Any]]] = None
    ) -> List[discord.Message]:
        """Convenience method to post a dream."""
        if not settings.BOT_BROADCAST_DREAMS:
            return []
        return await self.post_to_channel(
            dream_content,
            PostType.DREAM,
            character_name,
            provenance
        )
    
    async def post_diary(
        self,
        diary_content: str,
        character_name: str,
        provenance: Optional[List[Dict[str, Any]]] = None
    ) -> List[discord.Message]:
        """Convenience method to post a diary summary."""
        if not settings.BOT_BROADCAST_DIARIES:
            return []
        return await self.post_to_channel(
            diary_content,
            PostType.DIARY,
            character_name,
            provenance
        )
    
    async def post_observation(
        self,
        observation: str,
        character_name: str
    ) -> List[discord.Message]:
        """Convenience method to post an observation."""
        return await self.post_to_channel(
            observation,
            PostType.OBSERVATION,
            character_name
        )

    # --- Queue methods for worker (no Discord access) ---
    
    async def queue_broadcast(
        self,
        content: str,
        post_type: PostType,
        character_name: str,
        provenance: Optional[List[Dict[str, Any]]] = None,
        artifact_user_id: Optional[str] = None,
        target_channel_id: Optional[str] = None,
        target_user_id: Optional[str] = None
    ) -> bool:
        """
        Queue a broadcast for posting by the bot.
        Used by workers that don't have Discord access.
        
        Each bot has its own queue (broadcast:queue:{bot_name}) which it
        polls via the background task. This avoids race conditions.
        
        Args:
            content: The text content to post
            post_type: Type of post (diary, dream, etc.)
            character_name: Name of the character posting
            provenance: Optional source data
            artifact_user_id: If provided, bot will fetch pending artifacts for this user and attach them
            target_channel_id: Optional specific channel to post to (overrides global broadcast channels)
            target_user_id: Optional user ID to DM (overrides channel posting)
            
        Returns:
            True if queued successfully
        """
        try:
            queue_item = {
                "id": str(uuid.uuid4()),
                "content": content,
                "post_type": post_type.value,
                "character_name": character_name,
                "provenance": provenance or [],
                "queued_at": datetime.now(timezone.utc).isoformat(),
                "artifact_user_id": artifact_user_id,
                "target_channel_id": target_channel_id,
                "target_user_id": target_user_id
            }
            
            # Push to bot-specific queue (no more shared queue race conditions)
            bot_queue_key = f"broadcast:queue:{character_name.lower()}"
            await self._cache.rpush(
                bot_queue_key,
                json.dumps(queue_item)
            )
            
            logger.info(f"Queued {post_type.value} broadcast for {character_name} -> {bot_queue_key} (artifacts: {artifact_user_id}, target: {target_channel_id}, user: {target_user_id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to queue broadcast: {e}")
            return False
    
    async def queue_diary(
        self,
        diary_content: str,
        character_name: str,
        provenance: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Queue a diary broadcast (for workers without Discord access)."""
        if not settings.BOT_BROADCAST_DIARIES:
            return False
        return await self.queue_broadcast(
            diary_content,
            PostType.DIARY,
            character_name,
            provenance
        )
    
    async def process_queued_broadcasts(self) -> int:
        """
        Process all queued broadcasts (called by bot with Discord access).
        
        Each bot has its own queue (broadcast:queue:{bot_name}), so we only
        see items meant for this bot. No more race conditions!
        
        Returns:
            Number of broadcasts posted
        """
        if not self._bot:
            logger.debug("Bot not available to process broadcast queue")
            return 0
        
        posted = 0
        my_bot_name = settings.DISCORD_BOT_NAME.lower() if settings.DISCORD_BOT_NAME else ""
        queue_key = f"broadcast:queue:{my_bot_name}"
        
        try:
            # Process up to 10 items per call to avoid blocking
            for _ in range(10):
                item_json = await self._cache.lpop(queue_key)
                if not item_json:
                    break
                
                try:
                    item = json.loads(item_json)
                    
                    logger.debug(f"Processing queue item: type={item.get('post_type')}, id={item.get('id', 'unknown')}")
                    
                    # Validate target_user_id BEFORE extracting artifacts (which is destructive)
                    target_user_id_str = item.get("target_user_id")
                    if target_user_id_str:
                        if not target_user_id_str.isdigit() or len(target_user_id_str) < 17:
                            logger.warning(f"Invalid target_user_id '{target_user_id_str}' in queue - skipping (must be 17-20 digit Discord ID)")
                            continue
                    
                    # Fetch artifacts if specified (only after validation passes)
                    files = []
                    if item.get("artifact_user_id"):
                        # Note: This is destructive - artifacts are removed from pending list
                        files = await extract_pending_artifacts(item["artifact_user_id"])
                        if files:
                            logger.info(f"Attached {len(files)} artifacts to broadcast for {item['character_name']}")
                    
                    # Handle DM if target_user_id is present
                    if target_user_id_str:
                        try:
                            user_id = int(target_user_id_str)
                            user = await self._bot.fetch_user(user_id)
                            if user:
                                # Send DM
                                sent_msg = await user.send(item["content"], files=files)
                                posted += 1
                                logger.info(f"Sent queued DM to {user_id} from {item['character_name']}")
                                
                                # Save to memory/history
                                try:
                                    from src_v2.memory.manager import memory_manager
                                    await memory_manager.add_message(
                                        user_id=str(user_id),
                                        character_name=item["character_name"],
                                        role="ai",
                                        content=item["content"],
                                        user_name=user.name,
                                        channel_id=str(sent_msg.channel.id),
                                        message_id=str(sent_msg.id),
                                        metadata={"provenance": item.get("provenance"), "type": "proactive_dm"}
                                    )
                                except Exception as mem_err:
                                    logger.error(f"Failed to save DM to memory: {mem_err}")

                                continue
                            else:
                                logger.warning(f"Could not fetch user {user_id} for DM")
                        except Exception as e:
                            logger.error(f"Failed to send queued DM to {item.get('target_user_id')}: {e}")
                            continue

                    result = await self.post_to_channel(
                        content=item["content"],
                        post_type=PostType(item["post_type"]),
                        character_name=item["character_name"],
                        provenance=item.get("provenance"),
                        files=files,
                        target_channel_id=item.get("target_channel_id")
                    )
                    
                    if result:
                        posted += 1
                        logger.info(f"Posted queued {item['post_type']} for {item['character_name']}")
                    else:
                        logger.warning(f"post_to_channel returned None/empty for {item['post_type']}")
                    
                except Exception as e:
                    logger.warning(f"Failed to process queued broadcast: {e}")
            
        except Exception as e:
            logger.error(f"Error processing broadcast queue: {e}")
        
        return posted


# Global instance (bot will be set later)
broadcast_manager = BroadcastManager()
