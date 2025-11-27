import json
from typing import Optional, Any, Dict
from datetime import datetime
from loguru import logger
from src_v2.core.database import db_manager

class CacheManager:
    def __init__(self):
        self.default_ttl = 300  # 5 minutes
        self.attention_ttl = 1800  # 30 minutes for attention keys

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
