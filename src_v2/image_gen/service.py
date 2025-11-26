import asyncio
import aiohttp
import uuid
import json
import aiofiles
import redis.asyncio as redis
from io import BytesIO
from pathlib import Path
from loguru import logger
from typing import Optional, List
from src_v2.config.settings import settings

# Resolve storage directory relative to project root (works in Docker and local)
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_TEMP_DOWNLOADS_DIR = _PROJECT_ROOT / "temp_downloads"

class ImageGenerationResult:
    """Result from image generation containing URL and raw bytes."""
    
    def __init__(self, url: str, image_bytes: bytes, filename: str = "generated_image.jpg"):
        self.url = url
        self.image_bytes = image_bytes
        self.filename = filename
    
    def to_discord_file(self) -> "discord.File":
        """Convert to a Discord File object for uploading."""
        import discord
        return discord.File(BytesIO(self.image_bytes), filename=self.filename)


class PendingImageRegistry:
    """
    Redis-backed registry for images generated during response generation.
    Uses filesystem for storage and Redis for metadata/queueing.
    """
    
    def __init__(self):
        self._redis = None
        self._ttl = 300  # 5 minutes
        self._storage_dir = _TEMP_DOWNLOADS_DIR
        
        # Ensure storage directory exists
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        
    async def _get_redis(self):
        if not self._redis:
            self._redis = redis.from_url(settings.REDIS_URL)
        return self._redis

    async def add(self, user_id: str, result: ImageGenerationResult) -> None:
        """
        Save image to disk and add metadata to the user's pending queue in Redis.
        """
        try:
            # 1. Save image to disk
            file_id = str(uuid.uuid4())
            filename = f"{file_id}.png"
            filepath = self._storage_dir / filename
            
            async with aiofiles.open(filepath, "wb") as f:
                await f.write(result.image_bytes)
            
            # 2. Prepare metadata (store absolute path as string for JSON)
            metadata = {
                "path": str(filepath),
                "url": result.url,
                "filename": result.filename
            }
            
            # 3. Store in Redis
            key = f"pending_images:{user_id}"
            r = await self._get_redis()
            
            await r.rpush(key, json.dumps(metadata))
            await r.expire(key, self._ttl)
            
            logger.debug(f"Saved pending image to {filepath} and queued for user {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to add image to registry: {e}")

    async def pop_all(self, user_id: str) -> List[ImageGenerationResult]:
        """
        Retrieve all pending images for a user, load from disk, and cleanup.
        """
        key = f"pending_images:{user_id}"
        results = []
        
        try:
            r = await self._get_redis()
            
            # Get all items
            while True:
                data = await r.lpop(key)
                if not data:
                    break
                
                try:
                    meta = json.loads(data)
                    path = Path(meta["path"])
                    
                    if path.exists():
                        # Load bytes
                        async with aiofiles.open(path, "rb") as f:
                            image_bytes = await f.read()
                        
                        # Create result object
                        results.append(ImageGenerationResult(
                            url=meta["url"],
                            image_bytes=image_bytes,
                            filename=meta["filename"]
                        ))
                        
                        # Cleanup file
                        path.unlink()
                        logger.debug(f"Retrieved and cleaned up image: {path}")
                    else:
                        logger.warning(f"Pending image file not found: {path}")
                        
                except Exception as e:
                    logger.error(f"Error processing pending image item: {e}")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to retrieve images from Redis: {e}")
            return []
            
# Global registry instance
pending_images = PendingImageRegistry()


class ImageGenerationService:
    """
    Service for generating images using external providers (BFL, Replicate, Fal).
    Currently optimized for Black Forest Labs (BFL) direct API.
    """
    
    def __init__(self):
        self.provider = settings.IMAGE_GEN_PROVIDER
        self.model = settings.IMAGE_GEN_MODEL
        self.api_key = settings.FLUX_API_KEY.get_secret_value() if settings.FLUX_API_KEY else None
        self.base_url = "https://api.bfl.ai/v1"

    async def generate_image(self, prompt: str, width: int = 896, height: int = 1120) -> Optional[ImageGenerationResult]:
        """
        Generates an image from a prompt and returns an ImageGenerationResult with URL and bytes.
        Default is 4:5 portrait (896x1120).
        
        Returns:
            ImageGenerationResult containing URL and raw bytes for Discord upload, or None on failure.
        """
        if not self.api_key:
            logger.error("FLUX_API_KEY is not set. Cannot generate image.")
            return None

        if self.provider == "bfl":
            return await self._generate_bfl(prompt, width, height)
        else:
            logger.warning(f"Provider {self.provider} not implemented yet.")
            return None

    async def _download_image(self, url: str, session: aiohttp.ClientSession) -> Optional[bytes]:
        """Download image bytes from a URL."""
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    logger.error(f"Failed to download image: HTTP {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Exception downloading image: {e}")
            return None

    async def _generate_bfl(self, prompt: str, width: int, height: int) -> Optional[ImageGenerationResult]:
        """
        Generates image using BFL API (Async polling pattern).
        Returns ImageGenerationResult with both URL and downloaded bytes.
        """
        endpoint = f"{self.base_url}/{self.model}"
        headers = {
            "Content-Type": "application/json",
            "x-key": self.api_key
        }
        payload = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "prompt_upsampling": True,
            "safety_tolerance": 5
        }

        async with aiohttp.ClientSession() as session:
            # 1. Submit Task
            try:
                async with session.post(endpoint, json=payload, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"BFL API Error (Submit): {response.status} - {error_text}")
                        return None
                    
                    data = await response.json()
                    task_id = data.get("id")
                    
                    if not task_id:
                        logger.error(f"No task ID returned from BFL: {data}")
                        return None
                    
                    logger.info(f"Image generation task submitted: {task_id}")

            except Exception as e:
                logger.error(f"Exception submitting BFL task: {e}")
                return None

            # 2. Poll for Result
            max_retries = 30  # 30 seconds max
            for _ in range(max_retries):
                await asyncio.sleep(1)  # Wait 1s between polls
                
                poll_url = f"{self.base_url}/get_result"
                try:
                    async with session.get(poll_url, params={"id": task_id}, headers=headers) as response:
                        if response.status != 200:
                            # 404 means task is not yet indexed/ready
                            if response.status != 404:
                                logger.warning(f"BFL Poll Error: {response.status}")
                            continue
                        
                        result = await response.json()
                        status = result.get("status")
                        
                        if status == "Ready":
                            image_url = result.get("result", {}).get("sample")
                            if image_url:
                                logger.info(f"Image generated successfully: {image_url}")
                                
                                # Download the image bytes for Discord upload
                                image_bytes = await self._download_image(image_url, session)
                                if image_bytes:
                                    # Generate a unique filename based on task ID
                                    filename = f"generated_{task_id[:8]}.jpg"
                                    return ImageGenerationResult(
                                        url=image_url,
                                        image_bytes=image_bytes,
                                        filename=filename
                                    )
                                else:
                                    logger.error("Failed to download generated image bytes")
                                    return None
                            else:
                                logger.error(f"BFL returned Ready but no image URL: {result}")
                                return None
                        elif status == "Failed":
                            logger.error(f"BFL Task Failed: {result}")
                            return None
                        elif status in ["Pending", "Processing"]:
                            continue
                        else:
                            logger.warning(f"Unknown BFL status: {status}")
                            
                except Exception as e:
                    logger.error(f"Exception polling BFL task: {e}")
                    continue
            
            logger.error("Image generation timed out.")
            return None

# Global instance
image_service = ImageGenerationService()
