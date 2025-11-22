# WhisperEngine v2 AI Agent Instructions

**WhisperEngine v2 is a production multi-character Discord AI roleplay platform** using Vector Memory (Qdrant), Knowledge Graphs (Neo4j), and a Dual-Process cognitive architecture.

## 🏗️ Architecture Overview

### Entry Point & Runtime
- **Entry**: `run_v2.py <bot_name>` sets `DISCORD_BOT_NAME` env var and loads `src_v2.main`
- **Main**: `src_v2/main.py` initializes DB Manager → Memory System → Knowledge Graph → Discord Bot → FastAPI Server
- **v2 Only**: Work in `src_v2/`, not legacy `src/` directory

### The "Four Pillars" Data Layer
1. **PostgreSQL** (5432): Relational data, relationships, user preferences, sessions
2. **Qdrant** (6333): Vector memory with 384D embeddings for semantic retrieval
3. **Neo4j** (7687): Knowledge graph for facts, entities, relationships
4. **InfluxDB** (8086): Time-series metrics for engagement analytics

Each bot has a dedicated Qdrant collection: `whisperengine_memory_{bot_name}`

## 🚀 Deployment & Management

### Docker Compose Profiles (Profile-Based Architecture)
```bash
# Infrastructure only (postgres, qdrant, neo4j, influxdb)
./bot.sh infra
# Or: docker compose up -d

# Start specific bot (uses profile)
./bot.sh up elena
# Or: docker compose --profile elena up -d --build

# Start all bots
./bot.sh up all
# Or: docker compose --profile all up -d

# Status & logs
./bot.sh ps
./bot.sh logs elena
```

**Key Pattern**: `docker-compose.yml` uses profiles (`elena`, `ryan`, `dotty`, `aria`, `dream`, `all`) for selective bot deployment. Infrastructure services have no profile (always available).

### Local Development
```bash
source .venv/bin/activate
python run_v2.py elena  # Loads .env.elena automatically
```

## ⚙️ Feature Flags (Resource Management)

Critical cost optimization via feature flags in `src_v2/config/settings.py`:

- **`ENABLE_REFLECTIVE_MODE`** (default: false): Enables complexity classifier + ReAct reasoning loop. Cost: 1 extra LLM call per message + 3-10 calls for complex queries (~$0.02-0.03 vs $0.001-0.005)
- **`ENABLE_RUNTIME_FACT_EXTRACTION`** (default: true): Extracts facts to Knowledge Graph. Cost: 1 LLM call per message
- **`ENABLE_PREFERENCE_EXTRACTION`** (default: true): Detects user preferences ("be concise", "use emojis"). Cost: 1 LLM call per message
- **`ENABLE_PROACTIVE_MESSAGING`** (default: false): Bot initiates conversations
- **`LLM_SUPPORTS_VISION`** (default: false): Image analysis capability

**Pattern**: Check feature flags before expensive operations:
```python
if settings.ENABLE_REFLECTIVE_MODE:
    complexity = await classifier.classify(message)
    if complexity == "complex":
        return await reflective_agent.process(message)
```

## 🧠 Cognitive Architecture

### Dual-Process System
- **Fast Mode (System 1)**: Direct LLM response with memory context (`src_v2/agents/engine.py`)
- **Reflective Mode (System 2)**: ReAct reasoning loop for complex queries (`src_v2/agents/reflective.py`)
- **Complexity Classifier**: GPT-4o-mini classifies as `simple|moderate|complex` (gated by `ENABLE_REFLECTIVE_MODE`)

### LLM Configuration Pattern
Three-tier LLM setup for cost optimization:
1. **Main LLM**: Primary conversational model (e.g., `gpt-4o`, Claude Sonnet 4.5)
2. **Router LLM**: Fast/cheap for tool selection (e.g., `gpt-4o-mini`) - optional
3. **Reflective LLM**: High-capability for deep reasoning (e.g., `claude-3.5-sonnet`) - optional

Configure via `LLM_PROVIDER`, `ROUTER_LLM_PROVIDER`, `REFLECTIVE_LLM_PROVIDER` in `.env.{bot}`

## �� Critical Workflows

### Database Migrations (Alembic)
```bash
source .venv/bin/activate
alembic revision --autogenerate -m "description"
alembic upgrade head
```
**Location**: `migrations_v2/` (NOT `migrations/` from v1)

### Adding a New Bot
1. Copy `characters/elena/` → `characters/newbot/`
2. Create `.env.newbot` (copy from `.env.example`)
3. Add to `docker-compose.yml`:
```yaml
newbot:
  profiles: ["newbot", "all"]
  container_name: whisperengine-v2-newbot
  env_file: .env.newbot
  environment:
    - DISCORD_BOT_NAME=newbot
  ports:
    - "8005:8005"  # Unique port
  depends_on:
    postgres: {condition: service_healthy}
    neo4j: {condition: service_healthy}
```

### Testing
- **Unit tests**: `pytest tests_v2/`
- **Direct validation**: `python tests_v2/test_feature_direct_validation.py`
- **HTTP API**: POST to `http://localhost:8000/api/chat`

## 📝 Code Conventions

- **Async-first**: All I/O uses `async/await`
- **Logging**: `from loguru import logger` (NOT `import logging`)
- **Type hints**: Use Pydantic models for validation
- **Paths**: `from pathlib import Path` (NOT `os.path`)
- **Imports**: Set `os.environ["TOKENIZERS_PARALLELISM"] = "false"` before imports (already done in `run_v2.py`)

## ⚠️ Common Pitfalls

- ❌ **Do NOT create docs** unless explicitly requested. Code is source of truth.
- ❌ **Do NOT commit `.env` files**. Use `.env.example` for templates.
- ❌ **Do NOT edit legacy `src/`**. Only work in `src_v2/`.
- ❌ **Do NOT use `make`**. Use `./bot.sh` or direct `docker compose`.
- ✅ **DO check feature flags** before adding expensive LLM calls.
- ✅ **DO restart bots** after code changes (no hot-reload for Python).

## 🗂️ Key Files
- `src_v2/config/settings.py`: Pydantic settings with feature flags
- `src_v2/agents/engine.py`: Main cognitive engine with feature flag gates
- `src_v2/discord/bot.py`: Discord integration with InfluxDB metrics
- `src_v2/knowledge/manager.py`: Knowledge Graph operations
- `src_v2/memory/manager.py`: Vector memory with Qdrant
- `docker-compose.yml`: Profile-based multi-bot deployment
- `bot.sh`: Bash management script for deployment
