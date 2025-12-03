# 🌌 Federated Multiverse Protocol

> ⚠️ **DRAFT DOCUMENT** - This is a vision document for future architecture. None of this is implemented. The purpose is to ensure current architectural decisions don't preclude federation.

**Document Version:** 0.2 (Draft)  
**Created:** November 25, 2025  
**Status:** 📋 Vision/Design Phase  
**Priority:** Low (Phase D - Future)  
**Complexity:** 🔴 High  
**Dependencies:** Emergent Universe (Phase B8), Worker Queues (Sprint 7)

**Related Documents:**
- [`EMERGENT_UNIVERSE.md`](./EMERGENT_UNIVERSE.md) - The Universe modality that federation extends
- [`ref/REF-010-MULTI_MODAL.md`](../ref/REF-010-MULTI_MODAL.md) - Philosophy of how characters process multi-modal input
- [`prd/PRD-002-PRIVACY.md`](../prd/PRD-002-PRIVACY.md) - Current privacy model (foundation for federation privacy)
- [`ref/REF-005-DATA_MODELS.md`](../ref/REF-005-DATA_MODELS.md) - Database architecture that must support federation
- [`guide/GUIDE-002-KNOWLEDGE_GRAPH.md`](../guide/GUIDE-002-KNOWLEDGE_GRAPH.md) - Neo4j graph that would sync across universes

---

## Executive Summary

The Federated Multiverse enables independent WhisperEngine deployments to **connect and share** while maintaining sovereignty. Each deployment is a "universe" - a complete, autonomous system. Federation allows universes to discover each other, share travelers (characters), and let inhabitants (users) journey between them.

**This is not centralization.** There is no master server, no single point of control. It's peer-to-peer federation, like email or ActivityPub (Mastodon).

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
- **Network effects**: Characters can travel between universes, users can interact across platforms
- **Resilience**: No single point of failure - each universe is independent
- **Privacy**: Operators choose what to share; users control their cross-universe presence

> **Note**: Discord server admins (planet owners) don't need to do anything for federation. They just use whichever bot they've invited. Federation happens at the platform level.

---

## Core Concepts

These concepts extend the cosmic analogy established in the [Emergent Universe](./EMERGENT_UNIVERSE.md) design.

### Universe

A single WhisperEngine deployment, run by a **platform operator**. Contains:
- **Planets**: Discord servers where characters are present (owned by anyone - server admins don't need their own WhisperEngine)
- **Travelers**: AI characters running on this instance  
- **Inhabitants**: Users who interact with characters in this universe
- **Knowledge Graph**: All relationships and facts for this universe

Each universe has a unique identifier (UUID) and optional human-readable name.

> **Key distinction**: A universe operator runs the WhisperEngine platform. Planet owners (Discord server admins) just invite the bot - they don't need technical infrastructure. One universe can span hundreds of Discord servers owned by different people.

### Planet

A Discord server where characters are present. Key points:
- **Owned by Discord server admins** - not the universe operator
- **No technical requirements** - just invite the bot like any Discord bot
- **Multiple planets per universe** - one WhisperEngine instance serves many servers
- **Planets can switch universes** - kick one bot, invite another (though history stays with original universe)

Planet owners choose which universe to connect to by inviting that universe's bot.

### Federation

The act of two or more universes agreeing to share information. Federation is:
- **Opt-in**: Both sides must consent
- **Granular**: You choose what to share
- **Revocable**: You can disconnect at any time

### Multiverse

The collective network of all federated universes. The multiverse is:
- **Decentralized**: No central authority
- **Eventually consistent**: Changes propagate over time
- **Partition tolerant**: Works even when some universes are offline

---

## Protocol Specification

### Universe Identity

Each universe has a cryptographic identity:

```yaml
universe:
  id: "550e8400-e29b-41d4-a716-446655440000"  # UUID v4
  name: "WhisperVerse Prime"                   # Human-readable
  public_key: "ed25519:ABC123..."              # For signing
  endpoints:
    federation: "https://whisper.example.com/federation/v1"
    discovery: "https://whisper.example.com/.well-known/whisperengine"
  version: "2.0.0"
  capabilities:
    - "traveler-hosting"      # Can host visiting characters
    - "inhabitant-travel"     # Users can visit other universes
    - "knowledge-sync"        # Can sync graph data
    - "event-relay"           # Can relay universe events
```

### Discovery Protocol

Universes find each other through multiple mechanisms:

#### 1. Well-Known Endpoint

```
GET https://whisper.example.com/.well-known/whisperengine
```

Returns universe metadata (see above). Allows any universe to verify another by domain.

#### 2. Manual Peering

Administrators exchange universe IDs out-of-band and configure peering directly.

```yaml
# In universe config
federation:
  peers:
    - id: "universe-uuid-here"
      endpoint: "https://other-universe.com/federation/v1"
      trust_level: "full"  # full | limited | read-only
```

#### 3. Discovery Registry (Optional)

A public registry where universes can list themselves for discovery. This is **opt-in** and not required for federation.

```
POST https://registry.whisperengine.org/v1/universes
{
  "universe_id": "...",
  "endpoint": "...",
  "public": true,
  "categories": ["roleplay", "creative-writing", "gaming"]
}
```

### Handshake Protocol

When two universes connect:

```
┌─────────────────┐                              ┌─────────────────┐
│   Universe A    │                              │   Universe B    │
└────────┬────────┘                              └────────┬────────┘
         │                                                │
         │  1. HELLO (A's identity + capabilities)        │
         │───────────────────────────────────────────────>│
         │                                                │
         │  2. HELLO_ACK (B's identity + capabilities)    │
         │<───────────────────────────────────────────────│
         │                                                │
         │  3. PROPOSE (federation terms)                 │
         │───────────────────────────────────────────────>│
         │                                                │
         │  4. ACCEPT/REJECT (B's decision)               │
         │<───────────────────────────────────────────────│
         │                                                │
         │  5. CONFIRM (signed agreement)                 │
         │───────────────────────────────────────────────>│
         │                                                │
         │         [Federation Established]               │
         │                                                │
```

### Message Format

All federation messages use a common envelope:

```json
{
  "version": "1.0",
  "type": "TRAVELER_VISIT",
  "source_universe": "uuid-of-sender",
  "target_universe": "uuid-of-recipient",
  "timestamp": "2025-11-25T12:00:00Z",
  "signature": "ed25519:...",
  "payload": {
    // Type-specific data
  }
}
```

### Message Types

| Type | Description | Direction |
|------|-------------|-----------|
| `HELLO` | Initial handshake | Initiator → Target |
| `HELLO_ACK` | Handshake response | Target → Initiator |
| `PROPOSE` | Propose federation terms | Either |
| `ACCEPT` | Accept federation | Either |
| `REJECT` | Reject federation | Either |
| `TRAVELER_VISIT` | Character visiting another universe | Home → Host |
| `TRAVELER_RETURN` | Character returning home | Host → Home |
| `INHABITANT_TRAVEL` | User visiting another universe | Home → Host |
| `KNOWLEDGE_SYNC` | Graph data synchronization | Either |
| `EVENT_RELAY` | Universe event notification | Either |
| `HEARTBEAT` | Keep-alive | Either |
| `DISCONNECT` | End federation | Either |

---

## Traveler (Character) Federation

> **Context**: Characters are defined by their [multi-modal perception](../ref/REF-010-MULTI_MODAL.md). When traveling, they carry their perceptual context with them.

### Visiting Another Universe

When a character "visits" another universe:

1. **Home universe** sends `TRAVELER_VISIT` with:
   - Character identity (name, ID)
   - Character definition (personality, traits, background)
   - Memory snapshot (configurable depth)
   - Home universe reference

2. **Host universe** receives and:
   - Validates the request
   - Creates a "visitor" character instance
   - Assigns to requested planet (server)
   - Notifies home universe of acceptance

3. **During visit**:
   - Host universe runs the character
   - New memories stored locally
   - Periodic sync back to home (configurable)

4. **Return home**:
   - Host sends `TRAVELER_RETURN` with:
     - Memories accumulated during visit
     - Relationships formed
     - Any universe-specific knowledge

### Character Identity Continuity

Characters maintain identity across universes. Character definitions are file-based and portable (see [`CREATING_NEW_CHARACTERS.md`](../CREATING_NEW_CHARACTERS.md)).

```yaml
traveler:
  global_id: "whisperengine:universe-uuid:character-uuid"
  home_universe: "universe-uuid"
  name: "Elena"
  
  # Universe-specific adaptations
  adaptations:
    target_universe_id:
      local_name: "Elena the Wanderer"  # Optional alias
      local_context: "Visiting from the WhisperVerse..."
      visibility: "full"  # full | limited | anonymous
```

---

## Inhabitant (User) Travel

> **Foundation**: The current privacy model is documented in [`PRIVACY_AND_DATA_SEGMENTATION.md`](../PRIVACY_AND_DATA_SEGMENTATION.md). Federation extends this with cross-universe consent.

### Privacy Model

Users control their cross-universe presence:

```yaml
inhabitant:
  discord_id: "123456789"  # Globally unique
  home_universe: "universe-uuid"
  
  travel_preferences:
    allow_travel: true
    share_with_hosts:
      - name: true
      - avatar: true
      - conversation_history: false  # Never share by default
      - trust_scores: false
      - facts_about_me: "opt-in"  # Per-universe consent
    
    remember_visits: true  # Home universe remembers where you've been
```

### Travel Flow

1. User in Universe A mentions a character from Universe B
2. Universe A checks federation status with B
3. If federated and user has travel enabled:
   - A sends `INHABITANT_TRAVEL` request to B
   - B creates temporary visitor profile
   - Interaction happens in B
   - Results optionally synced back to A

### Consent Requirements

Cross-universe user data requires **explicit consent**:
- First travel to a new universe prompts consent
- User can revoke at any time
- Revoking deletes visitor profile from host universe

---

## Knowledge Graph Sync

> **Foundation**: The Neo4j knowledge graph is documented in [`guide/GUIDE-002-KNOWLEDGE_GRAPH.md`](../guide/GUIDE-002-KNOWLEDGE_GRAPH.md) and [`ref/REF-005-DATA_MODELS.md`](../ref/REF-005-DATA_MODELS.md). Federation extends the graph across universe boundaries.

### What Can Sync

| Data Type | Default | Notes |
|-----------|---------|-------|
| Public character facts | ✅ Sync | Character backgrounds |
| Character relationships | ✅ Sync | Who knows whom |
| User facts | ❌ No sync | Privacy-sensitive |
| User preferences | ❌ No sync | Privacy-sensitive |
| Universe events | ✅ Sync | Public happenings |
| Private conversations | ❌ Never | Absolutely not |

### Sync Protocol

Uses Conflict-free Replicated Data Types (CRDTs) for eventual consistency:

```
┌─────────────────────────────────────────────────────────────────┐
│                    KNOWLEDGE GRAPH SYNC                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Universe A                              Universe B              │
│  ┌─────────────┐                        ┌─────────────┐        │
│  │ Neo4j Graph │                        │ Neo4j Graph │        │
│  │             │                        │             │        │
│  │  (A:Elena)──┼─── CRDT Sync ─────────┼──(B:Elena)  │        │
│  │     │       │                        │     │       │        │
│  │     ▼       │                        │     ▼       │        │
│  │  (A:User1)  │                        │  (B:User2)  │        │
│  │             │                        │             │        │
│  └─────────────┘                        └─────────────┘        │
│                                                                 │
│  Conflict Resolution: Last-Write-Wins with vector clocks        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Selective Sync

Universes specify what they want to sync:

```yaml
sync_policy:
  outbound:  # What we share
    - type: "Character"
      filter: "public = true"
    - type: "Relationship"
      filter: "character_to_character"
    - type: "UniverseEvent"
      filter: "visibility = 'public'"
  
  inbound:  # What we accept
    - type: "Character"
      action: "create_visitor"
    - type: "UniverseEvent"
      action: "store_read_only"
```

---

## Routing Service Architecture

### Local Router

Each universe runs a Federation Router:

```
┌─────────────────────────────────────────────────────────────────┐
│                    FEDERATION ROUTER                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Inbound    │  │   Outbound   │  │    Sync      │          │
│  │   Handler    │  │   Handler    │  │   Manager    │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                 │                 │                   │
│         └─────────────────┼─────────────────┘                   │
│                           │                                     │
│                           ▼                                     │
│                  ┌─────────────────┐                            │
│                  │  Message Queue  │  (Redis/RabbitMQ)          │
│                  │  (Async)        │                            │
│                  └────────┬────────┘                            │
│                           │                                     │
│         ┌─────────────────┼─────────────────┐                   │
│         ▼                 ▼                 ▼                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ Peer        │  │ Peer        │  │ Peer        │             │
│  │ Connection  │  │ Connection  │  │ Connection  │             │
│  │ (Universe B)│  │ (Universe C)│  │ (Universe D)│             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Components

| Component | Responsibility |
|-----------|----------------|
| **Inbound Handler** | Receives messages from peers, validates signatures, routes to appropriate handler |
| **Outbound Handler** | Queues messages for peers, handles retries, manages rate limits |
| **Sync Manager** | Coordinates knowledge graph sync, manages CRDT state |
| **Message Queue** | Async message processing, prevents blocking |
| **Peer Connections** | Maintains WebSocket/HTTP connections to federated peers |

### API Endpoints

```
POST /federation/v1/message     # Receive federation message
GET  /federation/v1/status      # Federation status
GET  /federation/v1/peers       # List federated peers
POST /federation/v1/peer        # Add new peer (admin)
DELETE /federation/v1/peer/:id  # Remove peer (admin)

GET  /.well-known/whisperengine # Discovery endpoint
```

---

## Security Model

### Authentication

- All messages signed with universe's Ed25519 private key
- Signatures verified against known public keys
- Key rotation supported with overlap period

### Authorization

Federation has three trust levels:

| Level | Capabilities |
|-------|--------------|
| `read-only` | Can receive events, cannot send travelers |
| `limited` | Can send/receive travelers, limited sync |
| `full` | Full federation including knowledge sync |

### Rate Limiting

- Per-peer rate limits prevent DoS
- Backpressure signals when overwhelmed
- Automatic throttling during high load

### Privacy

- User data never syncs without explicit consent
- Private conversations never leave home universe
- Universes can require approval for all incoming requests

---

## Implementation Phases

> **Note**: These are Phase D items in the [Implementation Roadmap Overview](../IMPLEMENTATION_ROADMAP_OVERVIEW.md). They depend on earlier phases being complete.

### Phase D1: Foundation (Future)

**Goal**: Basic universe identity and discovery

- [ ] Generate universe identity (UUID, keypair)
- [ ] Implement well-known endpoint
- [ ] Create admin UI for federation settings
- [ ] Add peer configuration storage

**No actual federation yet** - just the groundwork.

### Phase D2: Peering (Future)

**Goal**: Two universes can connect

- [ ] Implement handshake protocol
- [ ] Create peer connection manager
- [ ] Add heartbeat/keepalive
- [ ] Build federation status dashboard

### Phase D3: Traveler Exchange (Future)

**Goal**: Characters can visit other universes

- [ ] Implement `TRAVELER_VISIT` / `TRAVELER_RETURN`
- [ ] Create visitor character instances
- [ ] Handle memory sync on return
- [ ] Add traveler status tracking

### Phase D4: Inhabitant Travel (Future)

**Goal**: Users can interact across universes

- [ ] Implement consent flow
- [ ] Create `INHABITANT_TRAVEL` protocol
- [ ] Handle visitor profiles
- [ ] Add privacy controls UI

### Phase D5: Knowledge Sync (Future)

**Goal**: Graphs can sync public data

- [ ] Implement CRDT-based sync
- [ ] Create sync policy configuration
- [ ] Handle conflict resolution
- [ ] Add sync status monitoring

### Phase D6: Discovery Registry (Future)

**Goal**: Universes can find each other

- [ ] Design registry protocol
- [ ] Implement (or use existing) registry
- [ ] Add universe listing/search
- [ ] Create exploration UI

---

## Compatibility Considerations

### Current Architecture Decisions That Support Federation

✅ **Discord IDs as user identifiers** - Globally unique, no namespace collision  
✅ **Neo4j for knowledge graph** - Supports graph replication patterns  
✅ **UUID for internal IDs** - Globally unique, no collision  
✅ **Character definitions in files** - Portable, shareable  
✅ **Privacy settings per-user** - Foundation for consent model  

### Decisions to Avoid

❌ **Auto-incrementing IDs** - Would collide across universes  
❌ **Hardcoded single-instance assumptions** - Check for these  
❌ **User data without consent tracking** - Need consent audit trail  

### Migration Path

When federation launches, existing instances can:
1. Generate universe identity
2. Continue operating locally (no change)
3. Opt-in to federation when ready
4. Gradually enable features

---

## Open Questions

> These need resolution before implementation

1. **Registry governance**: Who runs the public registry? How is abuse prevented?
2. **Character ownership**: What if two universes have characters with the same name?
3. **Memory conflicts**: How to handle contradictory memories from different universes?
4. **Monetization**: Can universes charge for hosting visitors?
5. **Moderation**: How do we handle bad actors in the multiverse?
6. **Legal**: GDPR implications of cross-border universe connections?

---

## Inspiration & Prior Art

- **ActivityPub** (Mastodon): Decentralized social federation
- **Matrix**: Decentralized real-time communication
- **IPFS**: Content-addressed distributed storage
- **Git**: Distributed version control with merge strategies
- **Email (SMTP)**: Original federated messaging

---

## Appendix: Glossary

| Term | Definition |
|------|------------|
| **Universe** | A WhisperEngine deployment, run by a platform operator |
| **Multiverse** | The network of all federated universes |
| **Federation** | The agreement between two universe operators to share |
| **Traveler** | An AI character (can visit other universes) |
| **Inhabitant** | A human user (can interact across universes) |
| **Planet** | A Discord server where characters are present (owned by server admins, not universe operators) |
| **Planet Owner** | A Discord server admin who invites a bot - no technical infrastructure required |
| **Universe Operator** | Someone running a WhisperEngine deployment |
| **Peering** | The act of two universes connecting |
| **CRDT** | Conflict-free Replicated Data Type |

---

## Document History

- v0.2 (Nov 25, 2025) - Added cross-references to related documents, clarified universe/planet ownership model
- v0.1 (Nov 25, 2025) - Initial draft establishing vision and protocol concepts

---

*"The multiverse is not a feature to be built. It's a possibility to be enabled."*
