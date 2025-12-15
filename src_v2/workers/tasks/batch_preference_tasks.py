"""
Batch Preference Extraction Task

Extracts user preferences from an entire conversation session at once,
providing better context and reducing redundant preference detections.

This replaces per-message extraction with session-level extraction,
triggered at session end alongside batch knowledge extraction.
"""
from typing import Dict, Any, List
from loguru import logger


async def run_batch_preference_extraction(
    ctx: Dict[str, Any],
    user_id: str,
    character_name: str = "unknown",
    session_id: str = ""
) -> Dict[str, Any]:
    """
    Extract preferences from an entire conversation session.
    
    This is more effective than per-message extraction because:
    1. The LLM sees the full conversation context
    2. It can identify consistent preference patterns vs one-off requests
    3. It deduplicates redundant preference detections
    4. One LLM call per session instead of N calls per message
    
    Args:
        ctx: arq context
        user_id: Discord user ID
        character_name: Name of the bot that had the conversation
        session_id: Session identifier for logging and DB lookup
        
    Returns:
        Dict with success status and extracted preferences
    """
    from src_v2.config.settings import settings
    from src_v2.core.database import db_manager
    
    if not settings.ENABLE_PREFERENCE_EXTRACTION:
        return {"success": True, "skipped": True, "reason": "disabled"}
    
    # Fetch messages from DB
    messages = []
    if db_manager.postgres_pool:
        async with db_manager.postgres_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT role, content 
                FROM v2_chat_history 
                WHERE session_id = $1 
                ORDER BY timestamp ASC
            """, session_id)
            messages = [{"role": r["role"], "content": r["content"]} for r in rows]
    
    # Filter to only human messages (we extract preferences from the user)
    human_messages = [
        m["content"] for m in messages 
        if m.get("role") in ("human", "user") and m.get("content")
    ]
    
    if not human_messages:
        logger.debug(f"Batch preference extraction skipped for user {user_id}: no human messages")
        return {
            "success": True,
            "skipped": True,
            "reason": "no_human_messages",
            "user_id": user_id
        }
    
    # Combine all human messages into a single context block
    combined_text = "\n\n".join(human_messages)
    
    # Skip if total content is too short (unlikely to contain preferences)
    if len(combined_text.strip()) < 30:
        logger.debug(f"Batch preference extraction skipped for user {user_id}: combined text too short ({len(combined_text)} chars)")
        return {
            "success": True,
            "skipped": True,
            "reason": "content_too_short",
            "user_id": user_id
        }
    
    logger.info(f"Batch preference extraction for user {user_id}: {len(human_messages)} messages, {len(combined_text)} chars")
    
    try:
        from src_v2.evolution.extractor import preference_extractor
        from src_v2.evolution.trust import trust_manager
        from src_v2.utils.validation import smart_truncate
        
        # Truncate to avoid context window issues (2000 chars is plenty for preferences)
        truncated_text = smart_truncate(combined_text, max_length=2000)
        
        # Extract preferences from combined conversation
        prefs = await preference_extractor.extract_preferences(truncated_text)
        
        if prefs:
            logger.info(f"Batch extraction found preferences for {user_id}: {prefs}")
            for key, value in prefs.items():
                await trust_manager.update_preference(user_id, character_name, key, value)
            
            return {
                "success": True,
                "user_id": user_id,
                "preferences": prefs,
                "messages_processed": len(human_messages),
                "total_chars": len(combined_text),
                "session_id": session_id
            }
        else:
            return {
                "success": True,
                "user_id": user_id,
                "preferences": {},
                "messages_processed": len(human_messages),
                "session_id": session_id
            }
            
    except Exception as e:
        logger.error(f"Batch preference extraction failed for user {user_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "user_id": user_id
        }
