from typing import Dict, Any
from loguru import logger

# Import the context stripping function from shared utility
from src_v2.utils.content_cleaning import strip_context_markers

async def run_knowledge_extraction(
    ctx: Dict[str, Any],
    user_id: str,
    message: str,
    character_name: str = "unknown",
    is_bot: bool = False
) -> Dict[str, Any]:
    """
    Extract facts from a message and store in Neo4j knowledge graph.
    
    This is the most critical background task - it was previously blocking
    the response pipeline. Now runs asynchronously after response is sent.
    
    DEPRECATED: Use run_batch_knowledge_extraction for session-level extraction.
    
    Args:
        ctx: arq context
        user_id: Discord user ID
        message: User message text to extract facts from
        character_name: Name of the bot that received the message
        is_bot: If True, the message is from the bot itself (self-reflection)
        
    Returns:
        Dict with success status and extracted fact count
    """
    # Strip context markers (reply quotes, forwards) to avoid extracting
    # facts about other users/bots from quoted content
    if not is_bot:
        message = strip_context_markers(message)
    
    # Check data availability before LLM call
    if not message or len(message.strip()) < 20:
        logger.debug(f"Knowledge extraction skipped for user {user_id}: message too short ({len(message) if message else 0} chars)")
        return {
            "success": True,
            "skipped": True,
            "reason": "message_too_short",
            "user_id": user_id
        }
    
    logger.info(f"Processing knowledge extraction for user {user_id} (source: {character_name}, is_bot: {is_bot})")
    
    try:
        from src_v2.knowledge.manager import knowledge_manager
        from src_v2.agents.knowledge_graph import knowledge_graph_agent
        from src_v2.config.settings import settings
        
        if not settings.ENABLE_RUNTIME_FACT_EXTRACTION:
            return {"success": True, "skipped": True, "reason": "disabled"}
        
        # Use Graph Agent for extraction (includes validation loop)
        facts = await knowledge_graph_agent.run(message)
        
        if facts:
            # Save validated facts
            # If is_bot is True, we treat this as self-reflection (Character node)
            await knowledge_manager.save_facts(user_id, facts, character_name, is_self_reflection=is_bot)
            
            return {
                "success": True,
                "user_id": user_id,
                "facts_extracted": len(facts),
                "message_length": len(message)
            }
        else:
            return {
                "success": True,
                "user_id": user_id,
                "facts_extracted": 0,
                "message_length": len(message)
            }
        
    except Exception as e:
        logger.error(f"Knowledge extraction failed for user {user_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "user_id": user_id
        }
