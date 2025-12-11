import asyncio
import json
import time
from typing import Dict, Optional
from pydantic import BaseModel
from loguru import logger

from src_v2.config.settings import settings
from src_v2.core.database import db_manager

class BotInfo(BaseModel):
    name: str
    discord_id: str
    purpose: str
    status: str = "online"
    last_seen: float

class BotRegistry:
    """
    Distributed registry for WhisperEngine bots using Redis.
    Replaces the legacy cross_bot_manager.
    """
    def __init__(self):
        self.redis_prefix = f"{settings.REDIS_KEY_PREFIX}registry:"
        self.heartbeat_interval = 60  # 1 minute
        self.ttl = 180  # 3 minutes expiration

    async def register(self, bot_name: str, discord_id: str, purpose: str):
        """Register this bot in Redis with a TTL."""
        if not db_manager.redis_client:
            # Redis might not be ready yet during early startup
            return

        try:
            info = BotInfo(
                name=bot_name,
                discord_id=str(discord_id),
                purpose=purpose,
                last_seen=time.time()
            )
            
            key = f"{self.redis_prefix}{bot_name.lower()}"
            # Use setex for atomic set + expire
            await db_manager.redis_client.setex(
                key,
                self.ttl,
                info.model_dump_json()
            )
            logger.debug(f"Registered bot {bot_name} in registry.")
        except Exception as e:
            logger.warning(f"Failed to register bot {bot_name}: {e}")

    async def get_known_bots(self) -> Dict[str, BotInfo]:
        """Get all active bots from Redis."""
        if not db_manager.redis_client:
            return {}

        try:
            bots = {}
            pattern = f"{self.redis_prefix}*"
            # keys() can be slow in massive DBs but fine for <100 bots
            keys = await db_manager.redis_client.keys(pattern)
            
            if not keys:
                return {}

            # Mget for efficiency
            values = await db_manager.redis_client.mget(keys)
            
            for val in values:
                if val:
                    try:
                        data = json.loads(val)
                        bot = BotInfo(**data)
                        bots[bot.name.lower()] = bot
                    except Exception as e:
                        logger.warning(f"Failed to parse bot registry info: {e}")
            
            return bots
        except Exception as e:
            logger.error(f"Failed to get known bots: {e}")
            return {}

    async def start_heartbeat(self, bot):
        """Background task to keep registration alive."""
        logger.info("Starting BotRegistry heartbeat...")
        while True:
            try:
                if bot.user:
                    # Load purpose dynamically to catch updates
                    from src_v2.core.character import character_manager
                    char = character_manager.get_character(bot.character_name)
                    purpose = "An AI entity."
                    if char and char.behavior:
                        purpose = char.behavior.purpose
                    
                    await self.register(
                        bot.character_name,
                        str(bot.user.id),
                        purpose
                    )
            except Exception as e:
                logger.error(f"Registry heartbeat failed: {e}")
            
            await asyncio.sleep(self.heartbeat_interval)

# Global instance
bot_registry = BotRegistry()
