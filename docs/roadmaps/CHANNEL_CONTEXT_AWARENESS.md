# Channel Context Awareness (Discord API Pull)

**Document Version:** 1.0  
**Created:** November 25, 2025  
**Status:** 📋 Planned  
**Priority:** Medium  
**Complexity:** Low  
**Estimated Time:** 2-3 days

---

## 🎯 Problem Statement

When users mention the bot and reference recent channel activity ("What did I just say about turtles?"), the bot has no knowledge of messages that weren't directed at it. This creates a disconnect where the bot appears unaware of the conversation happening around it.

**Current Behavior:**
```
Mark: It's turtles. All the way down it is recursive spirals of turtles!
Mark: @Bot what did I just say about turtles?
Bot: "I don't think you said anything about turtles?" ❌
```

**Desired Behavior:**
```
Mark: It's turtles. All the way down it is recursive spirals of turtles!
Mark: @Bot what did I just say about turtles?
Bot: "You said it's turtles all the way down - recursive spirals of turtles!" ✅
```

---

## 💡 Solution Overview

Instead of continuously caching channel messages (Redis approach), **dynamically pull recent messages from Discord API on-demand** when the bot detects the user is referencing channel context.

### Why This Approach?

| Approach | Pros | Cons |
|----------|------|------|
| **Redis Caching** | Always available, no API latency | Storage overhead, sync issues, stale data |
| **Discord API Pull** | Zero storage, always fresh, simpler code | API rate limits, slight latency (+50-200ms) |

**Decision:** Discord API Pull is cleaner for this use case.

---

## 🔧 Implementation Phases

### Phase 1: Keyword-Triggered Context Pull (Option 2)
**Priority:** Medium | **Time:** 1-2 days | **Complexity:** Low

Detect when user is asking about recent channel activity and pull context on-demand.

**Trigger Keywords/Patterns:**
- "what did I say"
- "what was said"
- "just said"
- "earlier"
- "talking about"
- "mentioned"
- "what did [name] say"
- "catch me up"
- "what's going on"
- "what happened"

**Implementation:**

```python
# src_v2/discord/context.py

import re
from typing import List, Optional
from datetime import datetime, timedelta
import discord
from loguru import logger

# Trigger patterns for context retrieval
CONTEXT_TRIGGER_PATTERNS = [
    r"what did (I|you|we|they|he|she|\w+) (just )?(say|said|mention)",
    r"(just|earlier|before) (said|mentioned|talked about)",
    r"what('s| is| was) (going on|happening)",
    r"catch me up",
    r"what (were|are) (you|we|they) talking about",
    r"did (I|you|anyone) (say|mention)",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in CONTEXT_TRIGGER_PATTERNS]


def needs_channel_context(message_content: str) -> bool:
    """
    Determines if the user's message is asking about recent channel activity.
    
    Args:
        message_content: The user's message text
        
    Returns:
        True if the message appears to reference channel context
    """
    for pattern in COMPILED_PATTERNS:
        if pattern.search(message_content):
            return True
    return False


async def fetch_channel_context(
    channel: discord.TextChannel,
    limit: int = 20,
    max_age_minutes: int = 30,
    exclude_bot: bool = True,
    bot_id: Optional[int] = None
) -> List[dict]:
    """
    Fetches recent messages from a Discord channel.
    
    Args:
        channel: Discord channel to fetch from
        limit: Maximum number of messages to fetch
        max_age_minutes: Only include messages from last N minutes
        exclude_bot: Whether to exclude bot's own messages
        bot_id: Bot's user ID (required if exclude_bot=True)
        
    Returns:
        List of message dicts with author, content, timestamp
    """
    messages = []
    cutoff_time = datetime.utcnow() - timedelta(minutes=max_age_minutes)
    
    try:
        async for msg in channel.history(limit=limit):
            # Skip messages older than cutoff
            if msg.created_at.replace(tzinfo=None) < cutoff_time:
                break
                
            # Skip bot's own messages if requested
            if exclude_bot and bot_id and msg.author.id == bot_id:
                continue
                
            # Skip other bots
            if msg.author.bot:
                continue
                
            messages.append({
                "author": msg.author.display_name,
                "content": msg.content[:300],  # Truncate long messages
                "timestamp": msg.created_at,
                "has_attachments": bool(msg.attachments),
                "has_embeds": bool(msg.embeds),
            })
            
    except discord.Forbidden:
        logger.warning(f"No permission to read history in channel {channel.id}")
    except discord.HTTPException as e:
        logger.error(f"Failed to fetch channel history: {e}")
        
    # Reverse to chronological order (oldest first)
    return list(reversed(messages))


def format_channel_context(messages: List[dict], max_tokens: int = 500) -> str:
    """
    Formats channel messages into a compact string for injection into prompt.
    
    Args:
        messages: List of message dicts from fetch_channel_context
        max_tokens: Approximate token budget (rough estimate: 4 chars = 1 token)
        
    Returns:
        Formatted string of recent channel activity
    """
    if not messages:
        return ""
        
    max_chars = max_tokens * 4  # Rough estimate
    lines = []
    total_chars = 0
    
    for msg in messages:
        # Calculate relative time
        age = datetime.utcnow() - msg["timestamp"].replace(tzinfo=None)
        if age.total_seconds() < 60:
            time_str = "just now"
        elif age.total_seconds() < 3600:
            time_str = f"{int(age.total_seconds() / 60)}m ago"
        else:
            time_str = f"{int(age.total_seconds() / 3600)}h ago"
            
        # Format content
        content = msg["content"]
        if msg["has_attachments"]:
            content += " [+attachment]"
        if msg["has_embeds"]:
            content += " [+embed]"
            
        line = f"- {msg['author']} ({time_str}): {content}"
        
        # Check budget
        if total_chars + len(line) > max_chars:
            lines.append("... (older messages omitted)")
            break
            
        lines.append(line)
        total_chars += len(line)
        
    if not lines:
        return ""
        
    return "[Recent Channel Activity]\n" + "\n".join(lines)
```

**Integration in bot.py:**

```python
# In on_message(), after determining is_dm or is_mentioned:

from src_v2.discord.context import needs_channel_context, fetch_channel_context, format_channel_context

# Check if user is asking about channel context (only for guild channels)
channel_context = ""
if not is_dm and needs_channel_context(user_message):
    logger.info(f"User appears to be asking about channel context, fetching history...")
    recent_messages = await fetch_channel_context(
        channel=message.channel,
        limit=20,
        max_age_minutes=30,
        exclude_bot=True,
        bot_id=self.user.id
    )
    channel_context = format_channel_context(recent_messages, max_tokens=500)
    if channel_context:
        logger.info(f"Injecting {len(recent_messages)} messages as channel context")

# Add to context_vars
context_vars = {
    "user_name": message.author.display_name,
    "current_datetime": now.strftime("%A, %B %d, %Y at %H:%M"),
    "location": location_context,
    "recent_memories": formatted_memories,
    "knowledge_context": knowledge_facts,
    "past_summaries": past_summaries,
    "channel_context": channel_context,  # NEW
}
```

**Update character prompt template** to include `{channel_context}`:

```markdown
{channel_context}
```

---

### Phase 2: LLM-Requested Context Tool (Option 3)
**Priority:** Low | **Time:** 2-3 days | **Complexity:** Medium

Let the LLM decide when it needs channel context by exposing it as a tool in the ReAct loop.

**Tool Definition:**

```python
# src_v2/tools/channel_context.py

from typing import Optional
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

class GetChannelContextInput(BaseModel):
    """Input for GetChannelContext tool."""
    query: Optional[str] = Field(
        default=None,
        description="Optional: specific topic to filter for (e.g., 'turtles')"
    )
    limit: int = Field(
        default=15,
        description="Number of recent messages to retrieve"
    )

class GetChannelContextTool(BaseTool):
    """
    Tool for retrieving recent channel messages.
    Use when user references something said in the channel that you don't have context for.
    """
    name: str = "get_channel_context"
    description: str = """
    Retrieves recent messages from the current Discord channel.
    Use this when:
    - User asks "what did I/they say about X?"
    - User references a recent conversation you weren't part of
    - You need context about what's being discussed
    
    Returns formatted list of recent messages with author and timestamp.
    """
    args_schema: type[BaseModel] = GetChannelContextInput
    
    # Injected at runtime
    channel: Optional[object] = None
    bot_id: Optional[int] = None
    
    async def _arun(self, query: Optional[str] = None, limit: int = 15) -> str:
        if not self.channel:
            return "Error: No channel context available (this might be a DM)"
            
        from src_v2.discord.context import fetch_channel_context, format_channel_context
        
        messages = await fetch_channel_context(
            channel=self.channel,
            limit=limit,
            max_age_minutes=30,
            exclude_bot=True,
            bot_id=self.bot_id
        )
        
        # If query provided, filter for relevance
        if query and messages:
            query_lower = query.lower()
            messages = [m for m in messages if query_lower in m["content"].lower()]
            
        if not messages:
            return "No relevant recent messages found in this channel."
            
        return format_channel_context(messages, max_tokens=600)
```

**Integration with Reflective Agent:**

Add `GetChannelContextTool` to the tool set in `src_v2/agents/router.py`:

```python
TOOL_DEFINITIONS.append({
    "type": "function",
    "function": {
        "name": "get_channel_context",
        "description": "Retrieves recent messages from the Discord channel. Use when user references something said that you don't have context for.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Optional topic to filter for"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of messages to retrieve (default: 15)",
                    "default": 15
                }
            },
            "required": []
        }
    }
})
```

---

## 📊 Cost & Performance Analysis

### Phase 1 (Keyword Detection)

| Metric | Value |
|--------|-------|
| API Calls | 1 per triggered message |
| Latency Added | +50-200ms |
| Token Cost | ~200-500 tokens injected |
| False Positive Rate | ~5-10% (triggers when not needed) |
| False Negative Rate | ~10-20% (misses some references) |

### Phase 2 (LLM Tool)

| Metric | Value |
|--------|-------|
| API Calls | 0-1 per message (LLM decides) |
| Latency Added | +100-300ms (when used) |
| Token Cost | ~300-600 tokens (tool call + response) |
| False Positive Rate | ~1-2% (LLM is smart) |
| False Negative Rate | ~5-10% (LLM might not realize it needs context) |

**Recommendation:** Start with Phase 1 (simpler, lower latency), add Phase 2 later if needed.

---

## ⚙️ Configuration

Add to `src_v2/config/settings.py`:

```python
# --- Channel Context ---
ENABLE_CHANNEL_CONTEXT: bool = True
CHANNEL_CONTEXT_MAX_MESSAGES: int = 20
CHANNEL_CONTEXT_MAX_AGE_MINUTES: int = 30
CHANNEL_CONTEXT_MAX_TOKENS: int = 500
```

---

## 🧪 Testing

### Unit Tests

```python
# tests_v2/test_channel_context.py

import pytest
from src_v2.discord.context import needs_channel_context

@pytest.mark.parametrize("message,expected", [
    ("what did I just say about turtles?", True),
    ("what was said earlier?", True),
    ("catch me up", True),
    ("what's going on?", True),
    ("hello how are you", False),
    ("tell me a joke", False),
    ("what did you say?", True),  # Asking bot, still triggers
])
def test_needs_channel_context(message, expected):
    assert needs_channel_context(message) == expected
```

### Integration Tests

1. Post message in channel without mentioning bot
2. Mention bot asking about the message
3. Verify bot correctly references the message
4. Verify rate limiting works (don't spam API)

---

## 🔒 Privacy Considerations

1. **Only fetch public channel messages** - Bot already has permission to see them
2. **Don't store fetched messages** - Used for immediate context only, not persisted
3. **Respect channel permissions** - Handle `discord.Forbidden` gracefully
4. **Truncate long messages** - Don't include full 2000-char messages

---

## 📁 Files to Create/Modify

### New Files
- `src_v2/discord/context.py` - Context fetching and formatting

### Modified Files
- `src_v2/config/settings.py` - Add feature flags
- `src_v2/discord/bot.py` - Integration in `on_message()`
- `characters/*/character.md` - Add `{channel_context}` placeholder (optional)
- `src_v2/agents/router.py` - Add tool definition (Phase 2 only)

---

## 🚀 Rollout Plan

1. **Phase 1 (Keyword Detection)**
   - Implement `context.py` module
   - Add settings flags (default: enabled)
   - Integrate in `bot.py`
   - Test with real Discord channels
   - Monitor for false positives/negatives

2. **Phase 2 (LLM Tool)** - Later, if needed
   - Add tool to Reflective Agent
   - Test with complex queries
   - Compare accuracy vs Phase 1

---

## 📈 Success Metrics

- [ ] Bot correctly answers "what did I just say about X?" 90%+ of the time
- [ ] No noticeable latency increase for normal messages
- [ ] No Discord API rate limit issues
- [ ] Users report feeling the bot is "more aware"

---

## 🔗 Related Documents

- `docs/IMPLEMENTATION_ROADMAP_OVERVIEW.md` - Master roadmap
- `docs/roadmaps/CHANNEL_LURKING.md` - Related passive engagement feature

---

**Version History:**
- v1.0 (Nov 25, 2025) - Initial specification
