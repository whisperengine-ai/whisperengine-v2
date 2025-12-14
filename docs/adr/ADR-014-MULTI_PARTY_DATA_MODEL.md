# ADR-014: Multi-Party Conversation Data Model

**Status:** 📋 Proposed → **Phase 1 is PREREQUISITE for ADR-017**  
**Date:** December 13, 2025  
**Updated:** December 13, 2025  
**Deciders:** Mark, Claude (collaborative)

> **Priority Update:** ADR-017 (Bot-to-Bot Simplified) requires Phase 1 of this ADR before implementation. We can't properly store bot-to-bot conversations without `author_id` and `author_is_bot` fields.

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Architecture review during Daily Life Graph debugging |
| **Proposed by** | Claude (analysis of repeated "whack-a-mole" fixes) |
| **Catalyst** | Multiple tactical fixes failing because core data model assumes 1:1 conversations |

## Context

### Current Data Model (Dyadic/1:1)

The `v2_chat_history` table was designed for DM conversations:

```sql
v2_chat_history:
  id              -- PK
  user_id         -- THE human (assumes 1 person)
  character_name  -- THE bot (assumes 1 bot)
  role            -- "human" or "ai" (binary)
  content         -- message text
  timestamp
  -- Added later:
  channel_id      -- where it happened
  message_id      -- Discord message ID
  user_name       -- display name
  metadata        -- JSON blob
```

**The core assumption:** Every conversation is between ONE human (`user_id`) and ONE bot (`character_name`).

### Why This Breaks in Channels

In a Discord channel with multiple humans and bots:

| Problem | Root Cause |
|---------|------------|
| "Bot talking to self" | When bot posts to channel, `user_id = bot.user.id` because there's no "primary human" |
| Facts attributed to wrong person | Learning uses single `user_id`, not per-message author |
| Trust only updates for one person | `update_trust(user_id, ...)` — no multi-party concept |
| Sessions don't work in channels | Sessions are `(user_id, character_name)` pairs |
| Role is ambiguous | In multi-bot channels, whose "ai" is it? |

### Current Hacks (Will Be Fixed)

The codebase has workarounds that paper over this problem:

```python
# daily_life.py: Fake user_id for channel posts
if cmd.action_type == "reply" and cmd.target_author_id:
    context_user_id = cmd.target_author_id
else:
    context_user_id = f"channel_{channel.id}"  # HACK: Not a real user
```

This causes:
- Queries like `WHERE user_id = 'channel_123'` that find nothing useful
- Facts learned from channel conversations attributed to a fake user
- Trust scores for "channel_123" that mean nothing

### Key Insight: Three Different Concepts Conflated

The current `user_id` field conflates three things:

1. **Author** — Who wrote THIS specific message
2. **Participant** — Who was present in the conversation
3. **Session User** — Who the bot is "primarily" engaging with

In 1:1 DMs, these are the same. In channels, they're different.

## Decision

### Long-term Vision: Conversation + Message + Participant

```sql
-- Conversations: A context where messages happen
v2_conversations:
  id              -- UUID
  channel_id      -- Discord channel (nullable for DMs)
  type            -- 'dm' | 'group_dm' | 'channel'
  created_at
  last_activity_at

-- Messages: Who said what
v2_messages:
  id              -- PK
  conversation_id -- FK to v2_conversations
  discord_msg_id  -- Discord message ID (for dedup)
  author_id       -- WHO wrote it (human or bot ID)
  author_name     -- Display name at time of message
  author_is_bot   -- Boolean
  content
  timestamp
  reply_to_id     -- FK to v2_messages (threading)
  metadata        -- JSON (action_type, etc.)

-- Participants: Who was involved in a conversation
v2_participants:
  conversation_id -- FK
  user_id         -- Participant ID
  user_name       -- Current display name
  is_bot          -- Boolean
  first_seen_at
  last_seen_at
  message_count   -- How many messages they sent
```

**Note:** This is the FULL schema for Phase 2+. Phase 1 only adds columns to existing table.

### How This Solves the Problems

| Problem | Solution |
|---------|----------|
| "Bot talking to self" | Bot's message has `author_id = bot.id`, but conversation has multiple participants |
| Facts attributed wrong | Extract facts per `author_id`, not per conversation |
| Trust updates | Update trust for ALL participants in conversation |
| Sessions | Sessions become conversation-scoped, not user-scoped |
| Role ambiguity | No more "role" field — just `author_is_bot` |

---

## Phase 1: Minimum Viable Schema (DO FIRST)

This is the **minimum change needed** to unblock ADR-017 (bot-to-bot conversations).

### All Three Data Stores Need Updates

| Store | Current State | Problem | Fix |
|-------|---------------|---------|-----|
| **PostgreSQL** | `user_id` = conversation partner | Can't distinguish author | Add `author_id`, `author_is_bot` |
| **Qdrant** | `user_id` in payload | Same problem | Add `author_id`, `author_is_bot` to payload |
| **Neo4j** | `User` nodes only | Bots not represented | Add `is_bot` to User nodes OR separate `Bot` nodes |

---

### 1. PostgreSQL Changes

```sql
-- Add author tracking to existing table (non-breaking)
ALTER TABLE v2_chat_history ADD COLUMN author_id TEXT;
ALTER TABLE v2_chat_history ADD COLUMN author_is_bot BOOLEAN DEFAULT FALSE;
ALTER TABLE v2_chat_history ADD COLUMN reply_to_msg_id TEXT;  -- Discord message ID we're replying to

-- Index for efficient author queries
CREATE INDEX idx_v2_chat_history_author ON v2_chat_history(author_id);
CREATE INDEX idx_v2_chat_history_author_bot ON v2_chat_history(author_id, author_is_bot);
```

**Backfill:**
```sql
UPDATE v2_chat_history 
SET author_id = CASE 
    WHEN role = 'human' THEN user_id
    WHEN role = 'ai' THEN character_name  -- Will be replaced with bot Discord ID
    ELSE user_id
END,
author_is_bot = (role = 'ai')
WHERE author_id IS NULL;
```

---

### 2. Qdrant Payload Changes

Current payload structure:
```python
payload = {
    "type": "conversation",
    "user_id": str(user_id),      # Conversation partner - AMBIGUOUS
    "role": role,                  # "human" or "ai" - NOT WHO WROTE IT
    "content": content,
    "timestamp": timestamp_str,
    "channel_id": str(channel_id),
    "message_id": str(message_id),
    "source_type": source_type.value,
    "user_name": user_name
}
```

**New payload fields:**
```python
payload = {
    # ... existing fields ...
    "user_id": str(user_id),       # Keep for compatibility (conversation partner)
    "role": role,                   # Keep for compatibility
    # NEW FIELDS:
    "author_id": str(author_id),    # WHO wrote this message
    "author_is_bot": author_is_bot, # Is author a bot?
    "author_name": author_name,     # Display name of author
    "reply_to_msg_id": reply_to_msg_id,  # Threading
}
```

**Qdrant doesn't require migration** — new fields are automatically indexed. Old vectors just won't have these fields (use `user_id` as fallback).

**Query changes:**
```python
# Before: Find bot messages (unreliable - role doesn't mean author)
Filter(must=[FieldCondition(key="role", match=MatchValue(value="ai"))])

# After: Find messages written BY bots
Filter(must=[FieldCondition(key="author_is_bot", match=MatchValue(value=True))])

# After: Find messages written by specific bot
Filter(must=[FieldCondition(key="author_id", match=MatchValue(value=bot_discord_id))])
```

---

### 3. Neo4j Changes

Current graph model:
```
(:User {id: discord_id})-[:FACT]->(:Entity)
(:User)-[:HAS_MEMORY]->(:Memory)
(:Character {name: bot_name})  # Only for self-reflection
```

**Problem:** When Bot A talks to Bot B:
- We create `(:User {id: bot_a_id})` — but this is a bot, not a human
- Facts learned from Bot A are stored as if it's a human user
- No way to query "what do bots know?"

**Solution Option A: Add `is_bot` to User nodes (minimal change)**
```cypher
-- Add is_bot property to User nodes
MATCH (u:User)
SET u.is_bot = false  -- Default for existing users

-- When creating new User node for a bot:
MERGE (u:User {id: $author_id})
ON CREATE SET u.is_bot = $is_bot, u.name = $author_name
```

**Solution Option B: Separate Bot nodes (cleaner, more work)**
```cypher
-- Create Bot node type
(:Bot {id: discord_id, name: character_name})

-- Facts from bots use Bot nodes
(:Bot)-[:FACT]->(:Entity)

-- Bot-to-bot conversations
(:Bot)-[:TALKED_TO]->(:Bot)
```

**Recommended: Option A** — less disruptive, facts work the same way, just tagged.

---

### Code Changes Required

**1. `memory_manager.add_message()` — Add author fields:**

```python
async def add_message(
    self,
    user_id: str,           # Context user (conversation partner)
    character_name: str,     # Which bot's collection
    role: str,              # "human" or "ai" (keep for compatibility)
    content: str,
    user_name: Optional[str] = None,
    channel_id: str = None,
    message_id: str = None,
    # NEW FIELDS:
    author_id: str = None,           # WHO wrote this message
    author_is_bot: bool = False,     # Is author a bot?
    reply_to_msg_id: str = None,     # Discord msg ID we're replying to
    ...
):
    # If author_id not provided, derive from role
    if author_id is None:
        author_id = user_id if role == "human" else str(self.bot_user_id)
        author_is_bot = (role == "ai")
```

**2. `bot.py` — Pass author info when saving messages:**

```python
# When saving human message:
await memory_manager.add_message(
    user_id=str(message.author.id),
    character_name=self.character_name,
    role="human",
    content=message.content,
    author_id=str(message.author.id),      # NEW
    author_is_bot=message.author.bot,       # NEW
    reply_to_msg_id=str(message.reference.message_id) if message.reference else None,  # NEW
    ...
)

# When saving bot response:
await memory_manager.add_message(
    user_id=str(message.author.id),  # Still the user we're talking to
    character_name=self.character_name,
    role="ai",
    content=response,
    author_id=str(self.bot.user.id),        # NEW: Bot's Discord ID
    author_is_bot=True,                      # NEW
    reply_to_msg_id=str(message.id),         # NEW: Reply to user's message
    ...
)
```

**3. `knowledge_tasks.py` — Use author_id for fact attribution:**

```python
# Before: Facts attributed to user_id (the conversation partner)
await knowledge_manager.save_facts(user_id, facts, character_name)

# After: Facts attributed to author_id (who actually said it)
await knowledge_manager.save_facts(author_id, facts, character_name, is_bot=author_is_bot)
```

### What Phase 1 Enables

| Use Case | Before | After |
|----------|--------|-------|
| Bot A talks to Bot B | `user_id = bot_a_id, role = "human"` 🤔 | `author_id = bot_a_id, author_is_bot = true` ✅ |
| Query "what did bots say?" | Can't distinguish | `WHERE author_is_bot = true` |
| Learn facts from bot convo | Attributed to "human" | Attributed to correct author |
| Reply threading | No way to track | `reply_to_msg_id` links messages |

---

## Phase 2-5: Full Schema Migration (DEFERRED)

The full normalized schema (`v2_conversations`, `v2_messages`, `v2_participants`) is **deferred** until we need:
- Multi-party sessions (not just 1:1)
- Efficient participant queries
- Conversation-level metadata

Phase 1 is sufficient for bot-to-bot conversations.

### Migration Strategy (When Ready)

**Phase 2: Create New Tables (Parallel)**
Create `v2_conversations`, `v2_messages`, `v2_participants` alongside existing tables.

**Phase 3: Dual-Write**
Write to both old and new schemas during transition.

**Phase 4: Migrate Reads**
Update queries to use new schema.

**Phase 5: Deprecate Old Schema**
Drop `v2_chat_history` once all reads migrated.

---

## Consequences

### Positive
- Bot-to-bot conversations stored correctly across all 3 stores
- Learning attributes facts to correct authors
- Reply threading enables conversation reconstruction
- Non-breaking migration (additive)
- Qdrant needs no migration (payload fields auto-indexed)

### Negative
- `role` field becomes semi-redundant (but keep for compatibility)
- `user_id` still overloaded (context partner vs author) until Phase 2
- Need to backfill existing Postgres data
- Neo4j `User` nodes now include bots (slight semantic confusion)

### Neutral
- Storage slightly higher (new columns/fields)
- New indexes needed in Postgres

---

## Implementation Checklist

### Phase 1 (Do Now) — ✅ COMPLETE (Dec 13, 2025)

**PostgreSQL:**
- [x] Migration file: Add `author_id`, `author_is_bot`, `reply_to_msg_id` columns
- [x] Backfill script: Populate from existing `role` and `user_id`
- [x] Update `add_message()` INSERT statement

**Qdrant:**
- [x] Update `_save_vector_memory()` payload to include `author_id`, `author_is_bot`, `author_name`
- [x] Update `search_memories()` to return author fields in results
- [x] (No migration needed - new fields auto-indexed)

**Neo4j:**
- [x] Update `add_memory_node()` to pass `is_bot` flag
- [x] Update User node creation to set `is_bot` property
- [x] Create `:AUTHORED` relationship when author != conversation partner

**Code Integration:**
- [x] `memory_manager.add_message()`: Add author parameters
- [x] `memory_manager._save_vector_memory()`: Add author to payload  
- [x] `memory_manager.save_typed_memory()`: Add author tracking (bot-generated)
- [x] `memory_manager.save_summary_vector()`: Add author fields (bot-generated)
- [x] `memory_manager.get_chat_history()`: Query and display author info
- [x] `message_handler.py`: Pass `author_id`, `author_is_bot` when saving messages
- [x] `daily_life.py`: Pass author fields for autonomous messages
- [x] `broadcast/manager.py`: Author fields for broadcast posts and proactive DMs
- [x] `vision/manager.py`: Author fields for image analysis memories
- [x] `knowledge_manager.save_facts()`: Already handles `is_self_reflection` for bots

**Prompt Engineering (Context Formatting):**
- [x] `master_graph.py`: Format memories with `[Author (bot)]:` prefix
- [x] `tools/memory_tools.py`: SearchEpisodesTool returns author attribution
- [x] Legacy fallback: Uses `role` field when `author_id` missing

**Tests:**
- [ ] Verify bot message stored with correct `author_id`
- [ ] Verify facts attributed to correct author
- [ ] Verify Qdrant filter `author_is_bot=True` works
- [ ] Verify Neo4j User node has `is_bot` property
- [ ] Verify memory context shows `[BotName (bot)]:` format

### Phase 2+ (Deferred)

- [ ] Design `v2_conversations` table
- [ ] Design `v2_messages` table  
- [ ] Design `v2_participants` table
- [ ] Implement dual-write
- [ ] Migrate read queries
- [ ] Deprecate `v2_chat_history`

---

## Related ADRs

- **ADR-017**: Bot-to-Bot Simplified → **Depends on Phase 1**
- **ADR-013**: Event-Driven Architecture (processing architecture) → Deferred
- **ADR-012**: Unified Architecture (current system design)
