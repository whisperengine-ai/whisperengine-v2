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

### Manager Pattern
All subsystems use async `Manager` classes with `async def initialize()`:
- `DatabaseManager`: Connection pooling for all 4 databases with retry logic (`@retry_db_operation` decorator)
- `MemoryManager`: Hybrid Postgres + Qdrant storage with bot-specific collections
- `KnowledgeManager`: Neo4j graph operations with Cypher generation
- `CharacterManager`: Loads from `characters/{bot_name}/character.md` + `goals.yaml`

**Pattern**: Managers are initialized in `src_v2/main.py` startup sequence, then imported globally in modules.

## 🚀 Deployment & Management

### Docker Compose Profiles (Profile-Based Architecture)
```bash
# Infrastructure only (postgres, qdrant, neo4j, influxdb)
./bot.sh infra up
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

**Key Pattern**: `docker-compose.yml` uses profiles (`elena`, `ryan`, `dotty`, `aria`, `dream`, `jake`, `sophia`, `marcus`, `nottaylor`, `all`) for selective bot deployment. Infrastructure services have no profile (always available).

### Local Development
```bash
source .venv/bin/activate
python run_v2.py elena  # Loads .env.elena automatically
```

**Critical**: Always use `.venv` for Python commands. Never use system Python or assume global packages.

### Environment Files Pattern
- `.env.example`: Template with all settings documented
- `.env.{bot_name}`: Bot-specific config (e.g., `.env.elena`, `.env.ryan`)
- `run_v2.py` automatically loads correct env file based on bot name argument
- Settings loaded via Pydantic `BaseSettings` in `src_v2/config/settings.py`

## ⚙️ Feature Flags (Resource Management)

Critical cost optimization via feature flags in `src_v2/config/settings.py`:

- **`ENABLE_REFLECTIVE_MODE`** (default: false): Enables complexity classifier + ReAct reasoning loop. Cost: 1 extra LLM call per message + 3-10 calls for complex queries (~$0.02-0.03 vs $0.001-0.005)
- **`ENABLE_RUNTIME_FACT_EXTRACTION`** (default: true): Extracts facts to Knowledge Graph. Cost: 1 LLM call per message
- **`ENABLE_PREFERENCE_EXTRACTION`** (default: true): Detects user preferences ("be concise", "use emojis"). Cost: 1 LLM call per message
- **`ENABLE_PROACTIVE_MESSAGING`** (default: false): Bot initiates conversations
- **`LLM_SUPPORTS_VISION`** (default: false): Image analysis capability
- **`ENABLE_PROMPT_LOGGING`** (default: false): Log full prompts to `logs/prompts/` for debugging

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

## 🛠️ Critical Workflows

### Database Migrations (Alembic)
```bash
source .venv/bin/activate
alembic revision --autogenerate -m "description"
alembic upgrade head
```
**Location**: `migrations_v2/` (NOT `migrations/` from v1)
**Auto-run**: Migrations automatically run on startup in `src_v2/main.py`

### Adding a New Bot
1. Copy `characters/elena/` → `characters/newbot/`
2. Edit `character.md` (personality, background) and `goals.yaml` (learning objectives)
3. Create `.env.newbot` (copy from `.env.example`, set `DISCORD_BOT_NAME=newbot`)
4. Add to `docker-compose.yml`:
```yaml
newbot:
  profiles: ["newbot", "all"]
  container_name: whisperengine-v2-newbot
  env_file: .env.newbot
  environment:
    - DISCORD_BOT_NAME=newbot
  ports:
    - "8009:8009"  # Unique port (increment from last bot)
  depends_on:
    postgres: {condition: service_healthy}
    neo4j: {condition: service_healthy}
    qdrant: {condition: service_started}
    influxdb: {condition: service_healthy}
```
5. Start with `./bot.sh up newbot`

### Character Configuration
- **`characters/{name}/character.md`**: Markdown file loaded as system prompt. Supports template variables: `{user_name}`, `{current_datetime}`, `{recent_memories}`, `{knowledge_context}`
- **`characters/{name}/goals.yaml`**: Learning objectives with priority/category (see `characters/elena/goals.yaml` for format)
- **`characters/{name}/background.yaml`**: Optional structured background data

### Testing
- **Unit tests**: `pytest tests_v2/`
- **Direct validation**: `python tests_v2/test_feature_direct_validation.py`
- **HTTP API**: `curl -X POST http://localhost:8000/api/chat -H "Content-Type: application/json" -d '{"user_id":"test","message":"Hello"}'`

## 📝 Code Conventions

- **Python environment**: ALWAYS use `.venv` for Python commands. Activate with `source .venv/bin/activate` before running any Python code.
- **Type hints**: REQUIRED on all function signatures (arguments and return types). Use `typing` module or modern syntax (e.g., `list[str]`, `dict[str, Any]`, `Optional[int]`).
- **Async-first**: All I/O uses `async/await` (database, HTTP, file operations)
- **Logging**: `from loguru import logger` (NOT `import logging`). Configured in `src_v2/main.py` at startup
- **Paths**: `from pathlib import Path` (NOT `os.path`)
- **Database retries**: Use `@retry_db_operation()` decorator for DB methods (defaults to 3 retries)
- **Imports**: `os.environ["TOKENIZERS_PARALLELISM"] = "false"` set in `run_v2.py` before imports
- **Error handling**: Log with `logger.error(f"Context: {e}")`, not bare `except Exception: pass`

### Type Hints Examples
```python
# Good - explicit type hints
async def process_message(user_id: str, content: str, metadata: Optional[dict[str, Any]] = None) -> str:
    ...

# Good - return type for complex objects
def get_character(name: str) -> Optional[Character]:
    ...

# Bad - no type hints
async def process_message(user_id, content, metadata=None):
    ...
```

### Python Version
- **Target**: Python 3.12+ (specified in `pyproject.toml`)
- **Async runtime**: Uses `asyncio.run()` in `run_v2.py` and `src_v2/main.py`

## ⚠️ Common Pitfalls

- ❌ **Do NOT create docs** unless explicitly requested. Code is source of truth.
- ❌ **Do NOT commit `.env` files**. Use `.env.example` for templates.
- ❌ **Do NOT edit legacy `src/`**. Only work in `src_v2/`.
- ❌ **Do NOT use `make`**. Use `./bot.sh` or direct `docker compose`.
- ❌ **Do NOT add expensive LLM calls** without checking feature flags first.
- ❌ **Do NOT assume hot-reload**. Restart bots after code changes: `./bot.sh restart elena`
- ✅ **DO use profile-based deployment**: `./bot.sh up <bot_name>` (not `docker compose up <bot_name>`)
- ✅ **DO check `@retry_db_operation` on new DB methods** for resilience.
- ✅ **DO use async/await** for all I/O operations (no blocking calls).

## 🗂️ Key Files
- `src_v2/config/settings.py`: Pydantic settings with feature flags and env file loading
- `src_v2/agents/engine.py`: Main cognitive engine (`AgentEngine.generate_response()`)
- `src_v2/discord/bot.py`: Discord integration with event handlers
- `src_v2/knowledge/manager.py`: Knowledge Graph operations with Cypher generation
- `src_v2/memory/manager.py`: Hybrid Postgres + Qdrant vector memory
- `src_v2/core/database.py`: `DatabaseManager` with connection pooling and `@retry_db_operation`
- `src_v2/core/character.py`: `CharacterManager` loads from `characters/{name}/`
- `docker-compose.yml`: Profile-based multi-bot deployment with health checks
- `bot.sh`: Bash management script (preferred over direct `docker compose`)
- `run_v2.py`: Entry point that sets `DISCORD_BOT_NAME` and loads env files
