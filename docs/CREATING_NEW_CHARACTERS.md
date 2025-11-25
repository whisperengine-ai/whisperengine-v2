# Creating New Character Bots

A step-by-step guide to creating and deploying a new character in WhisperEngine v2.

---

## 📋 Prerequisites

Before creating a new character, ensure you have:

1. **Discord Bot Token** - Create a new bot application at [Discord Developer Portal](https://discord.com/developers/applications)
2. **Infrastructure Running** - PostgreSQL, Qdrant, Neo4j, and InfluxDB must be up
3. **LLM API Access** - OpenAI, OpenRouter, or local LLM endpoint configured

---

## 🚀 Quick Start (5 Minutes)

For the impatient, here's the minimal setup:

```bash
# 1. Create character directory
mkdir -p characters/mybot

# 2. Copy templates
cp characters/character.md.template characters/mybot/character.md
cp characters/goals.yaml.template characters/mybot/goals.yaml

# 3. Create environment file
cp .env.example .env.mybot

# 4. Edit the files (see sections below)
# - characters/mybot/character.md (personality)
# - characters/mybot/goals.yaml (objectives)
# - .env.mybot (tokens and config)

# 5. Run locally
python run_v2.py mybot

# OR deploy with Docker
# (Add to docker-compose.yml first - see Step 6)
./bot.sh up mybot
```

---

## 📁 Step 1: Create Character Directory

Each character needs its own directory under `characters/`:

```bash
mkdir -p characters/mybot
```

Your character folder will eventually contain:
```
characters/mybot/
├── character.md       # Required: Main personality (system prompt)
├── goals.yaml         # Required: Conversation objectives
├── background.yaml    # Optional: Knowledge Graph facts
└── evolution.yaml     # Optional: Trust-based personality evolution
```

---

## 🎭 Step 2: Define the Personality (`character.md`)

Copy the template and customize:

```bash
cp characters/character.md.template characters/mybot/character.md
```

### Key Sections to Edit

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

**Expertise Section**:
```markdown
## Expertise
Game design, Unity/Unreal Engine, pixel art, narrative design, 
indie development lifecycle, Steam publishing, game jams.
```

**How You Respond**:
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
- `{user_name}` - Discord display name
- `{current_datetime}` - Current date/time
- `{recent_memories}` - Retrieved memories from vector DB
- `{knowledge_context}` - Facts from knowledge graph

Always include at the end:
```markdown
## Context for This Conversation

Recent Memories:
{recent_memories}

Knowledge Context:
{knowledge_context}
```

---

## 🎯 Step 3: Set Conversation Goals (`goals.yaml`)

Copy the template and customize:

```bash
cp characters/goals.yaml.template characters/mybot/goals.yaml
```

### Example Goals

```yaml
goals:
  # Universal goal - keep this
  - slug: learn_name
    description: Learn the user's name
    success_criteria: User explicitly states their name
    priority: 10
    category: personal_knowledge

  # Domain-specific goal
  - slug: discover_game_preferences
    description: Learn what games the user enjoys
    success_criteria: User mentions specific games or genres they like
    priority: 8
    category: personal_knowledge

  # Expertise-sharing goal
  - slug: share_dev_tips
    description: Share game development knowledge
    success_criteria: User shows interest in game dev concepts
    priority: 7
    category: expertise

  # Relationship goal
  - slug: find_collab_potential
    description: Explore if user is interested in game projects
    success_criteria: User expresses interest in making games
    priority: 6
    category: discovery
```

### Goal Fields

| Field | Required | Description |
|-------|----------|-------------|
| `slug` | Yes | Unique identifier (snake_case) |
| `description` | Yes | What the character wants to accomplish |
| `success_criteria` | Yes | How to know the goal is complete |
| `priority` | Yes | 1-10, higher = more important |
| `category` | No | For organization (`personal_knowledge`, `expertise`, `relationship`, `discovery`) |

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
ENABLE_REFLECTIVE_MODE=false         # Deep thinking (costs more, ~$0.02-0.03/query)
ENABLE_RUNTIME_FACT_EXTRACTION=true  # Learn facts from chat
ENABLE_PREFERENCE_EXTRACTION=true    # Learn user preferences
LLM_SUPPORTS_VISION=true             # Image analysis (requires GPT-4V/Claude 3)
ENABLE_PROACTIVE_MESSAGING=false     # Bot initiates contact
ENABLE_PROMPT_LOGGING=true           # Log prompts for debugging

# DM restrictions (comma-separated Discord user IDs)
# DM_ALLOWED_USER_IDS=123456789,987654321

# Voice (ElevenLabs) - optional
# ELEVENLABS_API_KEY=your-elevenlabs-api-key
# ELEVENLABS_VOICE_ID=your-voice-id
```

---

## 🧠 Step 5: Add Background Facts (Optional)

For richer character knowledge, create `background.yaml`:

```bash
cp characters/background.yaml.template characters/mybot/background.yaml
```

### Example Background

```yaml
facts:
  - predicate: HAS_FULL_NAME
    object: Luna Chen
  - predicate: HAS_AGE
    object: 28
  - predicate: LIVES_IN
    object: Seattle, Washington
  - predicate: OCCUPATION
    object: Indie Game Developer
  
  # Interests (important for Common Ground detection!)
  - predicate: HAS_INTEREST
    object: Pixel art and retro aesthetics
  - predicate: HAS_INTEREST
    object: Roguelike game design
  - predicate: HAS_INTEREST
    object: Game jam competitions
  - predicate: HAS_INTEREST
    object: Lo-fi music while coding
  
  # Values & personality depth
  - predicate: HAS_VALUE
    object: Creative independence over corporate jobs
  - predicate: HAS_FEAR
    object: Releasing a game that nobody plays
  - predicate: HAS_DREAM
    object: Creating a game that inspires others to make games
```

These facts are stored in Neo4j and retrieved when relevant to conversation.

---

## 🔄 Step 6: Add to Docker Compose (For Production)

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

## ▶️ Step 7: Run Your Bot

### Option A: Local Development (Recommended for Testing)

```bash
# Start infrastructure
./bot.sh infra up

# Run bot directly (hot-reload friendly)
source .venv/bin/activate
python run_v2.py mybot
```

### Option B: Docker Container

```bash
# Start infrastructure + your bot
./bot.sh up mybot

# Or start all bots
./bot.sh up all

# View logs
./bot.sh logs mybot
```

---

## ✅ Step 8: Verify Everything Works

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

## 🎨 Step 9: Add Evolution System (Optional)

For trust-based personality evolution, create `evolution.yaml`:

```bash
cp characters/evolution.yaml.template characters/mybot/evolution.yaml
```

This enables:
- **Trust Levels**: Behavior changes as relationship deepens
- **Unlockable Traits**: New personality aspects at higher trust
- **Milestones**: Celebration messages when trust thresholds are crossed

See `characters/elena/evolution.yaml` for a complete example.

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

| File | Required | Purpose |
|------|----------|---------|
| `character.md` | **Yes** | System prompt / personality definition |
| `goals.yaml` | **Yes** | Conversation objectives |
| `.env.{name}` | **Yes** | Environment configuration |
| `background.yaml` | No | Knowledge Graph facts for deep memory |
| `evolution.yaml` | No | Trust-based personality evolution |

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

- [Multi-Bot Deployment Guide](MULTI_BOT_DEPLOYMENT.md) - Managing multiple bots
- [Cognitive Engine Architecture](architecture/COGNITIVE_ENGINE.md) - How the AI works
- [Memory System](architecture/MEMORY_SYSTEM_V2.md) - How memories are stored
- [Knowledge Graph](features/KNOWLEDGE_GRAPH_MEMORY.md) - Using Neo4j for character facts

---

## 📝 Character Checklist

Use this checklist when creating a new character:

- [ ] Created `characters/{name}/` directory
- [ ] Created `character.md` with personality
- [ ] Created `goals.yaml` with objectives
- [ ] Created `.env.{name}` with tokens
- [ ] Set unique `API_PORT` in environment
- [ ] Created Discord bot application
- [ ] Enabled "Message Content Intent" in Discord
- [ ] Added to `docker-compose.yml` (if using Docker)
- [ ] Tested bot responds correctly
- [ ] (Optional) Added `background.yaml` for rich facts
- [ ] (Optional) Added `evolution.yaml` for trust evolution
