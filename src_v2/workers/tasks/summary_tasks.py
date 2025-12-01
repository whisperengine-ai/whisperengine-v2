from typing import Dict, Any, List, Optional
from loguru import logger

async def run_summarization(
    ctx: Dict[str, Any],
    user_id: str,
    character_name: str,
    session_id: str,
    messages: List[Dict[str, Any]],
    user_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate a session summary and save to database.
    
    Args:
        ctx: arq context
        user_id: Discord user ID
        character_name: Bot character name
        session_id: Conversation session ID
        messages: List of message dicts with 'role' and 'content' keys
        user_name: User's display name (for diary provenance)
        
    Returns:
        Dict with success status and summary content
    """
    logger.info(f"Processing summarization for session {session_id} (user: {user_id}, character: {character_name})")
    
    try:
        # Lazy import to avoid circular dependencies
        from src_v2.memory.summarizer import SummaryManager
        
        # Pass character_name to ensure we use the correct memory collection
        summarizer = SummaryManager(bot_name=character_name)
        result = await summarizer.generate_summary(messages)
        
        if result and result.meaningfulness_score >= 3:
            await summarizer.save_summary(session_id, user_id, result, user_name=user_name)
            logger.info(f"Summary saved for session {session_id} (score: {result.meaningfulness_score})")
            return {
                "success": True,
                "summary": result.summary,
                "meaningfulness_score": result.meaningfulness_score,
                "emotions": result.emotions,
                "session_id": session_id
            }
        else:
            logger.info(f"Session {session_id} not meaningful enough to summarize (score: {result.meaningfulness_score if result else 0})")
            return {
                "success": True,
                "skipped": True,
                "reason": "low_meaningfulness",
                "score": result.meaningfulness_score if result else 0,
                "session_id": session_id
            }
            
    except Exception as e:
        logger.error(f"Summarization failed for session {session_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "session_id": session_id
        }
