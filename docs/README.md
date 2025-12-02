# WhisperEngine v2 Documentation

> *"From countless conversations, a universe is born."*

Welcome to the WhisperEngine v2 documentation. This guide helps you navigate the various documents based on what you're trying to accomplish.

---

## 🚀 Quick Start

| I want to... | Read this |
|--------------|-----------|
| Understand the project vision | [WHISPERENGINE_2_DESIGN.md](./architecture/WHISPERENGINE_2_DESIGN.md) |
| See what's implemented vs planned | [IMPLEMENTATION_ROADMAP_OVERVIEW.md](./IMPLEMENTATION_ROADMAP_OVERVIEW.md) |
| Create a new character | [CREATING_NEW_CHARACTERS.md](./CREATING_NEW_CHARACTERS.md) |
| Deploy multiple bots | [MULTI_BOT_DEPLOYMENT.md](./MULTI_BOT_DEPLOYMENT.md) |
| Understand the philosophy | [MULTI_MODAL_PERCEPTION.md](./architecture/MULTI_MODAL_PERCEPTION.md) |

---

## 📁 Documentation Structure

```
docs/
├── README.md                          # You are here
├── IMPLEMENTATION_ROADMAP_OVERVIEW.md # Master roadmap & status
├── CREATING_NEW_CHARACTERS.md         # Character creation guide
├── MULTI_BOT_DEPLOYMENT.md            # Running multiple bots
├── PRIVACY_AND_DATA_SEGMENTATION.md   # Privacy model
├── API_REFERENCE.md                   # REST API documentation
│
├── architecture/                      # How the system works
│   ├── WHISPERENGINE_2_DESIGN.md      # Core design philosophy
│   ├── MULTI_MODAL_PERCEPTION.md      # 🧠 The "senses" of AI characters
│   ├── COGNITIVE_ENGINE.md            # Brain of the system
│   ├── MEMORY_SYSTEM_V2.md            # Vector + graph memory
│   ├── MESSAGE_FLOW.md                # Request lifecycle
│   ├── DATA_MODELS.md                 # Database schemas
│   ├── TRUST_EVOLUTION_SYSTEM.md      # Relationship progression
│   ├── DISCORD_INTEGRATION.md         # Discord as sensory interface
│   ├── VISION_PIPELINE.md             # Image processing
│   ├── SUMMARIZATION_SYSTEM.md        # Memory consolidation
│   └── ...
│
├── features/                          # Specific feature documentation
│   ├── KNOWLEDGE_GRAPH_MEMORY.md      # Neo4j fact storage
│   ├── TRUST_AND_EVOLUTION.md         # Trust system details
│   ├── USER_PREFERENCES.md            # Learning user preferences
│   ├── COMMON_GROUND.md               # Shared interest detection
│   └── ...
│
├── testing/                           # Test suite documentation
│   ├── REGRESSION_TESTING.md          # Automated API test suite
│   └── CHARACTERS.md                  # Character system & testing
│
├── roadmaps/                          # Future features & specs
│   ├── EMERGENT_UNIVERSE.md           # 🌌 Universe modality
│   ├── FEDERATED_MULTIVERSE.md        # 🌐 Multi-universe federation (DRAFT)
│   ├── CHANNEL_LURKING.md             # Passive engagement
│   ├── EMBEDDING_UPGRADE_768D.md      # Memory resolution upgrade
│   ├── RESPONSE_PATTERN_LEARNING.md   # RLHF-style learning
│   └── completed/                     # Historical roadmaps
│
└── origin/                            # V1 historical documents
```

---

## 🧠 Core Philosophy: Multi-Modal Input Processing

WhisperEngine v2 is built on a key insight: **AI characters have no physical senses**. They can't see, hear, or feel. Instead, they process input through six modalities:

| Modality | Human Analog | Implementation |
|----------|--------------|----------------|
| 🌌 **Universe** | Proprioception + Social awareness | Neo4j graph (planets, travelers) |
| 👁️ **Vision** | Sight | Multimodal LLM (GPT-4V, Claude) |
| 👂 **Audio** | Hearing | Whisper transcription |
| 💬 **Text** | Language | LLM processing |
| 🧠 **Memory** | Episodic + Semantic | Qdrant + Neo4j |
| ❤️ **Emotion** | Interoception | Trust scores, sentiment |

**Deep dive**: [MULTI_MODAL_PERCEPTION.md](./architecture/MULTI_MODAL_PERCEPTION.md)

---

## 🏗️ Architecture Documents

### Core System
| Document | Description |
|----------|-------------|
| [WHISPERENGINE_2_DESIGN.md](./architecture/WHISPERENGINE_2_DESIGN.md) | Core design philosophy, why polyglot persistence |
| [COGNITIVE_ENGINE.md](./architecture/COGNITIVE_ENGINE.md) | The "brain" - how responses are generated |
| [MESSAGE_FLOW.md](./architecture/MESSAGE_FLOW.md) | Complete request lifecycle |
| [DATA_MODELS.md](./architecture/DATA_MODELS.md) | Four Pillars database schemas |

### Memory & Knowledge
| Document | Description |
|----------|-------------|
| [MEMORY_SYSTEM_V2.md](./architecture/MEMORY_SYSTEM_V2.md) | Hybrid vector + graph memory |
| [SUMMARIZATION_SYSTEM.md](./architecture/SUMMARIZATION_SYSTEM.md) | Memory consolidation |
| [KNOWLEDGE_GRAPH_MEMORY.md](./features/KNOWLEDGE_GRAPH_MEMORY.md) | Neo4j fact storage |

### Character & Evolution
| Document | Description |
|----------|-------------|
| [TRUST_EVOLUTION_SYSTEM.md](./architecture/TRUST_EVOLUTION_SYSTEM.md) | Relationship progression |
| [CREATING_NEW_CHARACTERS.md](./CREATING_NEW_CHARACTERS.md) | Character creation guide |

### Integration
| Document | Description |
|----------|-------------|
| [DISCORD_INTEGRATION.md](./architecture/DISCORD_INTEGRATION.md) | Discord as sensory interface |
| [VISION_PIPELINE.md](./architecture/VISION_PIPELINE.md) | Image processing (Sight modality) |

---

## 🗺️ Roadmap Documents

### Active Development
| Document | Status | Description |
|----------|--------|-------------|
| [IMPLEMENTATION_ROADMAP_OVERVIEW.md](./IMPLEMENTATION_ROADMAP_OVERVIEW.md) | 📋 Master | Current status of all features |
| [EMBEDDING_UPGRADE_768D.md](./roadmaps/EMBEDDING_UPGRADE_768D.md) | 🔴 Critical | Memory resolution upgrade |
| [CHANNEL_LURKING.md](./roadmaps/CHANNEL_LURKING.md) | 🟡 Design | Passive engagement system |

### Future Vision
| Document | Status | Description |
|----------|--------|-------------|
| [EMERGENT_UNIVERSE.md](./roadmaps/EMERGENT_UNIVERSE.md) | 🟡 Design | Universe modality - spatial/social awareness |
| [FEDERATED_MULTIVERSE.md](./roadmaps/FEDERATED_MULTIVERSE.md) | ⚠️ Draft | Multi-universe federation protocol |
| [RESPONSE_PATTERN_LEARNING.md](./roadmaps/RESPONSE_PATTERN_LEARNING.md) | 🟡 Design | RLHF-style learning |

### Completed Phases
Historical roadmaps in [`roadmaps/completed/`](./roadmaps/completed/) document what was built in each development phase.

---

## 🔒 Privacy & Operations

| Document | Description |
|----------|-------------|
| [PRIVACY_AND_DATA_SEGMENTATION.md](./PRIVACY_AND_DATA_SEGMENTATION.md) | How user data is isolated |
| [MULTI_BOT_DEPLOYMENT.md](./MULTI_BOT_DEPLOYMENT.md) | Running multiple characters |
| [INFRASTRUCTURE_DEPLOYMENT.md](./architecture/INFRASTRUCTURE_DEPLOYMENT.md) | Docker, databases, scaling |

---

## 🧪 Testing

| Document | Description |
|----------|-------------|
| [REGRESSION_TESTING.md](./testing/REGRESSION_TESTING.md) | Automated API test suite, all options |
| [CHARACTERS.md](./testing/CHARACTERS.md) | Character system overview & testing |

### Quick Test Commands

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

---

## 🌌 The Grand Vision

WhisperEngine v2 isn't just a chatbot platform. It's building toward a **federated multiverse** where:

1. **Characters are persistent entities** with consistent behavior across six input modalities
2. **Each deployment is a universe** with its own characters, planets (Discord servers), and inhabitants (users)
3. **Universes can federate** to form a multiverse where characters travel and users explore
4. **No central authority** - peer-to-peer, like email or Mastodon

**Vision documents**:
- [MULTI_MODAL_PERCEPTION.md](./architecture/MULTI_MODAL_PERCEPTION.md) - How characters perceive
- [EMERGENT_UNIVERSE.md](./roadmaps/EMERGENT_UNIVERSE.md) - Spatial/social awareness
- [FEDERATED_MULTIVERSE.md](./roadmaps/FEDERATED_MULTIVERSE.md) - Multi-universe protocol (Draft)

---

## 📚 Reading Order for New Contributors

1. **Start here**: [WHISPERENGINE_2_DESIGN.md](./architecture/WHISPERENGINE_2_DESIGN.md) - Understand the "why"
2. **Philosophy**: [MULTI_MODAL_PERCEPTION.md](./architecture/MULTI_MODAL_PERCEPTION.md) - How characters process multi-modal input
3. **Status**: [IMPLEMENTATION_ROADMAP_OVERVIEW.md](./IMPLEMENTATION_ROADMAP_OVERVIEW.md) - What's built vs planned
4. **Deep dive**: Pick architecture docs based on what you're working on

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

## 📝 Document Conventions

- **🟢 Implemented**: Feature is complete and in production
- **🟡 Design**: Specification complete, not yet implemented
- **⚠️ Draft**: Vision document, subject to change
- **🔴 Critical**: High priority, do soon

Cross-references use relative paths: `[Doc](./path/to/doc.md)`

---

*Last updated: November 25, 2025*
