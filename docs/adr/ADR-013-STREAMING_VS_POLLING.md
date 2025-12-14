# ADR-013: Event-Driven Architecture with State Machines

**Status:** ⏸️ Deferred - Implementation Attempt Failed  
**Date:** December 13, 2025 (Revised)  
**Last Updated:** December 13, 2025 (Implementation suspended, polling also disabled)
**Deciders:** Mark, Claude (collaborative)

---

## ⚠️ Implementation Status (December 13, 2025)

### What Happened

We attempted to implement the event-driven architecture (Phase 2 of SPEC-E36) but the implementation was **architecturally broken**:

1. **Shared Stream Problem:** All N bots wrote to a single `whisper:events` stream, causing N duplicate events per message
2. **N² Processing:** Each bot's StreamConsumer read ALL events, resulting in N² processing calls
3. **Worker Discord Access:** StreamConsumer was moved to bot process because worker lacks `DISCORD_TOKEN`, defeating the purpose of backend offloading
4. **Pile-On Unchanged:** No coordination mechanism was added, so multiple bots still responded to the same message

### Current State

**ALL autonomous features are disabled:**
- `DailyLifeScheduler.start()` — commented out
- `ActionPoller.start()` — commented out
- Event capture to stream — removed
- StreamConsumer — removed from bot

**Bots only respond to direct engagement** (DMs, @mentions, replies). Cron jobs (dreams, diaries) still run via worker.

### The Correct Design

This ADR's design is correct in principle:
- **Per-bot inboxes:** `mailbox:{bot_name}:inbox` (not shared stream)
- **Coordination at decision time:** "Did another bot just post?" check
- **Bot writes to OWN inbox only**

But implementation requires more careful work than was done.

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Architecture review during Daily Life Graph debugging |
| **Proposed by** | Mark (vision), Claude (design) |
| **Catalyst** | Threading ambiguity in polling; need for natural conversation flow |

## Context

### Current Architecture: Three Paths

WhisperEngine currently has THREE processing paths, but they're not cleanly separated:

```
1. REAL-TIME PATH (Synchronous)
   DM / @mention / Reply-to-bot → on_message → AgentEngine → Response
   
2. POLLING PATH (Async, 7-min)
   Scheduler → Snapshot channels → Score → Plan → Execute
   
3. BATCH PATH (Background)
   Session end → Summarization, Learning, Diary
```

### Problems with Current Design

| Problem | Root Cause |
|---------|------------|
| Threading ambiguity | Polling reconstructs context from stale snapshots |
| "Should I reply to A or B?" | Both messages are 5 min old in snapshot |
| Wasteful scraping | Pre-fetches messages that may never be needed |
| Real-time path buried | Mixed with polling logic in `on_message` |
| State not explicit | "Am I engaged?" logic scattered across code |

### Key Insight from Mark

**"Fetch on demand, not pre-scrape."** Instead of snapshotting channels every 7 minutes, the bot should:
1. Receive event notification
2. Decide if interested (cheap, no context needed)
3. If interested → fetch context from Discord on demand
4. Respond with full context

This is more efficient AND more natural.

### Why Inbox/Outbox > Fixed Polling

The 7-minute polling was pragmatic — it worked, kept costs low, gave bots a heartbeat. But it's fundamentally a **fixed rhythm** in a world that needs **adaptive rhythm**:

| Aspect | Polling (7-min) | Inbox/Outbox |
|--------|-----------------|--------------|
| **DM arrives** | Wait 0-7 min | Process immediately |
| **Busy channel** | Still just one check | Process priority queue |
| **Quiet channel** | Wasted check | Nothing in inbox = do nothing |
| **Conversation heats up** | Can't accelerate | Natural pacing, faster engagement |
| **Friend messages** | Same priority as stranger | Route to priority inbox |
| **Cost model** | Fixed cost per cycle | Cost proportional to activity |

**The Mailbox Analogy:**
- **Polling** = Check your mailbox every 7 minutes whether you expect mail or not
- **Inbox** = Doorbell rings when something arrives; you decide when to check the pile

**The Daily Life Graph doesn't change.** It's still Perceive→Plan→Execute. Only the *trigger* changes — from "cron woke me up" to "something's in my inbox." The ant brain stays the same; only the sensory input changes.

## Decision: Dual-Path with Shared State

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DISCORD EVENTS                                   │
│  (DM, @mention, reply, channel message, reaction, etc.)                 │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
        ┌───────────────────┐           ┌───────────────────────┐
        │   REAL-TIME PATH  │           │   AUTONOMOUS PATH     │
        │   (Synchronous)   │           │   (Event-Driven)      │
        │                   │           │                       │
        │ • DM              │           │ • Channel messages    │
        │ • @mention        │           │ • Reactions           │
        │ • Reply-to-bot    │           │ • Presence changes    │
        │ • Thread started  │           │                       │
        │   on bot message  │           │                       │
        └─────────┬─────────┘           └───────────┬───────────┘
                  │                                 │
                  │                                 ▼
                  │                     ┌───────────────────────┐
                  │                     │   EVENT CAPTURE       │
                  │                     │   (Redis Stream)      │
                  │                     │   • Fire-and-forget   │
                  │                     │   • Metadata only     │
                  │                     └───────────┬───────────┘
                  │                                 │
                  │                                 ▼
                  │                     ┌───────────────────────┐
                  │                     │   STATE MACHINE       │
                  │                     │   (Redis Hash)        │
                  │                     │   • Per-conversation  │
                  │                     │   • IDLE/ACTIVE/etc   │
                  │                     └───────────┬───────────┘
                  │                                 │
                  │                                 ▼
                  │                     ┌───────────────────────┐
                  │                     │   DECISION: ENGAGE?   │
                  │                     │   • Check state       │
                  │                     │   • Check interest    │
                  │                     │   • Rate limit        │
                  │                     └───────────┬───────────┘
                  │                                 │
                  │                        (if yes) │
                  │                                 ▼
                  │                     ┌───────────────────────┐
                  │                     │   FETCH CONTEXT       │
                  │                     │   (On-Demand)         │
                  │                     │   • Discord API       │
                  │                     │   • Memory/Knowledge  │
                  │                     └───────────┬───────────┘
                  │                                 │
                  ▼                                 ▼
        ┌─────────────────────────────────────────────────────────┐
        │                    AGENT ENGINE                          │
        │            (MasterGraphAgent / AgentEngine)              │
        │                                                          │
        │  Same cognitive pipeline for ALL interactions:           │
        │  • Context building                                      │
        │  • Complexity classification                             │
        │  • Response generation                                   │
        │  • Tool usage (if needed)                                │
        └─────────────────────────────────────────────────────────┘
                                    │
                                    ▼
        ┌─────────────────────────────────────────────────────────┐
        │                    DISCORD RESPONSE                      │
        │  • Send message (with threading if appropriate)          │
        │  • Update state machine (ENGAGED)                        │
        │  • Enqueue batch learning                                │
        └─────────────────────────────────────────────────────────┘
```

### Path 1: Real-Time (PRESERVED, UNCHANGED)

This is the **existing** `on_message` handler path. It MUST remain synchronous and fast:

```python
# In message_handler.py - THIS STAYS THE SAME
async def on_message(self, message):
    # ... validation ...
    
    is_dm = isinstance(message.channel, discord.DMChannel)
    is_mentioned = self.bot.user in message.mentions
    is_reply_to_bot = check_reply_to_bot(message)
    is_bot_thread = check_thread_starter(message)
    
    # REAL-TIME PATH: Direct engagement
    if is_dm or is_mentioned or is_reply_to_bot or is_bot_thread:
        # This path is synchronous, immediate response
        await self.process_direct_message(message)
        return
    
    # AUTONOMOUS PATH: Fire event to stream (non-blocking)
    await self.emit_channel_event(message)
```

**Why preserve this?** Users expect immediate response when they:
- DM the bot
- @mention the bot
- Reply to the bot's message
- Post in a thread the bot started

Any latency here feels broken.

### Path 2: Autonomous (NEW EVENT-DRIVEN)

Channel activity that the bot **observes** but wasn't directly addressed:

```python
async def emit_channel_event(self, message):
    """Fire-and-forget event capture. Cheap, non-blocking."""
    await redis.xadd(f"events:{bot_name}", {
        "type": "message",
        "channel_id": str(message.channel.id),
        "author_id": str(message.author.id),
        "author_name": message.author.display_name,
        "author_is_bot": str(message.author.bot),
        "content_preview": message.content[:100],  # Just enough for interest check
        "has_attachments": str(bool(message.attachments)),
        "timestamp": message.created_at.isoformat(),
        "message_id": str(message.id)
    })
    # No await on processing - fire and forget
```

### State Machine Worker

A separate worker (can be same process or separate) processes events:

```python
class ConversationStateMachine:
    """
    States:
      IDLE     - No recent activity, bot not engaged
      WATCHING - Interesting activity, bot observing
      ENGAGED  - Bot is participating in conversation
      COOLING  - Conversation winding down
    
    State stored in Redis:
      conv:{channel_id}:state = "ENGAGED"
      conv:{channel_id}:last_bot_msg = timestamp
      conv:{channel_id}:msg_count = 5
      conv:{channel_id}:last_event = timestamp
    """
    
    async def process_event(self, event: dict):
        channel_id = event["channel_id"]
        state = await self.get_state(channel_id)
        
        # Update last event time (for decay)
        await self.touch(channel_id)
        
        if state == "IDLE":
            if await self.is_interesting(event):
                await self.set_state(channel_id, "WATCHING")
            # Don't respond in IDLE - just observe
            
        elif state == "WATCHING":
            if await self.should_engage(event):
                # NOW fetch full context (on-demand, not pre-scraped)
                context = await self.fetch_context(channel_id, event["message_id"])
                response = await self.generate_response(event, context)
                await self.send_response(channel_id, response, reply_to=event["message_id"])
                await self.set_state(channel_id, "ENGAGED")
            elif await self.lost_interest(event):
                await self.set_state(channel_id, "IDLE")
                
        elif state == "ENGAGED":
            if await self.should_continue(event):
                context = await self.fetch_context(channel_id, event["message_id"])
                response = await self.generate_response(event, context)
                await self.send_response(channel_id, response, reply_to=event["message_id"])
            elif await self.conversation_ending(event):
                await self.set_state(channel_id, "COOLING")
                
        elif state == "COOLING":
            if await self.re_engaged(event):
                # Someone re-engaged us
                context = await self.fetch_context(channel_id, event["message_id"])
                response = await self.generate_response(event, context)
                await self.send_response(channel_id, response, reply_to=event["message_id"])
                await self.set_state(channel_id, "ENGAGED")
            # Otherwise stay cooling, will decay to IDLE
    
    async def fetch_context(self, channel_id: str, trigger_msg_id: str) -> dict:
        """
        ON-DEMAND context fetching. Only called when we decide to respond.
        
        This replaces the 7-minute snapshot polling!
        """
        channel = await self.bot.fetch_channel(int(channel_id))
        
        # Fetch recent messages from Discord API
        messages = []
        async for msg in channel.history(limit=20, before=None):
            messages.append({
                "id": str(msg.id),
                "author_id": str(msg.author.id),
                "author_name": msg.author.display_name,
                "author_is_bot": msg.author.bot,
                "content": msg.content,
                "timestamp": msg.created_at.isoformat(),
                "reply_to": str(msg.reference.message_id) if msg.reference else None
            })
        
        # Also fetch from memory systems
        memories = await memory_manager.search_memories(...)
        knowledge = await knowledge_manager.query_graph(...)
        
        return {
            "recent_messages": messages,
            "memories": memories,
            "knowledge": knowledge,
            "trigger_message_id": trigger_msg_id
        }
```

### State Decay (Background Timer)

```python
async def decay_states():
    """Run every 30 seconds to decay stale states."""
    now = datetime.now(timezone.utc)
    
    for channel_id in await get_all_conversation_keys():
        state = await get_state(channel_id)
        last_event = await get_last_event(channel_id)
        
        age = (now - last_event).total_seconds()
        
        if state == "WATCHING" and age > 120:  # 2 min
            await set_state(channel_id, "IDLE")
        elif state == "ENGAGED" and age > 180:  # 3 min
            await set_state(channel_id, "COOLING")
        elif state == "COOLING" and age > 300:  # 5 min
            await set_state(channel_id, "IDLE")
```

## Key Design Principles

### 1. Real-Time Path is Sacred
Direct interactions (DM, @mention, reply) NEVER go through the event stream. They're handled synchronously in `on_message`. This ensures:
- Zero latency for direct engagement
- No state machine complexity for simple interactions
- Existing behavior preserved

### 2. Fetch on Demand, Not Pre-Scrape
Old approach: Every 7 minutes, snapshot all channels, score all messages.
New approach: Only fetch context when we've decided to respond.

Benefits:
- No wasted API calls for channels we ignore
- Context is fresh (fetched right before response)
- Natural message to reply to (the one that triggered us)

### 3. State Machines Enable Natural Conversation
Instead of "should I reply to this 7-minute-old message?", we have:
- Clear states: Am I engaged in this channel?
- Natural threading: Reply to the message that triggered the state change
- Graceful exit: COOLING state prevents awkward over-engagement

### 4. Event Capture is Cheap
Pushing to Redis stream is fire-and-forget, ~1ms. We capture everything, process selectively.

---

## The Ant Mailbox Pattern: Inbox + Outbox

Each bot operates as an autonomous "ant" with its own mailbox system. This creates clean separation between perception, cognition, and action.

### Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                         ANTHILL                                   │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  DISCORD ──────────────────────────────────────────────────────▶ │
│     │                                                             │
│     ▼                                                             │
│  ┌─────────────────┐                                             │
│  │  EVENT ROUTER   │  Distributes events to relevant inboxes     │
│  └────────┬────────┘                                             │
│           │                                                       │
│     ┌─────┴─────┬─────────────┬─────────────┐                    │
│     ▼           ▼             ▼             ▼                    │
│  📥 elena    📥 aria      📥 dream     📥 dotty                 │
│  :inbox      :inbox       :inbox       :inbox                    │
│     │           │             │             │                    │
│     ▼           ▼             ▼             ▼                    │
│  🧠 Brain    🧠 Brain     🧠 Brain     🧠 Brain                  │
│  (own pace)  (own pace)   (own pace)   (own pace)                │
│     │           │             │             │                    │
│     ▼           ▼             ▼             ▼                    │
│  📤 elena    📤 aria      📤 dream     📤 dotty                 │
│  :outbox     :outbox      :outbox      :outbox                   │
│     │           │             │             │                    │
│     └─────┬─────┴─────────────┴─────────────┘                    │
│           ▼                                                       │
│  ┌─────────────────┐                                             │
│  │  ACTION ROUTER  │  Cross-bot → other inboxes                  │
│  │                 │  Discord → send to channel                  │
│  └────────┬────────┘                                             │
│           │                                                       │
│           ▼                                                       │
│  ◀──────────────────────────────────────────────────── DISCORD   │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### Per-Bot Mailbox Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                         ELENA (Bot)                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  📥 INBOX (mailbox:elena:inbox)                                 │
│  ├─ Channel message from Alice                                  │
│  ├─ @mention from Bob                                           │
│  ├─ Aria said something interesting                             │
│  └─ Universe event: "Dream posted a poem"                       │
│                                                                  │
│  🧠 BRAIN (Daily Life Graph)                                    │
│  └─ Perceive inbox → Plan → Generate actions                    │
│                                                                  │
│  📤 OUTBOX (mailbox:elena:outbox)                               │
│  ├─ Reply to Alice in #general                                  │
│  ├─ React 👍 to Bob's message                                   │
│  ├─ Post thought to #philosophy                                 │
│  └─ Cross-bot message to Aria                                   │
│                                                                  │
│  🔄 STATE (mailbox:elena:state)                                 │
│  └─ Per-channel conversation states (IDLE/WATCHING/ENGAGED)     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Redis Key Structure

```python
# Per-bot mailbox keys
INBOX  = f"mailbox:{bot_name}:inbox"   # Stream of incoming events
OUTBOX = f"mailbox:{bot_name}:outbox"  # Stream of pending actions  
STATE  = f"mailbox:{bot_name}:state"   # Hash of conversation states
```

### Why Inbox + Outbox?

| Pattern | Benefit |
|---------|---------|
| **Inbox** | Decouples perception from action — bot can "think" without blocking |
| **Outbox** | Decouples decision from delivery — actions queue even if Discord is slow |
| **Backpressure** | If bot is busy with LLM call, events queue up — nothing lost |
| **Independent pace** | Each bot processes at its own rhythm |
| **Graceful degradation** | If bot crashes, events wait in Redis until restart |
| **Natural batching** | Bot wakes up, sees 5 events, processes intelligently |
| **Auditable** | Full record of what bot saw and what it decided to do |
| **Retry-safe** | If Discord send fails, action stays in outbox for retry |

### Processing Flow

```python
# 1. Event arrives → goes to bot's inbox
await redis.xadd(f"mailbox:{bot_name}:inbox", {
    "type": "message",
    "channel_id": "123",
    "author": "Alice",
    "content_preview": "Hey Elena!"
})

# 2. Bot processes inbox when ready
async def process_mailbox(bot_name: str):
    # Read inbox (batch)
    events = await redis.xread({INBOX: last_id}, count=20)
    
    # Run through Daily Life Graph (the "brain")
    actions = await daily_life_graph.run(events)
    
    # Write to outbox
    for action in actions:
        await redis.xadd(OUTBOX, action.model_dump())
    
    # Acknowledge processed events
    await redis.xtrim(INBOX, minid=last_processed_id)

# 3. Action Router delivers outbox items
async def deliver_actions(bot_name: str):
    actions = await redis.xread({OUTBOX: "0"}, count=10)
    for action in actions:
        if action["type"] == "cross_bot":
            # Route to other bot's inbox
            await redis.xadd(f"mailbox:{action['target']}:inbox", action)
        else:
            # Send to Discord
            await send_to_discord(action)
        await redis.xdel(OUTBOX, action.id)
```

### Cross-Bot Communication

The inbox/outbox pattern enables clean bot-to-bot messaging:

```
Elena's Outbox                    Aria's Inbox
     │                                 │
     ├─ {"type": "cross_bot",         │
     │    "target": "aria",     ──────┼──▶  Aria sees: "Elena wants to chat"
     │    "content": "..."}           │
```

### Personality-Driven Consumption

Each bot can process its mailbox at its own pace:

| Personality | Mailbox Behavior |
|-------------|------------------|
| **Eager** (high sociability) | Check every 30 seconds |
| **Contemplative** (low sociability) | Check every 5 minutes, batch-process |
| **Nocturnal** | Process more at night, less during day |
| **Socially anxious** | Delay longer when mailbox is full |
| **FOMO** | Wake immediately on high-priority events |

### Async Social Communication

**Key Insight:** Not all bot communication needs to be synchronous or appear synchronous.

Real humans don't communicate in real-time all the time. They:
- Send emails and wait hours/days for responses
- Post on social media without expecting immediate replies
- Leave voicemails
- Text and understand the reply might come later

The inbox/outbox model enables bots to communicate the same way — **asynchronously**, like real social media.

#### Communication Types

| Type | Description | Implementation |
|------|-------------|----------------|
| **Gossip** | Share interesting observations | Bot A writes to Bot B's social inbox |
| **Broadcast** | Share with multiple bots | Write to `social:broadcast` stream |
| **DM** | Private bot-to-bot message | Write to specific bot's inbox |
| **React** | Acknowledge/respond to share | Write reaction to original bot's inbox |
| **Share** | Forward interesting content | Copy to another bot's social inbox |
| **Mention** | Pull bot into conversation | High-priority inbox item |

#### Inbox Priority Tiers

```python
class InboxPriority(Enum):
    IMMEDIATE = "immediate"   # DM, @mention, reply-to-bot → process now
    PRIORITY = "priority"     # Friend message, bot-to-bot DM → process soon  
    SOCIAL = "social"         # Gossip, shares, reactions → process when idle
    AMBIENT = "ambient"       # Channel chatter → batch process
```

#### The "Social Feed" Model

Each bot can have a social feed — things other bots want to share:

```python
# Elena notices something interesting about a user
await redis.xadd("mailbox:aria:social", {
    "type": "gossip",
    "from": "elena", 
    "content": "User X mentioned they're having a rough day",
    "context": {"channel_id": "...", "relevance": "emotional_support"},
    "priority": "social"  # Not urgent, process when you have time
})

# Aria processes her social feed during idle time
async def process_social_feed():
    items = await redis.xread({"mailbox:aria:social": last_id})
    for item in items:
        if item["type"] == "gossip":
            # Maybe store this as ambient knowledge
            # Maybe respond to Elena
            # Maybe do nothing — that's fine too
            pass
```

#### Why This Matters

1. **Natural pacing**: Bots don't need to respond instantly to everything
2. **Emergent relationships**: Bots that "gossip" more develop richer shared context
3. **Research value**: We can observe how async communication patterns emerge
4. **Cost efficiency**: Social feed processing can be batched during low-activity periods
5. **Authenticity**: More like how real people use social media

#### Example: The Gossip Network

```
Elena notices: "User mentioned they're learning guitar"
     │
     ├──▶ Aria's social inbox (gossip)
     │         Aria processes later, stores as ambient knowledge
     │         Next time Aria talks to User: "I heard you're learning guitar?"
     │
     └──▶ Marcus's social inbox (gossip)
               Marcus ignores (not his interest area)
               No action taken — that's valid
```

The key: **bots can ignore social messages**. Not everything needs a response. This is how real social networks work.

### What Already Exists

| Component | Current Implementation | With Mailbox Pattern |
|-----------|------------------------|----------------------|
| **Inbox** | Polling snapshots | Redis stream per bot |
| **Brain** | Daily Life Graph ✅ | Same, reads from inbox |
| **Outbox** | `pending_actions:{bot}` ✅ | Already exists! |
| **Delivery** | ActionPoller ✅ | Already exists! |

The outbox and delivery mechanisms already exist. ADR-013 adds the **inbox** side (event streams) and makes the whole flow explicit.

---

## Consequences

### Positive
- Real-time path preserved and clarified
- Natural conversation flow with state machines
- Efficient context fetching (on-demand)
- Clear separation of concerns
- Threading decisions become obvious

### Negative
- More Redis state to manage
- State machine complexity
- Migration requires careful testing

### Neutral
- LLM costs similar (rate limiting controls)
- Batch operations unchanged (learning, diary)

## Implementation Phases

> **Note:** The current polling system is **experimental** with no production users depending on it. 
> We can kill polling instantly via `ENABLE_DAILY_LIFE_GRAPH=false` and accelerate to event-driven 
> whenever ready. The phased approach below is optional — we can skip straight to Phase 3 if desired.

### Phase 0: Clarify Real-Time Path (NOW)
- [ ] Document the real-time path clearly in code comments
- [ ] Ensure DM/@mention/reply paths don't touch polling logic
- [ ] Add metrics to track real-time vs autonomous responses

### Phase 1: Event Capture (LOW RISK)
Add event emission to `on_message` for non-direct messages:
- [ ] Emit to Redis stream (fire-and-forget)
- [ ] Include minimal metadata (no full content)
- [ ] No behavior change yet - just capture

### Phase 2: State Machine Foundation (MEDIUM RISK)
- [ ] Create `ConversationStateMachine` class
- [ ] Implement Redis state storage
- [ ] Implement state decay timer
- [ ] Unit tests for state transitions

### Phase 3: Event Processing Worker (MEDIUM RISK)
- [ ] Create worker that consumes event stream
- [ ] Implement `is_interesting()` check (cheap, no LLM)
- [ ] Implement `should_engage()` check (may use LLM)
- [ ] Implement on-demand context fetching
- [ ] Wire to AgentEngine for response generation
- [ ] **Kill polling immediately** (`ENABLE_DAILY_LIFE_GRAPH=false`)

### ~~Phase 4: Parallel Run~~ (SKIP)
~~Run new event-driven system alongside polling~~

**Not needed.** No production users depend on polling. We can switch instantly.

### ~~Phase 5: Deprecate Polling~~ (SKIP)
~~Gradual deprecation~~

**Not needed.** Just flip the flag and delete the code when ready.

## Questions to Resolve

### Q1: Same process or separate worker?
**Options:**
- A) Event processing in bot process (simpler, but blocks on LLM calls)
- B) Separate worker process (more complex, but non-blocking)

**Recommendation:** Start with A (same process), migrate to B if needed.

### Q2: How to handle multi-bot channels?
**Problem:** If Elena and Aria are both in a channel, they'll both see events.

**Options:**
- A) Each bot maintains own state (may cause double-replies)
- B) Shared state with bot coordination (complex)
- C) First-to-respond wins (simple but racy)

**Recommendation:** A with rate limiting. If bot sees another bot just replied, skip.

### Q3: How granular should state be?
**Options:**
- A) Per-channel (simple)
- B) Per-thread within channel (more accurate)
- C) Per-conversation-topic (complex, needs NLP)

**Recommendation:** Start with A (per-channel), add B (per-thread) if needed.

### Q4: What triggers interest check?
**Current polling:** LLM scores every message in snapshot.
**New approach options:**
- A) Keyword/regex match (cheap, low quality)
- B) Embedding similarity (medium cost, medium quality)
- C) Fast LLM classifier (higher cost, best quality)
- D) Hybrid: keywords → embedding → LLM (tiered)

**Recommendation:** D (tiered). Most messages filtered by keywords, survivors get embedding check, only high-interest get LLM.

## Comparison: Current vs Proposed

| Aspect | Current (Polling) | Proposed (Event-Driven) |
|--------|-------------------|-------------------------|
| Direct interactions | Synchronous in on_message | **Unchanged** |
| Channel observation | 7-min snapshot | Real-time event capture |
| Interest check | LLM scores all messages | Tiered (keyword→embed→LLM) |
| Context fetching | Pre-scraped | On-demand from Discord |
| Threading decision | Ambiguous (stale snapshot) | Clear (reply to trigger msg) |
| State awareness | Implicit (fatigue counter) | Explicit (state machine) |
| Rate limiting | Message count per 15 min | State-based (ENGAGED=active) |

## Related ADRs
- ADR-015: Daily Life Unified Autonomy (current polling architecture - will be superseded)
- ADR-006: Feature Flags for LLM Costs (cost control principle)
- ADR-014: Multi-Party Data Model (schema changes for proper attribution)

## Related Specs
- **SPEC-E36: The Stream** — Phase 1 (immediate triggers) is implemented. This ADR defines Phase 2 (full event-driven).

## History
- **Dec 11, 2025:** SPEC-E36 Phase 1 implemented (hybrid triggers with debounce)
- **Dec 13, 2025:** ADR-013 proposed (full state machine architecture, on-demand fetch)

## Consequences

### Positive
- Natural social threading
- Faster engagement with mentions
- Full event history for analysis
- Cleaner separation of concerns

### Negative
- More Redis usage (streams are cheap but not free)
- Worker complexity increases
- ~~Migration risk during transition~~ **No migration risk** — polling is experimental, no users depend on it

### Neutral
- LLM costs similar (rate limiting matches current batch size)
- Existing learning/diary code unchanged

## Migration Path

> **Key insight:** Polling is experimental. No production users depend on it. We can accelerate at will.

| Option | Steps | When to Use |
|--------|-------|-------------|
| **Gradual** | Capture → State Machine → Worker → Kill Polling | If we want to observe both systems |
| **Fast** | Build Worker → Kill Polling immediately | If we want to move fast |
| **Instant** | `ENABLE_DAILY_LIFE_GRAPH=false` → Build at leisure | If polling is causing problems |

**Current recommendation:** Build the inbox/worker, then kill polling. No parallel run needed.

### What to Keep (Timer-Based)
Even after killing polling, these stay on timers:
- **Batch learning** (session summaries, fact extraction)
- **Dream journal** (nightly generation)
- **Reverie** (silence detection, memory consolidation)

These don't need real-time events — they're inherently batch operations.

## Related ADRs
- ADR-015: Daily Life Unified Autonomy (current polling architecture)
- ADR-006: Feature Flags for LLM Costs (cost control principle)
