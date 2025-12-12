import json
from typing import Optional, Any, Dict
from datetime import datetime
from loguru import logger
from src_v2.core.database import db_manager
from src_v2.config.settings import settings


class CacheManager:
    """
    Unified Redis cache abstraction for WhisperEngine.
    
    All Redis operations should go through this class to ensure:
    - Consistent key namespacing (REDIS_KEY_PREFIX)
    - Fail-safe error handling (logs warnings, never crashes)
    - JSON serialization for complex data types
    
    CURRENT STATUS (v2.5):
    - String operations: get, set, get_json, set_json, delete, delete_pattern
    - List operations: lpush, rpush, lpop, rpop, ltrim, lrange, llen
    - Sorted Set operations: zadd, zrangebyscore, zremrangebyscore
    - Hash operations: hincrby, hgetall
    - Key operations: keys, expire
    - Attention system: set_attention, get_attention, clear_attention
    - TTL operations: setex, set_nx (locking)
    """
    
    def __init__(self):
        self.default_ttl = 300  # 5 minutes
        self.attention_ttl = 1800  # 30 minutes for attention keys
        self._prefix = settings.REDIS_KEY_PREFIX

    def _key(self, key: str) -> str:
        """Apply namespace prefix to key if not already prefixed."""
        if key.startswith(self._prefix):
            return key
        return f"{self._prefix}{key}"

    @property
    def redis(self):
        return db_manager.redis_client

    async def get(self, key: str) -> Optional[str]:
        if not self.redis:
            return None
        try:
            return await self.redis.get(self._key(key))
        except Exception as e:
            logger.warning(f"Redis get failed for {key}: {e}")
            return None

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        if not self.redis:
            return False
        try:
            await self.redis.set(self._key(key), value, ex=ttl or self.default_ttl)
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
            await self.redis.delete(self._key(key))
            return True
        except Exception as e:
            logger.warning(f"Redis delete failed for {key}: {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Deletes all keys matching a pattern. Use with caution."""
        if not self.redis:
            return 0
        try:
            prefixed_pattern = self._key(pattern)
            keys = await self.redis.keys(prefixed_pattern)
            if keys:
                await self.redis.delete(*keys)
            return len(keys)
        except Exception as e:
            logger.warning(f"Redis delete_pattern failed for {pattern}: {e}")
            return 0

    async def lpush(self, key: str, *values: str) -> int:
        if not self.redis:
            return 0
        try:
            return await self.redis.lpush(self._key(key), *values)
        except Exception as e:
            logger.warning(f"Redis lpush failed for {key}: {e}")
            return 0

    async def rpush(self, key: str, *values: str) -> int:
        if not self.redis:
            return 0
        try:
            return await self.redis.rpush(self._key(key), *values)
        except Exception as e:
            logger.warning(f"Redis rpush failed for {key}: {e}")
            return 0

    async def lpop(self, key: str) -> Optional[str]:
        if not self.redis:
            return None
        try:
            return await self.redis.lpop(self._key(key))
        except Exception as e:
            logger.warning(f"Redis lpop failed for {key}: {e}")
            return None

    async def ltrim(self, key: str, start: int, end: int) -> bool:
        if not self.redis:
            return False
        try:
            await self.redis.ltrim(self._key(key), start, end)
            return True
        except Exception as e:
            logger.warning(f"Redis ltrim failed for {key}: {e}")
            return False

    async def lrange(self, key: str, start: int, end: int) -> list:
        if not self.redis:
            return []
        try:
            return await self.redis.lrange(self._key(key), start, end)
        except Exception as e:
            logger.warning(f"Redis lrange failed for {key}: {e}")
            return []

    async def rpop(self, key: str) -> Optional[str]:
        if not self.redis:
            return None
        try:
            return await self.redis.rpop(self._key(key))
        except Exception as e:
            logger.warning(f"Redis rpop failed for {key}: {e}")
            return None

    async def setex(self, key: str, seconds: int, value: str) -> bool:
        if not self.redis:
            return False
        try:
            await self.redis.setex(self._key(key), seconds, value)
            return True
        except Exception as e:
            logger.warning(f"Redis setex failed for {key}: {e}")
            return False

    async def set_nx(self, key: str, value: str, ttl: int) -> bool:
        """Set key if not exists (atomic lock)."""
        if not self.redis:
            return False
        try:
            # redis-py set(..., nx=True, ex=ttl) returns True if set, None if not
            result = await self.redis.set(self._key(key), value, nx=True, ex=ttl)
            return bool(result)
        except Exception as e:
            logger.warning(f"Redis set_nx failed for {key}: {e}")
            return False

    async def zadd(self, key: str, mapping: Dict[str, float]) -> int:
        if not self.redis:
            return 0
        try:
            return await self.redis.zadd(self._key(key), mapping)
        except Exception as e:
            logger.warning(f"Redis zadd failed for {key}: {e}")
            return 0

    async def zrangebyscore(self, key: str, min_score: float | str, max_score: float | str) -> list:
        if not self.redis:
            return []
        try:
            return await self.redis.zrangebyscore(self._key(key), min_score, max_score)
        except Exception as e:
            logger.warning(f"Redis zrangebyscore failed for {key}: {e}")
            return []

    async def zremrangebyscore(self, key: str, min_score: float | str, max_score: float | str) -> int:
        if not self.redis:
            return 0
        try:
            return await self.redis.zremrangebyscore(self._key(key), min_score, max_score)
        except Exception as e:
            logger.warning(f"Redis zremrangebyscore failed for {key}: {e}")
            return 0

    async def keys(self, pattern: str) -> list:
        """
        Find keys matching pattern.
        Note: pattern should NOT include the global prefix, it will be added.
        Returns list of keys (without prefix? No, Redis returns full keys).
        """
        if not self.redis:
            return []
        try:
            # We prefix the pattern
            full_pattern = self._key(pattern)
            return await self.redis.keys(full_pattern)
        except Exception as e:
            logger.warning(f"Redis keys failed for {pattern}: {e}")
            return []

    async def hincrby(self, key: str, field: str, amount: int = 1) -> int:
        if not self.redis:
            return 0
        try:
            return await self.redis.hincrby(self._key(key), field, amount)
        except Exception as e:
            logger.warning(f"Redis hincrby failed for {key}: {e}")
            return 0

    async def hgetall(self, key: str) -> Dict[str, str]:
        if not self.redis:
            return {}
        try:
            return await self.redis.hgetall(self._key(key))
        except Exception as e:
            logger.warning(f"Redis hgetall failed for {key}: {e}")
            return {}

    async def expire(self, key: str, seconds: int) -> bool:
        if not self.redis:
            return False
        try:
            return await self.redis.expire(self._key(key), seconds)
        except Exception as e:
            logger.warning(f"Redis expire failed for {key}: {e}")
            return False

    async def llen(self, key: str) -> int:
        if not self.redis:
            return 0
        try:
            return await self.redis.llen(self._key(key))
        except Exception as e:
            logger.warning(f"Redis llen failed for {key}: {e}")
            return 0

    # ========== ATTENTION KEYS (Phase B9: Emergent Behavior) ==========
    
    async def set_attention(self, character_name: str, focus_type: str, focus_target: str, metadata: Optional[Dict] = None) -> bool:
        """
        Sets what a character is currently focused on.
        
        Examples:
        - set_attention("elena", "user", "user123") - Elena is talking to user123
        - set_attention("elena", "topic", "astronomy") - Elena is discussing astronomy
        - set_attention("marcus", "channel", "12345") - Marcus is active in channel
        
        Other characters can discover these and reference them naturally.
        """
        key = f"attention:{character_name}:{focus_type}"
        value = {
            "target": focus_target,
            "since": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        return await self.set_json(key, value, ttl=self.attention_ttl)
    
    async def get_attention(self, character_name: str, focus_type: str) -> Optional[Dict]:
        """
        Gets what a character is currently focused on.
        """
        key = f"attention:{character_name}:{focus_type}"
        return await self.get_json(key)
    
    async def get_all_attention(self, character_name: str) -> Dict[str, Any]:
        """
        Gets all current attention states for a character.
        """
        if not self.redis:
            return {}
        
        try:
            pattern = f"attention:{character_name}:*"
            keys = await self.redis.keys(pattern)
            
            result = {}
            for key in keys:
                focus_type = key.decode().split(":")[-1] if isinstance(key, bytes) else key.split(":")[-1]
                data = await self.get_json(key.decode() if isinstance(key, bytes) else key)
                if data:
                    result[focus_type] = data
            return result
        except Exception as e:
            logger.warning(f"Failed to get all attention for {character_name}: {e}")
            return {}
    
    async def get_other_characters_attention(self, exclude_character: str) -> Dict[str, Dict]:
        """
        Gets attention states of all OTHER characters (for cross-bot awareness).
        
        Returns: {"elena": {"user": {...}, "topic": {...}}, "marcus": {...}}
        """
        if not self.redis:
            return {}
        
        try:
            pattern = "attention:*:*"
            keys = await self.redis.keys(pattern)
            
            result: Dict[str, Dict] = {}
            for key in keys:
                key_str = key.decode() if isinstance(key, bytes) else key
                parts = key_str.split(":")
                if len(parts) >= 3:
                    char_name = parts[1]
                    focus_type = parts[2]
                    
                    if char_name == exclude_character:
                        continue
                    
                    if char_name not in result:
                        result[char_name] = {}
                    
                    data = await self.get_json(key_str)
                    if data:
                        result[char_name][focus_type] = data
            
            return result
        except Exception as e:
            logger.warning(f"Failed to get other characters attention: {e}")
            return {}
    
    async def clear_attention(self, character_name: str, focus_type: Optional[str] = None) -> int:
        """
        Clears attention state(s) for a character.
        If focus_type is None, clears all attention states.
        """
        if focus_type:
            await self.delete(f"attention:{character_name}:{focus_type}")
            return 1
        else:
            return await self.delete_pattern(f"attention:{character_name}:*")

cache_manager = CacheManager()
