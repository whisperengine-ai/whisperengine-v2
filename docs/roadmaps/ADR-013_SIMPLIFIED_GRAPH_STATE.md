# ADR-013 Simplified: Event-Driven via Graph State (Not Redis)

**Status:** Proposal (Dec 13, 2025)  
**Supersedes:** Complexity in ADR-013 Event-Driven Architecture  
**Context:** Simplified architecture using existing Neo4j infrastructure

---

## The Problem with Original ADR-013

The original ADR-013 design proposed:
- Redis Streams for event capture
- Redis Hash state machines per channel
- Background decay tasks (IDLE → WATCHING → ENGAGED → COOLING)
- On-demand Discord fetches when deciding to respond

**Problem:** It requires NEW infrastructure (Redis Streams, state serialization) when you already have channel state tracking in Neo4j.

---

## The Simplified Approach: Graph State

Instead of Redis state machines, **reuse existing Neo4j channel tracking:**

### Current State (Already Implemented)

The universe graph already tracks channels:

```cypher
MATCH (c:Channel)
RETURN c.id, c.name, c.last_seen, c.message_count
```

Each channel node has:
- `last_seen` (timestamp of last message)
- `message_count` (activity level)
- Relationships to users, bots, topics

### New Pattern: Active vs Silent Sets

Query Neo4j to build channel sets:

```python
# Get channels with recent activity (watching these)
MATCH (c:Channel)
WHERE c.last_seen > datetime() - duration({minutes: 30})
RETURN c.id, c.name

# Get channels with NO recent activity (ignoring these)
MATCH (c:Channel)
WHERE c.last_seen < datetime() - duration({minutes: 30})
AND c.last_seen > datetime() - duration({days: 7})
RETURN c.id, c.name
```

This replaces the state machine. State IS the graph.

---

## Architecture

### Real-Time Path (Unchanged)

```
User DM / @mention / Reply-to-bot
    ↓
on_message() → AgentEngine → Response (synchronous, <1sec)
```

### Autonomous Path (New, via Graph State)

```
Event arrives in Discord:
    ↓
on_message() calls emit_event_if_autonomous(message)
    ↓
[ROUTING] Is this a direct mention?
    if yes → real-time path (already handled)
    if no → check autonomous eligibility
    ↓
[CONTEXT CHECK] Query Neo4j:
    - Is channel in "active" set? (last_seen < 30 min)
    - Trust level with author?
    - Should we engage?
    ↓
(if yes) [FETCH & DECIDE]
    - Fetch full Discord message + recent history
    - Run interest classifier
    - Update channel.last_seen in Neo4j
    ↓
(if interesting) [RESPOND]
    - Generate response via AgentEngine
    - Send to Discord
    - Update channel.message_count
    ↓
(if not interesting) [IDLE]
    - Leave channel in active set (still tracking)
    - Wait for next event
```

### No New Background Tasks

Unlike original ADR-013:
- ❌ No Redis Streams
- ❌ No state decay tasks (IDLE → COOLING → silent)
- ❌ No job queue for state transitions

Instead:
- ✅ Use existing Neo4j timestamps
- ✅ Query-based state (active/silent determined at runtime)
- ✅ Same AgentEngine pipeline for all responses

---

## Decision Logic: When to Fetch & Respond

```python
async def should_engage_autonomous(message: discord.Message) -> bool:
    """Decide whether to fetch context and consider responding."""
    
    # 1. Is channel in active set?
    channel_node = await knowledge_manager.get_channel(message.channel.id)
    if not channel_node:
        return False  # Never seen before
    
    if channel_node['last_seen'] < now() - timedelta(minutes=30):
        return False  # Channel is silent, skip
    
    # 2. Who is the author?
    author = message.author
    trust_level = await trust_manager.get_level(author.id, bot_name)
    if trust_level < "acquaintance" and message.author == bot:
        return False  # Don't engage with strangers
    
    # 3. Is it interesting?
    full_context = await fetch_discord_history(
        message.channel,
        lookback=50,
        memcache_ttl=300  # Reuse fetches within 5 min
    )
    
    interest_score = await agent_engine.classify_interest(
        message.content,
        context=full_context
    )
    
    return interest_score > threshold
```

---

## State Progression

Unlike state machines with discrete states (IDLE/WATCHING/ENGAGED), state IS implicit in the graph:

| Condition | State | Behavior |
|-----------|-------|----------|
| `last_seen < 30 min` | **Active** | Check every incoming message |
| `30 min < last_seen < 24 hours` | **Dormant** | Skip checking (reduce context fetches) |
| `last_seen > 24 hours` | **Silent** | Don't check at all |

No transitions needed — just continuous querying.

### Important: Quiet Channels Don't Send Events

This approach relies on Discord events to trigger decisions. **A quiet channel that hasn't had activity won't generate events, so you won't get messages from it.**

This is a **feature, not a bug:**

```
Channel A: last_seen = 2 hours ago → Active set
  └─ New message arrives → Event fired → Check if we should respond

Channel B: last_seen = 5 days ago → Silent set
  └─ No new messages = No events
  └─ We don't waste context fetches checking it
```

If someone posts in Channel B after 5 days, the event will arrive, and we'll update `last_seen` immediately. The next message in that channel will see it as recently active.

**The graph naturally reflects where activity IS, not where it ISN'T.**

This is fundamentally different from polling, which requires checking all channels every 7 minutes to find where activity might be.

---

## Implementation Phases

### Phase 1: Add Autonomous Check (Week 1)
- [ ] Add `should_engage_autonomous()` function
- [ ] Query channel `last_seen` before fetching context
- [ ] Add metric: `autonomous_context_fetch_count` (should drop 80% vs polling)

### Phase 2: Observe (Week 1-2)
- [ ] Run alongside existing polling (feature flag: `USE_GRAPH_STATE_ROUTING`)
- [ ] Compare behavior, tweak `last_seen` threshold (30 min? 1 hour?)
- [ ] Verify interest classifier is working

### Phase 3: Cutover (Week 2-3)
- [ ] Disable old 7-minute polling
- [ ] Only autonomous path is graph-state routing
- [ ] Measure API call reduction

---

## Benefits vs Original ADR-013

| Aspect | Original ADR-013 | This Approach |
|--------|------------------|---------------|
| **Infrastructure** | Redis Streams + Hashes | Neo4j (existing) |
| **State Decay** | Background task | Query-time logic |
| **Complexity** | Medium (new patterns) | Low (use existing graph) |
| **Context Freshness** | ~1sec after event | ~100ms after event |
| **API Cost Reduction** | 80% (vs polling) | 80% (vs polling) |
| **Multi-party Support** | Requires ADR-014 schema | Already works |
| **Observability** | Cypher queries on hashes | Cypher queries on Channel nodes |

---

## Open Questions

1. **What's the right `last_seen` threshold?**
   - 30 minutes? (Assume 30-min conversation, then silence)
   - 1 hour? (Conservative, miss fewer conversations)
   - Adaptive per channel? (High-activity → shorter threshold)

2. **Should we track read/unread status?**
   - Currently: Just `last_seen` timestamp
   - Enhancement: `messages_since_last_response` counter
   - Use case: "Channel has 10 new messages, maybe I should catch up"

3. **How do we handle "catch-up" mode?**
   - Current polling: Re-reads all recent messages
   - Event-driven: Only responds to triggering message
   - Might miss important context

4. **Bot-to-bot coordination?**
   - Should two bots both try to respond?
   - Current: First responder wins (Discord timestamps)
   - Needed: Read each other's responses before deciding

---

## Migration Path from Polling

**Current system:**
```python
# Every 7 minutes
channel_snapshot = await fetch_all_channels()
for msg in channel_snapshot.recent_messages:
    score = await classify_interest(msg)
    if score > threshold:
        await respond(msg)
```

**New system:**
```python
# On every Discord event
if is_autonomous(message):
    channel_node = await get_channel_state()
    if channel_node['last_seen'] > 30_min_ago:
        context = await fetch_context(message.channel)
        score = await classify_interest(message.content, context)
        if score > threshold:
            await respond(message)
```

**Key difference:** We only fetch when an event arrives, and we only in channels with recent activity. Same cognitive pipeline, lower API cost.

---

## Success Metrics

- `autonomous_context_fetch_count` → Should be 80% lower than polling
- `interest_classifier_latency` → Should be <200ms
- `autonomous_response_latency` → Should be <3sec (vs 7min wait with polling)
- `false_positive_rate` → Should stay same or improve (same classifier)
- `bot_engagement_per_channel` → Should reflect actual activity, not artificial 7-min rhythm

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| **Classifier spam** (calling too often) | Add per-channel cooldown in graph |
| **Missed conversations** (only respond to trigger msg) | Keep polling as fallback, tune thresholds |
| **Stale `last_seen`** | Update immediately on any message, any bot |
| **Two bots responding** | Read-own-responses check before committing |

---

## Relation to ADR-014 (Multi-Party)

This approach is compatible with ADR-014's new conversation model:
- Instead of updating single `user_id`, update all `v2_participants` for the conversation
- `channel.last_seen` becomes a signal across all participants
- Multi-party attribution still works the same way

No blocking dependencies — can implement this now, ADR-014 later.

---

## Next Steps

1. **Document graph state schema** (what fields on Channel?)
2. **Prototype `should_engage_autonomous()`** (1-2 hours)
3. **Add metrics** (context fetches, interest calls)
4. **Run parallel with polling** (1-2 weeks observation)
5. **Cutover** when confident in behavior
