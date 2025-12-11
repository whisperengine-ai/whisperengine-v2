import asyncio
import json
from datetime import datetime
from typing import Dict, Optional
from loguru import logger
import discord

from src_v2.config.settings import settings
from src_v2.core.database import db_manager

class CrossBotManager:
    """
    Manages discovery and registration of bots in the WhisperEngine cluster.
    Uses Redis to maintain a heartbeat of active bots and their Discord IDs.
    """
    def __init__(self):
        self.bot: Optional[discord.Client] = None
        self.known_bots: Dict[str, int] = {}  # name -> discord_id
        self._running = False

    def set_bot(self, bot: discord.Client):
        self.bot = bot

    async def start_registration_loop(self):
        """Periodically register this bot in Redis."""
        if self._running:
            return
        self._running = True
        
        logger.info("Starting CrossBot registration loop...")
        while self._running:
            try:
                await self._register_self()
                await self.load_known_bots()
            except Exception as e:
                logger.error(f"Error in cross-bot registration loop: {e}")
            
            await asyncio.sleep(30)  # Heartbeat every 30s

    async def _register_self(self):
        if not self.bot or not self.bot.user:
            return
            
        if not db_manager.redis_client:
            return

        bot_name = settings.DISCORD_BOT_NAME
        if not bot_name:
            return

        # Key: whisper:bot:{name}:info
        key = f"{settings.REDIS_KEY_PREFIX}bot:{bot_name}:info"
        data = {
            "name": bot_name,
            "discord_id": self.bot.user.id,
            "status": "online",
            "last_seen": datetime.utcnow().isoformat()
        }
        
        # Set with TTL of 60s (must refresh to stay "known")
        await db_manager.redis_client.setex(key, 60, json.dumps(data))

    async def load_known_bots(self):
        """Discover other bots from Redis."""
        if not db_manager.redis_client:
            return

        pattern = f"{settings.REDIS_KEY_PREFIX}bot:*:info"
        # keys() returns bytes, need to decode if needed, but redis-py handles strings usually
        keys = await db_manager.redis_client.keys(pattern)
        
        new_known_bots = {}
        
        for key in keys:
            try:
                data_str = await db_manager.redis_client.get(key)
                if data_str:
                    data = json.loads(data_str)
                    name = data.get("name")
                    discord_id = data.get("discord_id")
                    if name and discord_id:
                        new_known_bots[name] = int(discord_id)
            except Exception as e:
                logger.warning(f"Failed to parse bot info from {key}: {e}")
        
        self.known_bots = new_known_bots
        # logger.debug(f"Known bots: {list(self.known_bots.keys())}")

cross_bot_manager = CrossBotManager()
