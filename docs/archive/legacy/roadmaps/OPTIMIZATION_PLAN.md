# WhisperEngine v2 - Optimization & Performance Roadmap

This document outlines the strategy for maximizing concurrency, reducing latency, and ensuring the system scales efficiently.

## 🚀 Phase 1: Low-Hanging Fruit (Immediate)
**Goal**: Reduce per-message latency by parallelizing independent I/O operations.

- [x] **Parallel Context Retrieval** (`src_v2/discord/bot.py`)
    - **Problem**: Memories, History, Knowledge, and Summaries were fetched sequentially.
    - **Fix**: Implemented `asyncio.gather` to fetch all 4 contexts simultaneously.
    - **Impact**: Reduces context loading time from sum of all calls (~600ms) to max of single call (~200ms).
- [x] **Parallel Tool Execution** (`src_v2/agents/router.py`)
    - **Problem**: If the Router selected multiple tools (e.g., "Search Memories" + "Lookup Facts"), they ran one after another.
    - **Fix**: Implemented `asyncio.gather` for tool execution loop.
    - **Impact**: Reduces multi-tool query latency significantly.
- [x] **Parallel Engine Pipeline** (`src_v2/agents/engine.py`)
    - **Problem**: Serial execution of Classifier -> Router -> Context Builder added unnecessary latency.
    - **Fix**: Run Classification, Routing, and Context Building in parallel `asyncio.create_task`.
    - **Impact**: Removes 1 full LLM round-trip from the critical path. Latency is now `Max(Classifier, Router) + Generation`.
- [x] **Semantic Fast-Track Classifier** (`src_v2/agents/classifier.py`)
    - **Problem**: Even small LLMs have a 1-5s latency floor on some providers.
    - **Fix**: Use local embeddings (FastEmbed) to match user input against cached "Simple Intents" (greetings, small talk).
    - **Impact**: Classifies ~60% of traffic in <50ms, bypassing the LLM entirely.

## ⚡ Phase 2: Database & Connection Optimization
**Goal**: Ensure the data layer doesn't become a bottleneck under load.

- [x] **PostgreSQL Connection Pooling Tuning**
    - **Current**: Default `asyncpg` pool settings work well for current load.
    - **Status**: Deferred - no issues observed. Will tune if needed under load.
- [x] **Qdrant Optimization**
    - **Current**: Single collection, standard HNSW index.
    - **Status**: Deferred - 18MB collection is tiny, no performance issues.
- [x] **Neo4j Query Optimization**
    - **Status**: Done - Constraints on `User(id)` and `Entity(name)` created on init.

## 🧠 Phase 3: LLM Latency Reduction
**Goal**: The LLM is the slowest part. Optimize how we use it.

- [x] **Streaming Responses**
    - **Status**: Done - Fast Mode streams tokens via `astream()`. Discord message edited every 0.7s.
    - **Note**: Reflective/Agency modes don't stream (acceptable for complex queries).
- [x] **Speculative Execution (Advanced)**
    - **Status**: Done - Cognitive routing runs in parallel with classification via `asyncio.create_task`.
- [ ] **Prompt Token Optimization**
    - **Plan**: Minify system prompts (remove whitespace/comments) before sending to API.
    - **Status**: Low priority - prompts are already concise.

## 🏗️ Phase 4: Architectural Scalability
**Goal**: Handle 1000+ concurrent users.

- [x] **Redis Caching Layer**
    - **Status**: Redis is connected. Trust scores cached. Further caching deferred until needed.
- [x] **Worker Queues for Background Tasks**
    - **Status**: Done - `arq` with Redis for persistent jobs. Shared insight-worker container.
- [ ] **Horizontal Scaling (Sharding)**
    - **Plan**: Shard users across containers using consistent hash on `user_id`.
    - **Status**: Future - not needed until 1000+ concurrent users.

## 📊 Monitoring & Profiling
- [x] **Add Latency Tracing**
    - **Status**: Done - Each step logs timing via `logger.debug()`. Grafana dashboards available.
    - Steps logged: Classification, Context Building, Cognitive Routing, LLM Generation.

## ✅ Phase 5: Operational Hardening (Added Nov 26, 2025)
**Goal**: Production reliability and disaster recovery.

- [x] **Database Backups**
    - `./bot.sh backup` - Creates timestamped backup of PostgreSQL, Qdrant, Neo4j, InfluxDB
    - `./bot.sh restore <dir>` - Restores from backup
