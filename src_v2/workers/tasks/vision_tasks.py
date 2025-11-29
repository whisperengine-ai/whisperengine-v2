from typing import Dict, Any
from loguru import logger
from src_v2.config.settings import settings

async def run_vision_analysis(
    ctx: Dict[str, Any],
    image_url: str,
    user_id: str,
    channel_id: str
) -> Dict[str, Any]:
    """
    Analyze an image attachment and store the description.
    
    Args:
        ctx: arq context
        image_url: URL of the image to analyze
        user_id: Discord user ID who sent the image
        channel_id: Channel ID where image was sent
        
    Returns:
        Dict with success status
    """
    if not settings.LLM_SUPPORTS_VISION:
        return {"success": False, "reason": "vision_disabled"}
        
    logger.info(f"Running vision analysis for user {user_id}")
    
    try:
        from src_v2.vision.manager import vision_manager
        
        await vision_manager.analyze_and_store(
            image_url=image_url,
            user_id=user_id,
            channel_id=channel_id
        )
        
        return {
            "success": True,
            "user_id": user_id,
            "image_url": image_url
        }
            
    except Exception as e:
        logger.error(f"Vision analysis failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "user_id": user_id
        }
