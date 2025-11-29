# Discord Search Tools

**Document Version:** 1.1  
**Created:** November 28, 2025  
**Last Updated:** November 29, 2025  
**Status:** 🚧 In Progress (Phase 2 complete)  
**Priority:** Medium  
**Complexity:** Low-Medium  
**Estimated Time:** 2-3 days

---

## 🎯 Problem Statement

The LLM currently has no way to **actively search Discord** for context. The existing approach is wasteful and limited:

**Current state (to be removed):**
- `bot.py` pre-fetches last 10 messages via `get_channel_context()` on **every single request**
- This is injected into the system prompt as `[RECENT CHANNEL ACTIVITY]`
- The previous `GetRecentActivityTool` just returned this same string—it did NOT query Discord
- **Wasteful:** Fetches 10 messages even for simple requests like "hello" or "tell me a joke"
- **Limited:** Only 10 messages, no filtering, includes bot messages that may not be relevant
- **No search:** LLM can't ask for specific topics or users

When users ask questions like:
- "What did I say about turtles earlier?"
- "What has Sarah been talking about today?"
- "Find where we discussed the project deadline"

...the bot either fails to find the information or relies on vector memory (which may not have indexed recent channel messages).

**Action:** Remove pre-fetch entirely. Replace with on-demand Discord search tools that the LLM calls only when needed.

---

## 💡 Solution Overview

Add a suite of **Discord Search Tools** that allow the LLM to query Discord directly via the Discord API. These tools enable on-demand, targeted searches rather than pre-fetching everything.

### Tool Suite

| Tool | Purpose | API Method |
|------|---------|------------|
| `search_channel_messages` | Search recent channel messages by keyword/topic | `channel.history()` + filter |
| `search_user_messages` | Find messages from a specific user | `channel.history()` + author filter |
| `get_message_context` | Get messages around a specific message ID | `channel.history(around=)` |
| `search_thread_messages` | Search within a thread | `thread.history()` + filter |
| `get_channel_summary` | Get a summary of recent channel activity | `channel.history()` + LLM summarization |

---

## 🔧 Tool Specifications

### 1. SearchChannelMessagesTool

**Purpose:** Search recent channel messages for a keyword or topic.

**When to use:**
- "What did I say about X?"
- "What happened earlier about Y?"
- "Catch me up on the conversation"

**Pseudocode:**
```
tool search_channel_messages(query: str, limit: int = 30) -> str:
  messages = []
  for msg in channel.history(limit=limit):
    if keyword_match(msg.content, query):
      messages.append(format_message(msg))
  
  if not messages:
    return f"No messages found matching '{query}'"
  
  return join(messages, "\n")

function keyword_match(content, query) -> bool:
  // Simple case-insensitive substring match
  // Could be enhanced with fuzzy matching or embeddings later
  return query.lower() in content.lower()

function format_message(msg) -> str:
  timestamp = relative_time(msg.created_at)  // "5 minutes ago"
  author = msg.author.display_name
  is_bot = " (Bot)" if msg.author.bot else ""
  return f"[{timestamp}] {author}{is_bot}: {msg.content[:300]}"
```

**Args Schema:**
```python
class SearchChannelMessagesInput(BaseModel):
    query: str = Field(description="Keyword or topic to search for in messages")
    limit: int = Field(default=30, description="Max messages to search (default 30, max 100)")
```

---

### 2. SearchUserMessagesTool

**Purpose:** Find messages from a specific user in the channel.

**When to use:**
- "What has Mark said today?"
- "Find Sarah's last message"
- "What did the user say about the deadline?"

**Pseudocode:**
```
tool search_user_messages(user_name: str, query: str = None, limit: int = 20) -> str:
  target_user = find_user_by_name(channel.guild, user_name)
  if not target_user:
    return f"Could not find user '{user_name}'"
  
  messages = []
  for msg in channel.history(limit=100):  // Search more to find user's messages
    if msg.author.id == target_user.id:
      if query is None or keyword_match(msg.content, query):
        messages.append(format_message(msg))
        if len(messages) >= limit:
          break
  
  if not messages:
    return f"No messages found from {user_name}" + (f" about '{query}'" if query else "")
  
  return join(messages, "\n")

function find_user_by_name(guild, name) -> User | None:
  // Fuzzy match on display_name or username
  for member in guild.members:
    if name.lower() in member.display_name.lower():
      return member
    if name.lower() in member.name.lower():
      return member
  return None
```

**Args Schema:**
```python
class SearchUserMessagesInput(BaseModel):
    user_name: str = Field(description="Display name or username to search for")
    query: str = Field(default=None, description="Optional keyword to filter their messages")
    limit: int = Field(default=20, description="Max messages to return (default 20)")
```

---

### 3. GetMessageContextTool

**Purpose:** Get messages surrounding a specific message (for context around a reply or reference).

**When to use:**
- User replies to an old message and asks about it
- "What led up to that message?"
- Understanding context of a referenced message

**Pseudocode:**
```
tool get_message_context(message_id: str, before: int = 5, after: int = 5) -> str:
  try:
    target_msg = channel.fetch_message(message_id)
  except NotFound:
    return "Message not found"
  
  // Get messages before
  before_msgs = list(channel.history(limit=before, before=target_msg))
  before_msgs.reverse()  // Chronological order
  
  // Get messages after
  after_msgs = list(channel.history(limit=after, after=target_msg))
  
  all_msgs = before_msgs + [target_msg] + after_msgs
  
  formatted = []
  for msg in all_msgs:
    prefix = ">>> " if msg.id == message_id else "    "
    formatted.append(prefix + format_message(msg))
  
  return join(formatted, "\n")
```

**Args Schema:**
```python
class GetMessageContextInput(BaseModel):
    message_id: str = Field(description="Discord message ID to get context around")
    before: int = Field(default=5, description="Number of messages before (default 5)")
    after: int = Field(default=5, description="Number of messages after (default 5)")
```

---

### 4. SearchThreadMessagesTool

**Purpose:** Search within a specific thread for messages.

**When to use:**
- "What was discussed in this thread?"
- "Find where we talked about X in the thread"
- Thread-specific context retrieval

**Pseudocode:**
```
tool search_thread_messages(query: str = None, limit: int = 30) -> str:
  if not is_thread(channel):
    return "This tool only works in threads. Use search_channel_messages instead."
  
  messages = []
  for msg in channel.history(limit=limit):
    if query is None or keyword_match(msg.content, query):
      messages.append(format_message(msg))
  
  if not messages:
    return f"No messages found" + (f" matching '{query}'" if query else " in this thread")
  
  return join(messages, "\n")
```

**Args Schema:**
```python
class SearchThreadMessagesInput(BaseModel):
    query: str = Field(default=None, description="Optional keyword to filter (returns all if empty)")
    limit: int = Field(default=30, description="Max messages to return (default 30)")
```

---

### 5. GetChannelSummaryTool

**Purpose:** Get an LLM-generated summary of recent channel activity.

**When to use:**
- "Catch me up on what I missed"
- "What's been happening in this channel?"
- "Summarize the conversation"

**Pseudocode:**
```
tool get_channel_summary(timeframe: str = "1 hour", focus: str = None) -> str:
  limit = timeframe_to_limit(timeframe)  // "1 hour" → ~50, "today" → ~200
  
  messages = list(channel.history(limit=limit))
  if not messages:
    return "No recent activity in this channel."
  
  messages.reverse()  // Chronological order
  
  formatted = [format_message(msg) for msg in messages]
  transcript = join(formatted, "\n")
  
  // Use router LLM for cheap summarization
  prompt = f"""Summarize this Discord conversation concisely.
{"Focus on: " + focus if focus else ""}

Conversation:
{transcript}

Summary:"""
  
  summary = await router_llm.invoke(prompt)
  return summary

function timeframe_to_limit(timeframe) -> int:
  match timeframe:
    "5 minutes" -> 20
    "15 minutes" -> 40
    "30 minutes" -> 60
    "1 hour" -> 100
    "today" -> 200
    _ -> 50  // default
```

**Args Schema:**
```python
class GetChannelSummaryInput(BaseModel):
    timeframe: str = Field(default="1 hour", description="How far back to summarize (e.g., '5 minutes', '1 hour', 'today')")
    focus: str = Field(default=None, description="Optional topic to focus the summary on")
```

**Note:** This tool has an LLM call cost (~$0.001-0.003 per use). Consider rate limiting or gating behind complexity level.

---

## 🏗️ Implementation Architecture

### Channel Reference Passing

Tools need access to the Discord channel object. This requires threading the channel through the agent stack:

```
bot.py (on_message)
  └── AgentEngine.generate_response(channel=message.channel)
        └── CharacterAgent.run(channel=channel)
              └── SearchChannelMessagesTool(channel=channel)
        └── ReflectiveAgent.run(channel=channel)
              └── SearchChannelMessagesTool(channel=channel)
```

**Alternative:** Pass `channel_id` and `guild_id`, then fetch channel in tool:
```python
channel = bot.get_channel(channel_id)
```

This is slightly slower but avoids passing Discord objects through the entire stack.

### Tool Registration

Add to existing tool lists in:
- `src_v2/agents/character_agent.py` → `_get_tools()`
- `src_v2/agents/reflective.py` → `_get_tools()`
- `src_v2/agents/router.py` → `route_and_retrieve()` (if needed)

### New File Structure

```
src_v2/tools/
├── memory_tools.py      # Existing: SearchSummaries, SearchEpisodes, etc.
├── universe_tools.py    # Existing: CheckPlanetContext, GetUniverseOverview
├── insight_tools.py     # Existing: AnalyzePatterns, DetectThemes
├── image_tools.py       # Existing: GenerateImage
└── discord_tools.py     # NEW: All Discord search tools
```

---

## ⚠️ Limitations & Considerations

### Discord API Limitations

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| No keyword search API | Must fetch + filter locally | Limit fetch to 100 messages max |
| Rate limits | 50 requests/second/channel | Unlikely to hit with normal usage |
| No full-text search | Substring match only | Accept limitation; vector memory handles semantic |
| Message edits/deletes | Fetched content may be stale | Accept; Discord API is source of truth |

### Performance

| Metric | Expected | Notes |
|--------|----------|-------|
| Latency per tool call | 50-200ms | Depends on message count |
| Max messages per search | 100 | Configurable, but more = slower |
| LLM cost (summary tool) | ~$0.002 | Uses router model |

### Privacy

- These tools only access messages in channels where the bot has permission
- Messages are not persisted—fetched on-demand and discarded
- Users in the channel can see these messages themselves; bot access is equivalent

---

## 🔗 Integration with Existing Tools

### Comparison with Existing Memory Tools

| Tool | Source | Search Type | Persistence | Use Case |
|------|--------|-------------|-------------|----------|
| `search_archived_summaries` | Qdrant | Semantic | Yes | "What did we talk about last week?" |
| `search_specific_memories` | Qdrant | Semantic | Yes | "What was that boat name?" |
| `lookup_user_facts` | Neo4j | Graph | Yes | "What's my dog's name?" |
| **`search_channel_messages`** | Discord API | Keyword | No | "What did I just say about turtles?" |
| **`search_user_messages`** | Discord API | Keyword | No | "What has Sarah said today?" |

### Router Disambiguation

The router needs to distinguish between:
- **Recent channel context** → Discord tools (mentions "just", "earlier", "today")
- **Historical memory** → Vector tools (mentions "last week", "remember when")

Update router prompt to include:
```
- search_channel_messages: For RECENT channel activity (last hour). "What did I just say?", "What happened earlier?"
- search_user_messages: For finding what a SPECIFIC person said recently.
- search_archived_summaries: For HISTORICAL topics (days/weeks ago). "What did we talk about last week?"
```

---

## 📋 Implementation Checklist

### Phase 1: Core Tools (Day 1-2)
- [x] Remove `GetRecentActivityTool` from `src_v2/tools/universe_tools.py`
- [x] Remove `GetRecentActivityTool` from `ReflectiveAgent._get_tools()`
- [x] Remove `channel_context` parameter threading (no longer needed for tool)
- [x] Remove `get_channel_context()` pre-fetch from `bot.py` (wasteful - fetches 10 messages on every request)
- [x] Remove `[RECENT CHANNEL ACTIVITY]` injection from `engine.py` system prompt
- [x] Create `src_v2/tools/discord_tools.py`
- [x] Implement `SearchChannelMessagesTool`
- [x] Implement `SearchUserMessagesTool`
- [x] Add channel parameter threading to `AgentEngine`
- [x] Register tools in `CharacterAgent._get_tools()`
- [x] Register tools in `ReflectiveAgent._get_tools()`
- [x] Update agent prompts to mention new tools

### Phase 2: Enhanced Tools (Day 2-3)
- [x] Implement `GetMessageContextTool`
- [x] Implement `GetRecentMessagesTool` (simpler alternative to summary - no LLM call)
- [ ] Implement `SearchThreadMessagesTool` (deferred - needs thread detection logic)
- [ ] Implement `GetChannelSummaryTool` (deferred - expensive LLM call per use)
- [ ] Add feature flag: `ENABLE_DISCORD_SEARCH_TOOLS` (deferred - tools are low-cost)

### Phase 3: Testing & Polish (Day 3)
- [ ] Add regression tests for Discord tools
- [ ] Test in DM context (should gracefully fail/skip)
- [ ] Test in threads
- [ ] Test with large message volumes
- [ ] Monitor latency impact

---

## 🔮 Future Enhancements

### Semantic Search (Hybrid)

Instead of pure keyword matching, embed search query and compare against message embeddings:

```
function semantic_match(query, messages) -> List[Message]:
  query_embedding = embed(query)
  scored = []
  for msg in messages:
    msg_embedding = embed(msg.content)
    score = cosine_similarity(query_embedding, msg_embedding)
    scored.append((msg, score))
  return sorted(scored, key=lambda x: x[1], reverse=True)[:10]
```

**Trade-off:** Much slower (~5ms per message for embedding), but better recall for semantic queries.

### Redis Caching Layer

Cache recent channel messages in Redis for faster repeated searches:

```
channel:{channel_id}:messages -> List of last 100 messages (5 min TTL)
```

**Trade-off:** Adds storage overhead and staleness risk, but reduces Discord API calls.

---

## 📚 Related Documents

- [CHANNEL_CONTEXT_AWARENESS.md](./CHANNEL_CONTEXT_AWARENESS.md) - Archived feature (passive channel awareness)
- [MESSAGE_FLOW.md](../architecture/MESSAGE_FLOW.md) - Current message handling architecture
- [CHARACTER_AS_AGENT.md](../architecture/CHARACTER_AS_AGENT.md) - Tool usage patterns

---

**Version History:**
- 1.0 (Nov 28, 2025): Initial specification
