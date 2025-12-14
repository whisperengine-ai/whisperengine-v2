# SPEC-E36: The Stream (Real-time Nervous System)

**Document Version:** 2.1
**Created:** December 11, 2025
**Updated:** December 13, 2025
**Status:** ⏸️ SUSPENDED - Architecture Redesign Required
**Priority:** 🔴 Blocked
**Dependencies:** Redis, Multi-Bot Coordination
**Superseded by:** ADR-013 (for Phase 2 architecture)

> ⚠️ **SUSPENDED:** Both polling and event-driven autonomous features are disabled as of December 13, 2025. See "Architecture Problem" section below.

---

## Architecture Problem (December 13, 2025)

### The Multi-Bot Coordination Failure

Both the polling system and the event-driven stream implementation suffer from the same fundamental flaw: **no coordination between multiple bots**.

**The Problem:**
```
1 Discord message arrives in #general (3 bots present: Elena, Aria, Dotty)

Polling approach:
  → Elena's 7-min poll fires → decides to respond
  → Aria's 7-min poll fires → decides to respond  
  → Dotty's 7-min poll fires → decides to respond
  = "Pile-on" - all 3 bots reply to same message

Event-driven approach (attempted):
  → Elena captures event to shared stream
  → Aria captures event to shared stream
  → Dotty captures event to shared stream
  = 3 duplicate events (N writes)
  
  → Each bot's consumer reads ALL events
  = 9 processing calls for 1 message (N² reads)
  = Even worse pile-on + wasted compute
```

**Root Cause:** Each bot makes independent decisions without knowing what other bots are doing. There's no coordination layer.

### Why We Disabled It

Rather than ship broken behavior (pile-on, duplicate processing), we disabled all autonomous features until the architecture is fixed.

**What's Disabled:**
- `DailyLifeScheduler` - 7-minute polling loop
- `ActionPoller` - Autonomous action execution
- Event capture to Redis stream
- StreamConsumer

**What Still Works:**
- Direct interactions (DMs, @mentions, replies)
- Cron jobs (dreams, diaries) via worker
- All memory/knowledge systems

### The Correct Design (ADR-013 + ADR-016)

ADR-013 specifies the fix:
1. **Per-bot inboxes:** `mailbox:{bot_name}:inbox` - not a shared stream
2. **Coordination at decision time:** Check "did another bot just post?" before responding
3. **Bot writes to OWN inbox only** - no N² duplication

[ADR-016: Worker Secrets Vault & Generic Workers](../adr/ADR-016-WORKER_SECRETS_VAULT.md) adds the missing piece:
1. **Config Vault:** Bot publishes secrets + LLM config to Redis (`vault:{bot}:*`)
2. **Generic Workers:** Any worker handles any bot (fetches config from vault)
3. **Discord REST API:** Workers send messages via REST (same token, no gateway conflict)
4. **Bot = Thin Gateway:** ~1ms per message (just `XADD` to inbox), no blocking
5. **Worker = Brain:** All LLM, memory, knowledge work offloaded to workers

This solves the "worker can't access Discord" blocker.

This requires significant refactoring and is deferred.

---

## Historical Context

### Phase 1: Hybrid Triggers (✅ IMPLEMENTED, ⏸️ DISABLED)
The initial implementation added **immediate triggers** for high-signal events:
- Trusted user (Level >= 4) messages
- Watchlist channel activity
- Still uses snapshot model underneath
- Debounce via Redis key

**Status:** Code exists but is disabled due to pile-on problem.

### Phase 2: Full Event-Driven (❌ FAILED IMPLEMENTATION)
Attempted to replace polling with Redis streams:
- ALL channel events → shared Redis stream
- StreamConsumer processes events

**Status:** Implementation was architecturally broken (N² processing). Rolled back.

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
