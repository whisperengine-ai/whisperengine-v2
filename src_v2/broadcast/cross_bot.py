"""
Cross-Bot Chat Manager (Phase E6)

Enables organic conversations between bot characters when they are mentioned
by each other or users in the broadcast channel.

Key Features:
- Detects when a bot is mentioned by another bot
- Tracks conversation chains to prevent infinite loops
- Respects cooldowns per channel
- Probabilistic engagement for natural feel

State Management (Redis-backed for cross-bot coordination):
- Cooldowns: Redis TTL keys (auto-expire, no cleanup needed)
- Active Chains: Redis hash (shared chain state across all bots)
- Burst Detection: Redis TTL keys (30s auto-expire)
- Known Bots: Redis keys with 24h TTL (bot registry)
"""

import asyncio
import json
import random
from typing import Optional, Dict, List, Set
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
import discord
from loguru import logger

from src_v2.config.settings import settings
from src_v2.core.database import db_manager


# Redis key prefixes for cross-bot state
REDIS_PREFIX_COOLDOWN = "crossbot:cooldown:"      # TTL-based, auto-expires
REDIS_PREFIX_CHAIN = "crossbot:chain:"            # Hash with chain state
REDIS_PREFIX_BURST = "crossbot:burst:"            # TTL-based, 30s auto-expire
REDIS_PREFIX_BOT = "crossbot:bot:"                # Bot registry, 24h TTL
REDIS_PREFIX_LOCK = "crossbot:lock:"              # Distributed lock for chain ops

# TTL constants
CHAIN_EXPIRE_MINUTES = 10  # Chains expire after 10 min of inactivity
BURST_EXPIRE_SECONDS = 30  # Burst detection window
LOCK_EXPIRE_SECONDS = 30   # Max time a lock can be held (prevents deadlocks)


def _redis_key(key: str) -> str:
    """Apply Redis namespace prefix."""
    prefix = settings.REDIS_KEY_PREFIX
    if key.startswith(prefix):
        return key
    return f"{prefix}{key}"


@dataclass
class ConversationChain:
    """Tracks a bot-to-bot conversation chain (Redis-serializable)."""
    channel_id: str
    participants: Set[str] = field(default_factory=set)  # Bot names in this chain
    message_count: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_message_id: Optional[str] = None
    last_bot: Optional[str] = None  # Last bot who spoke
    
    def add_message(self, bot_name: str, message_id: str) -> None:
        """Record a bot message in the chain."""
        self.participants.add(bot_name)
        self.message_count += 1
        self.last_message_id = message_id
        self.last_bot = bot_name
        self.last_activity_at = datetime.now(timezone.utc)  # Update activity time
    
    def should_continue(self, max_chain: int) -> bool:
        """Check if this chain should continue."""
        return self.message_count < max_chain
    
    def is_expired(self, minutes: int = CHAIN_EXPIRE_MINUTES) -> bool:
        """Check if chain is expired (no activity for N minutes)."""
        return datetime.now(timezone.utc) - self.last_activity_at > timedelta(minutes=minutes)
    
    def to_dict(self) -> dict:
        """Serialize to dict for Redis storage."""
        return {
            "channel_id": self.channel_id,
            "participants": list(self.participants),
            "message_count": self.message_count,
            "started_at": self.started_at.isoformat(),
            "last_activity_at": self.last_activity_at.isoformat(),
            "last_message_id": self.last_message_id,
            "last_bot": self.last_bot,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ConversationChain":
        """Deserialize from Redis dict."""
        return cls(
            channel_id=data["channel_id"],
            participants=set(data.get("participants", [])),
            message_count=data.get("message_count", 0),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else datetime.now(timezone.utc),
            last_activity_at=datetime.fromisoformat(data["last_activity_at"]) if data.get("last_activity_at") else datetime.now(timezone.utc),
            last_message_id=data.get("last_message_id"),
            last_bot=data.get("last_bot"),
        )


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
    is_direct_mention: bool = True  # True if @mention, False if just name-in-text
    is_direct_reply: bool = False  # True if replying to our message


class CrossBotManager:
    """
    Manages cross-bot interactions and conversations.
    
    All shared state is stored in Redis for cross-bot coordination:
    - Cooldowns: TTL keys that auto-expire (no cleanup needed)
    - Chains: JSON in Redis with TTL refresh on activity
    - Burst detection: TTL keys (30s window)
    - Bot registry: TTL keys (24h, refreshed on startup)
    
    Local caches are kept for fast-path reads but Redis is authoritative.
    """
    
    def __init__(self, bot: Optional[discord.Client] = None, bot_name: Optional[str] = None):
        self._bot = bot
        self._bot_name = bot_name or settings.DISCORD_BOT_NAME
        # Local caches (fast path, Redis is authoritative)
        self._known_bots: Dict[str, int] = {}  # bot_name -> discord_user_id
        self._chain_cache: Dict[str, ConversationChain] = {}  # channel_id -> chain (local cache)
    
    @property
    def known_bots(self) -> Dict[str, int]:
        """Return a copy of known bots."""
        return self._known_bots.copy()

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
                key = _redis_key(f"crossbot:bot:{self._bot_name.lower() if self._bot_name else 'unknown'}")
                await db_manager.redis_client.set(
                    key,
                    str(self._bot.user.id),
                    ex=86400  # 24 hours TTL
                )
            
            # Load all known bots by scanning for keys
            # Pattern: crossbot:bot:*
            cursor = 0  # redis-py with decode_responses=True uses int cursor, not bytes
            pattern = _redis_key("crossbot:bot:*")
            while True:
                cursor, keys = await db_manager.redis_client.scan(cursor, match=pattern, count=100)
                for key in keys:
                    try:
                        # key is already str because decode_responses=True
                        if isinstance(key, bytes):
                            key_str = key.decode()
                        else:
                            key_str = key
                        
                        # Extract bot name from key (format: whisper:crossbot:bot:name)
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
        """Background task to refresh bot registration. No cleanup needed - Redis TTLs handle expiration."""
        while True:
            try:
                await self.load_known_bots()
                # No local cleanup needed - Redis TTLs auto-expire cooldowns, chains, and burst keys
            except Exception as e:
                logger.error(f"Registration loop error: {e}")
            # Refresh every hour
            await asyncio.sleep(3600)
    
    # ========== Redis-backed State Management ==========
    
    async def _get_chain_from_redis(self, channel_id: str) -> Optional[ConversationChain]:
        """Get conversation chain from Redis."""
        if not db_manager.redis_client:
            return self._chain_cache.get(channel_id)
        
        try:
            key = _redis_key(f"{REDIS_PREFIX_CHAIN}{channel_id}")
            data = await db_manager.redis_client.get(key)
            if data:
                chain = ConversationChain.from_dict(json.loads(data))
                self._chain_cache[channel_id] = chain  # Update local cache
                return chain
        except Exception as e:
            logger.debug(f"Failed to get chain from Redis: {e}")
        
        return self._chain_cache.get(channel_id)
    
    async def _save_chain_to_redis(self, chain: ConversationChain) -> None:
        """Save conversation chain to Redis with TTL."""
        self._chain_cache[chain.channel_id] = chain  # Update local cache
        
        if not db_manager.redis_client:
            return
        
        try:
            key = _redis_key(f"{REDIS_PREFIX_CHAIN}{chain.channel_id}")
            ttl_seconds = CHAIN_EXPIRE_MINUTES * 60
            await db_manager.redis_client.setex(
                key, 
                ttl_seconds, 
                json.dumps(chain.to_dict())
            )
        except Exception as e:
            logger.debug(f"Failed to save chain to Redis: {e}")
    
    async def _delete_chain_from_redis(self, channel_id: str) -> None:
        """Delete conversation chain from Redis."""
        self._chain_cache.pop(channel_id, None)
        
        if not db_manager.redis_client:
            return
        
        try:
            key = _redis_key(f"{REDIS_PREFIX_CHAIN}{channel_id}")
            await db_manager.redis_client.delete(key)
        except Exception as e:
            logger.debug(f"Failed to delete chain from Redis: {e}")
    
    async def _check_burst(self, channel_id: str, bot_name: str) -> bool:
        """Check if this is a burst message (same bot posted within 30s). Uses Redis TTL.
        
        Uses atomic SET NX EX to avoid race conditions between EXISTS and SETEX.
        """
        burst_key = _redis_key(f"{REDIS_PREFIX_BURST}{channel_id}:{bot_name}")
        
        if not db_manager.redis_client:
            # Fallback: always allow (no burst detection without Redis)
            return False
        
        try:
            # Atomic: SET key value NX EX seconds
            # Returns True if key was SET (no burst), None/False if key already exists (burst)
            was_set = await db_manager.redis_client.set(
                burst_key, "1", nx=True, ex=BURST_EXPIRE_SECONDS
            )
            return not was_set  # True = burst (key existed), False = no burst (key was set)
        except Exception as e:
            logger.debug(f"Burst check failed: {e}")
            return False

    # ========== Distributed Lock for Race Condition Prevention ==========
    
    async def acquire_response_lock(self, channel_id: str) -> bool:
        """
        Acquire a distributed lock for responding in a channel.
        
        This prevents multiple bots from responding simultaneously to the same
        channel, which would cause message storms and chain count race conditions.
        
        Returns:
            True if lock acquired, False if another bot is already responding
        """
        if not db_manager.redis_client:
            # No Redis = no distributed coordination, allow response
            return True
        
        lock_key = _redis_key(f"{REDIS_PREFIX_LOCK}{channel_id}")
        lock_value = f"{self._bot_name}:{datetime.now(timezone.utc).isoformat()}"
        
        try:
            # Atomic: SET key value NX EX seconds
            # NX = only set if doesn't exist
            # EX = auto-expire to prevent deadlocks
            was_set = await db_manager.redis_client.set(
                lock_key, lock_value, nx=True, ex=LOCK_EXPIRE_SECONDS
            )
            if was_set:
                logger.debug(f"[CrossBot] Acquired response lock for channel {channel_id}")
                return True
            else:
                # Another bot has the lock
                existing = await db_manager.redis_client.get(lock_key)
                logger.info(f"[CrossBot] Lock held by another bot: {existing} - skipping response")
                return False
        except Exception as e:
            logger.warning(f"[CrossBot] Lock acquisition failed: {e}")
            # On error, be conservative and skip the response
            return False
    
    async def release_response_lock(self, channel_id: str) -> None:
        """Release the response lock for a channel (only if we own it)."""
        if not db_manager.redis_client:
            return
        
        lock_key = _redis_key(f"{REDIS_PREFIX_LOCK}{channel_id}")
        
        try:
            # Only release if we own the lock (prevents releasing another bot's lock)
            current = await db_manager.redis_client.get(lock_key)
            if current and current.startswith(f"{self._bot_name}:"):
                await db_manager.redis_client.delete(lock_key)
                logger.debug(f"[CrossBot] Released response lock for channel {channel_id}")
            elif current:
                logger.warning(f"[CrossBot] Lock owned by another bot, not releasing: {current}")
            # If current is None, lock already expired - nothing to release
        except Exception as e:
            logger.debug(f"[CrossBot] Lock release failed: {e}")

    async def _get_atomic_chain_count(self, channel_id: str) -> int:
        """Get the current chain count using the atomic counter key."""
        if not db_manager.redis_client:
            # Fallback to old chain object
            chain = await self._get_chain_from_redis(channel_id)
            return chain.message_count if chain else 0
        
        count_key = _redis_key(f"{REDIS_PREFIX_CHAIN}{channel_id}:count")
        
        try:
            count = await db_manager.redis_client.get(count_key)
            return int(count) if count else 0
        except Exception as e:
            logger.debug(f"[CrossBot] Failed to get atomic count: {e}")
            return 0
    
    async def _get_last_bot(self, channel_id: str) -> Optional[str]:
        """Get the last bot who spoke in the chain from metadata."""
        if not db_manager.redis_client:
            # Fallback to old chain object
            chain = await self._get_chain_from_redis(channel_id)
            return chain.last_bot if chain else None
        
        meta_key = _redis_key(f"{REDIS_PREFIX_CHAIN}{channel_id}:meta")
        
        try:
            data = await db_manager.redis_client.get(meta_key)
            if data:
                meta = json.loads(data)
                return meta.get("last_bot")
        except Exception as e:
            logger.debug(f"[CrossBot] Failed to get last bot: {e}")
        
        return None

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
        """Sync version: Check if channel is on cooldown (local cache only).
        
        DEPRECATED: Use is_on_cooldown_async() for accurate Redis-backed check.
        This method only checks local memory and may not see cooldowns set by other bots.
        """
        # This is a best-effort sync check - Redis is authoritative
        # The async version should be used whenever possible
        return False  # Conservative: assume not on cooldown, let async check handle it
    
    async def is_on_cooldown_async(self, channel_id: str) -> bool:
        """Async version: Check if channel is on cooldown (shared via Redis with TTL)."""
        if db_manager.redis_client:
            try:
                key = _redis_key(f"{REDIS_PREFIX_COOLDOWN}{channel_id}")
                ttl = await db_manager.redis_client.ttl(key)
                if ttl > 0:
                    return True
            except Exception as e:
                logger.debug(f"Redis cooldown check failed: {e}")
        
        # No Redis or Redis check failed - assume not on cooldown
        # Redis TTL is the authoritative source for cooldowns
        return False
    
    async def has_active_conversation_async(self, channel_id: str) -> bool:
        """Check if there's an active (non-expired) conversation chain in this channel (Redis-backed)."""
        chain = await self._get_chain_from_redis(channel_id)
        if not chain:
            return False
        return not chain.is_expired() and chain.message_count > 0
    
    def has_active_conversation(self, channel_id: str) -> bool:
        """Check if there's an active conversation (local cache only, use async for Redis)."""
        chain = self._chain_cache.get(channel_id)
        if not chain:
            return False
        return not chain.is_expired() and chain.message_count > 0

    async def is_last_turn_async(self, channel_id: str) -> bool:
        """Check if the next response would be the last turn in the chain (Redis-backed)."""
        chain = await self._get_chain_from_redis(channel_id)
        if not chain:
            return False
        return (chain.message_count + 1) >= settings.CROSS_BOT_MAX_CHAIN

    async def get_conversation_phase_async(self, channel_id: str) -> str:
        """
        Get a soft hint about the conversation phase (Redis-backed).
        Returns context that gently suggests where the conversation is,
        allowing emergent endings rather than forced ones.
        """
        chain = await self._get_chain_from_redis(channel_id)
        if not chain:
            return ""
        
        turn_count = chain.message_count
        max_turns = settings.CROSS_BOT_MAX_CHAIN
        
        # Early conversation (turns 1-3): no hint needed
        if turn_count < 3:
            return ""
        
        # Middle conversation (turns 3-5): gentle awareness
        if turn_count < max_turns - 2:
            return "\n[CONVERSATION FLOW: You've been chatting for a bit. Continue naturally.]"
        
        # Approaching natural pause (turns 5+): soft hint
        return """\n[CONVERSATION FLOW: This has been a nice exchange. 
If it feels natural to wrap up with a warm closing, you can.
If there's genuinely more to explore, continue.
Trust your instincts - there's no pressure either way.]"""
    
    # Legacy sync versions for backward compatibility (use local cache)
    def is_last_turn(self, channel_id: str) -> bool:
        """Sync version using local cache. Prefer is_last_turn_async()."""
        chain = self._chain_cache.get(channel_id)
        if not chain:
            return False
        return (chain.message_count + 1) >= settings.CROSS_BOT_MAX_CHAIN

    def get_conversation_phase(self, channel_id: str) -> str:
        """Sync version using local cache. Prefer get_conversation_phase_async()."""
        chain = self._chain_cache.get(channel_id)
        if not chain:
            return ""
        
        turn_count = chain.message_count
        max_turns = settings.CROSS_BOT_MAX_CHAIN
        
        if turn_count < 3:
            return ""
        if turn_count < max_turns - 2:
            return "\n[CONVERSATION FLOW: You've been chatting for a bit. Continue naturally.]"
        return """\n[CONVERSATION FLOW: This has been a nice exchange. 
If it feels natural to wrap up with a warm closing, you can.
If there's genuinely more to explore, continue.
Trust your instincts - there's no pressure either way.]"""

    async def _set_cooldown_async(self, channel_id: str) -> None:
        """Set cooldown for a channel (shared via Redis with TTL - auto-expires)."""
        if db_manager.redis_client:
            try:
                key = _redis_key(f"{REDIS_PREFIX_COOLDOWN}{channel_id}")
                cooldown_seconds = settings.CROSS_BOT_COOLDOWN_MINUTES * 60
                await db_manager.redis_client.setex(key, cooldown_seconds, "1")
                logger.info(f"Set shared cooldown for channel {channel_id} ({settings.CROSS_BOT_COOLDOWN_MINUTES} min)")
            except Exception as e:
                logger.debug(f"Failed to set Redis cooldown: {e}")
    
    async def _get_or_create_chain_async(self, channel_id: str) -> ConversationChain:
        """Get existing chain from Redis or create new one."""
        chain = await self._get_chain_from_redis(channel_id)
        
        # Create new chain if none exists or current is expired
        if not chain or chain.is_expired():
            chain = ConversationChain(channel_id=channel_id)
            await self._save_chain_to_redis(chain)
        
        return chain
    
    async def detect_cross_bot_mention(
        self,
        message: discord.Message
    ) -> Optional[CrossBotMention]:
        """
        Detect if this message mentions our bot from another bot.
        
        Returns CrossBotMention if we should potentially respond, None otherwise.
        """
        # Master switch must be enabled for any autonomous activity
        if not settings.ENABLE_AUTONOMOUS_ACTIVITY:
            return None
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
            logger.info(f"Unknown bot {message.author.name} (ID: {message.author.id}) - ignoring")
            return None
        
        channel_id = str(message.channel.id)
        mentioning_bot = self.get_bot_name(message.author.id)
        logger.info(f"[CrossBot] Received message from known bot: {mentioning_bot}")

        # Check if this is a direct reply to one of our messages FIRST
        # (needed for burst detection logic)
        is_direct_reply = False
        if message.reference and message.reference.message_id:
            try:
                # Check if the referenced message is from us
                ref_msg = message.reference.resolved
                if ref_msg and ref_msg.author.id == self._bot.user.id:
                    is_direct_reply = True
                    logger.debug("Message is a direct reply to our message")
                # Fallback: Fetch message if not resolved (e.g., old message not in cache)
                elif not ref_msg:
                    try:
                        ref_msg = await message.channel.fetch_message(message.reference.message_id)
                        if ref_msg and ref_msg.author.id == self._bot.user.id:
                            is_direct_reply = True
                            logger.debug("Message is a direct reply to our message (fetched)")
                    except Exception:
                        pass
            except Exception:
                pass
        
        # Must mention us via:
        # 1. Direct @mention (always triggers), OR
        # 2. Name in text (triggers but with lower probability - handled by should_respond)
        has_at_mention = self._bot.user in message.mentions
        has_name_mention = False
        
        if not has_at_mention:
            # Check for name in text
            import re
            our_name = self._bot_name.lower() if self._bot_name else ""
            if our_name:
                escaped_name = re.escape(our_name)
                has_name_mention = bool(re.search(rf"\b{escaped_name}\b", message.content.lower()))
        
        logger.info(
            f"[CrossBot] Detection: from={mentioning_bot}, @mention={has_at_mention}, "
            f"name_mention={has_name_mention}, is_reply={is_direct_reply}"
        )
        
        # Must have some form of engagement:
        # 1. Direct @mention, OR
        # 2. Name in text, OR
        # 3. Direct reply to our message (they're continuing the conversation)
        if not has_at_mention and not has_name_mention and not is_direct_reply:
            logger.info(f"[CrossBot] No mention/reply from {mentioning_bot} - content: {message.content[:100]}")
            return None
        
        # Get chain from Redis (shared state)
        chain = await self._get_or_create_chain_async(channel_id)
        mentioning_bot = self.get_bot_name(message.author.id)
        
        # Check if we're in an active chain and it's our turn
        in_active_chain = (
            not chain.is_expired() and 
            chain.message_count > 0 and 
            chain.last_bot != self._bot_name  # Other bot just spoke
        )
        
        # Skip cooldown check if:
        # 1. We're in an active chain and it's our turn, OR
        # 2. This is a direct reply to our message
        if not is_direct_reply and not in_active_chain:
            if await self.is_on_cooldown_async(channel_id):
                logger.info(f"[CrossBot] Channel {channel_id} on cooldown (shared via Redis)")
                return None
            
            # Burst detection using Redis TTL (shared across bots)
            if mentioning_bot:
                is_burst = await self._check_burst(channel_id, mentioning_bot)
                if is_burst:
                    logger.debug(f"Skipping: burst detection for {mentioning_bot} (within 30s, not in chain)")
                    return None
        
        # Check chain limit using atomic count (prevents race conditions)
        current_count = await self._get_atomic_chain_count(channel_id)
        if current_count >= settings.CROSS_BOT_MAX_CHAIN:
            logger.info(f"[CrossBot] Chain limit reached in channel {channel_id} (count: {current_count})")
            return None
        
        # Get last bot from metadata to check if it's our turn
        last_bot = await self._get_last_bot(channel_id)
        
        # Don't respond if we were the last bot in the chain
        # BUT: if this is a direct reply to our message, the other bot just spoke - so we CAN respond
        if last_bot == self._bot_name and not is_direct_reply and not has_at_mention:
            logger.info(f"[CrossBot] We were last bot in chain, skipping (last_bot={last_bot})")
            return None
        
        return CrossBotMention(
            channel_id=channel_id,
            message_id=str(message.id),
            mentioned_bot=self._bot_name or "unknown",
            mentioning_bot=mentioning_bot,
            content=message.content,
            chain_id=channel_id,
            is_direct_mention=has_at_mention,
            is_direct_reply=is_direct_reply
        )
    
    async def should_respond(self, mention: CrossBotMention) -> bool:
        """
        Decide probabilistically whether to respond to a cross-bot mention.
        """
        # Always respond to direct replies to our messages
        if mention.is_direct_reply:
            return True
        
        # Always respond if chain just started (first bot-to-bot exchange)
        chain = await self._get_chain_from_redis(mention.channel_id)
        if chain and chain.message_count == 0:
            return True
        
        # Lower probability for name-in-text mentions (e.g., "Dream Journal")
        # This reduces spam while still allowing occasional organic responses
        base_chance = settings.CROSS_BOT_RESPONSE_CHANCE
        if not mention.is_direct_mention:
            # 30% of the normal chance for name-in-text mentions
            base_chance *= 0.3
            logger.debug(f"Name-in-text mention: reduced probability to {base_chance:.2f}")
        
        return random.random() < base_chance
    
    async def record_response(
        self,
        channel_id: str,
        message_id: str
    ) -> bool:
        """
        Record that we responded in a cross-bot conversation (Redis-backed).
        
        Uses atomic Redis operations to prevent race conditions.
        
        Returns:
            True if the chain just completed (hit max), False otherwise.
            When True, caller should trigger batch post-conversation processing.
        """
        # Use atomic increment for message count to prevent race conditions
        count_key = _redis_key(f"{REDIS_PREFIX_CHAIN}{channel_id}:count")
        meta_key = _redis_key(f"{REDIS_PREFIX_CHAIN}{channel_id}:meta")
        
        new_count = 1
        
        if db_manager.redis_client:
            try:
                # Atomic increment - this is the critical fix for the race condition
                new_count = await db_manager.redis_client.incr(count_key)
                
                # Set TTL on first message
                if new_count == 1:
                    await db_manager.redis_client.expire(count_key, CHAIN_EXPIRE_MINUTES * 60)
                
                # Update metadata (last bot, participants) - less critical for race conditions
                meta = {
                    "last_bot": self._bot_name or "unknown",
                    "last_message_id": message_id,
                    "last_activity": datetime.now(timezone.utc).isoformat()
                }
                await db_manager.redis_client.setex(
                    meta_key, 
                    CHAIN_EXPIRE_MINUTES * 60, 
                    json.dumps(meta)
                )
                
                logger.info(f"[CrossBot] Atomic increment: chain count = {new_count}/{settings.CROSS_BOT_MAX_CHAIN}")
                
            except Exception as e:
                logger.warning(f"[CrossBot] Atomic increment failed: {e}, falling back to non-atomic")
                # Fallback to old method if Redis fails
                chain = await self._get_or_create_chain_async(channel_id)
                chain.add_message(self._bot_name or "unknown", message_id)
                new_count = chain.message_count
                await self._save_chain_to_redis(chain)
        else:
            # No Redis - use local cache (single bot only)
            chain = await self._get_or_create_chain_async(channel_id)
            chain.add_message(self._bot_name or "unknown", message_id)
            new_count = chain.message_count
        
        # Check if chain completed
        chain_completed = new_count >= settings.CROSS_BOT_MAX_CHAIN
        
        if chain_completed:
            await self._set_cooldown_async(channel_id)
            # Clean up both keys
            if db_manager.redis_client:
                try:
                    await db_manager.redis_client.delete(count_key)
                    await db_manager.redis_client.delete(meta_key)
                except Exception:
                    pass
            await self._delete_chain_from_redis(channel_id)
            logger.info(f"[CrossBot] Chain completed (count: {new_count}), cooldown set")
        
        return chain_completed
    
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
            mention_data = {
                "channel_id": mention.channel_id,
                "message_id": mention.message_id,
                "mentioned_bot": mention.mentioned_bot,
                "mentioning_bot": mention.mentioning_bot,
                "content": mention.content,
                "timestamp": mention.timestamp.isoformat()
            }
            
            # Queue for the mentioned bot to process
            queue_key = _redis_key(f"crossbot:mentions:{mention.mentioned_bot}")
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
        queue_key = _redis_key(f"crossbot:mentions:{self._bot_name}")
        
        try:
            # Process up to 5 mentions per call using non-blocking LPOP
            # For real-time processing, use BLPOP in a dedicated loop
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
                    logger.debug("Skipping mention (probability check)")
            
        except Exception as e:
            logger.error(f"Failed to process queued mentions: {e}")
        
        return mentions


# Global instance (bot will be set later)
cross_bot_manager = CrossBotManager()
