from typing import Optional
import aiohttp
import base64
from loguru import logger
from langchain_core.messages import HumanMessage
from src_v2.agents.llm_factory import create_llm
from src_v2.config.settings import settings
from src_v2.memory.manager import memory_manager


class VisionManager:
    def __init__(self):
        # Use reflective LLM for image analysis (utility task, needs vision capability)
        self.llm = create_llm(temperature=0.5, mode="reflective")

    async def _fetch_image_as_base64(self, image_url: str) -> Optional[str]:
        """
        Downloads an image and returns it as a base64 data URL.
        Fallback for when LLM providers can't access the URL directly (e.g., Discord CDN 403).
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as resp:
                    if resp.status == 200:
                        content_type = resp.headers.get('Content-Type', 'image/jpeg')
                        image_data = await resp.read()
                        b64_data = base64.b64encode(image_data).decode('utf-8')
                        return f"data:{content_type};base64,{b64_data}"
                    else:
                        logger.warning(f"Failed to fetch image: HTTP {resp.status}")
                        return None
        except Exception as e:
            logger.error(f"Error fetching image for base64 encoding: {e}")
            return None

    async def analyze_and_store(self, image_url: str, user_id: str, channel_id: str) -> Optional[str]:
        """
        Analyzes an image using a multimodal LLM and stores the description in memory.
        Returns the description.
        
        NOTE: This stores the visual description in vector memory for later recall,
        but does NOT extract structured facts to the knowledge graph. See:
        docs/roadmaps/VISION_FACT_EXTRACTION.md for the planned feature spec.
        """
        if not settings.LLM_SUPPORTS_VISION:
            logger.warning("Vision analysis requested but LLM_SUPPORTS_VISION is False.")
            return None

        try:
            logger.info(f"Analyzing image: {image_url}")
            
            # Try URL-based analysis first, fallback to base64 if it fails
            description = await self._try_analyze_image(image_url)
            
            if description is None:
                logger.info("URL-based analysis failed, trying base64 fallback...")
                b64_url = await self._fetch_image_as_base64(image_url)
                if b64_url:
                    description = await self._try_analyze_image(b64_url)
            
            if description is None:
                logger.error("Both URL and base64 analysis failed.")
                return None
            
            logger.info(f"Image description generated: {description[:50]}...")

            # Store in Memory
            memory_content = f"[Visual Memory] User sent an image. Description: {description}"
            
            await memory_manager.add_message(
                user_id=user_id,
                character_name=settings.DISCORD_BOT_NAME or "default_bot",
                role="system",
                content=memory_content,
                channel_id=channel_id,
                metadata={"type": "image_analysis", "image_url": image_url}
            )
            
            return str(description)

        except Exception as e:
            logger.error(f"Failed to analyze image: {e}")
            return None

    async def _try_analyze_image(self, image_url: str) -> Optional[str]:
        """
        Attempts to analyze an image using the LLM.
        Returns the description or None if it fails.
        """
        try:
            prompt = [
                HumanMessage(
                    content=[
                        {"type": "text", "text": "Describe this image in detail. Focus on the main subjects, setting, colors, and any text visible. Be objective but comprehensive."},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                )
            ]
            
            response = await self.llm.ainvoke(prompt)
            return response.content
        except Exception as e:
            logger.warning(f"Image analysis attempt failed: {e}")
            return None

vision_manager = VisionManager()
