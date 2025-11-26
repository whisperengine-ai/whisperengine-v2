import json
from typing import Optional, Any
from loguru import logger
from src_v2.core.database import db_manager

class CacheManager:
    def __init__(self):
        self.default_ttl = 300  # 5 minutes

    @property
    def redis(self):
        return db_manager.redis_client

    async def get(self, key: str) -> Optional[str]:
        if not self.redis:
            return None
        try:
            return await self.redis.get(key)
        except Exception as e:
            logger.warning(f"Redis get failed for {key}: {e}")
            return None

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        if not self.redis:
            return False
        try:
            await self.redis.set(key, value, ex=ttl or self.default_ttl)
            return True
        except Exception as e:
            logger.warning(f"Redis set failed for {key}: {e}")
            return False

    async def get_json(self, key: str) -> Optional[Any]:
        data = await self.get(key)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return None
        return None

    async def set_json(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        try:
            json_str = json.dumps(value)
            return await self.set(key, json_str, ttl)
        except Exception as e:
            logger.warning(f"Redis set_json failed for {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        if not self.redis:
            return False
        try:
            await self.redis.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Redis delete failed for {key}: {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Deletes all keys matching a pattern. Use with caution."""
        if not self.redis:
            return 0
        try:
            keys = await self.redis.keys(pattern)
            if keys:
                await self.redis.delete(*keys)
            return len(keys)
        except Exception as e:
            logger.warning(f"Redis delete_pattern failed for {pattern}: {e}")
            return 0

cache_manager = CacheManager()
