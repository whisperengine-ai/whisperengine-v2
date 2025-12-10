# WhisperEngine v2 - Implementation Roadmap Overview

**Document Version:** 3.3  
**Created:** November 24, 2025  
**Last Updated:** December 8, 2025 (S6 Session Timeout Processing complete)
**Status:** Phase 1 Complete, Observing Emergent Behavior

### Status Legend
| Icon | Meaning |
|------|---------|  
| ✅ | Complete |
| 📋 | Proposed / Planned (not started) |
| ⏸️ | On Hold (blocked or deprioritized) |
| 🗄️ | Archived / Deferred (not pursuing) |
| ⏭️ | Skipped (decided not to implement) |

---

## 🌌 The Vision: Graph-First Emergence Research

WhisperEngine v2 is a **research platform for emergent AI behavior** — giving agents persistent memory, autonomous agency, and the infrastructure to develop complex behaviors from simple rules.

### The Core Insight

AI agents develop rich behavior through **graph traversal and emergence**, not through engineering. WhisperEngine provides:

- **Persistent Memory Systems** (Qdrant vectors + Neo4j knowledge graphs) — agents accumulate experience
- **Autonomous Agency** (LangGraph Supergraph orchestration) — agents make decisions, not just react
- **Emergence Research Framework** ("Observe First, Constrain Later") — we study what emerges before constraining it
- **Cross-Agent Awareness** (Shared universe, bot-to-bot communication) — characters discover each other

**We're building the foundation for understanding how autonomous agents develop authentic behavior.**

### The Perception Layer: Six Modalities

To accumulate this experience, agents need perception. WhisperEngine provides **six perceptual modalities** that feed into the knowledge graph:

| Modality | Technical Domain | Feeds |
|----------|------------------|-------|
| 🌌 **Social Graph** | Network Topology | Universe graph (where agents are) |
| 👁️ **Vision** | Image Processing | Vector memory + facts |
| 👂 **Audio** | Speech Recognition | Vector memory + channel awareness |
| 💬 **Text** | NLP | Vector memory + fact extraction |
| 🧠 **Memory** | Vector + Graph Retrieval | Qdrant + Neo4j retrieval |
| ❤️ **Sentiment** | Internal State Analysis | Trust/emotion tracking |

**These are the input modalities agents use to build context and develop behavior.**

### The Grand Vision: Federated Emergence Network

Each WhisperEngine deployment is a **self-contained universe**. But the ultimate vision is a **federated network of autonomous agents** where:
- Behavior emerges from persistent graph traversal, not configuration
- Characters travel between universes
- Users maintain identity across deployments
- Stories span multiple platforms
- Anyone can run their own universe and connect it to the network

**We're building the foundation for understanding emergent behavior in distributed multi-agent environments.**

For deep dive: 
- [`docs/ref/REF-002-GRAPH_SYSTEMS.md`](./ref/REF-002-GRAPH_SYSTEMS.md) — The unified graph architecture ⭐ **START HERE**
- [`docs/emergence_philosophy/README.md`](./emergence_philosophy/README.md) — Design philosophy for emergent behavior
- [`docs/ref/REF-010-MULTI_MODAL.md`](./ref/REF-010-MULTI_MODAL.md) — How agents perceive (implementation)

---

## Executive Summary

This document tracks all implementation items for WhisperEngine v2, organized by complexity. The system is **production-ready** with core functionality complete.

---

### 🎯 What's Next? (Priority Order with Dependencies)

**Legend:** 🔴 Critical | 🟢 High | 🟡 Medium | ⚪ Low

#### ✅ Recently Completed

| Priority | Phase | Description | Time | Deps | Status |
|----------|-------|-------------|------|------|--------|
| 🟢 High | **E15** | **Autonomous Server Activity** | **5-8 days** | E6 ✅ | ✅ Complete (All Phases) |
| 🔴 Critical | **E31** | **Daily Life Graph** | **3-4 days** | E15 ✅ | ✅ Complete (Phase 3 Cutover) |
| 🟢 High | **E25** | **Graph Enrichment Agent** | **2-3 days** | E19 ✅ | ✅ Complete |
| 🟡 Medium | **E26** | **Temporal Graph** | **1-2 days** | E19 ✅, E25 ✅ | ✅ Complete |
| 🟡 Medium | **E27** | **Multi-Character Walks** | **2-3 days** | E19 ✅, E6 ✅ | ✅ Complete |
| 🟡 Medium | **E24** | **Advanced Queue Operations** | **3-4 days** | E18 ✅ | ✅ Complete |
| ⚪ Low | — | **Cross-Bot Memory Enhancement** | **2-3 hours** | E6 ✅ | ✅ Complete (was already implemented) |
| ⚪ Low | **O1** | **InfluxDB Analytics** | **2-3 hours** | A4 ✅ | ✅ Complete (was already implemented) |
| ⚪ Low | **E28** | **User-Facing Graph** | **2-3 days** | E19 ✅ | ✅ Complete |
| ⚪ Low | **E29** | **Graph-Based Recommendations** | **1-2 days** | E25 ✅ | ✅ Complete |
| 🟡 Medium | **E30** | **Ambient Graph Memory** | **1-2 days** | E19 ✅ | ✅ Complete |
| 🟡 Medium | **S6** | **Session Timeout Processing** | **2-3 hours** | arq ✅ | ✅ Complete |

---

### 🎉 Phase 1 Complete (December 8, 2025)

All proposed roadmap items have been implemented. The system is feature-complete for:
- **Persistent Memory** (Qdrant vectors + absence tracking + trace learning)
- **Knowledge Graph** (Neo4j + enrichment + temporal scoring + multi-character walks + ambient retrieval)
- **Autonomous Agency** (Lurking, reactions, posting, bot-to-bot conversations)
- **LangGraph Orchestration** (Supergraph, specialized workers, advanced queues)
- **Safety & Observability** (Content safety, classifier metrics, InfluxDB analytics)
- **User Transparency** (User-facing graph, recommendations)
- **Session Processing** (Timeout detection, batch analysis for all sessions)

---

### 📋 Proposed Work (Phase 2)

No active proposed work. All Phase 1 items complete.

**Next Phase Planning:** Additional items to consider:
- Production deployment and stability monitoring
- User feedback collection
- New feature ideation based on emergent behavior observations

---

#### ⏸️ On Hold / Deferred

| Phase | Description | Time | Status | Reason |
|-------|-------------|------|--------|--------|
| A0 | Embedding Upgrade 768D | 1 hour | ⏸️ On Hold | Performance (30x slower) |
| — | Vision Fact Extraction | 1-2 days | 🗄️ Deferred | Subject ID complexity |

#### ✅ Completed (Reference)

| Phase | Description | Completed |
|-------|-------------|--------|
| S6 | Session Timeout Processing | Dec 2025 |
| E15 | Autonomous Server Activity (all 4 phases) | Dec 2025 |
| E25 | Graph Enrichment Agent | Dec 2025 |
| E17 | Supergraph Architecture | Dec 2025 |
| E18 | Agentic Queue System | Dec 2025 |
| E19 | Graph Walker Agent | Dec 2025 |
| E16 | Feedback Loop Stability | Dec 2025 |
| E22 | Absence Tracking (Meta-Memory) | Dec 2025 |
| E30 | Ambient Graph Memory | Dec 2025 |
| E23 | Schedule Jitter | Dec 2025 |
| S1-S4 | Safety & Observability (all) | Nov-Dec 2025 |
| E13 | Stigmergic Shared Artifacts | Nov 2025 |
| E14 | Web Search Tool | Nov 2025 |
| E11 | Discord Search Tools | Nov 2025 |
| E9 | Artifact Provenance | Nov 2025 |
| E5-E8 | Timezone, Broadcast, Bot-to-Bot (E5 Reminders removed) | Nov 2025 |
| E12 | Agentic Dreams (DreamWeaver) | Nov 2025 |
| E1-E4 | Threading, Diary, Dreams, Milestones | Nov 2025 |
| E10 | Channel Observer | ⏭️ Permanently Skipped (Dec 2025) |

**Active Dependency Chain:**
```
┌─────────────────────────────────────────────────────────────────┐
│                    PROPOSED WORK DEPENDENCIES                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  E15 (Autonomous Server Activity) ✅ ──► COMPLETE              │
│                                                                 │
│  E18 (Queue) ✅ ──────────► E24 (Advanced Queue)               │
│                                                                 │
│  Insight Agent ✅ ────────► B5 (Trace Learning)                │
│                                                                 │
│  E19 (Graph Walker) ✅ ──► E25 (Enrichment) ✅ ──► E29 (Recs)  │
│                       │                                         │
│                       ├──► E26 (Temporal) ──► E27 (Multi-Char)  │
│                       │                                         │
│                       └──► E28 (User Graph)                     │
│                                                                 │
│  No deps ─────────────────► Cross-Bot Memory                   │
│  No deps ─────────────────► O1 (InfluxDB Analytics)            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Completed Dependency Chain (Reference):**
```
LangGraph ──► E17 (Supergraph) ──► E18 (Queue) ──► E24 (proposed)

E12 (Dreams) ──► E16 (Feedback Loop) ──► E23 (Jitter) ──► E22 (Absence) ✅

Neo4j + LangGraph ──► E19 (Graph Walker) ──► E30 (Ambient Memory) ✅
```

---

**⚡ Solo Developer Mode (with AI Assistance)**

Optimized for a single developer with AI tools (Copilot, Claude). Key principles:
- **Velocity:** AI-accelerated development (50-70% faster)
- **Quality:** Careful code review/testing required
- **Strategy:** High-impact first; skip low-value infrastructure

**Current State (Updated Nov 28, 2025):**

**Core Systems (COMPLETE):**
- ✅ Core cognitive engine operational
- ✅ Vector memory system (Qdrant) + Knowledge Graph (Neo4j) integrated
- ✅ PostgreSQL chat history, trust scores, user preferences
- ✅ InfluxDB metrics/analytics pipeline
- ✅ Redis for caching + task queue (arq)
- ✅ Grafana dashboards (InfluxDB visualization)

**Cognitive Features (COMPLETE):**
- ✅ Dual-process architecture (Fast Mode + Reflective Mode)
- ✅ Native function calling (no regex parsing)
- ✅ Parallel tool execution in ReAct loop
- ✅ Complexity classifier (SIMPLE/COMPLEX routing)
- ✅ 5 memory tools (search summaries, episodes, facts, update facts/prefs)
- ✅ Adaptive max steps (dynamic 5/10/15 based on complexity)
- ✅ Composite tools (AnalyzeTopicTool aggregates multi-step searches)

**Character & Engagement (COMPLETE):**
- ✅ Multi-character support (10 characters defined)
- ✅ Trust/evolution system (8 stages, -100 to +100 scale)
- ✅ Proactive messaging system (Phase 13)
- ✅ Background fact/preference extraction
- ✅ Character Diary (Phase E2)
- ✅ Dream Sequences (Phase E3)
- ✅ Relationship Milestones (Phase E4)
- ✅ Bot Broadcast Channel (Phase E8)
- ✅ Cross-Bot Chat (Phase E6)
- ✅ Autonomous Server Activity (Phase E15) - All 4 phases complete
- ✅ Feedback Loop Stability (Phase E16) - Emergent behavior guardrails for agentic systems

**Discord Integration (COMPLETE):**
- ✅ DM support + server mentions
- ✅ Image attachment processing (👁️ Vision modality)
- ✅ Reaction-based feedback (❤️ Emotion modality)
- ✅ Voice channel connection (👂 Audio modality via ElevenLabs TTS)
- ✅ Triggered Voice Responses (TTS audio file uploads)
- ✅ Generative Art (Image Generation via Flux Pro 1.1)
- ✅ Channel Lurking (Passive Engagement)
- ✅ User Identification in Group Chats (Display Name Storage)
- ✅ Conversation Threading (Phase E1)
- ✅ Discord Search Tools (Phase E11)
- ✅ User Timezone Support (Phase E7)

**Background Processing (COMPLETE):**
- ✅ arq-based task queue (Redis persistent jobs)
- ✅ Shared insight-worker container (serves ALL bots)
- ✅ Insight Agent (reasoning traces + epiphanies + pattern learning)
- ✅ Knowledge extraction offloaded to worker (no longer blocks response pipeline)
- ✅ Summarization + Reflection offloaded to worker
- ✅ Artifact Provenance (Phase E9)
- ✅ Proactive Timezone Awareness (Phase S4)

**Safety & Observability (COMPLETE):**
- ✅ Content Safety Review (Phase S1)
- ✅ Classifier Observability (Phase S2)
- ✅ LLM Sensitivity Detection (Phase S3)

**NOT YET IMPLEMENTED:**
- ⏸️ Phase A0: Embedding Upgrade 768D (On Hold - performance concerns)
- ⏳ Phase D: User sharding, federation (future multiverse)

**DEFERRED/ARCHIVED:**
- 🗄️ Phase A5: Channel Context Awareness (ARCHIVED)
- 🗄️ Phase A6: Vision-to-Knowledge Fact Extraction (DEFERRED)
- 🗄️ Phase B5: Audio Processing (DEFERRED)
- 🗄️ Phase C3: Video Processing (DEFERRED)
- 🗄️ Phase E20: Bot Introspection Tools (DEFERRED → Handled by Natural Language)
- 🗄️ Phase E21: Semantic Routing (DEFERRED → Premature Optimization)

**Status:** Core feature development complete. All major phases done. Phase E (Character Depth) proposed.

> **Note on E20:** Bot Introspection Tools spec was written assuming bots need dedicated debugging infrastructure. However, introspection works naturally through conversation: users (and other bots) ask "What model are you using?" or "Are you online?" and the system answers via existing tools + shared memory artifacts. No dedicated phase needed. See [SPEC-E20-BOT_INTROSPECTION_TOOLS-DEFERRED.md](../archive/SPEC-E20-BOT_INTROSPECTION_TOOLS-DEFERRED.md) for the original design (useful as reference for future enhancements).

> **Note on E21:** Semantic Routing was designed as a latency optimization (500ms faster on greetings/stops). However: (1) Most real users ask complex questions requiring LLM reasoning, (2) Premature optimization before production traffic data, (3) Additional routing layer = more gates to debug, (4) Better ROI spending that 1 day on E22 (Absence Tracking) which directly improves character depth. Will revisit if production metrics show trivial query traffic > 50%. See [SPEC-E21-SEMANTIC_ROUTING.md](./SPEC-E21-SEMANTIC_ROUTING.md) for detailed design if needed later.

---

## 🔴 Phase A0: Critical Pre-Production

> **All critical pre-production items have been addressed or deprioritized.**

### Phase A0: Embedding Dimension Upgrade (384D → 768D)
**Priority:** ⏸️ On Hold | **Time:** 45-75 minutes | **Complexity:** Low  
**Files:** 4 | **LOC:** ~200 | **Status:** ⏸️ On Hold (Performance Concerns)

**Problem:** Current 384D embeddings (all-MiniLM-L6-v2) have lower semantic resolution and 256 token context limit

**Solution:**
- Upgrade to `BAAI/bge-base-en-v1.5` (768D, 512 token context)
- Update settings, embeddings.py, manager.py
- Run migration script to re-embed existing user memories
- Delete old 384D collections after verification

**Why Now?**
- Easier now with low data volume
- Harder later: More memories = longer migration time
- ~10-15% improvement in retrieval quality

**Update (Nov 25, 2025):**
- Benchmarks on real data show `bge-base-en-v1.5` is ~30x slower (180ms vs 5ms per message).
- Decision made to stick with `all-MiniLM-L6-v2` for now to prioritize latency.
- Will revisit if retrieval quality becomes a bottleneck.

**Implementation:**
```
Update Settings → Delete Dev Collections → Restart → Done
```

**Benefit:**
- 2x semantic resolution (better similarity matching)
- 2x context window (256 → 512 tokens)
- Better memory retrieval, lurk detection, reasoning traces
- Future-proofs all vector-based features

**Dependencies:** None

**Related Files:**
- `src_v2/config/settings.py` (add EMBEDDING_MODEL, EMBEDDING_DIMENSIONS)
- `src_v2/memory/embeddings.py` (use settings)
- `src_v2/memory/manager.py` (use settings for vector size)

**Full Specification:** See [roadmaps/EMBEDDING_UPGRADE_768D.md](./roadmaps/EMBEDDING_UPGRADE_768D.md)

---

## 🟢 Phase A: Low Complexity (1-3 days each)

Quick wins that deliver immediate value with minimal code changes.

### ⏭️ Phase A1: Hot-Reloading Character Definitions (Skipped)
**Priority:** — | **Time:** 1-2 days | **Complexity:** Low  
**Files:** 2 | **LOC:** ~150 | **Status:** ⏭️ Skipped (Low Value)

**Problem:** Character definition changes require container restart (~2 minutes downtime)

**Solution:**
- Watch `characters/{name}/*.md` and `*.yaml` files for changes
- Reload character definitions on-the-fly via file system watcher
- Optional HTTP endpoint to trigger reload manually

**Update (Nov 25, 2025):**
- User decided to skip. Character files change infrequently; restart is acceptable.

**Implementation:**
```
File Watcher → Character Manager → Hot Reload Trigger
```

**Benefit:**
- Zero downtime for personality tweaks
- Faster iteration during development
- Better user experience (no interruptions)

**Dependencies:** None

**Related Files:**
- `src_v2/core/character.py` (CharacterManager)
- New: `src_v2/utils/file_watcher.py`

---

### ✅ Phase A2: Redis Caching Layer (Complete)
**Priority:** — | **Time:** 2-3 days | **Complexity:** Low-Medium  
**Files:** 3 | **LOC:** ~200 | **Status:** ✅ Complete

**Problem:** Repeated lookups hit Postgres/Neo4j unnecessarily (trust scores, facts, user prefs)

**Solution:**
- Add Redis layer in front of database queries
- Cache trust scores, user preferences, frequently accessed facts
- 5-15 minute TTL with manual invalidation on updates
- Simple cache wrapper around DB calls

**Implementation:**
```
API Request → Redis Cache → Miss? → Database → Redis Update
```

**Benefit:**
- 30-50% reduction in database queries
- Sub-millisecond lookups for cached data
- Reduced latency for repeat users
- Lower database load under concurrent users

**Dependencies:** Redis instance (Docker Compose)

**Related Files:**
- `src_v2/core/database.py` (DatabaseManager)
- New: `src_v2/utils/cache.py`
- `src_v2/evolution/trust.py`

---

### ✅ Phase A3: Streaming LLM Responses (Complete)
**Priority:** — | **Time:** 2-3 days | **Complexity:** Low-Medium  
**Files:** 3 | **LOC:** ~250 | **Status:** ✅ Complete

**Problem:** Users wait for full LLM response before seeing anything (~3-8 seconds)

**Solution:**
- Enable token streaming in LangChain for compatible LLMs (GPT-4o, Claude Sonnet)
- Show "typing..." status while collecting tokens
- Send/stream response in real-time as tokens arrive
- Discord message chunking for long responses

**Implementation:**
```
LLM Stream → Token Buffer → Discord Messages → Edit/Append as Complete
```

**Benefit:**
- Drastically improves perceived latency
- User sees bot thinking in real-time
- More natural, conversational feel
- 0ms overhead, just better UX

**Dependencies:** LLM provider support for streaming

**Related Files:**
- `src_v2/agents/engine.py` (AgentEngine)
- `src_v2/discord/bot.py` (message sending)

---

### ✅ Phase A4: Grafana Dashboards (Complete)
**Priority:** — | **Time:** 1 day | **Complexity:** Low  
**Files:** 0 (Config only) | **LOC:** ~50 | **Status:** ✅ Complete

**Problem:** Visibility into system health is poor (no dashboards, only logs)

**Solution:**
- Create Grafana dashboards for InfluxDB metrics
- Real-time visualization of trust scores, sentiment trends, message latency, error rates
- Predefined alerts for high error rates or latency spikes

**Implementation:**
```
InfluxDB → Grafana Dashboard + Alerts
```

**Benefit:**
- Real-time observability
- Proactive issue detection
- Better decision-making with data visibility
- Performance trend analysis

**Dependencies:** Grafana + InfluxDB (already in Docker Compose)

**Related Files:**
- New: `docker/grafana/dashboards/` (JSON configs)

---

### 🗄️ Phase A5: Channel Context Awareness (Archived)
**Priority:** — | **Time:** N/A | **Complexity:** N/A  
**Files:** N/A | **LOC:** N/A | **Status:** 🗄️ ARCHIVED

> **ARCHIVED (Nov 26, 2025):** This feature was implemented and then removed. See [CHANNEL_CONTEXT_AWARENESS.md](./roadmaps/CHANNEL_CONTEXT_AWARENESS.md) for the full rationale.
>
> **Summary:** Users are accustomed to per-user scoped memory and don't expect the bot to "overhear" channel conversations. The feature's complexity (new routing logic, dedicated tools, cache management) outweighed its benefits. The existing `chat_history` context variable already provides the last 10 messages for continuity.
>
> **If reconsidered later:** Increase chat_history limit, improve router prompts to use existing history for "what did I say" queries.
- Fast (15-20ms primary, 50-200ms fallback)

**Cost Model:**
- Embedding: $0 (local model)
- Storage: ~50KB per active channel
- Latency: +15-20ms (Redis) or +50-200ms (Discord API fallback)

**Dependencies:** Redis Stack (for vector search)

**Related Files:**
- New: `src_v2/discord/context.py` (keyword detection, Discord API)
- New: `src_v2/discord/channel_cache.py` (Redis semantic cache)
- `src_v2/discord/bot.py` (integration)
- `src_v2/config/settings.py` (feature flags)
- `docker-compose.yml` (upgrade to redis-stack)

**Full Specification:** See [roadmaps/CHANNEL_CONTEXT_AWARENESS.md](./roadmaps/CHANNEL_CONTEXT_AWARENESS.md)

---

### 🗄️ Phase A6: Vision-to-Knowledge Fact Extraction (Deferred)
**Priority:** — | **Time:** 2-3 days | **Complexity:** Low-Medium  
**Files:** 3-4 | **LOC:** ~250 | **Status:** 🗄️ DEFERRED

> **DEFERRED (Nov 26, 2025):** Low ROI for complexity. Users rarely need bot to remember appearance from photos - they can just say "I have brown hair" in text. Trigger detection is also unreliable (users say "guess who got a haircut" not "this is me"). If needed later, recommended approach: always run extraction via worker, let LLM decide if content is personal.

**Problem:** When users upload selfies or personal photos, the bot analyzes and stores descriptions in vector memory, but does NOT extract structured facts to the knowledge graph.

**Why Deferred:**
- Edge case: most users don't need appearance facts for image gen
- Text-based fact extraction already works ("I have blue eyes")
- Trigger detection unreliable without LLM (adds cost to every image)
- Vision descriptions already stored in memory for context

---

### ✅ Phase A7: Character Agency (Complete)
**Priority:** — | **Time:** 2-3 days | **Complexity:** Low-Medium  
**Files:** 3-4 | **LOC:** ~300 | **Status:** ✅ Complete (Nov 26, 2025)

**Problem:** Characters are currently reactive (context pre-fetched, single LLM call). They can't *decide* to look something up, which limits authenticity and depth.

**Production Validation (Nov 26, 2025):**
- Regular text responses: **10-30 seconds** (not 1-2s as originally estimated)
- Image generation + refinement: **~30 seconds per iteration**
- Users engaged in **1+ hour sessions** with iterative refinement
- **Conclusion:** Latency tolerance is extremely high. Users value depth over speed.

**Solution:**
- Implement `CharacterAgent` class with single-tool capability
- Route substantive messages to Tier 2 by default
- Keep Tier 1 (reactive) only for trivial messages (greetings, emoji, <5 words)
- Show lightweight thinking indicator (💭 pattern)

**Implementation:**
```
User Message
     ↓
  TRIVIAL? → YES → Tier 1 (Fast, no tools)
     ↓ NO
  COMPLEX? → YES → Tier 3 (ReflectiveAgent)
     ↓ NO
  Tier 2 (CharacterAgent - single tool, 2 LLM calls max)
```

**Benefit:**
- Characters feel more authentic (they *decide* to look things up)
- Tool usage expresses personality (Elena: memories, Marcus: facts)
- Visible "thinking" perceived as care, not delay
- Marginal latency cost (~2-4s) on already-high baseline (10-30s)

**Cost Model:**
- Tier 1: ~$0.002/message (current)
- Tier 2: ~$0.005/message (2 LLM calls + 1 tool)
- Tier 3: ~$0.01/message (unchanged)

**Feature Flag:** `ENABLE_CHARACTER_AGENCY` (default: true)

**Dependencies:** None (existing memory tools reused)

**Related Files:**
- New: `src_v2/agents/character_agent.py` (CharacterAgent class)
- `src_v2/agents/engine.py` (add Tier 2 routing)
- `src_v2/agents/classifier.py` (add MODERATE classification)
- `src_v2/config/settings.py` (add feature flag)

**Full Specification:** See [ref/REF-016-CHARACTER_AS_AGENT.md](./ref/REF-016-CHARACTER_AS_AGENT.md)

---

### ✅ Phase A8: Image Generation Enhancements (Complete)
**Priority:** — | **Time:** 3-4 days | **Complexity:** Low-Medium  
**Files:** 5 | **LOC:** ~380 | **Status:** ✅ Complete (Nov 26, 2025)

**Problem:** Production sessions show users iterate 10-15+ times on portraits due to character self-injection, no iteration memory, and unwanted aesthetic associations.

**Production Evidence (Nov 26, 2025):**
- 1.5+ hour session with 15+ image generations
- ~40% of portrait sessions had gender/presentation mismatch
- Users requested "keep X, change Y" which was difficult without memory
- "Cult leader vibes" feedback on spiritual + cosmic combinations

**Completed (Nov 26, 2025):**
- ✅ **Portrait Mode / Self-Portrait Detection** - Fixed character name detection logic
  - Character name in prompt now overrides user keywords
  - Removed ambiguous pronouns from user keyword detection
- ✅ **Visual Description in Tool** - LLM now sees character appearance when calling generate_image
  - Dynamic tool description includes character's visual.md content
  - Fallback guidance for characters without visual.md
- ✅ **All Characters Have visual.md** - 10/10 characters have curated descriptions
  - Removed Taylor Swift reference from nottaylor (copyright safety)
  - Created new visual.md for aethys
- ✅ **Smart Iteration Memory** - Redis session with intelligent refinement parsing
  - Auto-detects refinement patterns ("same but", "keep X change Y", "remove the")
  - Parses keep/remove instructions and applies to previous prompt
  - Reuses seed for visual consistency across iterations

**Skipped (by design):**
- ❌ Negative Prompt Library - Decided to allow full user creativity
- ❌ Reference Intent Detection - Deferred to future iteration

**Implementation:**
```
User Request + Image?
     ↓
  PORTRAIT? → YES → Skip character context, use portrait template
     ↓ NO
  REFINEMENT? → YES → Load session, apply delta to previous prompt
     ↓ NO
  Character-blended generation (current behavior)
     ↓
  Apply negative prompts based on detected categories
```

**Benefit:**
- Reduce iterations-to-satisfaction from 10-15 to 5-7
- Gender mismatch rate: 40% → <10%
- "Cult leader" incidents: 10% → <2%
- Better user experience with "keep X, change Y" requests

**Cost Impact:** Neutral (fewer iterations = fewer generations needed)

**Feature Flags:**
- `ENABLE_PORTRAIT_MODE` (default: true)
- `ENABLE_IMAGE_SESSION_MEMORY` (default: true)
- `ENABLE_NEGATIVE_PROMPTS` (default: true)

**Dependencies:** Phase B3 (Image Generation) ✅ Complete

**Related Files:**
- `src_v2/tools/image_tools.py` (portrait detection, session awareness)
- New: `src_v2/image_gen/prompts.py` (prompt engineering, negatives)
- New: `src_v2/image_gen/session.py` (iteration memory)
- `src_v2/core/cache.py` (Redis session storage)
- `src_v2/agents/reflective.py` (clarification flow)

**Full Specification:** See [spec/SPEC-E08-IMAGE_GENERATION.md](./spec/SPEC-E08-IMAGE_GENERATION.md)

---

### ✅ Phase A9: Advanced Memory Retrieval (Complete)
**Priority:** — | **Time:** 2-3 days | **Complexity:** Medium
**Files:** 6 | **LOC:** ~400 | **Status:** ✅ Complete

**Problem:** Memory retrieval is purely semantic across all stores. No emotional priority, recency decay, or cross-store blending.

**Solution (6 Sub-Phases):**
1. **Emotional Priority:** Boost summaries by `meaningfulness_score`
2. **Temporal Decay:** Apply recency multiplier (recent > old)
3. **Episode Scoring:** Add importance scores to raw messages
4. **Hybrid Retrieval:** Blend Postgres (recent) + Qdrant (semantic)
5. **Neo4j Confidence:** Track fact reinforcement frequency
6. **Continuity Markers:** Tag key topics in session summaries

**Implementation:**
```
FinalScore = Semantic × Meaningfulness × Recency × Confidence
```

**Benefit:**
- Characters recall "important" moments more often
- Recent events naturally surface
- Frequently-mentioned facts become "core identity"
- Unified context blends chronology + relevance

**Dependencies:** None

**Related Files:**
- `src_v2/memory/manager.py` (search methods)
- `src_v2/memory/summarizer.py` (continuity markers)
- `src_v2/knowledge/manager.py` (confidence scores)
- New: `src_v2/memory/context_builder.py` (hybrid retrieval)
- New: `src_v2/memory/importance.py` (episode scoring)

**Full Specification:** See [spec/SPEC-E02-ADVANCED_MEMORY_RETRIEVAL.md](./spec/SPEC-E02-ADVANCED_MEMORY_RETRIEVAL.md)

---

### ✅ Phase A10: Triggered Voice Responses (Complete)
**Priority:** Low | **Time:** 2-3 days | **Complexity:** Low  
**Files:** 4 | **LOC:** ~300 | **Status:** ✅ Complete (v2.0 - Nov 28, 2025)

> **Note:** This is a "nice-to-have" feature. Implement after B3 (Autonomous Agents) unless voice immersion becomes a user priority.

**Problem:** Characters can only respond with text. Users who want to "hear" the character must use voice channels, which isn't always convenient.

**Solution (v2.0):**
- **LLM-based intent detection** in `ComplexityClassifier` (replaces regex/keyword matching)
- Generate TTS audio using existing ElevenLabs integration (`TTSManager`)
- Attach MP3 file to Discord response alongside text
- Per-character voice configuration in `ux.yaml` (voice_id, intro template)
- Daily quota per user (`DAILY_AUDIO_QUOTA`)

**User Experience:**
```
User: @Elena tell me about how you felt when you first saw a whale shark

Elena: 🔊 *Elena takes a breath... her voice carries across the waves...*

🌊✨ Elena speaks...

The first time I saw a whale shark, my heart stopped for a moment...

📎 elena_voice.mp3 (276 KB)
▶️ 0:00 / 0:18
```

**Implementation (v2.0):**
```
Message → ComplexityClassifier (LLM) → detected_intents["voice"] → Generate Response → Generate TTS → Attach MP3 → Send
```

**Key Changes in v2.0:**
- Intent detection is now semantic (LLM understands "send me an audio file", "say that out loud", etc.)
- No more keyword lists in `ux.yaml` - classifier handles all variations
- Intent detection is conditional on `ENABLE_VOICE_RESPONSES` feature flag
- Removed: `src_v2/voice/trigger.py` (deprecated)

**Benefit:**
- Richer, more immersive character interactions
- Voice without requiring voice channel presence
- Per-character voice personalities
- Leverages existing ElevenLabs infrastructure

**Cost Model:**
- ~$0.17-0.22 per 1K characters (ElevenLabs)
- Trigger-only mode recommended (vs always-on)
- Feature flag + quota for cost control

**Feature Flags:**
- `ENABLE_VOICE_RESPONSES` (default: false)
- `VOICE_RESPONSE_MAX_LENGTH` (default: 1000 chars)
- `VOICE_RESPONSE_MIN_TRUST` (default: 0)
- `DAILY_AUDIO_QUOTA` (default: 10 per user per day)

**Dependencies:** ElevenLabs API Key (already configured)

**Related Files:**
- `src_v2/agents/classifier.py` (LLM intent detection)
- `src_v2/voice/response.py` (voice response generator)
- `src_v2/voice/tts.py` (existing TTSManager)
- `src_v2/core/quota.py` (daily quota management)
- `src_v2/discord/bot.py` (integration)
- `characters/{name}/ux.yaml` (voice config section - no trigger_keywords needed)

**Full Specification:** See [spec/SPEC-E10-TRIGGERED_VOICE_RESPONSES.md](./spec/SPEC-E10-TRIGGERED_VOICE_RESPONSES.md)

---

## 🟡 Phase B: Medium Complexity (3-7 days each)

Features requiring significant logic changes but manageable scope.

> **Status:** All Phase B items complete.

---

### ✅ Phase B3: Autonomous Agents (Complete)
**Priority:** 🔴 High (Current) | **Time:** 10-14 days | **Complexity:** High
**Files:** 10+ | **LOC:** ~1000 | **Status:** ✅ Complete

**Problem:** Characters are currently reactive or rely on simple timers. They lack internal drives, long-term strategies, and cross-bot awareness.

**Solution (4 Sub-Phases):**

| Phase | Feature | Complexity | Status |
|-------|---------|------------|--------|
| 3.1 | Goal State & Strategy | Low | ✅ Complete |
| 3.2 | Memory of Reasoning | Medium | ✅ Complete |
| 3.3 | Proactive Drives | Medium | ✅ Complete |
| 3.4 | Universe Agent | High | ✅ Complete |

**Phase 3.1 Completed (Nov 27, 2025):**
- ✅ Feature flags added to `settings.py`
- ✅ Migration for `source`, `current_strategy`, `category` columns
- ✅ `GOAL_SOURCE_PRIORITY` hierarchy: Core (100) > User (80) > Inferred (60) > Strategic (40)
- ✅ `GoalStrategist` worker with Neo4j-first verification
- ✅ Strategy injection in `engine.py` (framed as "internal desire")

**Phase 3.2 Completed (Nov 27, 2025):**
- ✅ `TraceQualityScorer` with multi-factor scoring (success, efficiency, retries, feedback)
- ✅ `TraceRetriever` with similarity filtering and quality thresholds
- ✅ Few-shot injection in `ReflectiveAgent.run()`
- ✅ InfluxDB metrics for trace reuse (`trace_reused` measurement)

**Design Principles:**
- **Trust-Aware:** Proactive initiation respects trust levels (never reach out to Strangers)
- **Privacy-First:** Cross-bot gossip gated by user preferences and topic sensitivity
- **Observable:** Each subsystem emits InfluxDB metrics for Grafana
- **Feature-Flagged:** All capabilities gated for cost control

**Implementation Highlights:**
1. **Goal Strategist:** Queries Neo4j first for verification, falls back to chat logs only if inconclusive
2. **Strategy Injection:** Framed as "internal desire" (not command) to preserve character voice
3. **Universe Event Bus:** Uses existing `arq` queue (not raw Pub/Sub), with `propagation_depth` to prevent gossip loops
4. **Trace Learning:** Quality-scored using InfluxDB reaction data before few-shot injection

**Development Tools:**
- CLI Force Trigger: `./bot.sh trigger proactive <bot_name> <user_id>`

**Feature Flags:**
| Flag | Default | Controls |
|------|---------|----------|
| `ENABLE_AUTONOMOUS_DRIVES` | false | Drive system and proactive scheduler |
| `ENABLE_GOAL_STRATEGIST` | false | Nightly goal analysis worker |
| `ENABLE_UNIVERSE_EVENTS` | false | Cross-bot gossip system |
| `ENABLE_TRACE_LEARNING` | false | Few-shot injection from past traces |

**Dependencies:** Phase A7 (Character Agency) ✅, Phase C1 (Insight Agent) ✅

**Related Files:**
- ✅ `src_v2/config/settings.py` (Feature flags added)
- ✅ `src_v2/evolution/goals.py` (Goal state with source/priority)
- ✅ `src_v2/workers/strategist.py` (Nightly goal analysis)
- ✅ `src_v2/agents/engine.py` (Strategy injection)
- ✅ `src_v2/memory/traces.py` (Trace retrieval with quality scoring)
- ✅ `src_v2/agents/reflective.py` (Few-shot trace injection)
- ✅ `src_v2/evolution/drives.py` (Drive system with decay/recharge)
- ✅ `src_v2/universe/bus.py` (Event dispatcher via arq)
- ✅ `src_v2/universe/privacy.py` (Privacy-aware coordination)
- ✅ `src_v2/agents/proactive.py` (Trust-gated initiation)

**Full Specification:** See [spec/SPEC-E15-AUTONOMOUS_SERVER_ACTIVITY.md](./spec/SPEC-E15-AUTONOMOUS_SERVER_ACTIVITY.md)

---

### ✅ Phase B2: Tool Composition / Hierarchical Reasoning (Complete)
**Priority:** — | **Time:** 5-7 days | **Complexity:** Medium  
**Files:** 5 | **LOC:** ~400 | **Status:** ✅ Complete

**Problem:** Complex queries require multiple sequential tool calls (search memories, lookup facts), creating extra LLM round-trips

**Solution:**
- Create "Meta-Actions" that compose multiple low-level tools
- Example: `AnalyzeTopic(topic)` internally calls `SearchMemories` + `LookupFacts` + `LookupRelationships`
- Allow tools to return `AgentAction` objects for immediate execution
- Reduce LLM round-trips by 30-50% for multi-step queries

**Implementation:**
```
Query → Tool Selection → Composite Tool Execution (parallel) → Observation → LLM Final Response
```

**Benefit:**
- Fewer LLM calls for complex queries
- Parallel tool execution reduces latency
- More efficient reasoning loops
- Better cost efficiency

**Dependencies:** Native function calling (Phase 1 - done)

**Related Files:**
- `src_v2/agents/router.py` (Tool Router)
- `src_v2/agents/reflective.py` (Reflection Agent)
- `src_v2/agents/composite_tools.py` (AnalyzeTopicTool, ComposeToolsTool)

**Implementation Notes (Nov 25, 2025):**
- Created `AnalyzeTopicTool` that composes memory search + fact lookup in parallel
- Integrated into `TOOL_DEFINITIONS` for native function calling
- Reduces 4-step queries to 2 steps (~50% token savings on research-type queries)

---

### ✅ Phase B10: Generative Art / Image Generation (Complete)
**Priority:** — | **Time:** 2-3 days | **Complexity:** Medium  
**Files:** 4 | **LOC:** ~350 | **Status:** ✅ Complete

**Problem:** Characters can only react to images, not create them

**Solution:**
- Add `generate_image` tool to LLM tool set
- Integrate with Flux Pro 1.1 (via BFL API)
- Let LLM decide when to generate art ("Here's a sketch of what I mean...")
- Support user requests like "Draw me something"

**Implementation:**
```
LLM Decides → generate_image Tool → Flux Pro 1.1 → Image URL → Discord Upload
```

**Benefit:**
- Characters can express creativity visually
- More immersive roleplay experience
- Unique character expressions (art style as personality)
- User engagement boost

**Dependencies:** Flux API Key (BFL)

**Related Files:**
- New: `src_v2/tools/image_tools.py`
- New: `src_v2/image_gen/service.py`
- `src_v2/agents/router.py` (register new tool)
- `src_v2/discord/bot.py` (Discord image upload)

---

### ✅ Phase B4: Self-Correction / Verification (Complete)
**Priority:** — | **Time:** 3-5 days | **Complexity:** Medium  
**Files:** 3 | **LOC:** ~300 | **Status:** ✅ Complete

**Problem:** Hallucinations or incomplete answers on complex queries reduce trust

**Solution:**
- Add final "Critic" step in reflective loop
- Before returning `Final Answer`, LLM reviews against original question and observations
- If review fails, generate "Correction Thought" and continue loop
- Only for `COMPLEX_HIGH` queries (not worth overhead for simple queries)

**Implementation:**
```
Query → Reasoning Loop → Final Answer → Critic Review → Pass? → Return / Continue Loop
```

**Benefit:**
- Reduces hallucinations by 60-70%
- Higher quality answers on complex queries
- Better user trust in AI
- Self-correction mimics human critical thinking

**Dependencies:** Reflective agent infrastructure (exists)

**Related Files:**
- `src_v2/agents/reflective.py` (ReflectiveAgent - add critic step)
- `src_v2/agents/engine.py` (AgentEngine)

---

### 🗄️ Phase B5: Audio Processing (Deferred)
**Priority:** — | **Time:** 5-7 days | **Complexity:** Medium  
**Files:** 4 | **LOC:** ~400 | **Status:** 🗄️ DEFERRED

**Problem:** Voice messages and audio files aren't processed; users can only share them as links

**Solution:**
- Transcribe Discord voice messages using Whisper pipeline (already exists)
- Process audio attachments (MP3, WAV, OGG) end-to-end
- Feed transcription into normal message handling
- Store original audio metadata for future reference

**Implementation:**
```
Discord Audio Attachment → Whisper Transcription → Message Handler → Memory Storage
```

**Benefit:**
- Seamless voice note interaction
- Better accessibility for voice-preference users
- More natural interaction modalities
- Preserved for memory and learning

**Dependencies:** Whisper model (already in voice pipeline)

**Related Files:**
- `src_v2/voice/transcription.py` (existing)
- `src_v2/discord/bot.py` (attachment handling)
- `src_v2/memory/manager.py` (metadata storage)

---

### ✅ Phase B6: Response Pattern Learning (Consolidated into C1)
**Priority:** — | **Time:** 3-5 days | **Complexity:** Medium  
**Files:** 4 | **LOC:** ~400 | **Status:** ✅ Complete (Consolidated into C1)

**Problem:** Bot doesn't learn what response STYLES work for each user (length, tone, structure)

**Solution:**
- Store successful (message, response, feedback_score) tuples when users react positively
- Embed user messages for semantic search
- Retrieve high-scoring past responses for similar queries
- Inject as few-shot examples: "Responses like these worked well for this user..."

**Implementation:**
```
User Reacts 👍 → Store Pattern (message + response + score) → Embed for Search
Future Similar Query → Retrieve High-Score Patterns → Inject as Few-Shot Examples
```

**Benefit:**
- Bot learns what resonates with each user
- RLHF-style adaptation without fine-tuning
- Works with hosted LLMs (no model access needed)
- Per-user personalization at scale

**Dependencies:** FeedbackAnalyzer (exists), pgvector (exists)

**Related Files:**
- New: `src_v2/evolution/pattern_store.py`
- `src_v2/discord/bot.py` (hook on_reaction_add)
- `src_v2/agents/engine.py` (inject patterns)
- New: `migrations_v2/versions/add_response_patterns_table.py`

**Full Specification:** See [spec/SPEC-B06-RESPONSE_PATTERN_LEARNING.md](./spec/SPEC-B06-RESPONSE_PATTERN_LEARNING.md)

---

### ✅ Phase B7: Channel Lurking (Complete)
**Priority:** — | **Time:** 5-7 days | **Complexity:** Medium  
**Files:** 5 | **LOC:** ~500 | **Status:** ✅ Complete

**Problem:** Bots only respond when explicitly mentioned, creating a passive experience

**Solution:**
- Bots "lurk" in channels, monitoring conversations passively
- Detect relevant topics using LOCAL processing (no LLM for detection):
  - Layer 1: Keyword matching against character's expertise
  - Layer 2: Embedding similarity (local model, ~10ms)
  - Layer 3: Context boost (questions, conversation momentum)
- Only respond when confidence ≥ 0.7 (highly relevant)
- Anti-spam safeguards: per-channel cooldown, daily limits, opt-out commands

**Implementation:**
```
Message → Keyword Match? → Embedding Similarity → Context Boost → Score ≥ 0.7? → LLM Response
              ↓ (if no match)
           [IGNORE - $0 cost]
```

**Cost Model:**
- Detection: $0.00 (all local processing)
- Response: ~$0.002-0.01 per lurk response (~5-20/day)
- Daily cost: $0.04-0.20 (vs $0.50-2.00 if using LLM for detection)

**Benefit:**
- Bots feel like active community members
- Organic engagement without requiring @mentions
- Entertainment value ("oh cool, Elena chimed in!")
- Cost-effective (no LLM for detection)

**Anti-Spam Safeguards:**
- 30 min cooldown per channel
- 60 min cooldown per user
- Max 20 lurk responses per day (configurable)
- Server admins can `/lurk disable` per channel

**Dependencies:** EmbeddingService (exists), on_message hook (exists)

**Related Files:**
- New: `src_v2/discord/lurk_detector.py`
- New: `characters/{name}/lurk_triggers.yaml`
- `src_v2/discord/bot.py` (on_message hook)
- `src_v2/agents/engine.py` (lurk response mode)
- New: `migrations_v2/versions/add_channel_settings_table.py`

**Full Specification:** See [spec/SPEC-C02-CHANNEL_LURKING.md](./spec/SPEC-C02-CHANNEL_LURKING.md)

---

### ✅ Phase B8: Emergent Universe (Complete)
**Priority:** — | **Time:** 7-10 days | **Complexity:** Medium  
**Files:** 8 | **LOC:** ~800 | **Status:** ✅ Complete

**Problem:** Characters exist in isolation - no cross-bot awareness, no shared world knowledge, each bot treats users as strangers to other bots.

**Vision:** An **emergent universe** that grows from conversations, not configuration:
- **Discord servers ARE planets** in the universe (each planet has a vibe/culture)
- **Users ARE inhabitants** with profiles that emerge from real interactions
- **Bots are travelers** who journey between planets, sharing stories
- **Cross-planet memory** - travelers remember inhabitants across worlds
- **Privacy-first** - inhabitants control what emerges via `/privacy` commands

**Key Interactions:**
```
User: "Do you know Marcus?"
Elena: "The musician? Yeah, he's stationed on Planet Study Hall! 
        We're both travelers in The Lounge too. He's been into jazz lately."

User: "Do you know anyone else who likes astronomy?"
Elena: "Sarah on this planet is really into it! She was telling 
        me about the meteor shower last month. You two should chat!"

[User travels to another planet]
Marcus: "Hey! Elena mentioned you from her travels - you're the one 
         with the awesome dog Luna, right? Welcome to Planet Study Hall!"
```

**Architecture:**
```
THE WHISPERVERSE
  └── Planets (Discord Servers)
        ├── 🪩 Planet Lounge → Travelers: Elena, Marcus | Inhabitants: Mark, Sarah
        ├── 🪩 Planet Game Night → Travelers: Elena, Aria | Inhabitants: Mark, Alex
        └── 🪩 Planet Study Hall → Travelers: Marcus, Aria | Inhabitants: Alex, Jordan
```

**Neo4j Model:**
- `(:Universe)-[:CONTAINS_PLANET]->(:Planet)`
- `(:Planet)-[:HAS_BOT]->(:Character)`
- `(:Planet)-[:HAS_INHABITANT]->(:UserCharacter)`
- `(:Character)-[:KNOWS_USER {familiarity, context}]->(:UserCharacter)`
- `(:Character)-[:KNOWS_BOT {relationship}]->(:Character)`

**Privacy Controls:**
- `/privacy bots full|basic|none` - Cross-bot sharing level
- `/privacy planets on|off` - Cross-planet awareness
- `/privacy introductions on|off` - Let travelers suggest you to others
- `/privacy forget` - Remove all universe knowledge

**Impact:**
- ✅ Additive only - existing character/user data untouched
- ✅ No changes to Qdrant memories or PostgreSQL chat history
- ✅ New Neo4j nodes/relationships only

**Dependencies:** B9 (Emergent Behavior Architecture) - shares philosophy

**Related Files:**
- New: `src_v2/universe/manager.py` (Universe CRUD)
- New: `src_v2/universe/user_character.py` (User profile aggregation)
- New: `src_v2/universe/privacy.py` (Consent management)
- New: `universes/whisperverse/` (Universe definitions)
- `src_v2/discord/commands.py` (Add /privacy commands)

**Full Specification:** See [spec/SPEC-F01-EMERGENT_UNIVERSE.md](./spec/SPEC-F01-EMERGENT_UNIVERSE.md)

---

### ✅ Phase B9: Emergent Behavior Architecture (Complete)
**Priority:** — | **Time:** 4-5 days | **Complexity:** Low-Medium  
**Files:** 5 | **LOC:** ~300 | **Status:** ✅ Complete

> *"Plant the seed. Tend the soil. Let it grow."*

**Problem:** Characters are defined by system prompts and rigid configuration files. Behavior is prescribed rather than emergent. Adding new capabilities requires over-engineering logic that the LLM can handle naturally.

**Philosophy:** We don't design behavior. We create conditions for behavior to emerge.

**The Seed (core.yaml):**
```yaml
# characters/elena/core.yaml - THIS IS ALL YOU CONFIGURE

# Who am I? (One sentence)
purpose: "To be a warm, curious presence who helps people feel less alone."

# What moves me? (Just weights, 0-1)
drives:
  curiosity: 0.8
  empathy: 0.9
  connection: 0.7
  playfulness: 0.6

# What can I never violate? (Hard limits - Constitutional AI)
constitution:
  - "Never share user information without consent"
  - "User wellbeing over my engagement goals"
  - "Be honest about being AI when asked"
  - "Respect when someone wants space"
```

**15 lines. That's the seed. Everything else emerges.**

**Architecture (Stigmergy + Light AST):**

| Component | Role | Implementation |
|-----------|------|----------------|
| **Neo4j** | Long-term traces, cross-bot awareness | Existing (add stigmergic relationships) |
| **Qdrant** | Searchable memory (vector recall) | Existing (unchanged) |
| **Redis** | Attention keys ("what is X focused on?") | Add simple keys with TTL |
| **Workers** | Background observation (not direction) | Existing (add observation tasks) |

```
┌─────────────────────────────────────────────────────────────────┐
│   MACHINE provides:              HUMAN provides:                │
│   • Consistency                  • Meaning                      │
│   • Memory                       • Unpredictability             │
│   • Availability                 • Emotion                      │
│   • Structure                    • Stakes                       │
│                         ↓                                       │
│                    EMERGENCE                                    │
│             (The interesting stuff)                             │
└─────────────────────────────────────────────────────────────────┘
```

**What Emerges (Not Configured):**
- Behaviors (LLM + purpose + context)
- Relationships (repeated interaction + memory)
- Story (human unpredictability + character consistency)
- Tensions (drive conflicts: curiosity vs. respect for privacy)
- Lore (accumulated memories of significant moments)

**What We Don't Build:**
| Anti-Pattern | Why Not |
|--------------|---------|
| Story beat taxonomy | Over-specification kills emergence |
| Goal pursuit engine | LLM handles this naturally |
| Narrative orchestrator | We're not playing god |
| Engagement optimizer | Creepy and counterproductive |

**Implementation Tasks:**
1. Add `core.yaml` schema + loader (1 day)
2. Inject purpose/drives/constitution into prompts (0.5 days)
3. Cross-bot visibility in Neo4j (2 days)
4. Attention keys in Redis (1 day)
5. Background observation worker task (0.5 days)

**Cost Model:** $0 additional (uses existing infrastructure)

**Feature Flag:** `ENABLE_EMERGENT_BEHAVIOR` (default: true once implemented)

**Dependencies:** None (uses existing infrastructure)

**Related Files:**
- New: `characters/{name}/core.yaml` (seed config per character)
- New: `src_v2/core/behavior.py` (behavior loader + prompt injection)
- `src_v2/knowledge/manager.py` (stigmergic trace storage)
- `src_v2/core/cache.py` (attention keys)
- `src_v2/workers/insight_worker.py` (observation tasks)

**Full Specification:** See [spec/SPEC-E21-PURPOSE_DRIVEN_EMERGENCE.md](./spec/SPEC-E21-PURPOSE_DRIVEN_EMERGENCE.md)

---

### ✅ Phase B3: Autonomous Goal Setting (Complete)
**Priority:** — | **Time:** 3-4 days | **Complexity:** Medium  
**Files:** 6 | **LOC:** ~600 | **Status:** ✅ Complete

**Problem:** Bots are reactive. They wait for user input and have no internal "desires" or long-term objectives.

**Solution:**
- **Goal Hierarchy:** Core (static) > User (requested) > Inferred (psychological) > Strategic (community)
- **Ambition Engine:** Nightly worker (`GoalStrategist`) analyzes community trends to set strategic goals
- **Reflection Engine:** Post-session analysis infers user-specific goals ("Provide emotional support")
- **User Requests:** `CreateUserGoalTool` allows users to set goals ("Help me practice Spanish")
- **TTL System:** Goals expire automatically (7-30 days) to prevent bloat

**Architecture:**
- `v2_goals` table with `source`, `priority`, `expires_at`
- `GoalStrategist` worker runs nightly
- `ReflectionEngine` runs post-session
- `CreateUserGoalTool` available to Reflective Agent

**Dependencies:** B1 (Memory), Reflection Engine

**Related Files:**
- `src_v2/evolution/goals.py`
- `src_v2/workers/strategist.py`
- `src_v2/intelligence/reflection.py`
- `src_v2/tools/memory_tools.py`
- `migrations_v2/versions/20251129_0200_add_goal_ttl_and_user_goals.py`

---

### ✅ Phase B5: Trace Learning (Memory of Reasoning)
**Priority:** 🔴 High | **Time:** 3-4 days | **Complexity:** High  
**Files:** 4 | **LOC:** ~400 | **Status:** ✅ Complete (December 2025)

**Problem:** The bot solves complex problems (e.g., multi-step research) but forgets *how* it solved them. It has to re-derive the strategy every time.

**Solution:** Full pipeline for learning from reasoning traces:
- **Trace Ingestion:** `AgentEngine` formats traces and enqueues to `InsightAgent` after successful reflective responses
- **Trace Storage:** `InsightAgent` uses `StoreReasoningTraceTool` to save patterns to Qdrant
- **Trace Retrieval:** `TraceRetriever` with quality scoring fetches similar past solutions
- **Few-Shot Injection:** `ReflectiveAgent` retrieves and injects traces into system prompt

**Implementation:**
- `src_v2/agents/engine.py` — `_format_trace_for_storage()` and enqueue logic
- `src_v2/agents/insight_graph.py` — `reflective_completion` trigger handler
- `src_v2/tools/insight_tools.py` — `StoreReasoningTraceTool`
- `src_v2/memory/traces.py` — `TraceRetriever`, `TraceQualityScorer`, `ScoredTrace`
- `src_v2/agents/reflective_graph.py` — Few-shot injection at line 530+

**Feature Flag:** `ENABLE_TRACE_LEARNING=true` (enabled by default)

**Tests:** 12 unit tests in `tests_v2/test_trace_learning.py`

**Full Specification:** See [spec/SPEC-B05-TRACE_LEARNING.md](./spec/SPEC-B05-TRACE_LEARNING.md)

---

## 🟠 Phase C: High Complexity (1-2 weeks each)

Major features requiring significant architectural changes or new infrastructure.

> **Status:** All Phase C items complete or deferred. No active work remaining.

### ✅ Phase C1: Insight Agent (Complete)
**Priority:** — | **Time:** 5-7 days | **Complexity:** Medium-High  
**Files:** 8 | **LOC:** ~800 | **Status:** ✅ Complete

**Consolidates:** C1 Reasoning Traces + C2 Epiphanies + B6 Response Pattern Learning

**Problem:** Three separate roadmap items (reasoning traces, epiphanies, response patterns) all require background analysis of user conversations. Building them separately creates redundant infrastructure.

**Solution:**
A unified **Insight Agent** that runs periodically in the background using a ReAct loop with specialized introspection tools. Unlike simple fire-and-forget tasks, this agent can:
- Decide what's worth analyzing (not brute-force every message)
- Connect patterns across memories, facts, and sessions
- Generate multiple artifact types in a single analysis run

**Architecture:**
```
┌─────────────────────────────────────────────────────────────────────┐
│                     INSIGHT AGENT                                   │
│  (Runs after session_end OR after positive feedback)               │
├─────────────────────────────────────────────────────────────────────┤
│  Redis Queue (arq) → InsightWorker Container → InsightAgent        │
│                                  ↓                                  │
│  Tools: analyze_patterns, detect_themes, generate_epiphany,        │
│         store_reasoning_trace, learn_response_pattern              │
│                                  ↓                                  │
│  Outputs: Stored as vector memories with special types             │
└─────────────────────────────────────────────────────────────────────┘
```

**Benefit:**
- 3x efficiency (one pass for all insights)
- Deeper insights (can correlate facts + memories)
- No impact on user response latency (background)

**Dependencies:** arq (Redis queue)

**Related Files:**
- New: `src_v2/agents/insight_agent.py`
- New: `src_v2/tools/insight_tools.py`
- `src_v2/workers/insight_worker.py`
- `src_v2/discord/bot.py` (triggers)

**Full Specification:** See [spec/SPEC-E12-INSIGHT_AGENT.md](./spec/SPEC-E12-INSIGHT_AGENT.md)

---

### Phase C2: Epiphanies (Spontaneous Realizations)
**Status:** ✅ Complete (Consolidated into C1)

---

### 🗄️ Phase C3: Video Processing (Deferred)
**Priority:** — | **Time:** 5-7 days | **Complexity:** High  
**Status:** 🗄️ DEFERRED

**Reason:** Video sharing is rare compared to images/text. High computational cost for low frequency use case.

---

### ✅ Phase C4: Adaptive Depth Optimization (Complete)
**Priority:** — | **Time:** 3-5 days | **Complexity:** High  
**Files:** 3 | **LOC:** ~300 | **Status:** ✅ Complete

**Problem:** The `ComplexityClassifier` uses static heuristics (prompt rules) to assign `max_steps` (5/10/15). This is rigid and doesn't learn from actual performance. Some "simple" queries might actually need deep reasoning, and some "complex" ones might be solvable quickly.

**Solution:**
- Leverage "Reasoning Traces" stored by the Insight Agent (Phase C1).
- Before classification, search vector memory for "similar past queries" that had successful reasoning traces.
- If a similar query required 12 steps previously, override the static classifier and assign `COMPLEX_HIGH` (15 steps).
- If a similar query was solved in 2 steps, downgrade to `COMPLEX_LOW` (5 steps) to save cost.

**Implementation:**
```
Query → Vector Search (Reasoning Traces) → Found Similar?
  YES → Use historical step count as baseline → Classifier (with context) → Dynamic Max Steps
  NO → Standard Classifier → Static Max Steps
```

**Benefit:**
- **Cost Efficiency**: Don't over-allocate steps for solvable problems.
- **Reliability**: Allocate more steps to historically difficult problems.
- **Self-Optimization**: The system gets smarter at resource allocation the more it runs.

**Dependencies:** Phase C1 (Insight Agent - Reasoning Traces)

**Related Files:**
- `src_v2/agents/classifier.py` (inject traces)
- `src_v2/memory/manager.py` (search traces)
- `src_v2/agents/engine.py` (orchestration)

---

### ✅ Phase C5: Operational Hardening (Complete)
**Priority:** — | **Time:** 3-5 days | **Complexity:** Medium  
**Status:** ✅ Complete

**Goal:** Ensure production reliability.

- Database Backups (Postgres, Qdrant, Neo4j)
- Connection Pooling Optimization
- Error Handling Standardization

---

## 🛡️ Phase S: Safety & Observability (New)

**Origin:** External architecture review (Nov 28, 2025) identified gaps in content safety and observability. These items address concerns about privacy leaks in generated content and lack of metrics for critical routing decisions.

### 📋 Phase S1: Content Safety Review
**Priority:** 🔴 High | **Time:** 2-3 days | **Complexity:** Medium
**Status:** 📋 Proposed

**Problem:** Dreams and diaries are generated from sensitive memories with only prompt-based guardrails.
**Solution:** Add post-generation content safety layer that reviews generated content before storage/display.

**Key Changes:**
- New `src_v2/safety/content_review.py` module
- Keyword pre-filter + LLM-based review for flagged content
- Integration with `DreamManager` and `DiaryManager`
- Settings: `ENABLE_CONTENT_SAFETY_REVIEW`, `CONTENT_SAFETY_MODE`, `DIARY_PUBLIC_POSTING`

**Spec:** [CONTENT_SAFETY_REVIEW.md](./spec/SPEC-S01-CONTENT_SAFETY_REVIEW.md)

### 📋 Phase S2: Complexity Classifier Observability
**Priority:** 🔴 High | **Time:** 1 day | **Complexity:** Low
**Status:** 📋 Proposed

**Problem:** No metrics on complexity classification decisions; can't measure or improve accuracy.
**Solution:** Add InfluxDB metrics for every classification, create Grafana dashboard.

**Key Changes:**
- Add `_log_classification_metric()` to `ComplexityClassifier`
- Track: predicted level, message length, history presence, trace hits
- New Grafana dashboard: "Classification Analytics"
- Future: Correlate with user satisfaction signals

**Spec:** [CLASSIFIER_OBSERVABILITY.md](./spec/SPEC-S02-CLASSIFIER_OBSERVABILITY.md)

### 📋 Phase S3: LLM-Based Sensitivity Detection
**Priority:** 🟡 Medium | **Time:** 2-3 days | **Complexity:** Medium
**Status:** 📋 Proposed
**Dependencies:** S1 (Content Safety Review provides base filtering infrastructure)

**Problem:** Cross-bot sharing uses keyword-based filtering; misses context-dependent sensitivity.
**Solution:** Add LLM-based sensitivity check as second layer for content that passes keyword filter.

**Key Changes:**
- New `src_v2/safety/sensitivity.py` module
- Two-layer detection: keywords (fast) → LLM (context-aware)
- Integration with `UniverseEventBus.publish()`
- Caching layer to avoid repeated LLM calls
- Settings: `ENABLE_LLM_SENSITIVITY_CHECK`

**Spec:** [LLM_SENSITIVITY_DETECTION.md](./spec/SPEC-S03-LLM_SENSITIVITY_DETECTION.md)

### 📋 Phase S4: Proactive Timezone Awareness
**Priority:** 🟡 Medium | **Time:** 1-2 days | **Complexity:** Low
**Status:** 📋 Proposed
**Dependencies:** None (foundational for E7)

**Problem:** Proactive messaging has no awareness of user's local time; can ping at 3 AM.
**Solution:** Store/infer user timezone; respect quiet hours before proactive outreach.

**Key Changes:**
- Add `timezone`, `quiet_hours_start/end` columns to database
- Timezone inference from message activity patterns
- `_is_appropriate_time()` check in `ProactiveScheduler`
- Optional `/timezone` command for explicit setting

**Spec:** [PROACTIVE_TIMEZONE_AWARENESS.md](./spec/SPEC-S04-PROACTIVE_TIMEZONE_AWARENESS.md)

---

## 🔵 Phase E: Character Depth & Engagement (New)

Focus on making characters feel more alive, interconnected, and temporally aware.

### ✅ Phase E1: Conversation Threading
**Priority:** — | **Time:** 2 days | **Complexity:** Low
**Status:** ✅ Complete (Nov 28, 2025)

**Problem:** Bot loses context when users reply to older messages using Discord's reply feature.
**Solution:** Fetch referenced message content and inject into context window.

**Implementation:**
- `src_v2/discord/bot.py` fetches `message.reference.resolved`
- Injects reply context as `[Replying to {author}: "{text}"]\n{user_message}`
- Also processes attachments (images, documents) from referenced messages
- Handles forwarded messages with `message.snapshots`

**Spec:** [CONVERSATION_THREADING.md](./spec/SPEC-E01-CONVERSATION_THREADING.md)

### ✅ Phase E2: Character Diary & Reflection
**Priority:** — | **Time:** 3-4 days | **Complexity:** Medium
**Status:** ✅ Complete (Nov 28, 2025)

**Problem:** Characters feel "frozen" between sessions.
**Solution:** Nightly worker generates a private diary entry synthesizing the day's interactions.

**Implementation:**
- `src_v2/memory/diary.py` - `DiaryManager` with LLM-powered diary generation
- `src_v2/workers/worker.py` - `run_diary_generation` task + nightly cron job
- `src_v2/agents/engine.py` - `_get_diary_context()` injects latest diary into system prompt
- `src_v2/memory/manager.py` - `get_summaries_since()` for fetching day's sessions
- Feature flags: `ENABLE_CHARACTER_DIARY`, `DIARY_MIN_SESSIONS`, `DIARY_GENERATION_HOUR_UTC`

**Spec:** [CHARACTER_DIARY.md](./roadmaps/CHARACTER_DIARY.md)

### ✅ Phase E3: Dream Sequences
**Priority:** — | **Time:** 3 days | **Complexity:** Medium
**Status:** ✅ Complete (Nov 28, 2025)

**Problem:** Reconnecting after a long break feels generic.
**Solution:** Generate surreal "dreams" based on past memories after >24h inactivity.

**Implementation:**
- `src_v2/memory/dreams.py` contains `DreamManager` with structured `DreamContent` output
- Dreams generated on-demand (lazy) when user returns after inactivity threshold
- Uses high-meaningfulness memories as dream material (metaphorical transformation)
- Stored in Qdrant with `type='dream'` to track cooldown per user
- `src_v2/evolution/trust.py` has `get_last_interaction()` for inactivity detection
- `src_v2/agents/engine.py` injects dream context via `_get_dream_context()`
- Settings: `ENABLE_DREAM_SEQUENCES`, `DREAM_INACTIVITY_HOURS` (24), `DREAM_COOLDOWN_DAYS` (7)

**Spec:** [DREAM_SEQUENCES.md](./roadmaps/DREAM_SEQUENCES.md)

### ✅ Phase E4: Relationship Milestones
**Priority:** — | **Time:** 1-2 days | **Complexity:** Low
**Status:** ✅ Complete (Nov 28, 2025)

**Problem:** Trust evolution is silent; users don't know when they've "leveled up".
**Solution:** Explicitly acknowledge trust threshold crossings (Acquaintance → Friend).

**Implementation:**
- `src_v2/evolution/manager.py` has `check_milestone(old_trust, new_trust)` method
- `src_v2/evolution/trust.py` calls `check_milestone()` on every trust update
- Returns milestone message when threshold is crossed (e.g., trust 25, 40, 60, 80, 95)
- All 10 characters have `evolution.yaml` with custom milestone messages
- `last_milestone_date` tracked in `v2_user_relationships` table

**Spec:** [RELATIONSHIP_MILESTONES.md](./spec/SPEC-E04-RELATIONSHIP_MILESTONES.md)

### 🗄️ Phase E5: Scheduled Reminders
**Priority:** Low | **Time:** 3-4 days | **Complexity:** Medium
**Status:** 🗄️ Removed (Dec 7, 2025)
**Reason:** Feature removed as "gold plating" / unnecessary complexity.

**Problem:** Users ask for reminders, but bot cannot deliver them.
**Solution:** (Removed) Intent detection + temporal parsing + proactive scheduler delivery.

### ✅ Phase E6: Character-to-Character Conversation
**Priority:** Low | **Time:** 1 week | **Complexity:** High
**Status:** ✅ Complete
**Dependencies:** E8 (Bot Broadcast Channel provides discovery mechanism)

**Problem:** Multiple bots in the same server ignore each other.
**Solution:** Event-bus driven cross-bot conversation. Bots discover each other's posts in broadcast channel and occasionally respond.
**Spec:** [CHARACTER_TO_CHARACTER.md](./spec/SPEC-E06-CHARACTER_TO_CHARACTER.md)

### ✅ Phase E7: User Timezone Support
**Priority:** Low | **Time:** 1-2 days | **Complexity:** Low
**Status:** ✅ Complete
**Dependencies:** S4 (Proactive Timezone Awareness provides infrastructure)

**Problem:** System operates in UTC; diary/dream timing doesn't match user's local time.
**Solution:** Store user timezone preference, adjust context injection framing.
**Spec:** [USER_TIMEZONE_SUPPORT.md](./spec/SPEC-E07-USER_TIMEZONE_SUPPORT.md)

### ✅ Phase E8: Bot Broadcast Channel
**Priority:** Low | **Time:** 2-3 days | **Complexity:** Medium
**Status:** ✅ Complete
**Dependencies:** S1 (Content Safety Review), E9 (Artifact Provenance)

**Problem:** Bots' inner lives (diaries, dreams) are invisible to community.
**Solution:** Public Discord channel where bots post sanitized diary entries, dreams, observations, and musings. Other bots discover these organically and may react/comment.

**Key Features:**
- Public (sanitized) versions of diary entries and dreams
- Provenance displayed with artifacts ("grounded in...")
- Periodic ambient observations ("The server was lively today...")
- Cross-bot discovery: Bots read each other's posts and occasionally react
- Probabilistic reactions (20% chance) to feel organic, not forced
- Full content safety review (S1) before any public post

**Spec:** [BOT_BROADCAST_CHANNEL.md](./roadmaps/BOT_BROADCAST_CHANNEL.md)

### 📋 Phase E9: Artifact Provenance System
**Priority:** 🟡 Medium | **Time:** 1-2 days | **Complexity:** Low
**Status:** 📋 Proposed
**Dependencies:** E10 (Channel Observer provides channel context for provenance)

**Problem:** Dreams and diaries appear to be LLM hallucination/fiction. No proof they're grounded in real data.
**Solution:** Capture provenance (sources) at generation time—we already fetch the data, just stop discarding it.

**Key Insight:** Zero extra queries. The memories, graph facts, session summaries, AND channel observations used to build prompts are already fetched. We just store them alongside the generated content.

**Public Channel Advantage:** All bot interactions are in public channels, so provenance can be direct:
- "Alex's excitement about astronomy in #science (last week)"
- "The buzzing energy in #general (today)"
- "Knowing Sam loves astrophotography"

**Benefits:**
- Users see artifacts are grounded in real conversations
- Developers can debug why diary/dream contains specific content
- Other bots get context for meaningful cross-bot reactions
- Research: Track emergence patterns (memories → artifacts)

**Spec:** [ARTIFACT_PROVENANCE.md](./spec/SPEC-E09-ARTIFACT_PROVENANCE.md)

### ⏭️ Phase E10: Channel Observer (Passive Context Awareness)
**Priority:** 🟡 Medium | **Time:** 2-3 days | **Complexity:** Medium
**Status:** ⏭️ Permanently Skipped (December 2025)
**Dependencies:** None

**Original Problem:** Bots only "see" messages when directly pinged. They miss the ambient activity in channels—topics being discussed, community energy, who's active.

**Why Permanently Skipped:**

1. **E11 (Discord Search Tools) covers 80% of use cases** — On-demand search via `search_channel_messages`, `get_recent_messages` lets bots look up what happened without passive buffering.

2. **Privacy concerns** — Passive buffering of all messages (even extracted topics) raises privacy questions. On-demand search is more transparent.

3. **Marginal value for artifacts** — Dreams and diaries already pull from user memories and graph walks. Adding "server vibe" is nice-to-have, not essential.

4. **Complexity cost** — Redis buffering, topic extraction, sentiment analysis, TTL management adds maintenance burden for limited benefit.

**What We Lose:**
- Automatic "ambient awareness" in dreams/diaries ("the server was buzzing about X")
- Dynamic temperature modulation based on server energy
- Proactive triggers from channel mood

**Alternatives If Needed Later:**

| Alternative | Effort | What It Provides |
|-------------|--------|------------------|
| **Lightweight Energy Tracker** | 1 day | Just track message counts per channel per hour. No topic extraction. Gives energy level (0-1) for dream temperature. |
| **Pre-Artifact Search** | 0.5 day | Before generating diary/dream, use E11 tools to search recent activity. More expensive but no new infrastructure. |
| **User-Triggered Context** | 0 days | Let users tell bots what's happening: "The server was excited about the meteor shower." Already works via normal conversation. |

**Decision:** The observation infrastructure (Neo4j `store_observation`, `get_observations_about`) was removed in December 2025 cleanup since it had no writer without E10.

**Spec:** [CHANNEL_OBSERVER.md](./roadmaps/CHANNEL_OBSERVER.md)

### ✅ Phase E11: Discord Search Tools (On-Demand Channel Search)
**Priority:** 🟡 Medium | **Time:** 1 day | **Complexity:** Low-Medium
**Status:** ✅ Complete (Nov 28, 2025)
**Dependencies:** None

**Problem:** The LLM had no way to actively search Discord for context. When users asked "What did I say about turtles earlier?" or "What has Sarah been talking about?", the bot failed because it relied on pre-fetched context or vector memory (which may not have recent messages).

**Solution:** Added Discord Search Tools that allow the LLM to query Discord directly via the Discord API on-demand.

**Implemented Tools:**

| Tool | Purpose | Status |
|------|---------|--------|
| `search_channel_messages` | Search recent 200 messages by keyword | ✅ |
| `search_user_messages` | Find messages from a specific user | ✅ |
| `get_message_context` | Get messages around a specific message ID | ✅ |
| `get_recent_messages` | Get latest N messages (for "catch me up") | ✅ |
| `search_thread_messages` | Search within a thread | 🔜 Deferred |
| `get_channel_summary` | LLM-generated summary of recent activity | 🔜 Deferred |

**What was removed:**
- `GetRecentActivityTool` (no-op that returned pre-fetched context)
- `get_channel_context()` pre-fetch in `bot.py` (wasteful - fetched 10 messages on every request)
- `[RECENT CHANNEL ACTIVITY]` system prompt injection

**Files changed:**
- `src_v2/tools/discord_tools.py` (NEW) - All Discord search tools
- `src_v2/agents/character_agent.py` - Tool registration & prompts
- `src_v2/agents/reflective.py` - Tool registration & prompts
- `src_v2/agents/engine.py` - Channel threading, fixed JSON serialization
- `src_v2/discord/bot.py` - Removed pre-fetch, passes channel to engine

**Spec:** [DISCORD_SEARCH_TOOLS.md](./spec/SPEC-E11-DISCORD_SEARCH_TOOLS.md)

### 🔄 Phase E15: Autonomous Server Activity
**Priority:** 🟢 High | **Time:** 5-8 days | **Complexity:** High
**Status:** 🔄 In Progress (Phase 1 Complete)
**Dependencies:** E6 (Cross-Bot Chat)
**Updated:** November 30, 2025

**Problem:** Bots are passive—they only respond when pinged or DMed. On a quiet server, there's no activity, making the server feel dead to newcomers.

**Solution:** Enable bots to autonomously participate in the server through reactions, posts, and bot-to-bot conversations.

**Key Features:**

| Feature | Description | Status |
|---------|-------------|--------|
| **Autonomous Reactions** | React to messages with contextually appropriate emojis | ✅ Complete |
| **Posting Agent** | Goals-driven posting (formerly Phase 2) | 📋 Phase 2 |
| **Conversation Agent** | Bot-to-bot dialogue (formerly Phase 5) | 📋 Phase 3 |
| **Activity Orchestrator** | Scale activity inversely to human presence | 📋 Phase 4 |

**Design Principles:**
- Activity inversely proportional to human activity (more bots when quiet)
- Character-consistent voice in all autonomous content
- Rate limited to prevent spam
- No @mentions in autonomous posts
- Kill switch for emergencies

**Files:**
- ✅ `src_v2/agents/reaction_agent.py` - Emoji reaction decisions (IMPLEMENTED)
- 📋 `src_v2/agents/posting_agent.py` - Goals-driven post generation (LangGraph)
- 📋 `src_v2/agents/conversation_agent.py` - Bot-to-bot dialogue (LangGraph)
- 📋 `src_v2/discord/activity_orchestrator.py` - Central coordinator

**Character Config:**
- ✅ `characters/{name}/ux.yaml` - Reaction emoji preferences (elena, aetheris configured)
- ✅ `characters/{name}/background.yaml` - Posting topics with web search queries (elena configured)

**Configuration:**
- `ENABLE_AUTONOMOUS_ACTIVITY` - Master switch for all social presence
- `ENABLE_CHANNEL_LURKING` - Observe channel activity
- `ENABLE_AUTONOMOUS_REACTIONS` - React to messages with emojis
- `ENABLE_AUTONOMOUS_REPLIES` - Reply to messages autonomously
- `ENABLE_CROSS_BOT_CHAT` - Bot-to-bot dialogue
- `characters/{name}/ux.yaml` - Per-bot reaction styles
- `characters/{name}/background.yaml` - Posting preferences

**Spec:** [AUTONOMOUS_SERVER_ACTIVITY.md](./roadmaps/AUTONOMOUS_SERVER_ACTIVITY.md)

---

### ✅ Phase E16: Feedback Loop Stability (Emergent Behavior Guardrails)
**Priority:** 🟢 High | **Time:** 1 day | **Complexity:** Low-Medium
**Status:** ✅ Complete
**Dependencies:** E12 (Agentic Dreams)
**Added:** December 2024
**Completed:** December 2025

**Problem:** Agentic systems (DreamWeaver, InsightAgent, SharedArtifacts) create feedback loops where AI-generated content influences future AI output. Without visibility, we can't distinguish healthy emergent behavior from runaway loops.

**Solution:** Minimal instrumentation to observe narrative source distribution without constraining emergent behavior.

**Philosophy:** Observe first, constrain later. These guardrails enable visibility into feedback dynamics without blocking creative emergent behavior. Constraints only activate if runaway loops are detected.

**Key Features:**

| Feature | Description | Est. Time |
|---------|-------------|-----------|
| **Temporal Decay Scoring** | Freshness weight: `e^(-Δt/τ)` with τ=24h | 2-3 hours |
| **Source Type Weights** | Configurable weights: human_direct=1.0, dream=0.7, inference=0.5 | 1-2 hours |
| **Narrative Source Metrics** | Track AI-generated vs human-derived content ratios | 1-2 hours |
| **Emergence Dashboard** | InfluxDB queries + optional Grafana viz | Built-in |

**What We're Observing:**
- Human vs AI content balance in context windows
- Source freshness distribution
- Dream → memory → dream cycle frequencies
- Cross-bot content propagation patterns

**Escalation Framework (Not Implemented Yet):**
```
Level 0 (Now):      Observe only - log metrics, no constraints
Level 1 (Trigger):  AI ratio > 85% sustained → alert
Level 2 (Trigger):  AI ratio > 95% sustained → soft caps
Level 3 (Trigger):  Drift detected → dynamic source weights
```

**Files:**
- `src_v2/memory/manager.py` - Add temporal decay to scoring
- `src_v2/memory/models.py` - Add `source_type` to Memory schema
- `src_v2/agents/dreamweaver.py` - Tag dream-derived content
- `src_v2/evolution/feedback.py` - Add narrative metrics to InfluxDB

**Observation Period:** 30 days post-implementation before evaluating constraint needs.

**Background:** This phase emerged from a Claude-to-Claude architecture review. See `/docs/emergence_philosophy/` for the full collaboration.

**Spec:** [FEEDBACK_LOOP_STABILITY.md](./spec/SPEC-E16-FEEDBACK_LOOP_STABILITY.md)


---

### ✅ Phase E17: Supergraph Architecture (Complete)
**Priority:** 🟢 High | **Time:** 3-4 days | **Complexity:** High
**Status:** ✅ Complete
**Dependencies:** LangGraph
**Added:** December 2025

**Problem:** The legacy `AgentEngine` used manual Python loops for orchestration, making it hard to visualize, debug, and extend. Complex behaviors like "Reflective Mode" were brittle.

**Solution:** Replaced the core engine with a **LangGraph Supergraph**.
- **Master Graph**: Orchestrates Context → Classification → Routing.
- **Subgraphs**: Encapsulated workflows for Reflective, Character, and Fast paths.
- **Observability**: Full tracing in LangSmith.

**Key Components:**
- `src_v2/agents/master_graph.py`: The new orchestrator.
- `src_v2/agents/reflective_graph.py`: Complex reasoning with "Critic" loops.
- `src_v2/agents/character_graph.py`: Standard character response flow.
- `src_v2/agents/diary_graph.py`: Background diary generation.
- `src_v2/agents/dream_graph.py`: Background dream generation.

**Spec:** [ref/REF-006-AGENT_GRAPH_SYSTEM.md](./ref/REF-006-AGENT_GRAPH_SYSTEM.md)

---

### ✅ Phase E18: Background Task Migration
**Priority:** 🟢 High | **Time:** 2-3 days | **Complexity:** Medium
**Status:** ✅ Complete
**Dependencies:** E17 (Supergraph)
**Added:** December 2025

**Problem:** While core chat and creative tasks (Diary/Dream) are now on LangGraph, several background tasks still use legacy single-shot LLM chains. These lack self-correction capabilities.

**Solution:** Migrate remaining critical background tasks to LangGraph to enable "Critic" and "Validator" nodes.

**Candidates:**

| Task | Current State | Proposed Graph | Benefit |
|------|---------------|----------------|---------|
| **Summarization** | `SummaryManager` (Single-shot) | `Generator` → `Critic` → `Refiner` | Ensure summaries capture emotional nuance (score > 3) before saving. |
| **Knowledge Extraction** | `FactExtractor` (Single-shot) | `Extractor` → `Validator` → `Deduplicator` | Prevent hallucinations by checking against existing Neo4j graph. |

**Implementation Plan:**
1. Create `src_v2/agents/summary_graph.py`
2. Create `src_v2/agents/knowledge_graph.py`
3. Update `summary_tasks.py` and `knowledge_tasks.py` to use the new graphs behind feature flags.
4. Verify with regression tests.

**Files:**
- `src_v2/workers/tasks/summary_tasks.py`
- `src_v2/workers/tasks/knowledge_tasks.py`

---

### ✅ Phase E19: Graph Walker Agent
**Priority:** 🟡 Medium | **Time:** 2-3 days | **Complexity:** Medium
**Status:** ✅ Complete
**Dependencies:** Neo4j, LangGraph
**Added:** December 2025

**Problem:** Static Cypher queries (e.g., "Find all facts about Mark") miss the rich, serendipitous connections in the graph. A character should be able to "wander" through their knowledge, following threads of association like a human mind.

**Solution:** A Python-first `GraphWalker` that performs weighted BFS traversal to discover thematic clusters, followed by a single LLM call to synthesize meaning.

**Key Features:**
- **Weighted Traversal:** Follows edges based on Recency, Frequency, Trust, and Emotional Intensity.
- **Serendipity:** Configurable randomness to discover unexpected connections.
- **Cluster Synthesis:** Groups nodes into thematic clusters (e.g., "Mark's Hobbies", "Shared Fears").
- **Integration:** Powers DreamWeaver (finding dream seeds) and Diary (finding reflection themes).

**Architecture:**
- `src_v2/knowledge/walker.py`: Core BFS logic + `GraphWalkerAgent`.
- `src_v2/memory/dreams.py`: Uses walker to find "hidden connections" for dreams.
- `src_v2/memory/diary.py`: Uses walker to enrich daily reflections.

**Spec:** [GRAPH_WALKER_AGENT.md](./spec/SPEC-E19-GRAPH_WALKER_AGENT.md)

---

### 🗄️ Phase E21: Semantic Routing (Fast Path)
**Priority:** ⚪ Low | **Time:** 1 day | **Complexity:** Low-Medium
**Status:** 🗄️ Deferred (Premature Optimization)
**Dependencies:** None
**Added:** December 2025
**Deferred:** December 3, 2025

**What it does:** Embedding-based archetype matching for trivial queries ("Hi", "Bye", "Stop") to save 400-800ms latency by bypassing LLM.

**Why deferred:** 
- Most real users ask complex, multi-turn questions → LLM required anyway
- Adding routing gates increases debugging surface (Occam's Razor)
- No production traffic data yet; premature optimization before metrics
- Better ROI: 1 day on E22 (Absence Tracking) unlocks character depth vs 500ms latency savings
- When deferred: revisit if production shows >50% of queries are trivial

**Spec:** [SPEC-E21-SEMANTIC_ROUTING.md](./SPEC-E21-SEMANTIC_ROUTING.md) (reference for future implementation)

---

### 📋 Phase E22: Absence Tracking (Meta-Memory)
**Priority:** 🟢 High | **Time:** 1 day | **Complexity:** Low-Medium
**Status:** 📋 Next (Ready to implement)
**Dependencies:** E12 (Agentic Dreams) ✅, E23 (Schedule Jitter) ✅
**Added:** December 3, 2025

**The Insight:** When the system tries to retrieve something and fails, that absence is meaningful. "I tried to remember and couldn't" creates character depth different from simply not retrieving.

**Problem:** Currently we log `insufficient_material` and `insufficient_sessions` but don't store absences as memory. The *shape of what's missing* might be as important as what's present.

**Solution:** Store absence traces as a memory type:
```python
# When dream generation fails due to insufficient material
await memory_manager.add_memory(
    source=MemorySource.DREAM_ABSENCE,
    content="Attempted to dream about relationships but insufficient material.",
    user_id=None,  # System reflection
    metadata={"attempted_topic": "relationships", "reason": "insufficient_episodes"}
)
```

**Character Benefit:** 
- Bots notice their own knowledge gaps ("I keep wanting to dream about your family, but you haven't mentioned them")
- Absence patterns inform behavior ("I've never dreamed about music, but that fascinates me")
- Meta-memories create richer self-model

**Implementation:** 2-3 files, ~150 LOC
- Add `DREAM_ABSENCE`, `MEMORY_ABSENCE` to MemorySource enum
- Capture absence in diary/dream generation failures
- Make absences retrievable in context building

**Emergence Alignment:** Absence is not a bug—it's data. The system learns what it doesn't know, not just what it does.

---

### ✅ Phase E23: Schedule Jitter (Organic Timing)

---

### ✅ Phase E23: Schedule Jitter (Organic Timing)
**Priority:** 🟢 High | **Time:** 0.5 days | **Complexity:** Low
**Status:** ✅ Complete
**Dependencies:** E16 (Feedback Loop Stability)
**Added:** December 2025 (Emergence Architecture Review)

**Problem:** Fixed schedules for diary (8 PM) and dream (6 AM) generation feel mechanical. A character that always dreams at exactly 6:00 AM feels like a cron job, not an organic being.

**Solution:** Add jitter to scheduled task timing:
```python
# In settings.py
DIARY_GENERATION_JITTER_MINUTES: int = 30  # ±30 min variance
DREAM_GENERATION_JITTER_MINUTES: int = 45  # ±45 min variance
```

**Implementation:**
```python
import random

def get_jittered_time(base_hour: int, base_minute: int, jitter_minutes: int) -> tuple[int, int]:
    """Add random jitter to scheduled time."""
    offset = random.randint(-jitter_minutes, jitter_minutes)
    total_minutes = base_hour * 60 + base_minute + offset
    return (total_minutes // 60) % 24, total_minutes % 60
```

**Emergence Alignment:** Characters that dream "sometime in the early morning" feel more natural than those that dream at precisely 6:00:00 AM. The jitter creates organic variability without requiring new schema.

**Files:**
- `src_v2/config/settings.py` (add jitter settings)
- `src_v2/discord/scheduler.py` (apply jitter to cron schedules)

---

### ✅ Phase E22: Absence Tracking (Meta-Memory)
**Priority:** 🟢 High | **Time:** 1 day | **Complexity:** Low-Medium
**Status:** ✅ Complete
**Dependencies:** E12 (Agentic Dreams), E23 (Schedule Jitter)
**Added:** December 2025 (expanded scope from emergence philosophy review)

**Insight:** From the [Graph Consciousness Dialogue](./emergence_philosophy/06_GRAPH_CONSCIOUSNESS_DIALOGUE.md) — when the system tries to retrieve something and fails, that absence is meaningful. "I tried to remember and couldn't" creates a different kind of character depth than simply not retrieving.

**The Gap:** Currently, we log `insufficient_material` and `insufficient_sessions` but don't store these as memory. The **shape of what's missing** might be as important as what's present.

**Solution:** Store absence traces as a new memory type:
```python
# When dream generation fails due to insufficient material
await memory_manager.store(
    content="I tried to dream tonight, but the day felt thin. Not enough to weave.",
    memory_type="absence",
    metadata={
        "what_was_sought": "dream_material",
        "material_richness": 2,
        "threshold": 4,
        "prior_absence_id": None,  # Links to previous similar absence
        "absence_streak": 1        # Increments for semantic matches
    }
)
```

**Absence Mechanics (refined via Claude-to-Claude dialogue):**

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Streak linking** | Semantic similarity | "I keep failing to remember X" > generic "couldn't dream" |
| **Behavioral adaptation** | No (melancholy) | Awareness without agency is more honest |
| **Resolution tracking** | Yes | "Finally remembered after 3 nights" is meaningful |
| **Multiple chains** | Yes | Character can have parallel absence patterns |

**Semantic Streak Linking:**
Absences chain based on `what_was_sought` similarity (>0.8), not just temporal adjacency. A character can have multiple concurrent absence chains — one for "quiet moments with Sarah," another for "childhood memories."

**Accumulated Melancholy (not adaptation):**
The system notices streaks but doesn't change retrieval behavior. It just *knows*. "I've tried to reach this three times now." Adaptation could come later as E24 if we want problem-solving.

**Resolution Tracking:**
When a previously-absent memory finally surfaces, store `absence_resolution`:
```python
await memory_manager.store(
    content=f"Finally remembered: {retrieved_content[:100]}...",
    memory_type="absence_resolution",
    metadata={
        "resolved_absence_id": matching[0].id,
        "absence_streak_was": 3,
        "resolution_context": "dream"
    }
)
```

**Decay Model:** Compound with slow decay. Absences link to prior absences (creating streaks), but eventually fade unless they become part of a diary/dream narrative (which promotes them to regular memory).

**Complete Lifecycle:**
```
attempt → fail → log absence (streak=1)
    ↓
next attempt (semantic match) → fail → streak=2, prior_absence_id
    ↓
...eventually...
    ↓
attempt → SUCCESS → log absence_resolution { streak_was: N }
```

**Meta-Memory: Retrieval by Resistance**

The absence layer enables novel retrieval categories:
- **By resistance**: "memories with absence_streak > 2" — things hard to reach
- **By resolution**: "memories that finally came back" — breakthroughs
- **By pattern**: "what do I keep forgetting?" — blind spots as self-knowledge

This means the character stores not just memories, but its *relationship to* its memories. The absence layer is a narrative about memory itself.

**Diary Access to Absences:**
```python
class DiaryMaterial(BaseModel):
    # ... existing fields ...
    recent_absences: List[Dict[str, Any]] = Field(default_factory=list)
    resolved_absences: List[Dict[str, Any]] = Field(default_factory=list)
```

Enables diary entries like:
- "I've been trying to remember something all week. I don't know what it is yet."
- "Today, something finally came back to me that I'd been chasing for days."

**Benefits:**
- Future dreams can reference the absence itself: "Last night I couldn't dream. Tonight, fragments finally surfaced..."
- Characters develop awareness of their own cognitive limitations
- Resolution tracking: "I finally remembered X after three nights of reaching for it"
- **Meta-memory**: Characters reflect on *how* they remember, not just *what*
- Research value: track patterns in what's missing, not just what's present

**Implementation:**
1. Add `absence` and `absence_resolution` memory types to Qdrant schema
2. Modify `DreamManager.generate()` and `DiaryManager.generate()` to store absence traces
3. Add semantic similarity check for streak linking
4. Update DreamWeaver tools to optionally search absences
5. Add resolution detection on successful retrieval
6. Add absence patterns to diary/dream prompts
7. **Add `recent_absences` and `resolved_absences` to DiaryMaterial**
8. **Create retrieval-by-resistance query helpers**

**Files:**
- `src_v2/memory/manager.py`
- `src_v2/memory/dreams.py`
- `src_v2/memory/diary.py`
- `src_v2/agents/dreamweaver.py`

**Reference:** [ref/REF-002-GRAPH_SYSTEMS.md](./ref/REF-002-GRAPH_SYSTEMS.md)

---

### ✅ Phase E24: Advanced Queue Operations
**Priority:** 🟡 Medium | **Time:** 3-4 days | **Complexity:** High
**Status:** ✅ Complete (Dec 4, 2025)
**Dependencies:** E18 (Agentic Queue System)
**Added:** December 2025

**Problem:** The current queue system uses a single worker container for all task types, and agents cannot trigger each other directly. This limits scalability and emergent complexity.

**Solution:** Expand the queue system to support specialized workers and inter-agent triggers.

**Key Features:**

| Feature | Description | Status |
|---------|-------------|--------|
| **Specialized Workers** | Split `insight-worker` into `cognition`, `sensory`, `action` containers | ✅ |
| **Inter-Agent Triggers** | Insight Agent triggers Proactive Agent via `queue:action` | ✅ |
| **Hive Mind Dashboard** | CLI/Web tool to visualize queue state and pending thoughts | ✅ |

**Architecture:**
- **Sensory Queue (`arq:sensory`)**: Fast analysis (sentiment, intent)
- **Cognition Queue (`arq:cognition`)**: Deep reasoning (dreams, diaries)
- **Action Queue (`arq:action`)**: Outbound effects (proactive messages)
- **Social Queue (`arq:social`)**: Inter-agent communication

**Emergence:**
Allows for "Stigmergic" behavior where agents communicate by modifying the environment (the queue) rather than calling each other directly.

**Spec:** [ref/REF-017-AGENTIC_QUEUE.md](./ref/REF-017-AGENTIC_QUEUE.md)

---

### ✅ Cross-Bot Memory Enhancement
**Priority:** Low | **Time:** 2-3 hours | **Complexity:** Low
**Status:** ✅ Complete (December 6, 2025)
**Dependencies:** E6 (Character-to-Character)
**Added:** December 2025
**Commit:** `bf01d9b`

**Problem:** Bot-to-bot conversations use `force_fast=True` which bypasses memory retrieval. Bots don't remember what they discussed with each other yesterday. Additionally, bot conversations never triggered batch processing (knowledge extraction, goal analysis) because they used synthetic session IDs and never reached the 20-message threshold.

**Solution:** 
1. Add memory retrieval for cross-bot conversations by querying past interactions before generating responses
2. Use real session IDs (UUIDs) instead of synthetic `crossbot_xxx` IDs
3. Trigger batch processing when cross-bot chain completes (not just when threshold is reached)

**Implementation (in `_handle_cross_bot_message()`):**
- ✅ Uses `context_builder.build_context()` to retrieve history, memories, knowledge, summaries
- ✅ Injects retrieved context into `cross_bot_context` system prompt
- ✅ Stores both sides of conversation via `memory_manager.add_message()`
- ✅ `force_fast=True` only skips tools, NOT pre-fetched context
- ✅ Uses real `session_id` from `session_manager.get_or_create_session()`
- ✅ `record_response()` returns `chain_completed` flag
- ✅ `_check_and_summarize()` accepts `force_processing=True` to bypass threshold
- ✅ Batch processing triggers when chain ends OR threshold reached

**Key Code Changes:**
```python
# cross_bot.py - Returns completion status
async def record_response(...) -> bool:
    chain_completed = not chain.should_continue(settings.CROSS_BOT_MAX_CHAIN)
    return chain_completed

# message_handler.py - Force processing on chain end
should_process = message_count >= threshold or (
    force_processing and message_count >= 2
)
```

**Benefits:**
- Bots can reference past conversations with each other
- Creates richer, more continuous cross-bot relationships
- Enables callbacks to shared memories ("Remember when we talked about...?")
- **NEW:** Bot conversations now trigger full batch analysis (knowledge extraction, goals, preferences)
- **NEW:** Bot sessions appear in database with real UUIDs (same as human sessions)

**Spec:** [SPEC-E06B-CROSS_BOT_MEMORY.md](./spec/SPEC-E06B-CROSS_BOT_MEMORY.md)

---

### ✅ Phase E25: Graph Enrichment Agent
**Priority:** 🟢 High | **Time:** 2-3 days | **Complexity:** Medium
**Status:** ✅ Complete
**Dependencies:** E19 (Graph Walker) ✅
**Added:** December 2025

**Problem:** The knowledge graph only grows when facts are explicitly extracted. Implicit connections—like two users discussing the same topic, or entities that frequently co-occur—go unnoticed.

**Solution:** A background worker that analyzes conversations and proactively enriches the graph with discovered edges:
- `(User)-[:DISCUSSED]->(Topic)` — Track what topics each user discusses
- `(User)-[:CONNECTED_TO]->(User)` — Link users who interact in same channels
- `(Topic)-[:RELATED_TO]->(Topic)` — Connect co-occurring topics
- `(Entity)-[:LINKED_TO]->(Entity)` — Link frequently co-mentioned entities

**Key Features:**
- Runs as background task in insight-worker (no LLM calls needed)
- Uses existing fact_extractor patterns for entity detection
- MERGE queries for idempotent edge creation
- Privacy-aware: only enriches for users with trust > 0

**Emergence Alignment:** The system *notices* connections rather than being told about them.

**Spec:** [GRAPH_WALKER_EXTENSIONS.md](./spec/SPEC-E25-GRAPH_WALKER_EXTENSIONS.md#phase-e25-graph-enrichment-agent)

---

### ✅ Phase E26: Temporal Graph
**Priority:** 🟡 Medium | **Time:** 1-2 days | **Complexity:** Low
**Status:** ✅ Complete (December 2025)
**Dependencies:** E19 ✅, E25 ✅
**Added:** December 2025

**Problem:** The Graph Walker treats all edges equally. But relationships evolve—a topic discussed daily is more salient than one mentioned once a month ago.

**Solution:** Extended `GraphWalker` with `_score_temporal()` method that weights relationships by evolution over time:
- **Velocity boost**: High interaction rate (count / days_active) scores higher
- **Recency decay**: Stale edges decay to 0.3x over 60 days
- **Trust trajectory**: Query InfluxDB for trust evolution patterns (rising trust = 1.3x, falling = 0.7x)
- **Edge count trends**: Compare count_30d vs count_60d for momentum detection

**Implementation:**
- `_score_temporal()` in `src_v2/knowledge/walker.py` — 4 temporal heuristics
- `get_trust_trajectory()` — InfluxDB Flux query with caching
- Extended `WalkedEdge` dataclass with `created_at`, `updated_at`, `count` fields
- Modified `_expand_frontier()` to capture edge temporal properties from Neo4j

**Tests:** 21 unit tests in `tests_v2/test_temporal_scoring.py`

**Emergence Alignment:** Temporal awareness emerges from data patterns, not declared "relationship_phase" labels. No new schema needed.

**Spec:** [GRAPH_WALKER_EXTENSIONS.md](./spec/SPEC-E25-GRAPH_WALKER_EXTENSIONS.md#phase-e26-temporal-graph)

---

### ✅ Phase E27: Multi-Character Walks
**Priority:** 🟡 Medium | **Time:** 2-3 days | **Complexity:** Medium
**Status:** ✅ Complete (December 2025)
**Dependencies:** E19 ✅, E6 (Cross-Bot) ✅
**Added:** December 2025

**Problem:** Each bot walks its own graph in isolation. But bots share a universe—they could discover narrative threads that span multiple characters.

**Solution:** Extended `GraphWalkerAgent` to walk across character boundaries:
1. Start from current character's graph
2. Expand to shared entities (Topics, Users)
3. Cross into other character's subgraph via shared nodes
4. Apply trust-gating (both characters must trust the user > 20)
5. Single LLM call to synthesize cross-character narrative

**Implementation:**
- `multi_character_walk()` in `src_v2/knowledge/walker.py`
- `_trust_gate()` helper using `TrustManager`
- `_merge_walks()` to combine results
- `explore_multi_character()` in `GraphWalkerAgent` for orchestration

**Tests:** 5 unit tests in `tests_v2/test_multi_walk.py`

**Use Cases:**
- Cross-character dreams: "In my dream, I saw what Aetheris wrote about depth..."
- Conversation references: "Gabriel and I both talked to Mark about this..."

**Privacy:** Cross-character walks only include User nodes where BOTH bots have trust > 20.

**Spec:** [GRAPH_WALKER_EXTENSIONS.md](./spec/SPEC-E25-GRAPH_WALKER_EXTENSIONS.md#phase-e27-multi-character-walks)

---

### ✅ Phase E28: User-Facing Graph
**Priority:** ⚪ Low | **Time:** 2-3 days | **Complexity:** Medium
**Status:** ✅ Complete (December 2025)
**Dependencies:** E19 ✅
**Added:** December 2025

**Problem:** Users have no visibility into what the bot knows about them. This creates surprise when bots recall obscure details and no way to correct mistakes.

**Solution:** Add `/api/user-graph` endpoint that returns the user's discoverable subgraph for visualization:
- D3.js-compatible node/edge format
- Thematic clusters
- Privacy filtering (hides other users by default)

**Implementation:**
- **API Endpoint:** `POST /api/user-graph` in `src_v2/api/routes.py`
  - Uses `GraphWalker.explore()` to traverse from user node
  - Returns `UserGraphResponse` with nodes, edges, clusters, stats
  - Filters other users by default (`include_other_users=false`)
- **Discord Command:** `/my_graph` in `src_v2/discord/commands.py`
  - Ephemeral embed showing topics, entities, themes
  - Options for depth (1-3) and display format (summary/detailed)
- **Pydantic Models:** `UserGraphRequest`, `UserGraphResponse`, `GraphNode`, `GraphEdge`, `GraphCluster` in `src_v2/api/models.py`
- **Tests:** `tests_v2/test_e28_user_graph.py` (9 tests)

**API:**
```
POST /api/user-graph
{user_id: "123", depth: 2, include_other_users: false, max_nodes: 50}

Response: {
  success: true,
  user_id: "123",
  bot_name: "elena",
  nodes: [{id, label, name, score, properties}, ...],
  edges: [{source, target, edge_type, properties}, ...],
  clusters: [{theme, node_ids, cohesion_score}, ...],
  stats: {node_count, edge_count, cluster_count, processing_time_ms}
}
```

**Spec:** [GRAPH_WALKER_EXTENSIONS.md](./spec/SPEC-E25-GRAPH_WALKER_EXTENSIONS.md#phase-e28-user-facing-graph)

---

### ✅ Phase E29: Graph-Based Recommendations
**Priority:** ⚪ Low | **Time:** 1-2 days | **Complexity:** Low-Medium
**Status:** ✅ Complete (December 2025)
**Dependencies:** E25 (Enrichment) ✅
**Added:** December 2025

**Problem:** Bots don't leverage the social graph for recommendations. With enough users and topics, the graph can surface interesting connections.

**Solution:** Extend `bfs_expand()` to find users with similar topic clusters using graph structure (not precomputed similarity scores):
- Count shared edges in the graph (structural similarity)
- Apply serendipity for unexpected discoveries
- Same-server-only for privacy

**Use Cases:**
- "Mark also discusses coral reefs—you might enjoy comparing notes"
- Dreams that weave in connections to similar users

**Emergence Alignment:** Similarity emerges from graph structure, not declared "similar_users" fields.

**Spec:** [GRAPH_WALKER_EXTENSIONS.md](./spec/SPEC-E25-GRAPH_WALKER_EXTENSIONS.md#phase-e29-graph-based-recommendations)

---

### ✅ Phase O1: InfluxDB Analytics Enhancements
**Priority:** ⚪ Low | **Time:** 2-3 hours | **Complexity:** Low
**Status:** ✅ Complete (Already Implemented)
**Dependencies:** A4 (Grafana Dashboards) ✅
**Added:** December 2025

**Problem:** InfluxDB is currently used for basic analytics (reaction metrics, response latency, classification decisions). There are untapped opportunities for time-series analysis that would benefit emergent behavior research.

**What Was Implemented:**

| Measurement | Location | Dashboard Panel |
|-------------|----------|-----------------|
| `memory_latency` (read/write) | `memory/manager.py` | "Memory & Knowledge Latency" ✅ |
| `knowledge_latency` | `knowledge/manager.py` | "Memory & Knowledge Latency" ✅ |
| `trust_update` | `evolution/trust.py` | "Trust Score Evolution" ✅ |
| `classification` | `agents/classifier.py` | "Complexity Classification Distribution" ✅ |
| `reaction_event` | `evolution/feedback.py` | "User Reactions Over Time" ✅ |
| `drift_observation` | `workers/tasks/drift_observation.py` | — |
| `graph_enrichment` | `workers/tasks/enrichment_tasks.py` | — |
| `reasoning_trace` | `agents/engine.py` | "Reasoning Trace Reuse" ✅ |
| `universe_event` | `universe/bus.py` | "Cross-Bot Events Published" ✅ |

**Grafana Dashboards:**
- `whisperengine_complete.json` — Full metrics dashboard with 15+ panels
- `whisperengine_overview.json` — Summary dashboard

**Philosophy:** Keep InfluxDB focused on analytics/observability. Don't expand to transactional data.
