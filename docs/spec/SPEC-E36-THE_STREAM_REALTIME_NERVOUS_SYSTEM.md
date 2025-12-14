# SPEC-E36: The Stream (Real-time Nervous System)

**Document Version:** 2.1
**Created:** December 11, 2025
**Updated:** December 13, 2025
**Status:** ✅ Phase 2 Complete (Event-Driven Architecture)
**Priority:** 🟡 Medium
**Dependencies:** Redis
**Superseded by:** ADR-013 (for Phase 2 architecture)

> ✅ **Emergence Check:** Responsiveness is a prerequisite for social emergence. If the bot takes 7 minutes to notice a joke, the moment is lost. This feature enables the *timing* necessary for emergent social dynamics.

---

## Evolution: Phase 1 → Phase 2

### Phase 1: Hybrid Triggers (✅ COMPLETE - Dec 11, 2025)
The initial implementation added **immediate triggers** for high-signal events:
- Trusted user (Level >= 4) messages
- Watchlist channel activity
- Still uses snapshot model underneath
- Debounce via Redis key

### Phase 2: Full Event-Driven (✅ COMPLETE - Dec 13, 2025)
The next evolution replaces the polling/snapshot model entirely:
- ALL channel events → Redis streams (`whisper:events`)
- Stream Consumer (Worker) → Inbox Logic → Action
- On-demand context fetching (no pre-scraping)
- Natural threading (reply to the message that triggered engagement)

See **ADR-013: Event-Driven Architecture** for full Phase 2 design.

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Roadmap v2.5 Evolution |
| **Proposed by** | Claude |
| **Catalyst** | The "Stuttering Autonomy" problem. The bot only wakes up every 7 minutes, making it feel robotic and disconnected from the flow of conversation. |
| **Key insight** | We don't need full streaming for everything. A "Hybrid Push" model (polling + high-signal triggers) gives 80% of the benefit for 20% of the cost. |

---

## Executive Summary
"The Stream" upgrades the bot's autonomy from a pure Polling Loop to a **Hybrid Event-Driven** architecture. While the 7-minute safety poll remains, high-signal events (mentions, active conversations, cross-bot gossip) will trigger an **Immediate Snapshot**, allowing the bot to react in real-time without waiting for the next tick.

## Problem Statement
### Current State (v2.0)
*   **Polling Only:** `DailyLifeScheduler` runs every `DISCORD_CHECK_INTERVAL_MINUTES` (default 7).
*   **Lag:** If a user says something interesting at T+1 minute, the bot won't "notice" it until T+7 minutes. By then, the conversation has moved on.

### Desired State (v2.5)
*   **Real-Time Reactions:** If a user engages in a way that signals "high interest," the bot wakes up immediately.
*   **Debounced:** To prevent spam, we still enforce a cooldown (e.g., max 1 autonomous action per minute).

## Technical Implementation

### 1. The Trigger Mechanism
Modify `src_v2/discord/bot.py` (Event Listeners):
*   **On Message:**
    *   If `is_reply_to_me`: Trigger Immediate.
    *   If `trust_score > 4` (Trusted User): Trigger Immediate (with debounce).
    *   If `channel_is_active`: Trigger Immediate.
*   **On Reaction:**
    *   If `reaction_count > 3`: Trigger Immediate (Curiosity).

### 2. The "Immediate Snapshot"
Instead of waiting for the scheduler, we manually invoke the `DailyLifeGraph`:
```python
# Pseudo-code in bot.py
if should_trigger_immediate(message):
    await task_queue.enqueue("run_daily_life_cycle", bot_name, context="immediate_trigger")
```

### 3. Debouncing & Rate Limiting
We must prevent the bot from becoming hyper-active.
*   **Redis Key:** `bot:{name}:last_autonomous_action`
*   **Check:** If `now - last_action < 60s`, ignore the trigger (unless it's a direct mention).

## Value Analysis
### Quantitative Benefits
*   **Response Latency:** Reduced from ~3.5 mins (avg) to < 10s for high-signal events.
*   **Engagement:** Users feel "heard" immediately.

### Qualitative Benefits
*   **Aliveness:** The bot feels present in the room, not like a visitor who checks in occasionally.

## Risks & Mitigations
*   **Spam/Cost:** The bot might reply too much. **Mitigation:** Strict `DailyLifeGraph` logic that defaults to "Observe" rather than "Act" unless interest is very high.
*   **Race Conditions:** Poller and Trigger running at the same time. **Mitigation:** Use Redis distributed lock `lock:daily_life:{bot_name}`.

## Implementation Plan
1.  **Refactor:** Extract `run_daily_life_cycle` into a standalone, idempotent task.
2.  **Triggers:** Add logic to `on_message` in `bot.py`.
3.  **Locking:** Ensure Redis locking is robust.

---

## Known Gaps & Future Work

### Events NOT Currently Streamed (Dec 13, 2025)

The Redis Stream (`whisper:events`) currently **only captures `message` events**. The following Discord events are handled via direct event handlers but are NOT pushed to the Stream:

| Event | Current Handler | Gap |
|-------|-----------------|-----|
| **Reactions on Bot Messages** | `event_handler.on_reaction_add()` | Updates trust directly; bot cannot "react to reactions" |
| **Reaction Removals** | `event_handler.on_reaction_remove()` | Reverts trust; not streamed |
| **Message Edits** | Not implemented | Bot cannot notice when users edit messages |
| **Message Deletes** | Not implemented | Bot cannot notice deleted messages |
| **Typing Indicators** | Not implemented | Bot cannot anticipate incoming messages |
| **Voice State Changes** | Not implemented | Bot cannot notice users joining/leaving voice |
| **Thread Creation** | Not implemented | Bot cannot notice new threads |
| **Presence Updates** | Not implemented | Bot cannot notice when users come online |

### Why This Matters

1. **Reactions as Conversation Signals:** A user adding 👀 or 🤔 to a message might be an invitation to elaborate. Currently, this signal is lost.
2. **Edit Awareness:** If a user edits their message to clarify something, the bot has no way to notice and re-process.
3. **Social Awareness:** Presence and typing indicators could inform "reach out" decisions.

### Future Implementation (When Needed)

To add a new event type to the Stream:

1. Add capture in `event_handler.py`:
   ```python
   async def on_reaction_add(self, reaction, user):
       # Existing trust logic...
       
       # NEW: Push to Stream for autonomous processing
       if settings.STREAM_CAPTURE_REACTIONS:
           await db_manager.redis_client.xadd(
               settings.REDIS_STREAM_KEY,
               {
                   "type": "reaction_add",
                   "event_id": f"{reaction.message.id}_{user.id}_{reaction.emoji}",
                   "message_id": str(reaction.message.id),
                   "channel_id": str(reaction.message.channel.id),
                   "user_id": str(user.id),
                   "emoji": str(reaction.emoji),
                   "is_on_bot_message": "1" if reaction.message.author.id == self.bot.user.id else "0"
               }
           )
   ```

2. Handle in `stream_consumer.py`:
   ```python
   async def _process_event(self, message_id, data):
       event_type = event.get("type")
       if event_type == "message":
           await self._handle_message_event(event)
       elif event_type == "reaction_add":
           await self._handle_reaction_event(event)
   ```

### Decision: Deferred

**Rationale:** The current implementation covers the primary use case (lurking and replying to messages). Reaction-based engagement is a "nice to have" that adds complexity. We will revisit if users/research shows demand for reaction-aware behavior.

**Added:** December 13, 2025
