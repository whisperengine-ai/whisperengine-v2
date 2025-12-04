from typing import Dict, Any, Optional
from loguru import logger
from src_v2.agents.proactive import ProactiveAgent
from src_v2.broadcast.manager import broadcast_manager, PostType

async def run_proactive_message(
    ctx: Dict[str, Any],
    user_id: str,
    character_name: str,
    reason: str
) -> Dict[str, Any]:
    """
    Worker task to generate and send a proactive message.
    Triggered by Insight Agent via queue:action.
    """
    logger.info(f"Running proactive message task for {user_id} (reason: {reason})")
    
    agent = ProactiveAgent()
    
    # Generate opener
    # Note: user_name is not passed, we might need to fetch it or just use "Friend"
    # ProactiveAgent.generate_opener needs user_name.
    # We can try to fetch it from DB or just pass a placeholder.
    # Ideally, the caller should pass user_name.
    # But TriggerProactiveActionTool only takes user_id.
    # We can fetch user_name from DB if available.
    
    # For now, let's use "Friend" as fallback.
    user_name = "Friend"
    
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
