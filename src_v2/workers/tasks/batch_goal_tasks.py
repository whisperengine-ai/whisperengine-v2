"""
Batch Goal Analysis Task

Analyzes an entire conversation session to determine goal progress,
rather than checking after every single message exchange.

This replaces per-message goal analysis with session-level analysis,
triggered at session end alongside other batch processing tasks.
"""
from typing import Dict, Any, List
from loguru import logger


async def run_batch_goal_analysis(
    ctx: Dict[str, Any],
    user_id: str,
    messages: List[Dict[str, str]],
    character_name: str = "unknown",
    session_id: str = ""
) -> Dict[str, Any]:
    """
    Analyze goal progress from an entire conversation session.
    
    This is more effective than per-message analysis because:
    1. The LLM sees the full conversation arc
    2. It can detect gradual goal progress across multiple exchanges
    3. One LLM call per session instead of N calls per response
    4. Reduces redundant "no_change" detections
    
    Args:
        ctx: arq context
        user_id: Discord user ID
        messages: List of message dicts with 'role' and 'content' keys
        character_name: Name of the bot that had the conversation
        session_id: Optional session identifier for logging
        
    Returns:
        Dict with success status and goal analysis stats
    """
    from src_v2.evolution.goals import goal_manager, goal_analyzer
    
    # Check if there are any active goals before doing expensive processing
    active_goals = await goal_manager.get_active_goals(user_id, character_name)
    if not active_goals:
        logger.debug(f"Batch goal analysis skipped for {character_name}: no active goals")
        return {
            "success": True,
            "skipped": True,
            "reason": "no_active_goals",
            "user_id": user_id
        }
    
    # Build conversation text from all messages
    if not messages:
        logger.debug(f"Batch goal analysis skipped for user {user_id}: no messages")
        return {
            "success": True,
            "skipped": True,
            "reason": "no_messages",
            "user_id": user_id
        }
    
    # Format conversation as alternating User/AI text
    conversation_parts = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if not content:
            continue
        
        if role in ("human", "user"):
            conversation_parts.append(f"User: {content}")
        elif role in ("ai", "assistant"):
            conversation_parts.append(f"AI: {content}")
    
    if not conversation_parts:
        return {
            "success": True,
            "skipped": True,
            "reason": "no_content",
            "user_id": user_id
        }
    
    conversation_text = "\n".join(conversation_parts)
    
    # Skip if total content is too short
    if len(conversation_text.strip()) < 50:
        logger.debug(f"Batch goal analysis skipped for user {user_id}: conversation too short ({len(conversation_text)} chars)")
        return {
            "success": True,
            "skipped": True,
            "reason": "conversation_too_short",
            "user_id": user_id
        }
    
    logger.info(f"Batch goal analysis for {character_name} with user {user_id}: {len(messages)} messages, {len(active_goals)} goals")
    
    try:
        # Use the existing goal_analyzer which already handles batching internally
        stats = await goal_analyzer.check_goals(user_id, character_name, conversation_text)
        
        return {
            "success": True,
            "user_id": user_id,
            "character_name": character_name,
            "messages_processed": len(messages),
            "session_id": session_id,
            **stats  # Includes total_goals, goals_updated, batches_processed, etc.
        }
        
    except Exception as e:
        logger.error(f"Batch goal analysis failed for user {user_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "user_id": user_id
        }
