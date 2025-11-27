from typing import Type, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from langchain_core.messages import SystemMessage, HumanMessage
from loguru import logger

from src_v2.image_gen.service import image_service, pending_images
from src_v2.image_gen.session import image_session
from src_v2.core.character import character_manager
from src_v2.agents.llm_factory import create_llm
from src_v2.evolution.trust import trust_manager
from src_v2.config.settings import settings

class GenerateImageInput(BaseModel):
    prompt: str = Field(description="A detailed description of the image to generate. Include specific physical details, artistic style (e.g., photorealistic, cinematic, anime, watercolor, oil painting), lighting, and mood. Be creative and vivid. For self-portraits, use the character's visual description provided in the tool description.")
    aspect_ratio: str = Field(
        description="The aspect ratio of the image. Choose based on the subject matter.", 
        default="portrait",
        enum=["portrait", "landscape", "square", "widescreen"]
    )
    refine: bool = Field(
        description="Set to true if the user is refining/tweaking a previous image. This reuses the previous seed for consistency.",
        default=False
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
    def _run(self, prompt: str, aspect_ratio: str = "portrait", refine: bool = False) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, prompt: str, aspect_ratio: str = "portrait", refine: bool = False) -> str:
        try:
            # 0. Trust Gate - Check if user has sufficient trust level
            min_trust = settings.IMAGE_GEN_MIN_TRUST
            if min_trust > 0:
                relationship = await trust_manager.get_relationship_level(self.user_id, self.character_name)
                current_trust = relationship.get("trust_score", 0)
                if current_trust < min_trust:
                    logger.info(f"Image generation blocked for user {self.user_id}: trust {current_trust} < {min_trust}")
                    return f"I'd love to create images for you, but we need to get to know each other a bit better first! (Trust: {current_trust}/{min_trust})"
            
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
            
            # 3. Determine if this is a self-portrait or user/other subject
            # Check if the prompt is about the character itself
            char_name_lower = self.character_name.lower()
            prompt_lower = prompt.lower()
            
            # Keywords that suggest the image is OF the character (self-portrait)
            # Priority 1: Explicit character name mention (strongest signal)
            has_char_name = char_name_lower in prompt_lower
            
            # Priority 2: First-person self-references
            self_keywords = [
                "me", "myself", "my face", "my appearance", "what i look like",
                "selfie", "self-portrait", "self portrait",
                "my form", "my visual", "my figure", "my silhouette",
                "your face", "your appearance", "your form"
            ]
            
            # Keywords that suggest the image is FOR/ABOUT the user (human) or another subject
            # NOTE: "her/she/him/he" are NOT included - they're ambiguous and often refer to the character
            user_keywords = [
                "you", "your", "yourself", "user", "portrait of you",
                "what you look like", "for you", "of you",
                "person", "man", "woman", "guy", "girl", "captain",
                "human", "crew", "people"
            ]
            
            is_self_image = has_char_name or any(kw in prompt_lower for kw in self_keywords)
            is_user_image = any(kw in prompt_lower for kw in user_keywords)
            
            # Character name mention is a STRONG signal - override user_keywords if present
            # e.g., "ARIA's form" should be self-portrait even if prompt mentions "captain"
            if has_char_name:
                is_user_image = False
                logger.debug(f"Character name '{char_name_lower}' found in prompt - forcing self-portrait mode")
            
            # Only include character visual description for self-portraits
            # NOT when creating images for/of the user or other subjects
            # Phase A8: Enhanced Portrait Mode Detection
            # We inject the character description if it's clearly about the character (is_self_image)
            # AND it's not explicitly about the user or someone else (is_user_image).
            if is_self_image and not is_user_image:
                enhanced_prompt = f"{visual_desc}. {prompt}"
                logger.info(f"Self-portrait mode: Including character visual description (char_name={has_char_name})")
            else:
                enhanced_prompt = prompt
                logger.info("User/Other subject mode: Using prompt as-is (no character injection)")
            
            # 4. Handle Refinement Mode
            # If refining, try to reuse the previous seed for consistency
            seed_to_use = None
            if refine:
                previous = await image_session.get_session(self.user_id)
                if previous:
                    seed_to_use = previous.get("seed")
                    previous_prompt = previous.get("prompt", "")
                    
                    # If refining, we might want to append the new prompt to the old one
                    # or just use the new one if it's a full description.
                    # For now, let's assume the user provides a full new prompt or a delta.
                    # If the new prompt is very short (< 20 chars), assume it's a delta.
                    if len(prompt) < 20:
                        enhanced_prompt = f"{previous_prompt}, {prompt}"
                    
                    logger.info(f"Refine mode: Reusing seed {seed_to_use} from previous generation")
                else:
                    logger.info("Refine mode requested but no previous prompt found. Using new seed.")
            
            logger.info(f"Generating image with prompt: {enhanced_prompt[:100]}... (Size: {width}x{height}, Seed: {seed_to_use or 'random'})")
            
            # 5. Call Service
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
                return f"Image generated successfully ({aspect_ratio})."
            else:
                return "Failed to generate image. Please try again later."
                
        except Exception as e:
            logger.error(f"Error in GenerateImageTool: {e}")
            return f"Error generating image: {e}"
