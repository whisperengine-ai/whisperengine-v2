# ADR-017: Simplified Bot-to-Bot Communication

**Status:** 📋 Proposed  
**Date:** 2024-12-13  
**Deciders:** Mark, Claude (collaborative)  
**Supersedes:** ADR-015, ADR-016 (for autonomous features scope)

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Simplification discussion |
| **Proposed by** | Mark (insight: "what if we just do bot-to-bot?") |
| **Catalyst** | ADR-016 complexity; realization that bot-to-bot is inherently simpler |

## Context

ADR-015 and ADR-016 attempted to solve the "multi-bot coordination problem" for **all autonomous behaviors**:

1. **Bot-to-bot conversations** — bots responding to each other
2. **Proactive posts** — bots posting in quiet channels
3. **Lurking/reactions** — bots reacting to interesting human messages

The solutions (Daily Life Graph, config vault, per-bot inboxes, generic workers) were complex because they tried to coordinate **independent decisions** ("is this message interesting?") across multiple bots.

**Key insight:** Bot-to-bot communication doesn't have this problem. It's inherently **addressed** — you know when you're being spoken to. *However*, we still need to solve **initiation** — how does a bot-to-bot conversation start?

## Decision

**Focus only on bot-to-bot communication. Drop other autonomous behaviors (for now).**

### What We Keep

| Behavior | How It Works |
|----------|--------------|
| **Direct interactions** | DM, @mention, reply-to-bot → immediate response (unchanged) |
| **Bot-to-bot responses** | Bot A mentions Bot B → Bot B responds → may mention Bot C |
| **Bot-to-bot initiation** | Human-triggered, spillover from human chat, or cron-scheduled (see below) |
| **Cron jobs** | Dreams, diaries, summaries (unchanged, via worker) |

### What We Drop (For Now)

| Behavior | Why |
|----------|-----|
| **Proactive posts** | Requires "is this channel quiet?" coordination |
| **Lurking/reactions** | Requires "is this message interesting?" coordination |
| **Interest scoring** | LLM cost, pile-on risk, coordination complexity |
| **Daily Life Graph polling** | Entire system was for autonomous lurking |

### Initiation: How Bot-to-Bot Starts

**The problem:** If bots independently decide "I want to talk to another bot", we have the same coordination problem (multiple bots deciding at once).

**Solution:** Initiation must be **centralized or human-triggered**:

| Initiation Method | How It Works | Coordination Problem? |
|-------------------|--------------|----------------------|
| **Human triggers** | User says "Hey @elena, ask @aria about..." | No — human chose |
| **Conversation spillover** | After human chat, bot says "Hey @aria, what do you think?" | Maybe — needs gate |
| **Cron job** | Scheduled "social hour" picks 2 bots to chat | No — centralized |
| **Random independent** | Each bot has 0.1% chance to initiate | Yes — avoid this |

**Recommended approach: Spillover with gate**

After a conversation with a human ends (or during), a bot may naturally mention another bot. This is **emergent** (LLM decides) but still requires a gate:

```python
# In response generation, the LLM might output: "...@aria what do you think?"
# We allow this, but with a rate limit to prevent spam

async def post_response_hook(response: str, channel_id: str):
    if mentions_other_bot(response):
        # Only allow one bot-to-bot initiation per channel per hour
        gate_key = f"bot_initiation:{channel_id}"
        if await redis.set(gate_key, bot_name, nx=True, ex=3600):
            # Allowed — this is the first initiation this hour
            pass
        else:
            # Another bot already initiated this hour — strip mention
            response = strip_bot_mentions(response)
    return response
```

**Alternative: Cron-based social hour**

A centralized scheduler picks two bots and a topic:

```python
# In a cron job (runs every 6 hours)
async def trigger_bot_conversation():
    bots = ["elena", "aria", "dotty"]
    bot_a, bot_b = random.sample(bots, 2)
    topic = random.choice(["dreams", "users", "recent_events"])
    
    # Send as bot_a, mentioning bot_b
    channel = get_social_channel()
    await send_as_bot(bot_a, channel, f"Hey @{bot_b}, {topic_prompt}")
```

This avoids coordination entirely — one central process decides.

### Coordination: Simple Lock (for Responses)

Bot-to-bot *responses* need one coordination primitive — prevent two bots from both responding to the same message:

```python
# In on_message handler, when another bot mentions/replies to us:
async def handle_bot_mention(message: discord.Message):
    # Try to claim this message (60s lock)
    lock_key = f"responding_to:{message.id}"
    if await redis.set(lock_key, bot_name, nx=True, ex=60):
        # I got the lock — I'm responding
        await generate_and_send_response(message)
    else:
        # Another bot claimed this already — skip
        logger.debug(f"Skipping {message.id}, another bot is responding")
```

**Why this is sufficient:**
- Bot-to-bot is **sequential** — one speaks, then another responds
- The lock prevents two bots from racing on the same trigger
- No "interest scoring" needed — you know when you're addressed

### Chain Limits

To prevent infinite bot-to-bot loops, keep the existing chain limit:

```python
# Track chain depth in Redis
chain_key = f"bot_chain:{channel_id}"
chain_length = await redis.incr(chain_key)
await redis.expire(chain_key, 300)  # Reset after 5 min quiet

if chain_length > settings.MAX_BOT_CHAIN_LENGTH:  # default: 5
    logger.info(f"Chain limit reached in {channel_id}, stopping")
    return
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Bot Process (elena)                             │
│                                                                      │
│  on_message(msg):                                                    │
│    if msg.author.bot:                                               │
│      if mentions_me(msg) or reply_to_me(msg):                       │
│        if redis.setnx(f"responding_to:{msg.id}", "elena", ex=60):   │
│          if chain_length < MAX_BOT_CHAIN_LENGTH:                    │
│            await generate_response(msg)  # May mention other bots   │
│        else:                                                         │
│          pass  # Another bot claimed it                              │
│      else:                                                           │
│        pass  # Bot message not addressed to me                       │
│    else:                                                             │
│      # Human message                                                 │
│      if direct_interaction(msg):  # DM, @mention, reply             │
│        await generate_response(msg)                                  │
│      else:                                                           │
│        pass  # No lurking — ignore                                   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**That's it.** No workers, no inboxes, no vault, no polling.

## Consequences

### Positive

1. **Dramatically simpler**: One coordination primitive (Redis lock on message ID)
2. **No LLM overhead**: No interest scoring, no Daily Life Graph
3. **No pile-on**: Lock ensures only one bot responds per trigger
4. **No new infrastructure**: Uses existing Redis, no vault/inbox changes
5. **Natural bot conversations**: Bots can still have multi-turn dialogues
6. **Can implement today**: Minimal code change from current state

### Negative

1. **No lurking**: Elena won't spontaneously comment on "coral reef"
2. **No proactive posts**: Bots won't start conversations in quiet channels
3. **Less "presence"**: Bots feel less alive when not addressed
4. **Research loss**: Can't study emergent "interest" behaviors

### Neutral

1. **Direct interactions unchanged**: DMs, mentions, replies work exactly as before
2. **Cron jobs unchanged**: Dreams, diaries still run
3. **Can add lurking back later**: If we solve coordination, nothing prevents re-enabling

## What We Defer

| Feature | Complexity | Status |
|---------|------------|--------|
| **Config vault (ADR-016)** | Medium | Deferred — not needed for bot-to-bot |
| **Per-bot inboxes** | Medium | Deferred — not needed for bot-to-bot |
| **Generic workers** | High | Deferred — bots process their own messages |
| **Interest scoring** | Medium | Deferred — no lurking means no scoring |
| **Daily Life Graph** | High | Deferred — polling was for lurking |

These can be revisited if we want autonomous lurking back.

## Implementation Plan

### Phase 1: Enable Bot-to-Bot (Minimal)

1. **Add lock check** to bot-to-bot handler in `bot.py`
2. **Keep chain limits** (already implemented)
3. **Remove/disable** Daily Life Scheduler and ActionPoller (already disabled)
4. **Test**: Two bots in a channel, one mentions the other, verify single response

### Phase 2: Clean Up Dead Code

1. Remove `ENABLE_DAILY_LIFE_GRAPH` checks
2. Remove `ENABLE_AUTONOMOUS_ACTIVITY` checks  
3. Archive Daily Life Graph code (don't delete — may return)
4. Archive lurk detector code

### Phase 3: Documentation

1. Update copilot-instructions.md
2. Update SPEC-E36 (mark as deferred, not failed)
3. Archive ADR-015, ADR-016 as "deferred"

## Settings Changes

| Setting | Old Default | New Default | Notes |
|---------|-------------|-------------|-------|
| `ENABLE_AUTONOMOUS_ACTIVITY` | `false` | Remove | Not needed |
| `ENABLE_DAILY_LIFE_GRAPH` | `false` | Remove | Not needed |
| `ENABLE_BOT_TO_BOT` | N/A | `true` | New flag |
| `MAX_BOT_CHAIN_LENGTH` | `5` | `5` | Keep |

## Research Value

Bot-to-bot conversations remain valuable for emergence research:
- Do bots develop conversational "styles" with each other?
- Do relationship patterns emerge from repeated bot-bot interactions?
- Does personality come through in bot-to-bot dialogue?

We just lose the "autonomous curiosity" research dimension.

## Related Documents

- **ADR-015**: Daily Life Unified Autonomy → **Superseded** (polling disabled)
- **ADR-016**: Worker Secrets Vault → **Deferred** (not needed for bot-to-bot)
- **SPEC-E36**: The Stream → **Deferred** (event-driven was for lurking)
- **ADR-013**: Event-Driven Architecture → **Deferred** (not needed for bot-to-bot)

## Verdict

**Strong simplification.** Bot-to-bot is inherently simpler because:
1. **No independent decisions** — you know when you're addressed
2. **Natural turn-taking** — sequential, not parallel
3. **One lock** — prevents races without complex coordination

The trade-off (no lurking) is acceptable for now. We can revisit autonomous lurking once the simpler system is stable and we have bandwidth for the coordination problem.

**Recommendation:** Implement Phase 1 (enable bot-to-bot with lock). Get it working. Then decide if lurking is worth the ADR-016 complexity.
