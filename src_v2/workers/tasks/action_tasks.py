from typing import Dict, Any, Optional
from loguru import logger
from src_v2.agents.proactive import ProactiveAgent
from src_v2.broadcast.manager import broadcast_manager, PostType


async def _get_user_display_name(user_id: str, character_name: str) -> str:
    """
    Fetch user's display name from the database.
    Falls back to "Friend" if not found.
    """
    try:
        from src_v2.core.database import db_manager
        
        if db_manager.postgres_pool:
            async with db_manager.postgres_pool.acquire() as conn:
                # Try to get from trust profile first (most reliable)
                row = await conn.fetchrow("""
                    SELECT user_name FROM v2_trust_profiles 
                    WHERE user_id = $1 AND character_name = $2
                """, user_id, character_name)
                
                if row and row["user_name"]:
                    return row["user_name"]
                    
                # Fallback: get from most recent chat history
                row = await conn.fetchrow("""
                    SELECT user_name FROM v2_chat_history 
                    WHERE user_id = $1 AND character_name = $2 AND user_name IS NOT NULL
                    ORDER BY timestamp DESC LIMIT 1
                """, user_id, character_name)
                
                if row and row["user_name"]:
                    return row["user_name"]
    except Exception as e:
        logger.debug(f"Failed to fetch user display name: {e}")
    
    return "Friend"


async def run_proactive_message(
    ctx: Dict[str, Any],
    user_id: str,
    character_name: str,
    reason: str,
    user_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Worker task to generate and send a proactive message.
    Triggered by Insight Agent via queue:action.
    
    Args:
        ctx: arq context
        user_id: Discord user ID
        character_name: Bot character name
        reason: Why this proactive message is being sent
        user_name: Optional display name (fetched from DB if not provided)
        
    Returns:
        Dict with success status and content
    """
    from src_v2.config.settings import settings
    if not settings.ENABLE_PROACTIVE_MESSAGING:
        logger.info(f"Skipping proactive message for {user_id}: ENABLE_PROACTIVE_MESSAGING is False")
        return {"success": False, "reason": "disabled"}

    logger.info(f"Running proactive message task for {user_id} (reason: {reason})")
    
    agent = ProactiveAgent()
    
    # Fetch user_name from DB if not provided
    if not user_name:
        user_name = await _get_user_display_name(user_id, character_name)
    
    content = await agent.generate_opener(
        user_id=user_id,
        user_name=user_name,
        character_name=character_name,
        is_public=False
    )
    
    if not content:
        logger.warning(f"ProactiveAgent failed to generate content for {user_id}")
        return {"success": False, "reason": "generation_failed"}
        
    # Queue for sending via bot
    success = await broadcast_manager.queue_broadcast(
        content=content,
        post_type=PostType.MUSING, # Use MUSING as generic type
        character_name=character_name,
        target_user_id=user_id,
        provenance=[{"source": "insight_agent", "reason": reason}]
    )
    
    return {"success": success, "content": content}
