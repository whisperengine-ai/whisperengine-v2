from typing import Type, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from langchain_core.messages import SystemMessage, HumanMessage
from loguru import logger

from src_v2.image_gen.service import image_service
from src_v2.core.character import character_manager
from src_v2.agents.llm_factory import create_llm

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
