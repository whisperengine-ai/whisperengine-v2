"""
Shared utility for retrieving bot autonomous actions from Qdrant.

Used by both diary.py and dreams.py to fetch the bot's own posts/replies
for self-reflection in diary entries and dream generation.

Phase E35: Bot's autonomous activity as first-class diary/dream material.
"""
from typing import List, Dict, Any
from datetime import datetime, timezone, timedelta
from loguru import logger
from qdrant_client.models import Filter, FieldCondition, MatchValue

from src_v2.core.database import db_manager

# Constants for action retrieval limits
DIARY_AUTONOMOUS_ACTION_LIMIT = 20
DREAM_AUTONOMOUS_ACTION_LIMIT = 10


async def get_autonomous_actions(
    collection_name: str,
    hours: int,
    limit: int = DIARY_AUTONOMOUS_ACTION_LIMIT
) -> List[Dict[str, Any]]:
    """
    Get the bot's autonomous posts and replies from the last N hours.
    
    These are messages stored with source_type=INFERENCE where the bot
    is both the author and the user_id (autonomous actions save with
    user_id = bot's discord user id).
    
    Args:
        collection_name: The Qdrant collection to query (bot-specific)
        hours: How many hours back to look
        limit: Maximum number of actions to return (default: 20 for diary, use 10 for dreams)
        
    Returns:
        List of autonomous action records with content, channel info, and context
    """
    try:
        if not db_manager.qdrant_client:
            return []
        
        threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
        threshold_iso = threshold.isoformat()
        
        # Query for messages that are:
        # 1. Type = "conversation" (stored messages)
        # 2. source_type = "inference" (autonomous actions)
        # 3. role = "ai" (bot's own messages)
        results = await db_manager.qdrant_client.scroll(
            collection_name=collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="type", match=MatchValue(value="conversation")),
                    FieldCondition(key="source_type", match=MatchValue(value="inference")),
                    FieldCondition(key="role", match=MatchValue(value="ai"))
                ]
            ),
            limit=50,  # Fetch extra for date filtering
            with_payload=True,
            with_vectors=False
        )
        
        # Filter by timestamp and extract action info
        # Note: ISO timestamp string comparison works because ISO 8601 is lexicographically sortable
        actions = []
        for point in results[0]:
            payload = point.payload
            if not payload:
                continue
                
            ts = payload.get("timestamp", "")
            if ts < threshold_iso:
                continue
            
            # Determine action type based on context
            # If there's a context field (what triggered the reply), it's a reply; otherwise a post
            context = payload.get("context", "")
            is_reply = bool(context)
            
            actions.append({
                "action_type": "reply" if is_reply else "post",
                "content": payload.get("content", ""),
                "channel_id": payload.get("channel_id", ""),
                "channel_name": payload.get("channel_name", "unknown"),
                "context": context,  # What the bot was replying to
                "timestamp": ts,
                "message_id": payload.get("message_id", "")
            })
        
        # Sort by timestamp descending (most recent first)
        actions.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        logger.debug(f"Found {len(actions)} autonomous actions in last {hours} hours (limit: {limit})")
        return actions[:limit]
        
    except Exception as e:
        logger.debug(f"Failed to get autonomous actions: {e}")
        return []
