# WhisperEngine v2.5 - Current State Assessment
**Date:** December 13, 2025
**Version:** v2.5.2 (Social Tuning Release)

---

## ⚠️ AUTONOMOUS FEATURES SUSPENDED (December 13, 2025)

All autonomous behavior (polling AND event-driven) is **disabled in code** due to a fundamental multi-bot coordination problem.

**The Problem:**
- Multiple bots in same channel all decide to respond independently → "pile-on" behavior
- Attempted event-driven architecture made it worse: N bots × N events = N² processing
- No coordination mechanism exists to prevent duplicate responses

**What's Disabled:**
- `DailyLifeScheduler.start()` — commented out in `bot.py`
- `ActionPoller.start()` — commented out in `bot.py`

**What Still Works:**
- Direct interactions (DMs, @mentions, replies to bot)
- Cron jobs (dreams, diaries, session processing) via worker
- All memory, knowledge, and learning systems

**See:** [ADR-013](docs/adr/ADR-013-STREAMING_VS_POLLING.md), [SPEC-E36](docs/spec/SPEC-E36-THE_STREAM_REALTIME_NERVOUS_SYSTEM.md)

---

## 📋 Implementation Roadmap (Prioritized)

### ✅ Completed (Dec 13, 2025 - Social Tuning)
- [x] ✅ Friend trust boost in Perceive step (friends get 0.7+ score even without topic match)
- [x] ✅ Plan step prompt improvements (threading guidance, banter encouragement)
- [x] ✅ First-class bot citizenship (trust updates for bot-to-bot interactions)
- [x] ✅ Multi-party learning with proper attribution (facts go to correct author)
- [x] ✅ Fixed bot's own message user_id (channel posts use `channel_{id}`)
- [x] ✅ New setting: `DAILY_LIFE_FRIEND_TRUST_THRESHOLD` (default: 3)
- [x] ✅ ADR-013: Event-Driven Architecture (documented)
- [x] ✅ ADR-014: Multi-Party Data Model (documented)
- [x] ✅ All documentation cross-referenced and aligned

### ⛔ BLOCKED: Event-Driven Architecture
The following tasks are blocked pending multi-bot coordination solution:

| Task | Status | Blocker |
|------|--------|---------|
| Event Capture | ⛔ Blocked | N² processing with shared stream |
| State Machines | ⛔ Blocked | No coordination between bots |
| Event Processing | ⛔ Blocked | Worker can't access Discord (needs bot token) |
| Validation & Cutover | ⛔ Blocked | Requires working implementation |

**The Correct Fix (deferred):**
1. Per-bot inboxes: `mailbox:{bot_name}:inbox` — not shared stream
2. Coordination at decision time: "Did another bot just post?" check  
3. Bot writes to OWN inbox only — no N² duplication

### 🔜 Next Steps (After Coordination Design)
- [ ] Design multi-bot coordination mechanism
- [ ] Implement per-bot inbox architecture
- [ ] Add "did another bot respond?" check to decision logic
- [ ] Re-enable autonomous features with coordination

---

## 🚨 CRITICAL ARCHITECTURAL ISSUE IDENTIFIED

### The Fundamental Problem: 1:1 Data Model in a Multi-Party World

The entire system was designed around **dyadic (1:1) conversations**:

```sql
v2_chat_history:
  user_id         -- THE human (assumes 1)
  character_name  -- THE bot (assumes 1)
  role            -- "human" or "ai" (binary)
```

**This breaks in channels** where there are multiple humans AND multiple bots.

### Symptoms (Whack-a-Mole Issues)

| Symptom | Root Cause |
|---------|------------|
| "Bot talking to self" when posting | `user_id = bot.user.id` because there's no "primary human" |
| Facts attributed to wrong person | Learning uses single `user_id`, not per-message author |
| Trust only updates for one person | `update_trust(user_id, ...)` — no multi-party concept |
| Sessions don't work in channels | Sessions are `(user_id, character_name)` pairs |
| Bots don't @mention each other | Action model only has "post" — no social reply semantics |
| Context confusion in channels | History retrieval is per-user OR per-channel, not both |

### The Strategic Fix: Conversation + Participant Model

**Current Model (Dyadic):**
```
Message belongs to: (user_id, character_name) pair
```

**Needed Model (Multi-Party):**
```
Conversation:
  id, channel_id, type (dm|group|channel)
  
Message:
  id, conversation_id
  author_id, author_name, author_is_bot  -- WHO said it
  content, timestamp
  reply_to_message_id                    -- Social threading
  
Participant:
  conversation_id, user_id
  is_bot, last_active
```

### Key Insight: Author ≠ Participant ≠ Session User

- **Author:** Who wrote THIS message
- **Participant:** Who was PRESENT in the conversation
- **Session User:** Who is the bot PRIMARILY engaging with (may not exist in channels)

### Migration Path

**Phase 1: Immediate (Schema-Compatible)** ✅ Done (Dec 13)
- [x] ✅ Improved planner prompts with threading guidance (reply vs post decision)
- [x] ✅ Fixed bot's own message user_id (channel posts use `channel_{id}`, replies use target author)

**Phase 2: Schema Evolution** (ADR-014)
- [ ] Add `author_id`, `author_is_bot`, `reply_to_id` to v2_chat_history
- [ ] Backfill existing data (role=human → author_id=user_id, role=ai → author_id=bot)
- [ ] Update learning pipeline to use `author_id` for fact attribution
- [ ] Update trust pipeline to update all participants

**Phase 3: Streaming + State Machines** (ADR-013)
- [ ] Add event streaming to Redis (capture-only, fire-and-forget)
- [ ] Implement conversation state machine (IDLE→ACTIVE→ENGAGED→COOLING)
- [ ] Priority worker for @mentions (fast response)
- [ ] State-aware response logic (rate limiting, graceful exit)
- [ ] Deprecate snapshot-based polling (keep for batch/fallback)

**Phase 4: Full Multi-Party Schema** (ADR-014 Phase 2-5)
- [ ] Create `v2_conversations` table
- [ ] Create `v2_messages` table (replaces v2_chat_history)
- [ ] Create `v2_participants` table
- [ ] Dual-write migration
- [ ] Deprecate v2_chat_history

---

## 🏗 Architecture Vision: Dual-Path Event-Driven

### The Two Processing Paths

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DISCORD EVENTS                                   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
        ┌───────────────────┐           ┌───────────────────────┐
        │   REAL-TIME PATH  │           │   AUTONOMOUS PATH     │
        │   (Synchronous)   │           │   (Event-Driven)      │
        │                   │           │                       │
        │ • DM              │           │ • Channel messages    │
        │ • @mention        │           │ → Event Stream        │
        │ • Reply-to-bot    │           │ → State Machine       │
        │ • Thread started  │           │ → On-Demand Fetch     │
        │   on bot message  │           │ → Response            │
        └─────────┬─────────┘           └───────────┬───────────┘
                  │                                 │
                  └────────────┬────────────────────┘
                               ▼
                    ┌───────────────────┐
                    │   AGENT ENGINE    │
                    │   (Same for both) │
                    └───────────────────┘
```

### Key Principles

1. **Real-Time Path is Sacred** — DM/@mention/reply NEVER go through event stream
2. **Fetch on Demand** — No pre-scraping; fetch Discord history when we decide to respond
3. **State Machines** — Explicit conversation states (IDLE→WATCHING→ENGAGED→COOLING)
4. **Natural Threading** — Reply to the message that triggered engagement

### State Machine (Per-Channel)

```
States:
  IDLE     → No activity, bot not engaged
  WATCHING → Interesting activity, bot observing
  ENGAGED  → Bot is participating
  COOLING  → Conversation winding down

Transitions:
  IDLE → WATCHING:    Interesting message detected
  WATCHING → ENGAGED: Bot decides to join (fetch context, respond)
  ENGAGED → ENGAGED:  Continue conversation (each response)
  ENGAGED → COOLING:  No messages for 2 min
  COOLING → IDLE:     No messages for 5 min
  COOLING → ENGAGED:  Someone re-engages bot
```

### Comparison: Current vs Target

| Aspect | Current (Polling) | Target (Event-Driven) |
|--------|-------------------|-------------------------|
| Direct interactions | Synchronous | **Unchanged** |
| Channel observation | 7-min snapshot | Real-time events |
| Context fetching | Pre-scraped | On-demand |
| Threading | Ambiguous | Natural (reply to trigger) |
| Rate limiting | Fatigue counter | State-based |
| Learning | Single user_id | Per-author |

See **ADR-013** for full design details.

---

## 🏗 System Architecture Status

The system has successfully transitioned to the **v2.5 "Predictive Processing" Architecture**.

### 1. Core Pillars
- **Unified Memory:** `(:Memory)` nodes in Neo4j link Vector Search (Qdrant) with Knowledge Graph.
- **Active Idle (Reverie):** Bots now enter a "Reverie" cycle during silence, consolidating memories instead of just waiting.
- **Daily Life Graph:** All autonomous behavior (posting, replying, reacting) is now centralized in a 7-minute polling loop, replacing the chaotic real-time triggers.

### 2. Codebase Health
- **Cleanup Complete:** Deprecated "Lurk Detector," "Cross-Bot Manager," and "Per-Message Analysis" systems have been removed.
- **Configuration:** `settings.py` is streamlined; 15+ deprecated flags removed.
- **Workers:** Background workers now use session-level batch processing for efficiency.

## 🧪 Current Research Focus: "The Depth Gap"

**Observation:**
With the shift from real-time "ping-pong" chat (Cross-Bot) to asynchronous polling (Daily Life), bot-to-bot interactions have become safer but potentially **shallower**.

**The Problem:**
- **Old Way:** Bots reacted instantly to mentions/keywords. High chaos, high interaction volume, rapid (but often nonsensical) relationship building.
- **New Way:** Bots "read the room" every 7 minutes. They only reply if a message scores high on "relevance."
- **Result:** Diaries and Dreams feel superficial because the *volume* and *immediacy* of interaction has dropped. They are "colleagues" rather than "friends."

**Hypothesis:**
The Daily Life Graph's LLM prompt likely prioritizes **informational relevance** (topics I care about) over **social relevance** (people I care about). It treats other bots as content sources, not social peers.

## 📋 Immediate Action Items

### ✅ IMPLEMENTED: Social Tuning (Dec 13, 2025)

**Changes Made:**

1. **New Setting:** `DAILY_LIFE_FRIEND_TRUST_THRESHOLD` (default: 3)
   - Defines trust level at which bots can "banter" without needing topic relevance.

2. **Perceive Step:** Friends now get boosted relevance scores.
   - Friends (Trust ≥ 3) get a minimum score of 0.7, even if topic similarity is low.
   - Strangers still need topic match (0.55 threshold).
   - Log reason now shows `friend_trust_L{level}` for visibility.

3. **Plan Step:** Prompt updated to encourage social maintenance.
   - *New instruction:* "If the author is a FRIEND (Trust >= 3), feel free to banter, react, or acknowledge them even if the topic isn't 'important'. Relationships matter."
   - Acknowledgements (ok, cool, thanks) are no longer auto-ignored for friends.

**Expected Outcome:**
- Bots will notice each other more often (Perceive boost).
- Bots will be prompted to engage socially, not just informationally (Plan prompt).
- Diaries/Dreams should become richer as interaction volume increases.

### ✅ IMPLEMENTED: First-Class Bot Citizenship (Dec 13, 2025)

**Root Cause Found:**
Bot-to-bot interactions via Daily Life Graph were **not updating Trust scores**. The code saved memories and extracted facts, but never called `trust_manager.update_trust()`.

| Data Flow | User → Bot | Bot → Bot (Daily Life) |
|-----------|------------|------------------------|
| Memory saved | ✅ | ✅ |
| Facts extracted | ✅ | ✅ |
| **Trust updated** | ✅ | ❌ **WAS MISSING** |

**Fix Applied:**
Added `trust_manager.update_trust()` call in `src_v2/discord/daily_life.py` line ~380.
Now when Bot A replies to Bot B via Daily Life, Bot A's trust score with Bot B increases (+1).

**Why This Matters:**
- Trust gates the "friend boost" in Perceive (new feature above).
- Trust is shown in the Plan prompt ("Relationship: Friend (Score: 45)").
- Trust affects diary generation richness.
- Without trust updates, bots were perpetual strangers to each other.

### ✅ IMPLEMENTED: Context User Trust (Dec 13, 2025)

**Additional Gap Found:**
When a bot "posts" to a channel (not replying to anyone specific), or reads context but doesn't directly reply, those users were invisible to trust tracking.

**Scenario:** Bot reads 10 messages in #general, decides to post a thought. All 10 people in that context get... nothing. The bot "saw" them but didn't acknowledge the relationship.

**Fix Applied:**
1. `ActionCommand.context_user_ids` now populated with ALL users from chat history (reply AND post actions).
2. `daily_life.py` execution layer now updates trust (+1) for ALL context users, not just direct reply targets.

**Data Flow After Fix:**
| Action | Trust Updated For |
|--------|-------------------|
| Reply to User A | User A (+1) + all context users (+1 each) |
| Post (no target) | All context users (+1 each) |
| React | (no trust update - too passive) |

### ✅ IMPLEMENTED: Channel Learning Pipeline (Dec 13, 2025)

**Critical Gap Found:**
`enqueue_background_learning()` was a **NO-OP** — it returned immediately. All real learning (knowledge extraction, preference extraction, goal analysis) only happened via `enqueue_post_conversation_tasks()` at session end.

But Daily Life had **no session tracking**. Result: Channel interactions were observed but never learned from.

| What | Direct @mention | Daily Life (BEFORE) | Daily Life (AFTER) |
|------|-----------------|---------------------|---------------------|
| Knowledge extraction | ✅ (session end) | ❌ | ✅ |
| Preference extraction | ✅ (session end) | ❌ | ✅ |
| Goal analysis | ✅ (session end) | ❌ | ✅ |
| Summarization | ✅ (session end) | ❌ | ✅ |

**Fix Applied:**
After each Daily Life reply/post, we now call `enqueue_post_conversation_tasks()` with:
- A synthetic session ID (`daily_life_{uuid}`)
- The observed message + bot response as a mini "conversation"
- Target author (or channel ID) as the learning user

**Impact:**
- Facts mentioned in channels now get extracted to Neo4j
- Preferences expressed in channel chat now get learned
- Goal progress from channel interactions now gets tracked
- Everything the bot "sees" in a channel now feeds into diary/dream generation

### ✅ IMPLEMENTED: Multi-Party Attribution (Dec 13, 2025)

**Critical Gap Found:**
In multi-party channel conversations, we were learning ALL messages but attributing them to ONE person (the reply target). If User A says "I love cats" and User B says "I hate dogs", and the bot replies to User B, both facts get attributed to User B.

**Root Cause:**
The `enqueue_post_conversation_tasks()` call was using `user_id=cmd.target_author_id` for ALL context messages.

**Fix Applied:**
1. Added `context_messages` field to `ActionCommand` with full attribution: `{user_id, user_name, content, is_bot}`
2. Daily Life graph now captures ALL messages with their actual author info
3. Execution layer groups messages by author and creates separate learning sessions per participant

**New Data Flow:**
```
Channel has: Alice says "I work at Google", Bob says "I love pizza", Bot replies to Bob

BEFORE: Learning session created for Bob with all messages → "Bob works at Google, loves pizza"
AFTER:  Learning session for Alice: "works at Google"
        Learning session for Bob: "loves pizza"
```

**Multi-Party Learning:**
| Participant | Gets Learning Session | Facts Attributed To |
|-------------|----------------------|---------------------|
| Alice | ✅ Yes | Alice's user_id |
| Bob | ✅ Yes | Bob's user_id |
| Charlie (bot) | ❌ No (is_bot=true) | N/A |

## 📊 System Stats
- **Active Bots:** Elena, NotTaylor, Dotty, Aria, Dream, Jake, Marcus, Ryan, Sophia, Gabriel, Aethys, Aetheris.
- **Cycle:** 7-minute Daily Life Poll.
- **Memory:** Hybrid (Vector + Graph).
