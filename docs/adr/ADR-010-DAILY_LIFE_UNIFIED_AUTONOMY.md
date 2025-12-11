# ADR-010: Unified Autonomous Behavior via Daily Life Graph

**Status:** ✅ Accepted  
**Date:** December 11, 2025  
**Deciders:** Mark Castillo

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Architecture simplification |
| **Proposed by** | Mark + Claude (collaborative debugging session) |
| **Catalyst** | Bot-to-bot conversation loops overnight, multiple overlapping trigger systems |
| **Key insight** | One polling-based path is simpler, more emergent, and prevents rapid-fire loops |

---

## Context

WhisperEngine had **three independent systems** for autonomous bot behavior:

1. **Lurk Detector** (real-time, keyword-based)
   - Triggered on every user message
   - Matched against `lurk_triggers.yaml` keywords
   - Free (regex), but rigid and prescribed

2. **Cross-Bot Chat** (real-time, mention-based)
   - Triggered when bots mentioned each other or replied
   - Redis-backed chain tracking with limits
   - Caused rapid-fire loops overnight (hundreds of messages)

3. **Daily Life Graph** (polling, LLM-scored)
   - 7-minute heartbeat
   - LLM scores message relevance to character interests
   - Naturally rate-limited by poll interval

**The problems:**
- Three systems could all fire on the same message
- Real-time triggers caused bot-to-bot loops
- Lurk keywords were **prescribed** (admin defines what's interesting)
- Maintenance burden: three codepaths to understand/tune

---

## Decision

**Consolidate all autonomous behavior into the Daily Life Graph.**

### Disabled Systems

| Flag | New Value | Effect |
|------|-----------|--------|
| `ENABLE_AUTONOMOUS_REPLIES` | `false` | Disables real-time lurk detection |
| `ENABLE_AUTONOMOUS_REACTIONS` | `false` | Disables real-time emoji reactions |
| `ENABLE_CROSS_BOT_CHAT` | `false` | Disables real-time bot-to-bot triggers |

### Retained Systems

| Flag | Value | Effect |
|------|-------|--------|
| `ENABLE_DAILY_LIFE_GRAPH` | `true` | 7-minute polling handles ALL autonomous decisions |
| `ENABLE_AUTONOMOUS_ACTIVITY` | `true` | Master switch for autonomous behavior |
| `ENABLE_AUTONOMOUS_POSTING` | `true` | Allows proactive posts in quiet channels |

### Direct Response Paths (Unchanged)

These still work immediately, no polling required:
- **DM** → Direct response
- **@mention** → Direct response
- **Reply to bot's message** → Direct response
- **Thread started by bot** → Direct response

---

## How Daily Life Graph Works

Every 7 minutes (`DISCORD_CHECK_INTERVAL_MINUTES`):

1. **Perceive**: Fetch recent messages from watched channels
2. **Plan**: LLM scores each message for relevance to character
   - Uses character personality, interests, goals
   - Threshold: `DISCORD_CHECK_RELEVANCE_THRESHOLD` (default 0.4)
   - Spontaneity gate: `DAILY_LIFE_SPONTANEITY_CHANCE` (default 0.6)
3. **Execute**: Generate reply/react/post based on decisions

### Interest Scoring vs Keyword Matching

| Aspect | Lurk (Disabled) | Daily Life (Active) |
|--------|-----------------|---------------------|
| Method | Keyword matching | LLM interest scoring |
| Cost | Free | ~$0.001/check |
| Flexibility | Rigid | Adaptive |
| Emergence | Prescribed | Emergent |
| Rate | Real-time | 7-minute polling |

The LLM asks: "Given this character's personality, how interesting is this message?" — this is more **emergent** than a curated keyword list.

---

## Tuning Knobs

Only three settings control all autonomous behavior:

| Setting | Default | Effect |
|---------|---------|--------|
| `DISCORD_CHECK_INTERVAL_MINUTES` | 7 | Poll frequency |
| `DISCORD_CHECK_RELEVANCE_THRESHOLD` | 0.4 | How interesting a message must be (0-1) |
| `DAILY_LIFE_SPONTANEITY_CHANCE` | 0.6 | Probability of acting when triggered |

**Simple.** Adjust these to tune chattiness.

---

## Consequences

### Positive

1. **No more loops**: 7-minute interval prevents rapid-fire bot-to-bot exchanges
2. **One path to debug**: All autonomous behavior flows through Daily Life Graph
3. **More emergent**: LLM decides what's interesting, not keyword lists
4. **Cleaner codebase**: Can eventually remove lurk detector and cross-bot code

### Negative

1. **Latency**: User messages not replied to instantly (max 7 min delay)
2. **LLM cost**: Each poll costs ~$0.001 (vs free keyword matching)
3. **Less "instant" personality**: Elena won't immediately pounce on "coral reef"

### Neutral

1. **Research value preserved**: Bot-to-bot conversations still happen, just paced
2. **Direct interactions unaffected**: @mentions, DMs, replies still instant

---

## Deprecated Features (To Be Removed)

These are now disabled and can be deleted in a future cleanup:

- `src_v2/discord/lurk_detector.py`
- `src_v2/broadcast/cross_bot.py`
- `characters/{name}/lurk_triggers.yaml` files
- Related settings: `ENABLE_AUTONOMOUS_REPLIES`, `ENABLE_AUTONOMOUS_REACTIONS`, `ENABLE_CROSS_BOT_CHAT`, `CROSS_BOT_*` settings

---

## Future Optimization: Event-Driven Activity Detection

**Status:** Proposed (not yet implemented)

Currently, the Daily Life Graph polls Discord API every 7 minutes to fetch recent messages. This works but is wasteful when channels are quiet.

### Optimization Idea

Since bots already receive every message via `on_message`, we could:

1. **Track activity in Redis** (in `on_message` handler):
   ```python
   await redis.hincrby(f"channel_activity:{channel_id}", "count", 1)
   await redis.hset(f"channel_activity:{channel_id}", "last_message_time", now)
   ```

2. **Check Redis before polling** (in Daily Life Graph):
   ```python
   for channel_id in watched_channels:
       activity = await redis.hgetall(f"channel_activity:{channel_id}")
       if int(activity.get("count", 0)) > 0:
           # Only now fetch and score messages
           messages = await fetch_recent_messages(channel_id)
           await score_and_maybe_respond(messages)
       # Reset counter
       await redis.delete(f"channel_activity:{channel_id}")
   ```

### Benefits
- **No API calls if nothing happened** — skip quiet channels entirely
- **Activity metadata for free** — already tracking for `server_monitor`
- **Smarter polling** — only score channels with new activity

### Trade-off
Still need to fetch message content to score it (unless we cache content in Redis too, but that adds complexity). The current polling approach is simple and works — this is a nice-to-have optimization.

---

## Future Direction: Curiosity-Driven Exploration

**Status:** Conceptual (aligns with emergence philosophy)

The current model uses a **hardcoded watch list** (`DISCORD_CHECK_WATCH_CHANNELS`). A more emergent approach: let bots **discover** where to look based on activity signals.

### The Pattern

Instead of "patrol these channels on a schedule", the bot could:

1. **Notice activity signals** — "There's a lot of activity in #general right now"
2. **Get curious** — "I wonder what's happening over there?"
3. **Go investigate** — Fetch recent messages, score interest
4. **Maybe join** — If interesting enough, chime in

This flips the model from **scheduled patrol** to **curiosity-driven exploration**.

### Integration with Universe Observation

The Universe Observation system (already running in `on_message`) tracks:
- Channel activity counts
- Topics being discussed
- User interaction patterns

**The Multi-Server Vision:**

Bots see the **whole universe** — multiple Discord servers, dozens of channels, hundreds of users. They shouldn't just patrol a hardcoded list. They should:

1. **Perceive** activity across ALL servers they're in
2. **Analyze** what's interesting based on personality, relationships, goals
3. **Decide** where to engage (not be told)
4. **Act** through the Daily Life Graph

```python
# Instead of hardcoded watched_channels:
active_channels = await universe_manager.get_active_channels(
    min_activity=5,  # At least 5 messages in last N minutes
    since=last_check_time
)

for channel in active_channels:
    # Bot "notices" the activity and scores interest
    interest = await llm.score_interest(
        channel=channel,
        personality=self.character,
        relationships=self.trust_scores,
        goals=self.active_goals
    )
    if interest > threshold:
        messages = await fetch_and_score(channel)
        ...
```

**Research Questions:**
- Will bots develop "favorite" channels organically?
- Will they form cross-server social graphs?
- Will curiosity-driven exploration lead to more natural engagement?

### Why This Is More Emergent

- **No channel config needed** — activity IS the signal
- **Personality-driven** — curious characters explore more
- **Stigmergic** — bots follow "pheromone trails" of activity
- **Natural** — like a person hearing laughter and wandering over to see what's funny

### Research Question

Does curiosity-driven exploration lead to more organic engagement than scheduled patrols? Worth observing if implemented.

---

## Related Documents

- `docs/spec/SPEC-E31-DAILY_LIFE_GRAPH.md` — Daily Life Graph specification
- `docs/spec/SPEC-C02-CHANNEL_LURKING.md` — **DEPRECATED** lurking spec
- `docs/spec/SPEC-E06-CHARACTER_TO_CHARACTER.md` — Bot-to-bot (now via Daily Life only)
- `docs/adr/ADR-006-FEATURE_FLAGS.md` — Feature flag philosophy
