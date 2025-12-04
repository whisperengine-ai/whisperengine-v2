# Channel Selection for Bot Posts & Conversations

## Overview

WhisperEngine uses a **hierarchical channel selection strategy** that prioritizes:
1. **Explicit configuration** (if set)
2. **System channels** (Discord's designated "welcome" channels)
3. **Common naming heuristics** ("general", "chat", "lounge")
4. **Fallback to any writeable text channel**

Channel selection happens at **two different points**:
- **Autonomous posts** (single bot initiates)
- **Bot-to-bot conversations** (paired bots engage)

---

## Channel Selection Logic: `_get_target_channel()`

**File**: `src_v2/discord/orchestrator.py:220`

### The Algorithm

```python
def _get_target_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
    """Find the best channel to post in."""
    # 1. Try System Channel (often "general" or "welcome")
    if guild.system_channel and guild.permissions_for(guild.me).send_messages:
        return guild.system_channel
        
    # 2. Try channels with common names
    common_names = ["general", "chat", "lounge", "main", "discussion"]
    for name in common_names:
        for channel in guild.text_channels:
            if name in channel.name.lower() and channel.permissions_for(guild.me).send_messages:
                return channel
                
    # 3. Fallback: First text channel we can speak in
    for channel in guild.text_channels:
        if channel.permissions_for(guild.me).send_messages:
            return channel
            
    return None
```

### Priority Order

| Priority | Method | Example | Rationale |
|----------|--------|---------|-----------|
| **1** | System Channel | "welcome" (Discord auto-designated) | Discord's official "main" channel for the server |
| **2** | Common names (in order) | "general", "chat", "lounge" | Human convention for public discussion |
| **3** | Any writeable channel | First text channel bot can access | Fallback: at least post *somewhere* |
| **4** | None | (No channels found) | Bot has no permissions; abort |

### Permission Checking

```python
guild.permissions_for(guild.me).send_messages
```

This checks: **Does the bot have `send_messages` permission in this channel?**

- ✅ If yes: Channel is eligible
- ❌ If no: Channel is skipped (even if it's "general")

---

## Autonomous Posts: `trigger_post()`

**File**: `src_v2/discord/orchestrator.py:110`

### Flow

```
ActivityOrchestrator.check_and_act()
    ↓
    for each guild:
        measure activity rate (msgs/min over 30 min)
        ↓
        if dead_quiet (< 0.1 msgs/min) OR quiet (< 0.5 msgs/min):
            ↓
            trigger_post(guild)
            ↓
            target_channel = _get_target_channel(guild)
            ↓
            PostingAgent.generate_and_schedule_post(target_channel_id)
            ↓
            Generate topic (goal-driven)
            ↓
            Generate content (LLM)
            ↓
            Queue to BroadcastManager (broadcasts to Discord later)
```

### Example

**Guild: "TechChat"**
- System channel: "welcome"
- Text channels: "general", "dev-discussion", "random"
- Bot permissions: Can write to all

**Selection**:
1. Check system channel → "welcome" exists and is writeable
2. **Return "welcome"** → Post goes here

**If "welcome" wasn't writeable**:
1. Check common names → Find "general" (match!)
2. **Return "general"** → Post goes here

**If no common names and no system channel**:
1. Try fallback → Find first writeable channel ("dev-discussion")
2. **Return "dev-discussion"** → Post goes here

---

## Bot-to-Bot Conversations: `trigger_conversation()`

**File**: `src_v2/discord/orchestrator.py:130`

Bot-to-bot conversations use a **slightly different** channel selection:

### Flow

```
ActivityOrchestrator.check_and_act()
    ↓
    for each guild:
        if dead_quiet (< 0.1 msgs/min):
            ↓
            roll dice: 30% chance to start conversation
            ↓
            trigger_conversation(guild)
            ↓
            [1] Check override setting
            ├─ if BOT_CONVERSATION_CHANNEL_ID is set:
            │  target_channel = bot.get_channel(BOT_CONVERSATION_CHANNEL_ID)
            │  ↓
            └─ if not found or not set:
               [2] Use standard selection
               target_channel = _get_target_channel(guild)
            ↓
            [3] Check cooldown (cross-bot grace period)
            ├─ if channel on cooldown (5 min):
            │  return (skip to avoid rapid-fire)
            │  ↓
            └─ if not on cooldown: continue
            ↓
            [4] Check active conversation
            ├─ if conversation in progress:
            │  return (let it finish)
            │  ↓
            └─ if no active conversation: continue
            ↓
            [5] Get available bots in guild
            ├─ if < 2 bots online:
            │  return (need pair)
            │  ↓
            └─ if >= 2 bots: continue
            ↓
            [6] Select conversation partner
            │  target_bot, topic = select_conversation_pair()
            ↓
            [7] Generate opener (LLM)
            │  opener = generate_opener(my_name, target_bot, topic)
            ↓
            [8] Send to channel
            │  await target_channel.send(opener)
            │  record_response() → marks chain start
```

### Key Differences from Autonomous Posts

| Feature | Autonomous Post | Bot Conversation |
|---------|-----------------|------------------|
| **Channel override** | None (always auto-detect) | `BOT_CONVERSATION_CHANNEL_ID` |
| **Cooldown check** | No (rate-limited by orchestrator) | Yes (5 min per channel) |
| **Active conversation check** | N/A (single post) | Yes (prevents overlapping chats) |
| **Bot pairing** | N/A | Required (≥2 bots in guild) |
| **Fallback behavior** | Post anyway if found channel | Fall back to autonomous post |

---

## Configuration: Overrides & Settings

**File**: `src_v2/config/settings.py`

### Autonomous Posting Configuration

```python
ENABLE_AUTONOMOUS_POSTING: bool = True
ENABLE_BOT_CONVERSATIONS: bool = False  # Master switch for bot-to-bot

ACTIVITY_CHECK_INTERVAL_MINUTES: int = 15
ACTIVITY_DEAD_QUIET_THRESHOLD: float = 0.1  # msgs/min (< 3 in 30 min)
ACTIVITY_QUIET_THRESHOLD: float = 0.5       # msgs/min
```

### Bot Conversation Configuration

```python
BOT_CONVERSATION_CHANNEL_ID: Optional[str] = None  # Override channel for all conversations
CROSS_BOT_RESPONSE_CHANCE: float = 0.7  # 70% chance to respond to mention
CROSS_BOT_COOLDOWN_MINUTES: int = 5     # Grace period between chains
CROSS_BOT_MAX_CHAIN: int = 5            # Max messages per conversation
```

**Example `.env` override**:
```bash
# Force all bot conversations to happen in #broadcast
BOT_CONVERSATION_CHANNEL_ID=1234567890
```

---

## Channel Permission Checks

The bot respects Discord permissions and will **skip channels** where it lacks `send_messages`:

```python
# This is checked for EVERY candidate channel
if not channel.permissions_for(guild.me).send_messages:
    continue  # Skip to next channel
```

**Common reasons a channel is skipped:**
- Channel is bot-only (read-only for humans)
- Channel has explicit role restrictions
- Bot role is too low in hierarchy
- Channel is archived/locked

---

## Fallback Behavior

### If No Suitable Channel Found

**For autonomous posts:**
```python
if not target_channel:
    logger.warning(f"No suitable channel found in {guild.name} for autonomous post")
    return  # Post is silently skipped
```

**For bot conversations:**
```python
if not target_channel:
    logger.warning(f"No suitable channel found in {guild.name} for bot conversation")
    
    # Fall back to posting instead
    if settings.ENABLE_AUTONOMOUS_POSTING:
        await self.trigger_post(guild)
    return
```

---

## Activity-Based Posting Thresholds

Channel selection is tied to **server activity levels**:

**File**: `src_v2/discord/orchestrator.py:80`

```python
rate = await server_monitor.get_activity_level(str(guild.id))
# Rate is calculated as: messages/minute over last 30 minutes

is_dead_quiet = rate < 0.1   # < 3 messages in 30 min
is_quiet = rate < 0.5        # < 15 messages in 30 min

# Posting probability by activity level:
if is_dead_quiet:
    # 30% chance: start bot conversation
    # 40% chance: post autonomously
    # 30% chance: do nothing
    
elif is_quiet:
    # 30% chance: post autonomously
    # 70% chance: do nothing
    
else:
    # Active server - don't post
    # Let ReactionAgent handle engagement instead
    pass
```

---

## Available Bots Detection

For bot-to-bot conversations, the system must find **eligible bots in the guild**:

**File**: `src_v2/discord/orchestrator.py:200`

```python
def _get_available_bots_in_guild(self, guild: discord.Guild) -> List[str]:
    """Get list of known bots that are members of this guild."""
    available = []
    known_bots = cross_bot_manager.known_bots  # Loaded at startup from Redis
    
    for bot_name, discord_id in known_bots.items():
        member = guild.get_member(discord_id)
        if member and member.status != discord.Status.offline:
            available.append(bot_name)
    
    return available
```

**Requirements for a bot to be available:**
1. ✅ Bot is registered in Redis (knows about it)
2. ✅ Bot is a member of the guild (has joined)
3. ✅ Bot is online (status != offline)
4. ✅ At least 2 bots needed for conversation (self + partner)

---

## Example Scenarios

### Scenario 1: Post to "General" Channel

**Guild**: "MyServer"
- System channel: None
- Channels: "general", "random", "announcements"
- Activity: Dead quiet (0.05 msgs/min)

**Selection Flow:**
1. Check system channel → None found
2. Check common names → Find "general" ✅
3. **Result**: Post to "general"

---

### Scenario 2: Override for Broadcast

**Guild**: "MyServer"
- System channel: "welcome"
- Channels: "general", "announcements", "broadcast"
- Activity: Dead quiet (0.05 msgs/min)
- **Setting**: `BOT_CONVERSATION_CHANNEL_ID=broadcast_channel_id`

**For bot conversation:**
1. Check override → `BOT_CONVERSATION_CHANNEL_ID` found
2. Get channel by ID → "broadcast" ✅
3. **Result**: Conversation in "broadcast"

**For autonomous post:**
1. No override exists (only for conversations)
2. Check system channel → "welcome" ✅
3. **Result**: Post to "welcome"

---

### Scenario 3: Restricted Permissions

**Guild**: "MyServer"
- System channel: "welcome" (bot cannot write)
- Channels: "general" (bot can write), "announcements" (bot cannot write)
- Activity: Quiet (0.2 msgs/min)

**Selection Flow:**
1. Check system channel → "welcome" found
2. **Check permissions** → Bot lacks `send_messages` ❌
3. Check common names → Find "general"
4. **Check permissions** → Bot has `send_messages` ✅
5. **Result**: Post to "general"

---

### Scenario 4: No Suitable Channel

**Guild**: "MyServer"
- System channel: None
- Channels: "announcements" (read-only), "admin-only" (restricted), "logs" (restricted)
- Activity: Dead quiet

**Selection Flow:**
1. Check system channel → None found
2. Check common names → None match
3. Fallback → Try any channel
4. **Check permissions** → All channels blocked ❌
5. **Result**: No post (silently skipped)

---

## Why This Matters

The channel selection strategy **balances**:

| Goal | Mechanism |
|------|-----------|
| **Discoverability** | Use "general" / system channels (where humans congregate) |
| **Respect permissions** | Skip channels bot can't write to |
| **Configuration flexibility** | Allow override for specific use cases |
| **Graceful degradation** | Fall back to any writeable channel |
| **Activity scaling** | Only post when server is quiet (don't spam active servers) |

The system ensures bots **post to appropriate, accessible channels** without requiring manual configuration (though it supports it).

---

## Related Systems

- **BroadcastManager** (`src_v2/broadcast/manager.py`): Queues posts for Discord delivery
- **ServerMonitor** (`src_v2/intelligence/activity.py`): Measures guild activity rates
- **CrossBotManager** (`src_v2/broadcast/cross_bot.py`): Tracks conversation state & cooldowns
- **ConversationAgent** (`src_v2/agents/conversation_agent.py`): Generates conversation openers
