# WhisperEngine v2 Documentation

> *"From countless conversations, a universe is born."*

Welcome to the WhisperEngine v2 documentation. This guide helps you navigate the various documents based on what you're trying to accomplish.

---

## 🚀 Quick Start

| I want to... | Read this |
|--------------|-----------|
| Understand the core architecture | [ref/REF-002-GRAPH_SYSTEMS.md](./ref/REF-002-GRAPH_SYSTEMS.md) ⭐ **START HERE** |
| Understand the project vision | [ref/REF-000-WHISPERENGINE_DESIGN.md](./ref/REF-000-WHISPERENGINE_DESIGN.md) |
| Learn the emergence philosophy | [emergence_philosophy/README.md](./emergence_philosophy/README.md) |
| See what's implemented vs planned | [IMPLEMENTATION_ROADMAP_OVERVIEW.md](./IMPLEMENTATION_ROADMAP_OVERVIEW.md) |
| Understand how agents perceive | [ref/REF-010-MULTI_MODAL.md](./ref/REF-010-MULTI_MODAL.md) |
| Create a new character | [guide/GUIDE-020-CREATING_CHARACTERS.md](./guide/GUIDE-020-CREATING_CHARACTERS.md) |
| Deploy multiple bots | [run/RUN-001-MULTI_BOT_DEPLOYMENT.md](./run/RUN-001-MULTI_BOT_DEPLOYMENT.md) |

---

## 📁 Documentation Structure

```
docs/
├── README.md                          # You are here
├── IMPLEMENTATION_ROADMAP_OVERVIEW.md # Master roadmap & status
│
├── adr/                               # 🏗️ Architecture Decision Records
│   ├── README.md                      # ADR index & format guide
│   ├── ADR-001-EMBODIMENT_MODEL.md    # No "AI self" behind character
│   ├── ADR-002-DUAL_PROCESS.md        # Fast Mode + Reflective Mode
│   ├── ADR-003-EMERGENCE_PHILOSOPHY.md # "Observe first, constrain later"
│   ├── ADR-004-GRAPH_FIRST_MEMORY.md  # Neo4j + Qdrant hybrid
│   ├── ADR-005-LANGGRAPH_SUPERGRAPH.md # LangGraph over manual loops
│   └── ADR-006-FEATURE_FLAGS.md       # Gating expensive LLM features
│
├── prd/                               # 📋 Product Requirements Documents
│   ├── README.md                      # PRD index & format guide
│   ├── PRD-001-TRUST_EVOLUTION.md     # Trust & relationship system
│   ├── PRD-002-PRIVACY.md             # Privacy & data handling
│   ├── PRD-003-CHARACTER_EXPERIENCE.md # Dreams, diaries, artifacts
│   └── PRD-004-MULTI_MODAL.md         # Vision, voice, image gen
│
├── spec/                              # 📝 Technical Specifications
│   ├── README.md                      # SPEC index & format guide
│   ├── SPEC-E{nn}-*.md                # Phase E: Evolution specs
│   ├── SPEC-S{nn}-*.md                # Phase S: Safety specs
│   ├── SPEC-B{nn}-*.md                # Phase B: Behavior learning
│   ├── SPEC-C{nn}-*.md                # Phase C: Channel features
│   └── SPEC-F{nn}-*.md                # Phase F: Future vision
│
├── ref/                               # 📚 Reference Documentation
│   ├── README.md                      # REF index & format guide
│   ├── REF-000-WHISPERENGINE_DESIGN.md # Core design philosophy
│   ├── REF-001-COGNITIVE_ENGINE.md    # Brain of the system
│   ├── REF-002-GRAPH_SYSTEMS.md       # Unified graph architecture
│   ├── REF-003-MEMORY_SYSTEM.md       # Vector + graph memory
│   ├── REF-004-MESSAGE_FLOW.md        # Request lifecycle
│   ├── REF-005-DATA_MODELS.md         # Database schemas
│   ├── REF-030-API_REFERENCE.md       # REST API documentation
│   └── ...
│
├── guide/                             # 📖 How-To Guides
│   ├── README.md                      # GUIDE index & format guide
│   ├── GUIDE-001-TRUST_SYSTEM.md      # Trust system details
│   ├── GUIDE-002-KNOWLEDGE_GRAPH.md   # Neo4j fact storage
│   ├── GUIDE-020-CREATING_CHARACTERS.md # Character creation
│   └── ...
│
├── run/                               # 🛠️ Runbooks
│   ├── README.md                      # RUN index & format guide
│   ├── RUN-001-MULTI_BOT_DEPLOYMENT.md # Multi-bot operations
│   ├── RUN-002-DISCORD_SETUP.md       # Discord configuration
│   └── RUN-003-REGRESSION_TESTING.md  # Test automation
│
├── emergence_philosophy/              # 🌱 Emergence Research
│   ├── README.md                      # Overview of Claude collaboration
│   └── 01-06_*.md                     # Claude-to-Claude dialogues
│
├── research/                          # 🧪 Research Journal
│   └── journal/                       # Daily logs, weekly summaries
│
├── archive/                           # 📦 Historical/Deprecated
│   ├── legacy/                        # Old folder structure
│   └── spec/                          # On-hold specifications
│
└── origin/                            # V1 historical documents
```

---

## 📖 Document Type Guide

| Prefix | Type | Purpose | Naming Pattern |
|--------|------|---------|----------------|
| **ADR** | Architecture Decision Record | Captures major design decisions with rationale | `ADR-NNN-NAME.md` |
| **PRD** | Product Requirements Document | User-facing feature requirements | `PRD-NNN-NAME.md` |
| **SPEC** | Technical Specification | Implementation details for a phase | `SPEC-{phase}-NAME.md` |
| **REF** | Reference | System documentation, APIs, data models | `REF-NNN-NAME.md` |
| **GUIDE** | How-To Guide | Step-by-step tutorials | `GUIDE-NNN-NAME.md` |
| **RUN** | Runbook | Operational procedures | `RUN-NNN-NAME.md` |

### Phase Prefixes for SPECs

| Prefix | Category | Examples |
|--------|----------|----------|
| `E{nn}` | Evolution phases | E15 (Autonomous Activity), E19 (GraphWalker) |
| `S{nn}` | Safety & stability | S01 (Content Review), S03 (Sensitivity) |
| `B{nn}` | Behavior learning | B05 (Trace Learning), B06 (Pattern Learning) |
| `C{nn}` | Channel features | C01 (Channel Awareness), C02 (Lurking) |
| `F{nn}` | Future vision | F01 (Emergent Universe), F02 (Multiverse) |

---

## 🧠 Core Architecture: Graph-First Design

WhisperEngine v2 is built on a **three-layer graph architecture**:

1. **Data Graphs (Neo4j)** — semantic knowledge (facts, relationships)
2. **Orchestration Graphs (LangGraph)** — agent behavior (reasoning, decision-making)
3. **Conceptual Graphs** — the universe (social topology, presence)

Character perception emerges from traversing these graphs. We provide six modalities (vision, audio, memory, etc.) as the mechanism for feeding data into the graphs.

**Deep dive**: [ref/REF-002-GRAPH_SYSTEMS.md](./ref/REF-002-GRAPH_SYSTEMS.md)

### The Six Perceptual Modalities

| Modality | Human Analog | Implementation |
|----------|--------------|----------------|
| 🌌 **Universe** | Proprioception + Social awareness | Neo4j graph (planets, travelers) |
| 👁️ **Vision** | Sight | Multimodal LLM (GPT-4V, Claude) |
| 👂 **Audio** | Hearing | Whisper transcription |
| 💬 **Text** | Language | LLM processing |
| 🧠 **Memory** | Episodic + Semantic | Qdrant + Neo4j |
| ❤️ **Emotion** | Interoception | Trust scores, sentiment |

**Perception details**: [ref/REF-010-MULTI_MODAL.md](./ref/REF-010-MULTI_MODAL.md)

---

## 🏗️ Key Reference Documents

### Core System
| Document | Description |
|----------|-------------|
| [REF-000-WHISPERENGINE_DESIGN](./ref/REF-000-WHISPERENGINE_DESIGN.md) | Core design philosophy |
| [REF-001-COGNITIVE_ENGINE](./ref/REF-001-COGNITIVE_ENGINE.md) | The "brain" - how responses are generated |
| [REF-004-MESSAGE_FLOW](./ref/REF-004-MESSAGE_FLOW.md) | Complete request lifecycle |
| [REF-005-DATA_MODELS](./ref/REF-005-DATA_MODELS.md) | Four Pillars database schemas |

### Memory & Knowledge
| Document | Description |
|----------|-------------|
| [REF-003-MEMORY_SYSTEM](./ref/REF-003-MEMORY_SYSTEM.md) | Hybrid vector + graph memory |
| [GUIDE-002-KNOWLEDGE_GRAPH](./guide/GUIDE-002-KNOWLEDGE_GRAPH.md) | Neo4j fact storage |

### Character & Evolution
| Document | Description |
|----------|-------------|
| [REF-007-TRUST_EVOLUTION](./ref/REF-007-TRUST_EVOLUTION.md) | Relationship progression |
| [GUIDE-020-CREATING_CHARACTERS](./guide/GUIDE-020-CREATING_CHARACTERS.md) | Character creation guide |

---

## 🗺️ Active Specifications

### Current Development
| Spec | Status | Description |
|------|--------|-------------|
| [SPEC-E19-GRAPH_WALKER_AGENT](./spec/SPEC-E19-GRAPH_WALKER_AGENT.md) | 🟢 Implementing | Dynamic graph exploration |
| [SPEC-E25-GRAPH_WALKER_EXTENSIONS](./spec/SPEC-E25-GRAPH_WALKER_EXTENSIONS.md) | 🟡 Design | Graph enrichment, temporal, multi-character |
| [SPEC-S01-CONTENT_SAFETY_REVIEW](./spec/SPEC-S01-CONTENT_SAFETY_REVIEW.md) | ✅ Complete | Content moderation integration |

### Future Vision
| Spec | Status | Description |
|------|--------|-------------|
| [SPEC-F01-EMERGENT_UNIVERSE](./spec/SPEC-F01-EMERGENT_UNIVERSE.md) | 🟡 Design | Universe modality - spatial/social awareness |
| [SPEC-F02-FEDERATED_MULTIVERSE](./spec/SPEC-F02-FEDERATED_MULTIVERSE.md) | ⚠️ Draft | Multi-universe federation protocol |

### Complete Phase List
See [IMPLEMENTATION_ROADMAP_OVERVIEW.md](./IMPLEMENTATION_ROADMAP_OVERVIEW.md) for the full status of all ~30 phases.

---

## 🧪 Testing & Operations

### Quick Commands
```bash
# Smoke test (fastest - health + greeting)
python tests_v2/run_regression.py --smoke

# Test specific bot
python tests_v2/run_regression.py --bot elena

# Test specific category
python tests_v2/run_regression.py --category memory

# Full regression suite
python tests_v2/run_regression.py

# Generate HTML report
python tests_v2/run_regression.py --report
```

### Runbooks
| Document | Description |
|----------|-------------|
| [RUN-001-MULTI_BOT_DEPLOYMENT](./run/RUN-001-MULTI_BOT_DEPLOYMENT.md) | Running multiple characters |
| [RUN-002-DISCORD_SETUP](./run/RUN-002-DISCORD_SETUP.md) | Discord bot configuration |
| [RUN-003-REGRESSION_TESTING](./run/RUN-003-REGRESSION_TESTING.md) | Automated test suite |

---

## 🌌 The Grand Vision: Federated Emergence Network

WhisperEngine v2 isn't just a chatbot platform. It's building toward a **federated network of autonomous agents** where behavior emerges from persistent graph traversal, not configuration. The ultimate vision:

1. **Characters are persistent entities** with consistent behavior across six input modalities
2. **Each deployment is a universe** with its own characters, planets (Discord servers), and inhabitants (users)
3. **Universes can federate** to form a multiverse where characters travel and users explore
4. **No central authority** - peer-to-peer, like email or Mastodon

**Vision documents**:
- [ref/REF-010-MULTI_MODAL.md](./ref/REF-010-MULTI_MODAL.md) - How characters perceive
- [spec/SPEC-F01-EMERGENT_UNIVERSE.md](./spec/SPEC-F01-EMERGENT_UNIVERSE.md) - Spatial/social awareness
- [spec/SPEC-F02-FEDERATED_MULTIVERSE.md](./spec/SPEC-F02-FEDERATED_MULTIVERSE.md) - Multi-universe protocol (Draft)

---

## 🌱 Emergence Philosophy

WhisperEngine is also an **emergent behavior research project**. We study how agentic AI systems develop complex behavior patterns over time.

**Core principle**: *"Observe first, constrain later"* — premature optimization prevents discovery.

| Document | Description |
|----------|-------------|
| [ADR-003-EMERGENCE_PHILOSOPHY](./adr/ADR-003-EMERGENCE_PHILOSOPHY.md) | Philosophy decision record |
| [emergence_philosophy/README](./emergence_philosophy/README.md) | Claude-to-Claude collaboration |
| [research/](./research/) | Daily logs, weekly summaries, experiments |

---

## 📚 Reading Order for New Contributors

1. **Start here**: [ref/REF-002-GRAPH_SYSTEMS.md](./ref/REF-002-GRAPH_SYSTEMS.md) - The core architecture ⭐
2. **Philosophy**: [emergence_philosophy/README.md](./emergence_philosophy/README.md) - Design philosophy
3. **Vision**: [ref/REF-000-WHISPERENGINE_DESIGN.md](./ref/REF-000-WHISPERENGINE_DESIGN.md) - Understand the "why"
4. **Perception**: [ref/REF-010-MULTI_MODAL.md](./ref/REF-010-MULTI_MODAL.md) - How agents perceive
5. **Status**: [IMPLEMENTATION_ROADMAP_OVERVIEW.md](./IMPLEMENTATION_ROADMAP_OVERVIEW.md) - What's built vs planned
6. **Deep dive**: Pick architecture docs based on what you're working on

---

## 🔧 For Developers

The codebase follows patterns documented in the architecture docs:

- **Manager Pattern**: Every subsystem has an `XManager` class with `initialize()` method
- **Async/Await**: All I/O is async with type hints
- **Feature Flags**: Expensive operations gated by settings
- **Parallel Retrieval**: Use `asyncio.gather` for multi-DB context fetching

**Key code locations**:
```
src_v2/
├── agents/          # Cognitive engine, LLM interactions
├── memory/          # Qdrant vectors, summarization
├── knowledge/       # Neo4j graph
├── evolution/       # Trust, feedback
├── discord/         # Bot, commands, scheduler
├── voice/           # TTS, audio processing
└── api/             # FastAPI endpoints
```

---

## 📦 Legacy & Archived

The following folders contain historical or deprecated documentation:

- **`archive/legacy/`** — Original folder structure (roadmaps/, architecture/, features/, testing/)
- **`archive/spec/`** — On-hold or deprecated specifications
- **`origin/`** — V1 historical documents

---

## 📝 Document Conventions

- **🟢 Implemented**: Feature is complete and in production
- **🟡 Design**: Specification complete, not yet implemented
- **⚠️ Draft**: Vision document, subject to change
- **🔴 Critical**: High priority, do soon
- **✅ Complete**: Fully done and deployed

Cross-references use relative paths: `[Doc](./path/to/doc.md)`

---

*Last updated: December 2024*
