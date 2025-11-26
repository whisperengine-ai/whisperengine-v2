import asyncio
import aiohttp
from loguru import logger
from typing import Optional, Dict, Any
from src_v2.config.settings import settings

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

    async def generate_image(self, prompt: str, width: int = 896, height: int = 1120) -> Optional[str]:
        """
        Generates an image from a prompt and returns the URL.
        Default is 4:5 portrait (896x1120).
        """
        if not self.api_key:
            logger.error("FLUX_API_KEY is not set. Cannot generate image.")
            return None

        if self.provider == "bfl":
            return await self._generate_bfl(prompt, width, height)
        else:
            logger.warning(f"Provider {self.provider} not implemented yet.")
            return None

    async def _generate_bfl(self, prompt: str, width: int, height: int) -> Optional[str]:
        """
        Generates image using BFL API (Async polling pattern).
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
                                return image_url
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
