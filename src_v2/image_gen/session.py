import json
import redis.asyncio as redis
from typing import Optional, Dict, Any
from loguru import logger
from src_v2.config.settings import settings

class ImageSessionManager:
    """
    Manages image generation sessions to support iterative refinement.
    Stores the last prompt, seed, and parameters for each user.
    """
    
    def __init__(self):
        self._redis = None
        self._ttl = 3600  # 1 hour session
        
    async def _get_redis(self):
        if not self._redis:
            self._redis = redis.from_url(settings.REDIS_URL)
        return self._redis
        
    async def save_session(self, user_id: str, prompt: str, seed: int, params: Dict[str, Any]) -> None:
        """
        Saves the current generation state.
        """
        try:
            r = await self._get_redis()
            key = f"image_session:{user_id}"
            
            data = {
                "prompt": prompt,
                "seed": seed,
                "params": params,
                "timestamp": params.get("timestamp")
            }
            
            await r.setex(key, self._ttl, json.dumps(data))
            logger.debug(f"Saved image session for user {user_id} (seed: {seed})")
            
        except Exception as e:
            logger.error(f"Failed to save image session: {e}")
            
    async def get_session(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the last generation state.
        """
        try:
            r = await self._get_redis()
            key = f"image_session:{user_id}"
            data = await r.get(key)
            
            if data:
                return json.loads(data)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get image session: {e}")
            return None
            
    async def clear_session(self, user_id: str) -> None:
        """
        Clears the session (e.g. when starting a completely new topic).
        """
        try:
            r = await self._get_redis()
            key = f"image_session:{user_id}"
            await r.delete(key)
        except Exception as e:
            logger.error(f"Failed to clear image session: {e}")

# Global instance
image_session = ImageSessionManager()
