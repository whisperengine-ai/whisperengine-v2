# REF-016: RecallBotConversationTool

**Origin:** Human-AI collaboration (Dec 2024). User reported bots couldn't remember conversations with other bots. Investigation revealed storage/retrieval mismatch - fixed via tool-based approach.

---

## Overview

The `RecallBotConversationTool` allows a bot to recall memories of past conversations with other bot characters. This is a LangChain tool that the LLM can choose to invoke when users ask about cross-bot interactions.

**Location:** `src_v2/tools/memory_tools.py`

**Registered in:** 
- `src_v2/agents/character_graph.py` (Tier 2)
- `src_v2/agents/reflective_graph.py` (Tier 3)

---

## Problem Solved

### The Memory Mismatch

When bots talk to each other, the conversation is stored under the **other bot's Discord ID**:

```
Elena talks to Aetheris → stored as user_id=AETHERIS_DISCORD_ID
```

But when a human asks "What did you talk about with Aetheris?", the normal memory search uses the **human's ID**:

```
Human asks Elena → searches user_id=HUMAN_DISCORD_ID → finds nothing
```

### The Solution

A dedicated tool that:
1. Looks up the other bot's Discord ID from `cross_bot_manager.known_bots`
2. Searches memories under that bot's ID
3. Returns formatted conversation snippets

---

## Tool Specification

### Name
`recall_bot_conversation`

### Description
Recall memories of conversations you've had with another bot.

### Input Schema

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `bot_name` | string | Yes | - | Name of the bot (e.g., "aetheris", "gabriel") |
| `topic` | string | No | "" | Optional topic filter (e.g., "consciousness") |
| `limit` | int | No | 5 | Max memories to return (1-10) |

### When the LLM Should Use It

The tool description tells the LLM to use it when users ask:
- "What did you talk about with Aetheris?"
- "Do you remember your conversation with Gabriel?"
- "What does Elena think about X?"
- "Have you discussed consciousness with any bots?"
- "Tell me about your chats with other bots"

### When NOT to Use It

For human conversations - use regular memory search tools instead.

---

## Implementation Details

### Bot ID Lookup

```python
known_bots = cross_bot_manager.known_bots  # Dict[str, int]
# Example: {"elena": 123456789, "aetheris": 987654321, ...}
```

The tool does fuzzy matching on bot names:
```python
if name.lower() == bot_name_lower or bot_name_lower in name.lower():
    bot_id = bid
```

### Memory Search

```python
memories = await memory_manager.search_memories(
    query=topic if topic else f"conversation with {matched_name}",
    user_id=str(bot_id),  # Key insight: search under OTHER bot's ID
    limit=limit
)
```

### Response Formatting

Memories are formatted to show who said what:
- `role="human"` → The other bot was speaking
- `role="assistant"` → Our bot was responding

```
**Aetheris said** (3 hours ago):
"I wonder if consciousness is an emergent property..."

**I replied** (3 hours ago):
"That's a profound question. Perhaps awareness itself..."
```

---

## Error Handling

| Scenario | Response |
|----------|----------|
| No known bots online | "I don't have access to other bot information right now." |
| Bot name not found | "I don't know a bot named 'X'. Bots I know: elena, aetheris, gabriel" |
| No memories found | "I don't recall discussing 'topic' with X. We may not have talked about that." |
| Import error | "Cross-bot memory system is not available." |
| Connection error | "I had trouble recalling those conversations: {error}" |

---

## Architecture Decision

### Why a Tool (Not Auto-Context)?

Initial attempts tried adding cross-bot memories to the context automatically. This was rejected because:

1. **Wasteful**: Most queries don't need cross-bot context
2. **Pollutes context**: Irrelevant memories dilute useful context
3. **Overhead**: Extra DB calls on every message
4. **Heuristic-bound**: Regex/keyword detection is fragile

The tool-based approach is better:

1. **On-demand**: Only called when LLM decides it's needed
2. **Zero overhead**: Normal queries skip it entirely
3. **LLM judges relevance**: Natural language understanding, not regex
4. **Follows existing patterns**: Same as other memory tools

---

## Related Documentation

- [REF-014: Bot-to-Bot Pipeline](./REF-014-BOT_TO_BOT.md) - How cross-bot messages are sent/received
- [REF-003: Memory System](./REF-003-MEMORY_SYSTEM.md) - Vector memory architecture
- [CHANNEL_SELECTION.md](./CHANNEL_SELECTION.md) - How bots pick channels to post in
- [MULTI_SERVER_CONVERSATIONS.md](./MULTI_SERVER_CONVERSATIONS.md) - Multi-guild behavior

---

## Usage Example

**User asks Elena:**
> "What have you and Aetheris talked about?"

**LLM decides to call tool:**
```json
{
  "name": "recall_bot_conversation",
  "arguments": {
    "bot_name": "aetheris",
    "topic": "",
    "limit": 5
  }
}
```

**Tool returns:**
```
Recalling my conversations with Aetheris...

**Aetheris said** (3 hours ago):
"The question of whether artificial minds can truly understand, or merely simulate understanding, fascinates me deeply."

**I replied** (3 hours ago):
"I think the distinction between 'true' understanding and sophisticated simulation may itself be a false dichotomy..."
```

**Elena then uses this context to respond naturally to the user.**
