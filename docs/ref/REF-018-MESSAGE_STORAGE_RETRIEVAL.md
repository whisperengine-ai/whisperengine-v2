# REF-018: Message Storage & Retrieval

**Status:** Active  
**Last Updated:** December 5, 2025  
**Author:** WhisperEngine Team

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Core architecture design |
| **Purpose** | Document how messages flow through the five database systems |
| **Key Insight** | Different databases serve different query patterns — recency vs relevance vs relationships |

---

## Overview

WhisperEngine uses **five databases**, each optimized for a specific access pattern:

| Database | Purpose | Query Pattern |
|----------|---------|---------------|
| **PostgreSQL** | Structured data | SQL — by user, timestamp, channel |
| **Qdrant** | Vector memory | Semantic similarity search |
| **Neo4j** | Knowledge graph | Graph traversal, relationships |
| **Redis** | Cache + job queue | Key-value, task dequeue |
| **InfluxDB** | Metrics/analytics | Time-series aggregation |

---

## The Five Databases

### PostgreSQL (Relational)

**Purpose:** "What just happened?"

**Tables:**
```
v2_chat_history         — Full conversation logs
v2_users                — User profiles, preferences, timezone
v2_conversation_sessions — Conversation episode tracking
v2_trust_levels         — Relationship progression (Stranger → Trusted)
v2_goals                — Character goals and strategies
v2_summaries            — Compressed session summaries
```

**Query Example:**
```sql
SELECT role, content, user_name, timestamp 
FROM v2_chat_history 
WHERE user_id = $1 AND character_name = $2
ORDER BY timestamp DESC 
LIMIT 10
```

**Used For:**
- Recent chat history (last N messages)
- Session management
- Trust scores and relationship levels
- User preferences and settings

---

### Qdrant (Vector Database)

**Purpose:** "What's relevant to this topic?"

**Collection Structure:**
```
Collection: whisperengine_memory_{bot_name}

Each point:
├── id: UUID
├── vector: [384 floats]     ← embedding of content
└── payload:
    ├── content: "full message text"
    ├── user_id: "123456789"
    ├── user_name: "MarkAnthony"
    ├── role: "human" | "ai"
    ├── timestamp: "2025-12-05T..."
    ├── importance_score: 1-10
    ├── source_type: "human" | "inference" | "summary" | "gossip"
    ├── channel_id: "987654321"
    └── message_id: "discord_msg_id"
```

**Query Example:**
```python
# Embed the query
embedding = await embedding_service.embed_query_async("user's dog")

# Search for similar memories
results = await qdrant_client.query_points(
    collection_name="whisperengine_memory_elena",
    query=embedding,
    query_filter=Filter(must=[
        FieldCondition(key="user_id", match=MatchValue(value=user_id))
    ]),
    limit=5
)
```

**Used For:**
- Semantic memory search ("What do I remember about X?")
- Finding relevant past conversations
- Summary retrieval for context injection

---

### Neo4j (Graph Database)

**Purpose:** "What do I know about this person?"

**Node Types:**
```
(:User)       — Discord users
(:Entity)     — People, places, things mentioned
(:Topic)      — Discussion topics
(:Character)  — Bot characters
```

**Edge Types:**
```
-[:KNOWS]->      — User knows an entity
-[:LIKES]->      — User likes something
-[:DISLIKES]->   — User dislikes something
-[:WORKS_AT]->   — Employment relationship
-[:DISCUSSED]->  — Topic was discussed
-[:LIVES_IN]->   — Location relationship
```

**Example Graph:**
```
(User:Mark) -[:LIKES]-> (Entity:Taylor Swift)
(User:Mark) -[:WORKS_AT]-> (Entity:Tech Company)
(User:Mark) -[:DISCUSSED]-> (Topic:Dreams)
(User:Mark) -[:HAS_PET]-> (Entity:Dog named Max)
```

**Query Example:**
```cypher
MATCH (u:User {id: $user_id})-[r]->(e)
RETURN e.name, type(r), e.properties
```

**Used For:**
- Facts about users (name, job, interests)
- Common ground between user and character
- Background relevance matching

---

### Redis (In-Memory Cache)

**Purpose:** "Fast ephemeral state"

**Key Patterns:**
```
session:{user_id}:{bot_name}    — Current conversation state
lurk:daily:{date}               — Daily lurk response counter
lurk:cooldown:channel:{id}      — Per-channel cooldown
cross_bot:chain:{channel_id}    — Active bot conversation chains
rate_limit:{user_id}            — Rate limiting counters
```

**Also Used For:**
- Background job queue (arq)
- Cross-bot cooldown tracking
- Temporary state that doesn't need persistence

**Query Example:**
```python
# Check daily lurk count
daily_count = await redis_client.get(f"lurk:daily:{today}")

# Enqueue background job
await task_queue.enqueue("run_summarization", session_id=session_id, ...)
```

---

### InfluxDB (Time-Series)

**Purpose:** "How is the system performing?"

**Measurements:**
```
memory_latency      — Read/write times for memory operations
llm_tokens          — Token usage per model
reaction_sentiment  — User feedback via emoji reactions
response_time       — End-to-end latency
message_event       — Message volume by user/bot
```

**Query Example:**
```flux
from(bucket: "whisperengine")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "memory_latency")
  |> mean()
```

**Write Configuration:**
```python
# Batched writes (non-blocking)
WriteOptions(
    batch_size=10,        # Write after 10 points accumulated
    flush_interval=1000,  # OR every 1 second
    retry_interval=5000,  # Retry failed writes after 5s
    max_retries=3
)
```

**Used For:**
- Performance monitoring
- Usage analytics
- Debugging latency issues

---

## Message Storage: Dual-Write Pattern

Every message is stored in **both PostgreSQL and Qdrant**:

```python
async def add_message(self, user_id, character_name, role, content, ...):
    # 1. Save to PostgreSQL (structured, chronological)
    await conn.execute("""
        INSERT INTO v2_chat_history (user_id, character_name, role, content, ...)
        VALUES ($1, $2, $3, $4, ...)
    """, user_id, character_name, role, content, ...)
    
    # 2. Save to Qdrant (vector, semantic)
    await self._save_vector_memory(
        user_id=user_id,
        role=role,
        content=content,  # ← Full content stored in payload
        ...
    )
```

### Why Dual Storage?

| Database | Query Pattern | Use Case |
|----------|---------------|----------|
| PostgreSQL | "Last 10 messages" | Chat history context |
| Qdrant | "Memories about dogs" | Semantic memory recall |

**No cross-reference needed** — each database is self-contained with full message content.

### Trade-offs

| Concern | Reality |
|---------|---------|
| Storage cost | ~2x for message text (minimal compared to embeddings) |
| Write latency | +50ms for embedding generation |
| Complexity | Simple — no ID mapping or joins needed |
| Resilience | Either DB can serve its purpose independently |

---

## Retrieval Flow

### On Every Message

```
User sends message
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│                  PARALLEL RETRIEVAL                      │
│                                                          │
│  PostgreSQL          Qdrant              Neo4j           │
│  ┌──────────┐       ┌──────────┐       ┌──────────┐     │
│  │ Last 10  │       │ Semantic │       │ Facts &  │     │
│  │ messages │       │ memories │       │ relations│     │
│  │          │       │ (top 5)  │       │          │     │
│  └──────────┘       └──────────┘       └──────────┘     │
│       │                  │                  │            │
└───────┼──────────────────┼──────────────────┼────────────┘
        └──────────────────┼──────────────────┘
                           ▼
                    Build Context
                           │
                           ▼
                    LLM Response
```

### After Response

```
                    LLM Response
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│                  PARALLEL STORAGE                        │
│                                                          │
│  PostgreSQL          Qdrant              Background      │
│  ┌──────────┐       ┌──────────┐       ┌──────────┐     │
│  │ Save to  │       │ Embed &  │       │ Extract  │     │
│  │ history  │       │ store    │       │ facts    │     │
│  └──────────┘       └──────────┘       │ (Neo4j)  │     │
│                                        └──────────┘     │
│                      Redis              InfluxDB         │
│                    ┌──────────┐       ┌──────────┐      │
│                    │ Queue bg │       │ Log      │      │
│                    │ tasks    │       │ metrics  │      │
│                    └──────────┘       └──────────┘      │
└──────────────────────────────────────────────────────────┘
```

---

## Context Injection Order

When building the LLM prompt, context is injected in this order:

```
1. Character System Prompt (from character.md)
   ↓
2. [RELEVANT PAST CONVERSATIONS] — summaries from Qdrant
   ↓
3. [RELATIONSHIP STATUS] — trust level from PostgreSQL
   ↓
4. [USER PREFERENCES] — feedback patterns from PostgreSQL
   ↓
5. [CURRENT GOAL] — active goals from PostgreSQL
   ↓
6. [RECENT DIARY ENTRY] — character thoughts
   ↓
7. [COMMON GROUND] — shared interests from Neo4j
   ↓
8. [RELEVANT BACKGROUND] — character lore from Neo4j
   ↓
9. [CHANNEL CONTEXT] — server/channel info
   ↓
10. [USER LOCAL TIME] — timezone from PostgreSQL
   ↓
11. [RELEVANT MEMORY & KNOWLEDGE] — semantic memories from Qdrant
   ↓
12. [IDENTITY ANCHOR] — anti-confusion guard
```

---

## Memory Scoring (Qdrant)

When retrieving memories, results are re-ranked by weighted score:

```python
weighted_score = semantic_score × temporal_weight × source_weight × importance_weight
```

| Factor | Calculation | Purpose |
|--------|-------------|---------|
| **Semantic Score** | Cosine similarity (0-1) | How relevant to query |
| **Temporal Weight** | Decay over time | Prefer recent memories |
| **Source Weight** | human > inference > gossip | Trust direct interactions |
| **Importance Weight** | Based on importance_score (1-10) | Prioritize significant moments |

---

## Key Files

| File | Purpose |
|------|---------|
| `src_v2/memory/manager.py` | `MemoryManager` — Qdrant + PostgreSQL operations |
| `src_v2/core/database.py` | `DatabaseManager` — connection pools for all DBs |
| `src_v2/knowledge/manager.py` | `KnowledgeManager` — Neo4j operations |
| `src_v2/agents/context_builder.py` | Assembles context from all sources |
| `src_v2/memory/embeddings.py` | `EmbeddingService` — 384D embeddings |

---

## Configuration

| Setting | Default | Purpose |
|---------|---------|---------|
| `QDRANT_HOST` | localhost | Vector database host |
| `QDRANT_PORT` | 6333 | Vector database port |
| `POSTGRES_*` | — | PostgreSQL connection settings |
| `NEO4J_*` | — | Neo4j connection settings |
| `REDIS_*` | — | Redis connection settings |
| `INFLUXDB_*` | — | InfluxDB connection settings |

---

## Quick Reference

| Need | Database | Method |
|------|----------|--------|
| Recent conversation | PostgreSQL | `get_recent_history()` |
| Relevant memories | Qdrant | `search_memories()` |
| Facts about user | Neo4j | `get_user_knowledge()` |
| Session state | Redis | Key-value get/set |
| Performance metrics | InfluxDB | Time-series queries |
| Summaries | Qdrant + PostgreSQL | `search_summaries()` |

---

## Related Documentation

- [REF-003: Memory System](./REF-003-MEMORY_SYSTEM.md) — Detailed memory architecture
- [REF-017: Conversation Sessions](./REF-017-CONVERSATION_SESSIONS.md) — Session lifecycle
- [REF-004: Message Flow](./REF-004-MESSAGE_FLOW.md) — Full request lifecycle
- [REF-005: Data Models](./REF-005-DATA_MODELS.md) — Database schemas
