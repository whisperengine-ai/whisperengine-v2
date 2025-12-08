# REF-040: Cross-Bot Data Sharing Mechanisms

**Version:** 1.0  
**Last Updated:** December 8, 2025  
**Status:** Reference Documentation  
**Author:** WhisperEngine Team

---

## Overview

WhisperEngine bots share data through **6 distinct channels**, each serving a different purpose. This document provides a comprehensive reference for how data flows between bot instances while maintaining user privacy.

---

## 1. Universe Event Bus (Gossip System)

**Purpose:** Share significant life events about users across bots

### Components

| Component | Location |
|-----------|----------|
| Event Detection | `src_v2/universe/detector.py` |
| Event Bus | `src_v2/universe/bus.py` |
| Privacy Rules | `src_v2/universe/privacy.py` |
| Worker Task | `src_v2/workers/tasks/social_tasks.py` → `run_gossip_dispatch()` |

### Event Types

```python
class EventType(str, Enum):
    USER_UPDATE = "user_update"          # Major life event (new job, moved, etc.)
    EMOTIONAL_SPIKE = "emotional_spike"  # User is notably happy/sad
    TOPIC_DISCOVERY = "topic_discovery"  # User revealed new interest/hobby
    GOAL_ACHIEVED = "goal_achieved"      # User completed something meaningful
```

### Flow

```
User tells Elena "I got promoted!" 
  → EventDetector detects life update
  → Publishes UniverseEvent to event_bus
  → Worker checks privacy (user trust ≥ FRIEND with target bots)
  → Stores gossip in SharedArtifactManager
  → Other bots discover it via semantic search in dreams/diaries
```

### Privacy Controls

- **Sensitive topics blocked:** health, finance, relationships, legal, secrets
- **Trust requirement:** FRIEND+ level (trust score ≥ 20) with target bot
- **User opt-out:** `share_with_other_bots` privacy setting
- **Loop prevention:** `propagation_depth > 1` events are ignored

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `ENABLE_UNIVERSE_EVENTS` | `true` | Master switch for gossip system |
| `ENABLE_SENSITIVITY_CHECK` | `false` | LLM-based sensitivity filtering (expensive) |
| `MIN_TRUST_FOR_GOSSIP` | `20` | Minimum trust score required |

---

## 2. Shared Artifacts Pool (Qdrant)

**Purpose:** Central repository for cross-bot discoverable content

### Components

| Component | Location |
|-----------|----------|
| Manager | `src_v2/memory/shared_artifacts.py` |
| Collection | `whisperengine_shared_artifacts` (Qdrant) |

### Artifact Types

| Type | Description | Source |
|------|-------------|--------|
| `gossip` | Life events from Universe Event Bus | `run_gossip_dispatch()` |
| `epiphany` | Insights discovered by InsightGraphAgent | `insight_tools.py` |
| `pattern` | Behavioral patterns detected | `insight_tools.py` |

### Storage Schema

```python
payload = {
    "type": artifact_type,        # gossip, epiphany, pattern
    "content": content,           # The actual content
    "source_bot": source_bot,     # Bot that created this
    "user_id": user_id,           # Related user (if any)
    "confidence": confidence,     # 0.0-1.0 confidence score
    "created_at": timestamp,      # ISO format
    "eligible_recipients": [...], # Bots allowed to see this (gossip only)
    **metadata                    # Additional context
}
```

### Discovery API

```python
# Discover artifacts from other bots
results = await shared_artifact_manager.discover_artifacts(
    query="user's recent news",
    artifact_types=["gossip", "epiphany"],
    exclude_bot="elena",  # Don't show own artifacts
    user_id="123456",     # Filter by user
    limit=5
)

# Get gossip specifically for a bot (with privacy filtering)
gossip = await shared_artifact_manager.get_gossip_for_bot(
    bot_name="dotty",
    hours=24
)
```

### Privacy Enforcement

- `exclude_bot` filter prevents self-discovery
- `eligible_recipients` field checked on gossip retrieval
- `confidence >= STIGMERGIC_CONFIDENCE_THRESHOLD` (default: 0.7) filters low-quality artifacts
- Semantic search ensures relevance

---

## 3. Universe Graph (Neo4j)

**Purpose:** Shared knowledge about planets, users, topics, and relationships

### Components

| Component | Location |
|-----------|----------|
| Manager | `src_v2/universe/manager.py` |
| Context Builder | `src_v2/universe/context_builder.py` |

### Graph Schema

#### Node Types

| Node | Properties | Description |
|------|------------|-------------|
| `Planet` | `id`, `name`, `active`, `last_seen` | Discord server |
| `Channel` | `id`, `name`, `type`, `last_seen` | Channel in server |
| `User` | `id`, `display_name`, `traits[]` | Discord user |
| `Topic` | `name`, `mention_count` | Emergent interest |
| `Character` | `name`, `bot_id` | Bot identity |

#### Relationship Types

| Relationship | Description |
|--------------|-------------|
| `Character -[:KNOWS_USER]-> User` | Bot has interacted with user |
| `Planet -[:HAS_CHANNEL]-> Channel` | Server contains channel |
| `User -[:ON_PLANET]-> Planet` | User is on server |
| `User -[:DISCUSSED]-> Topic` | User has discussed topic |

> **Note:** Bot-planet presence is *inferred* via `Character -[:KNOWS_USER]-> User -[:ON_PLANET]-> Planet`, not stored directly.

#### Familiarity Tracking

```python
# KNOWS_USER relationship properties
{
    "familiarity": 15,           # Accumulated interaction score
    "interaction_count": 42,     # Total interactions
    "first_interaction": "...",  # Timestamp
    "last_interaction": "...",   # Timestamp
    "guild_id": "..."            # Where they met
}
```

### Cross-Bot Queries

```cypher
// What other bots know this user?
MATCH (c:Character)-[r:KNOWS_USER]->(u:User {id: $user_id})
RETURN c.name, r.familiarity
ORDER BY r.familiarity DESC

// What bots are active on this planet? (inferred from user relationships)
MATCH (c:Character)-[:KNOWS_USER]->(:User)-[:ON_PLANET]->(p:Planet {id: $guild_id})
RETURN DISTINCT c.name

// Who else discusses this topic?
MATCH (u:User)-[:DISCUSSED]->(t:Topic {name: $topic})<-[:DISCUSSED]-(other:User)
WHERE u.id <> other.id
RETURN other.id, count(*) as shared_topics
```

---

## 4. Redis Bot Registry & Coordination

**Purpose:** Real-time cross-bot state coordination

### Components

| Component | Location |
|-----------|----------|
| Cross-Bot Manager | `src_v2/broadcast/cross_bot.py` |
| Cache Manager | `src_v2/core/cache.py` |

### Redis Key Patterns

| Key Pattern | Purpose | TTL |
|-------------|---------|-----|
| `whisper:crossbot:bot:{name}` | Bot registry (discord ID) | 24h (refreshed hourly) |
| `whisper:crossbot:cooldown:{channel}` | Channel cooldown after chain | Config-based |
| `whisper:crossbot:chain:{channel}` | Active conversation chain state | 10 minutes |
| `whisper:crossbot:burst:{channel}` | Burst detection window | 30 seconds |
| `whisper:crossbot:lock:{channel}` | Distributed lock for chain ops | 30 seconds |

> **TTL Strategy:** Bot registry uses 24h TTL as a safety net for crashed bots. Running bots refresh via `start_registration_loop()` every hour, resetting the TTL. Dead bots auto-expire after 24h without manual cleanup.

### Bot Discovery Flow

```python
# 1. Each bot registers itself on startup
key = f"whisper:crossbot:bot:{bot_name.lower()}"
await redis.set(key, str(discord_user_id), ex=86400)  # 24h TTL

# 2. Other bots scan for peers
pattern = "whisper:crossbot:bot:*"
cursor, keys = await redis.scan(0, match=pattern)
for key in keys:
    bot_name = key.split(":")[-1]
    discord_id = await redis.get(key)
    known_bots[bot_name] = int(discord_id)
```

### Conversation Chain State

```python
@dataclass
class ConversationChain:
    channel_id: str
    participants: Set[str]      # Bot names in chain
    message_count: int          # Current turn count
    started_at: datetime
    last_activity_at: datetime
    last_message_id: str
    last_bot: str               # Last bot who spoke
```

---

## 5. Cross-Bot Chat (Direct Conversations)

**Purpose:** Bots can talk to each other in channels

### Components

| Component | Location |
|-----------|----------|
| Mention Detection | `src_v2/broadcast/cross_bot.py` → `detect_cross_bot_mention()` |
| Chain Management | `src_v2/broadcast/cross_bot.py` → `ConversationChain` |
| Orchestrator | `src_v2/discord/orchestrator.py` |

### Detection Triggers

1. **Direct @mention:** `@Elena what do you think?`
2. **Name in text:** `I wonder what Elena would say...`
3. **Reply to bot message:** Replying to another bot's message

### Flow

```
Elena mentions @Dotty in broadcast channel
  → Dotty's CrossBotManager detects mention
  → Checks cooldowns, chain limits (max 4 turns default)
  → Probabilistic engagement (CROSS_BOT_RESPONSE_CHANCE)
  → Dotty responds, chain increments
  → After chain ends, cooldown applied
```

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `ENABLE_CROSS_BOT_CHAT` | `false` | Master switch (opt-in per bot) |
| `CROSS_BOT_MAX_CHAIN` | `5` | Max turns per conversation |
| `CROSS_BOT_RESPONSE_CHANCE` | `0.7` | Probability of responding |
| `CROSS_BOT_COOLDOWN_MINUTES` | `10` | Cooldown after chain ends |

### Memory Storage

Cross-bot messages are stored in **both** locations:

**1. Per-Bot Collection** (`whisperengine_memory_{bot_name}`):
```python
# Stored via memory_manager.add_message()
{
    "role": "human",  # or "ai" for bot's response
    "source_type": "gossip",
    "metadata": {
        "type": "gossip",
        "source_bot": "elena",
        "is_cross_bot": True
    }
}
```

**2. Shared Collection** (`whisperengine_shared_artifacts`):
Universe gossip events (life updates) are stored here with `eligible_recipients` for privacy filtering.

**Retrieval:** `get_gossip_for_bot()` aggregates from both sources during diary/dream generation.

---

## 6. Recommendation Engine (User Similarity)

**Purpose:** Find users with shared interests for social features

### Components

| Component | Location |
|-----------|----------|
| Engine | `src_v2/knowledge/recommendations.py` |
| Algorithm | Graph walk via Neo4j |

### Algorithm

Uses **structural similarity** (shared edges) rather than pre-computed scores:

```cypher
MATCH (u:User {id: $user_id})-[:DISCUSSED]->(t:Topic)<-[:DISCUSSED]-(other:User)
WHERE other.id <> $user_id
WITH other, count(DISTINCT t) as shared_count, collect(t.name) as topic_names
WHERE shared_count >= $min_shared
RETURN other.id as user_id, shared_count, topic_names
ORDER BY shared_count DESC
LIMIT $limit
```

### Serendipity Factor

10% chance to include a random active user (configurable):

```python
if random.random() < self.serendipity:
    random_user = await self._get_random_active_user(session, server_id, exclude)
    recommendations.append(SimilarUser(
        user_id=random_user,
        reason="serendipity",
        score=0.5
    ))
```

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `min_shared_topics` | `2` | Minimum shared topics (class default) |
| `serendipity` | `0.1` | Random user injection rate (class default) |

> **Note:** These are class-level defaults in `RecommendationEngine.__init__()`, not environment settings.

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INTERACTION                          │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    EVENT DETECTOR (detector.py)                  │
│    Detects: emotional spikes, life updates, topic discoveries   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                 UNIVERSE EVENT BUS (bus.py)                      │
│    Privacy check → Sensitive filter → User opt-out check        │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│              WORKER: run_gossip_dispatch (Redis Queue)           │
│    Trust check → Store in SharedArtifactManager                  │
└─────────────────────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┴───────────────────────┐
        ▼                                               ▼
┌───────────────────┐                      ┌───────────────────────┐
│  SHARED ARTIFACTS │                      │   UNIVERSE GRAPH      │
│     (Qdrant)      │                      │      (Neo4j)          │
│                   │                      │                       │
│ • Gossip          │                      │ • Planets/Channels    │
│ • Epiphanies      │                      │ • User-Character rels │
│ • Patterns        │                      │ • Topics discussed    │
└───────────────────┘                      │ • Familiarity scores  │
        │                                  └───────────────────────┘
        │                                               │
        └───────────────────────┬───────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    OTHER BOTS DISCOVER VIA:                      │
│  • Diary generation (get_gossip_for_bot)                         │
│  • Dream generation (semantic search)                            │
│  • Context building (planet awareness)                           │
│  • Cross-bot chat (direct @mentions)                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Privacy Enforcement Summary

| Layer | Mechanism | Enforcement |
|-------|-----------|-------------|
| Event Detection | Keyword filter | Sensitive topics blocked at source |
| Event Bus | User preferences | `share_with_other_bots` setting checked |
| Event Bus | Propagation limit | `depth > 1` events ignored |
| Gossip Dispatch | Trust check | FRIEND+ level required per bot |
| Shared Artifacts | Recipient filter | `eligible_recipients` field enforced |
| Graph Queries | Server scope | Optional server_id filtering |
| Recommendations | Trust threshold | Min trust for suggested users |

### Sensitive Topics (Never Shared)

```python
SENSITIVE_TOPICS = frozenset([
    "health", "medical", "doctor", "therapy", "medication", "diagnosis",
    "finance", "money", "debt", "salary", "income", "bankrupt",
    "relationship", "dating", "partner", "divorce", "breakup",
    "legal", "lawsuit", "arrest", "crime", "court",
    "secret", "private", "confidential", "don't tell",
])
```

---

## Debugging & Monitoring

### Useful Log Searches

```bash
# Gossip events
grep "gossip" logs/worker.log

# Cross-bot interactions
grep "CrossBot" logs/elena.log

# Universe events blocked
grep "Event blocked" logs/worker.log

# Shared artifact storage
grep "shared artifact" logs/worker.log
```

### Redis Inspection

```bash
# List all known bots
redis-cli KEYS "whisper:crossbot:bot:*"

# Check active chains
redis-cli KEYS "whisper:crossbot:chain:*"

# View chain state
redis-cli GET "whisper:crossbot:chain:{channel_id}"
```

### Neo4j Queries

```cypher
// Count cross-bot relationships
MATCH (c:Character)-[:KNOWS_USER]->(u:User)
RETURN c.name, count(u) as users_known

// Most discussed topics
MATCH (u:User)-[:DISCUSSED]->(t:Topic)
RETURN t.name, count(u) as discussers
ORDER BY discussers DESC
LIMIT 10
```

---

## Related Documentation

- [REF-032: Design Philosophy](REF-032-DESIGN_PHILOSOPHY.md) — Embodiment model approach
- [SPEC-E16: Feedback Loop Stability](../spec/SPEC-E16-FEEDBACK_LOOP_STABILITY.md) — Emergent behavior guardrails
- [ADR-003: Emergence Philosophy](../adr/ADR-003-EMERGENCE_PHILOSOPHY.md) — Pre-implementation checklist

---

## Origin

| Field | Value |
|-------|-------|
| Proposed By | Mark + Claude Opus 4.5 |
| Trigger | Code review and architecture documentation request |
| AI Contribution | Documentation synthesis from codebase analysis |
| Human Review | Pending |
