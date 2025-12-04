import hashlib
import json
import time
from typing import Optional, List, Set, Any, Dict, Tuple
from loguru import logger
from src_v2.core.database import db_manager
from src_v2.config.settings import settings

class SpamDetector:
    """
    Detects cross-posting spam by tracking user messages across channels.
    Uses Redis for temporary storage of message hashes.
    """
    
    def __init__(self):
        self.enabled = settings.ENABLE_CROSSPOST_DETECTION
        self.threshold = settings.CROSSPOST_THRESHOLD
        self.window = settings.CROSSPOST_WINDOW_SECONDS
        self.warning_message = settings.CROSSPOST_WARNING_MESSAGE
        self.action = settings.CROSSPOST_ACTION
        # Cache for whitelisted role IDs per guild: {guild_id: {role_id, ...}}
        self._whitelisted_roles: Dict[str, Set[str]] = {} 
        self._whitelist_loaded: Set[str] = set() # Track which guilds have been loaded
        self._settings_loaded = False

    async def _load_settings(self) -> None:
        """Load persisted settings from Redis."""
        if self._settings_loaded or not db_manager.redis_client:
            return
        
        try:
            enabled_val = await db_manager.redis_client.get("spam:settings:enabled")
            if enabled_val:
                self.enabled = enabled_val == "1"
            
            threshold_val = await db_manager.redis_client.get("spam:settings:threshold")
            if threshold_val:
                self.threshold = int(threshold_val)
            
            action_val = await db_manager.redis_client.get("spam:settings:action")
            if action_val:
                self.action = action_val
            
            self._settings_loaded = True
        except Exception as e:
            logger.error(f"Failed to load spam settings from Redis: {e}")

    async def set_enabled(self, enabled: bool) -> None:
        """Set and persist enabled state."""
        self.enabled = enabled
        if db_manager.redis_client:
            await db_manager.redis_client.set("spam:settings:enabled", "1" if enabled else "0")

    async def set_threshold(self, threshold: int) -> None:
        """Set and persist threshold."""
        self.threshold = threshold
        if db_manager.redis_client:
            await db_manager.redis_client.set("spam:settings:threshold", str(threshold))

    async def set_action(self, action: str) -> None:
        """Set and persist action."""
        if action not in ["warn", "delete"]:
            raise ValueError(f"Invalid action: {action}")
        self.action = action
        if db_manager.redis_client:
            await db_manager.redis_client.set("spam:settings:action", action)

    async def is_whitelisted(self, member_roles: List[Any], guild_id: str) -> bool:
        """Check if user has a whitelisted role."""
        if guild_id not in self._whitelist_loaded:
            # Try to load from Redis if cache is empty for this guild
            if db_manager.redis_client:
                roles = await db_manager.redis_client.smembers(f"spam:whitelist:{guild_id}")
                self._whitelisted_roles[guild_id] = set(roles)
            else:
                self._whitelisted_roles[guild_id] = set()
            self._whitelist_loaded.add(guild_id)
        
        guild_roles = self._whitelisted_roles.get(guild_id, set())
        if not guild_roles:
            return False
            
        for role in member_roles:
            if str(role.id) in guild_roles:
                return True
        return False

    async def add_whitelist(self, role_id: str, guild_id: str) -> None:
        """Add a role to the whitelist."""
        if guild_id not in self._whitelisted_roles:
            self._whitelisted_roles[guild_id] = set()
            
        self._whitelisted_roles[guild_id].add(role_id)
        if db_manager.redis_client:
            await db_manager.redis_client.sadd(f"spam:whitelist:{guild_id}", role_id)

    async def remove_whitelist(self, role_id: str, guild_id: str) -> None:
        """Remove a role from the whitelist."""
        if guild_id in self._whitelisted_roles:
            self._whitelisted_roles[guild_id].discard(role_id)
            
        if db_manager.redis_client:
            await db_manager.redis_client.srem(f"spam:whitelist:{guild_id}", role_id)

    async def check_file_crosspost(self, user_id: str, channel_id: str, attachments: List[Any]) -> Tuple[bool, bool]:
        """
        Check if the user is cross-posting the same files to multiple channels.
        Returns (is_spam, should_warn).
        """
        await self._load_settings()
        
        if not self.enabled or not attachments:
            return False, False
            
        # Skip if Redis is not available
        if not db_manager.redis_client:
            return False, False

        # Create a hash for the files
        # We use filename + size as a proxy for content to avoid downloading
        file_signatures = [f"{a.filename}:{a.size}" for a in attachments]
        content_hash = hashlib.md5("|".join(sorted(file_signatures)).encode()).hexdigest()
        
        return await self._process_hash(user_id, channel_id, content_hash, "file")

    async def check_crosspost(self, user_id: str, channel_id: str, content: str) -> Tuple[bool, bool]:
        """
        Check if the user is cross-posting the same message to multiple channels.
        Returns (is_spam, should_warn).
        """
        await self._load_settings()
        
        if not self.enabled:
            return False, False
            
        # Skip if Redis is not available
        if not db_manager.redis_client:
            return False, False

        # Ignore short messages (too common, e.g. "lol", "thanks")
        if len(content.strip()) < 10:
            return False, False

        # Create a hash of the content
        # We normalize by lowercasing and stripping whitespace
        content_hash = hashlib.md5(content.strip().lower().encode()).hexdigest()
        
        return await self._process_hash(user_id, channel_id, content_hash, "text")

    async def _process_hash(self, user_id: str, channel_id: str, content_hash: str, type_prefix: str) -> Tuple[bool, bool]:
        """
        Internal method to process message/file hashes.
        Returns (is_spam, should_warn)
        """
        key = f"spam:crosspost:{user_id}"
        warn_key = f"spam:warned:{user_id}:{content_hash}"
        now = time.time()
        
        try:
            # 1. Check if we already warned about this specific spam wave recently
            if await db_manager.redis_client.exists(warn_key):
                # It IS spam, but we already warned.
                # Return True (is_spam) so we can delete it, but False (should_warn) to avoid noise.
                return True, False

            # 2. Add current message to history
            entry = json.dumps({
                "h": content_hash,
                "c": channel_id,
                "t": now
            })
            
            async with db_manager.redis_client.pipeline() as pipe:
                await pipe.lpush(key, entry)
                await pipe.ltrim(key, 0, 19)
                await pipe.expire(key, self.window * 2)
                await pipe.lrange(key, 0, -1)
                results = await pipe.execute()
            
            history_raw = results[3]
            
            # 3. Analyze history
            seen_channels: Set[str] = set()
            
            for item in history_raw:
                try:
                    data = json.loads(item)
                    if now - data["t"] > self.window:
                        continue
                    if data["h"] == content_hash:
                        seen_channels.add(data["c"])
                except Exception:
                    continue
                    
            # 4. Decision
            if len(seen_channels) >= self.threshold:
                logger.warning(f"Spam detected ({type_prefix}) for user {user_id}: {len(seen_channels)} channels")
                await db_manager.redis_client.setex(warn_key, 300, "1")
                return True, True
                
        except Exception as e:
            logger.error(f"Error in spam detection: {e}")
            return False, False
            
        return False, False

# Global instance
spam_detector = SpamDetector()
