from typing import Type, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from langchain_core.messages import SystemMessage, HumanMessage
from loguru import logger

from src_v2.image_gen.service import image_service, pending_images
from src_v2.image_gen.session import (
    image_session, 
    parse_refinement_instructions,
    apply_refinement_to_prompt
)
from src_v2.core.character import character_manager
from src_v2.agents.llm_factory import create_llm
from src_v2.evolution.trust import trust_manager
from src_v2.config.settings import settings
from src_v2.core.quota import quota_manager

class GenerateImageInput(BaseModel):
    prompt: str = Field(description="A detailed description of the image to generate. Include specific physical details, artistic style (e.g., photorealistic, cinematic, anime, watercolor, oil painting), lighting, and mood. Be creative and vivid. For self-portraits, use the character's visual description provided in the tool description.")
    image_type: str = Field(
        description="The type of image being generated. 'self' = self-portrait of the AI character, 'other' = image of user/scenery/objects/other people, 'refine' = tweaking a previous image.",
        default="other",
        enum=["self", "other", "refine"]
    )
    aspect_ratio: str = Field(
        description="The aspect ratio of the image. Choose based on the subject matter.", 
        default="portrait",
        enum=["portrait", "landscape", "square", "widescreen"]
    )

class GenerateImageTool(BaseTool):
    name: str = "generate_image"
    description: str = ""  # Will be set dynamically in __init__
    args_schema: Type[BaseModel] = GenerateImageInput
    character_name: str = ""
    user_id: str = ""
    _visual_description: str = ""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Load visual description synchronously from file (async DB lookup happens at runtime)
        char = character_manager.get_character(self.character_name)
        self._visual_description = char.visual_description if char else "A generic AI assistant."
        
        # Build dynamic description with character's appearance
        base_desc = (
            "Generates an image based on a prompt. Use this when the user asks to see something, "
            "or wants a visual. Include the artistic style and mood in your prompt "
            "(e.g., 'cinematic portrait with dramatic lighting', 'soft watercolor of a sunset'). "
            "Choose aspect ratio: portrait (4:5), landscape (16:9), square (1:1), widescreen (2.4:1). "
            "Set refine=true when the user is tweaking/adjusting a previous image."
        )
        
        # Add self-portrait guidance - with specific description if available, otherwise instruct to derive from character
        if self._visual_description and self._visual_description != "A generic AI assistant.":
            self.description = (
                f"{base_desc}\n\n"
                f"YOUR APPEARANCE (use this for self-portraits): {self._visual_description}\n"
                f"When generating images of yourself, include these specific physical details in your prompt."
            )
        else:
            self.description = (
                f"{base_desc}\n\n"
                f"SELF-PORTRAIT GUIDANCE: When generating images of yourself, derive your physical appearance "
                f"from your character description in the system prompt. Include specific visual details like: "
                f"form (humanoid, digital, ethereal, etc.), coloring, distinguishing features, clothing/style, "
                f"and any characteristic visual elements. Be detailed and consistent with your established identity."
            )
    def _run(self, prompt: str, image_type: str = "other", aspect_ratio: str = "portrait") -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, prompt: str, image_type: str = "other", aspect_ratio: str = "portrait") -> str:
        try:
            # 0. Trust Gate - Check if user has sufficient trust level
            min_trust = settings.IMAGE_GEN_MIN_TRUST
            if min_trust > 0:
                relationship = await trust_manager.get_relationship_level(self.user_id, self.character_name)
                current_trust = relationship.get("trust_score", 0)
                if current_trust < min_trust:
                    logger.info(f"Image generation blocked for user {self.user_id}: trust {current_trust} < {min_trust}")
                    return f"I'd love to create images for you, but we need to get to know each other a bit better first! (Trust: {current_trust}/{min_trust})"
            
            # 0.5 Quota Check
            has_quota = await quota_manager.check_quota(self.user_id, 'image')
            if not has_quota:
                logger.info(f"Image generation blocked for user {self.user_id}: Daily quota exceeded")
                return f"You've reached your daily image generation limit ({settings.DAILY_IMAGE_QUOTA}). Please try again tomorrow!"

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
            
            # 3. Determine image type from LLM-provided parameter
            # The classifier detects intent (image_self, image_other, image_refine) and the 
            # reflective agent sets image_type accordingly. No more keyword detection needed.
            enhanced_prompt = prompt
            seed_to_use = None
            
            if image_type == "self":
                # Self-portrait: Prepend character visual description
                enhanced_prompt = f"{visual_desc}. {prompt}"
                logger.info("Self-portrait mode: Including character visual description")
            elif image_type == "refine":
                # Refinement: Reuse seed from previous generation and merge prompts
                previous = await image_session.get_session(self.user_id)
                if previous:
                    seed_to_use = previous.get("seed")
                    previous_prompt = previous.get("prompt", "")
                    
                    # Parse refinement instructions to extract keep/remove/change elements
                    keep_elements, remove_elements, modification = parse_refinement_instructions(prompt)
                    
                    if keep_elements or remove_elements:
                        # Smart refinement: apply structured changes to previous prompt
                        enhanced_prompt = apply_refinement_to_prompt(
                            previous_prompt, 
                            modification, 
                            keep_elements, 
                            remove_elements
                        )
                        logger.info(f"Smart refinement: keep={keep_elements}, remove={remove_elements}")
                    elif len(prompt) < 30:
                        # Short prompt without explicit keep/remove - treat as simple addition
                        enhanced_prompt = f"{previous_prompt}. {prompt}"
                        logger.info("Simple refinement: appending to previous prompt")
                    else:
                        # Longer prompt - assume it's a full new description but keep seed
                        logger.info("Full prompt refinement: using new prompt with previous seed")
                    
                    logger.info(f"Refine mode: Reusing seed {seed_to_use} from previous generation")
                else:
                    logger.info("Refine mode requested but no previous session found. Using new seed.")
            else:
                # image_type == "other": Use prompt as-is for user/scenery/objects
                logger.info("Other subject mode: Using prompt as-is (no character injection)")
            
            logger.info(f"Generating image with prompt: {enhanced_prompt[:100]}... (Size: {width}x{height}, Seed: {seed_to_use or 'random'})")
            
            # 4. Call Service
            image_result = await image_service.generate_image(enhanced_prompt, width=width, height=height, seed=seed_to_use)
            
            if image_result:
                # Save prompt and seed for future refinement
                await image_session.save_session(
                    self.user_id, 
                    enhanced_prompt,
                    image_result.seed,
                    {"width": width, "height": height}
                )
                
                # Register the image for later retrieval by the Discord bot
                await pending_images.add(self.user_id, image_result)
                
                # Increment Quota
                await quota_manager.increment_usage(self.user_id, 'image')
                
                return f"Image generated successfully ({aspect_ratio})."
            else:
                return "Failed to generate image. Please try again later."
                
        except Exception as e:
            logger.error(f"Error in GenerateImageTool: {e}")
            return f"Error generating image: {e}"
