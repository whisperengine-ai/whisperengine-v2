"""
Batch Knowledge Extraction Task

Extracts facts from an entire conversation session at once,
providing better context for fact extraction and reducing LLM costs.

This replaces per-message extraction with session-level extraction,
triggered at session end (when summarization runs).
"""
from typing import Dict, Any, List
from loguru import logger


async def run_batch_knowledge_extraction(
    ctx: Dict[str, Any],
    user_id: str,
    messages: List[Dict[str, str]],
    character_name: str = "unknown",
    session_id: str = ""
) -> Dict[str, Any]:
    """
    Extract facts from an entire conversation session.
    
    This is more effective than per-message extraction because:
    1. The LLM sees the full conversation flow
    2. It can identify relationships across messages
    3. It reduces redundant/fragmented facts
    4. One LLM call per session instead of N calls per message
    
    Args:
        ctx: arq context
        user_id: Discord user ID
        messages: List of message dicts with 'role' and 'content' keys
        character_name: Name of the bot that had the conversation
        session_id: Optional session identifier for logging
        
    Returns:
        Dict with success status and extracted fact count
    """
    # Filter to only human messages (we extract facts about the user)
    human_messages = [
        m["content"] for m in messages 
        if m.get("role") in ("human", "user") and m.get("content")
    ]
    
    if not human_messages:
        logger.debug(f"Batch extraction skipped for user {user_id}: no human messages")
        return {
            "success": True,
            "skipped": True,
            "reason": "no_human_messages",
            "user_id": user_id
        }
    
    # Combine all human messages into a single context block
    combined_text = "\n\n".join(human_messages)
    
    # Skip if total content is too short
    if len(combined_text.strip()) < 50:
        logger.debug(f"Batch extraction skipped for user {user_id}: combined text too short ({len(combined_text)} chars)")
        return {
            "success": True,
            "skipped": True,
            "reason": "content_too_short",
            "user_id": user_id
        }
    
    logger.info(f"Batch knowledge extraction for user {user_id}: {len(human_messages)} messages, {len(combined_text)} chars")
    
    try:
        from src_v2.knowledge.manager import knowledge_manager
        from src_v2.agents.knowledge_graph import knowledge_graph_agent
        from src_v2.config.settings import settings
        
        if not settings.ENABLE_RUNTIME_FACT_EXTRACTION:
            return {"success": True, "skipped": True, "reason": "disabled"}
        
        # Use Graph Agent for extraction (includes validation loop)
        # The agent sees the full conversation context
        facts = await knowledge_graph_agent.run(combined_text)
        
        if facts:
            # Save validated facts
            await knowledge_manager.save_facts(user_id, facts, character_name)
            
            logger.info(f"Batch extraction complete for user {user_id}: {len(facts)} facts from {len(human_messages)} messages")
            
            return {
                "success": True,
                "user_id": user_id,
                "facts_extracted": len(facts),
                "messages_processed": len(human_messages),
                "total_chars": len(combined_text),
                "session_id": session_id
            }
        else:
            return {
                "success": True,
                "user_id": user_id,
                "facts_extracted": 0,
                "messages_processed": len(human_messages),
                "total_chars": len(combined_text),
                "session_id": session_id
            }
        
    except Exception as e:
        logger.error(f"Batch knowledge extraction failed for user {user_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "user_id": user_id,
            "session_id": session_id
        }
