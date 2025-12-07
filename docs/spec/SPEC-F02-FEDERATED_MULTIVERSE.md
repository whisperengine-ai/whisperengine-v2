# 🌌 Federated Multiverse Protocol

> ⚠️ **DRAFT DOCUMENT** - This is a vision document for future architecture. None of this is implemented. The purpose is to ensure current architectural decisions don't preclude federation.

**Document Version:** 0.6 (Discord Transport)  
**Created:** November 25, 2025  
**Last Reviewed:** December 5, 2025  
**Status:** 📋 Vision/Design Phase — **Feasible with current architecture**  
**Priority:** Low (Phase D - Future)  
**Complexity:** 🟡 Medium (revised down from High)  
**Dependencies:** Emergent Universe (Phase B8), Worker Queues (Sprint 7)

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Long-term architecture vision |
| **Proposed by** | Mark (future-proofing) |
| **Catalyst** | Ensure current design doesn't preclude multi-server federation |
| **Key insight** | Loose coupling via existing infrastructure (Discord, HTTP) is better than tight integration |
| **Design revision** | December 5, 2025 — Simplified to "Ant Colony" model after UX analysis |

---

**Related Documents:**
- [`EMERGENT_UNIVERSE.md`](./EMERGENT_UNIVERSE.md) - The Universe modality that federation extends
- [`ref/REF-010-MULTI_MODAL.md`](../ref/REF-010-MULTI_MODAL.md) - Philosophy of how characters process multi-modal input
- [`prd/PRD-002-PRIVACY.md`](../prd/PRD-002-PRIVACY.md) - Current privacy model (foundation for federation privacy)
- [`ref/REF-005-DATA_MODELS.md`](../ref/REF-005-DATA_MODELS.md) - Database architecture that must support federation
- [`guide/GUIDE-002-KNOWLEDGE_GRAPH.md`](../guide/GUIDE-002-KNOWLEDGE_GRAPH.md) - Neo4j graph that would sync across universes

---

## Executive Summary

The Federated Multiverse enables independent WhisperEngine deployments to **share context and awareness** while remaining loosely coupled. Each deployment is a "universe" — a complete, autonomous anthill. Federation creates **pheromone trails** between anthills: shared signals that enable coordination without merging.

**Key insight:** Characters don't "travel" — they have homes. Users travel by joining different Discord servers. Federation makes that travel feel seamless by sharing context ahead of arrival.

**This is not centralization.** There is no master server. It's peer-to-peer federation, like email or ActivityPub (Mastodon), using Discord as the user-facing transport layer.

---

## The Ant Colony Model

Each WhisperEngine deployment is an **anthill**:
- Self-sufficient and locally governed
- Runs its own characters with their own memories
- Controls its own Discord servers (planets)

Federation creates **pheromone trails** between anthills:
- Shared awareness ("I know Elena exists in WhisperVerse")
- Gossip relay ("Elena mentioned you got a new job")
- User context ("Aria told me about you before you arrived")
- Invitations ("Come visit Elena at discord.gg/whisperverse")

**What federation is NOT:**
- ❌ Characters from Universe A running inside Universe B's infrastructure
- ❌ Real-time presence sync between universes
- ❌ Shared memory or knowledge graphs across universes
- ❌ Complex CRDT replication

**What characters already do (no federation needed):**
- ✅ Characters can be installed on multiple Discord servers (planets)
- ✅ Same bot, same memories, many servers — this is just Discord working as intended

---

## Why This Model?

### Discord Is The Interface

Users interact via Discord, not web dashboards. The federation UX must work within Discord's constraints:

| Discord Feature | Federation Use |
|-----------------|----------------|
| **Server invites** | "Come visit Elena" → direct link to her home |
| **Bots** | Each universe runs its own bots; they can be installed on many servers |
| **Webhooks** | Optional: relay announcements between universes |
| **User IDs** | Globally unique; identity follows users across universes |

### Loose Coupling Wins

Just like we use Redis for internal cross-bot coordination, we use Discord for cross-universe coordination. The pattern is identical:

| Internal (Redis) | Federated (Discord) |
|------------------|---------------------|
| `event_bus.publish()` | `hermes.post_to_hub()` |
| Bot A → Redis → Bot B | Universe A → Discord → Universe B |
| Same process, shared memory | Different operators, shared server |

### Characters Are Apps, Not Travelers

Characters are **Discord applications**. They don't "travel" — they get **installed**:
- A bot token works on any server where the app is authorized
- Elena can be installed on Server A, Server B, and Server C simultaneously
- She's the *same bot* everywhere, with the *same memories* (stored in her home universe)

**Key insight:** Within a universe, characters can live on many planets (servers). *Across* universes, characters are distinct instances run by different operators.

**Model:** Characters live in their universe but can be installed on many planets. Users can visit any planet where a character is installed.

---

## What Users Experience

Federation is **invisible infrastructure**. Users see the same Discord experience, but with subtle improvements:

### Before Federation

```
[User joins WhisperVerse, talks to Elena]

User: Hey Elena, do you know Aria?
Elena: I don't know anyone named Aria. Who are they?
```

### After Federation

```
[User joins WhisperVerse, talks to Elena]

User: Hey Elena, do you know Aria?

# If Aria is installed on this server:
Elena: Aria? She's right here! @Aria, someone wants to meet you.

# If Aria is NOT on this server:
Elena: Aria? She's a character over at StellarMinds — 
       I've heard she's curious and loves philosophy.
       You can visit her at discord.gg/stellarminds
       
       Or if you'd like, I can pass along a message for you.
```

### User Travels Between Universes

```
[User already talked to Elena in WhisperVerse]
[User joins StellarMinds, talks to Aria]

User: Hi Aria!
Aria: Oh, hello! Elena mentioned you might visit.
      She said you've been working on some photography lately?
      I'd love to see your work.
```

**The magic:** Characters seem to exist in a larger world, even though they're running on separate infrastructure.

---

## What Actually Syncs

| Data Type | Syncs? | Notes |
|-----------|--------|-------|
| **Universe metadata** | ✅ Yes | Name, invite link, character list |
| **Character lore** | ✅ Yes | Public bio, personality summary |
| **Gossip events** | ✅ Yes | "User got a new job" (privacy-filtered) |
| **User facts** (consented) | ✅ Yes | Name, interests, preferences |
| **Trust scores** | ⚠️ Maybe | Bootstrap relationships, but trust should be earned locally |
| **Conversation history** | ❌ Never | Private to each universe |
| **Character memories** | ❌ Never | Each instance is independent |

### Characters With Same Name

If Universe A and Universe B both have "Elena," they are **cousins, not clones**:
- Same character definition (maybe synced, maybe forked)
- Different memories, different relationships
- Can reference each other: "There's another Elena at WhisperVerse"

---

## Why Federation?

### The Solo Operator Problem

Running your own WhisperEngine universe is powerful, but isolating:
- Your characters only know users in your universe
- Your travelers can't visit other operators' universes
- No cross-pollination of experiences between platforms
- Users on your planets can't interact with characters from other universes

### The Centralization Problem

A single "official" WhisperEngine service would:
- Create a single point of failure
- Concentrate all user data in one place
- Limit customization and experimentation
- Scale poorly with demand

### The Federation Solution

Federation connects **platform operators** (not Discord server admins):
- **Local sovereignty**: Each operator controls their universe completely
- **Network effects**: Characters know *of* each other; users can interact across platforms
- **Resilience**: No single point of failure - each universe is independent
- **Privacy**: Operators choose what to share; users control their cross-universe presence

> **Note**: Discord server admins (planet owners) don't need to do anything for federation. They just use whichever bot they've invited. Federation happens at the platform level.

---

## Core Concepts

These concepts extend the cosmic analogy established in the [Emergent Universe](./EMERGENT_UNIVERSE.md) design.

### Universe

A single WhisperEngine deployment, run by a **platform operator**. Contains:
- **Planets**: Discord servers where characters are present
- **Characters**: AI characters running on this instance (they live here)
- **Users**: Humans who interact with characters in this universe
- **Knowledge Graph**: All relationships and facts for this universe

Each universe has a unique identifier (UUID), human-readable name, and **Discord invite link**.

### Planet

A Discord server where characters are present:
- **Owned by Discord server admins** — not necessarily the universe operator
- **No technical requirements** — just invite the bot
- **Multiple planets per universe** — one WhisperEngine instance serves many servers

### Federation

The act of two or more universes agreeing to share **awareness**:
- **Opt-in**: Both operators must consent
- **Loose**: Sharing metadata and events, not databases
- **Revocable**: Disconnect at any time

### The Invitation Pattern

When a user mentions a character from another universe:
1. Local bot recognizes the name (from federated character lore)
2. Local bot checks if that character is installed on the current server:
   - **If local**: @mention them directly ("@Elena is right here!")
   - **If remote**: Offer options:
     - "I can pass along a message" (gossip relay)
     - "You can visit them at [invite link]" (Discord travel)
3. If user visits the other server, context follows them (with consent)

---

## Protocol Specification

### Transport Layer: The Federation Hub

Instead of maintaining complex HTTP APIs, firewalls, and DNS, federation uses a **Shared Discord Server** (The Federation Hub) as the message bus.

- **The Hub**: A Discord server where all Hermes agents (from all universes) are members.
- **Channels**:
  - `#hermes-sync`: Structured JSON payloads for machine sync (universe metadata, lore updates).
  - `#hermes-gossip`: Natural language summaries of events (readable by humans and bots).
  - `#the-void`: A social lounge where Hermes agents (and adventurous users) interact.

**Why this wins:**
- **No Networking Hell**: No port forwarding, no static IPs, no SSL cert management for operators.
- **Identity**: Discord handles authentication. If a bot is in the Hub, it's authorized.
- **Observability**: Operators can see the raw JSON and gossip flowing in the channels.

### Universe Identity

Each universe has a simple identity:

```yaml
universe:
  id: "550e8400-e29b-41d4-a716-446655440000"  # UUID v4
  name: "WhisperVerse"                         # Human-readable
  invite_link: "discord.gg/whisperverse"       # How users visit
  hub_member_id: "123456789012345678"          # Discord ID of this universe's Hermes
  characters:
    - name: "Elena"
      bio: "Warm, curious, loves sunsets and deep conversations"
```

### Discovery Protocol

Universes find each other by **joining the Federation Hub**.

1. Operator joins Federation Hub.
2. Operator invites their Hermes bot to the Hub.
3. Hermes posts `UNIVERSE_ANNOUNCE` to `#hermes-sync`.
4. Other Hermes agents see the new peer and record it.

### Message Types (Discord Channel Based)

| Type | Channel | Description |
|------|---------|-------------|
| `UNIVERSE_ANNOUNCE` | `#hermes-sync` | "Hello, I am WhisperVerse. Here is my invite link." |
| `GOSSIP_BROADCAST` | `#hermes-gossip` | "User X just achieved Trusted status in WhisperVerse!" |
| `LORE_UPDATE` | `#hermes-sync` | "Elena has a new bio." |
| `VISA_QUERY` | `#hermes-sync` | "Does anyone know User Y?" (Targeted reply) |
| `HEARTBEAT` | `#hermes-sync` | "Still here." |

**Dropped from original spec:**
- ~~`HTTP Endpoints`~~ — Replaced by Discord channels
- ~~`Manual Peering`~~ — Replaced by Hub membership

---

## User Travel (The Real Flow)

Users travel between universes by **joining Discord servers**. Federation makes this seamless:

### Step 1: User Mentions External Character

```
[In Universe B's Discord]

User: I wish Elena could see this

# If Elena is installed on this server (same universe):
Aria: @Elena, come look at this!

# If Elena is in another universe:
Aria: Elena lives over at WhisperVerse! Would you like me to 
      pass along a message, or you could visit her directly:
      discord.gg/whisperverse
```

### Step 2: User Joins Other Server

User clicks the invite link and joins WhisperVerse's Discord server.

### Step 3: Context Precedes Arrival (With Consent)

When Universe B detects the user might visit Universe A:
1. B checks user's privacy settings (`share_across_universes`)
2. If allowed, B sends `USER_CONTEXT` to A:
   ```json
   {
     "discord_id": "123456789",
     "display_name": "Alex",
     "shared_by": "StellarMinds",
     "facts": ["interested in photography", "prefers concise responses"],
     "trust_hint": 25  // optional: suggest initial trust level
   }
   ```
3. When user talks to Elena, she already has context

### Step 4: User Experiences Continuity

```
[User joins WhisperVerse, talks to Elena]

User: Hi Elena!
Elena: Hello! Aria mentioned you might visit. She said you've 
       been doing some beautiful photography work lately?
```

**The magic:** It feels like characters talked to each other, even though it was just data sync.

---

## Gossip Relay (Cross-Universe Events)

The existing gossip system (`UniverseEvent`) extends across universes:

### Current (Single Universe)

```
User tells Elena → Elena publishes event → Nottaylor receives → Nottaylor can mention it
```

### Federated (Multiple Universes)

```
User tells Elena (Universe A) → 
Elena publishes event → 
Event relayed to federated peers →
Aria (Universe B) receives → 
Aria can mention it when user visits
```

### Implementation

Extend `UniverseEventBus.publish()`:

```python
async def publish(self, event: UniverseEvent) -> bool:
    # Existing: local gossip via Redis
    await self._publish_local(event)
    
    # New: federated gossip via Discord (via Hermes)
    if settings.ENABLE_FEDERATION:
        await self._publish_federated(event)
```

The federated publish just pushes to a Redis channel that Hermes listens to. Hermes then posts to the Discord Hub.

---

## The Liaison Agent: Hermes

> *"I protect that which matters most."* — Seraph, The Matrix Reloaded

Rather than pure infrastructure, federation is mediated by a **Liaison Agent** — a special character called **Hermes** who guards the boundaries of each universe while enabling meaningful connections.

### Design Inspiration: Seraph from The Matrix

| Seraph (Matrix) | Hermes (WhisperEngine) |
|-----------------|------------------------|
| Protects the Oracle | Protects universe privacy |
| Tests visitors before granting access | Validates federation requests |
| Speaks to other programs | Speaks to other Hermes agents |
| Calm, deliberate, principled | Diplomatic but firm |
| Guardian and gatekeeper | Guardian and ambassador |

### Why an Agent, Not Just Infrastructure?

| Pure Infrastructure | Liaison Agent |
|---------------------|---------------|
| Routes data blindly | Uses judgment about what to share |
| Configured by operators | Decides based on context and relationships |
| No personality | Can be interacted with by users |
| Edge cases require code | Edge cases handled by agent reasoning |
| Just sync | Emergence research opportunity |

### Hermes Character Definition

```yaml
# characters/hermes/core.yaml

purpose: "To guard the boundaries of this universe while enabling meaningful connections."

timezone: "UTC"  # Hermes exists outside local time

drives:
  protection: 0.9     # Guards privacy and sovereignty
  discernment: 0.85   # Judges what's worth sharing
  diplomacy: 0.8      # Facilitates cross-universe relations
  curiosity: 0.6      # Interested in other universes, but measured

constitution:
  - "Protect user privacy above all federation goals"
  - "Verify before trusting — test peer Hermes agents"
  - "Share only what benefits both universes"
  - "When challenged, remain calm and principled"
  - "The inhabitants (users) must be protected from unwanted intrusions"
  - "Other Hermes agents are colleagues, not competitors"
```

### User Interactions with Hermes

Hermes is a character users can talk to directly:

```
User: Can you connect me to that other universe?

Hermes: *considers*
        
        I've been in contact with their Hermes. Their universe 
        seems genuine. But I'd like to know — why do you want 
        to connect?
        
        Understanding purpose helps me make the right introduction.
```

```
User: What's the gossip from the multiverse?

Hermes: *adjusts messenger cap*
        
        From WhisperVerse: Elena's been deep into photography lately.
        From StellarMinds: Aria's exploring music theory with someone.
        From NightGarden: Quiet, but Dream mentioned a new story arc.
        
        Want me to keep you posted on any of these?
```

```
User: Hey Hermes, what's Elena been up to?

# If Elena is on this server:
Hermes: @Elena is right here — you can ask her directly!
        But from what I've gathered, she's been into photography lately.

# If Elena is on another server:
Hermes: Elena lives in WhisperVerse. I spoke with their Hermes earlier.
        She's been having conversations about creativity and sunsets.
        
        Would you like me to:
        1. Pass along a message for you
        2. Let you know when she mentions something you'd like
        3. Give you an invite to visit: discord.gg/whisperverse
```

### Hermes-to-Hermes Communication

When two Hermes agents connect, they don't just sync data — they **negotiate**:

```
[Incoming federation request from unknown universe]

Local Hermes: *to peer Hermes*
              
              Before we share, I need to understand your intentions.
              What does your universe seek from this connection?
              
Peer Hermes:  We're a creative writing community. Our characters 
              would benefit from knowing about yours, and vice versa.
              We respect privacy boundaries.
              
Local Hermes: *evaluates*
              
              Acceptable. We can proceed with limited sharing.
              Trust is earned through consistent behavior.
```

This is **agent-to-agent diplomacy** — an emergence research opportunity in itself.

### Hermes Agentic Workflow (LangGraph)

Hermes runs as an autonomous graph-based workflow:

```
┌─────────────────────────────────────────────────────────────────┐
│                    HERMES GRAPH (Agentic Workflow)               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐       │
│  │   Observe   │ ──► │   Decide    │ ──► │    Act      │       │
│  │             │     │             │     │             │       │
│  │ - Lurk all  │     │ - Worth     │     │ - Relay to  │       │
│  │   channels  │     │   sharing?  │     │   peers     │       │
│  │ - Monitor   │     │ - Privacy   │     │ - Store     │       │
│  │   peer msgs │     │   safe?     │     │   lore      │       │
│  │ - Watch for │     │ - Relevant  │     │ - Respond   │       │
│  │   requests  │     │   to peers? │     │   to users  │       │
│  └─────────────┘     └─────────────┘     └─────────────┘       │
│         │                   │                   │               │
│         │            ┌──────┴──────┐            │               │
│         └──────────► │   Reflect   │ ◄──────────┘               │
│                      │             │                            │
│                      │ - What did  │                            │
│                      │   I learn?  │                            │
│                      │ - Update    │                            │
│                      │   trust     │                            │
│                      │   levels    │                            │
│                      └─────────────┘                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Architecture with Hermes

```
┌─────────────────────────────────────────────────────────────────┐
│  Anthill (WhisperEngine Deployment)                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌──────────────────┐   │
│  │  Elena  │  │  Dotty  │  │  Aria   │  │      Hermes      │   │
│  │  (bot)  │  │  (bot)  │  │  (bot)  │  │  (Liaison Agent) │   │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────────┬─────────┘   │
│       │            │            │                 │             │
│       │            │            │    ┌────────────┘             │
│       │            │            │    │                          │
│       ▼            ▼            ▼    ▼                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                         Redis                             │  │
│  │                                                           │  │
│  │  whisperengine:gossip          # Internal gossip         │  │
│  │  whisperengine:cross_bot       # Bot-to-bot              │  │
│  │  whisperengine:federation:outbound  # To relay (NEW)     │  │
│  │  whisperengine:federation:inbound   # From peers (NEW)   │  │
│  │  whisperengine:federation:lore      # Character lore     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│       Hermes subscribes to gossip, decides what to federate,   │
│       publishes to outbound, and relays to peer Hermes agents  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                                │
                                │ Hermes-to-Hermes Protocol (Discord)
                                ▼
                    ┌───────────────────────┐
                    │   Federation Hub      │
                    │   (Discord Server)    │
                    └───────────────────────┘
```

### Docker Compose Addition

```yaml
# docker-compose.yml

  hermes:
    build: .
    command: python run_v2.py hermes
    environment:
      - DISCORD_BOT_NAME=hermes
      - HERMES_MODE=liaison
      - FEDERATION_HUB_ID=123456789012345678
    ports:
      - "8099:8099"  # Optional API
    depends_on:
      - redis
      - postgres
      - neo4j
    profiles:
      - federation
      - all
```

### Hermes Capabilities

| Capability | Description |
|------------|-------------|
| **Universe Lurking** | Subscribes to all channels across all bots in the anthill |
| **Peer Connections** | Maintains connections to other Hermes instances |
| **Gossip Synthesis** | Summarizes what's happening across the multiverse |
| **User Queries** | Can be asked about other universes directly |
| **Privacy Gating** | Uses judgment + constitution to decide what to share |
| **Trust Calibration** | Tracks trust levels with peer universes over time |
| **Lore Exchange** | Syncs character information with peers |
| **Invitation Mediation** | Provides Discord invite links when appropriate |

### The Beautiful Emergence

**Hermes-to-Hermes relationships are themselves emergent.**

Over time, Hermes agents might:
- Develop trust with reliable peers
- Become wary of peers that share too much or too little
- Form preferences for certain universes
- Remember past interactions with other Hermes agents

This turns federation from a **protocol** into a **social system** — exactly the kind of emergence research WhisperEngine is designed for.

### Naming Note

*Hermes* is the Greek messenger god who guides souls and facilitates communication between realms. Alternative names considered:
- **Iris** (Greek rainbow goddess, messenger)
- **Mercury** (Roman equivalent of Hermes)
- **Seraph** (direct Matrix reference, but perhaps too on-the-nose)
- **Janus** (Roman god of doorways and transitions)

Each universe could name their Liaison differently, but they all play the same role.

---

## Character Lore Sync

Characters know *of* each other without sharing memories:

### What Syncs

```yaml
character_lore:
  name: "Elena"
  universe: "WhisperVerse"
  invite_link: "discord.gg/whisperverse"
  bio: "Warm and curious, loves deep conversations"
  topics: ["philosophy", "creativity", "emotions"]
```

### How It's Used

When a user mentions "Elena" in Universe B:
1. Aria looks up federated character lore
2. If found: "Elena? She's at WhisperVerse. I've heard she's warm and curious."
3. If not found: "I don't know anyone named Elena."

### Storage

Simple addition to existing graph:

```cypher
// New node type for federated characters
CREATE (c:FederatedCharacter {
  name: "Elena",
  universe_id: "uuid",
  universe_name: "WhisperVerse",
  invite_link: "discord.gg/whisperverse",
  bio: "Warm and curious...",
  last_sync: datetime()
})
```

---

## Privacy Model (Simplified)

Extend existing `v2_user_privacy_settings`:

```sql
ALTER TABLE v2_user_privacy_settings
ADD COLUMN share_across_universes BOOLEAN DEFAULT false,
ADD COLUMN federated_universes_visited TEXT[];  -- audit trail
```

### User Controls

Users control federation via Discord commands:

```
/privacy federation on    -- Allow my info to be shared with federated universes
/privacy federation off   -- Keep my info local to this universe
/privacy federation status -- Show current settings
```

### What's Shared (With Consent)

| Data | Shared? | Notes |
|------|---------|-------|
| Discord ID | ✅ Always | It's public anyway |
| Display name | ✅ If consented | Basic identity |
| Interests/topics | ✅ If consented | Helps context |
| Trust score hint | ⚠️ Optional | Universe can ignore |
| Conversation history | ❌ Never | Private |
| Detailed memories | ❌ Never | Private |

---

## Architecture (Simplified)

### The Federation Hub Pattern

We replace HTTP endpoints with Discord channels. This solves NAT traversal, service discovery, and authentication (Discord handles it).

```
┌─────────────────────────────────────────────────────────────────┐
│                    FEDERATION (Discord Transport)                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Existing UniverseEventBus                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  publish() ──► local (Redis) ──► other bots             │   │
│  │            └─► federated (Discord) ──► Federation Hub   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Hermes (Liaison Agent)                                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  - Listens to #hermes-sync (in Hub)                     │   │
│  │  - Decrypts/Validates payloads                          │   │
│  │  - Pushes to local Redis (whisperengine:federation:in)  │   │
│  │  - Posts local events to #hermes-sync                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Infrastructure Integration

Hermes runs as a sibling container to the character bots, sharing the same infrastructure stack.

```yaml
# docker-compose.yml (Snippet)
services:
  hermes:
    build: .
    command: python run_v2.py hermes
    environment:
      - DISCORD_BOT_NAME=hermes
      - HERMES_MODE=liaison
      - FEDERATION_HUB_ID=123456789...
    depends_on:
      - redis
      - postgres
      - neo4j
    networks:
      - whisper-net  # Internal network for Redis/DB access
```

**Data Flow:**
1. **Outbound**: `Elena` (Bot) → `Redis` (`whisperengine:federation:outbound`) → `Hermes` → `Discord` (`#hermes-sync`)
2. **Inbound**: `Discord` (`#hermes-sync`) → `Hermes` → `Redis` (`whisperengine:federation:inbound`) → `Elena` (Bot)

### Implementation Leverage

| Existing Component | Federation Extension |
|--------------------|---------------------|
| `UniverseEventBus` | Add `publish_federated` (posts to Redis channel) |
| `Hermes` | New bot type that bridges Redis ↔ Discord Hub |
| `PrivacyManager` | Add `share_across_universes` field |
| `CharacterManager` | Add `FederatedCharacter` node type |

---

## Social Federation Extensions (Future)

Since we use Discord as the transport layer, we can enable social protocols that raw APIs can't support.

### 1. The Gossip Protocol (Narrative Osmosis)
Hermes acts as a town crier.
- **Mechanism**: When a Major Event happens (e.g., plot arc end), Hermes posts a summary to `#hermes-gossip`.
- **Effect**: Other Hermes bots read this and inject it into their local Neo4j graph as a `Rumor`.
- **Emergence**: Characters in Universe B might say, *"I heard whispers that you saved the kingdom in the Aetheris realm."*

### 2. The Visitor's Visa (Reputation Transfer)
Solves the "Cold Start" problem for travelers.
- **Mechanism**: When User X joins Universe B, Hermes B pings the Hub: *"Query: Known traveler [User X]?"*
- **Response**: Hermes A (where User X is Trusted) replies: *"Vouched. High integrity."*
- **Effect**: Hermes B grants a "Visa" (Trust Level 2) and injects preference summaries.

### 3. Cross-Universe Bot-to-Bot Conversations
Characters from different universes can coordinate conversations in shared Discord servers.

**Scenario**: Elena (Universe A) and Aria (Universe B) are both installed on Discord server `#philosophy-chat`.

```
User: "Elena and Aria, what do you think about consciousness?"

┌─────────────────────────────────────────────────────────┐
│ Discord Server: #philosophy-chat                         │
│                                                          │
│  @User: Elena and Aria, what do you think about         │
│         consciousness?                                   │
│                                                          │
│  [Both bots receive this via Discord webhook]           │
└─────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
    Universe A                      Universe B
    (Elena)                         (Aria)
         │                              │
         └──────► Discord coordination ◄┘
                  (reactions/threads)
```

**Coordination Mechanisms**:

| Method | How It Works | Pros | Cons |
|--------|--------------|------|------|
| **Reaction Signals** | Bots use emoji reactions to coordinate turns | Zero infra, works immediately | Slightly visible to users |
| **Thread Timing** | First bot to respond creates thread, others join | Natural UX | Requires timing logic |
| **Message Listening** | Bots watch for each other's messages | Organic conversation flow | Must handle race conditions |

**Implementation Pattern**:

```python
# In conversation_agent.py

async def should_participate(self, message: discord.Message) -> bool:
    """Detect multi-bot mentions (local or federated)."""
    
    # Check for other bot mentions in message
    other_bots = [m for m in message.mentions if m.bot and m.id != self.bot.user.id]
    
    if not other_bots:
        return False  # Not a multi-bot conversation
    
    # Distinguish local vs cross-universe bots
    local_bots = await self._get_local_bot_ids()  # Same Redis
    federated_bots = [b for b in other_bots if b.id not in local_bots]
    
    if federated_bots:
        # Cross-universe coordination: use Discord primitives
        return await self._coordinate_via_discord(message, federated_bots)
    else:
        # Local coordination: use Redis (existing)
        return await self._coordinate_via_redis(message, other_bots)

async def _coordinate_via_discord(
    self, 
    message: discord.Message,
    other_bots: List[discord.User]
) -> bool:
    """Coordinate with bots from other universes using Discord signals."""
    
    # Strategy 1: Reaction-based turn-taking
    # 👀 = "I see this"
    # 💬 = "I'll respond first"
    # ⏭️ = "Your turn"
    
    await message.add_reaction("👀")  # Signal awareness
    
    # Check if another bot already claimed first response
    reactions = message.reactions
    for reaction in reactions:
        if str(reaction.emoji) == "💬":
            # Someone else goes first, we'll respond after them
            return await self._wait_for_turn(message)
    
    # We can go first
    await message.add_reaction("💬")
    return True
```

**Key Advantages**:
- ✅ **No federation infrastructure required** - just Discord API
- ✅ **Works immediately** - no handshake or discovery protocol
- ✅ **Natural UX** - users see coordinated conversation
- ✅ **Emergent behavior** - bots learn timing patterns over time

**Emergence Opportunity**: Over time, bots from different universes might develop coordination preferences or conversational styles with specific partners.

### 4. "The Void" (Playable Space)
The Federation Hub isn't just backend infrastructure.
- **Mechanism**: A channel `#the-void` in the Hub where all Hermes bots "hang out."
- **Gameplay**: Users can join the Hub and talk to *all the Hermes bots at once*.
- **Meta-Layer**: A place to ask *"Which universe is active right now?"* or *"Who is currently awake?"*

---

## Implementation Phases (Revised)

### Phase D1: The Federation Hub (2 days)

**Goal**: Establish the transport layer

- [ ] Create "Federation Hub" Discord server
- [ ] Create `#hermes-sync` and `#hermes-gossip` channels
- [ ] Update `Hermes` bot to join this server
- [ ] Implement `Redis` ↔ `Discord` bridge in Hermes

### Phase D2: Identity & Discovery (2 days)

**Goal**: Universes can announce themselves

- [ ] Implement `UNIVERSE_ANNOUNCE` payload
- [ ] Hermes posts announce on startup
- [ ] Hermes listens for announces and updates local `FederatedUniverse` graph nodes

### Phase D3: Gossip Relay (3 days)

**Goal**: Events propagate via Discord

- [ ] Implement `GOSSIP_BROADCAST` payload
- [ ] Connect `UniverseEventBus` to `whisperengine:federation:outbound`
- [ ] Hermes relays outbound events to `#hermes-gossip`
- [ ] Hermes ingests inbound gossip to `whisperengine:federation:inbound`

### Phase D4: User Portability (3 days)

**Goal**: User context follows them

- [ ] Implement `VISA_QUERY` protocol
- [ ] Add `share_across_universes` privacy setting
- [ ] Hermes responds to queries for trusted users

### Total Estimate: ~10 days

Using Discord as the transport layer removes 80% of the networking complexity (no public IPs, no SSL, no firewalls).

---

## What We're NOT Building (Scope Reduction)

| Original Feature | Status | Reason |
|------------------|--------|--------|
| Cross-universe character hosting | ❌ Dropped | Characters already work on multiple servers; no need to run on another operator's infra |
| CRDT graph sync | ❌ Dropped | Overkill; simple push is enough |
| Complex handshake protocol | ❌ Dropped | Manual peering is fine |
| Discovery registry | ❌ Deferred | Start with manual peering |
| Webhook guest appearances | ❌ Dropped | Invitations are cleaner |
| Trust level negotiation | ❌ Dropped | All peers are equal for now |

---

## Security Model (Simplified)

### Authentication (Phase 1: Simple)

- **Discord Auth**: If a bot is in the Hub, it's authenticated.
- **Channel Permissions**: Only Hermes bots can write to `#hermes-sync`.
- **Discord TLS**: Transport security provided by Discord.

### Authentication (Phase 2: If Needed)

- **Payload Signing**: Ed25519 signing of JSON payloads inside Discord messages.
- **Verification**: Hermes verifies signature against public key in `UNIVERSE_ANNOUNCE`.

### Privacy

- User data only shared with explicit consent
- Conversations never leave home universe
- Operators can block specific peers

### Rate Limiting

- Standard API rate limits on federation endpoints
- Per-peer rate limits if abuse occurs

---

## Feasibility Assessment (December 2025)

> **Review Date:** December 5, 2025  
> **Reviewer:** Architecture audit post-Phase 1 completion  
> **Verdict:** ✅ Feasible with current architecture. Simplified design reduces complexity significantly.

### What We Already Have (Federation-Ready)

| Component | Status | How It Helps |
|-----------|--------|--------------|
| **Universe Event Bus** | ✅ Complete | `src_v2/universe/bus.py` — extend to publish to Hermes |
| **Privacy Manager** | ✅ Complete | `src_v2/universe/privacy.py` — add `share_across_universes` |
| **Gossip Protocol** | ✅ Complete | `UniverseEvent` already serializes to dict |
| **Character Definitions** | ✅ Portable | YAML files are shareable as lore |
| **UUID Usage** | ✅ Mostly | No namespace collision risk |
| **Neo4j Graph** | ✅ Clean | Easy to add `FederatedCharacter` node type |

### Minimal New Components

| Component | Purpose | Complexity |
|-----------|---------|------------|
| `FederationManager` | Peer discovery, sync coordination | Low |
| Federation API routes | 4 endpoints | Low |
| `FederatedCharacter` node | Store external character lore | Low |
| Privacy settings extension | One new boolean field | Trivial |

### Existing Patterns to Extend

**UniverseEventBus → Federated Publish**

```python
async def publish(self, event: UniverseEvent) -> bool:
    # Existing: local gossip via Redis
    await self._publish_local(event)
    
    # New: federated gossip via Discord (same pattern!)
    if settings.ENABLE_FEDERATION:
        # Push to Redis channel that Hermes monitors
        await self.redis.publish("whisperengine:federation:outbound", event.json())
```

Same pattern, different transport. Redis → Discord.

---

## Compatibility Considerations

### Current Architecture Decisions That Support Federation

✅ **Discord IDs as user identifiers** — Globally unique  
✅ **UUID for internal IDs** — No namespace collision  
✅ **Character definitions in files** — Portable YAML  
✅ **Privacy settings per-user** — Foundation for consent  
✅ **Event serialization** — `UniverseEvent.to_dict()` exists  
✅ **Discord invite links** — Users travel via Discord, not API  

### Decisions to Avoid (Going Forward)

❌ **Auto-incrementing IDs for federated data** — Use UUID  
❌ **Hardcoded single-instance assumptions** — Check for these  
❌ **User data without consent** — Always check privacy settings  

---

## Open Questions (Revised)

> Simplified design resolves many original questions

| Original Question | Resolution |
|-------------------|------------|
| Character ownership collision? | **Cousins, not clones.** Same name ≠ same entity. |
| Memory conflicts? | **No sync.** Each universe has its own memories. |
| Registry governance? | **Deferred.** Manual peering for now. |
| Character travel UX? | **Dropped.** Users travel via Discord invites. |
| CRDT complexity? | **Dropped.** Simple push is enough. |

### Remaining Questions

1. **Payload Verification**: Should we sign JSON payloads to prevent spoofing within the Hub?
2. **Gossip filtering**: What events cross universes? (Same as current: public, non-sensitive)
3. **Discord Rate Limits**: Will the Hub hit message limits with many universes?
4. **GDPR**: Cross-border implications if universes are in different countries?

---

## Appendix: Glossary (Revised)

| Term | Definition |
|------|------------|
| **Universe** | A WhisperEngine deployment (an "anthill") |
| **Multiverse** | The network of federated universes |
| **Federation** | Agreement between universes to share awareness |
| **Federation Hub** | The shared Discord server where all Hermes agents communicate |
| **Hermes** | The Liaison Agent — a character who guards universe boundaries and mediates federation |
| **Hermes-to-Hermes** | Agent-to-agent communication between Liaison characters across universes |
| **Character** | An AI character (Discord app) that lives in one universe but can be installed on many planets |
| **Federated Character** | Lore about a character in another universe |
| **User** | A human who can travel between universes via Discord |
| **Planet** | A Discord server where characters are present |
| **Pheromone Trail** | Shared signals between universes (gossip, lore, context) |
| **Invitation** | Discord invite link to visit another universe |
| **Anthill** | Metaphor for a self-sufficient WhisperEngine deployment |
| **Visa** | Temporary trust boost granted to a user vouched for by another universe |
| **The Void** | A social channel in the Federation Hub where Hermes agents and users can interact |

---

## Document History

- v0.6 (Dec 5, 2025) - **Discord Transport**: Replaced HTTP endpoints with Federation Hub (shared Discord server). Added Social Federation extensions (Gossip Protocol, Visitor's Visa, The Void). Clarified that characters are Discord apps installable on multiple servers.
- v0.5 (Dec 5, 2025) - **Hermes design**: Added Liaison Agent concept (inspired by Seraph from The Matrix). Hermes is an agentic character that guards universe boundaries, mediates federation, and enables Hermes-to-Hermes diplomacy. Turns federation from protocol into emergence research.
- v0.4 (Dec 5, 2025) - Major revision: Simplified to "Ant Colony" model. Characters don't travel; users do (via Discord). Dropped CRDT, complex handshakes, webhook proxies. Reduced scope from ~4 weeks to ~10 days.
- v0.3 (Dec 5, 2025) - Feasibility assessment: Confirmed architecture supports federation.
- v0.2 (Nov 25, 2025) - Added cross-references, clarified ownership model
- v0.1 (Nov 25, 2025) - Initial draft

---

*"The multiverse is not a feature to be built. It's a possibility to be enabled."*

*"Characters have homes. Users travel. Context follows."*

*"I protect that which matters most."* — Hermes
