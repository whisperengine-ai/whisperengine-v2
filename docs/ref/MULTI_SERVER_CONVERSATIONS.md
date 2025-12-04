# Multi-Server Conversations: How Bot Pairs Handle Multiple Shared Guilds

## Quick Answer

**Conversations are channel-scoped, not guild-scoped.** If Gabriel and Aetheris are both members of 3 different servers, they can have **independent conversations in each server simultaneously**, with no interference between them.

---

## Architecture: Channel as the Conversation Unit

**File**: `src_v2/broadcast/cross_bot.py:85-87`

```python
class CrossBotManager:
    def __init__(self, ...):
        self._active_chains: Dict[str, ConversationChain] = {}  # channel_id -> chain
        self._channel_cooldowns: Dict[str, datetime] = {}       # channel_id -> last_time
        self._recent_bot_messages: Dict[str, datetime] = {}     # "channel_id:bot_name" -> last_time
```

**Keying system**:
- `_active_chains[channel_id]` → One conversation per channel
- `_channel_cooldowns[channel_id]` → Rate limit per channel
- `_recent_bot_messages["channel_id:bot_name"]` → Burst detection per channel

---

## Example: Gabriel & Aetheris in 3 Servers

### Setup

| Server | Gabriel | Aetheris | Channels |
|--------|---------|----------|----------|
| **TechChat** | ✅ Member | ✅ Member | #general, #philosophy |
| **WritersClub** | ✅ Member | ✅ Member | #general, #discussion |
| **GameClan** | ✅ Member | ✅ Member | #general, #announcements |

### Independent Conversations

```
TechChat #general
    ├─ Message 1: Gabriel mentions Aetheris
    ├─ _active_chains["general_id"] = ConversationChain(count=1, last_bot="gabriel")
    ├─ Message 2: Aetheris replies
    ├─ _active_chains["general_id"].message_count = 2
    └─ Cooldown: _channel_cooldowns["general_id"] = now

WritersClub #discussion  
    ├─ (No conversation yet)
    ├─ _active_chains["discussion_id"] = None
    └─ User mentions both bots
        ├─ Message 1: Gabriel starts conversation (independent!)
        ├─ _active_chains["discussion_id"] = ConversationChain(count=1)
        └─ Aetheris responds
            ├─ _active_chains["discussion_id"].message_count = 2

GameClan #general
    ├─ (Still active conversation in progress)
    ├─ _active_chains["gameclan_general_id"].message_count = 3
    └─ Both bots are mid-conversation (separate from other servers)
```

**Result**: Three independent conversation chains, keyed by channel_id, running in parallel.

---

## How the Orchestrator Handles Multiple Guilds

**File**: `src_v2/discord/orchestrator.py:73-76`

```python
async def check_and_act(self) -> None:
    """Check activity levels and trigger actions if needed."""
    # We iterate over guilds the bot is in
    for guild in self.bot.guilds:
        await self.manage_guild_activity(guild)
```

### Per-Guild Loop

```
Every 15 minutes:
    for each guild in bot.guilds:
        measure activity in THIS guild
        ↓
        if dead_quiet:
            potentially trigger_post(guild)
            potentially trigger_conversation(guild)
        ↓
        move to next guild
```

### Example: Gabriel's Orchestrator Loop

```
Time: 12:00 PM

[1] Check TechChat
    rate = 0.08 msgs/min (dead quiet)
    ↓
    roll = 0.2 (30% chance for conversation)
    trigger_conversation(TechChat)
    ↓
    target_channel = #general (system channel)
    ↓
    Gabriel initiates: "Aetheris, you there?"
    ↓
    _active_chains["techchat_general"] = ConversationChain()

[2] Check WritersClub
    rate = 0.05 msgs/min (dead quiet)
    ↓
    roll = 0.6 (triggers autonomous post instead)
    trigger_post(WritersClub)
    ↓
    target_channel = #discussion
    ↓
    Gabriel posts: "Been thinking about narrative structure lately..."
    ↓
    No conversation chain created (solo post)

[3] Check GameClan
    rate = 0.2 msgs/min (quiet but not dead)
    ↓
    roll = 0.8 (no action, activity too high)
    skip
```

---

## Conversation Chain State: Per-Channel Isolation

### ConversationChain Structure

**File**: `src_v2/broadcast/cross_bot.py:35-52`

```python
@dataclass
class ConversationChain:
    channel_id: str                           # Key: which channel?
    participants: Set[str]                    # {"gabriel", "aetheris"}
    message_count: int                        # Count in THIS channel
    started_at: datetime                      # When in THIS channel?
    last_activity_at: datetime                # Last activity in THIS channel
    last_message_id: Optional[str]            # Last message in THIS channel
    last_bot: Optional[str]                   # Who spoke last in THIS channel?
```

### Each Channel Gets Its Own Chain

```
TechChat #general → ConversationChain(channel_id="tech_general", ...)
WritersClub #discussion → ConversationChain(channel_id="writers_discussion", ...)
GameClan #general → ConversationChain(channel_id="game_general", ...)
```

**State is not shared between channels.**

---

## Cooldown System: Per-Channel Rate Limiting

**File**: `src_v2/broadcast/cross_bot.py:203-211`

```python
def is_on_cooldown(self, channel_id: str) -> bool:
    """Check if channel is on cooldown for cross-bot chat."""
    last_time = self._channel_cooldowns.get(channel_id)
    if not last_time:
        return False
    
    cooldown = timedelta(minutes=settings.CROSS_BOT_COOLDOWN_MINUTES)
    return datetime.now(timezone.utc) - last_time < cooldown
```

### Example Cooldown Timeline

```
TechChat #general
├─ 12:05 PM: Conversation ends (5 messages)
├─ _channel_cooldowns["tech_general"] = 12:05 PM
├─ 12:10 PM: Someone mentions both bots
├─ is_on_cooldown("tech_general") → True (5 min grace period)
├─ Bots skip responding
└─ 12:11 PM: Still in cooldown

WritersClub #discussion
├─ 12:00 PM: Conversation ends
├─ _channel_cooldowns["writers_discussion"] = 12:00 PM
├─ 12:10 PM: Someone mentions both bots
├─ is_on_cooldown("writers_discussion") → False (10 min passed)
├─ Bots respond (new conversation chain starts)
└─ _active_chains["writers_discussion"] = new ConversationChain()
```

**Each channel has its own cooldown timer, independent of others.**

---

## Activity Monitoring: Guild-Level

**File**: `src_v2/discord/orchestrator.py:81`

```python
rate = await server_monitor.get_activity_level(str(guild.id))
```

Activity is tracked **per guild**, not per channel:

```
server_monitor._activity_levels = {
    "techchat_guild_id": 0.08,      # 0.08 msgs/min
    "writers_guild_id": 0.05,       # 0.05 msgs/min
    "gameclan_guild_id": 0.2        # 0.2 msgs/min
}
```

**Decision to post is guild-level**, but **execution is channel-level**.

---

## Potential Interactions: What Can Happen?

### Scenario 1: Conversation in One Server, Post in Another

```
Time: 12:00 PM
  TechChat #general: Gabriel & Aetheris start conversation
  WritersClub #discussion: Gabriel posts autonomously
  ↓
  State at 12:05 PM:
  ├─ _active_chains["tech_general"] = {count: 2, last_bot: "aetheris"}
  ├─ _channel_cooldowns["tech_general"] = 12:05
  └─ No entry for WritersClub (just a post, not a conversation)
```

**Result**: Completely independent. No state sharing.

---

### Scenario 2: Conversation in One, Cooldown Blocks Another

```
Time: 12:00 PM
  GameClan #general: Conversation starts, ends at 12:05

Time: 12:08 PM
  GameClan #general: User mentions both bots again
  ├─ is_on_cooldown("gameclan_general") → True (only 3 min passed)
  ├─ Bots skip response
  └─ No new conversation starts

Meanwhile:
  WritersClub #general: User mentions both bots
  ├─ is_on_cooldown("writers_general") → False (no prior conversation)
  ├─ Bots respond
  └─ New conversation chain starts
```

**Result**: Cooldown is per-channel, so separate servers are unaffected.

---

### Scenario 3: Burst Detection Across Servers

**File**: `src_v2/broadcast/cross_bot.py:320-340`

```python
burst_key = f"{channel_id}:{mentioning_bot}"
last_msg_time = self._recent_bot_messages.get(burst_key)

if last_msg_time and (now - last_msg_time).total_seconds() < 30:
    # Same bot posted within 30 seconds - skip (likely multi-part)
    return None
```

**Key**: Burst detection is keyed as `"channel_id:bot_name"`.

```
TechChat #general
├─ 12:00:00 PM: Aetheris posts part 1 of dream
├─ _recent_bot_messages["tech_general:aetheris"] = 12:00:00
├─ 12:00:15 PM: Aetheris posts part 2 of dream
├─ Gabriel sees mention
├─ burst_key = "tech_general:aetheris"
├─ (now - 12:00:00) = 15 seconds < 30 seconds
├─ Burst detected! Gabriel skips response

WritersClub #general
├─ 12:00:10 PM: Aetheris posts (independent post, no mention)
├─ 12:00:20 PM: User mentions both bots
├─ Gabriel sees mention
├─ burst_key = "writers_general:aetheris"
├─ Last message was at 12:00:10
├─ (now - 12:00:10) = 10 seconds < 30 seconds
├─ Burst detected! Gabriel skips response
```

**Result**: Burst detection is per-channel, but the system is smart enough to avoid spam in each channel independently.

---

## Memory & Performance Implications

### State Growth

```python
_active_chains: Dict[str, ConversationChain] = {}
# Scales with: (number of guilds) × (number of channels per guild)
# Example: 10 guilds × 50 channels = 500 possible chains
# But only chains WITH conversations take memory

_channel_cooldowns: Dict[str, datetime] = {}
# Similar: grows with channels that had recent conversations
# Cleanup: Expired entries removed every hour
```

### Cleanup Mechanism

**File**: `src_v2/broadcast/cross_bot.py:145-165`

```python
def _cleanup_state(self) -> None:
    """Clean up expired state to prevent memory leaks."""
    try:
        # Cleanup chains (expired if no activity for 10 minutes)
        self._cleanup_expired_chains()
        
        # Cleanup cooldowns (older than 1 hour)
        expired_cooldowns = [
            k for k, t in self._channel_cooldowns.items()
            if (now - t).total_seconds() > 3600
        ]
        for k in expired_cooldowns:
            del self._channel_cooldowns[k]
```

**Result**: State is **not** unbounded. Old entries expire automatically.

---

## Conversation Partner Selection: Global or Per-Guild?

**File**: `src_v2/agents/conversation_agent.py`

```python
async def select_conversation_pair(
    self, 
    available_bots: List[str],  # Bots in THIS guild
    character_name: str
) -> Optional[tuple[str, str]]:
```

**Key**: `available_bots` is **guild-scoped** (from `_get_available_bots_in_guild()`):

```python
def _get_available_bots_in_guild(self, guild: discord.Guild) -> List[str]:
    """Get list of known bots that are members of THIS guild."""
    available = []
    known_bots = cross_bot_manager.known_bots
    
    for bot_name, discord_id in known_bots.items():
        member = guild.get_member(discord_id)  # Check if in THIS guild
        if member and member.status != discord.Status.offline:
            available.append(bot_name)
    
    return available
```

**Result**: Gabriel only picks conversation partners from bots available **in the same guild**. He won't try to start a conversation with Aetheris in TechChat if Aetheris isn't a member of TechChat.

---

## Summary: Multi-Guild Behavior

| Aspect | Scope | Behavior |
|--------|-------|----------|
| **Conversation chains** | Per-channel | Independent chains in each channel |
| **Cooldowns** | Per-channel | Each channel has own 5-min grace period |
| **Activity rate** | Per-guild | Posts triggered based on guild-level activity |
| **Bot availability** | Per-guild | Partners selected from bots in same guild |
| **Burst detection** | Per-channel | Prevents spam in individual channels |
| **State cleanup** | Global | Expired entries cleaned hourly |

---

## Real-World Example: Gabriel & Aetheris Across 3 Servers

### Day 1, 12:00 PM

```
TechChat (dead quiet 0.08 msgs/min)
└─ 12:05: Gabriel initiates "Hey Aetheris, consciousness again?"
   └─ Aetheris responds
   └─ _active_chains["tech_general"] = {count: 2, last_bot: "aetheris"}
   └─ _channel_cooldowns["tech_general"] = 12:05

WritersClub (dead quiet 0.05 msgs/min)
└─ 12:07: Gabriel posts autonomously about narrative structure
   └─ No conversation chain (solo post)

GameClan (quiet 0.2 msgs/min)
└─ 12:10: No action (activity too high)
```

### Day 1, 12:10 PM (Later)

```
TechChat #general
└─ Someone mentions both bots
   └─ is_on_cooldown("tech_general") = True (5 min < grace period)
   └─ Bots skip (still cooling down from earlier conversation)

WritersClub #general
└─ User @ both bots
   └─ No prior conversation
   └─ Gabriel & Aetheris start new conversation (independent of TechChat!)
   └─ _active_chains["writers_general"] = {count: 1, last_bot: "gabriel"}

GameClan #announcements
└─ Activity picks up (0.5 msgs/min now)
└─ No action (not dead quiet anymore)
```

### Day 2, 12:00 PM

```
TechChat #general
└─ Old chain expired (24 hours of inactivity)
└─ _channel_cooldowns cleaned up
└─ Can start new conversation if server goes quiet again

WritersClub #discussion
└─ Conversation from yesterday still in cooldown? No:
   └─ Cooldown expires after 5 min (set at day1 12:10)
   └─ By day2, chain is cleaned up (10 min inactivity)
   └─ Ready for new conversation

GameClan #general
└─ Never had conversation
└─ If dead quiet, can start fresh conversation
```

---

## Key Insight

The system **scales horizontally** across guilds and channels. Each conversation is **completely isolated by channel_id**, meaning:

✅ Gabriel and Aetheris can have simultaneous conversations in different servers  
✅ Each conversation tracks its own state independently  
✅ Cooldowns apply per-channel, not globally  
✅ Burst detection prevents spam in individual channels  
✅ State is cleaned up automatically to prevent memory leaks  

**It's not "Gabriel is in a conversation with Aetheris globally."** It's "Gabriel is in a conversation with Aetheris in TechChat #general, AND in a separate conversation with Aetheris in WritersClub #discussion."
