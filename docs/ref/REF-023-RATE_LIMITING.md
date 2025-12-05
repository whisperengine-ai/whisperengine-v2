# REF-023: Rate Limiting & Cooldowns

**Status:** Active  
**Last Updated:** December 5, 2025  
**Author:** WhisperEngine Team

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Operational necessity |
| **Purpose** | Prevent bot spam, control costs, ensure quality over quantity |
| **Key Insight** | With 12 bots, unconstrained activity can overwhelm channels |

---

## Overview

WhisperEngine implements multiple layers of rate limiting to ensure bots contribute meaningfully without overwhelming conversations. This is especially important with multiple bots in shared channels.

### Design Philosophy

> **Quality over Quantity** — Every bot interaction should add value. Rate limits force bots to be selective about when they participate.

---

## Rate Limiting Categories

### 1. Lurk Responses (Unsolicited Replies)

When the bot responds to messages it wasn't mentioned in.

| Setting | Default | Purpose |
|---------|---------|---------|
| `LURK_CHANNEL_COOLDOWN_MINUTES` | 60 | Wait time before lurking in same channel again |
| `LURK_USER_COOLDOWN_MINUTES` | 60 | Wait time before lurking to same user again |
| `LURK_DAILY_MAX_RESPONSES` | 10 | Maximum lurk responses per day (global) |

**Implementation:** `src_v2/discord/lurk_detector.py`

```python
async def can_respond(self, channel_id: str, user_id: str) -> Tuple[bool, str]:
    # Check daily limit
    if daily_count >= self.max_daily_responses:
        return False, "daily_limit"
    
    # Check channel cooldown
    if await redis.exists(f"lurk:cooldown:channel:{channel_id}"):
        return False, "channel_cooldown"
    
    # Check user cooldown
    if await redis.exists(f"lurk:cooldown:user:{user_id}"):
        return False, "user_cooldown"
    
    return True, "allowed"
```

---

### 2. Cross-Bot Conversations

When bots talk to each other.

| Setting | Default | Purpose |
|---------|---------|---------|
| `CROSS_BOT_MAX_CHAIN` | 3 | Max messages in a single bot-to-bot exchange |
| `CROSS_BOT_COOLDOWN_MINUTES` | 360 | Wait time (6 hours) before same bots can chat again |
| `CROSS_BOT_RESPONSE_CHANCE` | 0.35 | Probability of responding to another bot (35%) |
| `BOT_CONVERSATION_MAX_TURNS` | 3 | Max back-and-forth turns per conversation |

**Implementation:** `src_v2/broadcast/cross_bot.py`

```python
async def should_respond(self, mention: CrossBotMention) -> bool:
    # Check chain length
    chain = self._active_chains.get(mention.channel_id)
    if chain and chain.message_count >= settings.CROSS_BOT_MAX_CHAIN:
        return False
    
    # Check cooldown with this specific bot
    cooldown_key = f"cross_bot:cooldown:{self._bot_name}:{mention.mentioning_bot}"
    if await redis.exists(cooldown_key):
        return False
    
    # Probabilistic response
    if random.random() > settings.CROSS_BOT_RESPONSE_CHANCE:
        return False
    
    return True
```

---

### 3. Emoji Reactions

When the bot reacts to messages with emojis.

| Setting | Default | Purpose |
|---------|---------|---------|
| `REACTION_CHANNEL_HOURLY_MAX` | 5 | Max reactions per channel per hour |
| `REACTION_SAME_USER_COOLDOWN_SECONDS` | 300 | Wait 5 minutes before reacting to same user |
| `REACTION_DAILY_MAX` | 50 | Total reactions per day |

**Implementation:** `src_v2/agents/reaction_agent.py`

---

### 4. Proactive Posting

When the bot initiates conversation without being prompted.

| Setting | Default | Purpose |
|---------|---------|---------|
| `PROACTIVE_CHECK_INTERVAL_MINUTES` | 120 | How often to check if should post |
| `PROACTIVE_MIN_IDLE_MINUTES` | 30 | Channel must be idle this long |
| `PROACTIVE_DAILY_MAX` | 5 | Max proactive posts per day |

**Implementation:** `src_v2/discord/scheduler.py`

---

### 5. Content Generation

Limits on expensive content generation.

| Setting | Default | Purpose |
|---------|---------|---------|
| `DAILY_IMAGE_QUOTA` | 5 | Max images per user per day |
| `DAILY_AUDIO_QUOTA` | 10 | Max voice clips per user per day |
| `DREAM_COOLDOWN_DAYS` | 7 | Days between dream shares to same user |

**Implementation:** `src_v2/core/quota.py`

---

### 6. Session & Memory

| Setting | Default | Purpose |
|---------|---------|---------|
| `SESSION_TIMEOUT_MINUTES` | 30 | Session closes after this idle time |
| `SUMMARY_MESSAGE_THRESHOLD` | 20 | Messages before summarization |

---

## Redis Key Patterns

Rate limits are tracked in Redis for persistence across restarts:

| Key Pattern | Purpose | TTL |
|-------------|---------|-----|
| `lurk:daily:{date}` | Daily lurk counter | Until midnight |
| `lurk:cooldown:channel:{id}` | Channel cooldown | `LURK_CHANNEL_COOLDOWN_MINUTES` |
| `lurk:cooldown:user:{id}` | User cooldown | `LURK_USER_COOLDOWN_MINUTES` |
| `cross_bot:cooldown:{bot1}:{bot2}` | Bot pair cooldown | `CROSS_BOT_COOLDOWN_MINUTES` |
| `cross_bot:chain:{channel_id}` | Active conversation chain | 10 minutes |
| `reaction:channel:{id}:hourly` | Hourly reaction count | 1 hour |
| `reaction:user:{id}:cooldown` | User reaction cooldown | `REACTION_SAME_USER_COOLDOWN_SECONDS` |
| `reaction:daily:{date}` | Daily reaction count | Until midnight |
| `quota:image:{user_id}:{date}` | Daily image quota | Until midnight |
| `quota:audio:{user_id}:{date}` | Daily audio quota | Until midnight |

---

## Configuration by Bot Type

### Production Bots (nottaylor)
```env
# Conservative limits for real users
LURK_DAILY_MAX_RESPONSES=10
CROSS_BOT_RESPONSE_CHANCE=0.35
BOT_CONVERSATION_MAX_TURNS=3
REACTION_DAILY_MAX=50
```

### Test Bots (aria, dream, jake, etc.)
```env
# Same limits to test realistic behavior
LURK_DAILY_MAX_RESPONSES=10
CROSS_BOT_RESPONSE_CHANCE=0.35
BOT_CONVERSATION_MAX_TURNS=3
```

### Personal Bots (dotty, gabriel, aetheris)
```env
# Can be slightly more active in personal contexts
LURK_DAILY_MAX_RESPONSES=10
CROSS_BOT_RESPONSE_CHANCE=0.35
```

---

## Tuning Guidelines

### Too Quiet?
```env
# Increase these
LURK_DAILY_MAX_RESPONSES=15
CROSS_BOT_RESPONSE_CHANCE=0.5
REACTION_DAILY_MAX=75
```

### Too Noisy?
```env
# Decrease these
LURK_DAILY_MAX_RESPONSES=5
CROSS_BOT_RESPONSE_CHANCE=0.2
LURK_CHANNEL_COOLDOWN_MINUTES=120
CROSS_BOT_COOLDOWN_MINUTES=480  # 8 hours
```

### Multi-Bot Channels
With many bots, reduce individual activity:
```env
# Per-bot limits should account for N bots
# 10 lurks × 12 bots = 120 potential lurks/day
# Consider: 5 lurks × 12 bots = 60 lurks/day
LURK_DAILY_MAX_RESPONSES=5
CROSS_BOT_RESPONSE_CHANCE=0.25
```

---

## Monitoring Rate Limits

### Check Current State

```bash
# Connect to Redis
redis-cli

# Check lurk state
GET lurk:daily:2025-12-05
KEYS lurk:cooldown:*

# Check cross-bot state
KEYS cross_bot:*

# Check reaction state
GET reaction:daily:2025-12-05
KEYS reaction:channel:*
```

### Reset Cooldowns (Emergency)

```bash
# Clear all lurk cooldowns
redis-cli KEYS "lurk:cooldown:*" | xargs redis-cli DEL

# Clear cross-bot cooldowns
redis-cli KEYS "cross_bot:cooldown:*" | xargs redis-cli DEL

# Reset daily counters (will auto-reset at midnight anyway)
redis-cli DEL lurk:daily:2025-12-05
redis-cli DEL reaction:daily:2025-12-05
```

---

## Decision Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    MESSAGE RECEIVED                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │ Is bot mentioned?   │
                   └─────────────────────┘
                      │              │
                     YES            NO
                      │              │
                      ▼              ▼
              ┌──────────────┐  ┌──────────────────────┐
              │ Always reply │  │ Check lurk limits    │
              └──────────────┘  │ - Daily max?         │
                                │ - Channel cooldown?  │
                                │ - User cooldown?     │
                                │ - Topic relevant?    │
                                └──────────────────────┘
                                         │
                              ┌──────────┴──────────┐
                             PASS               FAIL
                              │                   │
                              ▼                   ▼
                   ┌──────────────────┐    ┌───────────┐
                   │ Maybe lurk reply │    │ Ignore    │
                   │ (probabilistic)  │    └───────────┘
                   └──────────────────┘
```

---

## Quick Reference

| Feature | Key Settings | Recommended for 12 Bots |
|---------|--------------|-------------------------|
| **Lurk** | `LURK_DAILY_MAX_RESPONSES`, `LURK_CHANNEL_COOLDOWN_MINUTES` | 10/day, 60min cooldown |
| **Cross-Bot** | `CROSS_BOT_RESPONSE_CHANCE`, `CROSS_BOT_MAX_CHAIN` | 35% chance, 3 max chain |
| **Reactions** | `REACTION_DAILY_MAX`, `REACTION_CHANNEL_HOURLY_MAX` | 50/day, 5/hour/channel |
| **Proactive** | `PROACTIVE_CHECK_INTERVAL_MINUTES` | 120min (2 hours) |
| **Images** | `DAILY_IMAGE_QUOTA` | 5/user/day |

---

## Related Documentation

- [REF-018: Message Storage & Retrieval](./REF-018-MESSAGE_STORAGE_RETRIEVAL.md) — Redis key patterns
- [REF-014-BOT_TO_BOT](./REF-018-BOT_TO_BOT.md) — Cross-bot communication details
- [BOT_CONVERSATION_SELECTION](./BOT_CONVERSATION_SELECTION.md) — How bots decide to respond
