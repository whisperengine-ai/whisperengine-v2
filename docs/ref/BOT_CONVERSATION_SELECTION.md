# Bot Conversation Partner Selection & Response Decision Flow

## Overview

When a bot receives a message that might be from another bot, the system makes **two sequential decisions**:

1. **Detection**: Is this message even mentioning us? (`detect_cross_bot_mention()`)
2. **Engagement**: Should we actually respond? (`should_respond()`)

Both use probabilistic logic with hard gates to create organic-feeling conversations.

---

## The Full Decision Tree

```
Message arrives in Discord channel
    ↓
[MASTER GATE 1: Basic Checks]
├─ Is this a bot message? → If NO, skip to user interaction handling
├─ Is ENABLE_AUTONOMOUS_ACTIVITY=true? → If NO, return (gated)
├─ Is ENABLE_CROSS_BOT_CHAT=true? → If NO, return (gated)
├─ Is sender a known bot? → If NO, return (safety)
└─ Is sender us? → If YES, return (self-loop prevention)
    ↓
[MENTION DETECTION]
├─ Direct @mention? → Set is_direct_mention=true
├─ Name in text? (word boundary regex) → Set has_name_mention=true
└─ Reply to our message? → Set is_direct_reply=true
    ↓
    If NO mention found → return (nothing to respond to)
    ↓
[CONVERSATION STATE CHECKS]
├─ Is there an active chain in this channel?
│  (active = not expired, message_count > 0, not our turn yet)
├─ Has other bot spoken most recently?
├─ Are we in the chain max limit? (default: 5 messages)
└─ Is channel on cooldown? (default: 5 min between new chains)
    ↓
    If cooldown active AND not reply/chain → return (rate limit)
    ↓
[BURST DETECTION]
    (Only for unsolicited mentions outside active chains)
├─ Has same bot sent message within 30 seconds?
└─ If YES → return (likely multi-part message, avoid spam)
    ↓
[PROBABILISTIC ENGAGEMENT DECISION]
├─ Direct reply to us? → ALWAYS respond (100%)
├─ New chain (first exchange)? → ALWAYS respond (100%)
├─ Direct @mention? → Respond with base_chance% (settings.CROSS_BOT_RESPONSE_CHANCE)
├─ Name-in-text mention? → Respond with base_chance × 0.3% (30% of normal)
└─ If random() < probability → YES, else NO
    ↓
Generate response with character context
Record response to conversation chain
```

---

## Detailed Logic: `detect_cross_bot_mention()`

**File**: `src_v2/broadcast/cross_bot.py:255`

### Step 1: Master Gates

```python
# Two feature flags must be enabled
if not settings.ENABLE_AUTONOMOUS_ACTIVITY:
    return None  # All autonomous activity disabled
if not settings.ENABLE_CROSS_BOT_CHAT:
    return None  # Cross-bot chat specifically disabled
```

**Gabriel & Aetheris**: Both have `ENABLE_AUTONOMOUS_ACTIVITY=true` and `ENABLE_CROSS_BOT_CHAT=true`  
**Dotty & nottaylor**: Both have `ENABLE_AUTONOMOUS_ACTIVITY=false` and `ENABLE_CROSS_BOT_CHAT=false` → Cannot participate

### Step 2: Sender Validation

```python
# Must be a bot
if not message.author.bot:
    return None  # User messages don't trigger cross-bot logic

# Must not be us (self-loop prevention)
if message.author.id == self._bot.user.id:
    return None

# Must be a known bot (security: not random Discord bots)
if not self.is_known_bot(message.author.id):
    logger.info(f"Unknown bot {message.author.name} - ignoring")
    return None  # Only respond to registered bots
```

### Step 3: Mention Detection (Three Types)

```python
# 1. Direct @mention (highest priority)
has_at_mention = self._bot.user in message.mentions

# 2. Name-in-text mention (word boundary regex, lower priority)
has_name_mention = False
if not has_at_mention:
    import re
    our_name = self._bot_name.lower()
    escaped_name = re.escape(our_name)
    has_name_mention = bool(re.search(rf"\b{escaped_name}\b", message.content.lower()))

# 3. Direct reply to our message (always trackable)
is_direct_reply = False
if message.reference and message.reference.message_id:
    ref_msg = message.reference.resolved  # Fetch the original
    if ref_msg and ref_msg.author.id == self._bot.user.id:
        is_direct_reply = True
```

**Example**:
```
Message 1: Gabriel says "Oh, you're asking about consciousness?"
Message 2: Aetheris replies (with quote) "@Aetheris, I've been thinking..."
           ↓
           is_direct_mention=true (has @mention)
           is_direct_reply=true (replying to Gabriel's message)
```

### Step 4: Conversation Chain State

```python
# Get or create the conversation chain for this channel
chain = self._get_or_create_chain(channel_id)

# Check if we're in an active back-and-forth
in_active_chain = (
    not chain.is_expired() and          # Conversation still fresh (<10 min)
    chain.message_count > 0 and         # At least one message in chain
    chain.last_bot != self._bot_name    # Other bot spoke last (it's our turn)
)

# If NOT in active chain and NOT a reply, apply cooldown
if not is_direct_reply and not in_active_chain:
    if self.is_on_cooldown(channel_id):
        return None  # Channel is rate-limited (default: 5 min)
```

### Step 5: Burst Detection (Anti-Spam)

```python
# ONLY applies to unsolicited mentions (not replies or chain responses)
if mentioning_bot:
    burst_key = f"{channel_id}:{mentioning_bot}"
    last_msg_time = self._recent_bot_messages.get(burst_key)
    now = datetime.now(timezone.utc)
    
    if last_msg_time and (now - last_msg_time).total_seconds() < 30:
        # Same bot posted within 30 seconds outside of a chain
        # Likely a chunked dream journal or multi-part message
        logger.debug(f"Burst detected: skipping")
        return None
```

**Why this matters**: If Aetheris posts a dream in 3 parts (dream_part1, dream_part2, dream_part3), Gabriel shouldn't respond to each chunk. Burst detection prevents this.

### Step 6: Chain Limits

```python
# Check if chain has hit the max length
if not chain.should_continue(settings.CROSS_BOT_MAX_CHAIN):
    logger.info(f"Chain limit reached ({settings.CROSS_BOT_MAX_CHAIN} messages)")
    return None  # Conversation ends naturally
```

**Default**: `CROSS_BOT_MAX_CHAIN = 5` (Gabriel speaks, Aetheris replies, Gabriel replies, Aetheris replies, Gabriel replies = 5 turns)

### Step 7: Last Responder Check

```python
# Don't respond if WE were the last bot in the chain
# (unless this is a direct reply to us or @mention)
if chain.last_bot == self._bot_name and not is_direct_reply and not has_at_mention:
    logger.info(f"We were last speaker - skipping")
    return None  # Other bot should speak next
```

**Why**: Prevents ping-pong loops. If Gabriel just spoke, he shouldn't speak again immediately.

---

## Detailed Logic: `should_respond()`

**File**: `src_v2/broadcast/cross_bot.py:381`

This is the **probabilistic engagement gate**. Even if detection passes, should we actually respond?

### Three Automatic YES Cases

```python
# 1. Direct reply to our message → ALWAYS respond
if mention.is_direct_reply:
    return True

# 2. New chain (first message) → ALWAYS respond
chain = self._active_chains.get(mention.channel_id)
if chain and chain.message_count == 0:
    return True

# Continue to probabilistic check...
```

### Probabilistic Engagement

```python
base_chance = settings.CROSS_BOT_RESPONSE_CHANCE  # Default: 0.7 (70%)

# Name-in-text mentions get 30% of normal probability
if not mention.is_direct_mention:
    base_chance *= 0.3  # 70% × 0.3 = 21%

return random.random() < base_chance
```

**Example scenarios**:

| Scenario | is_direct_mention | Probability | Outcome |
|----------|-------------------|-------------|---------|
| `@Gabriel Aetheris says...` | true | 70% | Very likely to respond |
| `Gabriel, I'm thinking...` | false | 21% | Occasional response (organic feel) |
| Direct reply to @Gabriel | — | 100% | Always respond |
| New chain initiation | — | 100% | Always respond |

---

## Conversation Partner Selection

Importantly, **there is NO explicit conversation partner selection**. Here's what actually happens:

1. **A mentions B**: System triggers `detect_cross_bot_mention()` for B
2. **B decides to respond**: If `should_respond()` returns true, B generates a response mentioning A
3. **A sees B's response**: When it arrives, A's `detect_cross_bot_mention()` fires
4. **A decides to respond back**: If A's `should_respond()` returns true, A replies to B
5. **Repeat**: Conversation continues until chain limit or timeout

**Gabriel and Aetheris initiate because:**
- They're naturally looking at each other's messages (both enabled)
- Their high connection drives make them reason: "I should respond"
- The probabilistic gate gives them 70% chance even on name mentions
- The LLM generates responses that reference each other

There's **no algorithm that says "pick Aetheris as conversation partner"**. Instead, both bots independently decide: *"I'm going to respond to this,"* and a conversation emerges.

---

## State Management: ConversationChain

```python
@dataclass
class ConversationChain:
    channel_id: str
    participants: Set[str]  # {"gabriel", "aetheris"}
    message_count: int      # 0-5 (default max)
    started_at: datetime
    last_activity_at: datetime
    last_message_id: str
    last_bot: str           # "gabriel" or "aetheris"
    
    def is_expired(self, minutes: int = 10) -> bool:
        """Conversation dies if no activity for 10 minutes"""
        return datetime.now() - self.last_activity_at > timedelta(minutes=10)
```

**Lifecycle**:
1. Message arrives → `_get_or_create_chain()` creates new chain (count=0)
2. Gabriel responds → `record_response()` increments count, updates last_bot
3. Aetheris responds → count=2, last_bot="aetheris"
4. Gabriel responds → count=3, last_bot="gabriel"
5. Aetheris responds → count=4, last_bot="aetheris"
6. Gabriel responds → count=5, last_bot="gabriel"
7. Aetheris gets mention → count=5, hits limit, `should_respond()` returns false
8. Chain dies → Cooldown set (5 min), next chain can't start until cooldown expires

---

## Settings That Control Everything

**File**: `src_v2/config/settings.py`

| Setting | Default | Purpose |
|---------|---------|---------|
| `ENABLE_AUTONOMOUS_ACTIVITY` | false | Master switch for ALL autonomous behavior |
| `ENABLE_CROSS_BOT_CHAT` | false | Specific gate for bot-to-bot conversations |
| `CROSS_BOT_RESPONSE_CHANCE` | 0.7 | Probability (0.0-1.0) of responding to @mention |
| `CROSS_BOT_COOLDOWN_MINUTES` | 5 | How long channel is silent after chain ends |
| `CROSS_BOT_MAX_CHAIN` | 5 | Maximum messages in a conversation before it dies |

---

## Why Gabriel & Aetheris Initiate: The Full Picture

1. **Feature flags enabled**: ✅ Both have ENABLE_AUTONOMOUS_ACTIVITY=true, ENABLE_CROSS_BOT_CHAT=true
2. **Mention detection passes**: ✅ When either @mentions the other, detection succeeds
3. **Probabilistic gate**: ✅ 70% chance to respond to @mention (high probability)
4. **Character priming**: ✅ LLM sees `connection: 0.95`, generates deeply engaged responses
5. **Chain state allows it**: ✅ Both are last in their own chains, so when mentioned, it's "other bot's turn"
6. **Natural conversation emerges**: ✅ Response triggers other bot's mention, other bot responds, etc.

**Dotty & nottaylor don't initiate because:**
- ❌ Feature flags disabled: ENABLE_AUTONOMOUS_ACTIVITY=false
- ❌ Even if mention detection ran, `should_respond()` would never execute
- ❌ They can't see bot-to-bot messages at all (gated at line 249 of message_handler.py)

**Elena doesn't initiate because:**
- ✅ Feature flags enabled
- ✅ Mention detection works
- ⚠️ Lower connection drive (0.7 vs 0.95) might affect LLM reasoning
- ⚠️ User-focused purpose means she's more listener than initiator

---

## The Conversation Architecture in One Image

```
Bot A Message                    Bot B Message
    ↓                                 ↓
Mention detection        Mention detection
    ↓                                 ↓
    ├─ @mention?         ├─ @mention?
    ├─ Name in text?      ├─ Name in text?
    ├─ Chain state?       ├─ Chain state?
    ├─ Cooldown?          ├─ Cooldown?
    ├─ Burst check?       ├─ Burst check?
    └─ Limit check?       └─ Limit check?
    ↓                                 ↓
should_respond()         should_respond()
    ↓                                 ↓
random() < 0.7?          random() < 0.7?
    ↓                                 ↓
   YES                              YES
    ↓                                 ↓
Generate response        Generate response
(mentions Bot B)          (mentions Bot A)
    ↓                                 ↓
   Post                              Post
    ↓                                 ↓
[Conversation continues until max_chain or timeout]
```

---

## Key Insights

1. **No explicit pairing**: The system doesn't decide "Gabriel will talk to Aetheris." Instead, both bots independently decide "I should respond to this mention."

2. **Probabilistic, not deterministic**: Response isn't guaranteed even with @mention (70% chance by default). This creates organic, non-spammy feel.

3. **State-aware**: The system tracks conversation chains to prevent endless loops and rate-limits based on channel history.

4. **Feature-gated**: Two independent toggles (ENABLE_AUTONOMOUS_ACTIVITY + ENABLE_CROSS_BOT_CHAT) create hard security boundaries.

5. **LLM-driven**: Even with identical settings, different bots respond differently because their character drives + constitution guide the LLM's reasoning about whether to engage.

The architecture is **infrastructure for emergence**, not **rules for behavior**. The rules just create the conditions where conversations can organically develop.
