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

### Key Insight: Three Different Concepts Conflated

The current `user_id` field conflates three things:

1. **Author** — Who wrote THIS specific message
2. **Participant** — Who was present in the conversation
3. **Session User** — Who the bot is "primarily" engaging with

In 1:1 DMs, these are the same. In channels, they're different.

## Decision

### New Schema: Conversation + Message + Participant

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

### How This Solves the Problems

| Problem | Solution |
|---------|----------|
| "Bot talking to self" | Bot's message has `author_id = bot.id`, but conversation has multiple participants |
| Facts attributed wrong | Extract facts per `author_id`, not per conversation |
| Trust updates | Update trust for ALL participants in conversation |
| Sessions | Sessions become conversation-scoped, not user-scoped |
| Role ambiguity | No more "role" field — just `author_is_bot` |

### Migration Strategy

**Phase 1: Add author_id (Non-Breaking)**
```sql
ALTER TABLE v2_chat_history ADD COLUMN author_id TEXT;
ALTER TABLE v2_chat_history ADD COLUMN author_is_bot BOOLEAN DEFAULT FALSE;
ALTER TABLE v2_chat_history ADD COLUMN reply_to_id INTEGER;
```

Backfill:
- For `role = 'human'`: `author_id = user_id`
- For `role = 'ai'`: `author_id = character_name` (bot)

**Phase 2: Create New Tables (Parallel)**
Create `v2_conversations`, `v2_messages`, `v2_participants` alongside existing tables.

**Phase 3: Dual-Write**
Write to both old and new schemas during transition.

**Phase 4: Migrate Reads**
Update queries to use new schema.

**Phase 5: Deprecate Old Schema**
Drop `v2_chat_history` once all reads migrated.

## Consequences

### Positive
- Multi-party conversations work correctly
- Learning attributes facts to correct authors
- Trust updates for all participants
- Threading (`reply_to_id`) enables conversation reconstruction
- Cleaner separation of concerns

### Negative
- Schema migration complexity
- Dual-write period adds latency
- Existing queries need rewriting
- More JOINs in queries

### Neutral
- Storage slightly higher (normalized vs denormalized)
- Index strategy changes

## Alternatives Considered

### A: Keep Current Schema + Convention
Use `user_id` conventions like `channel_{id}` for channel posts.

**Rejected:** This is a hack that doesn't fix learning/trust attribution.

### B: JSON Blob for Participants
Store participant list as JSON in existing table.

**Rejected:** Can't efficiently query/index, joins are awkward.

### C: Separate Channel History Table
Create `v2_channel_history` with different schema.

**Rejected:** Code duplication, harder to search across DMs and channels.

## Implementation Order

1. **ADR-014** (this doc) — Approve data model direction
2. **Phase 1 migration** — Add `author_id`, `author_is_bot`, `reply_to_id` to existing table
3. **Update learning pipeline** — Use `author_id` for fact attribution
4. **Update trust pipeline** — Update all participants
5. **Phase 2-5** — Full schema migration (can be deferred)

## Relationship to ADR-013 (Event-Driven Architecture)

These two ADRs work together:

| ADR-013 (Architecture) | ADR-014 (Data Model) |
|------------------------|----------------------|
| How events flow | How data is stored |
| State machines | Conversation records |
| On-demand context fetch | What gets fetched |
| Response threading | `reply_to_id` field |

**Implementation order:** ADR-013 can be implemented first (event capture, state machines) using the existing schema. ADR-014's Phase 1 (add `author_id`) enables proper attribution. Full schema migration can happen later.

## Related ADRs
- ADR-013: Event-Driven Architecture (processing architecture)
- ADR-012: Unified Architecture (current system design)
