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
    ) -> Optional[discord.Message]:
        """
        Posts content to the bot broadcast channel.
        
        Args:
            content: The text content to post
            post_type: Type of post (diary, dream, observation, etc.)
            character_name: Name of the character posting
            provenance: Optional list of source data for grounding
            reply_to: Optional message to reply to
            
        Returns:
            The sent message, or None if posting failed/blocked
        """
        if not settings.ENABLE_BOT_BROADCAST:
            logger.debug("Bot broadcast is disabled")
            return None
        
        if not settings.BOT_BROADCAST_CHANNEL_ID:
            logger.debug("No broadcast channel ID configured")
            return None
        
        if not self._bot:
            logger.warning("Bot instance not set for broadcast manager")
            return None
        
        # Check rate limit
        if not await self._can_post(character_name):
            logger.debug(f"Rate limit active for {character_name}")
            return None
        
        # Content safety check
        try:
            review = await content_safety_checker.review_content(content, post_type.value)
            if not review.safe:
                logger.warning(f"Broadcast blocked by safety review: {review.concerns}")
                return None
        except Exception as e:
            logger.warning(f"Safety review failed, blocking broadcast: {e}")
            return None
        
        # Format message
        formatted = self._format_broadcast(content, post_type, character_name)
        
        try:
            channel = self._bot.get_channel(int(settings.BOT_BROADCAST_CHANNEL_ID))
            if not channel:
                channel = await self._bot.fetch_channel(int(settings.BOT_BROADCAST_CHANNEL_ID))
            
            if not channel or not isinstance(channel, discord.TextChannel):
                logger.error(f"Broadcast channel not found or not a text channel: {settings.BOT_BROADCAST_CHANNEL_ID}")
                return None
            
            # Send message
            if reply_to:
                message = await reply_to.reply(formatted)
            else:
                message = await channel.send(formatted)
            
            # Update rate limit tracker
            self._last_post_times[character_name] = datetime.now(timezone.utc)
            
            # Store broadcast record
            await self._store_broadcast(message, post_type, character_name, content, provenance)
            
            logger.info(f"Broadcast posted by {character_name}: {post_type.value}")
            return message
            
        except discord.Forbidden:
            logger.error(f"No permission to post in broadcast channel {settings.BOT_BROADCAST_CHANNEL_ID}")
            return None
        except discord.HTTPException as e:
            logger.error(f"Failed to post broadcast: {e}")
            return None
    
    async def _can_post(self, character_name: str) -> bool:
        """Check if character can post (respects rate limit)."""
        last_post = self._last_post_times.get(character_name)
        if not last_post:
            return True
        
        min_interval = timedelta(minutes=settings.BOT_BROADCAST_MIN_INTERVAL_MINUTES)
        return datetime.now(timezone.utc) - last_post >= min_interval
    
    def _format_broadcast(self, content: str, post_type: PostType, character_name: str) -> str:
        """Format the broadcast message with appropriate prefix."""
        prefix = POST_PREFIXES.get(post_type, "💬")
        return f"{prefix} **{character_name.title()}**\n{content}"
    
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
            key = f"broadcast:{character_name}:{message.id}"
            await db_manager.redis_client.set(
                key,
                json.dumps(broadcast_data),
                ex=86400  # 24 hours
            )
            
            # Also add to a sorted set for chronological retrieval
            await db_manager.redis_client.zadd(
                "broadcasts:recent",
                {key: datetime.now(timezone.utc).timestamp()}
            )
            
            # Trim old entries
            await db_manager.redis_client.zremrangebyscore(
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
        if not db_manager.redis_client:
            return []
        
        try:
            import json
            
            # Get recent broadcast keys
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp()
            keys = await db_manager.redis_client.zrangebyscore(
                "broadcasts:recent",
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
    ) -> Optional[discord.Message]:
        """Convenience method to post a dream."""
        if not settings.BOT_BROADCAST_DREAMS:
            return None
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
    ) -> Optional[discord.Message]:
        """Convenience method to post a diary summary."""
        if not settings.BOT_BROADCAST_DIARIES:
            return None
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
    ) -> Optional[discord.Message]:
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
        Queue a broadcast for later posting by the bot.
        Used by workers that don't have Discord access.
        
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
            
            # Push to queue (list)
            await db_manager.redis_client.rpush(
                "broadcast:queue",
                json.dumps(queue_item)
            )
            
            logger.info(f"Queued {post_type.value} broadcast for {character_name}")
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
        
        Returns:
            Number of broadcasts posted
        """
        if not self._bot:
            logger.debug("Bot not available to process broadcast queue")
            return 0
        
        if not db_manager.redis_client:
            return 0
        
        posted = 0
        requeue_items = []  # Items for other bots
        my_bot_name = settings.DISCORD_BOT_NAME.lower() if settings.DISCORD_BOT_NAME else ""
        
        try:
            import json
            
            # Process up to 10 items per call to avoid blocking
            for _ in range(10):
                item_json = await db_manager.redis_client.lpop("broadcast:queue")
                if not item_json:
                    break
                
                try:
                    item = json.loads(item_json)
                    item_bot_name = item.get("character_name", "").lower()
                    
                    # Only process broadcasts for THIS bot
                    if item_bot_name != my_bot_name:
                        # Not for us - requeue it
                        requeue_items.append(item_json)
                        continue
                    
                    result = await self.post_to_channel(
                        content=item["content"],
                        post_type=PostType(item["post_type"]),
                        character_name=item["character_name"],
                        provenance=item.get("provenance")
                    )
                    
                    if result:
                        posted += 1
                        logger.info(f"Posted queued {item['post_type']} from {item['character_name']}")
                    
                except Exception as e:
                    logger.warning(f"Failed to process queued broadcast: {e}")
            
            # Requeue items for other bots
            for item_json in requeue_items:
                await db_manager.redis_client.rpush("broadcast:queue", item_json)
            
        except Exception as e:
            logger.error(f"Error processing broadcast queue: {e}")
        
        return posted


# Global instance (bot will be set later)
broadcast_manager = BroadcastManager()
