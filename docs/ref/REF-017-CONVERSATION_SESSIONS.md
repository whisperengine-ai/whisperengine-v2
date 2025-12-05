# REF-017: Conversation Sessions

**Status:** Active  
**Last Updated:** December 5, 2025  
**Author:** WhisperEngine Team

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Core architecture design |
| **Purpose** | Group messages into conversation episodes for summarization and context boundaries |
| **Key Insight** | Continuous conversations need natural break points for memory compression |

---

## Overview

A **session** represents a continuous conversation window between a specific user and a specific bot character. Think of it like a "conversation episode" — it starts when you begin talking and ends after 30 minutes of silence.

Sessions enable:
- **Memory compression** via summarization
- **Context boundaries** between unrelated conversations
- **Analytics** on conversation patterns
- **Knowledge extraction** at natural break points

---

## Database Schema

### PostgreSQL: `v2_conversation_sessions`

```sql
CREATE TABLE v2_conversation_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         TEXT NOT NULL,
    character_name  TEXT NOT NULL,
    start_time      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    end_time        TIMESTAMPTZ,
    is_active       BOOLEAN DEFAULT TRUE,
    updated_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast lookup of active sessions
CREATE INDEX idx_sessions_active ON v2_conversation_sessions(user_id, character_name, is_active);
```

| Column | Type | Purpose |
|--------|------|---------|
| `id` | UUID | Unique identifier for the session |
| `user_id` | TEXT | Discord user ID |
| `character_name` | TEXT | Bot name (elena, nottaylor, etc.) |
| `start_time` | TIMESTAMPTZ | When conversation began |
| `end_time` | TIMESTAMPTZ | When session was closed (null if active) |
| `is_active` | BOOLEAN | TRUE while conversation ongoing |
| `updated_at` | TIMESTAMPTZ | Last message timestamp |

### PostgreSQL: `v2_summaries` (linked to sessions)

```sql
CREATE TABLE v2_summaries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID REFERENCES v2_conversation_sessions(id),
    user_id         TEXT NOT NULL,
    character_name  TEXT NOT NULL,
    content         TEXT NOT NULL,
    meaningfulness  INTEGER DEFAULT 3,  -- 1-5 scale
    embedding_id    TEXT,               -- Qdrant point ID
    created_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

| Column | Type | Purpose |
|--------|------|---------|
| `session_id` | UUID | FK → v2_conversation_sessions.id |
| `content` | TEXT | LLM-generated summary text |
| `meaningfulness` | INTEGER | 1-5 score (how deep was the convo?) |
| `embedding_id` | TEXT | Qdrant point ID for semantic search |

---

## Session Lifecycle

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SESSION LIFECYCLE                            │
└─────────────────────────────────────────────────────────────────────┘

User sends first message
         │
         ▼
┌─────────────────────┐
│  CREATE SESSION     │  ← New UUID, is_active=TRUE, start_time=NOW
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│  User sends msg #2  │  ← updated_at refreshed
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│  User sends msg #3  │  ← updated_at refreshed
└─────────────────────┘
         │
         ▼
    ... more messages ...
         │
         ▼
┌─────────────────────┐
│  20+ messages?      │──YES──► Enqueue summarization (background)
└─────────────────────┘         (doesn't close session yet)
         │
         ▼
┌─────────────────────┐
│  30 min no activity │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│  Next message       │  ← Triggers timeout check
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│  CLOSE OLD SESSION  │  ← is_active=FALSE, end_time=NOW
│  CREATE NEW SESSION │  ← Fresh UUID for new conversation
└─────────────────────┘
```

---

## How Sessions Are Used

| Feature | How Session is Used |
|---------|---------------------|
| **Message Grouping** | All messages in a session belong to one "conversation episode" |
| **Summarization Trigger** | When session hits 20+ messages, enqueue summary job |
| **Summary Storage** | Summary is linked to `session_id` in `v2_summaries` table |
| **Context Boundaries** | Prevents mixing unrelated conversations from different days |
| **Graph Enrichment** | When session reaches certain thresholds, extract knowledge to Neo4j |

---

## Session vs Other Storage

| Concept | Purpose | Storage |
|---------|---------|---------|
| **Session** | Group messages into conversation episodes | PostgreSQL `v2_conversation_sessions` |
| **Chat History** | Individual messages | PostgreSQL `v2_chat_history` |
| **Memories** | Semantically searchable messages | Qdrant vectors |
| **Summaries** | Compressed session content | PostgreSQL `v2_summaries` + Qdrant |

---

## Code Flow

### 1. Session Creation/Retrieval

```python
# Every incoming message (message_handler.py)
session_id = await session_manager.get_active_session(user_id, bot_name)
```

### 2. Inside `get_active_session()`

```python
async def get_active_session(self, user_id: str, character_name: str) -> Optional[str]:
    """Get or create an active session for this user+character pair."""
    
    # Find existing active session
    row = await conn.fetchrow("""
        SELECT id, updated_at FROM v2_conversation_sessions
        WHERE user_id = $1 AND character_name = $2 AND is_active = TRUE
    """, user_id, character_name)
    
    if row:
        last_activity = row['updated_at']
        
        # Check for timeout (30 min)
        if (now - last_activity) > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
            # Close old session
            await self._close_session(row['id'])
            # Create new session
            return await self._create_session(user_id, character_name)
        else:
            # Update activity timestamp
            await self._touch_session(row['id'])
            return str(row['id'])
    
    # No active session - create one
    return await self._create_session(user_id, character_name)
```

### 3. Summarization Trigger

```python
# After bot responds (message_handler.py)
message_count = await memory_manager.count_messages_since(
    user_id, character_name, session_start_time
)

if message_count >= settings.SUMMARY_MESSAGE_THRESHOLD:  # default: 20
    await enqueue_post_conversation_tasks(
        session_id=session_id,
        messages=msg_dicts,
        user_id=user_id,
        user_name=display_name,
        character_name=character_name
    )
```

### 4. Background Summarization

```python
# summary_tasks.py (background worker)
async def run_summarization(session_id: str, messages: List[dict], ...):
    # 1. LLM generates summary
    summary_result = await summary_graph.run(
        messages=messages,
        user_name=user_name,
        character_name=character_name
    )
    
    # 2. Score meaningfulness (1-5)
    meaningfulness = summary_result.get("meaningfulness", 3)
    
    # 3. If meaningful enough, save
    if meaningfulness >= 3:
        # Save to PostgreSQL
        await save_summary(session_id, summary_result["content"], meaningfulness)
        
        # Embed and save to Qdrant for semantic search
        await save_summary_embedding(user_id, summary_result["content"])
```

---

## Configuration

| Setting | Default | Purpose | Location |
|---------|---------|---------|----------|
| `SESSION_TIMEOUT_MINUTES` | 30 | How long until session auto-closes | `session.py` |
| `SUMMARY_MESSAGE_THRESHOLD` | 20 | Messages needed before summarizing | `settings.py` |

---

## Key Files

| File | Purpose |
|------|---------|
| `src_v2/memory/session.py` | `SessionManager` class |
| `src_v2/discord/handlers/message_handler.py` | Session integration in message flow |
| `src_v2/workers/tasks/summary_tasks.py` | Background summarization |
| `src_v2/agents/summary_graph.py` | LLM summarization agent |

---

## Why Sessions Matter

1. **Memory Compression** — Long conversations get summarized, saving context tokens
2. **Semantic Continuity** — "Last time we talked about X" works because sessions group related messages
3. **Analytics** — Track conversation length, engagement patterns, meaningful interactions
4. **Knowledge Extraction** — Graph enrichment runs on session boundaries
5. **Natural Boundaries** — 30-minute timeout mirrors natural conversation pauses

---

## Summary Retrieval

Summaries are stored in both PostgreSQL (for metadata) and Qdrant (for semantic search):

```python
# Semantic search for relevant past conversations
async def search_summaries(self, query: str, user_id: str, limit: int = 3):
    """Search summaries by semantic similarity."""
    embedding = await self.embedding_service.embed_query_async(query)
    
    results = await db_manager.qdrant_client.query_points(
        collection_name=self.collection_name,
        query=embedding,
        query_filter=Filter(must=[
            FieldCondition(key="user_id", match=MatchValue(value=user_id)),
            FieldCondition(key="type", match=MatchValue(value="summary"))
        ]),
        limit=limit
    )
    return results
```

These summaries are injected into the prompt as `[RELEVANT PAST CONVERSATIONS]`.

---

## Related Documentation

- [REF-003: Memory System](./REF-003-MEMORY_SYSTEM.md) — Overall memory architecture
- [REF-012: Summarization System](./REF-012-SUMMARIZATION.md) — LLM summarization details
- [REF-004: Message Flow](./REF-004-MESSAGE_FLOW.md) — Where sessions fit in the pipeline
