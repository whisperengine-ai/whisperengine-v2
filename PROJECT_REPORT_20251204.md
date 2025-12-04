# WhisperEngine v2 - Project Statistics Report
**Generated**: December 4, 2025

---

## 📊 Executive Summary

WhisperEngine v2 is a **production-grade multi-character Discord AI roleplay platform** with a sophisticated architecture spanning:
- **~35,591 lines of core Python code** (33% increase from previous report)
- **23 specialized modules** across agents, memory, knowledge, evolution, and more
- **~955MB total project size** (18% increase from previous report)
- **245 configuration, documentation, and data files** (20% increase from previous report)

---

## 📈 Codebase Metrics

### Overall Statistics
| Metric | Value | Change from Nov 29 |
|--------|-------|-------------------|
| **Total Python LOC** | 35,591 | +9,000 (+33%) |
| **Python Files** | 141 | +29 (+26%) |
| **Project Size** | 955MB | +149MB (+18%) |
| **Core Source Size** | 3.9MB | +1.1MB (+39%) |
| **Modules** | 23 | +3 |
| **Config/Docs/Data Files** | 245 | +41 (+20%) |

### Directory Breakdown

| Module | LOC | Change | Purpose |
|--------|-----|--------|---------|
| **agents** | 7,391 | +3,714 (+101%) | LLM engine, routing, proactive agents, graphs |
| **discord** | 4,981 | +947 (+23%) | Discord bot integration, commands, voice, scheduling |
| **memory** | 4,437 | +1,012 (+30%) | Vector memory (Qdrant), session management, dreams, diary |
| **knowledge** | 3,111 | +1,832 (+143%) | Knowledge graph (Neo4j) management, enrichment, pruning |
| **workers** | 3,269 | +746 (+30%) | Background task processing |
| **tools** | 1,941 | -274 (-12%) | Agent tools and utilities |
| **evolution** | 1,960 | +21 (+1%) | Character evolution, feedback, goals, trust, style |
| **universe** | 1,526 | +1 (0%) | Universe management and simulation |
| **broadcast** | 1,206 | +223 (+23%) | Broadcasting capabilities |
| **api** | 1,007 | +74 (+8%) | FastAPI routes and models |
| **core** | 1,006 | +101 (+11%) | Database, character loading |
| **intelligence** | 708 | +61 (+9%) | Reflection and activity analysis |
| **moderation** | 552 | +82 (+17%) | Content moderation |
| **utils** | 552 | +24 (+5%) | Helper utilities |
| **image_gen** | 483 | +5 (+1%) | Image generation services |
| **config** | 405 | +99 (+32%) | Settings and configuration management |
| **artifacts** | 391 | **NEW** | Artifact management system |
| **voice** | 250 | +6 (+2%) | Voice processing and integration |
| **safety** | 217 | 0 (0%) | Safety mechanisms |
| **vision** | 106 | +1 (+1%) | Image processing and vision capabilities |
| **scripts** | 26 | 0 (0%) | Utility scripts |
| **TOTAL** | **35,591** | **+8,991 (+33%)** | |

---

## 🏛️ Architecture Overview

### Core Modules

#### **Agents Module (7,391 LOC)** - **MAJOR EXPANSION**
- **engine.py** (1,327 LOC) - LLM engine with multi-model support
- **reflective_graph.py** (654 LOC) - Reflective agent logic with graph-based reasoning
- **strategist_graph.py** (636 LOC) - Strategic planning agent
- **conversation_agent.py** (531 LOC) - Conversation management
- **reflection_graph.py** (527 LOC) - Reflection processing graph

#### **Discord Module (4,981 LOC)**
- **handlers/message_handler.py** (2,033 LOC) - **NEW LARGEST FILE** - Main message processing
- **commands.py** (789 LOC) - User commands and interactions
- **lurk_detector.py** (666 LOC) - Lurker detection system

#### **Memory Module (4,437 LOC)**
- **manager.py** (1,126 LOC) - Qdrant vector memory orchestration
- **dreams.py** (1,106 LOC) - Dream memory management
- **diary.py** (1,037 LOC) - Diary entry management

#### **Knowledge Module (3,111 LOC)** - **SIGNIFICANT GROWTH**
- **manager.py** (992 LOC) - Neo4j knowledge graph management
- **walker.py** (696 LOC) - Graph traversal and analysis
- **enrichment.py** (617 LOC) - Knowledge enrichment processes
- **pruning.py** (504 LOC) - Knowledge pruning and optimization

#### **Workers Module (3,269 LOC)**
- Background task processing and queue management

#### **Broadcast Module (1,206 LOC)**
- **manager.py** (690 LOC) - Broadcasting capabilities
- **cross_bot.py** (506 LOC) - Cross-bot communication

---

## 🔝 Largest Files

| File | LOC | Module | Change |
|------|-----|--------|--------|
| src_v2/discord/handlers/message_handler.py | 2,033 | **NEW** - Discord Message Handler | - |
| src_v2/agents/engine.py | 1,327 | LLM Agent Engine | -162 |
| src_v2/memory/manager.py | 1,126 | Vector Memory | +140 |
| src_v2/memory/dreams.py | 1,106 | Dream Memory | +270 |
| src_v2/memory/diary.py | 1,037 | Diary Memory | +272 |
| src_v2/knowledge/manager.py | 992 | Knowledge Graph | +16 |
| src_v2/discord/commands.py | 789 | Discord Commands | +29 |
| src_v2/universe/manager.py | 776 | Universe Manager | 0 |
| src_v2/knowledge/walker.py | 696 | Knowledge Walker | **NEW** |
| src_v2/broadcast/manager.py | 690 | Broadcast Manager | **NEW** |

---

## 📁 Project Structure

```
whisperengine-v2/
├── src_v2/                  (3.9MB - Core Source)
│   ├── agents/              (7,391 LOC) - MAJOR EXPANSION
│   ├── api/                 (1,007 LOC)
│   ├── artifacts/           (391 LOC) - NEW MODULE
│   ├── broadcast/           (1,206 LOC) - EXPANDED
│   ├── config/              (405 LOC)
│   ├── core/                (1,006 LOC)
│   ├── discord/             (4,981 LOC)
│   │   └── handlers/        (2,033 LOC) - NEW SUBMODULE
│   ├── evolution/           (1,960 LOC)
│   ├── image_gen/           (483 LOC)
│   ├── intelligence/        (708 LOC)
│   ├── knowledge/           (3,111 LOC) - MAJOR EXPANSION
│   ├── memory/              (4,437 LOC)
│   ├── moderation/          (552 LOC)
│   ├── safety/              (217 LOC)
│   ├── tools/               (1,941 LOC)
│   ├── universe/            (1,526 LOC)
│   ├── utils/               (552 LOC)
│   ├── vision/              (106 LOC)
│   ├── voice/               (250 LOC)
│   ├── workers/             (3,269 LOC)
│   └── scripts/             (26 LOC)
├── tests_v2/                (Tests)
├── migrations_v2/           (DB Migrations)
├── characters/              (Character Definitions)
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

## 🚀 Entry Points

### Primary Entry Point
```bash
python run_v2.py <bot_name>
```
- Loads `.env.{bot_name}` configuration
- Initializes all database managers
- Starts Discord bot and FastAPI server

### Helper Scripts
- `bot.sh` - Docker management script
- `check_diary_nottaylor.py`
- `check_dreams_nottaylor.py`
- `check_qdrant.py`

### Character System
- Located in: `characters/{name}/`
- Files:
  - `character.md` - Personality, backstory, traits
  - `goals.yaml` - Evolution goals and learning objectives
  - `core.yaml` - Identity (purpose, drives, constitution)
  - `ux.yaml` - UX config (thinking indicators, response style)

---

## 💾 Database Migrations

**Location**: `migrations_v2/` (using Alembic)

Recent migrations include:
- Fix session ID types
- Add reminders table
- Add timezone to user relationships
- Add goal TTL and user goals
- Add user daily usage
- Add goal source priority strategy
- Add character profiles
- Add universe privacy
- Add channel lurking

---

## 📝 Configuration Files

**Count**: 245 files including `.md`, `.yaml`, `.json`, `.yml` (excluding logs/coverage)

Key files:
- `.env.example` - Environment template
- `.env.{bot_name}` - Character-specific configs
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
- ✅ **Path Handling**: Uses pathlib.Path for cross-platform compatibility
- ✅ **Database Versioning**: Proper migration management with Alembic
- ✅ **Massive Expansion**: Significant growth in Agents (101%), Knowledge (143%), and new Artifacts module

### Growth Areas
- **Large Files**: `message_handler.py` (2,033 LOC) is now the largest file, indicating potential need for further modularization
- **Complexity**: The rapid expansion in Agents and Knowledge modules adds significant architectural complexity
- **Documentation**: With continued rapid growth, maintaining comprehensive documentation is increasingly critical
- **Testing**: With 33% code growth, ensuring test coverage scales appropriately

---

## 📊 Complexity Analysis

### Module Complexity (by size)
1. **Agents Engine** (7,391 LOC) - **MOST COMPLEX** - **MAJOR EXPANSION**
   - Multi-model LLM support, routing, reflection, conversation management, graph-based reasoning

2. **Discord Integration** (4,981 LOC)
   - Event handling, routing, commands, lurk detection, message processing

3. **Memory System** (4,437 LOC)
   - Vector embeddings, session management, dreams, diary

4. **Knowledge Graph** (3,111 LOC) - **SIGNIFICANT GROWTH**
   - Neo4j management, enrichment, pruning, graph traversal

5. **Workers** (3,269 LOC)
   - Background processing infrastructure

---

## 📋 Summary

WhisperEngine v2 has experienced **significant growth** since the November 29 report, representing a **large-scale, production-grade AI platform** with:
- **33% increase in code volume** (from ~26.6k to ~35.6k LOC)
- **Expanded module set** (23 modules, +3 new)
- **Major feature expansions**: Agents module doubled in size, Knowledge module grew 143%, new Artifacts system
- **Architectural maturation**: Message handler refactoring, graph-based reasoning agents, knowledge enrichment
- **Robust infrastructure**: 5-pillar data layer with enhanced Redis task queues

The codebase demonstrates **aggressive feature development** while maintaining modular architecture, though the emergence of very large files and rapid complexity growth suggests a need for continued architectural review and potential refactoring initiatives.

---

**Report Generated**: December 4, 2025 | **Repository**: whisperengine-v2 | **Branch**: main