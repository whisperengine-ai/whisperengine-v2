# WhisperEngine v2 - AI Agent Development Guide

**Optimized for solo developer with AI-assisted tools** (Nov 28, 2025)

WhisperEngine v2 is a production multi-character Discord AI roleplay platform with Vector Memory (Qdrant), Knowledge Graphs (Neo4j), and Dual-Process cognitive architecture.

## 🤖 Bot Configurations

### Active Bots & Models

| Bot | Port | Status | Main Model | Reflective Model |
|-----|------|--------|------------|------------------|
| elena | 8000 | Production | `openai/gpt-4o` | `openai/gpt-4o` |
| nottaylor | 8008 | Production | `openai/gpt-4o` | `openai/gpt-4o` |
| dotty | 8002 | Production | `openai/gpt-4o` | `openai/gpt-4o` |
| aria | 8003 | Test | `google/gemini-2.5-flash` | `anthropic/claude-3.5-sonnet` |
| dream | 8004 | Test | `deepseek/deepseek-r1` | `google/gemini-2.5-flash` |
| jake | 8005 | Test | `anthropic/claude-3.5-sonnet` | `meta-llama/llama-3.3-70b-instruct` |
| marcus | 8007 | Test | `mistralai/mistral-large` | `deepseek/deepseek-r1` |
| ryan | 8001 | Test | `meta-llama/llama-3.3-70b-instruct` | `mistralai/mistral-large` |
| sophia | 8006 | Test | `google/gemini-2.5-pro` | `openai/gpt-4o` |
| aethys | - | Inactive | - | - |

**Router model**: All bots use `openai/gpt-4o-mini` for fast routing decisions.

**Production bots** (nottaylor, dotty, elena): Use stable GPT-4o configuration, do not change models.

**Test bots**: Used for A/B testing different LLM providers via OpenRouter.

## ⚡ Quick Architecture

### Runtime Flow
`run_v2.py elena` → `src_v2/main.py` → `db_manager.connect_all()` → Initialize Memory/Knowledge → Discord Bot + FastAPI

### The "Five Pillars"
| System | Port | Pattern |
|--------|------|---------|
| PostgreSQL | 5432 | Chat history, users, trust scores (Alembic migrations) |
| Qdrant | 6333 | Vector memory, `whisperengine_memory_{bot_name}` collection |
| Neo4j | 7687 | Knowledge graph, Cypher queries, constraints on `User.id` |
| InfluxDB | 8086 | Metrics/analytics (Flux queries in `evolution/feedback.py`) |
| Redis | 6379 | Cache layer + task queue (arq for background jobs) |

### Manager Pattern (Every Subsystem)
```python
class XManager:
    async def initialize(self) -> None: pass  # Called in main.py
    @retry_db_operation(max_retries=3)  # Auto-retry transients
    async def method(...): pass
```

Key singletons: `db_manager`, `memory_manager`, `knowledge_manager`, `character_manager`, `trust_manager`, `AgentEngine`, `task_queue` (imported globally after init)

## 🎯 Critical Code Patterns

### 0. Documentation Style: Pseudocode in Design Docs
When writing feature specifications or roadmap documents (in `docs/roadmaps/`), **use pseudocode instead of full Python code**. This keeps docs:
- Readable and focused on design, not implementation
- Language-agnostic (easier to adapt to Rust, Go, TypeScript later if needed)
- Concise (pseudocode is ~1/3 the LOC of Python)
- Maintainable (small changes to spec don't require code rewrites)

**Pattern for docs:**
```
// Use clean pseudocode with minimal syntax
function needs_channel_context(message) -> bool:
  if has_recent_marker(message):
    return true
  if has_past_marker(message):
    return false
  return default(true)
```

**When to use full code instead:**
- Implementation guides with real error handling
- Code examples that users will copy-paste
- Tests that need to actually run
- API integration examples

**See:** `docs/roadmaps/CHANNEL_CONTEXT_AWARENESS.md` for pseudocode examples

### 1. Async/Await + Type Hints (REQUIRED)
All I/O is async; type hints on ALL function signatures:
```python
# GOOD - LangChain integration pattern
async def generate_response(
    self, 
    user_message: str,
    chat_history: Optional[List[BaseMessage]] = None,
    image_urls: Optional[List[str]] = None
) -> str:
    """Docstring with type context."""
```

### 2. Dependency Injection Pattern
Engines accept dependencies for testability:
```python
# In AgentEngine.__init__
self.trust_manager = trust_manager_dep or trust_manager  # Use injected or global
```

### 3. Error Handling with Logging
Use `loguru` (not `logging`); log context:
```python
from loguru import logger
try:
    result = await some_operation()
except Exception as e:
    logger.error(f"Operation failed with user_id={user_id}, reason: {e}")
    raise
```

### 4. Feature Flags (Cost Control)
Check before expensive LLM calls:
```python
if settings.ENABLE_REFLECTIVE_MODE and complexity == "complex":
    return await self.reflective_agent.process(message)
return await self.direct_response()  # Fast path
```

### 5. Parallel Context Retrieval
Use `asyncio.gather` to fetch from multiple DBs simultaneously:
```python
memories, facts, trust, goals = await asyncio.gather(
    memory_manager.get_recent(user_id),
    knowledge_manager.query_graph(user_id, msg),
    trust_manager.get_relationship_level(user_id, char_name),
    goal_manager.get_active_goals(user_id)
)
```

## 📁 File Organization & Entry Points

### Database Layer
- `src_v2/core/database.py`: `DatabaseManager` with `@retry_db_operation` decorator for resilience
- `migrations_v2/`: Alembic migration files. Always run: `alembic upgrade head` on startup (auto-run in `main.py`)

### Memory System
- `src_v2/memory/manager.py`: Hybrid Postgres + Qdrant. Collection name: `whisperengine_memory_{settings.DISCORD_BOT_NAME}`
- `src_v2/memory/embeddings.py`: `EmbeddingService` (384D, auto-initialized)

### Knowledge Graph
- `src_v2/knowledge/manager.py`: Neo4j Cypher operations. Auto-initializes constraints on `User(id)`, `Entity(name)`
- `src_v2/knowledge/extractor.py`: Pydantic `Fact` model for LLM-generated facts

### Cognitive Engine
- `src_v2/agents/engine.py`: `AgentEngine.generate_response()` - main entry for LLM responses
- `src_v2/agents/classifier.py`: Fast complexity classification (simple/moderate/complex)
- `src_v2/agents/reflective.py`: ReAct reasoning loop for complex queries (gated by `ENABLE_REFLECTIVE_MODE`)
- `src_v2/agents/router.py`: Routes to appropriate tools (memory search, fact lookup, etc.)
- `src_v2/agents/llm_factory.py`: Multi-model LLM setup (main + reflective + router)
- `src_v2/agents/composite_tools.py`: Meta-tools that compose multiple tool calls (AnalyzeTopicTool)

### Background Workers
- `src_v2/workers/task_queue.py`: TaskQueue singleton wrapping arq for Redis job queue
- `src_v2/workers/insight_worker.py`: Shared worker container for ALL background processing
  - `run_insight_analysis`: Pattern detection and epiphany generation
  - `run_summarization`: Session summary generation (post-session)
  - `run_reflection`: User pattern analysis across sessions
  - `run_knowledge_extraction`: Fact extraction to Neo4j (offloaded from response pipeline)
- `src_v2/agents/insight_agent.py`: ReAct agent for pattern detection and epiphanies
- `src_v2/tools/insight_tools.py`: Introspection tools (analyze_patterns, detect_themes, etc.)

### Character & Evolution
- `src_v2/core/character.py`: Loads `characters/{name}/character.md`, `.yaml` files
- `characters/{name}/character.md`: System prompt (supports `{user_name}`, `{recent_memories}` template vars)
- `characters/{name}/core.yaml`: Identity (purpose, drives, constitution)
- `characters/{name}/ux.yaml`: UX config (thinking indicators, response style)
- `src_v2/evolution/trust.py`: Trust scoring (5 levels: Stranger→Acquaintance→Friend→Close→Soulmate)
- `src_v2/evolution/feedback.py`: Reaction analysis via InfluxDB metrics

### Discord Integration
- `src_v2/discord/bot.py`: Event handlers (`on_message`, `on_reaction_add`), message routing
- `src_v2/discord/scheduler.py`: Proactive engagement (Phase 13 complete)
- `src_v2/voice/`: Voice channels, TTS (ElevenLabs)

### API
- `src_v2/api/app.py`: FastAPI app with Uvicorn
- `src_v2/api/routes.py`: Chat and diagnostic endpoints
- `src_v2/api/models.py`: Pydantic request/response models
- `docs/API_REFERENCE.md`: Full API documentation

**API Endpoints** (for automated testing without Discord):

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/chat` | POST | Send message, get response (same as Discord DM) |
| `/api/diagnostics` | GET | Bot config, DB status, feature flags |
| `/api/user-state` | POST | Get trust score, memories, knowledge for user |
| `/api/conversation` | POST | Multi-turn conversation test |
| `/api/clear-user-data` | POST | Clear user data for test isolation |
| `/health` | GET | Health check |

## 🔧 Development Workflows

### Testing

**Automated API Testing** (no Discord needed):
```bash
# Run full regression suite across all bots
python tests_v2/run_regression.py

# Quick smoke test (health + basic chat)
python tests_v2/run_regression.py --smoke

# Test specific bot
python tests_v2/run_regression.py --bot elena

# Test specific category
python tests_v2/run_regression.py --category memory

# Generate HTML report
python tests_v2/run_regression.py --report
```

**Test Categories**:
- `health` - Health endpoint, diagnostics, model verification
- `chat` - Basic greetings, questions, context injection  
- `character` - Self-description, personality consistency
- `memory` - Memory storage and recall
- `conversation` - Multi-turn conversation coherence
- `complexity` - Routing (simple→fast, complex→reflective)
- `comparison` - Same prompt across all models
- `production` - Stability tests for production bots

**Direct API Testing**:
```bash
# Simple chat
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","message":"Hello!"}'

# Get diagnostics (model config, DB status)
curl http://localhost:8000/api/diagnostics

# Multi-turn conversation test
curl -X POST http://localhost:8000/api/conversation \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","messages":["Hi","What is your name?"]}'

# Check user state (trust, memories)
curl -X POST http://localhost:8000/api/user-state \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test"}'
```

**Unit Tests**:
```bash
pytest tests_v2/test_memory_manager.py -v
python tests_v2/test_feature_direct_validation.py
```

### Database Migrations
```bash
source .venv/bin/activate
# Generate: alembic revision --autogenerate -m "description"
# Apply: alembic upgrade head
# Rollback: alembic downgrade -1
```

### Running Locally
```bash
./bot.sh infra up          # Infrastructure only
python run_v2.py elena    # Start bot (loads .env.elena)
./bot.sh logs elena -f    # Stream logs
./bot.sh restart elena    # Restart a single bot (only takes ONE bot name)
```

**Note**: `./bot.sh restart` only accepts a single bot name. To restart multiple bots, run the command multiple times.

## ⚙️ Settings & Feature Flags

**Location**: `src_v2/config/settings.py` (Pydantic BaseSettings)

**Critical flags**:
- `ENABLE_REFLECTIVE_MODE` (default: false): ReAct reasoning loop (~$0.02-0.03 per complex query)
- `ENABLE_RUNTIME_FACT_EXTRACTION` (default: true): Extract facts to Neo4j ($0.001 per message)
- `ENABLE_PREFERENCE_EXTRACTION` (default: true): Detect "be concise" style hints
- `ENABLE_PROACTIVE_MESSAGING` (default: false): Bot initiates contact (requires trust ≥ 20)

**Environment loading order**: Env vars → `.env.{DISCORD_BOT_NAME}` → `.env.example` defaults

## 🚀 Deployment & Multi-Bot

### Docker Compose Profiles
```bash
./bot.sh up elena        # Start elena (uses --profile elena)
./bot.sh up all          # Start all bots (uses --profile all)
./bot.sh infra up        # Infrastructure only
```

**Key pattern**: `docker-compose.yml` uses profiles. Infrastructure (postgres, qdrant, neo4j, influxdb, redis) has NO profile (always up). Each bot has profile `[name, "all"]`. The shared `insight-worker` has profile `["workers", "all"]`.

### Running Background Workers
```bash
./bot.sh start workers    # Start shared insight-worker container
```

**Worker Architecture:** A single `insight-worker` serves ALL bot instances. Jobs include `bot_name` in the payload so the worker loads the correct character context. No 1:1 bot-to-worker mapping needed.

### Adding a New Bot
1. Create `.env.newbot` (copy `.env.example`)
2. Create `characters/newbot/` with `character.md`, `goals.yaml`
3. Add to `docker-compose.yml` with unique port, profile `["newbot", "all"]`
4. `./bot.sh up newbot`

## ⚠️ Solo Developer Pitfalls

- ❌ **Don't add LLM calls without feature flags** → Can 10x costs
- ❌ **Don't use system Python** → Always `source .venv/bin/activate`
- ❌ **Don't skip type hints** → Breaks AI code generation
- ❌ **Don't assume hot-reload** → Restart after code changes
- ❌ **Don't edit `src/` legacy code** → Only `src_v2/`
- ✅ **DO use `asyncio.gather` for parallel DB calls** → 3-5x faster context retrieval
- ✅ **DO log context in errors** → Speeds debugging with AI
- ✅ **DO apply `@retry_db_operation` to all DB methods** → Handles transient failures
- ✅ **DO test migrations locally first** → Alembic migrations are one-way

## 🧠 Message Flow (For New Features)

1. **Discord Input**: `on_message()` → Validate → Store to history
2. **Context Retrieval**: Parallel gather from Qdrant (memories) + Neo4j (facts) + Postgres (trust/prefs)
3. **Complexity Check**: Fast embeddings-based classifier (60% trivial, bypass LLM)
4. **Response Generation**: 
   - Simple: Direct LLM call with context
   - Complex (reflective): ReAct loop with tools (search, lookup, etc.)
5. **Post-Processing**: Extract facts/prefs (background), update trust, store response
6. **Discord Output**: Send to channel, save to history

## 📊 Performance Optimization (Solo Dev Edition)

**Already implemented** (no new work needed):
- ✅ Parallel context retrieval (3x faster)
- ✅ Fast semantic classifier (bypass LLM 60% of time)
- ✅ Native function calling (no regex parsing)
- ✅ Parallel tool execution (ReAct)
- ✅ Adaptive max steps (5/10/15 based on complexity)
- ✅ Composite tools (reduce 4-step queries to 2)
- ✅ Background insight agent (reasoning traces, epiphanies, pattern learning)

**Next phases** (from IMPLEMENTATION_ROADMAP_OVERVIEW.md):
1. Grafana dashboards (InfluxDB visualization)
2. Image generation (DALL-E 3 / Stable Diffusion)
3. Video processing (clip analysis)
4. Web dashboard (admin UI)

## 📞 Key References

- **Architecture Deep Dives**: `docs/architecture/` (COGNITIVE_ENGINE, DATA_MODELS, MESSAGE_FLOW, etc.)
- **API Reference**: `docs/API_REFERENCE.md` (all endpoints, request/response formats)
- **Regression Tests**: `tests_v2/regression/` (automated test suite), `tests_v2/run_regression.py` (master runner)
- **Roadmap**: `docs/IMPLEMENTATION_ROADMAP_OVERVIEW.md` (prioritized by complexity for solo dev)
- **Troubleshooting**: `QUICK_REFERENCE.md` (Docker networking, migrations, common issues)
- **Character System**: `docs/architecture/WHISPERENGINE_2_DESIGN.md` (why polyglot, LLM-native design)

---

**Version**: 2.2 (Nov 28, 2025 - Added API testing endpoints and regression suite)  
**Python Target**: 3.12+  
**Main Packages**: `langchain`, `discord.py`, `asyncpg`, `qdrant-client`, `neo4j`, `pydantic`, `loguru`, `arq`
