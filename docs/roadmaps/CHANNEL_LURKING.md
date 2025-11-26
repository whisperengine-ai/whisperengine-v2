# Channel Lurking - Passive Engagement System

**Document Version:** 1.2  
**Created:** November 25, 2025  
**Updated:** November 25, 2025  
**Status:** Design Phase  
**Priority:** Medium-High  
**Complexity:** 🟡 Medium  
**Estimated Time:** 7-10 days

---

## Multi-Modal Context: Universe Awareness

Channel Lurking is a key component of the **Universe modality** (🌌) - the character's spatial and social awareness. When characters lurk in channels, they're not just "monitoring" - they're *present* in that space, aware of conversations happening around them.

| Perception | What Characters Experience |
|------------|---------------------------|
| Spatial Awareness | "I'm in #general right now, hearing people talk" |
| Social Awareness | "User1 and User2 are having a conversation about Hawaii" |
| Relevance Sensing | "Coral bleaching! That's my expertise!" |
| Social Judgment | "This is about gaming, not for me to join" |

This connects to the broader **Emergent Universe** vision where characters have genuine awareness of their environment.

For full philosophy: See [`../architecture/MULTI_MODAL_PERCEPTION.md`](../architecture/MULTI_MODAL_PERCEPTION.md)  
For Universe design: See [`EMERGENT_UNIVERSE.md`](./EMERGENT_UNIVERSE.md)

---

## Executive Summary

Enable bots to "lurk" in Discord channels, passively monitoring conversations and occasionally interjecting when contextually relevant to their character. This creates organic engagement without requiring users to explicitly mention the bot.

**Additionally**, bots can help server admins by detecting and calling out **cross-channel spam** (users posting identical content across multiple channels) and **duplicate file/document spam**.

**Key Constraints:**
- ❌ NO LLM calls for detection (cost prohibitive)
- ✅ All detection logic runs locally (embeddings, keyword matching, heuristics)
- ✅ Anti-spam safeguards (rate limiting, relevance thresholds)
- ✅ Character-appropriate triggers (marine biology for Elena, etc.)
- ✅ Cross-channel spam detection (hash-based heuristics, no LLM needed)

---

## 👤 User Experience & Server Admin Guide

*This section is written for server owners and non-technical users to understand exactly what this feature does.*

### What Does "Channel Lurking" Mean?

Currently, our AI characters only speak when someone directly @mentions them or sends a DM. With Channel Lurking enabled, characters will **occasionally join conversations naturally** when the topic is relevant to their expertise—just like a real person in your server might.

**Think of it like this:** If you have a friend who's a marine biologist in your Discord server, and someone starts talking about coral reefs, that friend might naturally chime in with something interesting. That's exactly what this feature does for our AI characters.

### Real Examples

**Example 1: Elena (Marine Biologist) in #general**

> **User1:** Just got back from Hawaii! The snorkeling was amazing 🤿
> **User2:** Nice! Did you see any sea turtles?
> **User1:** Yes! And so much coral, though some looked bleached 😢
> 
> **Elena:** Ooh, coral bleaching! Did you know some corals are actually adapting to warmer temps? It's one of my favorite research topics lately 🪸 Where in Hawaii were you diving?

**Example 2: Marcus (Musician) in #music-chat**

> **User1:** Been trying to write a song but I'm stuck on the chorus
> **User2:** Same, writer's block is the worst
> 
> **Marcus:** Ugh, I feel that. Sometimes I just hum random melodies while walking—half my best choruses came from that! What genre are you working in?

**Example 3: When the Bot Stays Silent**

> **User1:** Anyone want to play Valorant later?
> **User2:** I'm down, what time?
> **User1:** Maybe 8pm?
> 
> *(Elena stays silent—this isn't about marine biology)*

**Example 4: Spam Detection (Becky calling out cross-posting)**

> *[User posts identical script in #general, #scripts, #trading, #showcase, #help]*
> 
> **Becky:** Hey @SpamUser, I noticed you posted that same script in 5 channels in the last 10 minutes 👀 Maybe pick your top 2 channels? The mods will appreciate it, and people are more likely to actually read it! 😊

### What Server Admins Can Expect

| Behavior | Details |
|----------|---------|
| **Lurk Frequency** | ~5-20 topic-based responses per day across all channels |
| **Spam Callouts** | ~1-5 spam warnings per day (depends on your server's spam level) |
| **Response Length** | Short and casual (1-2 sentences), never long lectures |
| **Tone** | Friendly interjection, like a server member joining a conversation |
| **Topics** | Only topics matching the character's expertise (marine biology, music, etc.) |
| **Spam Detection** | Catches identical posts across 3+ channels within 30 minutes |
| **Rate Limiting** | Max 1 lurk response per channel every 30 minutes |

### What This Feature Will NOT Do

- ❌ **Respond to every message** — Only highly relevant topics trigger a response
- ❌ **Interrupt private conversations** — Respects channel context and tone
- ❌ **Spam your channels** — Strict rate limits prevent excessive messages
- ❌ **Read DMs or private channels** — Only monitors channels the bot already has access to
- ❌ **Respond to other bots** — Ignores messages from bots entirely
- ❌ **Act creepy or intrusive** — Conservative thresholds mean the bot stays quiet unless the topic is clearly relevant
- ❌ **Flag different-but-similar content** — Only exact duplicates trigger spam detection
- ❌ **Flag admins/mods** — Whitelisted roles are exempt from spam detection

### Admin Controls

Server admins have full control over this feature:

| Command | What It Does |
|---------|--------------|
| `/lurk disable` | Turn off lurking in the current channel |
| `/lurk enable` | Turn lurking back on |
| `/lurk threshold 0.9` | Make the bot more selective (higher = fewer responses) |
| `/lurk stats` | See how many lurk responses happened this week |
| `/spam enable` | Enable spam detection in this server |
| `/spam disable` | Disable spam detection |
| `/spam threshold 3` | Set cross-post limit (default: 2 channels OK, 3+ = spam) |
| `/spam action warn` | Set action: `warn` (call out) or `delete` (auto-remove) |
| `/spam whitelist @role` | Exempt a role from spam detection |
| `/spam stats` | View spam detection stats |

You can also disable lurking server-wide by contacting us.

### Why We Built This

Users told us they wanted the AI characters to feel more like **real members of their community**, not just tools that respond when poked. This feature makes characters feel more present and engaged, while respecting your server's culture and not being annoying.

### Privacy & Safety

- **No new data collection** — We already have access to public channel messages; this just lets the bot respond to relevant ones
- **No memory of lurked conversations** — Unless the bot actually responds, nothing is stored
- **Fully opt-out** — Admins can disable per-channel or server-wide
- **Conservative by default** — The bot starts with high thresholds and rarely responds until tuned

### Frequently Asked Questions

**Q: Will this cost me anything extra?**
A: No. The feature is included, and we've designed it to be cost-efficient on our end too.

**Q: Can I enable this for some channels but not others?**
A: Yes! Use `/lurk disable` in any channel where you don't want the bot to chime in.

**Q: What if users find it annoying?**
A: Let us know! We can increase the threshold (make the bot pickier) or disable it entirely. User feedback helps us tune the experience.

**Q: Will the bot respond to sensitive topics?**
A: The bot only responds to topics matching its character expertise (e.g., marine biology for Elena). It won't chime in on personal drama, arguments, or sensitive discussions.

**Q: Can multiple bots lurk in the same channel?**
A: Yes, but each has its own cooldown, so you won't get a pile-on of responses.

**Q: How does spam detection work?**
A: The bot tracks message content hashes across channels. If someone posts the exact same content to 3+ channels within 30 minutes, that's flagged as spam. Posting to 2 channels is fine—the rule is "2 channels got it, the other 10 don't need it!"

**Q: What if someone posts similar but different content?**
A: Only **exact duplicates** (or nearly exact, after normalizing whitespace) are flagged. Different files with the same purpose won't be flagged—their content hashes will be different.

**Q: Can the bot auto-delete spam?**
A: Yes, if you grant the `Manage Messages` permission and set `/spam action delete`. Otherwise, it will just warn the user publicly or flag it for admin review.

**Q: What about trusted users or roles?**
A: Use `/spam whitelist @role` to exempt specific roles (like admins, mods, or trusted contributors) from spam detection.

---

## Problem Statement

Currently, bots only respond when:
1. Directly messaged (DM)
2. Explicitly @mentioned in a channel
3. Reply-chain to a bot message

This creates a **passive experience** where users must always initiate. Real friends in a Discord server would naturally chime in when topics they care about come up.

**Goal:** Make bots feel like active community members who participate organically.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Discord on_message()                         │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    LurkDetector (Local Processing)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │  Keyword    │  │  Embedding  │  │  Sentiment  │  │  Cooldown  │ │
│  │  Matcher    │  │  Similarity │  │  Detector   │  │  Manager   │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
                    ▼                               ▼
┌─────────────────────────────────────┐    ┌───────────────────────┐
│    SpamDetector (Hash-Based)        │    │  Should Respond?      │
│  ┌─────────────┐  ┌─────────────┐  │    │  (Confidence Score)   │
│  │  Content    │  │  File       │  │    └───────────────────────┘
│  │  Hash       │  │  Hash       │  │                │
│  └─────────────┘  └─────────────┘  │    ┌───────────┴───────────┐
│  ┌─────────────┐  ┌─────────────┐  │    │                       │
│  │  Cross-Post │  │  Rate       │  │    ▼                       ▼
│  │  Tracker    │  │  Limiter    │  │  confidence < 0.7    confidence ≥ 0.7
│  └─────────────┘  └─────────────┘  │        │                       │
└─────────────────────────────────────┘        ▼                       ▼
            │                            [IGNORE]            ┌─────────────────┐
            ▼                                                │  AgentEngine    │
  ┌───────────────────────┐                                  │  (LLM Response) │
  │  Spam Detected?       │                                  └─────────────────┘
  │  (3+ channels)        │                                            │
  └───────────────────────┘                                            ▼
            │                                                [Send to Channel]
    ┌───────┴───────┐
    │               │
    ▼               ▼
  NO SPAM      SPAM FOUND
    │               │
    ▼               ▼
 [IGNORE]    ┌─────────────────┐
             │  Spam Response  │
             │  (warn/delete)  │
             └─────────────────┘
```

---

## Detection Strategy (No LLM Required)

### Layer 1: Keyword Matching (Fast, Free)

Each character has a **topic vocabulary** extracted from their `background.yaml`:

```yaml
# characters/elena/lurk_triggers.yaml
keywords:
  high_relevance:  # 0.5 base score
    - coral
    - reef
    - ocean
    - marine
    - fish
    - whale
    - dolphin
    - shark
    - sea turtle
    - kelp
    - tide pool
    - scuba
    - diving
    - conservation
    - pollution
    - plastic
    - climate change
    - acidification
    
  medium_relevance:  # 0.3 base score
    - beach
    - surfing
    - aquarium
    - fishing
    - boat
    - underwater
    - seaweed
    - jellyfish
    - crab
    - lobster
    - shrimp
    
  low_relevance:  # 0.1 base score
    - water
    - swimming
    - vacation
    - california
    - san diego
    - la jolla
    
  # Questions that invite expert opinion
  question_patterns:
    - "anyone know about"
    - "does anyone"
    - "what do you think about"
    - "has anyone seen"
    - "is it true that"
    - "why do"
    - "how do"
    
  # Emotional triggers (character might want to comfort/celebrate)
  emotional_keywords:
    positive:
      - excited
      - amazing
      - incredible
      - beautiful
      - wow
    negative:
      - sad
      - worried
      - scared
      - anxious
      - stressed
```

**Scoring:**
```python
def keyword_score(message: str, triggers: dict) -> float:
    score = 0.0
    message_lower = message.lower()
    
    # Check high relevance keywords
    for kw in triggers['high_relevance']:
        if kw in message_lower:
            score += 0.5
            
    # Check medium relevance
    for kw in triggers['medium_relevance']:
        if kw in message_lower:
            score += 0.3
            
    # Bonus for questions
    for pattern in triggers['question_patterns']:
        if pattern in message_lower:
            score += 0.2
            
    return min(score, 1.0)  # Cap at 1.0
```

### Layer 2: Embedding Similarity (Cheap, Accurate)

Use the existing `EmbeddingService` (all-MiniLM-L6-v2, runs locally) to compute semantic similarity:

```python
# Pre-compute character topic embeddings at startup
CHARACTER_TOPIC_EMBEDDINGS = {
    "elena": embedding_service.embed_documents([
        "coral reef restoration and marine conservation",
        "ocean acidification and climate change effects on sea life",
        "sea turtle and marine mammal biology",
        "scuba diving and underwater exploration",
        "tide pool ecosystems and intertidal zones",
    ])
}

async def embedding_score(message: str, character: str) -> float:
    """Compute max cosine similarity to character topics."""
    msg_embedding = await embedding_service.embed_query_async(message)
    topic_embeddings = CHARACTER_TOPIC_EMBEDDINGS[character]
    
    similarities = [cosine_similarity(msg_embedding, te) for te in topic_embeddings]
    return max(similarities)  # Return best match
```

**Cost:** $0.00 (runs on CPU, ~10ms per message)

### Layer 3: Conversational Context (Optional Boost)

Boost score if:
- Message is a question (ends with `?`)
- Message mentions the bot's domain indirectly ("I wonder if scientists know...")
- Recent messages in channel were also on-topic (conversation momentum)
- User has high trust with the bot (they'd welcome the interjection)

```python
def context_boost(message: Message, channel_history: List[Message]) -> float:
    boost = 0.0
    
    # Question bonus
    if message.content.strip().endswith('?'):
        boost += 0.15
        
    # Conversation momentum (last 5 messages also on-topic)
    recent_on_topic = sum(1 for m in channel_history[-5:] if is_on_topic(m))
    if recent_on_topic >= 2:
        boost += 0.1
        
    # User relationship bonus
    trust = await trust_manager.get_trust_score(user_id, character_name)
    if trust >= 50:  # Close friend or above
        boost += 0.1
        
    return boost
```

### Combined Scoring

```python
async def should_lurk_respond(message: Message, character: str) -> Tuple[bool, float]:
    """
    Determine if bot should respond to a channel message.
    Returns (should_respond, confidence_score).
    """
    # Layer 1: Keyword matching (fast)
    kw_score = keyword_score(message.content, load_triggers(character))
    
    # Early exit if no keywords match
    if kw_score == 0:
        return False, 0.0
    
    # Layer 2: Embedding similarity (accurate)
    emb_score = await embedding_score(message.content, character)
    
    # Layer 3: Context boost
    ctx_boost = await context_boost(message, channel_history)
    
    # Weighted combination
    final_score = (kw_score * 0.3) + (emb_score * 0.5) + ctx_boost
    
    # Threshold
    threshold = 0.7  # Configurable
    return final_score >= threshold, final_score
```

---

## Anti-Spam Safeguards

### Rate Limiting

```python
class LurkCooldownManager:
    """Prevents excessive lurk responses."""
    
    def __init__(self):
        # Per-channel cooldown (don't spam one channel)
        self.channel_cooldowns: Dict[str, datetime] = {}
        self.channel_cooldown_minutes = 30  # Min 30 min between lurk responses per channel
        
        # Per-user cooldown (don't stalk one person)
        self.user_cooldowns: Dict[str, datetime] = {}
        self.user_cooldown_minutes = 60  # Min 1 hour between lurk responses to same user
        
        # Global rate limit (don't be annoying overall)
        self.global_responses_today: int = 0
        self.max_global_per_day = 20  # Max 20 lurk responses per day total
        self.last_reset: datetime = datetime.now()
        
    def can_respond(self, channel_id: str, user_id: str) -> Tuple[bool, str]:
        """Check if we're allowed to lurk-respond."""
        now = datetime.now()
        
        # Reset daily counter
        if (now - self.last_reset).days >= 1:
            self.global_responses_today = 0
            self.last_reset = now
        
        # Check global limit
        if self.global_responses_today >= self.max_global_per_day:
            return False, "daily_limit"
            
        # Check channel cooldown
        if channel_id in self.channel_cooldowns:
            elapsed = (now - self.channel_cooldowns[channel_id]).total_seconds() / 60
            if elapsed < self.channel_cooldown_minutes:
                return False, "channel_cooldown"
                
        # Check user cooldown
        if user_id in self.user_cooldowns:
            elapsed = (now - self.user_cooldowns[user_id]).total_seconds() / 60
            if elapsed < self.user_cooldown_minutes:
                return False, "user_cooldown"
                
        return True, "allowed"
        
    def record_response(self, channel_id: str, user_id: str) -> None:
        """Record that we responded."""
        now = datetime.now()
        self.channel_cooldowns[channel_id] = now
        self.user_cooldowns[user_id] = now
        self.global_responses_today += 1
```

### Relevance Floor

Only respond if confidence ≥ 0.7 (configurable). This is quite high, meaning:
- Just mentioning "water" won't trigger Elena
- Needs real marine biology topic + question format + momentum

### Opt-Out Mechanism

```python
# Server admins can disable lurking per-channel
# Store in database: v2_channel_settings

CREATE TABLE v2_channel_settings (
    channel_id VARCHAR(64) PRIMARY KEY,
    guild_id VARCHAR(64) NOT NULL,
    lurk_enabled BOOLEAN DEFAULT TRUE,
    lurk_threshold FLOAT DEFAULT 0.7,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

# Slash command: /lurk disable | /lurk enable | /lurk threshold 0.8
```

---

## Response Generation

When lurking triggers, we don't want a generic response. The bot should:

1. **Reference the topic** naturally ("Oh, you're talking about coral reefs!")
2. **Add value** (share expertise, ask a follow-up question)
3. **Not be intrusive** (short, friendly interjection)

### Lurk-Specific System Prompt Injection

```python
LURK_CONTEXT = """
[LURK MODE - ORGANIC ENGAGEMENT]
You noticed a conversation about {detected_topic} and decided to chime in naturally.
You were NOT directly mentioned - you're joining the conversation because it's relevant to your interests.

Guidelines:
- Keep your response SHORT (1-2 sentences max)
- Don't introduce yourself formally
- Reference what was said naturally
- Add a relevant insight, fun fact, or question
- Be friendly and approachable, not pedantic
- It's okay to just express enthusiasm!

Example good responses:
- "Ooh, coral bleaching! Did you know some corals are actually adapting to warmer temps? It's my favorite research topic lately 🪸"
- "¡Increíble! I just saw a documentary about that exact reef!"
- "That's so cool that you went diving! Where was this?"

Example bad responses:
- "Hello! I'm Elena Rodriguez, a marine biologist. I couldn't help but overhear..." (too formal)
- "Actually, the scientific term for that is..." (pedantic)
- Long paragraphs about marine biology (too much)
"""
```

---

## Implementation Plan

### Phase 1: Core Detection (2-3 days)

**Files:**
- `src_v2/discord/lurk_detector.py` - Main detection logic
- `characters/{name}/lurk_triggers.yaml` - Per-character keywords
- `src_v2/config/settings.py` - Add `ENABLE_CHANNEL_LURKING` flag

**Tasks:**
1. Create `LurkDetector` class with keyword + embedding scoring
2. Create `LurkCooldownManager` for rate limiting
3. Load/cache character topic embeddings at startup
4. Add hook in `bot.py` `on_message()` for non-mentioned messages

### Phase 2: Response Integration (1-2 days)

**Files:**
- `src_v2/agents/engine.py` - Add `lurk_mode` parameter
- `src_v2/discord/bot.py` - Wire lurk detection to response generation

**Tasks:**
1. Create `generate_lurk_response()` method in AgentEngine
2. Inject lurk-specific context into system prompt
3. Handle Discord message sending (no @mention needed)
4. Log lurk responses to memory/history

### Phase 3: Configuration & Admin (1-2 days)

**Files:**
- `src_v2/discord/commands.py` - Add `/lurk` slash commands
- Database migration for `v2_channel_settings`

**Tasks:**
1. Create database table for per-channel settings
2. Implement `/lurk enable|disable|threshold|stats` commands
3. Add server admin permission checks
4. Create opt-out documentation

### Phase 4: Testing & Tuning (1 day)

**Tasks:**
1. Test with various message types
2. Tune threshold (start conservative at 0.8, lower if needed)
3. Verify rate limiting works correctly
4. Test multi-bot scenarios (avoid pile-ons)

### Phase 5: Spam Detection (2-3 days)

**Files:**
- `src_v2/discord/spam_detector.py` - Core detection logic
- `src_v2/discord/commands.py` - Add `/spam` commands
- Database migration for `v2_spam_settings`, `v2_spam_incidents`

**Tasks:**
1. Create `SpamDetector` class with content/file hashing (2-3 hours)
2. Integrate into `on_message()` flow (1-2 hours)
3. Create spam response templates per character (1-2 hours)
4. Implement `/spam` admin commands (2-3 hours)
5. Add delete capability (requires `manage_messages` permission) (1-2 hours)
6. Create mod channel logging (1-2 hours)
7. Test with simulated spam patterns (1-2 hours)

---

## Configuration

```python
# src_v2/config/settings.py

# --- Channel Lurking ---
ENABLE_CHANNEL_LURKING: bool = False  # Feature flag
LURK_CONFIDENCE_THRESHOLD: float = 0.7  # Min score to respond
LURK_CHANNEL_COOLDOWN_MINUTES: int = 30  # Per-channel cooldown
LURK_USER_COOLDOWN_MINUTES: int = 60  # Per-user cooldown
LURK_MAX_DAILY_RESPONSES: int = 20  # Global daily limit
LURK_REQUIRE_QUESTION: bool = False  # Only respond to questions?

# --- Spam Detection ---
ENABLE_SPAM_DETECTION: bool = False  # Feature flag
SPAM_CROSS_POST_THRESHOLD: int = 3  # 3+ channels = spam (2 is OK)
SPAM_TIME_WINDOW_MINUTES: int = 30  # Detection window
SPAM_MIN_CONTENT_LENGTH: int = 50  # Don't track short messages
SPAM_DEFAULT_ACTION: str = "warn"  # warn, delete, silent
SPAM_CALLOUT_COOLDOWN_MINUTES: int = 60  # Don't repeatedly call out same user
```

---

## Data Model

### lurk_triggers.yaml (Per Character)

```yaml
# Required fields
keywords:
  high_relevance: []
  medium_relevance: []
  low_relevance: []

# Optional fields
question_patterns: []
emotional_keywords:
  positive: []
  negative: []

# Pre-computed topic sentences for embedding comparison
topic_sentences:
  - "sentence that captures core expertise 1"
  - "sentence that captures core expertise 2"
```

### Database: v2_channel_settings

| Column | Type | Description |
|--------|------|-------------|
| channel_id | VARCHAR(64) PK | Discord channel ID |
| guild_id | VARCHAR(64) | Server ID |
| lurk_enabled | BOOLEAN | Is lurking enabled? |
| lurk_threshold | FLOAT | Custom threshold (0.0-1.0) |
| created_at | TIMESTAMP | Record creation |
| updated_at | TIMESTAMP | Last update |

### Database: v2_lurk_responses (Analytics)

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL PK | Auto-increment |
| channel_id | VARCHAR(64) | Where we responded |
| user_id | VARCHAR(64) | Who triggered it |
| character_name | VARCHAR(64) | Which bot responded |
| trigger_message | TEXT | Message that triggered |
| confidence_score | FLOAT | Detection confidence |
| response | TEXT | What we said |
| timestamp | TIMESTAMP | When |

---

## Cost Analysis

### Lurk Engagement

| Operation | Cost | Frequency |
|-----------|------|-----------|
| Keyword matching | $0.00 | Every message |
| Embedding (local) | $0.00 | Messages with keyword match |
| LLM response | ~$0.002-0.01 | Only when threshold met (~5-20/day) |

**Daily cost estimate:** $0.04-0.20 (vs $0.50-2.00 if using LLM for detection)

### Spam Detection

| Operation | Cost | Frequency |
|-----------|------|-----------|
| Content hashing | $0.00 | Every message |
| File hashing | $0.00 | Every attachment (<1MB) |
| Character callout response | ~$0.002-0.01 | Only when spam detected (~1-5/day) |

**Daily cost estimate:** $0.01-0.05 (hash-based detection is essentially free)

---

## Edge Cases & Considerations

### Multi-Bot Scenarios

If multiple bots are in the same channel and all have lurking enabled:
- Each bot evaluates independently
- Cooldown prevents pile-ons (30 min channel cooldown)
- Consider: shared cooldown via Redis if running multiple bots

### Private Channels

- Lurking only works in channels the bot can see
- Respect Discord permissions
- Don't lurk in channels marked as "private" or "staff"

### Character Appropriateness

- Some characters (like "therapist" types) might want different behavior
- Support per-character lurk config in `evolution.yaml` or similar

### Message Types to Ignore

```python
LURK_IGNORE_CONDITIONS = [
    lambda m: m.author.bot,  # Other bots
    lambda m: len(m.content) < 10,  # Too short
    lambda m: m.content.startswith('!'),  # Commands
    lambda m: m.content.startswith('/'),  # Slash commands
    lambda m: 'http' in m.content,  # Links (likely sharing, not discussing)
    lambda m: m.type != discord.MessageType.default,  # System messages
]
```

---

## 🚨 Spam Detection & Moderation

### The Problem

Server admins spend significant time manually:
1. **Detecting cross-channel spam** — Users posting identical scripts/content across 5-10+ channels
2. **Cleaning up duplicate files** — Same document posted everywhere
3. **Warning repeat offenders** — Tedious and time-consuming

### What This Feature Does

The bot passively monitors for:

| Spam Type | Detection Method | Threshold |
|-----------|-----------------|----------|
| **Cross-channel text spam** | Content hash matching | Same text in 3+ channels within 30 min |
| **Cross-channel file spam** | File hash + filename matching | Same file in 3+ channels within 30 min |
| **Rapid-fire posting** | Message rate per user | 10+ messages in 60 seconds |

**Key Rule:** Posting to 2 channels is fine ("2 channels got it"). 3+ channels with identical content = spam.

### How Detection Works (No LLM Required)

```python
class SpamDetector:
    """Detect cross-channel spam using content hashing."""
    
    def __init__(self):
        # Track recent posts: {content_hash: [(channel_id, timestamp, message_id)]}
        self.recent_posts: Dict[str, List[Tuple[str, datetime, str]]] = {}
        self.file_posts: Dict[str, List[Tuple[str, datetime, str]]] = {}  # file_hash -> posts
        self.ttl_minutes = 30  # Only track posts within this window
        
    def content_hash(self, text: str) -> str:
        """Normalize and hash text content."""
        # Normalize: lowercase, strip whitespace, remove emojis
        normalized = text.lower().strip()
        normalized = re.sub(r'[\s]+', ' ', normalized)  # Collapse whitespace
        normalized = re.sub(r'[^\w\s]', '', normalized)  # Remove punctuation
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def file_hash(self, attachment: discord.Attachment) -> str:
        """Hash file by content or fall back to name+size."""
        # For small files, hash content; for large, use name+size
        if attachment.size < 1_000_000:  # <1MB
            content = await attachment.read()
            return hashlib.md5(content).hexdigest()
        else:
            # Large files: hash name + size (good enough for spam detection)
            return hashlib.md5(f"{attachment.filename}:{attachment.size}".encode()).hexdigest()
    
    async def check_message(self, message: discord.Message) -> Optional[SpamAlert]:
        """Check if message is cross-channel spam."""
        now = datetime.now()
        self._cleanup_old_entries(now)
        
        guild_id = str(message.guild.id)
        channel_id = str(message.channel.id)
        user_id = str(message.author.id)
        
        # Check text content
        if len(message.content) >= 50:  # Only check substantial messages
            c_hash = self.content_hash(message.content)
            key = f"{guild_id}:{user_id}:{c_hash}"
            
            if key not in self.recent_posts:
                self.recent_posts[key] = []
            
            # Record this post
            self.recent_posts[key].append((channel_id, now, message.id))
            
            # Check for spam (3+ channels)
            unique_channels = set(ch for ch, _, _ in self.recent_posts[key])
            if len(unique_channels) >= 3:
                return SpamAlert(
                    type="cross_channel_text",
                    user_id=user_id,
                    channel_count=len(unique_channels),
                    channels=list(unique_channels),
                    content_preview=message.content[:100],
                    message_ids=[mid for _, _, mid in self.recent_posts[key]]
                )
        
        # Check file attachments
        for attachment in message.attachments:
            f_hash = await self.file_hash(attachment)
            key = f"{guild_id}:{user_id}:{f_hash}"
            
            if key not in self.file_posts:
                self.file_posts[key] = []
            
            self.file_posts[key].append((channel_id, now, message.id))
            
            unique_channels = set(ch for ch, _, _ in self.file_posts[key])
            if len(unique_channels) >= 3:
                return SpamAlert(
                    type="cross_channel_file",
                    user_id=user_id,
                    channel_count=len(unique_channels),
                    channels=list(unique_channels),
                    filename=attachment.filename,
                    message_ids=[mid for _, _, mid in self.file_posts[key]]
                )
        
        return None  # Not spam
```

### Response Options

Admins can configure how the bot responds to detected spam:

**Option 1: Friendly Call-Out (Default)**
```
Hey @SpamUser, I noticed you posted that same script in 5 channels in the 
last 10 minutes 👀 Maybe pick your top 2 channels? The mods will appreciate 
it, and people are more likely to actually read it! 😊
```

**Option 2: Stern Warning**
```
@SpamUser ⚠️ Cross-posting the same content to 5 channels is considered spam 
in this server. Please limit posts to 1-2 relevant channels. Continued 
spamming may result in a timeout.
```

**Option 3: Auto-Delete + DM**
- Bot deletes duplicate messages (keeps first 2)
- Sends DM to user explaining why
- Logs action for admin review

**Option 4: Silent Flag for Admins**
- Bot doesn't say anything publicly
- Sends alert to mod channel or logs
- Admin decides what to do

### Character-Appropriate Spam Responses

Each character handles spam callouts in their own voice:

**Becky (nottaylor):**
> "Babe, I love the hustle, but you just carpet-bombed 6 channels with that script 💣 Maybe chill? Pick your fave 2 and let the work speak for itself!"

**Elena:**
> "Hey! I noticed you're really excited to share that — it showed up in 5 channels! Maybe pick the most relevant one or two? That way people who are actually interested will see it 😊"

**Marcus:**
> "Yo, I get wanting to promote your stuff, but 7 channels with the same post? That's a lot. Pick your best 2 spots and let it breathe, fam."

### Data Model

```sql
-- Server-level spam settings
CREATE TABLE v2_spam_settings (
    guild_id VARCHAR(64) PRIMARY KEY,
    enabled BOOLEAN DEFAULT FALSE,
    cross_post_threshold INT DEFAULT 3,  -- 3+ channels = spam
    time_window_minutes INT DEFAULT 30,  -- Detection window
    action VARCHAR(20) DEFAULT 'warn',   -- warn, delete, silent
    response_style VARCHAR(20) DEFAULT 'friendly',  -- friendly, stern
    whitelist_roles TEXT[],  -- Role IDs exempt from detection
    mod_channel_id VARCHAR(64),  -- Where to log spam alerts
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Spam incident log
CREATE TABLE v2_spam_incidents (
    id SERIAL PRIMARY KEY,
    guild_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    spam_type VARCHAR(30) NOT NULL,  -- cross_channel_text, cross_channel_file, rapid_fire
    channel_count INT NOT NULL,
    channels TEXT[] NOT NULL,  -- Channel IDs where spam was detected
    content_hash VARCHAR(64),
    content_preview TEXT,
    filename VARCHAR(255),
    action_taken VARCHAR(20) NOT NULL,  -- warned, deleted, flagged
    message_ids TEXT[],  -- IDs of spam messages
    detected_at TIMESTAMP DEFAULT NOW()
);

-- Index for querying repeat offenders
CREATE INDEX idx_spam_incidents_user ON v2_spam_incidents(guild_id, user_id, detected_at);
```

### Configuration

```python
# src_v2/config/settings.py

# --- Spam Detection ---
ENABLE_SPAM_DETECTION: bool = False  # Feature flag
SPAM_CROSS_POST_THRESHOLD: int = 3  # 3+ channels = spam (2 is OK)
SPAM_TIME_WINDOW_MINUTES: int = 30  # Detection window
SPAM_MIN_CONTENT_LENGTH: int = 50  # Don't track short messages
SPAM_DEFAULT_ACTION: str = "warn"  # warn, delete, silent
SPAM_CALLOUT_COOLDOWN_MINUTES: int = 60  # Don't call out same user repeatedly
```

### Implementation Tasks

**Phase 5: Spam Detection (2-3 days)**

**Files:**
- `src_v2/discord/spam_detector.py` - Core detection logic
- `src_v2/discord/commands.py` - Add `/spam` commands
- Database migration for `v2_spam_settings`, `v2_spam_incidents`

**Tasks:**
1. Create `SpamDetector` class with content/file hashing (2-3 hours)
2. Integrate into `on_message()` flow (1-2 hours)
3. Create spam response templates per character (1-2 hours)
4. Implement `/spam` admin commands (2-3 hours)
5. Add delete capability (requires `manage_messages` permission) (1-2 hours)
6. Create mod channel logging (1-2 hours)
7. Test with simulated spam patterns (1-2 hours)

### Edge Cases

**Different Files, Same Purpose:**
> "Bear wouldn't get flagged his files are different"

The hash-based approach handles this correctly:
- Different file contents = different hash = not flagged
- Same exact file = same hash = flagged

**Legitimate Multi-Channel Posts:**
- Announcements from admins (whitelist admin roles)
- Bot commands (already ignored)
- Different but related content (different hashes, not flagged)

**User Appeals:**
- Log all incidents for admin review
- Provide `/spam history @user` for admins to see patterns
- Allow admins to pardon false positives

### Permission Requirements

For spam detection to work optimally, the bot needs:

| Permission | Required For |
|------------|-------------|
| `Read Messages` | Detecting spam |
| `Send Messages` | Warning users |
| `Manage Messages` | Auto-deleting spam (optional) |
| `View Channel` | Seeing all channels |

If `Manage Messages` isn't granted, bot will only warn (not delete).

### Success Metrics (Spam Detection)

- **Admin Time Saved:** Hours/week of manual spam cleanup
- **False Positive Rate:** % of flagged posts that weren't actually spam
- **User Behavior Change:** Do repeat offenders learn to stop?
- **Opt-Out Rate:** Servers disabling the feature

**Target:**
- 90%+ spam correctly identified
- <5% false positive rate
- 50%+ reduction in admin manual cleanup

---

## Success Metrics

- **Engagement Rate:** % of lurk responses that get reactions or replies
- **Opt-Out Rate:** How many channels disable lurking
- **User Sentiment:** Do users find it helpful or annoying?
- **False Positive Rate:** Responses to irrelevant topics

**Target:**
- 50%+ lurk responses get positive engagement
- <10% channels opt-out
- <5% false positive rate

---

## Rollout Plan

1. **Alpha (Week 1):** Enable on 1-2 test servers, threshold 0.85
2. **Beta (Week 2):** Lower threshold to 0.75, monitor feedback
3. **GA (Week 3):** Enable by default with threshold 0.7, document opt-out

---

## Related Documents

- `docs/features/PROACTIVE_MESSAGING.md` - Existing proactive engagement (DM-focused)
- `docs/roadmaps/RESPONSE_PATTERN_LEARNING.md` - Learning from feedback
- `src_v2/discord/scheduler.py` - Existing proactive scheduler (can share patterns)

---

## Appendix: Sample lurk_triggers.yaml Files

### Elena (Marine Biologist)

```yaml
keywords:
  high_relevance:
    - coral
    - reef
    - ocean
    - marine biology
    - sea turtle
    - whale
    - dolphin
    - shark
    - kelp forest
    - tide pool
    - scuba diving
    - marine conservation
    - ocean acidification
    - coral bleaching
    - sea urchin
    - plankton
    - bioluminescence
    
  medium_relevance:
    - beach
    - aquarium
    - fishing
    - surfing
    - underwater
    - seaweed
    - jellyfish
    - crab
    - lobster
    - octopus
    - squid
    - national geographic
    - documentary
    
  low_relevance:
    - water
    - swimming
    - vacation
    - california
    - san diego
    - la jolla
    - mexico
    - spanish

topic_sentences:
  - "coral reef restoration and protecting ocean ecosystems from climate change"
  - "marine biology research on sea turtles, whales, and ocean mammals"
  - "scuba diving adventures and underwater exploration stories"
  - "ocean conservation and fighting plastic pollution"
  - "tide pool ecosystems and intertidal marine life"
```

### Marcus (Musician)

```yaml
keywords:
  high_relevance:
    - music
    - guitar
    - songwriting
    - lyrics
    - melody
    - chord
    - band
    - concert
    - album
    - recording
    - studio
    - producing
    - mixing
    
  medium_relevance:
    - spotify
    - vinyl
    - playlist
    - musician
    - singer
    - drummer
    - bass
    - piano
    - keyboard
    - tour
    
  low_relevance:
    - art
    - creative
    - inspiration
    - practice

topic_sentences:
  - "songwriting process and finding inspiration for new music"
  - "guitar techniques and learning to play instruments"
  - "music production and recording in home studios"
  - "concert experiences and live music performances"
  - "music theory and chord progressions"
```

---

**Version History:**
- v1.1 (Nov 25, 2025) - Added spam detection & moderation capabilities based on admin feedback
- v1.0 (Nov 25, 2025) - Initial design document

