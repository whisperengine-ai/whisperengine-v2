# WhisperEngine v2

> *"From countless conversations, a universe is born."*

**A Multi-Modal Cognitive AI Platform for Discord**

WhisperEngine v2 creates AI agents with persistent memory and adaptive behavior. Beyond simple chatbots, agents have **Long-Term Memory**, **Advanced Reasoning**, **Knowledge Graphs**, and **Autonomous Engagement** — processing inputs through six distinct data streams to build a comprehensive context.

Built on a "Four Pillars" polyglot architecture (PostgreSQL, Qdrant, Neo4j, InfluxDB), it combines the speed of vector search with the precision of knowledge graphs.

**Version:** 2.0.2 | **Python:** 3.13+ | **Status:** Production Ready

## ✨ What Makes WhisperEngine Different

| Traditional Chatbots | WhisperEngine v2 |
|---------------------|------------------|
| Forgets everything between sessions | **Persistent memory** across conversations |
| Same personality for everyone | **Evolving relationships** (Stranger → Trusted Confidant) |
| Only responds when asked | **Autonomous engagement** when appropriate |
| Text-only understanding | **Multi-modal processing** (images, voice, context) |
| Single reasoning mode | **Dual-process architecture** (fast + reflective) |
| Isolated instances | **Multi-agent environment** with shared state |

## 🧠 The Six Modalities

The platform processes information through multiple input vectors:

| Modality | Technical Domain | Implementation |
|----------|--------------|----------------|
| 🌌 **Social Graph** | Network Topology | Neo4j graph (servers, users, relationships) |
| 👁️ **Vision** | Image Processing | Multimodal LLM (GPT-4V, Claude) |
| 👂 **Audio** | Speech Recognition | Whisper transcription + ElevenLabs TTS |
| 💬 **Text** | NLP | LLM processing + context injection |
| 🧠 **Memory** | Vector + Graph Retrieval | Qdrant vectors + Neo4j facts |
| ❤️ **Sentiment** | Internal State Analysis | Trust scores, sentiment, relationship depth |

**Deep dive:** [Multi-Modal Processing](docs/architecture/MULTI_MODAL_PERCEPTION.md)

## 📚 Documentation

Comprehensive documentation lives in `/docs/`:

| I want to... | Read this |
|--------------|-----------|
| Understand the vision | [Design Philosophy](docs/architecture/WHISPERENGINE_2_DESIGN.md) |
| See what's built vs planned | [Implementation Roadmap](docs/IMPLEMENTATION_ROADMAP_OVERVIEW.md) |
| Create a new character | [Character Creation Guide](docs/CREATING_NEW_CHARACTERS.md) |
| Deploy multiple bots | [Multi-Bot Deployment](docs/MULTI_BOT_DEPLOYMENT.md) |
| Understand memory architecture | [Memory System v2](docs/architecture/MEMORY_SYSTEM_V2.md) |
| Learn about the cognitive engine | [Cognitive Engine](docs/architecture/COGNITIVE_ENGINE.md) |

### Architecture Deep Dives

| Document | Description |
|----------|-------------|
| [Cognitive Architecture](docs/architecture/COGNITIVE_ENGINE.md) | Dual-process architecture, Fast Path vs Reflective Path |
| [Memory System v2](docs/architecture/MEMORY_SYSTEM_V2.md) | Vector + graph hybrid memory, consolidation |
| [Data Models](docs/architecture/DATA_MODELS.md) | Four Pillars schema definitions |
| [Message Flow](docs/architecture/MESSAGE_FLOW.md) | Complete request lifecycle |
| [Trust & Evolution](docs/architecture/TRUST_EVOLUTION_SYSTEM.md) | Relationship progression (8 stages) |
| [Discord Integration](docs/architecture/DISCORD_INTEGRATION.md) | Autonomous agents, voice architecture |
| [Vision Pipeline](docs/architecture/VISION_PIPELINE.md) | Image processing and understanding |
| [Summarization System](docs/architecture/SUMMARIZATION_SYSTEM.md) | Memory consolidation |

### Feature Documentation

| Document | Description |
|----------|-------------|
| [Knowledge Graph Memory](docs/features/KNOWLEDGE_GRAPH_MEMORY.md) | Neo4j fact storage |
| [User Preferences](docs/features/USER_PREFERENCES.md) | Learning user communication styles |
| [Common Ground](docs/features/COMMON_GROUND.md) | Shared interest detection |
| [Stats Footer](docs/features/STATS_FOOTER.md) | Debug information in responses |
| [Reflective Mode Controls](docs/features/REFLECTIVE_MODE_CONTROLS.md) | User override commands |

### Future Roadmaps

| Document | Status | Description |
|----------|--------|-------------|
| [Multi-Agent Environment](docs/roadmaps/EMERGENT_UNIVERSE.md) | 🟡 Design | Distributed context, cross-agent awareness |
| [Channel Lurking](docs/roadmaps/CHANNEL_LURKING.md) | 🟡 Design | Passive engagement system |
| [Response Pattern Learning](docs/roadmaps/RESPONSE_PATTERN_LEARNING.md) | 🟡 Design | RLHF-style adaptation |
| [Embedding Upgrade](docs/roadmaps/EMBEDDING_UPGRADE_768D.md) | 📋 Ready | 384D → 768D embeddings |
| [Reflective Mode Phase 2](docs/roadmaps/REFLECTIVE_MODE_PHASE_2.md) | 📋 Ready | Adaptive steps, self-correction |

## 🚀 Quick Start

### Prerequisites
- Python 3.13+
- Docker and Docker Compose
- Discord bot token
- LLM API key (OpenAI, OpenRouter, or local)

### Installation

```bash
# Clone the repository
git clone https://github.com/whisperengine-ai/whisperengine-v2.git
cd whisperengine-v2

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env.elena
# Edit .env.elena with your configuration
```

### Start Infrastructure

The Four Pillars (PostgreSQL, Qdrant, Neo4j, InfluxDB):

```bash
# Start everything (Docker is primary, even for dev)
./bot.sh up elena
```

### Run the Bot

**Docker (Primary - Recommended):**
```bash
./bot.sh up elena      # Single bot
./bot.sh up all        # All bots
./bot.sh logs elena -f # View logs
./bot.sh restart elena # After code changes
```

**Local Python (Debugging only):**
```bash
./bot.sh infra up          # Start infrastructure only
source .venv/bin/activate
python run_v2.py elena     # For debugger breakpoints
```

### Verify It's Working

```bash
# Check container status
./bot.sh ps

# View logs
./bot.sh logs elena -f

# Test the API
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","message":"Hello!","metadata":{}}'
```

## 🎭 Characters

WhisperEngine supports multiple unique AI personalities, each with their own character file, goals, and evolution parameters.

**Available characters:** `elena`, `ryan`, `dotty`, `aria`, `dream`, `jake`, `sophia`, `marcus`, `nottaylor`

### Character Configuration

Each character has:
- `characters/{name}/character.md` — System prompt and personality
- `characters/{name}/goals.yaml` — Learning objectives and character-specific goals
- `characters/{name}/evolution.yaml` — Trust thresholds and relationship parameters
- `characters/{name}/background.yaml` — Background knowledge and expertise

### Creating a New Character

```bash
# 1. Create directory
mkdir characters/newcharacter

# 2. Copy templates
cp characters/character.md.template characters/newcharacter/character.md
cp characters/goals.yaml.template characters/newcharacter/goals.yaml
cp characters/evolution.yaml.template characters/newcharacter/evolution.yaml
cp characters/background.yaml.template characters/newcharacter/background.yaml

# 3. Edit files with character specifics
# 4. Create environment file
cp .env.example .env.newcharacter

# 5. Add to docker-compose.yml (see QUICK_REFERENCE.md)
```

**Full guide:** [Creating New Characters](docs/CREATING_NEW_CHARACTERS.md) | **Deploy multiple:** [Multi-Bot Deployment](docs/MULTI_BOT_DEPLOYMENT.md)

## 🛠️ Development

### Bot Management

```bash
./bot.sh help             # All available commands
./bot.sh ps               # Container status
./bot.sh logs elena -f    # Stream logs
./bot.sh restart elena    # Restart after code changes
./bot.sh down all         # Stop all containers
./bot.sh infra up         # Start databases only
```

### Database Migrations

```bash
# Generate migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Testing

```bash
# All tests
pytest tests_v2/ -v

# Specific test file
pytest tests_v2/test_memory_manager.py -v

# With coverage
pytest tests_v2/ --cov=src_v2 --cov-report=html
```

### Project Structure

```
src_v2/
├── agents/          # Cognitive engine, LLM interactions, reflective mode
├── memory/          # Qdrant vectors, summarization, embeddings
├── knowledge/       # Neo4j graph, fact extraction
├── evolution/       # Trust scores, feedback analysis
├── discord/         # Bot, commands, scheduler, proactive messaging
├── voice/           # TTS (ElevenLabs), audio processing
├── api/             # FastAPI endpoints
├── core/            # Database, character loading, settings
└── utils/           # Helpers, validation, time utilities
```

## 🏗️ Architecture

### The Four Pillars

See [Data Models](docs/architecture/DATA_MODELS.md) for detailed schema definitions.

| Database | Purpose | Why This One |
|----------|---------|--------------|
| **PostgreSQL** | Chat history, users, [trust scores](docs/architecture/TRUST_EVOLUTION_SYSTEM.md) | ACID compliance, relational queries |
| **Qdrant** | [Vector memory](docs/architecture/MEMORY_SYSTEM_V2.md) search | Fast ANN search, payload filtering |
| **Neo4j** | [Knowledge graph](docs/features/KNOWLEDGE_GRAPH_MEMORY.md) (facts, relationships) | Cypher queries, graph traversal |
| **InfluxDB** | Metrics, analytics | Time-series data, Flux queries |

### Key Design Patterns

- **Manager Pattern:** Every subsystem has an `XManager` with `initialize()` method
- **Async/Await:** All I/O is async with type hints
- **Feature Flags:** Expensive LLM operations gated by settings
- **Parallel Retrieval:** `asyncio.gather` for multi-DB context fetching
- **Dependency Injection:** Engines accept dependencies for testability

**Full architecture:** [Data Models](docs/architecture/DATA_MODELS.md) | [Message Flow](docs/architecture/MESSAGE_FLOW.md)

## ✅ Current Features

### Core Systems
- ✅ Dual-process cognitive engine ([Fast Mode + Reflective Mode](docs/architecture/COGNITIVE_ENGINE.md))
- ✅ Native function calling with parallel tool execution
- ✅ Vector memory system ([Qdrant](docs/architecture/MEMORY_SYSTEM_V2.md)) with semantic search
- ✅ Knowledge graph ([Neo4j](docs/features/KNOWLEDGE_GRAPH_MEMORY.md)) with fact extraction
- ✅ Trust/evolution system ([8 stages](docs/architecture/TRUST_EVOLUTION_SYSTEM.md): Stranger → Soulmate)
- ✅ Background [fact](docs/features/KNOWLEDGE_GRAPH_MEMORY.md) and [preference](docs/features/USER_PREFERENCES.md) extraction

### Discord Integration
- ✅ DM support + server mentions
- ✅ Image attachment processing ([Vision modality](docs/architecture/VISION_PIPELINE.md))
- ✅ Reaction-based feedback ([Emotion modality](docs/features/TRUST_AND_EVOLUTION.md))
- ✅ Voice channel connection with ElevenLabs TTS
- ✅ [Proactive messaging](docs/architecture/DISCORD_INTEGRATION.md) system

### Multi-Character Support
- ✅ 9 characters with unique personalities ([create your own](docs/CREATING_NEW_CHARACTERS.md))
- ✅ Per-character memory isolation ([privacy model](docs/PRIVACY_AND_DATA_SEGMENTATION.md))
- ✅ Character-specific [goals](docs/features/GOALS.md) and evolution

## 🗺️ Roadmap

See the full [Implementation Roadmap](docs/IMPLEMENTATION_ROADMAP_OVERVIEW.md) for detailed planning.

**Coming Soon:**
- 🔜 Redis caching layer (30-50% DB reduction)
- 🔜 Streaming LLM responses
- 🔜 Hot-reload character definitions
- 🔜 [Channel lurking](docs/roadmaps/CHANNEL_LURKING.md) (passive engagement)
- 🔜 Reasoning traces (system learns from itself)
- 🔜 Epiphanies (characters have spontaneous insights)
- 🔜 [Emergent Universe](docs/roadmaps/EMERGENT_UNIVERSE.md) (cross-bot awareness)

## 📖 Additional Resources

- [Quick Reference](QUICK_REFERENCE.md) — Common commands, troubleshooting
- [Privacy & Data Segmentation](docs/PRIVACY_AND_DATA_SEGMENTATION.md) — How user data is isolated
- [Documentation Index](docs/README.md) — Full documentation navigation

## 📄 License

See [LICENSE](LICENSE) file for details.

---

*Built with ❤️ for AI agents that feel authentic.*
