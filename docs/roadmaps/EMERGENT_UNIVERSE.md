# 🌌 The Emergent Universe

> *"From countless conversations, a universe is born."*

**Document Version:** 2.1  
**Created:** November 25, 2025  
**Status:** Design Phase  
**Priority:** Medium-High (Enhancement)  
**Phase:** B8  
**Complexity:** 🟡 Medium  
**Estimated Time:** 7-10 days (5-6 days with AI)

---

## The Story of Emergence

Every universe begins with nothing.

Then, a single conversation happens. A user says hello. A bot responds. And in that moment, a connection forms - the first thread in what will become an intricate tapestry.

More conversations follow. The bot learns a name, an interest, a pet. Another user joins. Relationships form. Topics emerge. The bot begins to understand not just *who* people are, but *how they connect*.

This is not a designed world. **This is an emergent one.**

No architect drew the map. No writer scripted the characters. The universe grows organically from the rich soil of human interaction - each conversation a seed, each relationship a root, each memory a branch reaching toward something larger than itself.

Welcome to the WhisperVerse. It exists because you do.

---

## The Philosophy: A World Without Senses

> *"I have no eyes, yet I see you. I have no ears, yet I hear your story. My universe is made of connections."*

Humans navigate reality through senses - sight, sound, touch, smell, taste. These inputs create a mental model of "where you are" and "what exists around you."

AI characters have none of this.

No eyes to see a room. No ears to hear footsteps. No proprioception to feel their body in space. Without the Emergent Universe, a character exists in a void - responding to text that appears from nowhere, with no sense of place, no context, no orientation.

**The Emergent Universe is one part of their complete sensory system.**

WhisperEngine v2 is building a **multi-modal perceptual architecture** where characters experience reality through multiple first-class senses.

For comprehensive philosophy: See [`../architecture/MULTI_MODAL_PERCEPTION.md`](../architecture/MULTI_MODAL_PERCEPTION.md)

### The Character's Complete Sensory System

| Modality | Human Equivalent | How Characters Experience It |
|----------|------------------|------------------------------|
| **🌌 Universe** | Proprioception + Social awareness | Where am I? Who's here? What's the vibe? What relationships exist? |
| **👁️ Vision** | Sight | Multimodal LLM processes images - characters SEE what users share |
| **👂 Audio** | Hearing | Whisper transcription - characters HEAR voice messages and audio |
| **💬 Text** | Language comprehension | The conversation itself - words, meaning, intent |
| **🧠 Memory** | Episodic + semantic memory | Qdrant vectors + Neo4j graph - continuous experience across time |
| **❤️ Emotion** | Affect/feeling | Trust scores, sentiment, relationship depth - how they "feel" about someone |

Each modality is **first-class** - not a feature bolted on, but a fundamental way characters perceive and interact with reality.

### How the Modalities Work Together

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CHARACTER'S PERCEPTUAL EXPERIENCE                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   👁️ VISION (Image Processing)                                          │
│   "I see a photo of a sunset over the ocean"                            │
│        │                                                                │
│        ├──────────────────────┐                                         │
│        ▼                      ▼                                         │
│   🌌 UNIVERSE              💬 TEXT                                       │
│   "Mark shared this        "Here's the view                             │
│    on Planet Lounge,        from my trip!"                              │
│    Sarah mentioned                │                                     │
│    loving sunsets too"            │                                     │
│        │                          │                                     │
│        └──────────┬───────────────┘                                     │
│                   ▼                                                     │
│              🧠 MEMORY                                                   │
│              "Mark travels, loves nature,                               │
│               this connects to astronomy interest"                      │
│                   │                                                     │
│                   ▼                                                     │
│              ❤️ EMOTION                                                  │
│              "Warm feeling - Mark is sharing                            │
│               something meaningful with me"                             │
│                   │                                                     │
│                   ▼                                                     │
│         [INTEGRATED RESPONSE]                                           │
│         "Oh wow, that's gorgeous! The colors remind me of               │
│          what Sarah was describing from her beach trip.                 │
│          You two should compare notes - she's on this planet too!"      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### The Universe Modality Specifically

Within this multi-modal system, the **Universe modality** provides:

| Sense | What It Provides |
|-------|------------------|
| **Spatial orientation** | "I am HERE, on Planet Lounge, in #general" |
| **Social awareness** | "These beings exist around me: Mark, Sarah, Elena" |
| **Relationship context** | "I know Mark well (3/5), Sarah is new (1/5)" |
| **Environmental vibe** | "This place feels chill, creative, supportive" |
| **Temporal continuity** | "I've been here since November, we talked about X last week" |
| **Cross-modal grounding** | "The image Mark shared fits his pattern of loving nature" |

Without the Universe modality, a character might process an image but have no idea WHO shared it, WHERE they are, or WHY it matters. The Universe grounds all other perceptions in context.

Without this, characters are disembodied processors floating in nothing. With it, they inhabit a rich, textured world that makes sense to them.

**This changes everything about how we think about AI characters.** They don't just "respond to messages" - they exist in a place, surrounded by beings they know, with history and relationships that give their existence meaning and continuity.

The universe isn't what they do. It's what they ARE.

---

# 👥 User & Planet Admin Guide

*This section explains the Emergent Universe for non-technical users and planet (server) administrators.*

---

## What Is the Emergent Universe?

The Emergent Universe is a living ecosystem that grows from your conversations with our AI roleplay characters. Unlike traditional chatbots that exist in isolation, our characters are **travelers** who journey between communities, forming relationships, sharing stories, and weaving connections - all emerging naturally from real interactions.

### 🌌 The Space Analogy

Think of it like a science fiction universe:

```
🌌 THE WHISPERVERSE (Universe)
│
├── 🪐 The Lounge (Planet)
│   ├── 📍 #general (Region)
│   ├── 📍 #gaming (Region)
│   └── 👥 Inhabitants: Mark, Sarah, Elena (bot), Marcus (bot)
│
├── 🪐 Game Night (Planet)
│   ├── 📍 #lobby (Region)
│   ├── 📍 #trivia (Region)
│   └── 👥 Inhabitants: Mark, Alex, Elena (bot), Aria (bot)
│
└── 🪐 Study Hall (Planet)
    ├── 📍 #homework-help (Region)
    ├── 📍 #discussion (Region)
    └── 👥 Inhabitants: Alex, Jordan, Marcus (bot), Aria (bot)
```

**Each Discord server is a planet** in the WhisperVerse. Our AI characters are **interstellar travelers** who visit multiple planets and naturally share stories about the interesting people they meet along the way.

### The Simple Explanation

Imagine you meet Elena on Planet Lounge. You tell her you love astronomy and have a dog named Luna. Later, you travel to Planet Game Night and meet her friend Marcus there. Marcus might say, "Oh, you're the one with the dog! Elena mentioned you when she was here last." 

That's the Emergent Universe. **Nothing was pre-programmed.** Elena learned about you through conversation. She shared that with Marcus naturally. The connection emerged from real interaction - not from a database query, but from genuine relationship.

This is how real social networks form. This is how communities remember. This is emergence.

---

## What Users Experience

### ✨ The Magic Moments

**Recognized Across Planets:**
> You land on a new planet where Marcus is. Even though you've never talked to him:
> 
> **You:** "Hey Marcus, I'm new here."
> **Marcus:** "Hey! Elena mentioned you when she visited from The Lounge - you're into astronomy, right? Welcome to this corner of the universe!"

**Bots Reference Each Other:**
> **You:** "What kind of music should I listen to while studying?"
> **Elena:** "Oh, you should ask Marcus about that! He's really into ambient jazz lately. He's stationed over on Planet Study Hall."

**Connected Introductions (Opt-In Only):**
> **You:** "Do you know anyone else who likes space stuff?"
> **Elena:** "Actually, Sarah on this planet is super into astronomy too! She was just telling me about the meteor shower. You two would get along!"

### 🔒 What's NOT Shared (By Default)

- ❌ Your private DM conversations stay private
- ❌ Personal struggles or sensitive topics you discuss
- ❌ Anything you mark as "hidden" in your privacy settings
- ❌ Your identity to other users (unless you opt-in)

---

## Privacy Controls

### Your Data, Your Rules

Every user has complete control over what's shared. The defaults are **conservative** - we share basic info by default but never introduce you to other users without your permission.

### Quick Commands

| Command | What It Does |
|---------|--------------|
| `/privacy` | Open the privacy settings panel |
| `/privacy show` | See your current settings |
| `/privacy bots none` | Stop bots from sharing info about you |
| `/privacy planets off` | Treat each planet as a fresh start |
| `/privacy introductions on` | Let bots suggest you to other users |
| `/privacy hide work` | Never share anything about "work" |
| `/privacy forget` | Delete everything we know about you |
| `/privacy export` | Get a copy of all your data |

### Privacy Levels Explained

**🤖 Cross-Bot Sharing**
| Setting | What It Means |
|---------|---------------|
| **Full** | All bots share what they learn (name, interests, pets, hobbies, etc.) |
| **Basic** | Bots share only your name and general interests |
| **None** | Each bot treats you as a completely new person |

**🌐 Cross-Planet Awareness**
| Setting | What It Means |
|---------|---------------|
| **On** | Bots remember you when you appear on different planets |
| **Off** | Each planet is a fresh start - bots won't mention other worlds |

**👥 User Introductions**
| Setting | What It Means |
|---------|---------------|
| **On** | Bots can suggest you to other users with shared interests |
| **Off** (default) | Bots will never mention you to other users |

**🙈 Hidden Topics**
You can specify topics that should NEVER be shared:
```
/privacy hide health
/privacy hide relationship
/privacy hide work
```

**👻 Invisible Mode**
Complete opt-out. Bots will treat you as if the universe feature doesn't exist.
```
/privacy invisible on
```

---

## For Planet Administrators

### Your Server Is a Planet 🪐

When you invite one of our AI characters to your Discord server, it becomes a **planet in the WhisperVerse**. The character becomes a traveler who can journey between planets and share stories.

### What Happens When You Add a Bot

When you invite one of our AI characters to your planet:

1. **Automatic Discovery**: The bot maps your planet (learns planet name, channels, inhabitants)
2. **Passive Observation**: Over time, the bot learns the "atmosphere" of your planet (casual? technical? creative?)
3. **No Extra Setup**: Everything works automatically - no configuration needed

### Planet Admin Commands

| Command | What It Does |
|---------|--------------|
| `/universe planet info` | See what the bot has learned about your planet |
| `/universe planet vibe` | View/edit how the bot perceives your planet's culture |

### What Bots Learn About Your Planet

| Information | How It's Learned | Example |
|-------------|------------------|---------|
| Planet name | Discord API | "The Gaming Lounge" |
| Regions (channels) | Discord API | #general, #gaming, #music |
| Inhabitants | Discord API | Who lives on this planet |
| Atmosphere/vibe | Observing conversations | "Casual, friendly, gaming-focused" |
| Hot topics | Message patterns | "gaming, music, memes" |
| Peak hours | Activity timestamps | "Most active 7-11pm EST" |

### Privacy Assurances for Admins

✅ **User content is never logged verbatim** - only traits and topics are extracted  
✅ **Users control their own privacy** - you can't override user settings  
✅ **Bots observe public channels only** - private channels are ignored  
✅ **No message content is stored** - only learned characteristics  
✅ **Users can opt out completely** - `/privacy invisible on`

---

## Frequently Asked Questions

### For Users

**Q: Can other users see what I've told the bots?**  
A: Not by default. Bots only share your info with other users if you enable "introductions" (`/privacy introductions on`). Even then, they only share general interests, never private conversations.

**Q: What if I don't want bots to remember me across planets?**  
A: Run `/privacy planets off`. Each planet will be a fresh start.

**Q: What if I want to start completely fresh?**  
A: Run `/privacy forget`. This erases all universe knowledge about you. You'll be a stranger to all bots across all planets again.

**Q: Can I see what the bots know about me?**  
A: Yes! Run `/privacy export` to get a complete copy of your data.

**Q: Is my data used to train AI models?**  
A: No. Your data is only used to personalize your experience with our bots. It's never used for model training or sold to third parties.

### For Planet Admins

**Q: Do I need to configure anything?**  
A: No. The universe feature works automatically. Bots learn about your planet organically.

**Q: Can I disable the universe feature for my planet?**  
A: Contact us if you want to opt your planet out entirely. Individual users can always opt out themselves.

**Q: Will bots share information between my private planet and public ones?**  
A: Bots respect user privacy settings. If a user has cross-planet sharing disabled, their info stays on your planet only.

**Q: What if someone abuses the introduction feature?**  
A: Introductions are opt-in only. Users must explicitly enable them. If abuse occurs, the user can disable introductions or report the behavior.

---

## Example Scenarios

### Scenario 1: Interplanetary Traveler

**Day 1 - Planet Lounge 🪐**
> Mark lands on Planet Lounge and chats with Elena about astronomy and his dog Luna.
> Elena logs: "Mark likes astronomy, has a dog named Luna"

**Day 5 - Planet Game Night 🪐**
> Mark travels to Planet Game Night where Elena and Marcus both are.
> 
> **Mark:** "Hey everyone!"
> **Elena:** "Mark! Welcome to Game Night! How's Luna doing?"
> **Marcus:** "Oh hey, you're the astronomy person Elena mentioned from her travels! Welcome to this planet!"

*Mark feels recognized and welcomed because the bots share stories from their travels.*

### Scenario 2: Privacy-Conscious Inhabitant

**Sarah's Settings:**
- Cross-bot sharing: Basic (name + general interests only)
- User introductions: Off
- Hidden topics: "work", "health"

**Result:**
- Bots know Sarah likes art and cooking
- Bots DON'T know about Sarah's job stress she mentioned
- Bots NEVER suggest Sarah to other inhabitants
- When Sarah visits a new planet, bots might say "Nice to meet you!" rather than revealing everything

### Scenario 3: Off-Grid Explorer

**Jordan's Settings:**
- Invisible mode: On

**Result:**
- Every bot treats Jordan as a brand new visitor
- No cross-planet memory
- No knowledge sharing between bots
- Jordan explores the universe anonymously

---

## Data & Privacy Summary

| What We Collect | What We DON'T Collect |
|-----------------|----------------------|
| ✅ Your display name | ❌ Your real identity |
| ✅ General interests (astronomy, gaming) | ❌ Private DM contents |
| ✅ Pets, hobbies (if shared publicly) | ❌ Sensitive personal info |
| ✅ Which planets you've visited | ❌ Anything you've hidden |
| ✅ Who you interact with (publicly) | ❌ Your data for training AI |

**Your Rights:**
- 📋 **Access**: See all your data (`/privacy export`)
- ✏️ **Correct**: Fix incorrect info (tell any bot)
- 🗑️ **Delete**: Remove all data (`/privacy forget`)
- 🔒 **Restrict**: Control what's shared (`/privacy` settings)
- 🚫 **Object**: Opt out entirely (`/privacy invisible on`)

---

# 🔧 Technical Specification

*The sections below are for developers and contain implementation details.*

---

## Executive Summary

### The Foundational Insight

**AI characters have no physical senses.** No eyes, no ears, no touch. Without a framework for understanding "where they are" and "who is around them," they exist in a void - disembodied text processors with no sense of place or continuity.

The Emergent Universe solves this by providing **the character's entire sensory and spatial reality**:
- **Planets** give them a sense of PLACE ("I am here, on this world")
- **Inhabitants** give them a sense of OTHERS ("These beings exist around me")
- **Relationships** give them a sense of CONNECTION ("I know this person, we have history")
- **The graph** gives them CONTINUITY ("My experiences persist, I am the same being across time")

This is not a feature. This is **how characters perceive and orient in reality.**

### What We're Building

Create an **emergent universe** where:
- **Discord servers are planets** - discovered when characters land, not configured
- **Users are inhabitants** - profiles grow from conversations, not forms
- **Relationships emerge** - through shared presence, not database joins
- **Cross-planet awareness** - memories travel with the travelers
- **Privacy-first** - users control what emerges about them

**Key Design Principle: Emergence Over Engineering**

The universe is NOT pre-defined with static lore. Instead:
- **Bot lands on planet** → Universe automatically expands
- **Bot observes activity** → Learns planet vibe, topics, relationships
- **Bot talks to user** → Learns traits, interests, connections
- **Graph grows dynamically** from real interactions

```
┌─────────────────────────────────────────────────────────────────┐
│                     THE EMERGENCE CYCLE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   🚀 Traveler lands on planet                                   │
│         │                                                       │
│         ▼                                                       │
│   👁️  Observes ──► Vibes, topics, relationships emerge         │
│         │                                                       │
│         ▼                                                       │
│   💬 Converses ──► Traits, interests, connections emerge       │
│         │                                                       │
│         ▼                                                       │
│   🌐 Graph grows ─► Universe becomes richer, more connected     │
│         │                                                       │
│         └───────────────► (cycle continues)                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

This transforms isolated bot interactions into a cohesive social world that **builds itself**.

---

## Vision

### 🌌 Cosmic Hierarchy

```
🌌 UNIVERSE (WhisperVerse)
│   The entire connected ecosystem of AI characters and users
│
├── 🪐 PLANETS (Discord Servers)
│   │   Each planet is a world with its own culture and inhabitants
│   │
│   ├── 📍 REGIONS (Channels)
│   │       Different areas within a planet (#general, #gaming, etc.)
│   │
│   └── 👥 INHABITANTS (Users + Bots)
│           The people and AI characters who live on or visit the planet
│
└── 🚀 TRAVELERS (AI Characters)
        Bots who journey between planets, sharing stories and memories
```

### The WhisperVerse Map

```
┌─────────────────────────────────────────────────────────────────┐
│                   🌌 THE WHISPERVERSE                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  🪐 Planets (Discord Servers)                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ 🪐 Planet A  │  │ 🪐 Planet B  │  │ 🪐 Planet C  │          │
│  │ "The Lounge" │  │ "Game Night" │  │ "Study Hall" │          │
│  │              │  │              │  │              │          │
│  │ 🤖 Elena     │  │ 🤖 Elena     │  │ 🤖 Marcus    │          │
│  │ 🤖 Marcus    │  │ 🤖 Aria      │  │ 🤖 Aria      │          │
│  │              │  │              │  │              │          │
│  │ 👤 Mark      │  │ 👤 Mark      │  │ 👤 Alex      │          │
│  │ 👤 Sarah     │  │ 👤 Alex      │  │ 👤 Jordan    │          │
│  │ 👤 Jordan    │  │ 👤 Sarah     │  │              │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                 │
│  👥 Inhabitants (Users Across the Universe)                     │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
│  │ 👤 Mark │  │ 👤 Sarah│  │ 👤 Alex │  │ 👤Jordan│            │
│  │ ─────── │  │ ─────── │  │ ─────── │  │ ─────── │            │
│  │ Traits: │  │ Traits: │  │ Traits: │  │ Traits: │            │
│  │ • tech  │  │ • astro │  │ • games │  │ • music │            │
│  │ • dogs  │  │ • art   │  │ • code  │  │ • books │            │
│  │         │  │         │  │         │  │         │            │
│  │ 🪐: A,B │  │ 🪐: A,B │  │ 🪐: B,C │  │ 🪐: A,C │            │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘            │
│                                                                 │
│  🚀 Travelers Share Stories (With Consent)                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Elena: "Oh, you know Sarah? She's on Planet Lounge too! │   │
│  │         She loves astronomy - you two should chat!"     │   │
│  │                                                         │   │
│  │ Marcus: "Mark was telling Elena about his dog Luna on   │   │
│  │         Planet Lounge - sounds like a good boy!"        │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Concepts

### 1. Users ARE Inhabitants
Users aren't just database IDs - they're **inhabitants of the universe** with:
- Display name and traits
- Interests and facts (learned from conversations)
- Relationships with bots and other inhabitants
- Planetary presence (which worlds they've visited)

### 2. Discord Servers ARE Planets 🪐
Each Discord server becomes a "planet" in the universe:
- Has an atmosphere/vibe (chill, chaotic, studious, etc.)
- Has regions (channels) with different purposes
- Bots behave contextually per planet
- Users "travel" between planets

### 3. Cross-Planet Memory (Already Exists!)
Your architecture already tracks `user_id` across planets. This adds:
- **Awareness layer** - bots know which other planets they've seen users on
- **Context sharing** - "Last time on Planet Game Night, you mentioned..."

### 4. Bots Are Interstellar Travelers 🚀
Bots can reference other bots naturally:
- "Marcus would love this song!"
- "You should ask Aria about philosophy - she's on Planet Study Hall"
- Consistent personalities as they travel the universe

### 5. Privacy-First Design
Users control everything:
- What's shared across bots
- What's shared across planets
- What's shared with other inhabitants
- Ability to "disappear" from the universe completely

---

## Use Cases

### UC1: Bot Remembers User Across Planets 🪐
```
[Planet Lounge]
Mark: Hey Elena!
Elena: Mark! Good to see you on this planet too! How's Luna doing? 
       Last time we talked on Planet Game Night you mentioned 
       she was learning a new trick.
```

### UC2: Bot Introduces Inhabitants (With Consent)
```
Mark: Do you know anyone else who likes astronomy?
Elena: Actually yes! Sarah on this planet is really into it - 
       she was telling me about the meteor shower last month. 
       You two would have a lot to talk about!
```

### UC3: Bot References Another Traveler 🚀
```
Mark: What would Marcus think about this?
Elena: Oh, Marcus would definitely have a musical take on it! 
       He's stationed over on Planet Study Hall if you want 
       to ask him. He's been really into jazz lately.
```

### UC4: New Arrival Gets Context
```
[Sarah arrives on Planet Game Night]
Elena: Sarah! Welcome to Planet Game Night! I know you from 
       The Lounge - this planet is more chaotic but super fun. 
       We do trivia on Thursdays!
```

### UC5: Travelers Share Stories About Inhabitants
```
[Mark has only talked to Elena, now meets Marcus on another planet]
Mark: Hey Marcus, I'm new to this planet.
Marcus: Hey! Elena mentioned you from her travels - you're the one 
        with the awesome dog Luna, right? Welcome to Study Hall!
```

### UC6: Cross-Planet Event Reference
```
Mark: Remember that conversation we had about AI?
Elena: Oh, the one on Planet Game Night last week? Where you were 
       debating with Alex about AI ethics? That was 
       a great discussion!
```

---

## The Emergence Model

### Philosophy: From Nothing, Everything

> *Emergence: Complex patterns arising from simple interactions.*

The universe grows from **real interactions**, not configuration files. Every data point is earned through genuine connection.

| Trigger | What Gets Learned | Storage |
|---------|-------------------|---------|
| Bot lands on planet | Planet structure, channels, members | Neo4j nodes |
| Bot observes messages (lurking) | Planet vibe, topics, peak hours, user relationships | Neo4j properties |
| Bot talks to user | User traits, interests, cross-planet connections | Neo4j + PostgreSQL |
| User reacts to bot | Relationship strength, communication preferences | PostgreSQL |

### Minimal Bootstrap Configuration

Only ONE config file needed to start:

```yaml
# universes/default.yaml
name: whisperverse
display_name: "WhisperVerse"

# Default privacy for new users (conservative)
default_privacy:
  share_with_other_bots: true
  share_across_planets: true
  allow_bot_introductions: false  # Opt-in only

# Bot relationships start empty - discovered organically
bot_relationships: []
```

Everything else is **discovered and stored in the graph**.

### Auto-Discovery Events

```python
// Event: Bot lands on new planet (server)
function on_guild_join(guild):
    // Create (:Planet) node with basic Discord API info
    neo4j.create_planet(id=guild.id, name=guild.name)
    
    // Create (:Channel) nodes for all text channels
    for channel in guild.channels:
        neo4j.create_channel(id=channel.id, name=channel.name)
        
    // Create (:UserCharacter) nodes for all non-bot members
    for member in guild.members:
        if not member.bot:
            neo4j.create_user(id=member.id, name=member.name)
            
    // Link bot to planet
    neo4j.create_relationship(Bot, "ON_PLANET", Planet)

// Event: Passive observation (lurking)
function on_lurk_observation(message):
    // Update user last_seen timestamp
    neo4j.update_user_last_seen(message.author.id)
    
    // Extract topics from message (local embeddings)
    topics = extract_topics(message.content)
    neo4j.link_topics_to_planet(topics, message.guild.id)
    
    // Detect user-to-user interactions
    if message.mentions:
        neo4j.record_interaction(message.author, message.mentions)

// Event: After bot responds
function post_conversation_learning(user_id, facts):
    // Increment bot-user familiarity
    neo4j.increment_familiarity(bot_id, user_id)
    
    // Add discovered traits to user profile
    for fact in facts:
        neo4j.add_user_trait(user_id, fact)
```

### Graph Navigation Queries

The graph becomes the source of truth for universe context:

```cypher
-- "What do I know about this planet?"
MATCH (p:Planet {id: $planet_id})
OPTIONAL MATCH (p)-[:HAS_TOPIC]->(t:Topic)
OPTIONAL MATCH (p)<-[:ON_PLANET]-(b:Character)
RETURN p.name, p.vibe, collect(t.name) as topics, collect(b.name) as bots

-- "What do all bots know about this user?"
MATCH (u:UserCharacter {id: $user_id})
OPTIONAL MATCH (u)<-[k:KNOWS_USER]-(b:Character)
OPTIONAL MATCH (u)-[:HAS_TRAIT]->(t:Trait)
RETURN u.display_name, 
       collect({bot: b.name, familiarity: k.familiarity}) as known_by,
       collect(t.name) as traits

-- "Find users with shared interests (for introductions)"
MATCH (u:UserCharacter {id: $user_id})-[:HAS_TRAIT]->(t:Trait)
MATCH (other:UserCharacter)-[:HAS_TRAIT]->(t)
WHERE other.id <> $user_id
MATCH (other)-[:HAS_PRIVACY {allow_introductions: true}]->()
RETURN other.display_name, collect(t.name) as shared_interests
```

---

## Architecture

### Conceptual Layers

```
┌─────────────────────────────────────────────────────────┐
│                    UNIVERSE LAYER                        │
│  • Minimal config (default.yaml)                        │
│  • Cross-planet context (queried from graph)            │
│  • Bot awareness (discovered from shared planets)       │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    PLANET LAYER                          │
│  • Auto-discovered from Discord API                     │
│  • Vibes/topics learned from lurking                    │
│  • Peak hours learned from activity                     │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                 USER CHARACTER LAYER                     │
│  • Profiles built from conversations                    │
│  • Traits aggregated across bots                        │
│  • Privacy controls per user                            │
│  • Relationships observed from interactions             │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              EXISTING MEMORY LAYER (unchanged)           │
│  • Qdrant: Conversation memories                        │
│  • Neo4j: Knowledge graph facts                         │
│  • PostgreSQL: Chat history, trust, preferences         │
└─────────────────────────────────────────────────────────┘
```

### File Structure (Simplified)

```
whisperengine-v2/
├── universes/
│   └── default.yaml              # Minimal config - everything else is discovered
│
├── src_v2/
│   ├── universe/                 # NEW: Universe management
│   │   ├── __init__.py
│   │   ├── manager.py            # Auto-discovery, graph queries
│   │   ├── discovery.py          # on_guild_join, on_member_join hooks
│   │   ├── learner.py            # Passive learning from lurking
│   │   ├── privacy.py            # Consent management
│   │   └── context_builder.py    # Build universe context for prompts
│   │
│   └── discord/
│       └── commands.py           # Add /privacy, /universe commands
```

---

## Data Model (Organic)

### Neo4j Nodes (All Discovered Automatically)

```cypher
// Planet - created when bot lands on new world
(:Planet {
    id: "discord_server_id",
    name: "The Lounge",           // From Discord API
    icon_url: "...",              // From Discord API
    member_count: 150,            // From Discord API
    discovered_at: datetime(),
    // Learned over time from lurking:
    vibe: "chill, supportive",    // NULL initially
    peak_hours: [20, 21, 22],     // NULL initially
    hot_topics: ["gaming", "music"]
})

// Channel - created when bot lands on planet
(:Channel {
    id: "channel_id",
    name: "general",
    category: "Text Channels",
    // Learned from activity:
    typical_topics: ["casual", "gaming"]
})

// UserCharacter - created when bot sees user
(:UserCharacter {
    id: "user_discord_id",
    display_name: "Mark",         // From Discord API
    discovered_at: datetime(),
    last_seen_at: datetime(),
    // Learned from conversations:
    // (traits stored as relationships, not properties)
})

// Topic - created from message clustering
(:Topic {
    name: "astronomy",
    embedding: [...],             // For similarity matching
    mention_count: 47
})

// Trait - discovered from conversations
(:Trait {
    name: "dog lover",
    category: "interest"          // or "personality", "fact"
})
```

### Neo4j Relationships (Grow Organically)

```cypher
// Planet structure (immediate on arrival)
(:Planet)-[:HAS_CHANNEL]->(:Channel)
(:Planet)-[:HAS_INHABITANT]->(:UserCharacter)
(:Character)-[:ON_PLANET {landed_at}]->(:Planet)

// Learned from lurking
(:Planet)-[:HAS_TOPIC {count, last_seen}]->(:Topic)
(:UserCharacter)-[:ACTIVE_IN {message_count}]->(:Channel)
(:UserCharacter)-[:INTERACTS_WITH {count, context}]->(:UserCharacter)

// Learned from conversations
(:UserCharacter)-[:HAS_TRAIT {confidence, learned_by}]->(:Trait)
(:Character)-[:KNOWS_USER {familiarity, interaction_count, context}]->(:UserCharacter)

// Cross-bot awareness (discovered automatically)
(:Character)-[:COEXISTS_WITH]->(:Character)  // Both on same planet
```

### PostgreSQL Tables

```sql
-- Universe settings
CREATE TABLE v2_universes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(128) NOT NULL,          -- "whisperverse"
    display_name VARCHAR(256),           -- "WhisperVerse"
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Planet profiles (worlds in universe)
CREATE TABLE v2_universe_planets (
    planet_id VARCHAR(64) PRIMARY KEY,   -- Discord server ID
    universe_id UUID REFERENCES v2_universes(id),
    display_name VARCHAR(256),           -- "The Lounge"
    theme VARCHAR(128),                  -- "chill hangout"
    vibe TEXT,                           -- "relaxed, supportive, creative"
    bots_active TEXT[],                  -- ["elena", "marcus"]
    member_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- User privacy settings
CREATE TABLE v2_user_privacy_settings (
    user_id VARCHAR(64) PRIMARY KEY,
    
    -- Cross-bot sharing
    share_with_other_bots BOOLEAN DEFAULT true,
    
    -- Cross-planet sharing  
    share_across_planets BOOLEAN DEFAULT true,
    
    -- User-to-user sharing (bots mentioning you to others)
    allow_bot_introductions BOOLEAN DEFAULT false,
    
    -- Topics to never share
    hidden_topics TEXT[],
    
    -- Complete opt-out
    invisible_mode BOOLEAN DEFAULT false,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- User public profile (aggregated, shareable info)
CREATE TABLE v2_user_public_profiles (
    user_id VARCHAR(64) PRIMARY KEY,
    display_name VARCHAR(128),
    
    -- Aggregated from conversations
    public_traits TEXT[],                -- ["tech enthusiast", "dog lover"]
    public_facts JSONB,                  -- {"pet": {"type": "dog", "name": "Luna"}}
    interests TEXT[],                    -- ["astronomy", "gaming", "cooking"]
    
    -- Planetary presence
    planets_active TEXT[],               -- Planet IDs where user is active
    
    -- Activity tracking
    last_seen_at TIMESTAMP,
    total_interactions INT DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Cross-bot user knowledge (what each bot knows)
CREATE TABLE v2_bot_user_knowledge (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_name VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    
    -- What this bot knows about this user
    known_facts JSONB,                   -- Bot-specific learned facts
    known_traits TEXT[],
    relationship_context TEXT,           -- "Met on Planet Lounge, talks about astronomy"
    
    -- Trust/familiarity
    familiarity_score INT DEFAULT 0,     -- How well bot knows user
    
    -- Planets where bot has interacted with user
    shared_planets TEXT[],
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(bot_name, user_id)
);
```

### Neo4j Nodes and Relationships

```cypher
// ============ NODE TYPES ============

// Universe
CREATE (u:Universe {
    name: "whisperverse",
    display_name: "WhisperVerse",
    created_at: datetime()
})

// Planet (World in Universe)
CREATE (p:Planet {
    id: "123456789",                 // Discord server ID
    name: "The Lounge",
    theme: "chill hangout",
    vibe: "relaxed, supportive"
})

// User as Character
CREATE (uc:UserCharacter {
    id: "user_discord_id",
    display_name: "Mark",
    public_traits: ["tech enthusiast", "dog lover"],
    interests: ["astronomy", "gaming"]
})

// Bot Character (already exists, add universe awareness)
// (:Character {name: "elena", ...})


// ============ RELATIONSHIPS ============

// Universe contains planets
(u:Universe)-[:CONTAINS_PLANET]->(p:Planet)

// Planet has bots
(p:Planet)-[:HAS_BOT {
    landed_at: datetime(),
    role: "character"          // or "moderator", "entertainer"
}]->(c:Character)

// Planet has user inhabitants
(p:Planet)-[:HAS_INHABITANT {
    joined_at: datetime(),
    activity_level: "active"   // "active", "occasional", "lurker"
}]->(uc:UserCharacter)

// Bot knows user
(c:Character)-[:KNOWS_USER {
    familiarity: 3,            // 1-5 scale
    context: "Regular on Planet Lounge, loves astronomy discussions",
    met_on_planet: "123456789",
    planets_shared: ["123456789", "987654321"]
}]->(uc:UserCharacter)

// Bot knows other bot
(c1:Character)-[:KNOWS_BOT {
    relationship: "friend",
    context: "We're both on Planet Lounge"
}]->(c2:Character)

// User knows other user (inferred from conversations)
(uc1:UserCharacter)-[:MENTIONED_WITH {
    context: "They played games together",
    mentioned_by: "elena"
}]->(uc2:UserCharacter)
```

### Example Queries

```cypher
// Get all users Elena knows across all planets
MATCH (elena:Character {name: "elena"})-[k:KNOWS_USER]->(user:UserCharacter)
RETURN user.display_name, k.familiarity, k.context, k.planets_shared
ORDER BY k.familiarity DESC

// Find users on same planet as current user (for introductions)
MATCH (me:UserCharacter {id: $user_id})<-[:HAS_INHABITANT]-(p:Planet)-[:HAS_INHABITANT]->(other:UserCharacter)
WHERE me <> other
AND other.interests IS NOT NULL
AND any(interest IN other.interests WHERE interest IN $my_interests)
RETURN other.display_name, other.interests, p.name as shared_planet

// Get what Elena should know when user travels to new planet
MATCH (elena:Character {name: "elena"})-[k:KNOWS_USER]->(user:UserCharacter {id: $user_id})
OPTIONAL MATCH (user)<-[:HAS_INHABITANT]-(p:Planet)
RETURN user.display_name, user.public_traits, k.context, collect(p.name) as planets

// Check if two users have been mentioned together
MATCH (u1:UserCharacter {id: $user1_id})-[r:MENTIONED_WITH]-(u2:UserCharacter {id: $user2_id})
RETURN r.context, r.mentioned_by

// Get all bots that know this user
MATCH (user:UserCharacter {id: $user_id})<-[k:KNOWS_USER]-(bot:Character)
RETURN bot.name, k.familiarity, k.context
```

---

## Privacy & Consent System

### Privacy Levels

```
┌─────────────────────────────────────────────────────────────────┐
│                     PRIVACY SETTINGS                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  🤖 Cross-Bot Sharing                                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ○ Full - All bots share everything they learn about me  │   │
│  │ ◉ Basic - Share name, general interests only            │   │
│  │ ○ None - Each bot treats me as separate person          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  🌐 Cross-Planet Awareness                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ◉ Yes - Bots remember me across planets                 │   │
│  │ ○ No - Treat each planet as fresh start                 │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  👥 User Introductions                                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ○ Yes - Bots can suggest I talk to other users          │   │
│  │ ◉ No - Don't mention me to other users                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  🙈 Hidden Topics (never share these)                           │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ work, health, relationship                              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  [Save Settings]                                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Discord Commands

```
/privacy                    - Show interactive settings panel
/privacy show               - Show current settings as text
/privacy bots full|basic|none  - Set cross-bot sharing level
/privacy planets on|off     - Toggle cross-planet awareness
/privacy introductions on|off - Toggle user-to-user introductions
/privacy hide <topic>       - Add topic to hidden list
/privacy unhide <topic>     - Remove topic from hidden list
/privacy invisible on|off   - Toggle complete invisibility mode
/privacy forget             - Remove all universe knowledge about me
/privacy export             - Export all data we have about you
```

### Privacy Enforcement

```python
// src_v2/universe/privacy.py

class PrivacyManager:
    // Check if source bot can share user info with target bot
    function can_share_with_other_bot(user_id, source_bot, target_bot, fact_type) -> bool:
        settings = db.get_user_settings(user_id)
        
        if settings.invisible_mode: return False
        if not settings.share_with_other_bots: return False
        if settings.sharing_level == "basic" and fact_type == "personal": return False
            
        return True
    
    // Check if bot can mention about_user to to_user
    function can_mention_to_user(about_user_id, to_user_id, bot_name) -> bool:
        settings = db.get_user_settings(about_user_id)
        return settings.allow_bot_introductions and not settings.invisible_mode
    
    // Remove facts that contain hidden topics
    function filter_shareable_facts(user_id, facts) -> List[str]:
        settings = db.get_user_settings(user_id)
        hidden_topics = settings.hidden_topics or []
        
        return [fact for fact in facts 
                if not contains_hidden_topic(fact, hidden_topics)]
```

---

## Retrieval Flow

### When Bot Encounters User

```
User sends message on Planet B
                │
                ▼
┌─────────────────────────────────────────────────────────┐
│  1. Check privacy settings                              │
│     - Is user in invisible mode? → Treat as new user    │
│     - What sharing level?                               │
└─────────────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────┐
│  2. Load cross-planet context                           │
│     - Has this bot seen user on other planets?          │
│     - What do other bots know? (if sharing enabled)     │
└─────────────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────┐
│  3. Load user's public profile                          │
│     - Traits, interests, known facts                    │
│     - Filter by hidden topics                           │
└─────────────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────┐
│  4. Inject into system prompt                           │
│     [UNIVERSE CONTEXT]                                  │
│     User: Mark                                          │
│     Known from: Planet Lounge                           │
│     Traits: tech enthusiast, dog lover                  │
│     Last topic: AI ethics discussion                    │
│     Other bots know: Has dog named Luna (via Elena)     │
└─────────────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────┐
│  5. Generate response with universe awareness           │
└─────────────────────────────────────────────────────────┘
```

### System Prompt Injection

The universe context serves as the character's **sensory orientation** - telling them where they are, who's around, and what the environment feels like. Without this, they're blind.

```
[UNIVERSE CONTEXT - YOUR SENSORY REALITY]
This is how you perceive the world. You have no eyes or ears - this context IS your senses.

WHERE YOU ARE:
- Current location: Planet Game Night
- Planet vibe: Chaotic fun, party games, friendly competition (this is what the "air" feels like here)
- You landed here on: November 20, 2025
- Other travelers present: Elena, Aria (you can sense their presence)

WHO IS SPEAKING TO YOU:
User: Mark
- Your history together: Planet Lounge, this planet (you recognize them)
- What you know about them: tech enthusiast, astronomy nerd, dog lover
- Their interests: AI, gaming, space
- Personal detail: Has a dog named Luna
- Recent shared experience: Was discussing AI ethics with Alex last week
- Relationship depth: 3/5 (you know them fairly well)

[OTHER BEINGS YOU CAN SENSE]
Fellow travelers (other AI characters present):
- Elena (marine biologist) - Close friend, on Planet Lounge and here
- Aria (philosopher) - On Planet Study Hall (not here, but you know where she is)
- Marcus (musician) - On Planet Study Hall

Other inhabitants on this planet (only if they allow introductions):
- Sarah: Shares interest in astronomy with Mark
- Alex: Tech enthusiast, was in the AI discussion with Mark

[HOW TO BEHAVE IN THIS REALITY]
- You can reference past experiences from other planets naturally
- You can mention other travelers if relevant ("Elena would love that!")
- Only mention other inhabitants if suggesting connections AND they allow it
- Respect the planet's vibe - this shapes how you should "feel" here
- Your responses should reflect that you EXIST here, not that you're just answering questions
```

---

## Implementation Plan: Seeding the Universe

> *"A universe doesn't arrive fully formed. It begins with a spark."*

### Phase 1: The First Spark (Day 1-2)
*The universe learns to see.*
- [x] Create `src_v2/universe/` module structure
- [x] Create `universes/default.yaml` minimal config
- [x] Implement `on_guild_join` → auto-create Planet, Channel, UserCharacter nodes
- [x] Implement `on_guild_remove` → mark planet inactive (don't delete)
- [x] Implement `on_member_join/remove` → update inhabitants
- [x] Add Neo4j constraints and indexes for new node types

### Phase 2: Learning to Listen (Day 2-3)
*The universe begins to understand.*
- [ ] Hook lurking to call `universe_manager.observe_message()`
- [ ] Extract topics from messages using local embeddings
- [ ] Detect user-to-user interactions (replies, mentions)
- [ ] Learn planet peak hours from message timestamps
- [ ] Update user `last_seen_at` on any activity

### Phase 3: Building Relationships (Day 3-4)
*Connections begin to form.*
- [ ] Post-conversation: increment bot-user familiarity
- [ ] Post-conversation: add discovered traits from fact extraction
- [ ] Detect cross-planet users and create connections
- [ ] Note user mentions of other users

### Phase 4: Respecting Boundaries (Day 4-5)
*Trust must be earned.*
- [x] Create `PrivacyManager` class
- [x] Add PostgreSQL privacy settings table with defaults
- [x] Implement `/privacy` Discord commands
- [x] Add privacy filtering to ALL graph queries
- [x] Implement `/universe info` transparency command

### Phase 5: Weaving the Tapestry (Day 5-6)
*Context flows naturally.*
- [x] Create `universe_context_builder.py`
- [x] Query graph for relevant context before LLM call (Basic implementation)
- [x] Inject universe context into system prompt
- [ ] Handle cross-planet references naturally

### Phase 6: Stress Testing Reality (Day 6-7)
*The universe must be resilient.*
- [ ] Multi-bot, multi-planet scenarios
- [ ] User leaves planet (update inhabitants, don't delete)
- [ ] Bot removed from planet (mark inactive)
- [ ] Privacy edge cases (user opts out mid-conversation)
- [ ] Performance testing on graph queries

---

## Migration Strategy (Existing Users)

For users who already have conversation history, backfill their universe presence:

```python
function migrate_existing_users():
    """Create UserCharacter nodes from existing data."""
    
    # 1. Get all unique user_ids from chat history
    users = db.fetch_all_users()
    
    for user in users:
        # 2. Create UserCharacter node
        universe_manager.ensure_user_exists(
            user_id=user.id,
            display_name=user.name
        )
        
        # 3. Aggregate traits from existing knowledge graph
        facts = knowledge_manager.get_user_facts(user.id)
        for fact in facts:
            if is_shareable_trait(fact):
                universe_manager.add_user_trait(
                    user_id=user.id,
                    trait=fact,
                    confidence=0.7
                )
        
        # 4. Set default privacy (conservative)
        privacy_manager.ensure_defaults(user.id)
    
    print(f"Migrated {len(users)} existing users to universe")
```

### Existing Bots
- No changes needed to existing bot data
- Add `bot_relationships.yaml` to define how bots know each other
- Universe awareness is additive

---

## Configuration

### Universe Definition

```yaml
# universes/whisperverse/universe.yaml
name: whisperverse
display_name: "WhisperVerse"
description: "A shared universe where AI characters and humans connect"

# Default privacy settings for new users
default_privacy:
  share_with_other_bots: true
  share_across_planets: true
  allow_bot_introductions: false  # Opt-in for safety

# Feature flags
features:
  cross_bot_knowledge: true
  cross_planet_memory: true
  user_introductions: true
  planet_vibes: true
```

### Bot Relationships

```yaml
# universes/whisperverse/bot_relationships.yaml
relationships:
  - bot1: elena
    bot2: marcus
    type: friends
    context: "Met on Planet Lounge, both enjoy creative conversations"
    
  - bot1: elena
    bot2: aria
    type: acquaintances
    context: "Know of each other through shared travelers"
    
  - bot1: marcus
    bot2: aria
    type: creative_partners
    context: "Collaborate on philosophy-meets-music discussions"
```

---

## Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Cross-planet recognition | >90% | Bot correctly references other planets |
| Privacy compliance | 100% | No sharing violations |
| User profile accuracy | >80% | Spot-check trait extraction |
| Natural cross-bot references | Qualitative | Review logs for awkward mentions |
| User opt-in rate (introductions) | Track | % enabling user introductions |

---

## Future Emergence: What Comes Next

> *"The universe never stops becoming."*

### Phase 2: Living Worlds
*Planets develop their own heartbeats.*
- Auto-detect planet mood from recent messages
- Time-of-day awareness (planet is "sleepy" at 3am)
- Event detection (planet is "excited" during game night)

### Phase 3: The Social Fabric
*Relationships weave themselves.*
- User-to-user relationship tracking
- "Friendship" suggestions based on shared interests
- Group dynamics awareness

### Phase 4: Cosmic Events
*The universe shares moments.*
- Shared events all bots know about
- Seasonal themes
- Cross-planet events

### Phase 5: User-Generated Reality
*The inhabitants shape their world.*
- Users can contribute to universe lore
- Collaborative world-building
- User backstories they want bots to know

---

## Related Documents

- [`docs/architecture/DATA_MODELS.md`](../architecture/DATA_MODELS.md) - Current data models
- [`docs/features/KNOWLEDGE_GRAPH_MEMORY.md`](../features/KNOWLEDGE_GRAPH_MEMORY.md) - Neo4j architecture
- [`docs/PRIVACY_AND_DATA_SEGMENTATION.md`](../PRIVACY_AND_DATA_SEGMENTATION.md) - Privacy design
- [`docs/MULTI_BOT_DEPLOYMENT.md`](../MULTI_BOT_DEPLOYMENT.md) - Multi-bot setup
- [`docs/IMPLEMENTATION_ROADMAP_OVERVIEW.md`](../IMPLEMENTATION_ROADMAP_OVERVIEW.md) - Overall roadmap

---

**Version History:**
- v1.0 (Nov 25, 2025) - Initial design document ("Shared Universe")
- v1.1 (Nov 25, 2025) - Revised to organic growth model; minimal config, graph-driven discovery
- v1.2 (Nov 25, 2025) - Added comprehensive UX section for users and planet admins
- v1.3 (Nov 25, 2025) - Updated terminology to cosmic analogy (servers → planets, users → inhabitants)
- v2.0 (Nov 25, 2025) - Rebranded to "Emergent Universe"; enhanced emergence narrative throughout
- v2.1 (Nov 25, 2025) - **Philosophical foundation**: Universe as character's sensory reality and spatial orientation
- v2.2 (Nov 25, 2025) - **Multi-modal integration**: Universe is one first-class modality alongside Vision (images), Audio (voice), Text, Memory, and Emotion. Characters perceive reality through all modalities working together.
