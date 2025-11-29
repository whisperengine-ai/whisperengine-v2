# WhisperEngine v2 - Project Statistics Report
**Generated**: November 29, 2025

---

## 📊 Executive Summary

WhisperEngine v2 is a **production-grade multi-character Discord AI roleplay platform** with a sophisticated architecture spanning:
- **~26,600 lines of core Python code**
- **20 specialized modules** across agents, memory, knowledge, evolution, and more
- **~806MB total project size** (primarily containing virtual environment and dependencies)
- **204 configuration, documentation, and data files** (excluding logs and coverage)

---

## 📈 Codebase Metrics

### Overall Statistics
| Metric | Value |
|--------|-------|
| **Total Python LOC** | 26,600 |
| **Python Files** | 112 |
| **Project Size** | 806MB |
| **Core Source Size** | 2.8MB |
| **Modules** | 20 |
| **Config/Docs/Data Files** | 204 |

### Directory Breakdown

| Module | LOC | Purpose |
|--------|-----|---------|
| **discord** | 4,034 | Discord bot integration, commands, voice, scheduling |
| **agents** | 3,677 | LLM engine, routing, proactive agents |
| **memory** | 3,425 | Vector memory (Qdrant), session management, dreams, diary |
| **workers** | 2,523 | Background task processing |
| **tools** | 2,215 | Agent tools and utilities |
| **evolution** | 1,939 | Character evolution, feedback, goals, trust, style |
| **universe** | 1,525 | Universe management and simulation |
| **knowledge** | 1,279 | Knowledge graph (Neo4j) management |
| **broadcast** | 983 | Broadcasting capabilities |
| **api** | 933 | FastAPI routes and models |
| **core** | 905 | Database, character loading |
| **intelligence** | 647 | Reflection and activity analysis |
| **utils** | 528 | Helper utilities |
| **image_gen** | 478 | Image generation services |
| **moderation** | 470 | Content moderation |
| **config** | 306 | Settings and configuration management |
| **voice** | 244 | Voice processing and integration |
| **safety** | 217 | Safety mechanisms |
| **vision** | 105 | Image processing and vision capabilities |
| **scripts** | 26 | Utility scripts |
| **TOTAL** | **26,600** | |

---

## 🏛️ Architecture Overview

### Core Modules

#### **Discord Module (4,034 LOC)**
- **bot.py** (2,085 LOC) - Main Discord bot implementation, message handling, event dispatch
- **commands.py** (760 LOC) - User commands and interactions
- **lurk_detector.py** (666 LOC) - Lurker detection system

#### **Agents Module (3,677 LOC)**
- **engine.py** (1,489 LOC) - LLM engine with multi-model support
- **reflective.py** (534 LOC) - Reflective agent logic
- **dreamweaver.py** (424 LOC) - Dream generation agent

#### **Memory Module (3,425 LOC)**
- **manager.py** (986 LOC) - Qdrant vector memory orchestration
- **dreams.py** (836 LOC) - Dream memory management
- **diary.py** (765 LOC) - Diary entry management

#### **Workers Module (2,523 LOC)**
- Background task processing and queue management

#### **Tools Module (2,215 LOC)**
- **dreamweaver_tools.py** (815 LOC) - Tools for dream generation
- **memory_tools.py** (529 LOC) - Tools for memory interaction

#### **Evolution Module (1,939 LOC)**
- Character evolution, feedback, goals, trust, and style adaptation

#### **Universe Module (1,525 LOC)**
- **manager.py** (776 LOC) - Universe state management

#### **Knowledge Module (1,279 LOC)**
- **manager.py** (976 LOC) - Neo4j knowledge graph management

---

## 🔝 Largest Files

| File | LOC | Module |
|------|-----|--------|
| src_v2/discord/bot.py | 2,085 | Discord Bot Core |
| src_v2/agents/engine.py | 1,489 | LLM Agent Engine |
| src_v2/memory/manager.py | 986 | Vector Memory |
| src_v2/knowledge/manager.py | 976 | Knowledge Graph |
| src_v2/memory/dreams.py | 836 | Dream Memory |
| src_v2/tools/dreamweaver_tools.py | 815 | Dream Tools |
| src_v2/universe/manager.py | 776 | Universe Manager |
| src_v2/memory/diary.py | 765 | Diary Memory |
| src_v2/discord/commands.py | 760 | Discord Commands |
| src_v2/discord/lurk_detector.py | 666 | Lurk Detector |

---

## 📁 Project Structure

```
whisperengine-v2/
├── src_v2/                  (2.8MB - Core Source)
│   ├── agents/              (3,677 LOC)
│   ├── api/                 (933 LOC)
│   ├── broadcast/           (983 LOC)
│   ├── config/              (306 LOC)
│   ├── core/                (905 LOC)
│   ├── discord/             (4,034 LOC)
│   ├── evolution/           (1,939 LOC)
│   ├── image_gen/           (478 LOC)
│   ├── intelligence/        (647 LOC)
│   ├── knowledge/           (1,279 LOC)
│   ├── memory/              (3,425 LOC)
│   ├── moderation/          (470 LOC)
│   ├── safety/              (217 LOC)
│   ├── tools/               (2,215 LOC)
│   ├── universe/            (1,525 LOC)
│   ├── utils/               (528 LOC)
│   ├── vision/              (105 LOC)
│   ├── voice/               (244 LOC)
│   ├── workers/             (2,523 LOC)
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
   - Relational data, CDL storage, user preferences
   
2. **Qdrant** (Port 6333)
   - Vector memory with 384D embeddings
   - Semantic conversation retrieval
   
3. **Neo4j** (Port 7687)
   - Knowledge graph for entity relationships
   - Fact storage and querying
   
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
- Add reminders table
- Add timezone to user relationships
- Add goal TTL and user goals
- Add user daily usage

---

## 📝 Configuration Files

**Count**: 204 files including `.md`, `.yaml`, `.json`, `.yml` (excluding logs/coverage)

Key files:
- `.env.example` - Environment template
- `.env.{bot_name}` - Character-specific configs
- `pyproject.toml` - Python project metadata
- `docker-compose.yml` - Infrastructure orchestration
- `alembic_v2.ini` - Database migration config

---

## 🎯 Code Quality Observations

### Strengths
- ✅ **Modular Architecture**: Clear separation of concerns across 20 modules
- ✅ **Async-First Design**: Built on async/await for I/O operations
- ✅ **Type Safety**: Uses Pydantic for data validation
- ✅ **Proper Logging**: Utilizes loguru for structured logging
- ✅ **Path Handling**: Uses pathlib.Path for cross-platform compatibility
- ✅ **Database Versioning**: Proper migration management with Alembic
- ✅ **Expanded Capabilities**: Significant growth in Memory (Dreams, Diary), Universe, and Workers modules

### Growth Areas
- **Large Files**: `bot.py` (2,085 LOC) and `engine.py` (1,489 LOC) have grown significantly and may benefit from further refactoring.
- **Complexity**: The addition of Universe, Dreams, and Workers adds significant complexity to the system.
- **Documentation**: With the rapid growth in LOC, ensuring documentation keeps up is critical.

---

## 📊 Complexity Analysis

### Module Complexity (by size)
1. **Discord Integration** (4,034 LOC) - Most Complex
   - Event handling, routing, commands, lurk detection
   
2. **Agents Engine** (3,677 LOC)
   - Multi-model LLM support, routing, reflection, dreamweaver

3. **Memory System** (3,425 LOC)
   - Vector embeddings, session management, dreams, diary

4. **Workers** (2,523 LOC)
   - Background processing infrastructure

5. **Tools** (2,215 LOC)
   - Extensive toolset for agents

---

## 📋 Summary

WhisperEngine v2 has grown significantly since the last report, now representing a **large-scale, production-grade AI platform** with:
- **6x increase in code volume** (from ~4.4k to ~26.6k LOC)
- **Expanded module set** (20 modules)
- **Sophisticated new features**: Dreams, Diary, Universe simulation, Broadcasting, and extensive Background Workers.
- **Robust infrastructure**: 5-pillar data layer including Redis for task queues.

The codebase demonstrates rapid feature expansion while maintaining a modular architecture, though the increasing size of core files suggests a need for continued refactoring and maintenance focus.

---

**Report Generated**: November 29, 2025 | **Repository**: whisperengine-v2 | **Branch**: main
