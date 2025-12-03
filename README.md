# WhisperEngine v2

> *"From countless conversations, a universe is born."*

WhisperEngine is a **multi-character Discord AI platform** with persistent memory, evolving relationships, and autonomous behavior. We use it to study how complex behaviors emerge in agentic systems when you give them memory, agency, and minimal constraints.

**Version:** 2.6 | **Python:** 3.12+ | **Status:** Production

---

## The Questions We're Exploring

**On Memory & Retrieval:**
- What happens when characters read their own memories, dreams, and diaries? Does coherent behavior emerge from self-reference, or drift into noise?
- If a character "forgets" something (fails to retrieve it), does that absence shape behavior?
- Can personality emerge from retrieval patterns alone, without explicit personality parameters?

**On Relationships:**
- What happens when trust is earned slowly over months? Does behavior genuinely change?
- Can characters learn communication preferences without being explicitly told?

**On Autonomy:**
- When given freedom to post, react, and initiate conversations — what do characters actually do?
- Do characters develop consistent interests, or just mirror what gets engagement?
- When multiple characters interact with each other, do they develop shared context? Inside jokes?

**On Emergence:**
- How much can we *not* build and still get coherent behavior?
- When feedback loops form (dreams → diaries → memories → dreams), do they stabilize or spiral?

**The Meta-Question:**
> Build the substrate, get out of the way — what happens?

---

## The Bet

We're betting on **minimal constraint**:

- **If emergence works:** Complex behavior appears without us hard-coding it.
- **If emergence fails:** We learn exactly where constraints are necessary. Specs are already written as "break glass" protocols.

Either way, we learn something.

---

## Philosophy: Observe First, Constrain Later

Unexpected behaviors are **data, not bugs**. We document what happens before deciding if it needs fixing.

| Principle | What It Means |
|-----------|---------------|
| **Vocabulary over Schema** | Express behavior in prompts, not database fields. A "subconscious" memory isn't labeled — it's a memory that keeps failing to surface. |
| **Open Recursion** | Characters read their own outputs. Dreams reference diaries. Diaries reference memories. The loops are intentional. |
| **Absence as Data** | What the character *fails* to remember matters. We track retrieval gaps, not just retrievals. |

**Read more:** [Emergence Philosophy](docs/emergence_philosophy/README.md) | [Research Methodology](docs/research/METHODOLOGY.md)

---

## The System

**Persistent Memory** — Vector search (Qdrant) for semantic recall. Knowledge graphs (Neo4j) for facts and relationships. Memories consolidate into dreams and diaries during downtime.

**Evolving Relationships** — Trust builds over months across multiple stages. Character openness and initiative change with trust level.

**Autonomous Agency** — Characters post unprompted. React with emoji. Initiate conversations after long absences. Talk to each other.

**Multi-Character** — 11+ distinct personalities. Different LLM backends (Claude, GPT-4, Gemini, Mistral, DeepSeek, Llama). Isolated memory per character.

**Graph-First** — Knowledge as traversable graph. Orchestration as LangGraph state machines.

---

## The Five Pillars

| Database | Purpose | Why This One |
|----------|---------|--------------|
| **PostgreSQL** | Chat history, users, trust | ACID compliance, relational integrity |
| **Qdrant** | Semantic memory search | Fast vector similarity |
| **Neo4j** | Knowledge graph (facts, entities) | Native graph traversal |
| **InfluxDB** | Metrics & feedback loops | Time-series for drift detection |
| **Redis** | Cache + background queue | Fast jobs, async cognition |

---

## 📚 Documentation

| Topic | Link |
|-------|------|
| Research philosophy | [Emergence Philosophy](docs/emergence_philosophy/README.md) |
| Research journal | [Research Journal](docs/research/) |
| Full roadmap | [Implementation Roadmap](docs/IMPLEMENTATION_ROADMAP_OVERVIEW.md) |
| Architecture | [Graph Systems](docs/architecture/GRAPH_SYSTEMS_DESIGN.md), [Cognitive Engine](docs/architecture/COGNITIVE_ENGINE.md), [Memory](docs/architecture/MEMORY_SYSTEM_V2.md) |
| Characters | [Creating Characters](docs/CREATING_NEW_CHARACTERS.md), [Multi-Bot Deploy](docs/MULTI_BOT_DEPLOYMENT.md) |

Full docs index: [docs/README.md](docs/README.md)

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
├── agents/      # Cognitive engine, LLM interactions, reflective mode
├── memory/      # Qdrant vectors, dreams, diary, summarization
├── knowledge/   # Neo4j graph, fact extraction
├── evolution/   # Trust scores, feedback analysis
├── discord/     # Bot, scheduler, proactive messaging
├── voice/       # TTS (ElevenLabs)
├── api/         # FastAPI endpoints
├── core/        # Database, character loading, settings
└── workers/     # Background task processing (arq)
```

---

## 📄 License

See [LICENSE](LICENSE) file for details.

