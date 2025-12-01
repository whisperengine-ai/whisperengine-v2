"""
Bot Broadcast Manager (Phase E8)

Posts character thoughts, dreams, and observations to a public Discord channel.
Enables cross-bot discovery and reactions for emergent character awareness.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from enum import Enum
import discord
from loguru import logger

from src_v2.config.settings import settings
from src_v2.core.database import db_manager
from src_v2.safety.content_review import content_safety_checker
from src_v2.discord.utils.message_utils import chunk_message


def _redis_key(key: str) -> str:
    """Apply Redis namespace prefix."""
    prefix = settings.REDIS_KEY_PREFIX
    if key.startswith(prefix):
        return key
    return f"{prefix}{key}"


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
    
    def set_bot(self, bot: discord.Client) -> None:
        """Set the Discord bot instance (called after bot is ready)."""
        self._bot = bot
    
    async def post_to_channel(
        self,
        content: str,
        post_type: PostType,
        character_name: str,
        provenance: Optional[List[Dict[str, Any]]] = None,
        reply_to: Optional[discord.Message] = None
    ) -> List[discord.Message]:
        """
        Posts content to the bot broadcast channel(s).
        
        Args:
            content: The text content to post
            post_type: Type of post (diary, dream, observation, etc.)
            character_name: Name of the character posting
            provenance: Optional list of source data for grounding
            reply_to: Optional message to reply to (only works if in same channel)
            
        Returns:
            List of sent messages
        """
        if not settings.ENABLE_BOT_BROADCAST:
            logger.debug("Bot broadcast is disabled")
            return []
        
        channel_ids = settings.bot_broadcast_channel_ids_list
        if not channel_ids:
            logger.debug("No broadcast channel IDs configured")
            return []
        
        if not self._bot:
            logger.warning("Bot instance not set for broadcast manager")
            return []
        
        # Check rate limit
        if not await self._can_post(character_name):
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
                    if i == 0 and reply_to and reply_to.channel.id == channel_id:
                        message = await reply_to.reply(chunk)
                    else:
                        message = await channel.send(chunk)
                    
                    if i == 0:
                        first_message = message
                
                if first_message:
                    sent_messages.append(first_message)
                    # Store broadcast record (use first message for reference)
                    await self._store_broadcast(first_message, post_type, character_name, content, provenance)
                
            except discord.Forbidden:
                logger.error(f"No permission to post in broadcast channel {channel_id_str}")
            except discord.HTTPException as e:
                logger.error(f"Failed to post broadcast to {channel_id_str}: {e}")
            except ValueError:
                logger.error(f"Invalid channel ID: {channel_id_str}")
        
        if sent_messages:
            # Update rate limit tracker
            self._last_post_times[character_name] = datetime.now(timezone.utc)
            
            if len(sent_messages) < len(channel_ids):
                logger.warning(f"Broadcast partially failed for {character_name}: posted to {len(sent_messages)}/{len(channel_ids)} channels")
            else:
                logger.info(f"Broadcast posted by {character_name}: {post_type.value} to {len(sent_messages)} channels")
            
        return sent_messages
    
    async def _can_post(self, character_name: str) -> bool:
        """Check if character can post (respects rate limit)."""
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
        """Format the broadcast message with character name and provenance footer."""
        # Content already has full header: "🌙 DREAM JOURNAL — December 02, 2024..."
        # Just prepend character name
        main_content = f"**{character_name.title()}**\n{content}"
        
        # Add provenance footer if available
        footer = self._format_provenance_footer(provenance)
        if footer:
            return f"{main_content}\n{footer}"
        
        return main_content
    
    async def _store_broadcast(
        self,
        message: discord.Message,
        post_type: PostType,
        character_name: str,
        content: str,
        provenance: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """Store broadcast record in Redis for cross-bot discovery."""
        if not db_manager.redis_client:
            return
        
        try:
            import json
            
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
            key = _redis_key(f"broadcast:{character_name}:{message.id}")
            await db_manager.redis_client.set(
                key,
                json.dumps(broadcast_data),
                ex=86400  # 24 hours
            )
            
            # Also add to a sorted set for chronological retrieval
            await db_manager.redis_client.zadd(
                _redis_key("broadcasts:recent"),
                {key: datetime.now(timezone.utc).timestamp()}
            )
            
            # Trim old entries
            await db_manager.redis_client.zremrangebyscore(
                _redis_key("broadcasts:recent"),
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
        if not db_manager.redis_client:
            return []
        
        try:
            import json
            
            # Get recent broadcast keys
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp()
            keys = await db_manager.redis_client.zrangebyscore(
                _redis_key("broadcasts:recent"),
                cutoff,
                "+inf"
            )
            
            posts = []
            for key in keys[-limit:]:  # Take most recent
                data = await db_manager.redis_client.get(key)
                if data:
                    broadcast = json.loads(data)
                    
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
        provenance: Optional[List[Dict[str, Any]]] = None
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
            
        Returns:
            True if queued successfully
        """
        if not db_manager.redis_client:
            logger.warning("Redis not available for broadcast queue")
            return False
        
        try:
            import json
            import uuid
            
            queue_item = {
                "id": str(uuid.uuid4()),
                "content": content,
                "post_type": post_type.value,
                "character_name": character_name,
                "provenance": provenance or [],
                "queued_at": datetime.now(timezone.utc).isoformat()
            }
            
            # Push to bot-specific queue (no more shared queue race conditions)
            bot_queue_key = _redis_key(f"broadcast:queue:{character_name.lower()}")
            await db_manager.redis_client.rpush(
                bot_queue_key,
                json.dumps(queue_item)
            )
            
            logger.info(f"Queued {post_type.value} broadcast for {character_name} -> {bot_queue_key}")
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
        
        if not db_manager.redis_client:
            return 0
        
        posted = 0
        my_bot_name = settings.DISCORD_BOT_NAME.lower() if settings.DISCORD_BOT_NAME else ""
        queue_key = _redis_key(f"broadcast:queue:{my_bot_name}")
        
        try:
            import json
            
            # Process up to 10 items per call to avoid blocking
            for _ in range(10):
                item_json = await db_manager.redis_client.lpop(queue_key)
                if not item_json:
                    break
                
                try:
                    item = json.loads(item_json)
                    
                    logger.debug(f"Processing queue item: type={item.get('post_type')}, id={item.get('id', 'unknown')}")
                    
                    result = await self.post_to_channel(
                        content=item["content"],
                        post_type=PostType(item["post_type"]),
                        character_name=item["character_name"],
                        provenance=item.get("provenance")
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
