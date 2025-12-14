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

**Key insight:** Bot-to-bot *responses* don't have the coordination problem — you know when you're being spoken to. But bot-to-bot *initiation* **is** the autonomous posting problem.

## Decision

**Enable bot-to-bot responses (first-class, full pipeline). Defer autonomous initiation.**

### What We Keep

| Behavior | How It Works |
|----------|--------------|
| **Direct interactions** | DM, @mention, reply-to-bot → immediate response (unchanged) |
| **Bot-to-bot responses** | Bot A mentions Bot B → Bot B responds (full pipeline, first-class) |
| **Human-triggered bot-to-bot** | Human mentions two bots or asks one about the other |
| **Cron jobs** | Dreams, diaries, summaries (unchanged, via worker) |

### What We Drop (For Now)

| Behavior | Why |
|----------|-----|
| **Autonomous bot-to-bot initiation** | IS the autonomous posting problem |
| **Proactive posts** | Requires "is this channel quiet?" coordination |
| **Lurking/reactions** | Requires "is this message interesting?" coordination |
| **Interest scoring** | LLM cost, pile-on risk, coordination complexity |
| **Daily Life Graph polling** | Entire system was for autonomous lurking |

### The First-Class Citizen Problem

**Core principle (from copilot-instructions.md):** Bots are first-class citizens. Their autonomous actions must use the **same processing flow** as human messages. No special-case code.

This creates a hard constraint:

| If we want... | Then we need... |
|---------------|-----------------|
| Bot A responds to Bot B | Bot A processes Bot B's message through full pipeline ✅ |
| Bot A *initiates* conversation with Bot B | Bot A decides autonomously to post, which requires... autonomous posting |

**The honest truth:** First-class bot-to-bot initiation **is** autonomous posting. If a bot can independently decide "I want to talk to Aria," that's the same coordination problem as "I want to post about coral reefs."

### What This Means

We have two options:

**Option 1: Response-only bot-to-bot (simpler, but limited)**
- Bots can only respond when addressed (by humans OR other bots)
- Initiation must come from humans: "Hey @elena, what do you think @aria would say?"
- No autonomous initiation = no coordination problem
- **Trade-off:** Bot-to-bot only happens when humans start it

**Option 2: Full autonomous (first-class, but complex)**
- Bots can autonomously decide to post (which may mention other bots)
- This decision goes through the full cognitive pipeline
- Requires solving the coordination problem (ADR-016 complexity)
- **Trade-off:** We're back to the hard problem we deferred

### Decision: Response-Only (For Now)

We choose **Option 1** — bots respond to each other, but don't autonomously initiate.

**Why this is acceptable:**
- Human-triggered bot-to-bot still produces emergent conversations
- The responding bot uses the **full pipeline** (first-class citizen)
- We're not creating special-case code — just not enabling autonomous posting
- We can add autonomous initiation later when we solve coordination

**What "response-only" looks like:**
1. Human says: "Hey @elena, have you talked to @aria about dreams lately?"
2. Elena responds (full pipeline), her response mentions Aria
3. Aria sees the mention, responds (full pipeline)
4. Conversation continues naturally

The bots are still first-class — they process messages the same way regardless of whether the author is human or bot. We're just not giving them the ability to start conversations unprompted.

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

## ⚠️ Prerequisite: Multi-Party Data Model (ADR-014)

**Critical realization:** Before implementing bot-to-bot properly, we need the right data schema.

### The Problem with Current Schema

The current `v2_chat_history` assumes 1:1 conversations:
- `user_id` = THE human
- `character_name` = THE bot  
- `role` = "human" or "ai"

This breaks for channel conversations with multiple bots and humans:

| Problem | Symptom |
|---------|---------|
| Who said what? | `author_id` doesn't exist — can't attribute correctly |
| Bot talking to bot | Both messages have `role = "ai"` — which bot? |
| Learning from bot messages | Facts get attributed to wrong entity |
| Trust updates | Only one `user_id` per conversation — can't track multi-party |

### Why ADR-014 Must Come First

If we implement bot-to-bot responses now:
1. Bot A mentions Bot B → Bot B responds
2. **But how do we store Bot B's message?** `user_id` = Bot A? `role` = "ai"? Which "ai"?
3. **How do we learn from the conversation?** Facts attributed to whom?
4. **How do we build context for Bot C joining?** Our schema can't represent this.

### The Correct Order

```
ADR-014 (Schema)  →  ADR-017 (Bot-to-Bot)  →  ADR-016/013 (Autonomous)
     │                      │                        │
     │                      │                        │
Multi-party storage    Response-only            Full autonomy
  author_id             Simple lock              Coordination
  is_bot flag           Chain limits             Interest scoring
  conversation_id       First-class              Proactive posts
```

**Minimum viable ADR-014 for ADR-017:**
- Add `author_id` to messages (who wrote this)
- Add `author_is_bot` flag (human or bot?)
- Keep existing tables (non-breaking migration)

This lets us properly store and reason about bot-to-bot conversations.

## What We Defer

| Feature | Complexity | Status |
|---------|------------|--------|
| **Multi-party schema (ADR-014 Phase 1)** | Medium | **PREREQUISITE — do first** |
| **Config vault (ADR-016)** | Medium | Deferred — not needed for bot-to-bot |
| **Per-bot inboxes** | Medium | Deferred — not needed for bot-to-bot |
| **Generic workers** | High | Deferred — bots process their own messages |
| **Interest scoring** | Medium | Deferred — no lurking means no scoring |
| **Daily Life Graph** | High | Deferred — polling was for lurking |
| **Autonomous initiation** | High | Deferred — IS the autonomous posting problem |

## Revised Implementation Plan

### Phase 0: Schema Foundation (ADR-014 Phase 1) ⬅️ DO FIRST

1. **Add `author_id`** to `v2_chat_history` (who wrote the message)
2. **Add `author_is_bot`** boolean flag
3. **Add `reply_to_id`** for threading (optional but helpful)
4. **Backfill** existing data:
   - `role = 'human'` → `author_id = user_id`, `author_is_bot = false`
   - `role = 'ai'` → `author_id = bot_user_id`, `author_is_bot = true`
5. **Update write paths** to populate new fields

**Time estimate:** 1-2 days

### Phase 1: Enable Bot-to-Bot Responses

1. **Add lock check** to bot-to-bot handler in `bot.py`
2. **Use `author_id`** to properly store bot messages
3. **Keep chain limits** (already implemented)
4. **Test**: Two bots in a channel, one mentions the other, verify single response with correct attribution

### Phase 2: Update Learning/Trust Pipelines

1. **Fact extraction** uses `author_id` (learn from correct speaker)
2. **Trust updates** use `author_id` (update relationship with correct party)
3. **Context building** properly identifies speakers

### Phase 3: Clean Up Dead Code

1. Archive Daily Life Graph code
2. Archive lurk detector code
3. Update documentation

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

- **ADR-014**: Multi-Party Data Model → **PREREQUISITE** (do first)
- **ADR-015**: Daily Life Unified Autonomy → **Superseded** (polling disabled)
- **ADR-016**: Worker Secrets Vault → **Deferred** (not needed for bot-to-bot)
- **SPEC-E36**: The Stream → **Deferred** (event-driven was for lurking)
- **ADR-013**: Event-Driven Architecture → **Deferred** (not needed for bot-to-bot)

## Verdict

**Strong simplification, but schema first.**

The insight is correct: bot-to-bot responses are simpler than autonomous initiation. But we can't implement them properly without fixing the data model.

**Correct order:**
1. **ADR-014 Phase 1** (add `author_id`, `author_is_bot`) — 1-2 days
2. **ADR-017 Phase 1** (bot-to-bot responses with lock) — 1 day
3. **Observe** what emerges from bot-to-bot conversations
4. **Later**: Decide if autonomous initiation is worth ADR-016 complexity
