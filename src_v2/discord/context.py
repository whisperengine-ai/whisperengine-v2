"""
Channel Context Helpers - Detection and formatting for channel context awareness.

Provides:
- needs_channel_context(): Detect if user is asking about recent channel activity
- fetch_channel_context(): Discord API fallback for fresh data
- format_channel_context(): Format messages for LLM consumption
"""

import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from loguru import logger
import discord

from src_v2.config.settings import settings


# Patterns that indicate user is asking about RECENT channel activity
# These should trigger channel context lookup
RECENT_CHANNEL_PATTERNS = [
    # Explicit time markers for recent
    r"\bjust\b.*\bsaid\b",
    r"\bearlier\b",
    r"\bmoment ago\b",
    r"\ba minute ago\b",
    r"\bjust now\b",
    r"\brecently\b.*\bsaid\b",
    
    # Questions about channel activity
    r"\bwhat did\b.*\bsay\b",
    r"\bwhat was\b.*\bsaid\b",
    r"\bwhat were\b.*\btalking\b",
    r"\bcatch me up\b",
    r"\bwhat's going on\b",
    r"\bwhat happened\b",
    r"\bwhat are (we|they|you) (talking|discussing)\b",
    r"\bwhat's the (topic|conversation|discussion)\b",
    r"\bwhat (are|is) (everyone|people) (saying|talking)\b",
    
    # References to other people's messages
    r"\bwhat did (he|she|they|someone|anybody)\b",
    r"\bdid (you|anyone) (see|hear|notice)\b",
]

# Patterns that indicate user is asking about HISTORICAL/PERSONAL memory
# These should NOT trigger channel context (use vector memory instead)
HISTORICAL_PATTERNS = [
    r"\byesterday\b",
    r"\blast week\b",
    r"\blast month\b",
    r"\blast year\b",
    r"\blong ago\b",
    r"\bremember when\b",
    r"\bwhen we first\b",
    r"\bback when\b",
    r"\btold you (before|previously|earlier)\b",
]


def needs_channel_context(message: str) -> bool:
    """
    Detect if the user's message is asking about recent channel activity.
    
    Uses pattern matching to distinguish between:
    - Recent channel activity ("what did I just say?") → True
    - Historical memory ("what did I tell you last week?") → False
    - Ambiguous → True (channel is cheaper/faster fallback)
    
    Args:
        message: User's message text
        
    Returns:
        True if we should look up channel context
    """
    message_lower = message.lower()
    
    # First check for historical patterns (these override recent patterns)
    for pattern in HISTORICAL_PATTERNS:
        if re.search(pattern, message_lower):
            logger.debug(f"Historical pattern detected: {pattern}")
            return False
    
    # Check for recent channel patterns
    for pattern in RECENT_CHANNEL_PATTERNS:
        if re.search(pattern, message_lower):
            logger.debug(f"Channel context pattern detected: {pattern}")
            return True
    
    # No explicit pattern - don't auto-inject (saves tokens)
    return False


async def fetch_channel_context(
    channel: discord.abc.Messageable,
    limit: int = 20,
    max_age_minutes: int = 30,
    exclude_bot: bool = True,
    bot_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Fetch recent messages from Discord API (fallback when Redis cache is empty).
    
    Args:
        channel: Discord channel to fetch from
        limit: Max messages to fetch
        max_age_minutes: Only include messages newer than this
        exclude_bot: Whether to exclude bot's own messages
        bot_id: Bot's user ID (required if exclude_bot is True)
        
    Returns:
        List of message dicts with author, content, timestamp
    """
    messages = []
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
    
    try:
        async for msg in channel.history(limit=limit):
            # Skip if too old
            if msg.created_at < cutoff:
                break
                
            # Skip bot messages if requested
            if exclude_bot and bot_id and msg.author.id == bot_id:
                continue
                
            # Skip empty messages
            if not msg.content or not msg.content.strip():
                continue
            
            messages.append({
                "message_id": str(msg.id),
                "author": msg.author.display_name,
                "author_id": str(msg.author.id),
                "content": msg.content[:300],  # Truncate
                "timestamp": msg.created_at.timestamp()
            })
        
        # Reverse to get chronological order (oldest first)
        messages.reverse()
        
    except Exception as e:
        logger.error(f"Failed to fetch channel context: {e}")
    
    return messages


def _smart_truncate(text: str, max_length: int = 200) -> str:
    """
    Smart truncation that keeps beginning and end of long messages.
    
    For messages longer than max_length, keeps first ~40% and last ~40%
    with " ... " in the middle.
    """
    if len(text) <= max_length:
        return text
    
    # Keep beginning and end
    keep_each = (max_length - 5) // 2  # -5 for " ... "
    return text[:keep_each] + " ... " + text[-keep_each:]


def format_channel_context(
    messages: List[Dict[str, Any]],
    max_tokens: int = 500,
    include_similarity: bool = False
) -> str:
    """
    Format channel messages for LLM context injection.
    
    Args:
        messages: List of message dicts from cache or API
        max_tokens: Approximate token budget (chars * 0.25)
        include_similarity: Whether to show relevance indicators
        
    Returns:
        Formatted string for system prompt injection
    """
    if not messages:
        return ""
    
    max_chars = max_tokens * 4  # Rough token estimate
    lines = []
    total_chars = 0
    
    for msg in messages:
        # Calculate time ago
        ts = msg.get("timestamp", 0)
        if ts:
            age_seconds = datetime.now(timezone.utc).timestamp() - ts
            time_str = _human_time_ago(age_seconds)
        else:
            time_str = "unknown"
        
        # Optional relevance indicator
        relevance_str = ""
        if include_similarity and "similarity" in msg:
            sim = msg["similarity"]
            if sim >= 0.7:
                relevance_str = " [highly relevant]"
            elif sim >= 0.5:
                relevance_str = " [relevant]"
        
        # Format line with smart truncation for long messages
        content = _smart_truncate(msg.get("content", ""), max_length=200)
        line = f"- {msg['author']} ({time_str}){relevance_str}: {content}"
        
        # Check token budget
        if total_chars + len(line) > max_chars:
            lines.append("... (older messages omitted)")
            break
        
        lines.append(line)
        total_chars += len(line) + 1  # +1 for newline
    
    if not lines:
        return ""
    
    return "[Recent Channel Activity]\n" + "\n".join(lines)


def _human_time_ago(seconds: float) -> str:
    """Convert seconds to human-readable time ago string."""
    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        mins = int(seconds / 60)
        return f"{mins}m ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours}h ago"
    else:
        days = int(seconds / 86400)
        return f"{days}d ago"


# Import timedelta for fetch_channel_context
from datetime import timedelta
