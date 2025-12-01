"""
Media Generation Tasks

Handles background generation of images and audio.
"""

import asyncio
from typing import Dict, Any, Optional
from loguru import logger

from src_v2.config.settings import settings
from src_v2.image_gen.service import image_service
from src_v2.image_gen.session import image_session
from src_v2.voice.tts import tts_manager
from src_v2.artifacts.registry import artifact_registry
from src_v2.broadcast.manager import BroadcastManager, PostType
from src_v2.core.quota import quota_manager

async def run_image_generation(
    ctx: Dict[str, Any],
    user_id: str,
    prompt: str,
    width: int,
    height: int,
    seed: Optional[int] = None,
    character_name: str = "default",
    channel_id: Optional[str] = None,
    message_id: Optional[str] = None
) -> str:
    """
    Generate an image in the background and queue a delivery message.
    """
    logger.info(f"Starting background image generation for {user_id} (char: {character_name})")
    
    try:
        # 1. Generate Image
        image_result = await image_service.generate_image(
            prompt=prompt,
            width=width,
            height=height,
            seed=seed
        )
        
        if not image_result:
            logger.error("Image generation returned None")
            return "failed"
            
        # 2. Save Session (for refinement)
        await image_session.save_session(
            user_id, 
            prompt,
            image_result.seed,
            {"width": width, "height": height}
        )
        
        # 3. Store in Artifact Registry
        await artifact_registry.add_image(
            user_id=user_id,
            data=image_result.image_bytes,
            filename=image_result.filename,
            prompt=prompt,
            seed=image_result.seed,
            url=image_result.url
        )
        
        # 4. Increment Quota
        await quota_manager.increment_usage(user_id, 'image')
        
        # 5. Queue Delivery Message via BroadcastManager
        # We use a special "media_delivery" post type or just OBSERVATION/REACTION
        # The bot will pick this up and send it to the channel
        
        broadcast_manager = BroadcastManager()
        
        # Construct a friendly delivery message
        delivery_text = f"Here is the image you requested: {prompt[:50]}..."
        
        # Queue it for the bot to pick up
        # We pass artifact_user_id so the bot knows to attach the files
        await broadcast_manager.queue_broadcast(
            content=delivery_text,
            post_type=PostType.REACTION, # Use REACTION for media replies
            character_name=character_name,
            artifact_user_id=user_id
        )
        
        logger.info(f"Image generated and delivery queued for {user_id}")
        return "success"
        
    except Exception as e:
        logger.error(f"Background image generation failed: {e}")
        return f"error: {str(e)}"


async def run_voice_generation(
    ctx: Dict[str, Any],
    user_id: str,
    text: str,
    voice_id: str,
    character_name: str
) -> str:
    """
    Generate voice audio in the background and queue a delivery message.
    """
    logger.info(f"Starting background voice generation for {user_id} (char: {character_name})")
    
    try:
        # 1. Generate Audio
        audio_bytes = await tts_manager.generate_speech(text, voice_id=voice_id)
        
        if not audio_bytes:
            logger.error("Voice generation returned None")
            return "failed"
            
        # 2. Store in Artifact Registry
        import os
        filename = f"{character_name.lower()}_voice_{os.urandom(4).hex()}.mp3"
        
        await artifact_registry.add_audio(
            user_id=user_id,
            data=audio_bytes,
            filename=filename,
            text=text,
            voice_id=voice_id
        )
        
        # 3. Increment Quota
        await quota_manager.increment_usage(user_id, 'audio')
        
        # 4. Queue Delivery Message
        broadcast_manager = BroadcastManager()
        
        # For voice, we might want to send the text as the message content
        # or just a "Voice message:" label if the text is long
        delivery_text = text if len(text) < 200 else "Voice message:"
        
        await broadcast_manager.queue_broadcast(
            content=delivery_text,
            post_type=PostType.REACTION,
            character_name=character_name,
            artifact_user_id=user_id
        )
        
        logger.info(f"Voice generated and delivery queued for {user_id}")
        return "success"
        
    except Exception as e:
        logger.error(f"Background voice generation failed: {e}")
        return f"error: {str(e)}"
