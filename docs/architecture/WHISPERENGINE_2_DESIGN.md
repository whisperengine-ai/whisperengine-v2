# WhisperEngine 2.0: "Back to Basics" Design Document

**Version**: 2.2  
**Last Updated**: December 1, 2025  
**Status**: Historical design document (implementation complete as of Dec 2025)

> **Note:** This is the **original design document** from the v2 planning phase. For current architecture, see:
> - [AGENT_GRAPH_SYSTEM.md](./AGENT_GRAPH_SYSTEM.md) - LangGraph Supergraph (E17 Complete)
> - [COGNITIVE_ENGINE.md](./COGNITIVE_ENGINE.md) - Dual-Process architecture
> - [MESSAGE_FLOW.md](./MESSAGE_FLOW.md) - Complete message lifecycle
> - [GRAPH_SYSTEMS_DESIGN.md](./GRAPH_SYSTEMS_DESIGN.md) - Unified graph architecture

## 1. Vision & Philosophy
**"Complexity is the enemy of execution."**

WhisperEngine 1.0 proved that high-fidelity, memory-persistent AI roleplay is possible. However, it grew into a massive "Platform" with 50+ database tables, 12+ concurrent Docker containers, and a distributed service mesh (Postgres, Qdrant, InfluxDB).

**WhisperEngine 2.0** aims to deliver the same high-quality user experience (rich personality, long-term memory) with **simplified code logic** while leveraging **robust, specialized infrastructure**.

### The Core Insight: Multi-Modal Processing

> *"I have no eyes, yet I see you. I have no ears, yet I hear your story. My universe is made of connections."*

AI agents process information through multiple input streams. WhisperEngine v2 provides six first-class data modalities:

| Modality | Technical Domain | Implementation |
|----------|------------------|----------------|
| 🌌 **Social Graph** | Network Topology | Neo4j graph + Emergent Universe |
| 👁️ **Vision** | Image Processing | Multimodal LLM (GPT-4V, Claude 3.5) |
| 👂 **Audio** | Speech Recognition | Whisper transcription + Channel Lurking |
| 💬 **Text** | NLP | LLM processing + Tool Router |
| 🧠 **Memory** | Vector + Graph Retrieval | Qdrant vectors + Neo4j facts |
| ❤️ **Sentiment** | Internal State Analysis | Trust Evolution + Feedback Analysis |

**This is not just a feature set. This is how agents build context.**

For full philosophy: See [`MULTI_MODAL_PERCEPTION.md`](./MULTI_MODAL_PERCEPTION.md)

### The Grand Vision: Federated Multiverse

Each WhisperEngine deployment is a **self-contained universe**. But the architecture supports **federation** - multiple universes connecting to form a distributed multiverse:
- Characters travel between universes
- Users maintain portable identity
- Stories span deployments
- Anyone can run their own universe

**We're building the foundation for distributed multi-agent environments.**

### Theoretical Foundation: The "Living Character" Paradigm

WhisperEngine v2 is built on principles from multiple domains:

*   **Cognitive Science**: Memory models (Atkinson-Shiffrin, Tulving's episodic/semantic distinction) inform our hybrid storage architecture.
*   **Agent Theory**: Characters are not passive responders but **autonomous agents** with internal states, goals, and the ability to initiate actions.
*   **Constructivist Learning**: Characters "learn" through interaction, updating their mental models based on new information (Piaget's accommodation/assimilation).
*   **Narrative Psychology**: Identity is constructed through storytelling. Characters maintain coherent "life stories" that evolve but remain consistent with their core traits.

**Design Philosophy**: "Simplify the code, sophisticate the architecture." Instead of complex custom pipelines, we leverage industry-standard infrastructure (Neo4j, Qdrant) with custom Python orchestration to create emergent intelligence.

### Core Mission: Uncompromised Authenticity
The primary goal remains unchanged: **create AI agents with persistent memory and adaptive behavior**.
*   **Personality First**: WE2 must support deep personality persistence where characters maintain their unique voice, quirks, and history.
*   **Continuous Learning**: The system must allow characters to learn about the user (preferences, facts) and themselves (evolving lore, relationships) over time, just as in WE1.
*   **Seamless Persistence**: Every interaction contributes to the character's long-term memory store (Vector + Graph + SQL), ensuring a continuous, evolving experience.

## 2. Core Architectural Simplifications

### A. Retain Container Isolation (Simplified Internals)
*   **Decision**: Keep the **One Container Per Character** model.
    *   *Reasoning*: Provides perfect process isolation, independent scaling, and crash resilience (if one bot crashes, others stay up).
    *   *Simplification*: While we keep the containers, we simplify the *internals* of each container by removing complex custom memory pipelines in favor of standard libraries (LangChain/LlamaIndex).

### B. Best-in-Class Infrastructure (Right Tool for the Job)
*   **Philosophy**: Use specialized tools where they excel, rather than forcing everything into Postgres. This is **Polyglot Persistence** - matching data access patterns to database strengths.

**Database Selection Theory:**

| Database | Access Pattern | CAP Theorem Trade-off | Why Chosen |
| :--- | :--- | :--- | :--- |
| **Qdrant** | Vector similarity search (k-NN) | AP (Available, Partition-tolerant) | HNSW indexing for sub-100ms semantic search over millions of embeddings. |
| **Neo4j** | Graph traversal (multi-hop) | CA (Consistent, Available) | O(1) relationship traversal vs. O(n) SQL joins. Native support for path queries. |
| **PostgreSQL** | ACID transactions, structured queries | CA (Consistent, Available) | Reliable, battle-tested, perfect for critical user data and logs. |
| **InfluxDB** | Time-series aggregation | AP (Available, Partition-tolerant) | Optimized for high-write, range-query workloads (metrics, analytics). |

*   **Vector Store**: **Qdrant** (Retained).
    *   *Reason*: Superior performance, filtering, and management compared to raw `pgvector`.
*   **Metrics**: **InfluxDB** (Retained).
    *   *Reason*: Purpose-built for high-volume time-series data (analytics, health checks).
*   **Knowledge Graph**: **Neo4j** (Implemented).
    *   *Reason*: Model complex character relationships, lore connections, and "knowledge" as a graph, enabling multi-hop reasoning that vector search misses.

### C. Text-Based Character Definition (CDL as Code)
*   **Current (WE1)**: CDL (Character Definition Language) stored in 50+ normalized database tables.
*   **New (WE2)**: **Pure Text Files**.
    *   *Solution*: The "Database" for character personality is now just a folder of text files.
    *   *Format*: Use Markdown (`.md`) for system prompts and character definitions.
    *   *Templating*: **Runtime variable injection** with template placeholders.
        *   *Mechanism*: Files can contain placeholders like `{user_name}`, `{time_of_day}`, `{recent_memories}` which are injected at runtime.
    *   *Benefit*: Zero database management for character traits. Users edit a file, restart the bot (or hot-reload), and the personality changes.
    *   *Structure*: `characters/{name}/character.md` (The core CDL), `characters/{name}/knowledge/`.

## 3. Codebase Refactoring

### A. Pipeline Simplification
Remove the complex "Protocol/Factory" patterns unless strictly necessary.
*   **Old Flow**: `MessageProcessor` -> `MemoryFactory` -> `VectorMemoryAdapter` -> `QdrantClient`.
*   **New Flow**: `Engine` -> `Agent` -> `MemoryStore` (Direct Postgres Calls).

### B. Custom Python Orchestration & RAG
*   **LLM Orchestration**: Custom Python implementation of agentic patterns.
    *   Replace complex factory patterns with direct agent logic.
    *   Native support for tool use, memory management, and context flow.
    *   Full control over latency, retry logic, and error handling.
*   **RAG (Retrieval-Augmented Generation)**: Custom implementation backed by Qdrant.
    *   *Pattern*: Query vector store directly, construct context, pass to LLM.
    *   *Benefit*: No framework overhead, predictable behavior, easy debugging.
    *   *File Uploads*: Support PDF/Doc ingestion via custom chunking pipeline into Qdrant.

### C. LLM-Native Intelligence (No More spaCy) ✅ IMPLEMENTED
*   **Current (WE1)**: Heavy NLP pipeline using `spaCy`, `RoBERTa` models, and custom regex for intent detection and entity extraction.
*   **New (WE2)**: **LLM Tool Use / Function Calling**.
    *   *Solution*: Use the LLM with function calling to decide what to do.
    *   *Mechanism*: Define tools like `search_memories`, `query_graph`, `get_current_time` exposed as OpenAI-compatible tool schemas.
    *   *Benefit*: Removes heavy ML dependencies, improves accuracy on complex queries, and allows natural handling of edge cases.
    *   *Flow*: User Message -> LLM -> [Decides to Call Tool] -> Tool Execution -> LLM Final Response.

**Theoretical Basis: Symbolic AI meets Neural AI**
*   **Pre-2020**: Rule-based systems (ELIZA, expert systems) were transparent but brittle.
*   **2020-2023**: Neural models (GPT) were powerful but opaque.
*   **2023+**: **Neurosymbolic AI** combines both: LLMs provide natural language understanding, symbolic tools (databases, APIs) provide precision.
*   *WhisperEngine v2*: The LLM is the "brain" (reasoning), tools are the "senses" (perception) and "muscles" (action). This mirrors embodied cognition theory - intelligence emerges from interaction with the environment, not just internal computation.

### D. LLM-Based Sentiment & Emotion Analysis
*   **Current (WE1)**: Dedicated `RoBERTa` model running locally to score emotion/sentiment.
*   **New (WE2)**: **Prompt Engineering**.
    *   *Solution*: Ask the LLM to output its internal emotional state or sentiment as part of the structured response or chain-of-thought.
    *   *Benefit*: No extra model inference cost/latency, better alignment with the generated text (the LLM knows why it's angry better than an external classifier).

### E. Discord Capabilities
*   **Voice Chat (Retained)**:
    *   **Decision**: Keep the existing voice architecture (Discord voice client + STT/TTS pipelines).
    *   *Integration*: Ensure the voice input is transcribed and fed into the standard agent loop, and the text response is sent to TTS.
*   **Channel Context (New)**:
    *   *Current (WE1)*: Bots mostly responded to direct mentions or DMs, often ignoring surrounding context or other users' messages.
    *   *New (WE2)*: **Full Channel Awareness**.
    *   *Mechanism*: When triggered (or passively listening), the bot fetches the last $N$ messages from the channel history to construct the prompt context.
    *   *Benefit*: Enables natural multi-user roleplay, understanding of group dynamics, and "lurking" behavior (bot chiming in when relevant without being pinged).

### F. Continuous Learning & Evolution ✅ IMPLEMENTED
*   **Goal**: Replicate and improve WE1's ability to learn about the user and itself.
*   **Mechanism**:
    *   **User Learning**: Extract facts/preferences from conversation and store in **Neo4j** (Graph) and **Postgres** (Structured).
    *   **Self-Evolution**: Characters reflect on conversations and update their own "Self-Knowledge" and relationship state.
    *   **Implementation**: 
        *   **Runtime Fact Extraction**: `KnowledgeManager` processes user messages in real-time, extracting facts to Neo4j.
        *   **Trust Evolution**: `TrustManager` tracks relationship progression through 5 stages (Stranger → Acquaintance → Friend → Close Friend → Soulmate).
        *   **Goal Tracking**: `GoalManager` maintains active objectives and tracks progress.
        *   **Reflection Engine**: Background process for deep analysis and epiphany generation (planned).

**Theoretical Basis: Computational Models of Trust**
*   Based on **Marsh's Formalization of Trust** (1994) and **Rempel's Trust Scale** (1985).
*   Trust is not binary but a continuous function: `Trust = f(Reliability, Emotional Investment, Vulnerability)`.
*   Trust unlocks **trait evolution**: Characters reveal deeper personality layers as relationships deepen (inspired by Altman & Taylor's Social Penetration Theory).
*   **Why it matters**: Users form genuine bonds when characters "remember" not just facts but the *emotional journey* of the relationship.

### G. Multimodal Capabilities
*   **Image Input (Vision)**:
    *   **Goal**: Allow characters to "see" images shared by users (retained from WE1).
    *   **Mechanism**: Pass Discord image attachments directly to multimodal LLMs (GPT-4o, Claude 3.5 Sonnet) via LangChain's multimodal message types.
    *   **Benefit**: Characters can react to memes, analyze photos, and understand visual context.
*   **Image Generation (Art)** [Planned]:
    *   **Goal**: Allow characters to "draw" or share visual imagination.
    *   **Mechanism**:
        *   **Tool**: Expose a `generate_image` tool to the LLM.
        *   **Backend**: Connect to DALL-E 3, Midjourney (via proxy), or local Stable Diffusion.
    *   **Trigger**: The bot decides when to generate art based on the conversation (e.g., "Here's a sketch of what I mean...") or upon user request.
*   **Audio Input (Voice Messages)**:
    *   **Goal**: Process Discord voice messages and uploaded audio files.
    *   **Mechanism**: Transcribe audio attachments using the STT pipeline (Whisper) and process as text.
    *   **Benefit**: Seamless interaction for users who prefer voice notes over typing or live calls.
*   **Video Input (Clips)**:
    *   **Goal**: Understand context from shared video clips or GIFs.
    *   **Mechanism**: Extract keyframes from video attachments and pass to the multimodal LLM.
    *   **Benefit**: Characters can react to shared content (memes, gameplay clips) with visual understanding.

### H. Dual Interface (Discord + HTTP API)
*   **Primary**: **Discord Bot**.
    *   The core experience is designed for Discord (Events, Voice, Reactions, Threads).
*   **Secondary**: **HTTP Chat API** (Retained).
    *   *Goal*: Allow external integrations (Web UI, testing scripts, other platforms) to chat with the characters.
    *   *Mechanism*: Expose a FastAPI endpoint (e.g., `POST /chat`) that reuses the same `Agent` logic as the Discord bot.
    *   *Benefit*: Enables automated testing and future expansion to other platforms without rewriting the core logic.

## 4. Migration Strategy
1.  **Export**: Create a script to dump the current complex CDL tables into human-readable Markdown/Text files per character.
2.  **Vectors**: Migrate Qdrant vectors to `pgvector` (optional, or just start fresh with better embedding models).
3.  **Code**: Start a fresh `src_v2/` directory to avoid entanglement with legacy code during the transition.

## 5. Proposed Stack
*   **Language**: Python 3.12+
*   **Frameworks**: **FastAPI** (HTTP API), **discord.py** (Discord Bot).
*   **Databases**:
    *   **PostgreSQL**: Relational data (Users, Chat Logs, Facts).
    *   **Qdrant**: Vector Memory.
    *   **Neo4j**: Knowledge Graph.
    *   **InfluxDB**: Metrics.
    *   **Redis**: Caching/PubSub (optional).
*   **Key Libraries**:
    *   **Configuration**: `pydantic-settings` (Type-safe config management).
    *   **Database ORM**: `asyncpg` (PostgreSQL), `qdrant-client`, `neo4j` (direct driver).
    *   **Background Tasks**: `arq` (Redis-backed task queue) + `asyncio` for simple fire-and-forget.
    *   **Migrations**: `alembic` (Database schema management).
    *   **Logging**: `loguru` (Structured, simplified logging).
    *   **HTTP Client**: `httpx` (Modern async HTTP client for LLM APIs).
    *   **Embeddings**: `sentence-transformers` (Local embedding generation).
*   **Removed**: `spaCy`, `RoBERTa`, `LangChain`, `LlamaIndex` (replaced by custom Python + LLM native function calling).
*   **Deployment**: `docker-compose.yml` with individual services per bot, shared infrastructure, and shared worker containers.

## 6. Background Worker Architecture

### The Shared Worker Model

Background processing uses a **shared worker** architecture - a single worker container serves **all bot instances**:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        WORKER ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Bot: Elena ─┐                                                     │
│               │                                                     │
│   Bot: Ryan ──┼──→ Redis Queue (arq) ──→ Shared Worker Container   │
│               │         ↑                        ↓                  │
│   Bot: Dotty ─┘         │              Job Handler (loads context)  │
│                         │                        ↓                  │
│                    Job Payload:          Execute analysis/task      │
│                    {                     Store results to DBs       │
│                      bot_name: "elena",                            │
│                      user_id: "123",                               │
│                      job_type: "insight"                           │
│                    }                                                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Why Shared Workers?**
- **Resource Efficient**: 1 worker container vs N workers (one per bot)
- **Simpler Deployment**: No 1:1 bot-to-worker mapping required
- **Context Routing**: Jobs include `bot_name` so worker loads correct character context
- **Concurrent Processing**: Worker can process jobs from multiple bots simultaneously

### Task Classification

| Task Type | Handler | When to Use |
|-----------|---------|-------------|
| **Fire-and-Forget** | `asyncio.create_task` | Simple, stateless tasks (fact extraction, metrics) |
| **Queued Background** | `arq` Redis queue | Long-running, agentic tasks (insight analysis) |

### Current Workers

| Worker | Purpose | Triggers |
|--------|---------|----------|
| `insight-worker` | Pattern detection, epiphanies, response learning | Positive reactions, session end |

### Starting Workers

```bash
# Start the shared worker (serves all bots)
./bot.sh start workers

# Or manually:
docker-compose --profile workers up -d insight-worker
```

### Adding New Background Tasks

1. Define job handler in `src_v2/workers/insight_worker.py` (or new worker file)
2. Register in `WorkerSettings.functions`
3. Enqueue from bot code: `await task_queue.enqueue("job_name", **params)`
