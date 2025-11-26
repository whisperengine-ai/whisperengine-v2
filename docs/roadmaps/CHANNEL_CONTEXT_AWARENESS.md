# Channel Context Awareness

**Document Version:** 1.1  
**Created:** November 25, 2025  
**Last Updated:** November 25, 2025  
**Status:** 📋 Planned  
**Priority:** Medium  
**Complexity:** Low-Medium  
**Estimated Time:** 3-5 days (all phases)

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

A **hybrid approach** combining multiple strategies for maximum flexibility:

| Phase | Approach | Search Type | Storage | Use Case |
|-------|----------|-------------|---------|----------|
| **1a** | Discord API pull + keyword filter | Exact match | None | Fallback, cold start |
| **1b** | Redis rolling buffer + semantic search | Similarity | ~50KB/channel | Primary, fast |
| **2** | LLM tool (model decides) | LLM chooses | Uses 1a/1b | Complex queries |

### Why Hybrid?

| Approach | Pros | Cons |
|----------|------|------|
| **Discord API Pull** | Zero storage, always fresh, simple | Keyword-only search, 50-200ms latency |
| **Redis + Local Embeddings** | Semantic search, 10-20ms, free | Storage overhead, stale on edit/delete |
| **Hybrid (both)** | Best of both worlds | Slightly more code |

**Decision:** Use Redis as primary (fast + semantic), Discord API as fallback (fresh + handles cold start).

### Note on Discord API Search

Discord's message search (Ctrl+F in client) is **not available to bots**. The Bot API only provides:
- `channel.history(limit=N)` - Fetch last N messages chronologically ✅
- `channel.fetch_message(id)` - Fetch specific message by ID ✅
- Message Search (keyword, filters) - **Not available** ❌

This is why we implement our own search layer via Redis.

---

## 🔧 Implementation Phases

### Phase 1a: Keyword-Triggered Context Pull (Discord API)
**Priority:** High | **Time:** 1 day | **Complexity:** Low

Detect when user is asking about recent channel activity and pull context on-demand from Discord API. This serves as the **fallback** when Redis cache is empty (cold start, bot restart).

**⚠️ Critical Design Challenge: Disambiguation**

The trigger patterns can overlap with memory-related queries:
- "what did I say last week?" - Could be channel context OR personal memory
- "what was said about security?" - Could be channel history OR knowledge graph  
- "what were we talking about?" - Could be immediate channel OR past sessions

**Smart Disambiguation Strategy:**

Instead of simple keyword matching, detect **temporal and referential clues**:

```
User: "what did I say about turtles?"
  ↓
1. Time Clue Detection:
   - Recent marker: "just", "earlier", "moment ago" → Channel (15-30 min window)
   - Past marker: "yesterday", "last week", "last month" → Vector memory (older)
   - No marker → Ambiguous, default to channel (cheaper, faster fallback)
  ↓
2. Referent Detection:
   - "I", "I said" → Likely personal memory
   - "we", "people", "you guys" → Likely channel context
  ↓
3. Fallback Strategy:
   - Try primary method first (based on clues)
   - If empty, try secondary method
   - If both empty, respond honestly: "I don't see recent messages about that"
```

**Pseudocode (Phase 1a):**

```
function needs_channel_context(message) -> bool:
  // Check for explicit time markers
  has_recent = matches(message, /just|earlier|moment ago|a minute/i)
  has_past = matches(message, /yesterday|last week|last month/i)
  
  if has_past:
    return false  // Likely vector memory (historical)
  
  if has_recent:
    return true   // Likely channel (recent)
  
  // Check referent hints
  has_we = matches(message, /\bwe\b|\bpeople\b|\byou guys\b/i)
  has_i_action = matches(message, /\bI said|\bI mentioned|\bI told/i)
  
  if has_we:
    return true   // Likely channel context
  if has_i_action:
    return false  // Likely personal memory
  
  // Ambiguous: default to channel (Redis is cheaper/faster)
  return true

function fetch_channel_context(channel, limit=20, max_age_min=30):
  messages = []
  cutoff = now() - duration(max_age_min)
  
  for msg in channel.history(limit=limit):
    if msg.timestamp < cutoff: break
    if msg.author.is_bot: continue
    
    messages.append({
      author: msg.author.name,
      content: msg.content[:300],
      time_ago: human_readable_duration(now() - msg.timestamp)
    })
  
  return reverse(messages)  // Chronological order

function format_channel_context(messages, max_tokens=500):
  if empty(messages): return ""
  
  lines = []
  for msg in messages:
    line = f"- {msg.author} ({msg.time_ago}): {msg.content}"
    lines.append(line)
  
  return "[Recent Channel Activity]\n" + join(lines, "\n")
```

**Integration in bot.py (Pseudocode):**

```
// In on_message(), when bot is mentioned:

channel_context = ""
use_vector_memory = false

if not is_dm:
  if needs_channel_context(user_message):  // Smart disambiguation
    // Try Redis semantic search first (fast, cheap)
    relevant = await channel_cache.search_semantic(channel_id, user_message)
    
    if relevant:
      channel_context = format_channel_context(relevant)
      log("Found context via Redis semantic search")
    else:
      // Fallback to Discord API (fresh data)
      recent = await fetch_channel_context(channel, max_age_min=30)
      channel_context = format_channel_context(recent)
      log("Fell back to Discord API")
  else:
    // Not channel-related, use vector memory instead
    use_vector_memory = true

// Add to context_vars
context_vars = {
  user_name: message.author.display_name,
  location: location_context,
  recent_memories: formatted_memories,
  knowledge_context: knowledge_facts,
  channel_context: channel_context,  // Only if channel query
  // ...existing context...
}
```

**Update character prompt template** to include `{channel_context}`:

```markdown
{channel_context}
```

---

### Phase 1b: Redis Rolling Buffer with Semantic Search
**Priority:** High | **Time:** 2 days | **Complexity:** Medium

Cache non-mentioned messages in Redis with embeddings for semantic search. Uses **local embedding model** (`all-MiniLM-L6-v2`) - zero API cost.

**Why Add This?**

| Feature | Phase 1a (Discord API) | Phase 1b (Redis Cache) |
|---------|------------------------|------------------------|
| Search type | Keyword/exact only | Semantic similarity ✨ |
| Latency | 50-200ms | 10-20ms |
| Storage | None | ~50KB/channel |
| Works if bot was offline | ✅ Yes | ❌ Only cached messages |
| Message edits/deletes | ✅ Reflects current | ❌ Stale until TTL |
| Finds "turtles" when asked about "reptiles" | ❌ No | ✅ Yes |

**Key Benefit:** User asks "what was Mark talking about earlier?" and we can find messages about "turtles" even if "turtles" isn't in the query.

**Architecture:**

```
Message arrives (not mentioned to bot)
    ↓
Generate embedding locally (~5ms, free)
    ↓
Store in Redis with 30min TTL
    ↓
When bot IS mentioned + needs_channel_context():
    ↓
Embed query locally → Redis KNN search → Return top-K matches
    ↓
If Redis empty → Fallback to Phase 1a (Discord API)
```

**Implementation (Pseudocode - Phase 1b):**

```
class ChannelContextCache:
  // Redis-backed rolling buffer with semantic search
  // Uses local embeddings (384-dim, ~5ms, $0 cost)
  
  async initialize():
    // Create Redis search index with vector field
    // Schema: content (text), author (tag), timestamp (numeric), embedding (vector-384d)
    // Index type: JSON with HNSW for efficient KNN search
  
  async add_message(channel_id, message_id, author, content, timestamp):
    if content.is_empty():
      return
    
    // Embed locally (~5ms, free)
    embedding = await embeddings.embed_text(content[:500])
    
    // Store in Redis JSON with TTL
    doc = {
      channel_id: channel_id,
      author: author,
      content: content[:500],
      timestamp: timestamp,
      embedding: embedding  // 384-dim vector
    }
    redis.json.set(f"channel_msg:{channel_id}:{message_id}", doc)
    redis.expire(key, 30_minutes)
    
    // Keep only 50 most recent per channel
    await prune_channel(channel_id)
  
  async search_semantic(channel_id, query, limit=10) -> List[dict]:
    // Embed query locally
    query_vec = await embeddings.embed_text(query)
    
    // Redis KNN search (filtered by channel_id)
    results = redis.ft(INDEX).search(
      query: "@channel_id:{channel_id}=>[KNN 10 @embedding $vec]",
      vector: query_vec
    )
    
    // Return top-K matches with similarity scores
    return format_results(results)
  
  async get_recent(channel_id, limit=20):
    // Get most recent messages without semantic filtering
    messages = redis.keys(f"channel_msg:{channel_id}:*")
    sort by timestamp descending
    return messages[:limit]
```

**Updated format function with similarity scores (Pseudocode):**

```
function format_channel_context(messages, max_tokens=500) -> string:
  if empty(messages):
    return ""
  
  max_chars = max_tokens * 4  // Rough token->char estimate
  lines = []
  
  for msg in messages:
    age = now() - msg.timestamp
    time_str = human_readable_age(age)  // "2m ago", "15m ago", "1h ago"
    
    // Optional: include similarity score if from semantic search
    score_str = ""
    if msg.has_score:
      similarity = 1 - msg.score  // Convert distance to similarity
      score_str = score_label(similarity)  // "[highly relevant]", "[relevant]", ""
    
    line = f"- {msg.author} ({time_str}){score_str}: {msg.content[:100]}"
    
    if total_chars(lines) + len(line) > max_chars:
      lines.append("... (more messages omitted)")
      break
    
    lines.append(line)
  
  return "[Recent Channel Activity]\n" + join(lines, "\n")
```

**Integration in bot.py - Passive Caching (Pseudocode):**

```
// In on_message(), EARLY - for non-mentioned messages in guilds:

if not message.author.is_bot and not is_dm:
  if not is_mentioned and not is_command:
    if settings.ENABLE_CHANNEL_CONTEXT:
      // Fire-and-forget: embed and cache (~5ms, local)
      async_task: channel_cache.add_message(
        channel_id: message.channel.id,
        message_id: message.id,
        author: message.author.display_name,
        content: message.content,
        timestamp: message.created_at
      )
    // Don't process non-mentioned messages further
    return
```

**Cost Analysis (Phase 1b):**

| Operation | Cost | Latency |
|-----------|------|---------|
| Embed message (local `all-MiniLM-L6-v2`) | $0 | ~5ms |
| Store to Redis | $0 | ~1ms |
| Embed query (local) | $0 | ~5ms |
| Redis KNN search | $0 | ~5-10ms |
| **Total per search** | **$0** | **~15-20ms** |

| Storage | Size |
|---------|------|
| Per message | ~1KB (text + 384-dim vector) |
| Per channel (50 msgs) | ~50KB |
| 100 active channels | ~5MB |

---

### Phase 2: LLM-Requested Context Tool
**Priority:** Low | **Time:** 1-2 days | **Complexity:** Medium

Let the LLM decide when it needs channel context by exposing it as a tool in the ReAct loop. Uses Phase 1a/1b under the hood.

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

### Phase 1a (Discord API - Fallback)

| Metric | Value |
|--------|-------|
| API Calls | 1 per triggered message |
| Latency Added | +50-200ms |
| Token Cost | ~200-500 tokens injected |
| Search Type | Keyword/exact match only |
| Best For | Cold start, bot restart, always-fresh data |

### Phase 1b (Redis + Local Embeddings - Primary)

| Metric | Value |
|--------|-------|
| Embedding Cost | $0 (local model) |
| Storage Cost | ~50KB per channel |
| Latency Added | +15-20ms |
| Token Cost | ~200-500 tokens injected |
| Search Type | Semantic similarity |
| Best For | Fast response, finding related content |

### Phase 2 (LLM Tool)

| Metric | Value |
|--------|-------|
| API Calls | 0-1 per message (LLM decides) |
| Latency Added | +100-300ms (when used) |
| Token Cost | ~300-600 tokens (tool call + response) |
| False Positive Rate | ~1-2% (LLM is smart) |
| False Negative Rate | ~5-10% (LLM might not realize it needs context) |

### Comparison Summary

| Feature | Phase 1a | Phase 1b | Phase 2 |
|---------|----------|----------|---------|
| Search Type | Keyword | Semantic | LLM decides |
| Latency | 50-200ms | 15-20ms | 100-300ms |
| Storage | None | ~50KB/ch | Uses 1a/1b |
| Works offline | ✅ | ❌ | ✅ |
| Finds "turtles" for "reptiles" | ❌ | ✅ | ✅ |
| Handles edits/deletes | ✅ | ❌ | ✅ |

**Recommendation:** 
1. Implement Phase 1b as **primary** (fast + semantic)
2. Use Phase 1a as **fallback** (fresh + cold start)
3. Add Phase 2 later if needed for complex queries

---

## ⚙️ Configuration

Add to `src_v2/config/settings.py`:

```python
# --- Channel Context ---
ENABLE_CHANNEL_CONTEXT: bool = True
CHANNEL_CONTEXT_MAX_MESSAGES: int = 50       # Max messages per channel in Redis
CHANNEL_CONTEXT_MAX_AGE_MINUTES: int = 30    # TTL for cached messages
CHANNEL_CONTEXT_MAX_TOKENS: int = 500        # Token budget for context injection
CHANNEL_CONTEXT_SEMANTIC_THRESHOLD: float = 0.6  # Min similarity for semantic results
```

**Redis Stack Requirement:**

Phase 1b requires **Redis Stack** (includes RediSearch + RedisJSON) instead of plain Redis. Update `docker-compose.yml`:

```yaml
redis:
  image: redis/redis-stack:latest  # Was: redis:7-alpine
  ports:
    - "6379:6379"
    - "8001:8001"  # RedisInsight UI (optional)
  volumes:
    - redis_data:/data
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
- `src_v2/discord/context.py` - Keyword detection, Discord API fetch, formatting
- `src_v2/discord/channel_cache.py` - Redis rolling buffer with semantic search

### Modified Files
- `src_v2/config/settings.py` - Add feature flags
- `src_v2/discord/bot.py` - Passive caching + context retrieval in `on_message()`
- `docker-compose.yml` - Upgrade to `redis/redis-stack` image
- `characters/*/character.md` - Add `{channel_context}` placeholder (optional)
- `src_v2/agents/router.py` - Add tool definition (Phase 2 only)

---

## 🚀 Rollout Plan

1. **Phase 1a (Discord API Fallback)** - Day 1
   - Implement `src_v2/discord/context.py` module
   - Add `needs_channel_context()` keyword detection
   - Add `fetch_channel_context()` Discord API wrapper
   - Add settings flags (default: enabled)
   - Test with real Discord channels

2. **Phase 1b (Redis Semantic Search)** - Day 2-3
   - Upgrade to `redis/redis-stack` in Docker Compose
   - Implement `src_v2/discord/channel_cache.py`
   - Add passive caching in `on_message()` for non-mentioned messages
   - Integrate semantic search when bot is mentioned
   - Use Phase 1a as fallback when cache is empty
   - Monitor embedding latency and Redis memory

3. **Phase 2 (LLM Tool)** - Later, if needed
   - Add `get_channel_context` tool to Reflective Agent
   - Test with complex queries
   - Compare accuracy vs keyword detection

---

## 📈 Success Metrics

- [ ] Bot correctly answers "what did I just say about X?" 90%+ of the time
- [ ] Semantic search finds related messages (e.g., "reptiles" finds "turtles")
- [ ] No noticeable latency increase for normal messages (<20ms overhead)
- [ ] No Discord API rate limit issues
- [ ] Redis memory usage stays under 10MB for typical usage
- [ ] Users report feeling the bot is "more aware"

---

## 🔗 Related Documents

- `docs/IMPLEMENTATION_ROADMAP_OVERVIEW.md` - Master roadmap
- `docs/roadmaps/CHANNEL_LURKING.md` - Related passive engagement feature

---

## 📝 Dependencies

- **Redis Stack** - Required for Phase 1b (vector search). Plain Redis won't work.
- **EmbeddingService** - Already exists (`src_v2/memory/embeddings.py`), uses `all-MiniLM-L6-v2`
- **numpy** - Already in requirements, needed for vector byte conversion

---

**Version History:**
- v1.0 (Nov 25, 2025) - Initial specification with Discord API approach
- v1.1 (Nov 25, 2025) - Added Phase 1b (Redis rolling buffer with semantic search using local embeddings). Restructured as hybrid approach with 1a as fallback.
