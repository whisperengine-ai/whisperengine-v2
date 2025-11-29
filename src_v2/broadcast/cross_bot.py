"""
Cross-Bot Chat Manager (Phase E6)

Enables organic conversations between bot characters when they are mentioned
by each other or users in the broadcast channel.

Key Features:
- Detects when a bot is mentioned by another bot
- Tracks conversation chains to prevent infinite loops
- Respects cooldowns per channel
- Probabilistic engagement for natural feel
"""

import asyncio
import random
from typing import Optional, Dict, Any, List, Set
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
import discord
from loguru import logger

from src_v2.config.settings import settings
from src_v2.core.database import db_manager


@dataclass
class ConversationChain:
    """Tracks a bot-to-bot conversation chain."""
    channel_id: str
    participants: Set[str] = field(default_factory=set)  # Bot names in this chain
    message_count: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_message_id: Optional[str] = None
    last_bot: Optional[str] = None  # Last bot who spoke
    
    def add_message(self, bot_name: str, message_id: str) -> None:
        """Record a bot message in the chain."""
        self.participants.add(bot_name)
        self.message_count += 1
        self.last_message_id = message_id
        self.last_bot = bot_name
    
    def should_continue(self, max_chain: int) -> bool:
        """Check if this chain should continue."""
        return self.message_count < max_chain
    
    def is_expired(self, minutes: int = 5) -> bool:
        """Check if chain is expired (no activity for N minutes)."""
        return datetime.now(timezone.utc) - self.started_at > timedelta(minutes=minutes)


@dataclass
class CrossBotMention:
    """A mention of one bot by another (or by a user referencing both)."""
    channel_id: str
    message_id: str
    mentioned_bot: str  # The bot being mentioned
    mentioning_bot: Optional[str]  # The bot doing the mentioning (None if user)
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    chain_id: Optional[str] = None  # ID of the conversation chain


class CrossBotManager:
    """
    Manages cross-bot interactions and conversations.
    """
    
    def __init__(self, bot: Optional[discord.Client] = None, bot_name: Optional[str] = None):
        self._bot = bot
        self._bot_name = bot_name or settings.DISCORD_BOT_NAME
        self._known_bots: Dict[str, int] = {}  # bot_name -> discord_user_id
        self._active_chains: Dict[str, ConversationChain] = {}  # channel_id -> chain
        self._channel_cooldowns: Dict[str, datetime] = {}  # channel_id -> last_interaction_time
    
    def set_bot(self, bot: discord.Client) -> None:
        """Set the Discord bot instance."""
        self._bot = bot
    
    def register_known_bot(self, bot_name: str, discord_id: int) -> None:
        """Register a known bot for mention detection."""
        self._known_bots[bot_name.lower()] = discord_id
        logger.debug(f"Registered known bot: {bot_name} (ID: {discord_id})")
    
    async def load_known_bots(self) -> None:
        """Load known bots from Redis (populated by all running bots)."""
        if not db_manager.redis_client:
            return
        
        try:
            # Each bot registers itself on startup with a TTL (24 hours)
            # This ensures dead bots are eventually removed from the registry
            if self._bot and self._bot.user:
                key = f"crossbot:bot:{self._bot_name.lower() if self._bot_name else 'unknown'}"
                await db_manager.redis_client.set(
                    key,
                    str(self._bot.user.id),
                    ex=86400  # 24 hours TTL
                )
            
            # Load all known bots by scanning for keys
            # Pattern: crossbot:bot:*
            cursor = 0  # redis-py with decode_responses=True uses int cursor, not bytes
            while True:
                cursor, keys = await db_manager.redis_client.scan(cursor, match="crossbot:bot:*", count=100)
                for key in keys:
                    try:
                        # key is already str because decode_responses=True
                        if isinstance(key, bytes):
                            key_str = key.decode()
                        else:
                            key_str = key
                            
                        bot_name = key_str.split(":")[-1]
                        discord_id = await db_manager.redis_client.get(key)
                        
                        if discord_id:
                            # discord_id is also str
                            if isinstance(discord_id, bytes):
                                discord_id = discord_id.decode()
                            self._known_bots[bot_name] = int(discord_id)
                    except Exception as e:
                        logger.warning(f"Failed to parse bot key {key}: {e}")
                
                if cursor == 0:
                    break
            
            logger.info(f"Loaded {len(self._known_bots)} known bots for cross-bot detection")
        except Exception as e:
            logger.warning(f"Failed to load known bots: {e}")

    async def start_registration_loop(self) -> None:
        """Background task to refresh bot registration periodically."""
        while True:
            try:
                await self.load_known_bots()
            except Exception as e:
                logger.error(f"Registration loop error: {e}")
            # Refresh every hour
            await asyncio.sleep(3600)
    
    def is_known_bot(self, user_id: int) -> bool:
        """Check if a Discord user ID belongs to a known bot."""
        return user_id in self._known_bots.values()
    
    def get_bot_name(self, user_id: int) -> Optional[str]:
        """Get bot name from Discord user ID."""
        for name, did in self._known_bots.items():
            if did == user_id:
                return name
        return None
    
    def is_on_cooldown(self, channel_id: str) -> bool:
        """Check if channel is on cooldown for cross-bot chat."""
        last_time = self._channel_cooldowns.get(channel_id)
        if not last_time:
            return False
        
        cooldown = timedelta(minutes=settings.CROSS_BOT_COOLDOWN_MINUTES)
        return datetime.now(timezone.utc) - last_time < cooldown
    
    def _set_cooldown(self, channel_id: str) -> None:
        """Set cooldown for a channel."""
        self._channel_cooldowns[channel_id] = datetime.now(timezone.utc)
    
    def _get_or_create_chain(self, channel_id: str) -> ConversationChain:
        """Get existing chain or create new one."""
        chain = self._active_chains.get(channel_id)
        
        # Create new chain if none exists or current is expired
        if not chain or chain.is_expired():
            chain = ConversationChain(channel_id=channel_id)
            self._active_chains[channel_id] = chain
        
        return chain
    
    def _cleanup_expired_chains(self) -> None:
        """Remove expired conversation chains."""
        expired = [
            cid for cid, chain in self._active_chains.items()
            if chain.is_expired()
        ]
        for cid in expired:
            del self._active_chains[cid]
    
    async def detect_cross_bot_mention(
        self,
        message: discord.Message
    ) -> Optional[CrossBotMention]:
        """
        Detect if this message mentions our bot from another bot.
        
        Returns CrossBotMention if we should potentially respond, None otherwise.
        """
        if not settings.ENABLE_CROSS_BOT_CHAT:
            return None
        
        if not self._bot or not self._bot.user:
            return None
        
        # Must be from another bot
        if not message.author.bot:
            return None
        
        # Must not be from ourselves
        if message.author.id == self._bot.user.id:
            return None
        
        # Must be a known bot (not random bots)
        if not self.is_known_bot(message.author.id):
            return None
        
        # Must mention us
        if self._bot.user not in message.mentions:
            # Also check for name mentions in content
            # Use regex to ensure word boundaries to avoid partial matches (e.g. "dreaming" matching "dream")
            import re
            our_name = self._bot_name.lower() if self._bot_name else ""
            if not our_name:
                return None
                
            # Escape name for regex safety
            escaped_name = re.escape(our_name)
            # Look for whole word match, case insensitive
            if not re.search(rf"\b{escaped_name}\b", message.content.lower()):
                return None
        
        # Check channel cooldown
        channel_id = str(message.channel.id)
        if self.is_on_cooldown(channel_id):
            logger.debug(f"Cross-bot cooldown active for channel {channel_id}")
            return None
        
        # Check chain limit
        chain = self._get_or_create_chain(channel_id)
        if not chain.should_continue(settings.CROSS_BOT_MAX_CHAIN):
            logger.debug(f"Cross-bot chain limit reached in channel {channel_id}")
            return None
        
        # Don't respond if we were the last bot in the chain
        if chain.last_bot == self._bot_name:
            logger.debug("We were the last bot to speak, skipping")
            return None
        
        mentioning_bot = self.get_bot_name(message.author.id)
        
        return CrossBotMention(
            channel_id=channel_id,
            message_id=str(message.id),
            mentioned_bot=self._bot_name or "unknown",
            mentioning_bot=mentioning_bot,
            content=message.content,
            chain_id=channel_id
        )
    
    async def should_respond(self, mention: CrossBotMention) -> bool:
        """
        Decide probabilistically whether to respond to a cross-bot mention.
        """
        # Always respond if chain just started (first bot-to-bot exchange)
        chain = self._active_chains.get(mention.channel_id)
        if chain and chain.message_count == 0:
            return True
        
        # Probabilistic response based on config
        return random.random() < settings.CROSS_BOT_RESPONSE_CHANCE
    
    async def record_response(
        self,
        channel_id: str,
        message_id: str
    ) -> None:
        """Record that we responded in a cross-bot conversation."""
        chain = self._get_or_create_chain(channel_id)
        chain.add_message(self._bot_name or "unknown", message_id)
        self._set_cooldown(channel_id)
        
        logger.info(f"Recorded cross-bot response in chain (count: {chain.message_count})")
    
    async def queue_cross_bot_mention(self, mention: CrossBotMention) -> bool:
        """
        Queue a cross-bot mention for processing.
        Uses Redis to coordinate across bot instances.
        
        NOTE: This is currently unused in the direct on_message flow, but is intended
        for future use cases where bots might be sharded or need to handle mentions
        asynchronously (e.g. broadcast channel events).
        """
        if not db_manager.redis_client:
            return False
        
        try:
            import json
            
            mention_data = {
                "channel_id": mention.channel_id,
                "message_id": mention.message_id,
                "mentioned_bot": mention.mentioned_bot,
                "mentioning_bot": mention.mentioning_bot,
                "content": mention.content,
                "timestamp": mention.timestamp.isoformat()
            }
            
            # Queue for the mentioned bot to process
            queue_key = f"crossbot:mentions:{mention.mentioned_bot}"
            await db_manager.redis_client.rpush(queue_key, json.dumps(mention_data))
            
            # Set TTL on queue (5 minutes)
            await db_manager.redis_client.expire(queue_key, 300)
            
            logger.debug(f"Queued cross-bot mention for {mention.mentioned_bot}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to queue cross-bot mention: {e}")
            return False
    
    async def process_queued_mentions(self) -> List[CrossBotMention]:
        """
        Process queued mentions for this bot.
        Returns list of mentions to respond to.
        """
        if not db_manager.redis_client:
            return []
        
        if not self._bot_name:
            return []
        
        mentions = []
        queue_key = f"crossbot:mentions:{self._bot_name}"
        
        try:
            import json
            
            # Process up to 5 mentions per call
            for _ in range(5):
                data = await db_manager.redis_client.lpop(queue_key)
                if not data:
                    break
                
                mention_data = json.loads(data)
                mention = CrossBotMention(
                    channel_id=mention_data["channel_id"],
                    message_id=mention_data["message_id"],
                    mentioned_bot=mention_data["mentioned_bot"],
                    mentioning_bot=mention_data.get("mentioning_bot"),
                    content=mention_data["content"],
                    timestamp=datetime.fromisoformat(mention_data["timestamp"])
                )
                
                # Check if we should respond
                if await self.should_respond(mention):
                    mentions.append(mention)
                else:
                    logger.debug(f"Skipping mention (probability check)")
            
        except Exception as e:
            logger.error(f"Failed to process queued mentions: {e}")
        
        return mentions


# Global instance (bot will be set later)
cross_bot_manager = CrossBotManager()
