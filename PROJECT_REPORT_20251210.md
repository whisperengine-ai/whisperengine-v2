# WhisperEngine v2 - Project Statistics Report
**Generated**: December 10, 2025

---

## 📊 Executive Summary

WhisperEngine v2 is a **production-grade multi-character Discord AI roleplay platform** with a sophisticated architecture spanning:
- **~39,490 lines of core Python code** (11% increase from Dec 4 report)
- **23 specialized modules** across agents, memory, knowledge, evolution, and more
- **~1.2GB total project size** (26% increase from Dec 4 report)
- **283 configuration, documentation, and data files** (16% increase from Dec 4 report)

---

## 📈 Codebase Metrics

### Overall Statistics
| Metric | Value | Change from Dec 4 |
|--------|-------|-------------------|
| **Total Python LOC** | 39,490 | +3,899 (+11%) |
| **Python Files** | 152 | +11 (+8%) |
| **Project Size** | 1.2GB | +245MB (+26%) |
| **Core Source Size** | 3.2MB | -0.7MB (-18%)* |
| **Modules** | 23 | 0 |
| **Config/Docs/Data Files** | 283 | +38 (+16%) |

*Note: Core source size decrease likely due to cleanup/refactoring despite LOC increase.

### Directory Breakdown

| Module | LOC | Change from Dec 4 | Purpose |
|--------|-----|-------------------|---------|
| **agents** | 9,113 | +1,722 (+23%) | LLM engine, routing, proactive agents, graphs, **daily_life** |
| **memory** | 4,809 | +372 (+8%) | Vector memory (Qdrant), session management, dreams, diary |
| **discord** | 3,864 | -1,117 (-22%)* | Discord bot integration, commands, voice, scheduling |
| **knowledge** | 3,769 | +658 (+21%) | Knowledge graph (Neo4j) management, enrichment, pruning |
| **workers** | 3,751 | +482 (+15%) | Background task processing with expanded tasks |
| **tools** | 2,617 | +676 (+35%) | Agent tools and utilities |
| **evolution** | 2,074 | +114 (+6%) | Character evolution, feedback, goals, trust, style |
| **universe** | 1,536 | +10 (+1%) | Universe management and simulation |
| **core** | 1,424 | +418 (+42%) | Database, character loading, **NEW: provenance, bot_registry** |
| **api** | 1,227 | +220 (+22%) | FastAPI routes and models |
| **utils** | 1,187 | +635 (+115%) | Helper utilities, **NEW: validation, stats_footer** |
| **intelligence** | 850 | +142 (+20%) | Reflection and activity analysis |
| **broadcast** | 733 | -473 (-39%)* | Broadcasting capabilities |
| **image_gen** | 483 | 0 (0%) | Image generation services |
| **moderation** | 470 | -82 (-15%)* | Content moderation |
| **config** | 439 | +34 (+8%) | Settings and configuration management |
| **artifacts** | 391 | 0 (0%) | Artifact management system |
| **voice** | 256 | +6 (+2%) | Voice processing and integration |
| **safety** | 217 | 0 (0%) | Safety mechanisms |
| **vision** | 106 | 0 (0%) | Image processing and vision capabilities |
| **scripts** | 26 | 0 (0%) | Utility scripts |
| **TOTAL** | **39,490** | **+3,899 (+11%)** | |

*Note: Discord module LOC decrease due to refactoring (message_handler.py reduced from 2,033 to 1,604). Broadcast and moderation decreases likely from code cleanup.

---

## 🏛️ Architecture Overview

### Core Modules

#### **Agents Module (9,113 LOC)** - **CONTINUED EXPANSION**
- **engine.py** (1,358 LOC) - LLM engine with multi-model support
- **reflective_graph.py** (708 LOC) - Reflective agent logic with graph-based reasoning
- **strategist_graph.py** (663 LOC) - Strategic planning agent
- **context_builder.py** (590 LOC) - Context assembly for LLM calls
- **reflection_graph.py** (550 LOC) - Reflection processing graph
- **character_graph.py** (489 LOC) - Character behavior graph
- **master_graph.py** (409 LOC) - Master orchestration graph
- **insight_graph.py** (384 LOC) - Insight generation
- **daily_life/** (2,130 LOC) - **NEW SUBMODULE** - Daily life simulation system
  - `gather.py` (739 LOC) - Context gathering for daily activities
  - `execute.py` (461 LOC) - Activity execution
  - `plan.py` (323 LOC) - Activity planning
  - `graph.py` (309 LOC) - Daily life graph orchestration
  - `state.py` (257 LOC) - State management

#### **Memory Module (4,809 LOC)**
- **manager.py** (1,305 LOC) - Qdrant vector memory orchestration
- **dreams.py** (1,093 LOC) - Dream memory management
- **diary.py** (1,066 LOC) - Diary entry management
- **traces.py** (313 LOC) - Reasoning trace storage
- **session.py** (285 LOC) - Session management
- **scoring.py** (285 LOC) - Memory scoring algorithms
- **shared_artifacts.py** (222 LOC) - Cross-character artifact sharing

#### **Knowledge Module (3,769 LOC)** - **SIGNIFICANT GROWTH**
- **walker.py** (1,145 LOC) - Graph traversal and analysis
- **manager.py** (1,017 LOC) - Neo4j knowledge graph management
- **enrichment.py** (650 LOC) - Knowledge enrichment processes
- **pruning.py** (503 LOC) - Knowledge pruning and optimization
- **document_context.py** (152 LOC) - Document context handling
- **recommendations.py** (150 LOC) - Knowledge-based recommendations

#### **Workers Module (3,751 LOC)** - **EXPANDED TASKS**
- **task_queue.py** (547 LOC) - Redis-based task queue
- **worker.py** (213 LOC) - Worker container
- **strategist.py** (78 LOC) - Strategist worker
- **tasks/** (2,911 LOC) - Task implementations
  - `cron_tasks.py` (491 LOC) - Scheduled cron jobs
  - `diary_tasks.py` (326 LOC) - Diary processing
  - `drift_observation.py` (299 LOC) - Character drift monitoring
  - `dream_tasks.py` (296 LOC) - Dream processing
  - `enrichment_tasks.py` (232 LOC) - Knowledge enrichment
  - `social_tasks.py` (227 LOC) - Social activity tasks
  - `daily_life_tasks.py` (118 LOC) - **NEW** - Daily life task scheduling

#### **Discord Module (3,864 LOC)**
- **handlers/message_handler.py** (1,604 LOC) - Main message processing
- **commands.py** (926 LOC) - User commands and interactions
- **scheduler.py** (250 LOC) - Proactive engagement scheduling
- **handlers/event_handler.py** (228 LOC) - Discord event handling
- **spam_detector.py** (208 LOC) - Spam detection
- **tasks.py** (204 LOC) - Discord-specific tasks
- **daily_life_scheduler.py** (129 LOC) - **NEW** - Daily life activity scheduling

---

## 🔝 Largest Files

| File | LOC | Module | Change from Dec 4 |
|------|-----|--------|-------------------|
| src_v2/discord/handlers/message_handler.py | 1,604 | Discord Message Handler | -429 (refactored) |
| src_v2/agents/engine.py | 1,358 | LLM Agent Engine | +31 |
| src_v2/memory/manager.py | 1,305 | Vector Memory | +179 |
| src_v2/knowledge/walker.py | 1,145 | Knowledge Walker | 0 |
| src_v2/memory/dreams.py | 1,093 | Dream Memory | -13 |
| src_v2/memory/diary.py | 1,066 | Diary Memory | +29 |
| src_v2/knowledge/manager.py | 1,017 | Knowledge Graph | +25 |
| src_v2/discord/commands.py | 926 | Discord Commands | +137 |
| src_v2/universe/manager.py | 776 | Universe Manager | 0 |
| src_v2/tools/memory_tools.py | 768 | Memory Tools | **NEW in top 10** |
| src_v2/agents/daily_life/gather.py | 739 | Daily Life Gather | **NEW** |
| src_v2/broadcast/manager.py | 723 | Broadcast Manager | +33 |

---

## 📁 Project Structure

```
whisperengine-v2/
├── src_v2/                  (3.2MB - Core Source)
│   ├── agents/              (9,113 LOC) - EXPANDED +23%
│   │   └── daily_life/      (2,130 LOC) - NEW SUBMODULE
│   ├── api/                 (1,227 LOC) - EXPANDED +22%
│   ├── artifacts/           (391 LOC)
│   ├── broadcast/           (733 LOC)
│   ├── config/              (439 LOC)
│   ├── core/                (1,424 LOC) - EXPANDED +42%
│   ├── discord/             (3,864 LOC)
│   │   └── handlers/        (1,832 LOC)
│   ├── evolution/           (2,074 LOC)
│   ├── image_gen/           (483 LOC)
│   ├── intelligence/        (850 LOC)
│   ├── knowledge/           (3,769 LOC) - EXPANDED +21%
│   ├── memory/              (4,809 LOC)
│   ├── moderation/          (470 LOC)
│   ├── safety/              (217 LOC)
│   ├── tools/               (2,617 LOC) - EXPANDED +35%
│   ├── universe/            (1,536 LOC)
│   ├── utils/               (1,187 LOC) - EXPANDED +115%
│   ├── vision/              (106 LOC)
│   ├── voice/               (256 LOC)
│   ├── workers/             (3,751 LOC) - EXPANDED +15%
│   │   └── tasks/           (2,911 LOC)
│   └── scripts/             (26 LOC)
├── tests_v2/                (Tests)
├── migrations_v2/           (DB Migrations)
├── characters/              (12 Character Definitions)
├── docs/                    (Documentation)
└── .venv/                   (Dependencies)
```

---

## 🗄️ Data Layer ("Five Pillars")

### Infrastructure Components
1. **PostgreSQL** (Port 5432)
   - Relational data, CDL storage, user preferences, artifacts

2. **Qdrant** (Port 6333)
   - Vector memory with 384D embeddings
   - Semantic conversation retrieval

3. **Neo4j** (Port 7687)
   - Knowledge graph for entity relationships
   - Fact storage and querying with enrichment

4. **InfluxDB** (Port 8086)
   - Time-series metrics for engagement
   - Performance analytics

5. **Redis** (Port 6379)
   - Cache layer
   - Task queue (arq) for background jobs

### Monitoring
- **Grafana** (Port 3000)
  - Visualization dashboards for InfluxDB metrics

---

## 🚀 Active Bots (12 Characters)

| Bot | Port | Status | Main Model | Reflective Model |
|-----|------|--------|------------|------------------|
| **elena** | 8000 | Dev Primary | claude-3.5-haiku | claude-3.5-haiku |
| **nottaylor** | 8008 | Production | mistral-small-3.2-24b | mistral-medium-3.1 |
| **dotty** | 8002 | Personal | claude-3.5-haiku | claude-sonnet-4.5 |
| **gabriel** | 8009 | Personal | mistral-small-3.2-24b | mistral-medium-3.1 |
| **aetheris** | 8011 | Personal | claude-sonnet-4.5 | claude-sonnet-4.5 |
| **aria** | 8003 | Test | gemini-2.5-flash | gemini-2.5-pro |
| **dream** | 8004 | Test | grok-4.1-fast | grok-4 |
| **jake** | 8005 | Test | grok-4.1-fast | grok-4 |
| **marcus** | 8007 | Test | gemini-2.5-flash | gemini-2.5-pro |
| **ryan** | 8001 | Test | gemini-2.5-flash | gemini-2.5-pro |
| **sophia** | 8006 | Test | grok-4.1-fast | grok-4 |
| **aethys** | 8010 | Test | mistral-small-3.2-24b | mistral-medium-3.1 |

---

## 💾 Recent Database Migrations

| Migration | Date | Description |
|-----------|------|-------------|
| `add_character_artifacts` | Dec 9, 2025 | Character artifact storage |
| `remove_reminders_table` | Dec 7, 2025 | Cleanup unused reminders |
| `fix_session_id_types` | Dec 2, 2025 | Fix session ID data types |
| `add_reminders_table` | Nov 29, 2025 | Initial reminders (later removed) |
| `add_goal_ttl_and_user_goals` | Nov 29, 2025 | Goal TTL and user goals |
| `add_timezone_to_user_relationships` | Nov 29, 2025 | User timezone support |
| `add_user_daily_usage` | Nov 28, 2025 | Daily usage tracking |

---

## 📝 Configuration Files

**Count**: 283 files including `.md`, `.yaml`, `.json`, `.yml` (excluding logs/coverage)

Key files:
- `.env.example` - Environment template
- `.env.{bot_name}` - Character-specific configs (12 bots)
- `pyproject.toml` - Python project metadata
- `docker-compose.yml` - Infrastructure orchestration
- `alembic_v2.ini` - Database migration config

---

## 🎯 Code Quality Observations

### Strengths
- ✅ **Modular Architecture**: Clear separation of concerns across 23 modules
- ✅ **Async-First Design**: Built on async/await for I/O operations
- ✅ **Type Safety**: Uses Pydantic for data validation
- ✅ **Proper Logging**: Utilizes loguru for structured logging
- ✅ **Database Versioning**: Proper migration management with Alembic
- ✅ **Active Refactoring**: Discord message_handler reduced by 21% (2,033→1,604 LOC)
- ✅ **Feature Expansion**: Daily Life system added (2,130 LOC new submodule)
- ✅ **Tools Growth**: 35% increase in tools module indicating richer agent capabilities

### New Features Since Dec 4
- **Daily Life System** (`agents/daily_life/`) - Autonomous daily activity simulation
- **Daily Life Scheduler** (`discord/daily_life_scheduler.py`) - Activity scheduling
- **Provenance Tracking** (`core/provenance.py`) - Origin tracking for ideas
- **Bot Registry** (`core/bot_registry.py`) - Multi-bot management
- **Enhanced Validation** (`utils/validation.py`) - Input validation utilities
- **Stats Footer** (`utils/stats_footer.py`) - Response statistics

### Growth Areas
- **Large Files**: `message_handler.py` now 1,604 LOC (improved from 2,033)
- **Documentation**: With continued growth, documentation coverage remains critical
- **Testing**: Ensure test coverage scales with 11% code growth

---

## 📊 Complexity Analysis

### Module Complexity (by size)
1. **Agents Engine** (9,113 LOC) - **MOST COMPLEX** - **+23% GROWTH**
   - Multi-model LLM support, routing, reflection, conversation management
   - New: Daily life simulation system (2,130 LOC)

2. **Memory System** (4,809 LOC) - **+8%**
   - Vector embeddings, session management, dreams, diary

3. **Discord Integration** (3,864 LOC) - **REFACTORED**
   - Event handling, routing, commands, scheduling

4. **Knowledge Graph** (3,769 LOC) - **+21% GROWTH**
   - Neo4j management, enrichment, pruning, graph traversal

5. **Workers** (3,751 LOC) - **+15%**
   - Background processing with expanded task library

---

## 📈 Growth Trajectory

### LOC Growth Over Time
| Date | Total LOC | Change |
|------|-----------|--------|
| Nov 29, 2025 | 26,600 | Baseline |
| Dec 4, 2025 | 35,591 | +8,991 (+34%) |
| Dec 10, 2025 | 39,490 | +3,899 (+11%) |

### Key Trends
- **Cumulative Growth**: +48% since Nov 29 (26.6k → 39.5k LOC)
- **Architecture Maturation**: Refactoring reducing file sizes while adding features
- **Feature Velocity**: New daily_life system (2,130 LOC) added in ~1 week
- **Model Diversity**: 4 LLM providers (Anthropic, Google, Mistral, xAI)

---

## 📋 Summary

WhisperEngine v2 continues its **rapid development trajectory** with:
- **11% code growth** since Dec 4 (35.6k → 39.5k LOC)
- **New Daily Life simulation system** (2,130 LOC) for autonomous character activities
- **Active refactoring**: Message handler reduced 21% while adding features
- **Expanded capabilities**: Tools module +35%, utils +115%
- **Mature infrastructure**: 5-pillar data layer, 12 active characters, 4 LLM providers

The codebase demonstrates **healthy development patterns** with simultaneous feature addition and code cleanup, indicating sustainable growth and architecture maturation.

---

**Report Generated**: December 10, 2025 | **Repository**: whisperengine-v2 | **Branch**: feature/daily-life-graph-cleanup
