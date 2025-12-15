from typing import Dict, Any, List, Optional
from loguru import logger

async def run_summarization(
    ctx: Dict[str, Any],
    user_id: str,
    character_name: str,
    session_id: str,
    messages: List[Dict[str, Any]],
    user_name: Optional[str] = None,
    channel_id: Optional[str] = None
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
        channel_id: Optional channel ID for shared context retrieval
        
    Returns:
        Dict with success status and summary content
    """
    logger.info(f"Processing summarization for session {session_id} (user: {user_id}, character: {character_name})")
    
    # Check data availability before LLM call
    if not messages or len(messages) < 2:
        logger.info(f"Summarization skipped for session {session_id}: insufficient messages ({len(messages) if messages else 0})")
        return {
            "success": True,
            "skipped": True,
            "reason": "insufficient_messages",
            "session_id": session_id
        }
    
    try:
        # Lazy import to avoid circular dependencies
        from src_v2.memory.summarizer import SummaryManager
        from src_v2.agents.summary_graph import summary_graph_agent
        
        # Format conversation text
        conversation_text = ""
        for msg in messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            conversation_text += f"{role}: {content}\n"
        
        # Skip if conversation is too short (lowered threshold to catch short emotional exchanges)
        if len(conversation_text) < 30:
            logger.info(f"Summarization skipped for session {session_id}: conversation too short ({len(conversation_text)} chars)")
            return {
                "success": True,
                "skipped": True,
                "reason": "conversation_too_short",
                "session_id": session_id
            }
            
        # Use Graph Agent for generation (includes critique loop)
        result = await summary_graph_agent.run(conversation_text)
        
        if result is None:
            logger.warning(f"Summarization failed for session {session_id}: Agent returned None (likely JSON validation failure)")
            return {
                "success": False,
                "error": "agent_returned_none",
                "session_id": session_id
            }

        if result.meaningfulness_score >= 3:
            # Use SummaryManager for saving (it handles DB logic)
            summarizer = SummaryManager(bot_name=character_name)
            saved = await summarizer.save_summary(session_id, user_id, result, user_name=user_name, channel_id=channel_id)
            
            if saved:
                logger.info(f"Summary saved for session {session_id} (score: {result.meaningfulness_score})")
            else:
                logger.warning(f"Summary generated but failed to save for session {session_id}")
            
            return {
                "success": True,
                "saved": saved,
                "summary": result.summary,
                "meaningfulness_score": result.meaningfulness_score,
                "emotions": result.emotions,
                "topics": result.topics,
                "session_id": session_id
            }
        else:
            logger.info(f"Session {session_id} not meaningful enough to summarize (score: {result.meaningfulness_score})")
            return {
                "success": True,
                "skipped": True,
                "reason": "low_meaningfulness",
                "score": result.meaningfulness_score,
                "session_id": session_id
            }
            
    except Exception as e:
        logger.error(f"Summarization failed for session {session_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "session_id": session_id
        }
