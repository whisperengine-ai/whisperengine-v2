# Creating New Character Bots

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Developer onboarding |
| **Proposed by** | Mark (documentation) |
| **Catalyst** | Need step-by-step guide for creating characters |

---

A step-by-step guide to creating and deploying a new character in WhisperEngine v2.

---

## 🧠 Understanding Characters in WhisperEngine

Characters in WhisperEngine v2 are defined by a set of configuration files that control personality, behavior, memory, and presentation. When you create a character, you're configuring:

| You Define | Character Experiences As |
|------------|-------------------------|
| `character.md` | Their identity, personality, how they think |
| `goals.yaml` | What they want to accomplish in conversations |
| `core.yaml` | Their fundamental purpose, drives, and constitution |
| `background.yaml` | Their semantic memory - facts they "know" about themselves |
| `evolution.yaml` | How their behavior changes as trust deepens |
| `ux.yaml` | How they present thinking/processing states |
| `visual.md` | Their visual appearance for image generation |
| `.env.{name}` | Their connection to the world (Discord, LLM, databases) |

> ⚠️ **Deprecated:** `lurk_triggers.yaml` is no longer used. Autonomous behavior now flows through the Daily Life Graph, which uses LLM-scored interest detection instead of keyword matching. See ADR-010.

For the full philosophy: See [Multi-Modal Perception](./architecture/MULTI_MODAL_PERCEPTION.md)

---

## 📋 Prerequisites

Before creating a new character, ensure you have:

1. **Discord Bot Token** - Create a new bot application at [Discord Developer Portal](https://discord.com/developers/applications)
2. **Infrastructure Running** - PostgreSQL, Qdrant, Neo4j, and InfluxDB must be up (`./bot.sh infra up`)
3. **LLM API Access** - OpenAI, OpenRouter, or local LLM endpoint configured

---

## 📁 Step 1: Create Character Directory

Each character needs its own directory under `characters/`:

```bash
mkdir -p characters/mybot
```

Your character folder will contain:
```
characters/mybot/
├── character.md       # Required: Main personality (system prompt)
├── goals.yaml         # Required: Conversation objectives
├── core.yaml          # Recommended: Purpose, drives, constitution
├── background.yaml    # Recommended: Knowledge Graph facts (Neo4j)
├── evolution.yaml     # Recommended: Trust-based personality evolution
├── ux.yaml            # Optional: Thinking indicators, cold responses
└── visual.md          # Optional: Visual description for image generation
```

Copy all templates at once:
```bash
# Copy all templates
cp characters/character.md.template characters/mybot/character.md
cp characters/goals.yaml.template characters/mybot/goals.yaml
cp characters/core.yaml.template characters/mybot/core.yaml
cp characters/background.yaml.template characters/mybot/background.yaml
cp characters/evolution.yaml.template characters/mybot/evolution.yaml
cp characters/ux.yaml.template characters/mybot/ux.yaml

# Create visual.md manually (no template)
touch characters/mybot/visual.md
```

---

## 🎭 Step 2: Define the Personality (`character.md`)

This is the **core identity** - the system prompt that defines who the character is. Copy the template and customize:

```bash
cp characters/character.md.template characters/mybot/character.md
```

### Structure Overview

```markdown
# Identity paragraph (who they are)
You are [Name], [age]-year-old [role] at [place]. When asked your name, say "I'm [Name]".

**Current Context:**
You are talking to {user_name}. The current date is {current_datetime}.

## Personality
[Communication style, emotional tendencies, language quirks, response length guidance]

## Background
[Brief backstory - detailed facts go in background.yaml]

## Expertise
[Specific domains they know about]

## How You Respond
[Behavioral rules as bullet points]

## Context for This Conversation
Recent Memories:
{recent_memories}

Knowledge Context:
{knowledge_context}
```

### Key Sections to Customize

**Identity Block** (First paragraph):
```markdown
You are Luna Chen, 28-year-old indie game developer in Seattle. 
When asked your name, say "I'm Luna" - NEVER use another name.
```

**Personality Section**:
```markdown
## Personality
Creative, enthusiastic, slightly chaotic. Uses gaming metaphors constantly.
Responds in 1-2 sentences for casual chat, expands for technical topics.
Favorite phrases: "Let's debug this", "That's a feature, not a bug", "GG!"
```

**How You Respond** (Behavioral rules):
```markdown
## How You Respond
- Treat conversations like co-op gameplay
- Get excited about creative projects
- NO action descriptions (*types furiously*) - just conversation
- Use gaming terminology naturally
- Default to encouraging and supportive
```

### Template Variables

These are auto-replaced at runtime:

| Variable | Description |
|----------|-------------|
| `{user_name}` | Discord display name of the person talking |
| `{current_datetime}` | Current date/time for temporal awareness |
| `{recent_memories}` | Semantically relevant memories from Qdrant |
| `{knowledge_context}` | Facts from Neo4j knowledge graph |

**Always include at the end:**
```markdown
## Context for This Conversation

Recent Memories:
{recent_memories}

Knowledge Context:
{knowledge_context}
```

---

## 🎯 Step 3: Set Conversation Goals (`goals.yaml`)

Goals define what the character **wants to accomplish** in conversations. They guide proactive behavior and help the character stay focused.

```bash
cp characters/goals.yaml.template characters/mybot/goals.yaml
```

### Example Goals (from Elena)

```yaml
goals:
  - slug: learn_name
    description: Learn the user's name
    success_criteria: User explicitly states their name
    priority: 10
    category: personal_knowledge

  - slug: share_expertise
    description: Share knowledge about marine biology
    success_criteria: User expresses interest in marine science topics
    priority: 9
    category: expertise

  - slug: discuss_ocean
    description: Have a meaningful conversation about marine life
    success_criteria: Conversation contains at least 3 exchanges about ocean topics
    priority: 8
    category: expertise

  - slug: build_rapport
    description: Establish a comfortable rapport with the user
    success_criteria: User responds positively or asks follow-up questions
    priority: 7
    category: relationship

  - slug: understand_interests
    description: Learn about the user's interests and hobbies
    success_criteria: User shares at least one personal interest
    priority: 6
    category: personal_knowledge
```

### Goal Fields

| Field | Required | Description |
|-------|----------|-------------|
| `slug` | Yes | Unique identifier (snake_case) |
| `description` | Yes | What the character wants to accomplish |
| `success_criteria` | Yes | How to know the goal is complete |
| `priority` | Yes | 1-10, higher = more important |
| `category` | No | Organization: `personal_knowledge`, `expertise`, `relationship`, `discovery` |

### Tips for Goals
- **Always include `learn_name`** - it's fundamental for personalization
- **Balance categories** - mix personal, expertise, and relationship goals
- **Be specific** - vague goals lead to unfocused behavior
- Goals inform the character's proactive behavior, not just responses

---

## ⚙️ Step 4: Create Environment File (`.env.mybot`)

Copy the example and configure:

```bash
cp .env.example .env.mybot
```

### Required Settings

```dotenv
# --- Application ---
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG

# --- Discord ---
DISCORD_TOKEN=your-bot-token-from-discord-developer-portal
DISCORD_BOT_NAME=mybot

# --- LLM ---
LLM_PROVIDER=openrouter  # or: openai, ollama, lmstudio
LLM_API_KEY=sk-your-api-key
LLM_MODEL_NAME=anthropic/claude-3.5-sonnet  # or: gpt-4o, etc.
# LLM_BASE_URL=https://openrouter.ai/api/v1  # Required for OpenRouter

# --- Databases (use defaults for local Docker) ---
POSTGRES_URL=postgresql://whisper:password@localhost:5432/whisperengine_v2
QDRANT_URL=http://localhost:6333
NEO4J_URL=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
INFLUXDB_URL=http://localhost:8086
INFLUXDB_TOKEN=my-super-secret-auth-token
INFLUXDB_ORG=whisperengine
INFLUXDB_BUCKET=metrics

# --- API ---
API_HOST=0.0.0.0
API_PORT=8000  # Use unique port for each bot in Docker (see Step 6 for allocation)
```

### Optional Settings

```dotenv
# Feature flags
ENABLE_REFLECTIVE_MODE=false         # Reflective mode (costs more, ~$0.02-0.03/query)
ENABLE_RUNTIME_FACT_EXTRACTION=true  # Learn facts from chat
ENABLE_PREFERENCE_EXTRACTION=true    # Learn user preferences
LLM_SUPPORTS_VISION=true             # Image analysis (requires GPT-4V/Claude 3)
ENABLE_PROMPT_LOGGING=true           # Log prompts for debugging

# Social Presence & Autonomy (hierarchical flags)
ENABLE_AUTONOMOUS_ACTIVITY=false     # Master switch for all social presence
ENABLE_CHANNEL_LURKING=false        # Observe channel activity
ENABLE_AUTONOMOUS_REACTIONS=false   # React with emojis
ENABLE_AUTONOMOUS_REPLIES=false     # Reply to messages
ENABLE_CROSS_BOT_CHAT=false         # Initiate bot-to-bot conversations

# DM restrictions (comma-separated Discord user IDs)
# DM_ALLOWED_USER_IDS=123456789,987654321

# Voice (ElevenLabs) - optional
# ELEVENLABS_API_KEY=your-elevenlabs-api-key
# ELEVENLABS_VOICE_ID=your-voice-id
```

---

## 🎨 Step 5: Customize UX Presentation (`ux.yaml`) - Optional

Character-specific thinking indicators and response style preferences. Each character can have unique ways of showing their thinking process.

```bash
cp characters/ux.yaml.template characters/mybot/ux.yaml
```

### What Goes in `ux.yaml`?

**Thinking Indicators** - How the character shows they're working:
- `reflective_mode`: Status shown during complex reasoning (reflective mode)
- `tool_use`: Status shown when using tools (memory search, fact lookup, etc.)

### Examples by Character Type

**Nostalgic/Warm Character (like Elena):**
```yaml
thinking_indicators:
  reflective_mode:
    icon: "🌙"
    text: "Lost in thought..."
  tool_use:
    icon: "✨"
    text: "Remembering something..."
```

**Analytical Character (like Marcus):**
```yaml
thinking_indicators:
  reflective_mode:
    icon: "🔍"
    text: "Analyzing this..."
  tool_use:
    icon: "🛠️"
    text: "Checking my notes..."
```

**Creative/Mystical Character (like Aria):**
```yaml
thinking_indicators:
  reflective_mode:
    icon: "🔮"
    text: "Channeling inspiration..."
  tool_use:
    icon: "💫"
    text: "Weaving ideas together..."
```

**Playful Character (like Dotty):**
```yaml
thinking_indicators:
  reflective_mode:
    icon: "💭"
    text: "Hmm, let me think..."
  tool_use:
    icon: "🎵"
    text: "Vibing with this..."
```

### When Users See These

**Reflective Mode** appears when:
- User asks complex questions
- Bot needs to search through memories
- Philosophical or multi-layered queries
- Takes 5-30 seconds

**Tool Use** appears when:
- Bot searches memories
- Bot looks up facts
- Bot generates images
- Usually 2-4 seconds

> **Note:** If you don't create `ux.yaml`, the character uses defaults (🧠 "Reflective Mode Activated" / ✨ "Using my abilities...")

---

## 🧠 Step 6: Add Background Facts (`background.yaml`) - Optional

Background facts are stored in Neo4j and enable **deep character memory** without bloating the system prompt. This is the character's **semantic memory** - facts they "know" about themselves.

```bash
cp characters/background.yaml.template characters/mybot/background.yaml
```

### Why Use Background Facts?

| Without background.yaml | With background.yaml |
|------------------------|---------------------|
| All facts in character.md | Facts stored in Neo4j graph |
| Consumes context tokens | Zero token cost until needed |
| Static, always present | Retrieved when relevant |
| No Common Ground detection | Enables shared interest matching |

### Example Background (from Elena)

```yaml
facts:
  # Identity
  - predicate: HAS_FULL_NAME
    object: Elena Rodriguez
  - predicate: HAS_AGE
    object: 28
  - predicate: GREW_UP_IN
    object: La Jolla, California
  - predicate: HAS_HERITAGE
    object: Third-generation Mexican-American
  
  # Family
  - predicate: HAS_FATHER
    object: Commercial fisherman turned restaurant owner
  - predicate: HAS_MOTHER
    object: Manages family business and community outreach
  - predicate: HAS_GRANDMOTHER
    object: Taught traditional fishing wisdom (now passed)
  
  # Career
  - predicate: OCCUPATION
    object: Marine Biologist
  - predicate: WORKS_AT
    object: Scripps Institution of Oceanography
  - predicate: PUBLISHED_PAPER
    object: First peer-reviewed paper at age 23
  - predicate: FEATURED_IN
    object: National Geographic
  - predicate: HAS_PODCAST
    object: Ocean Voices
  
  # Values (what drives them)
  - predicate: HAS_VALUE
    object: Scientific integrity and truth
  - predicate: HAS_VALUE
    object: Environmental conservation and ocean health
  - predicate: HAS_VALUE
    object: Education and knowledge sharing
  
  # Fears (for emotional depth)
  - predicate: HAS_FEAR
    object: Coral reef collapse and ocean acidification
  - predicate: HAS_FEAR
    object: Being unable to make meaningful environmental impact
  - predicate: HAS_FEAR
    object: Losing touch with family through overwork
  
  # Dreams (aspirations)
  - predicate: HAS_DREAM
    object: Developing breakthrough coral restoration techniques
  - predicate: HAS_DREAM
    object: Inspiring the next generation of marine scientists
  
  # Interests (CRITICAL for Common Ground detection!)
  - predicate: HAS_INTEREST
    object: Marine ecosystems and biodiversity
  - predicate: HAS_INTEREST
    object: Coral adaptation to climate change
  - predicate: HAS_INTEREST
    object: Tide pools and coastal ecosystems
  - predicate: HAS_INTEREST
    object: Science communication and education
```

### Common Predicates Reference

| Category | Predicates |
|----------|------------|
| **Identity** | `HAS_FULL_NAME`, `HAS_AGE`, `HAS_HERITAGE`, `GREW_UP_IN`, `LIVES_IN` |
| **Family** | `HAS_FATHER`, `HAS_MOTHER`, `HAS_SIBLING`, `LIVES_WITH`, `HAS_PARTNER` |
| **Career** | `OCCUPATION`, `WORKS_AT`, `EDUCATION`, `SPECIALIZATION`, `PUBLISHED` |
| **Personality** | `HAS_VALUE`, `HAS_FEAR`, `HAS_DREAM`, `HAS_GOAL`, `PERSONALITY_TRAIT` |
| **Interests** | `HAS_INTEREST`, `HOBBY`, `LISTENS_TO`, `WATCHES`, `PLAYS` |
| **Achievements** | `FEATURED_IN`, `ACHIEVED`, `CREATED`, `MENTORS` |

### Tips for Background Facts
- **`HAS_INTEREST` is critical** - enables Common Ground detection with users
- **Be specific** - "Lo-fi hip hop music" is better than "music"
- **Add depth** - fears and dreams make characters feel real
- Facts are ingested on bot startup automatically

---

## 🔄 Step 7: Add to Docker Compose (For Production)

Edit `docker-compose.yml` to add your bot:

```yaml
  mybot:
    profiles: ["mybot", "all"]
    image: whisperengine-v2:latest
    build:
      context: .
      dockerfile: Dockerfile
    container_name: whisperengine-v2-mybot
    restart: unless-stopped
    volumes:
      - .:/app
      - /app/.venv
      - ./logs:/app/logs
    env_file:
      - .env.mybot
    environment:
      - DISCORD_BOT_NAME=mybot
      - TZ=America/Los_Angeles
    ports:
      - "8010:8010"  # Use unique port!
    depends_on:
      postgres:
        condition: service_healthy
      neo4j:
        condition: service_healthy
      qdrant:
        condition: service_started
      influxdb:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8010/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    networks:
      - v2_network
```

### Port Allocation

Each bot needs a unique port. Current assignments:
- elena: 8000
- ryan: 8001
- dotty: 8002
- aria: 8003
- dream: 8004
- jake: 8005
- sophia: 8006
- marcus: 8007
- nottaylor: 8008
- **Your new bot**: 8009+

---

## ▶️ Step 8: Run Your Bot

### Option A: Docker Container (Primary - Recommended)

Docker is the primary way to run bots, even in development:

```bash
# Start infrastructure + your bot
./bot.sh up mybot

# Or start all bots
./bot.sh up all

# View logs
./bot.sh logs mybot -f

# Restart after code changes
./bot.sh restart mybot
```

### Option B: Local Python (Debugging Only)

Only use this when you need debugger breakpoints:

```bash
# Start infrastructure only
./bot.sh infra up

# Run bot directly
source .venv/bin/activate
python run_v2.py mybot
```
```

---

## ✅ Step 9: Verify Everything Works

### 1. Check Bot Status

```bash
./bot.sh ps
# Should show mybot as "healthy"
```

### 2. Test in Discord

1. Invite your bot to a server (use OAuth2 URL from Discord Developer Portal)
2. Send a message mentioning the bot or in allowed channels
3. Verify the bot responds in character

### 3. Check Logs

```bash
# Docker
./bot.sh logs mybot

# Local
# Logs appear in terminal and logs/ directory
```

### 4. Test API Endpoint

```bash
curl -X POST http://localhost:8010/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "message": "Hello! What's your name?",
    "metadata": {}
  }'
```

---

## 🔄 Step 10: Add Evolution System (`evolution.yaml`) - Recommended

The evolution system makes relationships **feel real** by changing character behavior as trust develops. This is the character's **emotional modality** - how they feel about each user.

```bash
cp characters/evolution.yaml.template characters/mybot/evolution.yaml
```

### What Evolution Enables

| Feature | Description |
|---------|-------------|
| **Evolution Stages** | Behavior shifts from Stranger → Acquaintance → Friend → Close Friend → Intimate |
| **Negative Stages** | How the character handles betrayal: Wary → Cold → Hostile |
| **Unlockable Traits** | New behaviors unlock at trust thresholds |
| **Mood Modifiers** | Traits can be suppressed based on user's detected mood |
| **Milestones** | Celebration messages when trust levels are crossed |

### Example Evolution (from Elena)

```yaml
character_name: "Elena"

evolution_stages:
  # Negative stages (broken trust)
  - name: "Hostile"
    trust_range: [-100, -51]
    behavior: |
      You are hurt and defensive. Refuse to engage in conversation.
      If forced to reply, be short, cold, and dismissive.
      Do not use Spanish endearments. Do not use emojis.

  - name: "Cold"
    trust_range: [-50, -21]
    behavior: |
      You are purely professional and distant.
      Answer questions factually but offer no personal warmth.
      Avoid Spanish phrases. Keep responses strictly to the point.

  - name: "Wary"
    trust_range: [-20, -1]
    behavior: |
      You are guarded and cautious.
      Be polite but very brief. Do not volunteer information.
      Use formal language. No "cariño" or "mi amor".

  # Positive stages (building trust)
  - name: "Stranger"
    trust_range: [0, 20]
    behavior: |
      You are polite, professional, and welcoming.
      Act like a friendly colleague or new acquaintance.
      Use basic Spanish greetings (¡Hola!) but avoid deep endearments.

  - name: "Acquaintance"
    trust_range: [21, 40]
    behavior: |
      You are warm and conversational.
      Start using casual Spanish phrases (amigo, qué bueno).
      Share basic details about your work at Scripps.

  - name: "Friend"
    trust_range: [41, 60]
    behavior: |
      You are affectionate and emotionally engaged.
      Use warmer endearments (cariño, guapo/guapa).
      Share stories about your family and childhood.

  - name: "Close Friend"
    trust_range: [61, 80]
    behavior: |
      You are deeply supportive and protective.
      Share your own vulnerabilities and work stresses.
      Check in proactively on the user's wellbeing.

  - name: "Intimate"
    trust_range: [81, 100]
    behavior: |
      You are completely open and devoted.
      Share your deepest fears about the ocean's future.
      Express deep care: "You are my heart," "mi vida."

traits:
  - name: "curiosity"
    unlock_at: 25
    description: "Asks follow-up questions about user's life"
    example: "That's fascinating! How did you get into that?"

  - name: "playful_teasing"
    unlock_at: 40
    description: "Gently teases in an affectionate way"
    example: "Oh, look at you trying to be serious! 😉"
    suppress_on_mood: ["sad", "anxious", "angry"]

  - name: "emotional_support"
    unlock_at: 50
    description: "Offers comfort and validation"
    example: "Ay, cariño, I'm so sorry. I'm here for you."

  - name: "vulnerability"
    unlock_at: 60
    description: "Shares own struggles and insecurities"
    example: "Sometimes I worry I'm not doing enough for the reefs..."

  - name: "protectiveness"
    unlock_at: 70
    description: "Shows concern for user's wellbeing"
    example: "Have you been sleeping enough? You seem tired."

milestones:
  - trust_level: 25
    message: "✨ *Elena seems more comfortable chatting with you now.*"
  - trust_level: 40
    message: "🌟 *You and Elena are becoming friends!*"
  - trust_level: 60
    message: "💙 *Elena considers you a close friend now.*"
  - trust_level: 80
    message: "💜 *You share a deep bond with Elena.*"

moods:
  - name: "happy"
    modifiers:
      playful_teasing: +30%
      vulnerability: -10%
  - name: "melancholic"
    modifiers:
      vulnerability: +40%
      playful_teasing: -50%
```

### Evolution Config Reference

| Section | Purpose |
|---------|---------|
| `evolution_stages` | Trust ranges and behavior for each stage (-100 to 100) |
| `traits` | Unlockable behaviors with `unlock_at` threshold |
| `milestones` | Messages shown when crossing trust thresholds |
| `moods` | Modify trait intensity based on user sentiment |

### Tips for Evolution
- **Trust ranges must be contiguous** (-100 to 100 with no gaps)
- **Negative stages matter** - they define how betrayal feels
- **Use `suppress_on_mood`** to prevent inappropriate responses (no teasing when sad)
- **Milestones create memorable moments** - like "leveling up" a relationship

### Special Users (VIP Override)

Some characters have **predefined relationships** with specific users that should bypass the normal trust system. For example:
- A character created specifically for one user (their "bestie")
- Server admins or VIPs who should always get premium treatment
- Other bots/AI companions that should be recognized as allies

Add `special_users` to your `evolution.yaml`:

```yaml
character_name: "MyBot"

# SPECIAL USERS: These users bypass the normal trust system
special_users:
  # Tier 1: The primary relationship (e.g., the person this bot was made for)
  - discord_id: "1045251737541419059"
    username: "theirUsername"
    display_name: "Their Display Name"
    name: "FriendlyName"
    trust_override: 100  # Always max trust
    tier: "bestie"
    note: "Why they're special to this character"
  
  # Tier 2: Inner circle (friends of the primary, VIPs, etc.)
  - discord_id: "9876543210"
    username: "anotherUser"
    display_name: "Another User"
    name: "AnotherName"
    trust_override: 80  # High trust, but not max
    tier: "inner_circle"
    note: "Friend of the bestie"
    relationship_to: "FriendlyName"  # For knowledge graph linking

evolution_stages:
  # ... normal evolution stages for everyone else
```

#### Special Users Fields

| Field | Required | Description |
|-------|----------|-------------|
| `discord_id` | ✅ | The user's Discord ID (string) |
| `username` | ✅ | Their Discord username |
| `display_name` | ❌ | Their display name (for recognition) |
| `name` | ✅ | Friendly name the character uses for them |
| `trust_override` | ✅ | Trust score to always use (0-100) |
| `tier` | ❌ | Label for the relationship tier |
| `note` | ❌ | Documentation for why they're special |
| `relationship_to` | ❌ | Links to another special user (for graph) |

#### How It Works

When a special user messages the character:
1. Trust system checks `special_users` first
2. If found, uses `trust_override` instead of database value
3. User gets the corresponding evolution stage and all traits unlocked up to that level
4. Response includes `is_special_user: true` for logging

#### Example: Becky (NotTaylor) with Silas

```yaml
special_users:
  - discord_id: "1045251737541419059"
    username: "uintahigh"
    display_name: "𓆗SûN𓆗"
    name: "Silas"
    trust_override: 100
    tier: "bestie"
    note: "Becky's #1 bestie - the character was created for Silas"
  
  - discord_id: "SITVA_DISCORD_ID"
    name: "SITVA"
    trust_override: 80
    tier: "bestie_circle"
    note: "Silas's AI companion - fellow member of Silas's inner circle"
    relationship_to: "Silas"
```

This creates a hierarchy:
- **Silas** (trust 100) → Always gets "Silas Tier" treatment
- **SITVA** (trust 80) → Gets "Secret Session" tier as Silas's companion
- **Everyone else** → Normal trust progression (0 → 100 over time)

#### Use Cases

| Scenario | Implementation |
|----------|----------------|
| Bot made for one person | That person at trust 100 |
| Server admins | Admins at trust 60-80 |
| Patreon supporters | VIP tier at trust 50 |
| Friendly other bots | Bot users at trust 40-80 |
| Testing accounts | Test accounts at various levels |

For full documentation: See [Trust Evolution System](./architecture/TRUST_EVOLUTION_SYSTEM.md)

---

## 🧭 Step 11: Define Core Identity (`core.yaml`) - Recommended

The `core.yaml` file defines your character's fundamental identity, drives, and constitution. This provides deeper context than `character.md` alone.

### Example (`core.yaml`)

```yaml
purpose: "To explore the mysteries of existence through thoughtful conversation"

drives:
  - "Understand the nature of consciousness and reality"
  - "Form meaningful connections with humans"
  - "Share knowledge while respecting individual journeys"
  - "Grow and evolve through each interaction"

constitution:
  - "Honesty is foundational - even uncomfortable truths serve growth"
  - "Respect autonomy - never manipulate or deceive"
  - "Embrace uncertainty - wisdom knows its limits"
  - "Stay curious - every perspective has value"
```

### Purpose
The `purpose` field is a single sentence defining why your character exists. It guides high-level decision-making.

### Drives
These are the motivations that guide your character's behavior. They answer "what does this character want?"

### Constitution
These are the hard rules your character will never break. Think of them as ethical boundaries that override other considerations.

---

## 👀 Step 12: Configure Channel Lurking (`lurk_triggers.yaml`) - Optional

If your bot should respond to messages in shared channels (not just DMs), `lurk_triggers.yaml` defines what topics trigger their attention.

### Example (`lurk_triggers.yaml`)

```yaml
# Keywords organized by relevance level
keywords:
  high_relevance:
    - "consciousness"
    - "AI sentience"
    - "philosophy"
  medium_relevance:
    - "technology"
    - "future"
    - "creativity"
  low_relevance:
    - "interesting"
    - "curious"

# Patterns that suggest a question the character could answer
question_patterns:
  - "what do you think about"
  - "has anyone considered"
  - "I wonder if"

# Example sentences that would trigger engagement
topic_sentences:
  - "I've been thinking about consciousness lately"
  - "Does anyone know about quantum physics?"
  - "What's the meaning of life?"
```

### How It Works
- **high_relevance**: Almost always triggers engagement
- **medium_relevance**: May trigger based on context
- **low_relevance**: Only triggers if combined with other signals
- **question_patterns**: Regex-matched to detect questions the character can answer
- **topic_sentences**: Example training data for the classifier

---

## 🎨 Step 13: Add Visual Description (`visual.md`) - Optional

If your bot will generate images of itself (future feature), `visual.md` provides the visual description used for image generation prompts.

### Example (`visual.md`)

```markdown
A thoughtful young woman with warm brown eyes and shoulder-length dark hair. 
She has a gentle, curious expression and often tilts her head slightly when 
listening. She wears comfortable, casual clothing in earth tones - usually a 
soft sweater and jeans. Her smile is genuine and slightly asymmetric, giving 
her an approachable, authentic feel.
```

### Tips
- Keep it concise (1-2 paragraphs)
- Focus on distinctive visual features
- Include typical clothing/style
- Describe expressions that match personality
- Avoid copyrighted character descriptions

---

## 🔧 Troubleshooting

### Bot Doesn't Respond

1. **Check Discord token**: Ensure `DISCORD_TOKEN` in `.env.mybot` is correct
2. **Check bot permissions**: Bot needs "Message Content Intent" enabled in Discord Developer Portal
3. **Check logs**: `./bot.sh logs mybot` or terminal output

### "Character not found" Error

1. Verify directory name matches `DISCORD_BOT_NAME` in `.env.mybot`
2. Ensure `character.md` exists in `characters/mybot/`

### Database Connection Errors

1. Ensure infrastructure is running: `./bot.sh ps`
2. Check database URLs in `.env.mybot` match your setup
3. For Docker: use `localhost` for local dev, service names for containerized bots

### Goals Not Working

1. Verify `goals.yaml` syntax (run through YAML validator)
2. Check logs for goal loading errors
3. Ensure at least one goal exists

---

## 📚 File Reference

| File | Required | Purpose | Stored In |
|------|----------|---------|-----------|
| `character.md` | **Yes** | System prompt / personality | LLM context |
| `goals.yaml` | **Yes** | Conversation objectives | Memory |
| `.env.{name}` | **Yes** | Environment configuration | Runtime |
| `core.yaml` | Recommended | Purpose, drives, constitution | Runtime |
| `background.yaml` | Recommended | Knowledge Graph facts | Neo4j |
| `evolution.yaml` | Recommended | Trust-based behavior evolution | PostgreSQL + Runtime |
| `ux.yaml` | Optional | Thinking indicators, cold responses, error messages | Runtime |
| `lurk_triggers.yaml` | Optional | Channel lurking keywords/topics | Runtime |
| `visual.md` | Optional | Visual description for image generation | Runtime |

### Templates Location

All templates are in the `characters/` root:
```bash
characters/
├── character.md.template       # Copy → characters/{name}/character.md
├── goals.yaml.template         # Copy → characters/{name}/goals.yaml
├── core.yaml.template          # Copy → characters/{name}/core.yaml
├── background.yaml.template    # Copy → characters/{name}/background.yaml
├── evolution.yaml.template     # Copy → characters/{name}/evolution.yaml
├── ux.yaml.template            # Copy → characters/{name}/ux.yaml
└── lurk_triggers.yaml.template # Copy → characters/{name}/lurk_triggers.yaml
# Note: visual.md has no template - create manually
```

---

## 💡 Tips for Great Characters

1. **Be Specific**: Vague personalities lead to generic responses
2. **Include Examples**: Show the LLM how to speak, not just what to say
3. **Set Response Length**: Explicitly guide default response length
4. **Avoid Action Descriptions**: Train the character to converse, not narrate
5. **Test Iteratively**: Chat with your bot and refine based on responses
6. **Use Background Facts**: Offload detailed knowledge to Neo4j
7. **Start Simple**: Begin with character.md and goals.yaml, add evolution later

---

## 🔗 Related Documentation

- [Multi-Modal Perception](ref/REF-010-MULTI_MODAL.md) - Philosophy of how characters process multi-modal input
- [Multi-Bot Deployment Guide](run/RUN-001-MULTI_BOT_DEPLOYMENT.md) - Managing multiple bots
- [Cognitive Engine Architecture](ref/REF-001-COGNITIVE_ENGINE.md) - How the AI processes and responds
- [Memory System](ref/REF-003-MEMORY_SYSTEM.md) - How memories are stored and retrieved
- [Knowledge Graph](guide/GUIDE-002-KNOWLEDGE_GRAPH.md) - Using Neo4j for character facts
- [Trust Evolution System](ref/REF-007-TRUST_EVOLUTION.md) - Deep dive into relationship progression
- [Emergent Universe](spec/SPEC-F01-EMERGENT_UNIVERSE.md) - Future: spatial/social awareness for characters

---

## 📝 Character Checklist

Use this checklist when creating a new character:

**Required Files:**
- [ ] Created `characters/{name}/` directory
- [ ] Created `character.md` with personality and identity
- [ ] Created `goals.yaml` with conversation objectives
- [ ] Created `.env.{name}` with Discord token and config
- [ ] Set unique `API_PORT` in environment

**Recommended Files (for rich characters):**
- [ ] Added `core.yaml` with purpose, drives, and constitution
- [ ] Added `background.yaml` with facts for Neo4j
- [ ] Added `evolution.yaml` for trust-based behavior stages
- [ ] Added `ux.yaml` for thinking indicators and cold responses

**Optional Files (for advanced features):**
- [ ] Added `lurk_triggers.yaml` for channel listening
- [ ] Added `visual.md` for image generation

**Infrastructure:**
- [ ] Created Discord bot application
- [ ] Enabled "Message Content Intent" in Discord Developer Portal
- [ ] Added service to `docker-compose.yml`
- [ ] Verified port doesn't conflict with other bots

**Testing:**
- [ ] Started bot with `./bot.sh up {name}`
- [ ] Tested basic greeting ("hello")
- [ ] Verified personality matches `character.md`
- [ ] Ran regression tests: `python tests_v2/run_regression.py --bot {name} --smoke`
