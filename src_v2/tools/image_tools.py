from typing import Type, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from loguru import logger

from src_v2.image_gen.service import image_service
from src_v2.core.character import character_manager
from src_v2.config.settings import settings

class GenerateImageInput(BaseModel):
    prompt: str = Field(description="A description of the image to generate. Be creative and descriptive.")
    style: str = Field(description="The artistic style of the image (e.g., 'photorealistic', 'oil painting', 'sketch', 'cyberpunk').", default="photorealistic")

class GenerateImageTool(BaseTool):
    name: str = "generate_image"
    description: str = "Generates an image based on a prompt. Use this when the user asks to see something, or when you want to show a visual representation of your thoughts. The prompt should be descriptive."
    args_schema: Type[BaseModel] = GenerateImageInput
    character_name: str = Field(exclude=True)

    def _run(self, prompt: str, style: str = "photorealistic") -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, prompt: str, style: str = "photorealistic") -> str:
        try:
            # 1. Get Character Visual Description
            character = character_manager.get_character(self.character_name)
            visual_desc = character.visual_description if character else "A generic AI assistant."
            
            # 2. Construct Enhanced Prompt
            # "A photorealistic image of [Visual Desc]. [User Prompt]. Style: [Style]"
            enhanced_prompt = f"{style} image of {visual_desc}. {prompt}"
            
            logger.info(f"Generating image with prompt: {enhanced_prompt}")
            
            # 3. Call Service
            image_url = await image_service.generate_image(enhanced_prompt)
            
            if image_url:
                return f"Image generated successfully: {image_url}\n(SYSTEM: You MUST include this URL in your final response.)"
            else:
                return "Failed to generate image. Please try again later."
                
        except Exception as e:
            logger.error(f"Error in GenerateImageTool: {e}")
            return f"Error generating image: {e}"
