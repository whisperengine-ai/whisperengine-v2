from typing import Dict, Any, Optional
from loguru import logger
from src_v2.config.settings import settings

async def run_goal_analysis(
    ctx: Dict[str, Any],
    user_id: str,
    character_name: str,
    interaction_text: str
) -> Dict[str, Any]:
    """
    Analyze an interaction to see if it advances any character goals.
    
    Args:
        ctx: arq context
        user_id: Discord user ID
        character_name: Bot character name
        interaction_text: Combined user message and AI response
        
    Returns:
        Dict with success status
    """
    logger.info(f"Running goal analysis for {character_name} with user {user_id}")
    
    try:
        from src_v2.evolution.goals import goal_analyzer
        
        await goal_analyzer.check_goals(user_id, character_name, interaction_text)
        
        return {
            "success": True,
            "user_id": user_id,
            "character_name": character_name
        }
        
    except Exception as e:
        logger.error(f"Goal analysis failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "user_id": user_id
        }


async def run_preference_extraction(
    ctx: Dict[str, Any],
    user_id: str,
    character_name: str,
    message_content: str
) -> Dict[str, Any]:
    """
    Extract user preferences from a message and update the trust profile.
    
    Args:
        ctx: arq context
        user_id: Discord user ID
        character_name: Bot character name
        message_content: User message text
        
    Returns:
        Dict with success status and extracted preferences
    """
    if not settings.ENABLE_PREFERENCE_EXTRACTION:
        return {"success": False, "reason": "disabled"}
        
    logger.info(f"Running preference extraction for user {user_id}")
    
    try:
        from src_v2.evolution.extractor import preference_extractor
        from src_v2.evolution.trust import trust_manager
        
        prefs = await preference_extractor.extract_preferences(message_content)
        
        if prefs:
            logger.info(f"Detected preferences for {user_id}: {prefs}")
            for key, value in prefs.items():
                await trust_manager.update_preference(user_id, character_name, key, value)
                
            return {
                "success": True,
                "user_id": user_id,
                "preferences": prefs
            }
        else:
            return {
                "success": True,
                "user_id": user_id,
                "preferences": {}
            }
            
    except Exception as e:
        logger.error(f"Preference extraction failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "user_id": user_id
        }
