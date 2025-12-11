# SPEC-E36: The Stream (Real-time Nervous System)

**Document Version:** 1.0
**Created:** December 11, 2025
**Status:** 📋 Proposed
**Priority:** 🟡 Medium
**Dependencies:** Redis

> ✅ **Emergence Check:** Responsiveness is a prerequisite for social emergence. If the bot takes 7 minutes to notice a joke, the moment is lost. This feature enables the *timing* necessary for emergent social dynamics.

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
