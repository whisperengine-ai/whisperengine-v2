# WhisperEngine v2 - AI Agent Development Guide

**Optimized for solo developer with AI-assisted tools** (Dec 2024)

WhisperEngine v2 is a production multi-character Discord AI roleplay platform with Vector Memory (Qdrant), Knowledge Graphs (Neo4j), and Dual-Process cognitive architecture. **This is also an emergent behavior research project** — we study how agentic AI systems develop complex behavior patterns over time.

> **Terminology Note:** We use terms like "perceive," "experience," "memory," and "think" as design metaphors for computational processes. WhisperEngine does not claim to create conscious or sentient AI. See `docs/ref/REF-032-DESIGN_PHILOSOPHY.md` for the "Embodiment Model" approach.

## ✍️ Writing Tone & Style

**The vibe:** Technically grounded, philosophically interesting, never pretentious.

We're doing real engineering that might have interesting implications. We don't oversell it.

| ✅ Do | ❌ Don't |
|-------|---------|
| Lead with mechanism, then note why it's interesting | Lead with grand claims about consciousness/emergence |
| Ask questions: "Can personality emerge from retrieval patterns?" | Make claims: "Personality emerges from retrieval patterns" |
| Show the math — costs, architectures, concrete examples | Hand-wave with buzzwords |
| Let implications be implicit | Say "this is groundbreaking" |
| Use explicit disclaimers when needed | Pretend we've solved hard problems |

**Examples:**

```markdown
# Good
Characters read their own dreams. We're watching whether this creates 
coherent self-models or divergent noise.

# Too woo-woo  
Through recursive self-reflection, characters develop an emergent sense 
of identity that transcends their initial programming.

# Too dry
The system stores dream artifacts in PostgreSQL and retrieves them 
during subsequent LLM calls.
```

**The key move:** Describe *what* it does, then note *why that might be interesting* — but as a question, not a claim.

## 🧪 Research Philosophy

**Core Principle: Observe First, Constrain Later**

WhisperEngine is an emergent behavior research platform. Key tenets:
- **Document behaviors before deciding if they need correction** — premature optimization prevents discovery
- **Minimal viable instrumentation** — add only metrics needed to answer current questions
- **Embrace surprise** — unexpected behaviors are data, not bugs
- **Character autonomy** — bot behavior patterns are worth observing, not just outputs

**Anti-Over-Engineering Principle: Less Code, More Emergent Behavior**

Before adding new fields, categories, or configuration:
- **Ask: "Will this emerge naturally, or must we declare it?"** — prefer behavior over taxonomy
- **Ask: "Can vocabulary do what schema would do?"** — prompt language is cheaper than code
- **Ask: "Are we building it, or letting the system notice it?"** — emergent > declared
- **Example:** We don't have a `memory_layer: "subconscious"` field. Instead, memories with high `absence_streak` *behave* as subconscious — the character notices this through retrieval patterns, not labels.

A declared subconscious is a filing system. An emergent subconscious is actually subconscious.

**Pre-Implementation Checklist (use before building new features):**

Before implementing, answer these four questions:
1. **Schema test:** Am I adding new fields/enums? (Prefer no new schema)
2. **Behavior test:** Can this be expressed as behavior instead of category?
3. **Vocabulary test:** Can prompts do what code would do?
4. **Discovery test:** Will the character *notice* this, or do we have to *tell* it?

If answers lean toward "need new schema/code/declarations" — reconsider the approach.

**Audit Reference:** See `docs/adr/ADR-003-EMERGENCE_PHILOSOPHY.md` for the full emergence philosophy and pre-implementation checklist.

**Research Documentation:**
- `docs/research/` — Research journal (daily logs, weekly summaries, experiments)
- `docs/emergence_philosophy/` — Claude-to-Claude architecture reviews and philosophy docs
- `docs/spec/SPEC-E16-FEEDBACK_LOOP_STABILITY.md` — Phase E16: Emergent behavior guardrails spec

### Bot Autonomy & First-Class Citizenship
**Core Principle:** Bots are first-class citizens.
- Their autonomous actions (replies AND proactive posts) must use the **same processing flow** as human user messages.
- Do not use separate/simplified LLM calls for bot actions.
- Use `MasterGraphAgent` for everything.
- Treat internal triggers (e.g., "I want to post about X") as `user_input` to be processed with full complexity analysis, context retrieval, and cognitive routing.
- This ensures bot behavior generates the same rich data (traces, complexity logs) as user behavior, enabling consistent research analysis.

**Research Cadence:**
- **Daily logs** (~5-10 min): Raw observations in `docs/research/journal/YYYY-MM/`
- **Weekly summaries** (~20-30 min): Pattern synthesis
- **Experiments**: Formal hypothesis testing with templates

**Documentation Templates:**
When creating new documentation, **always follow the template in the `README.md` of each documentation subfolder**:
- `docs/spec/README.md` — SPEC template (features, implementations)
- `docs/guide/README.md` — GUIDE template (how-to tutorials)
- `docs/adr/README.md` — ADR template (architecture decisions)
- `docs/prd/README.md` — PRD template (product requirements)
- `docs/ref/README.md` — REF template (system reference docs)
- `docs/run/README.md` — RUN template (operational runbooks)
- `docs/research/templates/` — Research templates (experiments, daily logs)

**Important:** All templates include an **Origin** section to track idea provenance (who proposed it, what triggered it, whether it emerged from human-AI collaboration). This is itself a form of emergence tracking.

## 🤖 Bot Configurations

### Active Bots

| Bot | Port | Status | Role |
|-----|------|--------|------|
| elena | 8000 | **Dev Primary** | Test all code changes HERE FIRST |
| nottaylor | 8008 | Production | Real users - DO NOT experiment |
| dotty | 8002 | Personal | Personal use, can experiment carefully |
| aria | 8003 | Test | Safe to experiment |
| dream | 8004 | Test | Dream of the Endless character |
| jake | 8005 | Test | Safe to experiment |
| marcus | 8007 | Test | Safe to experiment |
| ryan | 8001 | Test | Safe to experiment |
| sophia | 8006 | Test | Safe to experiment |
| gabriel | 8009 | Personal | AI companion for Cynthia |
| aethys | 8010 | Test | Cosmic transcendent entity |
| aetheris | 8011 | Personal | Philosophical AI companion (Liln) for Cynthia |
| sage | External | Test | External test bot on separate system |

**Note:** Model configurations change frequently. Check `.env.{bot_name}` for current models.

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
- `src_v2/memory/manager.py`: Hybrid Postgres + Qdrant + Neo4j (Unified Memory). Collection name: `whisperengine_memory_{settings.DISCORD_BOT_NAME}`
- `src_v2/memory/embeddings.py`: `EmbeddingService` (384D, auto-initialized)
- **Unified Memory (v2.5)**: Dual-write to Neo4j creates `(:Memory)` nodes for every vector, enabling Vector-First Traversal

### Knowledge Graph
- `src_v2/knowledge/manager.py`: Neo4j Cypher operations. Auto-initializes constraints on `User(id)`, `Entity(name)`, `Memory(id)`
- `src_v2/knowledge/extractor.py`: Pydantic `Fact` model for LLM-generated facts
- **Unified Memory (v2.5)**: `get_memory_neighborhood(vector_ids)` retrieves graph context from vector search results

### Cognitive Engine
- `src_v2/agents/engine.py`: `AgentEngine.generate_response()` - main entry for LLM responses
- `src_v2/agents/classifier.py`: Complexity classification + **intent detection** (voice, image, search)
- `src_v2/agents/reflective.py`: ReAct reasoning loop for complex queries (gated by `ENABLE_REFLECTIVE_MODE`)
- `src_v2/agents/router.py`: Routes to appropriate tools (memory search, fact lookup, etc.)
- `src_v2/agents/llm_factory.py`: Multi-model LLM setup (main + reflective + router)
- `src_v2/agents/composite_tools.py`: Meta-tools that compose multiple tool calls (AnalyzeTopicTool)

### Media Generation (Voice & Image)
- `src_v2/voice/response.py`: `VoiceResponseManager` for TTS generation (ElevenLabs)
- `src_v2/voice/tts.py`: `TTSManager` low-level ElevenLabs API wrapper
- `src_v2/image_gen/service.py`: Image generation via BFL/Replicate/Fal
- `src_v2/core/quota.py`: `QuotaManager` for daily per-user limits (separate for voice/image)

**Intent Detection (v2.0):** Voice and image intents are detected by the `ComplexityClassifier` LLM, not regex/keywords. The classifier only asks for intents that are enabled:
- `"voice"` intent: Only if `ENABLE_VOICE_RESPONSES=true`
- `"image"` intent: Only if `ENABLE_IMAGE_GENERATION=true`

### Background Workers
- `src_v2/workers/task_queue.py`: TaskQueue singleton wrapping arq for Redis job queue
- `src_v2/workers/worker.py`: Shared worker container for ALL background processing
  - `run_insight_analysis`: Pattern detection and epiphany generation
  - `run_summarization`: Session summary generation (post-session)
  - `run_reflection`: User pattern analysis across sessions
  - `run_knowledge_extraction`: Fact extraction to Neo4j (offloaded from response pipeline)
  - `run_dream_generation`: Dream journal generation (uses DreamJournalAgent)
  - `run_reverie_cycle`: Reverie memory consolidation (background, invisible to users)
- `src_v2/agents/insight_graph.py`: LangGraph agent for pattern detection and epiphanies
- `src_v2/agents/dream_journal_graph.py`: Dream Journal generator (first-person narrative broadcast)
- `src_v2/agents/reverie/graph.py`: Reverie (background memory consolidation, NOT dream journal)
- `src_v2/tools/insight_tools.py`: Introspection tools (analyze_patterns, detect_themes, etc.)

> **IMPORTANT DISTINCTION:**
> - **Dream Journal** (`dream_journal_graph.py`): Generates first-person dream narratives that are **broadcast to users**. Uses generator-critic loop with first-person enforcement.
> - **Reverie** (`reverie/graph.py`): Background memory consolidation that links memories together. **Invisible to users**. Does NOT generate dream narratives.

### Character & Evolution
- `src_v2/core/character.py`: Loads `characters/{name}/character.md`, `.yaml` files
- `characters/{name}/character.md`: System prompt (supports `{user_name}`, `{current_datetime}` template vars)
- `characters/{name}/core.yaml`: Identity (purpose, drives, constitution)
- `characters/{name}/ux.yaml`: UX config (thinking indicators, response style, reactions)
- `src_v2/evolution/trust.py`: Trust scoring (5 levels: Stranger→Acquaintance→Friend→Close Friend→Trusted)
- `src_v2/evolution/feedback.py`: Reaction analysis via InfluxDB metrics

### Discord Integration
- `src_v2/discord/bot.py`: Event handlers (`on_message`, `on_reaction_add`), message routing
- `src_v2/discord/daily_life.py`: DailyLifeScheduler and ActionPoller for autonomous activity
- `src_v2/agents/daily_life/graph.py`: **Daily Life Graph** — unified autonomous behavior (replies, reactions, posts)
- `src_v2/voice/`: Voice channels, TTS (ElevenLabs)

**Autonomous Behavior (ADR-015):** All autonomous activity flows through the Daily Life Graph:
- 7-minute polling cycle (`DISCORD_CHECK_INTERVAL_MINUTES`)
- LLM-scored interest (not keyword matching)
- Handles: replies to users, replies to bots, reactions, proactive posts
- See `docs/adr/ADR-015-DAILY_LIFE_UNIFIED_AUTONOMY.md`

**Deprecated (disabled, pending removal):**
- `src_v2/discord/lurk_detector.py` — Real-time keyword-based lurking
- `src_v2/broadcast/cross_bot.py` — Real-time bot-to-bot triggers

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

**⚠️ IMPORTANT: DO NOT automatically run regression tests after every change.**
- Only run tests when the user explicitly asks for them.
- Use `python -m py_compile <file>` for syntax validation.
- The user will decide when to run tests.

**Development workflow**: Test changes on elena first. User runs regression tests manually.

**Regression Test Suite** (API-based, no Discord needed):
```bash
# Quick smoke test (~1-2 min) - health + basic greeting for all bots
python tests_v2/run_regression.py --smoke

# Test elena only (~2-3 min) - run after code changes
python tests_v2/run_regression.py --bot elena

# Full regression suite (~10-15 min) - before releases
python tests_v2/run_regression.py

# Specific test category
python tests_v2/run_regression.py --category memory
python tests_v2/run_regression.py --category character

# Generate HTML report
python tests_v2/run_regression.py --report

# Combine options
python tests_v2/run_regression.py --bot elena --category chat --report
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

### Running Bots (Docker is Primary)

Syntax: `./bot.sh [command] [target]`

**Targets:** `all` | `infra` | `bots` | `workers` | `<name>` (e.g., `elena`, `postgres`)

```bash
./bot.sh up elena         # Start bot in Docker (recommended, even for dev)
./bot.sh up all           # Start all bots + workers
./bot.sh logs elena       # Stream logs
./bot.sh restart elena    # Restart a single bot
./bot.sh restart bots     # Restart all bots (not infra/workers)
./bot.sh restart workers  # Restart all workers
./bot.sh up infra         # Infrastructure only (for local Python debugging)
python run_v2.py elena    # Local Python run (only for debugging, requires infra up)
```

## ⚙️ Settings & Feature Flags

**Location**: `src_v2/config/settings.py` (Pydantic BaseSettings)

**Critical flags** (most now default to true since Phase 1 is complete):
- `ENABLE_REFLECTIVE_MODE` (default: true): ReAct reasoning loop for complex queries
- `ENABLE_RUNTIME_FACT_EXTRACTION` (default: true): Extract facts to Neo4j
- `ENABLE_PREFERENCE_EXTRACTION` (default: true): Detect "be concise" style hints
- `ENABLE_AUTONOMOUS_DRIVES` (default: true): Social Battery, Concern, Curiosity
- `ENABLE_GOAL_STRATEGIST` (default: true): Nightly goal analysis
- `ENABLE_UNIVERSE_EVENTS` (default: true): Cross-bot gossip system
- `ENABLE_GRAPH_ENRICHMENT` (default: true): Proactive graph edge creation
- `ENABLE_GRAPH_PRUNING` (default: true): Graph cleanup
- `ENABLE_VOICE_RESPONSES` (default: false): TTS audio generation (ElevenLabs)
- `ENABLE_IMAGE_GENERATION` (default: true): Image generation (BFL/Replicate/Fal)

**⚠️ SUSPENDED - Autonomous Features (December 2025):**
The following features are **disabled in code** due to multi-bot coordination problems:
- `ENABLE_AUTONOMOUS_ACTIVITY`: Master switch — **CODE DISABLED**
- `ENABLE_DAILY_LIFE_GRAPH`: 7-min polling — **CODE DISABLED**
- Daily Life Scheduler and ActionPoller are commented out in `bot.py`
- See ADR-013 and SPEC-E36 for details on the architecture problem

**The problem:** Multiple bots in the same channel all decide to respond independently, causing "pile-on" behavior. Event-driven architecture made it worse (N² processing). No coordination mechanism exists.

**Proposed solution (ADR-016):** Config vault + generic workers architecture:
- Bot publishes secrets + LLM config to Redis vault on startup
- Workers are generic (any worker handles any bot via vault lookup)
- Workers send to Discord via REST API (same token, no gateway conflict)
- Bot becomes thin gateway (~1ms/msg vs 1.5-11s today)
- Per-bot inboxes prevent N² duplication
- See `docs/adr/ADR-016-WORKER_SECRETS_VAULT.md` for details

**What still works:** Direct interactions (DMs, @mentions, replies), cron jobs (dreams, diaries).

**Deprecated flags** (disabled, pending removal — see ADR-010):
- `ENABLE_AUTONOMOUS_REPLIES`: Real-time lurk detection (superseded by Daily Life Graph)
- `ENABLE_AUTONOMOUS_REACTIONS`: Real-time emoji reactions (superseded by Daily Life Graph)
- `ENABLE_CROSS_BOT_CHAT`: Real-time bot-to-bot triggers (superseded by Daily Life Graph)

**Quotas**:
- `DAILY_IMAGE_QUOTA` (default: 5): Max images per user per day
- `DAILY_AUDIO_QUOTA` (default: 10): Max audio clips per user per day

**Environment loading order**: Env vars → `.env.{DISCORD_BOT_NAME}` → `.env.example` defaults

## 🚀 Deployment & Multi-Bot

### Docker Compose Profiles
```bash
./bot.sh up elena        # Start elena (uses --profile elena)
./bot.sh up all          # Start all bots (uses --profile all)
./bot.sh up infra        # Infrastructure only
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
3. **Unified Memory Traversal**: For retrieved memories, fetch graph neighborhood (Vector-First Traversal)
4. **Complexity + Intent Classification**: LLM classifier returns complexity level AND detected intents (voice, image, search)
4. **Response Generation**: 
   - Simple: Direct LLM call with context
   - Complex (reflective): ReAct loop with tools (search, lookup, image gen, etc.)
   - If "image" intent detected: Complexity promoted to COMPLEX_MID (ensures tools available)
5. **Post-Processing**: 
   - If "voice" intent: Generate TTS audio via ElevenLabs
   - If "image" in response: Attach generated images
   - Extract facts/prefs (background), update trust, store response
6. **Discord Output**: Send to channel with attachments, save to history

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
1. E26: Temporal Graph (time-aware graph traversal)
2. E27: Multi-Character Walks (graph walks across bot perspectives)
3. B5: Trace Learning (learn from reasoning traces)
4. Video processing (clip analysis)
5. Web dashboard (admin UI)

## 📞 Key References

- **Architecture Deep Dives**: `docs/architecture/` (COGNITIVE_ENGINE, DATA_MODELS, MESSAGE_FLOW, etc.)
- **API Reference**: `docs/API_REFERENCE.md` (all endpoints, request/response formats)
- **Regression Tests**: `tests_v2/regression/` (automated test suite), `tests_v2/run_regression.py` (master runner)
- **Testing Guide**: `docs/testing/REGRESSION_TESTING.md` (all test options, categories, expected times)
- **Character System**: `docs/testing/CHARACTERS.md` (folder structure, evolution, testing)
- **Roadmap**: `docs/IMPLEMENTATION_ROADMAP_OVERVIEW.md` (prioritized by complexity for solo dev)
- **Troubleshooting**: `QUICK_REFERENCE.md` (Docker networking, migrations, common issues)
- **Research Journal**: `docs/research/` (daily logs, weekly summaries, experiment templates)
- **Emergent Behavior Philosophy**: `docs/emergence_philosophy/` (Claude collaboration on system behavior principles)

**Architecture Evolution (v2.5 → v3.0):**
- **ADR-013**: Event-Driven Architecture — future streaming replacement for polling
- **ADR-014**: Multi-Party Data Model — schema refactor for group conversations
- **SPEC-E36**: "The Stream" — Redis-based real-time event system (Phase 2 = ADR-013)

---

**Version**: 2.5.0 (Dec 11, 2025 - Unified Memory: Graph Memory Unification)  
**Python Target**: 3.12+  
**Main Packages**: `langchain`, `discord.py`, `asyncpg`, `qdrant-client`, `neo4j`, `pydantic`, `loguru`, `arq`
