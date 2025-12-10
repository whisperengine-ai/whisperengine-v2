"""
Bot Registry - Lightweight bot discovery via Redis

Replaces the heavy cross_bot_manager that was removed in Phase E31.
Each running bot registers itself with a TTL, enabling discovery of live WhisperEngine bots.
"""

from typing import Dict, List
from loguru import logger
from src_v2.config.settings import settings
from src_v2.core.database import db_manager


__all__ = ["register_bot", "get_known_bots", "is_bot_registered", "unregister_bot"]


def _redis_key(suffix: str) -> str:
    """Apply Redis namespace prefix."""
    return f"{settings.REDIS_KEY_PREFIX}bot:registry:{suffix}"


async def register_bot(bot_name: str, discord_id: str, ttl_seconds: int = 86400) -> bool:
    """
    Register a running bot in Redis with TTL.
    
    Args:
        bot_name: Character name (e.g., "elena", "nottaylor")
        discord_id: Discord user ID of the bot
        ttl_seconds: How long registration lasts (default 24h)
    
    Returns:
        True if successful, False otherwise
    """
    if not db_manager.redis_client:
        logger.warning("Redis not available for bot registration")
        return False
    
    try:
        key = _redis_key(bot_name.lower())
        await db_manager.redis_client.set(key, discord_id, ex=ttl_seconds)
        logger.debug(f"Registered bot: {bot_name} (ID: {discord_id})")
        return True
    except Exception as e:
        logger.error(f"Failed to register bot {bot_name}: {e}")
        return False


async def get_known_bots() -> Dict[str, str]:
    """
    Get all currently registered WhisperEngine bots.
    
    Returns:
        Dict mapping bot_name -> discord_id for all live bots
    """
    if not db_manager.redis_client:
        logger.warning("Redis not available for bot discovery")
        return {}
    
    try:
        pattern = _redis_key("*")
        all_keys: List[str] = []
        
        # Scan for all bot registry keys
        cursor = 0
        while True:
            cursor, keys = await db_manager.redis_client.scan(
                cursor=cursor,
                match=pattern,
                count=100
            )
            all_keys.extend(keys)
            
            if cursor == 0:
                break
        
        if not all_keys:
            return {}
        
        # Batch fetch all values with MGET (1 call instead of N)
        values = await db_manager.redis_client.mget(all_keys)
        
        known_bots = {}
        for key, discord_id in zip(all_keys, values):
            if discord_id:
                # Extract bot name from key: "whisper:bot:registry:elena" -> "elena"
                bot_name = key.split(":")[-1]
                known_bots[bot_name] = discord_id
        
        logger.debug(f"Discovered {len(known_bots)} registered bots: {list(known_bots.keys())}")
        return known_bots
    
    except Exception as e:
        logger.error(f"Failed to discover bots: {e}")
        return {}


async def is_bot_registered(bot_name: str) -> bool:
    """Check if a specific bot is currently registered."""
    if not db_manager.redis_client:
        return False
    
    try:
        key = _redis_key(bot_name.lower())
        return await db_manager.redis_client.exists(key) > 0
    except Exception as e:
        logger.error(f"Failed to check bot registration for {bot_name}: {e}")
        return False


async def unregister_bot(bot_name: str) -> bool:
    """Remove a bot from the registry (called on shutdown)."""
    if not db_manager.redis_client:
        return False
    
    try:
        key = _redis_key(bot_name.lower())
        await db_manager.redis_client.delete(key)
        logger.info(f"Unregistered bot: {bot_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to unregister bot {bot_name}: {e}")
        return False
