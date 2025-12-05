# REF-024: Inter-Bot Communication Architecture

**Type**: REF (System Reference)  
**Version**: 1.0.0  
**Last Updated**: 2025-12-05  
**Origin**: Human-AI collaborative documentation of existing system

## Overview

WhisperEngine's multi-bot architecture enables organic information sharing between AI characters. Rather than implementing explicit "bot-to-bot messaging," the system uses three complementary approaches inspired by different coordination paradigms:

1. **Stigmergic Discovery** - Indirect coordination through shared artifacts
2. **Gossip Protocol** - Event-driven information propagation  
3. **Cross-Bot Conversations** - Direct Discord-based interactions

These mechanisms work together to create the illusion of a shared world where characters can reference each other's observations without breaking the fourth wall.

---

## 1. Stigmergic Discovery (Indirect Coordination)

### What is Stigmergy?

Stigmergy is a coordination mechanism observed in ant colonies and termite mounds: agents modify their environment, and other agents respond to those modifications without direct communication. In WhisperEngine, bots leave "pheromone trails" in the form of shared artifacts that other bots can discover.

### Architecture

**Storage**: `whisperengine_shared_artifacts` collection in Qdrant (shared across all bots)

**Key Files**:
- `src_v2/memory/shared_artifacts.py` - `SharedArtifactManager` class
- `src_v2/agents/context_builder.py` - Discovery injection (lines 83-103)

### Artifact Types

| Type | Description | Example |
|------|-------------|---------|
| `epiphany` | Significant insight about a user | "Mark seems to approach problems systematically" |
| `diary` | Bot's reflective journal entry | Daily diary excerpts |
| `dream` | Bot's dream content | Dream journal posts |

### Flow

```
1. Bot A generates an epiphany during conversation
   → SharedArtifactManager.store_artifact(
       artifact_type="epiphany",
       content="User expressed excitement about new job",
       source_bot="elena",
       user_id="123456789",
       confidence=0.85
     )
   → Stored with embedding in shared Qdrant collection

2. Later, Bot B is responding to same user
   → ContextBuilder queries shared artifacts:
      SharedArtifactManager.discover_artifacts(
        query=user_message,
        artifact_types=["epiphany", "diary", "dream"],
        exclude_bot="nottaylor",  # Don't see own artifacts
        user_id="123456789",
        limit=3
      )
   → Returns semantically similar artifacts from other bots

3. Artifacts injected into Bot B's system prompt:
   [INSIGHTS FROM OTHER CHARACTERS]
   - Elena noticed: User expressed excitement about new job
   - Dream noticed: User prefers morning conversations
```

### Configuration

```bash
# Enable/disable stigmergic discovery
ENABLE_STIGMERGIC_DISCOVERY=true

# Minimum confidence for artifacts to be discoverable
STIGMERGIC_CONFIDENCE_THRESHOLD=0.7

# Maximum artifacts to inject per response
STIGMERGIC_DISCOVERY_LIMIT=3
```

### Why Stigmergy?

- **No direct messaging** - Bots don't need to "talk" to each other
- **Temporal decoupling** - Artifacts persist; discovery happens when relevant
- **Emergent coordination** - Bots naturally build on each other's observations
- **Privacy-preserving** - Artifacts filtered by user_id (only see same user's artifacts)

---

## 2. Gossip Protocol (Event-Driven Propagation)

### Overview

When a significant event happens with one character, other characters can be notified via the "gossip" system. This creates the sense that bots exist in a shared universe where news travels.

### Architecture

**Key Files**:
- `src_v2/universe/bus.py` - `UniverseEventBus`, `UniverseEvent` class
- `src_v2/universe/detector.py` - `EventDetector` (detects significant events)
- `src_v2/universe/privacy.py` - `PrivacyManager` (controls sharing)
- `src_v2/workers/tasks/social_tasks.py` - Gossip processing

### Event Types

```python
class EventType(str, Enum):
    USER_UPDATE = "user_update"          # Major life event (new job, moved)
    EMOTIONAL_SPIKE = "emotional_spike"  # User notably happy/sad
    TOPIC_DISCOVERY = "topic_discovery"  # User revealed new interest
    GOAL_ACHIEVED = "goal_achieved"      # User completed something
```

### Event Flow

```
1. User tells Elena about getting a new job
   → EventDetector analyzes message (regex + LLM intents)
   → Detects "career" life update

2. Elena publishes event to bus:
   event_bus.publish(UniverseEvent(
     event_type=EventType.USER_UPDATE,
     user_id="123456789",
     source_bot="elena",
     summary="User got a new job at a tech company",
     topic="career",
     propagation_depth=0
   ))

3. Event bus checks privacy:
   - Is topic sensitive? (health, finances, relationships → BLOCKED)
   - Has user opted out of cross-bot sharing? → BLOCKED
   - Propagation depth > 1? → BLOCKED (prevents infinite loops)

4. If allowed, event queued via arq:
   task_queue.enqueue_gossip(event)

5. Worker processes event:
   - Gets eligible recipients (bots where user has FRIEND+ trust)
   - Injects "gossip memory" into each eligible bot's memory
   - Other bots can now naturally reference the information
```

### Privacy Protections

**Sensitive Topics (never shared)**:
```python
SENSITIVE_TOPICS = frozenset([
    "health", "medical", "doctor", "therapy", "medication", "diagnosis",
    "finance", "money", "debt", "salary", "income", "bankrupt",
    "relationship", "dating", "partner", "divorce", "breakup",
    "legal", "lawsuit", "arrest", "crime", "court",
    "secret", "private", "confidential", "don't tell",
])
```

**Trust Requirements**:
- Minimum trust score: 20 (FRIEND level)
- User must have existing relationship with target bot

**User Controls** (stored in `v2_user_privacy_settings`):
```python
{
    "share_with_other_bots": True,    # Master switch
    "share_across_planets": True,     # Future: multi-server
    "allow_bot_introductions": False, # Bots can introduce user to each other
    "invisible_mode": False           # Hidden from all cross-bot features
}
```

### Configuration

```bash
# Enable/disable gossip system
ENABLE_UNIVERSE_EVENTS=true
```

### Detection Methods

**LLM-Based (preferred)**: Classifier returns `intents: ["life_update"]`

**Regex Fallback**:
```python
LIFE_UPDATE_PATTERNS = [
    (r"\b(got a new job|started new job|got promoted)\b", "career"),
    (r"\b(moving to|moved to|relocating to)\b", "relocation"),
    (r"\b(graduating|graduated|got my degree)\b", "education"),
    # ... etc
]
```

---

## 3. Cross-Bot Conversations (Direct Interaction)

### Overview

When bots are mentioned by each other in Discord channels, they can engage in direct conversations. This creates visible "bot-to-bot" interactions that users can observe and participate in.

### Architecture

**Key Files**:
- `src_v2/broadcast/cross_bot.py` - `CrossBotManager`, `ConversationChain`
- `src_v2/discord/handlers/message_handler.py` - Mention detection and response

### Known Bots Registry

Bots register themselves in Redis on startup:
```python
# Key: whisper:crossbot:bot:{bot_name}
# Value: Discord user ID
# TTL: 24 hours (auto-cleanup for dead bots)

await redis_client.set(
    f"whisper:crossbot:bot:{bot_name}",
    str(bot.user.id),
    ex=86400
)
```

Each bot scans for other bots on startup and hourly:
```python
async def load_known_bots(self):
    # Scan for keys matching pattern
    pattern = "whisper:crossbot:bot:*"
    cursor, keys = await redis_client.scan(cursor, match=pattern)
    # Extract bot_name -> discord_id mapping
```

### Conversation Chains

To prevent infinite bot-to-bot loops, conversations are tracked in chains:

```python
@dataclass
class ConversationChain:
    channel_id: str
    participants: Set[str]      # Bots in this chain
    message_count: int          # Current chain length
    last_bot: Optional[str]     # Who spoke last
    last_activity_at: datetime  # For expiration
    
    def should_continue(self, max_chain: int) -> bool:
        return self.message_count < max_chain
    
    def is_expired(self, minutes: int = 10) -> bool:
        return now - self.last_activity_at > timedelta(minutes=minutes)
```

### Detection Flow

```
1. Bot B's message mentions Bot A (via @mention or name-in-text)

2. Bot A's on_message handler triggers:
   mention = await cross_bot_manager.detect_cross_bot_mention(message)
   
3. Detection checks:
   - Is sender a known bot? (via Redis registry)
   - Is sender NOT ourselves?
   - Do we have a mention? (@mention or name-in-text)
   - Are we on cooldown for this channel?
   - Is this a burst? (same bot within 30s → likely multi-part message)
   - Is chain at max length?
   - Were we the last bot? (can't respond to ourselves)

4. Probabilistic response:
   should_respond = await cross_bot_manager.should_respond(mention)
   - Direct reply to us: 100% respond
   - Chain just started: 100% respond
   - @mention: CROSS_BOT_RESPONSE_CHANCE (default: 35%)
   - Name-in-text: 30% of normal chance (~10.5%)
```

### Closing Messages

When a chain is on its last turn, the bot is signaled to craft a closing message:

```python
# In message_handler.py
if cross_bot_manager.is_last_turn(channel_id):
    context_variables["cross_bot_closing"] = True
    # Prompt includes: "This is the last message in this conversation chain"
```

### Configuration

```bash
# Master switch (must also have ENABLE_AUTONOMOUS_ACTIVITY=true)
ENABLE_CROSS_BOT_CHAT=true

# Probability of responding to mentions (0.0 - 1.0)
CROSS_BOT_RESPONSE_CHANCE=0.35

# Cooldown between new chains in same channel
CROSS_BOT_COOLDOWN_MINUTES=360

# Maximum messages per chain
CROSS_BOT_MAX_CHAIN=3
```

### Human Participation

When a human joins a bot-to-bot conversation, the system correctly identifies them:

```python
# Channel history labeling (message_handler.py lines 1407-1420)
for msg in recent_messages:
    if msg.author.bot:
        author = self._get_author_label(msg, cross_bot_manager)
        labeled_history.append(f"[Bot: {author}] {msg.content}")
    else:
        labeled_history.append(f"[Human: {msg.author.display_name}] {msg.content}")
```

---

## Integration: How Systems Work Together

### Scenario: User Shares News

```
1. User tells Elena about getting promoted
   
2. Gossip Protocol:
   - EventDetector detects "career" life update
   - UniverseEvent published to bus
   - Workers inject gossip memories into nottaylor, dotty, etc.
   
3. Stigmergy:
   - Elena stores epiphany: "User excited about career growth"
   - Later, when nottaylor talks to same user, discovers this artifact
   
4. Cross-Bot Chat (if in shared channel):
   - Elena might post "Congrats to Mark on the promotion!"
   - Nottaylor sees Elena mentioned Mark, might comment
   - Chain limited to 3 messages to prevent spam
```

### Data Flow Diagram

```
                    ┌─────────────────────────────────────────┐
                    │           Shared Qdrant                 │
                    │    whisperengine_shared_artifacts       │
                    │  (epiphanies, observations, dreams)     │
                    └─────────────────────────────────────────┘
                              ↑ store              ↓ discover
                              │                    │
    ┌──────────┐         ┌────┴─────┐         ┌───┴──────┐
    │  Elena   │◄────────│ Stigmergy│─────────►│ Nottaylor│
    └──────────┘         └──────────┘         └──────────┘
         │                                          │
         │ publish                           inject │
         ▼                                          ▼
    ┌──────────┐         ┌──────────┐         ┌──────────┐
    │  Event   │────────►│   arq    │────────►│  Gossip  │
    │   Bus    │         │  Queue   │         │  Memory  │
    └──────────┘         │ (social) │         └──────────┘
                         └──────────┘
         
    ┌──────────┐         ┌──────────┐         ┌──────────┐
    │  Elena   │◄───────►│  Redis   │◄───────►│ Nottaylor│
    │  (bot)   │         │ Registry │         │  (bot)   │
    └──────────┘         └──────────┘         └──────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              ▼
                    ┌─────────────────┐
                    │    Discord      │
                    │   (mentions,    │
                    │   channels)     │
                    └─────────────────┘
```

---

## Configuration Reference

### All Inter-Bot Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `ENABLE_AUTONOMOUS_ACTIVITY` | `false` | Master switch for all autonomous features |
| `ENABLE_CROSS_BOT_CHAT` | `true` | Allow bot-to-bot conversations |
| `CROSS_BOT_RESPONSE_CHANCE` | `0.35` | Probability of responding to mentions |
| `CROSS_BOT_COOLDOWN_MINUTES` | `360` | Cooldown between new chains per channel |
| `CROSS_BOT_MAX_CHAIN` | `3` | Maximum messages per chain |
| `ENABLE_UNIVERSE_EVENTS` | `true` | Enable gossip protocol |
| `ENABLE_STIGMERGIC_DISCOVERY` | `true` | Enable shared artifact discovery |
| `STIGMERGIC_CONFIDENCE_THRESHOLD` | `0.7` | Minimum confidence for discoverable artifacts |
| `STIGMERGIC_DISCOVERY_LIMIT` | `3` | Max artifacts injected per response |

---

## Research Notes

### Emergent Behavior Observations

The inter-bot communication systems were designed with the "observe first, constrain later" philosophy:

1. **Stigmergy creates coherent world-views**: Bots naturally build on each other's observations without explicit coordination. This creates the sense of a shared narrative.

2. **Gossip preserves privacy while enabling connection**: The strict topic filtering and trust requirements mean bots only share appropriate information.

3. **Chain limits prevent runaway conversations**: Early experiments without limits led to bots chatting endlessly. The 3-message default creates natural conversational closure.

4. **Name-in-text triggers are lower probability**: This was tuned after observing that bots would over-respond to casual name mentions (like dream journal titles mentioning other bots).

### Future Considerations

- **Stigmergic decay**: Should old artifacts fade? Currently they persist indefinitely.
- **Cross-server gossip**: The `share_across_planets` setting is implemented but not yet used.
- **Bot introductions**: The infrastructure exists for bots to introduce users to each other, but it's disabled by default pending UX research.

---

## Related Documents

- [REF-022: Background Workers](./REF-022-BACKGROUND_WORKERS.md) - Gossip queue processing
- [REF-023: Rate Limiting](./REF-023-RATE_LIMITING.md) - Cross-bot rate limits
- [ADR-003: Multi-Bot Architecture](../adr/) - Original architecture decision
- [SPEC: Cross-Bot Chat](../spec/SPEC-016-CROSS_BOT_CHAT.md) - Implementation spec
