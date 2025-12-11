# SPEC-E33: Activity-Driven Polling (Universe → Daily Life)

**Document Version:** 1.0  
**Created:** December 11, 2025  
**Status:** ✅ Implemented  
**Priority:** 🟢 High  
**Dependencies:** SPEC-E31 (Daily Life Graph), Universe Manager

> ✅ **Emergence Check:** Instead of being told "watch these 3 channels," the bot looks at the whole universe, notices where activity is happening ("pheromone trails"), and decides where to go. This allows bots to naturally migrate to active communities without configuration.

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Holistic Architecture Review (Dec 11, 2025) |
| **Proposed by** | Mark + Claude |
| **Catalyst** | Realization that bots see the "whole universe" but were artificially constrained to hardcoded watch lists |
| **Key insight** | Activity IS the signal. Bots should be curiosity-driven explorers, not scheduled patrols. |

---

## Executive Summary

Currently, the **Daily Life Graph** (SPEC-E31) polls a hardcoded list of channels (`DISCORD_CHECK_WATCH_CHANNELS`) every 7 minutes. This is rigid and doesn't scale to multi-server deployments.

This spec proposes **Activity-Driven Polling**:
1.  **Perceive:** The bot queries the **Universe Manager** for "hot spots" (channels with recent activity) across all servers it's in.
2.  **Prioritize:** It scores these hot spots based on personality, relationships, and goals.
3.  **Engage:** It dynamically selects which channels to "visit" (poll) during this cycle.

**Result:** A bot that naturally follows the conversation, wherever it moves, without admin configuration.

---

## Problem Statement

### Current State
-   **Hardcoded Lists:** Admins must manually set `DISCORD_CHECK_WATCH_CHANNELS=123,456,789`.
-   **Blind Spots:** If a conversation erupts in a channel not on the list, the bot never sees it.
-   **Wasteful Polling:** The bot polls empty channels repeatedly if they are on the list.
-   **Single-Server Bias:** Hard to manage across multiple servers (requires massive config lists).

### Desired State
-   **Zero Config:** Bot discovers channels automatically.
-   **Dynamic Attention:** Bot focuses on where people are actually talking.
-   **Multi-Server Native:** Bot seamlessly handles 10+ servers, prioritizing the most relevant conversations.
-   **Personality Driven:** A "curious" bot might check new channels; a "shy" bot sticks to known ones.

---

## Architecture

### 1. The Signal (Universe Manager)

The `UniverseManager` (already running) tracks activity in Redis via `on_message`. We need to expose a query method:

```python
# src_v2/universe/manager.py

async def get_activity_signals(self, since_minutes: int = 15) -> List[ActivitySignal]:
    """
    Returns channels with activity in the last N minutes.
    Sorted by activity density (messages / minute).
    """
    # Query Redis/InfluxDB for recent message counts per channel
    # Return list of {channel_id, guild_id, message_count, topic_summary}
```

### 2. The Decision (Daily Life Scheduler)

Update the `DailyLifeScheduler` in `src_v2/discord/daily_life.py` to use dynamic selection instead of static lists.

**Old Logic:**
```python
channels_to_poll = settings.DISCORD_CHECK_WATCH_CHANNELS.split(",")
```

**New Logic:**
```python
# 1. Get signals from the universe
signals = await universe_manager.get_activity_signals(since_minutes=15)

# 2. Filter/Score signals (The "Curiosity" Step)
channels_to_poll = []
for signal in signals:
    # Always check "home" channels (optional config)
    if signal.channel_id in settings.HOME_CHANNELS:
        channels_to_poll.append(signal.channel_id)
        continue
        
    # Check active channels if they meet criteria
    if signal.message_count >= 3:
        channels_to_poll.append(signal.channel_id)

# 3. Cap the list (don't poll 100 channels at once)
channels_to_poll = channels_to_poll[:5]  # Max 5 channels per cycle
```

### 3. The Execution (Worker)

The worker logic (SPEC-E31) remains largely unchanged. It receives a snapshot of the selected channels and decides whether to act.

---

## Implementation Plan

### Phase 1: Universe Query (1 day)
-   [ ] Implement `UniverseManager.get_activity_signals()`
-   [ ] Ensure `on_message` is correctly populating the activity metrics (Redis/Influx)

### Phase 2: Scheduler Update (1 day)
-   [ ] Modify `DailyLifeScheduler.run_daily_life_cycle()`
-   [ ] Replace `DISCORD_CHECK_WATCH_CHANNELS` usage with dynamic discovery
-   [ ] Add `MAX_CHANNELS_PER_CYCLE` setting (default: 5) to prevent rate limit issues

### Phase 3: Tuning (1 day)
-   [ ] Tune the activity threshold (e.g., "at least 2 messages in 15 mins")
-   [ ] Verify bots don't get "distracted" by spam channels

---

## Future Expansion: "Curiosity Scoring"

In a later phase, we can make the selection even smarter by using the LLM to score the *metadata* of the activity before polling.

*   "Channel #gaming has 50 messages. Topic: Elden Ring."
*   Bot (Elena): "Not interested."
*   Bot (Marcus): "Ooh, gaming! I'll check it out."

For now (Phase 1), simple activity counts are sufficient.

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| **Rate Limits** | Cap `MAX_CHANNELS_PER_CYCLE` to 5. The 7-minute interval is already conservative. |
| **Spam Distraction** | Bots might be drawn to spam channels. **Mitigation:** Trust scores and spam detection (already in place) will prevent engagement even if polled. |
| **Missing Context** | Bot joins late. **Mitigation:** The snapshot includes the last 50 messages, so it gets full context immediately. |
