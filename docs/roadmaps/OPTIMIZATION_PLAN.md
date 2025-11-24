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

- [ ] **PostgreSQL Connection Pooling Tuning**
    - **Current**: Default `asyncpg` pool settings.
    - **Plan**: Tune `min_size` and `max_size` based on load testing. Ensure connections are released promptly.
- [ ] **Qdrant Optimization**
    - **Current**: Single collection, standard HNSW index.
    - **Plan**: 
        - Enable `on_disk` payload storage if memory usage grows.
        - Optimize HNSW parameters (`m`, `ef_construct`) for faster retrieval vs build time.
- [ ] **Neo4j Query Optimization**
    - **Current**: Basic Cypher queries.
    - **Plan**: Add indexes on `User(id)` and `Entity(name)` to speed up lookups.

## 🧠 Phase 3: LLM Latency Reduction
**Goal**: The LLM is the slowest part. Optimize how we use it.

- [ ] **Streaming Responses**
    - **Current**: We wait for the full response before sending to Discord.
    - **Plan**: Implement token streaming. Send "typing..." status, then edit the message in chunks as tokens arrive (or send chunks).
    - **Benefit**: Drastically improves *perceived* latency.
- [ ] **Speculative Execution (Advanced)**
    - **Plan**: Start fetching memories *while* the Complexity Classifier is running. If it turns out we don't need them, discard.
- [ ] **Prompt Token Optimization**
    - **Plan**: Minify system prompts (remove whitespace/comments) before sending to API to save tokens and processing time.

## 🏗️ Phase 4: Architectural Scalability
**Goal**: Handle 1000+ concurrent users.

- [ ] **Redis Caching Layer**
    - **Plan**: Cache frequent lookups (e.g., User Trust Score, Knowledge Graph Facts) in Redis with a 5-minute TTL.
    - **Benefit**: Avoids hitting Postgres/Neo4j for every single message.
- [ ] **Worker Queues for Background Tasks**
    - **Current**: `asyncio.create_task` (in-memory).
    - **Risk**: If container restarts, tasks are lost.
    - **Plan**: Use `arq` or `Celery` with Redis to persist background tasks (Summarization, Reflection, Vision).
- [ ] **Horizontal Scaling (Sharding)**
    - **Plan**: If a single bot gets too popular, shard users across multiple containers/processes, using a consistent hash on `user_id`.

## 📊 Monitoring & Profiling
- [ ] **Add Latency Tracing**
    - Log the time taken for each step: `Classification`, `Retrieval`, `LLM Generation`, `TTS`.
    - Visualize in Grafana to identify the "Long Pole".
