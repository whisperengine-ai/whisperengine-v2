from typing import Type, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from langchain_core.messages import SystemMessage, HumanMessage
from loguru import logger

from src_v2.image_gen.service import image_service, pending_images
from src_v2.core.character import character_manager
from src_v2.agents.llm_factory import create_llm

class GenerateImageInput(BaseModel):
    prompt: str = Field(description="A description of the image to generate. Be creative and descriptive.")
    style: str = Field(description="The artistic style of the image (e.g., 'photorealistic', 'oil painting', 'sketch', 'cyberpunk').", default="photorealistic")
    aspect_ratio: str = Field(
        description="The aspect ratio of the image. Choose based on the subject matter.", 
        default="portrait",
        enum=["portrait", "landscape", "square", "widescreen"]
    )

class GenerateImageTool(BaseTool):
    name: str = "generate_image"
    description: str = "Generates an image based on a prompt. Use this when the user asks to see something, or when you want to show a visual representation of your thoughts. The prompt should be descriptive. You can choose the aspect ratio (portrait, landscape, square, widescreen)."
    args_schema: Type[BaseModel] = GenerateImageInput
    character_name: str = Field(exclude=True)
    user_id: str = Field(exclude=True)

    def _run(self, prompt: str, style: str = "photorealistic", aspect_ratio: str = "portrait") -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, prompt: str, style: str = "photorealistic", aspect_ratio: str = "portrait") -> str:
        try:
            # 1. Map Aspect Ratio to Dimensions
            # Flux 1.1 Pro has a hard limit of 1440px on any dimension.
            # All dimensions should be multiples of 32.
            width, height = 1152, 1440 # Default Portrait (4:5)
            
            if aspect_ratio == "landscape":
                width, height = 1440, 832 # 16:9 (approx)
            elif aspect_ratio == "square":
                width, height = 1440, 1440 # 1:1
            elif aspect_ratio == "widescreen":
                width, height = 1440, 608 # 2.37:1 (approx 2.4:1)
            elif aspect_ratio == "portrait":
                width, height = 1152, 1440 # 4:5
            
            # 2. Get Character Visual Description
            # Try to get from DB first (via the new async method), fallback to file
            visual_desc = await character_manager.get_visual_description(self.character_name)
            
            # Self-Discovery Logic: If no specific description exists, generate one
            if visual_desc == "A generic AI assistant.":
                logger.info(f"No visual description found for {self.character_name}. Initiating Self-Discovery...")
                
                # Get character system prompt for context
                char = character_manager.get_character(self.character_name)
                system_prompt = char.system_prompt if char else "You are an AI assistant."
                
                # Generate description using utility LLM
                try:
                    llm = create_llm(temperature=0.7, mode="utility")
                    messages = [
                        SystemMessage(content=system_prompt),
                        HumanMessage(content="You don't have a physical form defined yet. Based on your personality and background, describe exactly what you look like in 3 sentences. Focus on physical appearance, clothing, and vibe. Do not use bullet points.")
                    ]
                    response = await llm.ainvoke(messages)
                    new_desc = response.content.strip()
                    
                    logger.info(f"Generated new visual description: {new_desc}")
                    
                    # Save to DB for persistence
                    await character_manager.update_visual_description(self.character_name, new_desc)
                    visual_desc = new_desc
                except Exception as e:
                    logger.error(f"Self-Discovery failed: {e}. Using default.")
            
            # 3. Construct Enhanced Prompt
            # "A photorealistic image of [Visual Desc]. [User Prompt]. Style: [Style]"
            enhanced_prompt = f"{style} image of {visual_desc}. {prompt}"
            
            logger.info(f"Generating image with prompt: {enhanced_prompt} (Size: {width}x{height})")
            
            # 4. Call Service
            image_result = await image_service.generate_image(enhanced_prompt, width=width, height=height)
            
            if image_result:
                # Register the image for later retrieval by the Discord bot
                # We use the user_id to queue the image for the final response
                await pending_images.add(self.user_id, image_result)
                return f"Image generated successfully ({aspect_ratio})."
            else:
                return "Failed to generate image. Please try again later."
                
        except Exception as e:
            logger.error(f"Error in GenerateImageTool: {e}")
            return f"Error generating image: {e}"
