"""
Discord ID to Display Name Resolution Utility.

Provides functions to resolve Discord user IDs to human-readable display names
for use in dream/diary generation and other narrative contexts.

The resolver uses multiple sources:
1. Cached names from v2_chat_history (fastest)
2. Cached names from v2_user_relationships (fallback)
3. Fallback patterns for unknown IDs
"""
import re
from typing import Dict, List, Optional
from loguru import logger

from src_v2.core.database import db_manager


class NameResolver:
    """
    Resolves Discord user IDs to display names using cached data.
    
    This is designed for narrative generation where we want to replace
    raw numeric IDs with human-readable names.
    """
    
    # Simple in-memory cache to avoid repeated DB lookups within a session
    _cache: Dict[str, str] = {}
    
    @classmethod
    async def resolve_user_id(cls, user_id: str, character_name: str, fallback: str = "someone") -> str:
        """
        Resolve a single user ID to a display name.
        
        Args:
            user_id: Discord user ID (numeric string)
            character_name: Bot name for looking up relationship data
            fallback: Default name if resolution fails
            
        Returns:
            Display name or fallback
        """
        # Check cache first
        cache_key = f"{character_name}:{user_id}"
        if cache_key in cls._cache:
            return cls._cache[cache_key]
        
        # Skip if not a valid Discord ID pattern
        if not user_id or not user_id.isdigit() or len(user_id) < 17:
            return fallback
        
        name = None
        
        try:
            if db_manager.postgres_pool:
                async with db_manager.postgres_pool.acquire() as conn:
                    # Try chat history first (most recent names)
                    row = await conn.fetchrow("""
                        SELECT user_name 
                        FROM v2_chat_history 
                        WHERE user_id = $1 AND character_name = $2 AND user_name IS NOT NULL
                        ORDER BY timestamp DESC
                        LIMIT 1
                    """, str(user_id), character_name)
                    
                    if row and row['user_name']:
                        name = row['user_name']
                    else:
                        # Try user relationships (has preferences like nickname)
                        row = await conn.fetchrow("""
                            SELECT preferences->>'nickname' as nickname
                            FROM v2_user_relationships
                            WHERE user_id = $1 AND character_name = $2
                        """, str(user_id), character_name)
                        
                        if row and row['nickname']:
                            name = row['nickname']
        except Exception as e:
            logger.debug(f"Name resolution failed for {user_id}: {e}")
        
        result = name or fallback
        cls._cache[cache_key] = result
        return result
    
    @classmethod
    async def resolve_multiple(cls, user_ids: List[str], character_name: str) -> Dict[str, str]:
        """
        Resolve multiple user IDs to display names in one batch.
        
        Args:
            user_ids: List of Discord user IDs
            character_name: Bot name for context
            
        Returns:
            Dict mapping user_id -> display_name
        """
        result = {}
        
        for uid in user_ids:
            result[uid] = await cls.resolve_user_id(uid, character_name)
        
        return result
    
    @classmethod
    async def sanitize_text_ids(cls, text: str, character_name: str) -> str:
        """
        Replace raw Discord IDs in text with display names.
        
        Looks for patterns like:
        - Raw numeric IDs (18-20 digits)
        - Discord mention format <@123456789>
        
        Args:
            text: Text that may contain Discord IDs
            character_name: Bot name for resolution context
            
        Returns:
            Text with IDs replaced by names where possible
        """
        if not text:
            return text
        
        # Pattern for raw Discord IDs (18-20 digit numbers)
        # Be careful not to match things like dates, phone numbers, etc.
        # Discord IDs are typically 17-19 digits and start with specific prefixes
        id_pattern = r'\b([12]\d{17,19})\b'
        
        # Find all potential IDs
        matches = re.findall(id_pattern, text)
        
        if not matches:
            return text
        
        # Resolve unique IDs
        unique_ids = list(set(matches))
        name_map = await cls.resolve_multiple(unique_ids, character_name)
        
        # Replace in text
        result = text
        for uid, name in name_map.items():
            if name != "someone":  # Only replace if we found a real name
                result = result.replace(uid, name)
        
        return result
    
    @classmethod
    async def sanitize_content_with_context(
        cls, 
        content: str, 
        character_name: str,
        known_names: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Sanitize content by replacing IDs with names, using provided context.
        
        This is more efficient when you already have some name mappings.
        
        Args:
            content: Text content to sanitize
            character_name: Bot name
            known_names: Pre-resolved name mappings (user_id -> name)
            
        Returns:
            Sanitized content
        """
        if not content:
            return content
        
        known_names = known_names or {}
        
        # Pattern for Discord IDs
        id_pattern = r'\b([12]\d{17,19})\b'
        matches = re.findall(id_pattern, content)
        
        if not matches:
            return content
        
        result = content
        for uid in set(matches):
            if uid in known_names:
                name = known_names[uid]
            else:
                name = await cls.resolve_user_id(uid, character_name)
                known_names[uid] = name  # Cache for future use
            
            if name != "someone":
                result = result.replace(uid, name)
        
        return result
    
    @classmethod
    def clear_cache(cls) -> None:
        """Clear the in-memory name cache."""
        cls._cache.clear()


# Convenience function for simple cases
async def resolve_user_name(user_id: str, character_name: str) -> str:
    """Resolve a user ID to display name (convenience wrapper)."""
    return await NameResolver.resolve_user_id(user_id, character_name)


async def sanitize_ids_in_text(text: str, character_name: str) -> str:
    """Replace Discord IDs in text with names (convenience wrapper)."""
    return await NameResolver.sanitize_text_ids(text, character_name)


class BoundNameResolver:
    """
    A name resolver bound to a specific character/bot context.
    
    This simplifies usage when you're working within a single bot's context
    and don't want to pass character_name everywhere.
    """
    
    def __init__(self, character_name: str):
        self.character_name = character_name
    
    async def resolve_user_id(self, user_id: str) -> str:
        """Resolve a user ID to display name."""
        return await NameResolver.resolve_user_id(user_id, self.character_name)
    
    async def resolve_ids_in_text(self, text: str) -> str:
        """Replace Discord IDs in text with names."""
        return await NameResolver.sanitize_text_ids(text, self.character_name)


def get_name_resolver(character_name: Optional[str] = None) -> BoundNameResolver:
    """
    Get a name resolver bound to a character/bot context.
    
    If no character_name is provided, uses the global DISCORD_BOT_NAME from settings.
    
    Args:
        character_name: Optional bot name for resolution context
        
    Returns:
        BoundNameResolver instance
    """
    from src_v2.config.settings import settings
    name = character_name or settings.DISCORD_BOT_NAME or "bot"
    return BoundNameResolver(name)
