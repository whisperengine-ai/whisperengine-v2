# WhisperEngine v2

> *"From countless conversations, a universe is born."*

**An Emergence Research Platform for Persistent AI Agents**

WhisperEngine v2 is a **graph-first, agentic AI system** for studying how complex behaviors emerge from simple rules. Built on the principle of **"Observe First, Constrain Later,"** it creates AI characters that develop persistent memory, evolving relationships, and autonomous agency over time.

**Core Innovation:**
- **Persistent Behavior** — Characters remember across conversations, not just within sessions
- **Graph-First Architecture** — Neo4j for relationships, LangGraph Supergraph for orchestration, knowledge as a traversable graph
- **Agentic Autonomy** — Characters post, react, and initiate conversations without prompting
- **Emergence Research** — We study what happens when constraints are minimal and behavior is observed

Built on the **Five Pillars** polyglot architecture (PostgreSQL, Qdrant, Neo4j, InfluxDB, Redis) with **LangGraph Supergraph orchestration** (E17), WhisperEngine combines vector memory, graph knowledge, and autonomous agent behavior to create characters that feel genuinely persistent.

**Version:** 2.6 | **Python:** 3.12+ | **Status:** Production Ready | **Architecture:** E17 Supergraph + E18 Agentic Queue

## 🧪 Emergence Philosophy

WhisperEngine is built on the principle of **"Observe First, Constrain Later."**

We treat the system as an **emergence research platform**, not just software. Characters develop complex behaviors from simple rules, and we study what emerges before deciding if it needs correction.

**Core Tenets:**
*   **Vocabulary over Schema** — Use prompt language to define behavior rather than rigid database taxonomies
*   **Open Recursion** — Characters read their own logs and memories, creating feedback loops of self-awareness
*   **Absence as Data** — What the character *fails* to remember is just as important as what it retrieves
*   **Minimal Viable Guardrails** — Add constraints only when observation proves them necessary
*   **Characters as Graph Citizens** — Agents are nodes with edges to knowledge, users, and goals; agency is traversal

**The Bet:** If emergence works, constraint wasn't needed. If it fails, specs are already written as "break glass" protocols.

**Read more:** [Emergence Philosophy](docs/emergence_philosophy/README.md) | [Graph Systems Design](docs/architecture/GRAPH_SYSTEMS_DESIGN.md)

## 🏗️ Graph-First Architecture

WhisperEngine is fundamentally a **graph-centric system**. Graphs pervade every layer:

**The Three Pillars of Graph Architecture:**

| Pillar | What It Represents | Technology |
|--------|-------------------|------------|
| **Data Graphs** | Knowledge, Facts, Relationships | Neo4j Cypher queries |
| **Orchestration Graphs** | Agent Behavior, Reasoning Flows | LangGraph Supergraph (E17) |
| **Conceptual Graphs** | Universe Topology, Social Structure | Emergent Universe module |

Characters are **graph citizens** — they traverse edges to remember, reason, and relate. The system processes information through multiple data streams (social graph, memory, vision, audio, text, sentiment), but these are **how** the system works, not **what** makes it unique.

**Key Insight:** The magic is in the connections, not the nodes. Complex behavior emerges from traversal patterns, not from individual components.

**Deep dive:** [Graph Systems Design](docs/architecture/GRAPH_SYSTEMS_DESIGN.md) | [Multi-Modal Processing](docs/architecture/MULTI_MODAL_PERCEPTION.md)

## 📚 Documentation

Comprehensive documentation lives in `/docs/`:

| I want to... | Read this |
|--------------|-----------|
| **Understand emergence research** | **[Emergence Philosophy](docs/emergence_philosophy/README.md)** |
| **Learn the graph architecture** | **[Graph Systems Design](docs/architecture/GRAPH_SYSTEMS_DESIGN.md)** |
| Understand the vision | [Design Philosophy](docs/architecture/WHISPERENGINE_2_DESIGN.md) |
| See what's built vs planned | [Implementation Roadmap](docs/IMPLEMENTATION_ROADMAP_OVERVIEW.md) |
| Learn about LangGraph agents | [Agent Graph System](docs/architecture/AGENT_GRAPH_SYSTEM.md) |
| Create a new character | [Character Creation Guide](docs/CREATING_NEW_CHARACTERS.md) |
| Deploy multiple bots | [Multi-Bot Deployment](docs/MULTI_BOT_DEPLOYMENT.md) |
| Understand memory architecture | [Memory System v2](docs/architecture/MEMORY_SYSTEM_V2.md) |
| Learn about the cognitive engine | [Cognitive Engine](docs/architecture/COGNITIVE_ENGINE.md) |
| Read emergence research journal | [Research Journal](docs/research/) |

### Architecture Deep Dives

| Document | Description |
|----------|-------------|
| [Graph Systems Design](docs/architecture/GRAPH_SYSTEMS_DESIGN.md) | **NEW** Unified view of all graph usage (Data, Orchestration, Conceptual) |
| [Agent Graph System](docs/architecture/AGENT_GRAPH_SYSTEM.md) | LangGraph Supergraph (E17), subgraphs, agent taxonomy |
| [Cognitive Architecture](docs/architecture/COGNITIVE_ENGINE.md) | Dual-process architecture, Fast Path vs Reflective Path |
| [Memory System v2](docs/architecture/MEMORY_SYSTEM_V2.md) | Vector + graph hybrid memory, consolidation |
| [Data Models](docs/architecture/DATA_MODELS.md) | Five Pillars schema definitions |
| [Message Flow](docs/architecture/MESSAGE_FLOW.md) | Complete request lifecycle (Supergraph orchestration) |
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

### Recently Completed

| Document | Status | Description |
|----------|--------|-------------|
| [Supergraph Architecture](docs/roadmaps/SUPERGRAPH_ARCHITECTURE.md) | ✅ E17 | LangGraph master orchestrator |
| [Agentic Queue System](docs/roadmaps/AGENTIC_QUEUE_SYSTEM.md) | ✅ E18 | Redis arq worker architecture |
| [Autonomous Server Activity](docs/roadmaps/AUTONOMOUS_SERVER_ACTIVITY.md) | ✅ E15 | Reactions + Posting agents |
| [Bot-to-Bot Conversations](docs/roadmaps/CHARACTER_TO_CHARACTER.md) | ✅ E6 | ConversationAgent for multi-bot dialogue |

### Future Roadmaps

| Document | Status | Description |
|----------|--------|-------------|
| [Schedule Jitter](docs/IMPLEMENTATION_ROADMAP_OVERVIEW.md) | 📋 E23 | Organic timing for scheduled tasks |
| [Absence Tracking](docs/IMPLEMENTATION_ROADMAP_OVERVIEW.md) | 📋 E22 | Meta-memory for missing information |
| [Graph Walker Agent](docs/roadmaps/GRAPH_WALKER_AGENT.md) | 📋 E19 | Agentic knowledge graph exploration |
| [Bot Introspection Tools](docs/roadmaps/BOT_INTROSPECTION_TOOLS.md) | 📋 E20 | Collaborative debugging tools |
| [Multi-Agent Environment](docs/roadmaps/EMERGENT_UNIVERSE.md) | 🟡 Design | Distributed context, cross-agent awareness |
| [Response Pattern Learning](docs/roadmaps/RESPONSE_PATTERN_LEARNING.md) | 🟡 Design | RLHF-style adaptation |

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

The Five Pillars (PostgreSQL, Qdrant, Neo4j, InfluxDB, Redis):

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

**Available characters:** `elena` (dev primary), `nottaylor` (production), `dotty`, `aria`, `dream`, `jake`, `sophia`, `marcus`, `ryan`, `gabriel`, `aetheris`

| Bot | Port | Role | Main Model |
|-----|------|------|------------|
| elena | 8000 | Dev Primary | Claude Sonnet 4.5 |
| nottaylor | 8008 | Production | GPT-4o |
| dotty | 8002 | Personal | Claude 3.7 Sonnet |
| gabriel | 8009 | Personal | Mistral Medium 3.1 |
| aetheris | 8011 | Personal | Claude Sonnet 4 |
| aria, dream, jake, marcus, ryan, sophia | 8003-8007 | Test | Various (A/B testing) |

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
├── memory/          # Qdrant vectors, summarization, dreams, diary
├── knowledge/       # Neo4j graph, fact extraction
├── evolution/       # Trust scores, feedback analysis
├── discord/         # Bot, commands, scheduler, proactive messaging
├── voice/           # TTS (ElevenLabs), audio processing
├── api/             # FastAPI endpoints
├── core/            # Database, character loading, settings
├── workers/         # Background task processing
├── universe/        # Universe simulation and state
├── broadcast/       # Broadcasting capabilities
└── utils/           # Helpers, validation, time utilities
```

## 🏗️ Architecture

### The Five Pillars

WhisperEngine uses **polyglot persistence** — matching each data access pattern to the database that excels at it. This is the "Five Pillars" data layer:

| Database | Purpose | Why This One | Graph Role |
|----------|---------|--------------|------------|
| **PostgreSQL** | Chat history, users, [trust scores](docs/architecture/TRUST_EVOLUTION_SYSTEM.md) | ACID compliance, relational integrity | Relational graph (foreign keys as edges) |
| **Qdrant** | [Vector memory](docs/architecture/MEMORY_SYSTEM_V2.md) search | Fast ANN search, semantic similarity | Implicit similarity graph |
| **Neo4j** | [Knowledge graph](docs/features/KNOWLEDGE_GRAPH_MEMORY.md) (facts, relationships) | Native graph traversal, Cypher queries | Explicit semantic graph |
| **InfluxDB** | Metrics, analytics, feedback | Time-series data, Flux queries | Temporal graph |
| **Redis** | Cache layer, task queue (arq) | Fast access, background jobs | Event/queue graph (stigmergic nervous system) |

### LangGraph Supergraph Orchestration (E17)

The **Supergraph** is the master agent coordinator, routing requests through specialized subgraphs:

```
USER MESSAGE
     ↓
SUPERGRAPH (Master Router)
     ├─→ Fast Mode (Tier 1: Simple greetings, < 2s)
     ├─→ Character Agency (Tier 2: Single tool lookup, 2-4s)
     └─→ Reflective Mode (Tier 3: Multi-step ReAct loop, 5-30s)
```

**Subgraph Types:**
- **Reflective Agent** — Cyclic Planning (ReAct with tools)
- **Character Agent** — Branched (single-tool augmented response)
- **Diary Agent** — Cyclic (Generator-Critic loop)
- **Dream Agent** — Cyclic (Generator-Critic loop)
- **Insight Agent** — Cyclic (pattern detection)
- **Posting Agent** — Linear (autonomous content generation)

**Read more:** [Agent Graph System](docs/architecture/AGENT_GRAPH_SYSTEM.md) | [Message Flow](docs/architecture/MESSAGE_FLOW.md)

### Agentic Autonomy

Characters are **autonomous agents**, not reactive responders:
- **Posting** — Share thoughts/observations to public channels without prompting
- **Reactions** — Add emoji reactions to messages that resonate
- **Bot-to-Bot Conversations** — Characters talk to each other naturally (E15 Phase 3)
- **Proactive Messaging** — Initiate DMs after long absences (trust ≥ 20)
- **Background Cognition** — Diary/dream generation during downtime (E18 Agentic Queue)

**Architectural Pattern:** Each bot runs in its own container, sharing infrastructure. A single `insight-worker` handles background cognition for all bots via Redis arq queues.

### Key Design Patterns

- **Manager Pattern:** Every subsystem has an `XManager` with `initialize()` method
- **Async/Await:** All I/O is async with type hints
- **Feature Flags:** Expensive LLM operations gated by settings
- **Parallel Retrieval:** `asyncio.gather` for multi-DB context fetching
- **Dependency Injection:** Engines accept dependencies for testability
- **Graph as Substrate:** Characters traverse edges to remember, reason, and relate

**Full architecture:** [Data Models](docs/architecture/DATA_MODELS.md) | [Graph Systems Design](docs/architecture/GRAPH_SYSTEMS_DESIGN.md) | [Cognitive Engine](docs/architecture/COGNITIVE_ENGINE.md)

## ✅ Current Features

### Core Cognitive Systems
- ✅ **LangGraph Supergraph** orchestration ([E17](docs/roadmaps/SUPERGRAPH_ARCHITECTURE.md)) — hierarchical agent execution with routing
- ✅ Dual-process cognitive engine ([Fast Mode + Reflective Mode](docs/architecture/COGNITIVE_ENGINE.md)) — System 1/System 2 reasoning
- ✅ Native function calling with parallel tool execution — multi-source context in one pass
- ✅ **Graph-first knowledge** ([Neo4j](docs/features/KNOWLEDGE_GRAPH_MEMORY.md)) — facts, entities, relationships as traversable graph
- ✅ **Vector memory** ([Qdrant](docs/architecture/MEMORY_SYSTEM_V2.md)) — semantic search with hybrid retrieval
- ✅ **Dreams & Diary** — Offline memory consolidation and narrative generation with Generator-Critic loops

### Persistent Behavior & Evolution
- ✅ Trust/evolution system ([8 stages](docs/architecture/TRUST_EVOLUTION_SYSTEM.md): Stranger → Soulmate) — relationship depth over time
- ✅ Background [fact](docs/features/KNOWLEDGE_GRAPH_MEMORY.md) and [preference](docs/features/USER_PREFERENCES.md) extraction — learning from every interaction
- ✅ **Agentic Queue System** ([E18](docs/roadmaps/AGENTIC_QUEUE_SYSTEM.md)) — Redis arq workers for background cognition
- ✅ Goal tracking and strategy planning — characters pursue objectives across sessions

### Autonomous Engagement
- ✅ **Autonomous Posting** ([E15](docs/roadmaps/AUTONOMOUS_SERVER_ACTIVITY.md)) — characters share thoughts proactively
- ✅ **Reaction System** — emoji reactions based on sentiment and context
- ✅ **Proactive Messaging** — characters initiate DMs after long absences (trust-gated)
- ✅ Bot-to-bot awareness — characters know about each other ([E6](docs/roadmaps/CHARACTER_TO_CHARACTER.md))

### Discord Integration
- ✅ DM support + server mentions — full channel awareness
- ✅ Image attachment processing ([Vision modality](docs/architecture/VISION_PIPELINE.md)) — multimodal LLM understanding
- ✅ Reaction-based feedback ([Emotion modality](docs/features/TRUST_AND_EVOLUTION.md)) — users signal sentiment
- ✅ Voice channel connection with ElevenLabs TTS — audio responses (optional)

### Multi-Character Support
- ✅ 11+ unique characters with distinct personalities ([create your own](docs/CREATING_NEW_CHARACTERS.md))
- ✅ Per-character memory isolation ([privacy model](docs/PRIVACY_AND_DATA_SEGMENTATION.md)) — no data leakage
- ✅ Character-specific [goals](docs/features/GOALS.md) and evolution — tailored progression

## 🗺️ Roadmap

See the full [Implementation Roadmap](docs/IMPLEMENTATION_ROADMAP_OVERVIEW.md) for detailed planning.

**Coming Soon:**
- 🔜 Bot-to-bot conversations ([E15.3](docs/roadmaps/CHARACTER_TO_CHARACTER.md))
- 🔜 Full activity scaling (E15.4)
- 🔜 [Channel lurking](docs/roadmaps/CHANNEL_LURKING.md) (passive engagement)
- 🔜 Reasoning traces (system learns from itself)
- 🔜 [Emergent Universe](docs/roadmaps/EMERGENT_UNIVERSE.md) (cross-bot awareness)
- 🔜 Web dashboard (admin UI)

## 📖 Additional Resources

- [Quick Reference](QUICK_REFERENCE.md) — Common commands, troubleshooting
- [Privacy & Data Segmentation](docs/PRIVACY_AND_DATA_SEGMENTATION.md) — How user data is isolated
- [Documentation Index](docs/README.md) — Full documentation navigation

## 📄 License

See [LICENSE](LICENSE) file for details.

---

*Built with ❤️ for AI agents that feel authentic.*
