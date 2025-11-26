import asyncio
import aiohttp
import uuid
from io import BytesIO
from loguru import logger
from typing import Optional, Dict, Any, Tuple
from src_v2.config.settings import settings

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


import time

class PendingImageRegistry:
    """
    Thread-safe registry for images generated during response generation.
    Images are stored temporarily and retrieved by the Discord bot for upload.
    Includes TTL cleanup to prevent memory leaks.
    """
    
    def __init__(self):
        self._images: Dict[str, Tuple[float, ImageGenerationResult]] = {}
        self._ttl = 300  # 5 minutes
    
    def _cleanup(self):
        """Remove expired images."""
        now = time.time()
        expired = [k for k, (ts, _) in self._images.items() if now - ts > self._ttl]
        for k in expired:
            del self._images[k]
        if expired:
            logger.debug(f"Cleaned up {len(expired)} expired pending images")

    def register(self, result: ImageGenerationResult) -> str:
        """
        Register an image and return a unique ID for later retrieval.
        
        Args:
            result: The ImageGenerationResult to store
            
        Returns:
            A unique string ID that can be embedded in the response
        """
        self._cleanup()  # Lazy cleanup on registration
        image_id = str(uuid.uuid4())[:8]  # Short unique ID
        self._images[image_id] = (time.time(), result)
        logger.debug(f"Registered pending image: {image_id}")
        return image_id
    
    def retrieve(self, image_id: str) -> Optional[ImageGenerationResult]:
        """
        Retrieve and remove an image from the registry.
        
        Args:
            image_id: The unique ID returned from register()
            
        Returns:
            The ImageGenerationResult if found, None otherwise
        """
        entry = self._images.pop(image_id, None)
        if entry:
            logger.debug(f"Retrieved pending image: {image_id}")
            return entry[1]
        return None
    
    def clear(self) -> None:
        """Clear all pending images (cleanup on error)."""
        self._images.clear()


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
