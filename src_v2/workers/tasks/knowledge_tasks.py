from typing import Dict, Any
from loguru import logger

async def run_knowledge_extraction(
    ctx: Dict[str, Any],
    user_id: str,
    message: str,
    character_name: str = "unknown"
) -> Dict[str, Any]:
    """
    Extract facts from a message and store in Neo4j knowledge graph.
    
    This is the most critical background task - it was previously blocking
    the response pipeline. Now runs asynchronously after response is sent.
    
    Args:
        ctx: arq context
        user_id: Discord user ID
        message: User message text to extract facts from
        character_name: Name of the bot that received the message
        
    Returns:
        Dict with success status and extracted fact count
    """
    logger.info(f"Processing knowledge extraction for user {user_id} (source: {character_name})")
    
    try:
        from src_v2.knowledge.manager import knowledge_manager
        
        # This internally checks ENABLE_RUNTIME_FACT_EXTRACTION
        await knowledge_manager.process_user_message(user_id, message, character_name)
        
        return {
            "success": True,
            "user_id": user_id,
            "message_length": len(message)
        }
        
    except Exception as e:
        logger.error(f"Knowledge extraction failed for user {user_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "user_id": user_id
        }
