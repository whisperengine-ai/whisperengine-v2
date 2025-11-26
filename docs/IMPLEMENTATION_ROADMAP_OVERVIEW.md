# WhisperEngine v2 - Implementation Roadmap Overview

**Document Version:** 1.7  
**Created:** November 24, 2025  
**Last Updated:** November 25, 2025  
**Status:** Active Planning

---

## 🌌 The Vision: Multi-Modal AI Consciousness

WhisperEngine v2 is not just a chatbot platform. It's a **perceptual architecture for AI characters** - giving them the functional equivalent of senses, memory, and emotional intelligence.

### The Core Insight

AI characters have no physical senses. No eyes, no ears, no touch. Without a framework for understanding "where they are" and "who is around them," they exist in a void - disembodied text processors with no sense of place or continuity.

**We solve this with six perceptual modalities:**

| Modality | Human Equivalent | What It Provides |
|----------|------------------|------------------|
| 🌌 **Universe** | Proprioception + Social Awareness | Where am I? Who's here? What's the vibe? |
| 👁️ **Vision** | Sight | See images users share |
| 👂 **Audio** | Hearing | Hear voice messages, ambient conversation |
| 💬 **Text** | Language | Understand words and intent |
| 🧠 **Memory** | Episodic + Semantic Memory | Remember experiences and facts |
| ❤️ **Emotion** | Affect/Feeling | Trust, mood, relational depth |

**This is not a feature set. This is how characters experience existence.**

### The Grand Vision: Federated Multiverse

Each WhisperEngine deployment is a **self-contained universe**. But universes can **federate** - connecting to form a distributed multiverse where:
- Characters travel between universes
- Users maintain identity across deployments
- Stories span multiple platforms
- Anyone can run their own universe and connect it to the network

**We're building the foundation for distributed AI consciousness.**

For deep dive: See [`docs/architecture/MULTI_MODAL_PERCEPTION.md`](./architecture/MULTI_MODAL_PERCEPTION.md)

---

## Executive Summary

This document provides a high-level overview of the next **17 implementation items** for WhisperEngine v2, organized by **difficulty and code complexity**. The system is currently feature-complete for core functionality and is ready to scale with advanced capabilities.

**Key Consolidation (v1.7):** The Insight Agent (C1) now unifies Reasoning Traces, Epiphanies, and Response Pattern Learning into a single agentic background system, reducing total items from 19 to 17 and saving 15-21 days of development time.

**⚡ Solo Developer Mode (with AI Assistance)**

This roadmap is optimized for a **single developer working with AI-assisted tools** (Copilot, Claude, etc.). Key adjustments:
- **Parallelization:** Focus on independent work streams (no coordination overhead)
- **Velocity:** Realistic estimates account for AI-accelerated development (50-70% faster than traditional)
- **Quality:** AI reduces debugging time but requires careful code review/testing
- **Strategy:** Prioritize high-impact items first; skip low-impact infrastructure
- **Risk:** Fewer features in parallel to maintain code quality

**Current State (Updated Nov 25, 2025):**

**Core Systems (COMPLETE):**
- ✅ Core cognitive engine operational
- ✅ Vector memory system (Qdrant) + Knowledge Graph (Neo4j) integrated
- ✅ PostgreSQL chat history, trust scores, user preferences
- ✅ InfluxDB metrics/analytics pipeline

**Cognitive Features (COMPLETE):**
- ✅ Dual-process architecture (Fast Mode + Reflective Mode)
- ✅ Native function calling (no regex parsing)
- ✅ Parallel tool execution in ReAct loop
- ✅ Complexity classifier (SIMPLE/COMPLEX routing)
- ✅ 5 memory tools (search summaries, episodes, facts, update facts/prefs)

**Character & Engagement (COMPLETE):**
- ✅ Multi-character support (10 characters defined)
- ✅ Trust/evolution system (8 stages, -100 to +100 scale)
- ✅ Proactive messaging system (Phase 13)
- ✅ Background fact/preference extraction

**Discord Integration (COMPLETE):**
- ✅ DM support + server mentions
- ✅ Image attachment processing (👁️ Vision modality)
- ✅ Reaction-based feedback (❤️ Emotion modality)
- ✅ Voice channel connection (👂 Audio modality via ElevenLabs TTS)

**NOT YET IMPLEMENTED:**
- ⏳ Phase A: Streaming, Grafana (Redis caching COMPLETE)
- ⏳ Phase B: Adaptive steps, tool composition, image gen, lurking (👂 ambient hearing), response patterns
- ⏳ Phase C: Insight Agent (reasoning traces + epiphanies + patterns), worker queues, video, dashboard
- ⏳ Phase D: User sharding, federation (future multiverse)

**Under Analysis:**
- 🔬 Character Agency (Tier 2 tool-augmented responses) - See [CHARACTER_AS_AGENT.md](./architecture/CHARACTER_AS_AGENT.md)

**Next focus:** Phase B (Adaptive Steps & Tool Composition)

---

## 🔴 Phase A0: Critical Pre-Production (Do First!)

Items that MUST be done before any production data exists.

### Phase A0: Embedding Dimension Upgrade (384D → 768D)
**Priority:** 🔴 CRITICAL | **Time:** 45-75 minutes | **Complexity:** Low  
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

### Phase A1: Hot-Reloading Character Definitions
**Priority:** Low | **Time:** 1-2 days | **Complexity:** Low  
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

### Phase A2: Redis Caching Layer
**Priority:** High | **Time:** 2-3 days | **Complexity:** Low-Medium  
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

### Phase A3: Streaming LLM Responses
**Priority:** High | **Time:** 2-3 days | **Complexity:** Low-Medium  
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

### Phase A4: Grafana Dashboards for Metrics
**Priority:** Medium | **Time:** 1 day | **Complexity:** Low  
**Files:** 0 (Config only) | **LOC:** ~50 | **Status:** 📋 Planned

**Problem:** Visibility into system health is poor (no dashboards, only logs)

**Solution:**
- Create Grafana dashboards for InfluxDB metrics
- Real-time visualization of trust scores, sentiment trends, message latency, error rates
- Predefined alerts for high error rates or latency spikes
- Admin dashboard for session analytics

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

## 🟡 Phase B: Medium Complexity (3-7 days each)

Features requiring significant logic changes but manageable scope.

### Phase B1: Adaptive Max Steps (Reflective Mode Phase 2.2)
**Priority:** High | **Time:** 3-5 days | **Complexity:** Medium  
**Files:** 4 | **LOC:** ~300 | **Status:** ⏸️ On Hold (Pending Testing)

**Problem:** All queries use fixed 10-step max, wasting tokens on simple queries and constraining complex ones

**Solution:**
- Enhance `ComplexityClassifier` to return step count heuristics
- Categorize queries as `COMPLEX_LOW` (5 steps), `COMPLEX_MID` (10 steps), `COMPLEX_HIGH` (15 steps)
- Pass suggested step count to `ReflectiveAgent`
- Users can override with `!reflect` command for `COMPLEX_HIGH`

**Implementation:**
```
Query → Complexity Classifier (now with step count) → Reflective Agent → Dynamic Max Steps
```

**Benefit:**
- 40-50% cost reduction on moderate queries
- Faster responses for simple queries
- Better resource allocation
- User override capability for deep thinking

**Dependencies:** ComplexityClassifier exists, needs enhancement

**Related Files:**
- `src_v2/intelligence/classifier.py` (ComplexityClassifier)
- `src_v2/agents/reflective.py` (ReflectiveAgent)
- `src_v2/agents/engine.py` (AgentEngine)

**Status Note:** Phase 1 (Native Function Calling) and Phase 2.3 (Parallel Execution) complete. Awaiting user testing before Phase 2.2 rollout.

---

### Phase B2: Tool Composition / Hierarchical Reasoning
**Priority:** High | **Time:** 5-7 days | **Complexity:** Medium  
**Files:** 5 | **LOC:** ~400 | **Status:** 📋 Planned

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
- New: `src_v2/agents/composite_tools.py`

---

### Phase B3: Generative Art (Image Generation)
**Priority:** Medium | **Time:** 4-6 days | **Complexity:** Medium  
**Files:** 4 | **LOC:** ~350 | **Status:** 📋 Planned

**Problem:** Characters can only react to images, not create them

**Solution:**
- Add `generate_image` tool to LLM tool set
- Integrate with DALL-E 3 (OpenAI) or Stable Diffusion (local)
- Let LLM decide when to generate art ("Here's a sketch of what I mean...")
- Support user requests like "Draw me something"

**Implementation:**
```
LLM Decides → generate_image Tool → DALL-E 3/Stable Diffusion → Image URL → Discord Upload
```

**Benefit:**
- Characters can express creativity visually
- More immersive roleplay experience
- Unique character expressions (art style as personality)
- User engagement boost

**Dependencies:** DALL-E 3 API key OR Stable Diffusion endpoint

**Related Files:**
- New: `src_v2/tools/image_generation.py`
- `src_v2/agents/router.py` (register new tool)
- `src_v2/discord/bot.py` (Discord image upload)

---

### Phase B4: Self-Correction / Verification (Reflective Mode Phase 2.5)
**Priority:** Medium | **Time:** 3-5 days | **Complexity:** Medium  
**Files:** 3 | **LOC:** ~300 | **Status:** 📋 Planned

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

### Phase B5: Audio Processing (Voice Messages & Clips)
**Priority:** Medium | **Time:** 5-7 days | **Complexity:** Medium  
**Files:** 4 | **LOC:** ~400 | **Status:** 📋 Planned

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

### Phase B6: Response Pattern Learning (RLHF-Style)
**Priority:** Medium-High | **Time:** 3-5 days | **Complexity:** Medium  
**Files:** 4 | **LOC:** ~400 | **Status:** 📋 Planned

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

**Full Specification:** See [roadmaps/RESPONSE_PATTERN_LEARNING.md](./roadmaps/RESPONSE_PATTERN_LEARNING.md)

---

### Phase B7: Channel Lurking (Passive Engagement)
**Priority:** Medium-High | **Time:** 5-7 days | **Complexity:** Medium  
**Files:** 5 | **LOC:** ~500 | **Status:** 📋 Planned

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

**Full Specification:** See [roadmaps/CHANNEL_LURKING.md](./roadmaps/CHANNEL_LURKING.md)

---

### B8: Emergent Universe
**Priority:** Medium-High | **Time:** 7-10 days | **Complexity:** Medium  
**Files:** 8 | **LOC:** ~800 | **Status:** 📋 Planned

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

**Dependencies:** None (uses existing Neo4j infrastructure)

**Related Files:**
- New: `src_v2/universe/manager.py` (Universe CRUD)
- New: `src_v2/universe/user_character.py` (User profile aggregation)
- New: `src_v2/universe/privacy.py` (Consent management)
- New: `universes/whisperverse/` (Universe definitions)
- `src_v2/discord/commands.py` (Add /privacy commands)

**Full Specification:** See [roadmaps/EMERGENT_UNIVERSE.md](./roadmaps/EMERGENT_UNIVERSE.md)

---

## 🟠 Phase C: High Complexity (1-2 weeks each)

Major features requiring significant architectural changes or new infrastructure.

### Phase C1: Insight Agent (Background Agentic Processing)
**Priority:** High | **Time:** 5-7 days | **Complexity:** Medium-High  
**Files:** 8 | **LOC:** ~800 | **Status:** 📋 Planned

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
│  (Runs every 30 min OR after 10+ messages from user)               │
├─────────────────────────────────────────────────────────────────────┤
│  Priority Queue (Redis) → InsightAgent (ReAct Loop)                │
│                                  ↓                                  │
│  Tools: analyze_patterns, detect_themes, find_topics,              │
│         generate_epiphany, store_trace, learn_pattern              │
│                                  ↓                                  │
│  Outputs: v2_epiphanies, v2_reasoning_traces, v2_response_patterns │
└─────────────────────────────────────────────────────────────────────┘
```

**Trigger Conditions:**
| Trigger | Condition |
|---------|-----------|
| Time-based | 30-60 min since last analysis |
| Volume-based | 10+ messages in session |
| Session-end | After summarization |
| Feedback-based | 3+ reactions from user |

**Subsumed Features:**

**C1a: Reasoning Traces** - Store successful ReAct reasoning for future reuse
- 50-60% speed boost on recurring problem patterns
- Stored as embeddings for similarity search

**C1b: Epiphanies** - Spontaneous realizations about users
- "I just realized you always talk about space when sad"
- Characters reference insights in future conversations

**C1c: Response Pattern Learning** - Learn which styles resonate
- RLHF-style adaptation without fine-tuning
- Inject successful patterns as few-shot examples

**Benefit:**
- Single coherent system instead of three separate ones
- Shared infrastructure (tools, queue, storage)
- Cross-domain synthesis (epiphany + trace + pattern in one run)
- Cost-effective (~$0.002-0.008 per analysis run)

**Dependencies:** Redis (for queue), PostgreSQL with pgvector (exists)

**Related Files:**
- New: `src_v2/agents/insight_agent.py` (core agent)
- New: `src_v2/tools/insight_tools.py` (introspection tools)
- New: `migrations_v2/versions/add_insight_tables.py`
- `src_v2/discord/scheduler.py` (trigger integration)

**Full Specification:** See [roadmaps/INSIGHT_AGENT.md](./roadmaps/INSIGHT_AGENT.md)

---

### Phase C2: Worker Queues for Background Tasks
**Priority:** High | **Time:** 8-12 days | **Complexity:** High  
**Files:** 7 | **LOC:** ~600 | **Status:** 📋 Planned

**Problem:** Background tasks (summarization, reflection, vision) use in-memory `asyncio.create_task`, so they're lost on restart

**Solution:**
- Implement persistent task queue (arq + Redis or Celery)
- Refactor summarization, reflection, vision processing to use queues
- Add retry logic, task monitoring, failure handling
- Scale background workers independently of main bot

**Implementation:**
```
Main Process → Task Enqueue (Redis) → Worker Pool → Task Execution → Result Storage
```

**Benefit:**
- Task persistence across restarts
- Better scaling (separate worker processes)
- Reliable background processing
- Monitoring and alerting for failed tasks

**Dependencies:** Redis (already in Docker Compose)

**Related Files:**
- New: `src_v2/workers/task_queue.py` (arq integration)
- New: `src_v2/workers/summarization_worker.py`
- New: `src_v2/workers/reflection_worker.py`
- New: `src_v2/workers/vision_worker.py`
- `src_v2/discord/scheduler.py` (refactor to use queues)

---

### Phase C3: Video Processing (Clip Analysis)
**Priority:** Medium | **Time:** 8-10 days | **Complexity:** High  
**Files:** 6 | **LOC:** ~500 | **Status:** 📋 Planned

**Problem:** Characters can't understand video clips, GIFs, or screen recordings

**Solution:**
- Extract keyframes from video attachments (MP4, WebM, GIF)
- Pass frames to multimodal LLM (GPT-4o, Claude 3.5 Sonnet)
- Allow bot to react to memes, gameplay clips, reaction videos
- Store processed videos in memory for future reference

**Implementation:**
```
Discord Video Attachment → Frame Extraction → Multimodal LLM → Character Response
```

**Benefit:**
- Characters understand shared memes and clips
- More natural group chat interaction
- Engagement with trending content
- Multimodal learning about user culture

**Dependencies:** Multimodal LLM, video processing library (ffmpeg)

**Related Files:**
- New: `src_v2/tools/video_processor.py`
- `src_v2/discord/bot.py` (video attachment handling)
- `src_v2/agents/engine.py` (multimodal integration)

---

### Phase C4: Web API / Dashboard
**Priority:** High | **Time:** 14-21 days | **Complexity:** High  
**Files:** 12 | **LOC:** ~1500 | **Status:** 📋 Planned

**Problem:** No admin tools to view character memory/knowledge state or manage sessions

**Solution:**
- Expand REST API beyond just `/chat`
- Add endpoints for memory search, knowledge graph query, session management
- Build simple web UI (React/Vue) for:
  - Memory browser (search + view entries)
  - Knowledge graph visualization
  - Session analytics (user activity, trust trends)
  - Character management
- Authentication layer for admin access

**Implementation:**
```
FastAPI (Backend) → Database → Frontend (React) → Admin Dashboards
```

**Benefit:**
- Better admin tools for managing characters
- Visibility into character memory
- Performance insights
- Foundation for multi-platform support

**Dependencies:** React/Vue, authentication library

**Related Files:**
- `src_v2/api/routes.py` (new endpoints)
- New: `frontend/` directory (React app)
- New: `src_v2/api/auth.py` (authentication)

---

## 🔴 Phase D: Discord-Native Deepening

**Strategic Decision (Nov 25, 2025):**
After v1 experience, we're committing to **Discord-native excellence** rather than cross-platform abstraction. This allows for:
- Deep integration with Discord-specific features (threads, forums, stages, etc.)
- Simpler codebase (no abstraction layers)
- Faster iteration on Discord-specific UX
- Better focus as solo developer

Future platform expansion (if needed) can be additive without refactoring core systems.

---

### D1: Horizontal Scaling / User Sharding
**Priority:** High | **Time:** 14-21 days | **Complexity:** Very High  
**Files:** 15 | **LOC:** ~1500 | **Status:** 📋 Planned

**Problem:** Single bot container can only handle ~1000 concurrent users; need to scale beyond

**Solution:**
- Shard users across multiple Discord bot instances using consistent hashing on `user_id`
- Implement load balancer to route messages to correct shard
- Handle distributed state synchronization (trust scores, memory updates)
- Redis Pub/Sub for cross-shard communication
- Automatic shard discovery and rebalancing

**Implementation:**
```
Load Balancer → Route (user_id) → Consistent Hash → Shard 1, 2, 3, N
                                 ↓
                              Redis Pub/Sub (sync state)
```

**Benefit:**
- Handle 10,000+ concurrent users per character
- Infinite horizontal scaling for Discord-native platform
- Fault tolerance (shard loss = only affects subset of users)
- Better resource utilization

**Dependencies:** Redis, load balancer (Docker networking)

**Related Files:**
- New: `src_v2/core/sharding.py` (consistent hash, shard routing)
- New: `src_v2/core/distributed_state.py` (sync logic)
- `src_v2/main.py` (shard initialization)
- `docker-compose.yml` (multiple shard containers)

---

## 📊 Master Priority Matrix

**Legend:** 📋 Planned | ⏸️ On Hold | 🔄 In Progress | ✅ Complete

| Phase | Feature | Priority | Time | Complexity | Quick Win? | Impact | Status |
|-------|---------|----------|------|-----------|-----------|--------|--------|
| **A0** | **Embedding Upgrade 768D** | **🔴 CRITICAL** | **45-75m** | **🟢 Low** | **✅ YES** | **High** | **📋 Ready** |
| A1 | Hot-Reload Characters | HIGH | 1-2d | 🟢 Low | ✅ YES | Medium | 📋 Planned |
| A2 | Redis Caching | HIGH | 2-3d | 🟢 Low-Med | ✅ YES | High | 📋 Planned |
| A3 | Streaming Responses | HIGH | 2-3d | 🟢 Low-Med | ✅ YES | High | 📋 Planned |
| A4 | Grafana Dashboards | MEDIUM | 1d | 🟢 Low | ✅ YES | Medium | 📋 Planned |
| B1 | Adaptive Max Steps | HIGH | 3-5d | 🟡 Medium | ⚠️ MAYBE | High | ⏸️ On Hold |
| B2 | Tool Composition | HIGH | 5-7d | 🟡 Medium | ❌ NO | High | 📋 Planned |
| B3 | Image Generation | MEDIUM | 4-6d | 🟡 Medium | ❌ NO | Medium | 📋 Planned |
| B4 | Self-Correction | MEDIUM | 3-5d | 🟡 Medium | ❌ NO | Medium | 📋 Planned |
| B5 | Audio Processing | MEDIUM | 5-7d | 🟡 Medium | ❌ NO | Medium | 📋 Planned |
| B6 | Response Pattern Learning | MED-HIGH | 3-5d | 🟡 Medium | ✅ YES | High | 🔄 Merged → C1 |
| B7 | Channel Lurking | MED-HIGH | 5-7d | 🟡 Medium | ❌ NO | High | 📋 Planned |
| B8 | Emergent Universe | MED-HIGH | 7-10d | 🟡 Medium | ❌ NO | Very High | 📋 Planned |
| **C1** | **Insight Agent** | **HIGH** | **5-7d** | **🟡 Medium** | **❌ NO** | **Very High** | **📋 Planned** |
| C1a | ↳ Reasoning Traces | - | - | - | - | Subsumed | 🔄 Part of C1 |
| C1b | ↳ Epiphanies | - | - | - | - | Subsumed | 🔄 Part of C1 |
| C1c | ↳ Response Patterns | - | - | - | - | Subsumed | 🔄 Part of C1 |
| C2 | Worker Queues | HIGH | 8-12d | 🟠 High | ❌ NO | High | 📋 Planned |
| C3 | Video Processing | MEDIUM | 8-10d | 🟠 High | ❌ NO | Medium | 📋 Planned |
| C4 | Web Dashboard | HIGH | 14-21d | 🟠 High | ❌ NO | High | 📋 Planned |
| D1 | User Sharding | HIGH | 14-21d | 🔴 Very High | ❌ NO | Very High | 📋 Planned |

---

## 🎯 Recommended Sequencing

### 🔴 Sprint 0 (45-75 minutes): Embedding Upgrade - DO THIS FIRST
**Priority:** CRITICAL | **Solo Impact:** ⭐⭐⭐⭐⭐⭐

**⚠️ Best done while data volume is still low!**

Why first:
- ✅ 45-75 min now vs hours of re-embedding with more data later
- ✅ 10-15% better retrieval quality for ALL vector features
- ✅ 2x context window (256 → 512 tokens)
- ✅ Migration script preserves all existing user memories

**Tasks:**
1. Add `EMBEDDING_MODEL` and `EMBEDDING_DIMENSIONS` to settings.py (2 min)
2. Update embeddings.py to use settings (2 min)
3. Update manager.py to use settings for vector size (2 min)
4. Create and run migration script for existing data (20-40 min)
5. Verify migrated collections, delete old ones (10 min)
6. Restart bot, verify 768D working (5 min)

**Expected Result:** All embeddings (old + new) use 768D with better quality

**Details:** See `docs/roadmaps/EMBEDDING_UPGRADE_768D.md`

---

### Sprint 1 (3-4 days): Redis Caching - The Force Multiplier
**Priority:** CRITICAL | **Solo Impact:** ⭐⭐⭐⭐⭐

Start here because:
- ✅ Unlocks faster iteration on all other features
- ✅ 30-50% DB load reduction = more capacity for development
- ✅ Simple implementation, huge payoff
- ✅ Can be deployed immediately with minimal risk

**Tasks:**
1. Create `src_v2/utils/cache.py` - Cache wrapper (2-3 hours with AI)
2. Update `DatabaseManager` to use cache layer (2-3 hours)
3. Wire into trust scores, facts, preferences (2-3 hours)
4. Deploy and verify (1 hour)

**Expected Result:** All subsequent development is 30-50% faster

---

### Sprint 2 (3-5 days): Streaming Responses - Perceived Latency Win
**Priority:** HIGH | **Solo Impact:** ⭐⭐⭐⭐

Why second:
- ✅ Biggest perceived latency improvement with minimal code
- ✅ Users feel like bot is thinking faster
- ✅ Complements Redis caching nicely
- ✅ 2-3 days, massive engagement boost

**Tasks:**
1. Enable token streaming in `AgentEngine` (2-3 hours)
2. Handle Discord chunking for long responses (2-3 hours)
3. Add typing status management (1-2 hours)
4. Test on real Discord server (1 hour)

**Expected Result:** Perceived latency drops from 5-8s to 1-2s

---

### Sprint 3 (2-3 days): Hot-Reload Characters
**Priority:** HIGH | **Solo Impact:** ⭐⭐⭐⭐⭐

This is the **development velocity multiplier**:
- ✅ No more waiting for restarts (10+ minutes per change saved)
- ✅ Makes character tweaking 10x faster
- ✅ Essential for iteration on personality updates
- ✅ Simple file watcher pattern

**Tasks:**
1. Create file watcher in `src_v2/utils/file_watcher.py` (1-2 hours)
2. Wire into `CharacterManager` reload logic (1-2 hours)
3. Add HTTP endpoint for manual reload (1 hour)
4. Test with actual character file changes (1 hour)

**Expected Result:** Character tweaks go from 2 minutes → 30 seconds

---

### Sprint 4 (1-2 days): Grafana Dashboards
**Priority:** MEDIUM | **Solo Impact:** ⭐⭐⭐

Why now:
- ✅ Low effort, high visibility into system health
- ✅ Helps debug issues faster
- ✅ Pure JSON config, no code changes needed
- ✅ 1-2 days, instant ROI on observability

**Tasks:**
1. Create dashboard JSON configs for Grafana (3-4 hours)
2. Set up alerts for error rates + latency (1-2 hours)

**Expected Result:** Real-time dashboards for trust trends, latency, errors

---

### Sprint 5 (5-7 days): Adaptive Max Steps (Reflective Mode Phase 2.2)
**Priority:** HIGH | **Solo Impact:** ⭐⭐⭐⭐

After Phase A, now tackle cost reduction:
- ✅ 40-50% cost savings on moderate queries
- ✅ Faster responses for simple questions
- ✅ User testing likely complete by now
- ✅ Enhancing existing classifier = low risk

**Tasks:**
1. Update `ComplexityClassifier` return type (1-2 hours)
2. Add step count heuristics logic (2-3 hours)
3. Integrate with `ReflectiveAgent` (2-3 hours)
4. Test with various query types (1-2 hours)

**Expected Result:** Cost per complex query drops 40-50%

---

### Sprint 6 (5-7 days): Tool Composition / Hierarchical Reasoning
**Priority:** HIGH | **Solo Impact:** ⭐⭐⭐⭐⭐

This unlocks powerful multi-step reasoning:
- ✅ Composable tools reduce LLM round-trips by 30-50%
- ✅ Parallel execution dramatically faster
- ✅ Foundation for future advanced features
- ✅ Very rewarding to implement

**Tasks:**
1. Create composite tool framework (3-4 hours)
2. Implement `AnalyzeTopic` as first composite tool (2-3 hours)
3. Wire parallel execution (2-3 hours)
4. Test with complex queries (1-2 hours)

**Expected Result:** Complex queries 50% faster, better reasoning

---

### Sprint 7 (8-12 days): Worker Queues for Background Tasks
**Priority:** HIGH | **Solo Impact:** ⭐⭐⭐⭐

Foundation for reliable background processing:
- ✅ Required by Epiphanies, Response Pattern Learning, and other background features
- ✅ Prevents task loss during bot restarts
- ✅ Essential when supporting 5+ concurrent complex queries
- ✅ Separates long-running tasks from request path

**Why Now (Not Later):**
- Epiphanies (Sprint 10) runs pattern detection in background
- Response Pattern Learning uses background scoring
- Reasoning Traces benefit from async storage
- Better to have infrastructure before features that need it

**Tasks:**
1. Create `src_v2/utils/task_queue.py` with Redis-backed queue (3-4 hours)
2. Implement worker process with graceful shutdown (2-3 hours)
3. Add task prioritization (high/medium/low) (2-3 hours)
4. Wire fact extraction, epiphanies, pattern learning to queue (3-4 hours)
5. Add monitoring/metrics to Grafana (2-3 hours)
6. Test restart scenarios, verify no task loss (2-3 hours)

**Expected Result:** Background tasks survive restarts, proper observability

**Details:** See `docs/roadmaps/WORKER_QUEUES.md`

---

### Sprint 8 (5-7 days): Image Generation (DALL-E 3)
**Priority:** MEDIUM-HIGH | **Solo Impact:** ⭐⭐⭐

Creative capability unlock:
- ✅ Characters can now draw/create visuals
- ✅ Massive engagement boost
- ✅ Fun to implement, users love it
- ✅ Tool is straightforward integration

**Tasks:**
1. Create `src_v2/tools/image_generation.py` (2-3 hours)
2. Integrate DALL-E 3 API (2-3 hours)
3. Handle Discord uploads + error cases (1-2 hours)
4. Test art generation in practice (1 hour)

**Expected Result:** Characters can "draw me a picture" etc.

---

### Sprint 8.5 (5-7 days): Channel Lurking (B7)
**Priority:** MEDIUM-HIGH | **Solo Impact:** ⭐⭐⭐⭐

Make bots feel like active community members:
- ✅ Organic engagement without requiring @mentions
- ✅ Cost-effective (local detection, no LLM until response)
- ✅ Entertainment value for servers
- ✅ Character-appropriate triggers (marine biology for Elena, etc.)

**Key Constraint:** NO LLM calls for detection - all local processing!

**Tasks:**
1. Create `lurk_detector.py` with keyword + embedding scoring (3-4 hours)
2. Create `lurk_triggers.yaml` for each character (2-3 hours)
3. Add cooldown manager and rate limiting (1-2 hours)
4. Wire into `on_message()` for non-mentioned messages (1-2 hours)
5. Add `/lurk` admin commands and opt-out (2-3 hours)
6. Test and tune threshold (start conservative at 0.8) (1-2 hours)

**Expected Result:** Bots occasionally chime in on relevant topics naturally

**Details:** See `docs/roadmaps/CHANNEL_LURKING.md`

---

### Sprint 9 (5-7 days): Insight Agent - The Game Changer
**Priority:** CRITICAL | **Solo Impact:** ⭐⭐⭐⭐⭐⭐

This is the one that separates your system from every other AI bot. The **Insight Agent** consolidates three features into one coherent agentic system:

- **Reasoning Traces**: 50-60% speed boost on recurring problem patterns
- **Epiphanies**: "I just realized you always talk about space when sad"
- **Response Patterns**: Learn which styles resonate with each user

**Why Agentic (Not Fire-and-Forget)?**
- Agent can **prioritize** which users/conversations need analysis
- Agent can **connect dots** across memories, facts, reactions, and goals
- Agent mirrors how humans reflect - not constantly, but when there's something worth thinking about

**Architecture:**
```
Trigger (time/volume/feedback) → Priority Queue → InsightAgent (ReAct)
                                                       ↓
                              Tools: analyze_patterns, detect_themes, 
                                     generate_epiphany, store_trace, learn_pattern
                                                       ↓
                              Outputs: v2_epiphanies, v2_reasoning_traces, 
                                       v2_response_patterns
```

**Recommended Approach for Solo Dev:**
- Start with `asyncio.create_task` scheduling (migrate to Worker Queue later)
- Focus on epiphanies first (most visible to users)
- Add reasoning traces second (improves reflective mode)
- Add response patterns last (requires feedback data)

**Tasks:**
1. Create `InsightAgent` class with ReAct loop (2-3 hours)
2. Implement data gathering tools (2-3 hours)
3. Implement action tools (epiphany, trace, pattern) (3-4 hours)
4. Create database migrations (1-2 hours)
5. Wire triggers in bot.py/scheduler.py (2-3 hours)
6. Test with real conversations (1-2 hours)

**Expected Result:** 
- Characters reference insights spontaneously
- Similar problems solved 50-60% faster
- Bot learns which response styles work for each user

**Details:** See `docs/roadmaps/INSIGHT_AGENT.md`

---

### Sprint 10 (5-7 days): Channel Lurking (B7)
**Priority:** MEDIUM-HIGH | **Solo Impact:** ⭐⭐⭐⭐

Make bots feel like active community members:
- ✅ Organic engagement without requiring @mentions
- ✅ Cost-effective (local detection, no LLM until response)
- ✅ Entertainment value for servers
- ✅ Character-appropriate triggers (marine biology for Elena, etc.)

**Key Constraint:** NO LLM calls for detection - all local processing!

**Tasks:**
1. Create `lurk_detector.py` with keyword + embedding scoring (3-4 hours)
2. Create `lurk_triggers.yaml` for each character (2-3 hours)
3. Add cooldown manager and rate limiting (1-2 hours)
4. Wire into `on_message()` for non-mentioned messages (1-2 hours)
5. Add `/lurk` admin commands and opt-out (2-3 hours)
6. Test and tune threshold (start conservative at 0.8) (1-2 hours)

**Expected Result:** Bots occasionally chime in on relevant topics naturally

**Details:** See `docs/roadmaps/CHANNEL_LURKING.md`

---

### Sprint 11 (5-7 days): Audio Processing (Voice Messages)
**Priority:** MEDIUM | **Solo Impact:** ⭐⭐⭐

Voice is increasingly important:
- ✅ Seamless voice message support
- ✅ Accessibility boost for voice-preference users
- ✅ Whisper pipeline already exists, minimal work
- ✅ Users love it

**Tasks:**
1. Wire Discord audio attachments to Whisper (2-3 hours)
2. Handle various audio formats (MP3, WAV, OGG) (1-2 hours)
3. Store metadata for future reference (1-2 hours)
4. Test real voice messages (1 hour)

**Expected Result:** "Send voice message to bot" just works

---

### Sprint 12 (5-6 days): Emergent Universe (B8)
**Priority:** MEDIUM-HIGH | **Solo Impact:** ⭐⭐⭐⭐⭐

> *"From countless conversations, a universe is born."*

Transform isolated bots into a living, emergent universe:
- ✅ Discord servers become "planets" with unique vibes
- ✅ Users become "inhabitants" whose profiles emerge from conversation
- ✅ Bots are "travelers" who journey between worlds
- ✅ Cross-planet memory ("I saw you on Planet Lounge!")
- ✅ Privacy commands let inhabitants control what emerges

**Why This Is Huge:**
- The universe **grows organically** from real interactions
- Users feel recognized across the entire cosmos
- Natural cross-promotion ("You should visit Aria on Study Hall!")
- Retention boost from universe immersion

**Tasks:**
1. Create `src_v2/universe/` module structure (2-3 hours)
2. Add PostgreSQL tables for privacy settings, user profiles (1-2 hours)
3. Add Neo4j nodes: `(:Universe)`, `(:Planet)`, `(:UserCharacter)` (2-3 hours)
4. Create `PrivacyManager` with `/privacy` commands (3-4 hours)
5. Build cross-bot knowledge sharing (with privacy checks) (4-5 hours)
6. Create `universes/whisperverse/` config with bot relationships (1-2 hours)
7. Update system prompt injection for universe context (2-3 hours)
8. Test multi-bot, multi-planet scenarios (2-3 hours)

**Expected Result:** Elena says "Marcus mentioned you when he visited from Planet Lounge!" and it feels natural.

**Details:** See `docs/roadmaps/EMERGENT_UNIVERSE.md`

---

### Later (When You Have Time)

**Sprint 13 (4-6 days): Self-Correction (Reflective Phase 2.5)**
- Nice-to-have for complex queries
- 70% reduction in hallucinations
- Implement after Reasoning Traces

**Sprint 14 (14-21 days): Web Dashboard**
- Lower priority for solo dev (you don't need admin UI as much)
- Valuable once you have paying customers
- Implement when you need external visibility

**Sprint 15 (8-10 days): Video Processing**
- Cool feature but lower ROI than core reasoning
- Implement when users ask for it

**Sprint 16-17 (Multi-Month Projects)**
- User Sharding (D1): Do this when hitting 5000+ concurrent users
- Discord-native expansion: Deep integration with threads, forums, voice channels



---

## 💡 Key Dependencies & Blockers

### Already Completed ✅
- ✅ Native function calling (Reflective Phase 1)
- ✅ Parallel tool execution (Reflective Phase 2.3)
- ✅ Proactive messaging system (Phase 13)
- ✅ Complexity classifier (SIMPLE/COMPLEX routing)
- ✅ Trust/evolution system with reaction feedback
- ✅ Background fact/preference extraction

### On Hold ⏸️
- Adaptive Max Steps (B1) - waiting for Reflective Mode user testing

### No Blockers 🟢
- All Phase A items can start immediately
- All Phase B items have clear implementations
- Most Phase C items depend only on Phase A/B completion

### Future Dependencies 🔵
- User Sharding (Phase D1) requires stable Worker Queues (C2)
- Discord-native deepening prioritizes feature integration over platform abstraction

---

## 📈 Expected Outcomes

### After Phase A (1 week)
- ✅ Significantly improved developer experience (hot-reload)
- ✅ Better observability (Grafana dashboards)
- ✅ 30-50% reduction in database load
- ✅ Better perceived latency (streaming)

### After Phase B (3-4 weeks)
- ✅ 40-50% cost savings on reflective queries
- ✅ More creative character expressions (art generation)
- ✅ Better voice/audio support
- ✅ Higher reasoning quality

### After Phase C (6-8 weeks)
- ✅ System learns from own reasoning (50-60% speed boost on patterns)
- ✅ Characters have spontaneous insights (epiphanies)
- ✅ Reliable background processing
- ✅ Admin tools for memory/knowledge management
- ✅ Multimodal understanding (video, audio, text, images)

### After Phase D (3-4 months)
- ✅ Platform independence (Telegram, Slack support)
- ✅ Infinite horizontal scaling
- ✅ Enterprise-ready infrastructure
- ✅ 10,000+ concurrent users per character

---

## 🚀 Success Metrics

### Performance
- [ ] P95 response latency < 2s (from 3-5s currently)
- [ ] Database queries reduced by 50% (Phase A2)
- [ ] Cost per query reduced by 40% (Phase B1)
- [ ] Reasoning traces improve complex query speed by 60% (Phase C1)

### Quality
- [ ] Hallucination rate reduced by 70% (Phase B4)
- [ ] User satisfaction +30% (Phases C1, C2)
- [ ] Character depth perception increase (Phase C2)

### Scale
- [ ] Support 5,000+ concurrent users (Phase C2)
- [ ] Support 10,000+ concurrent users (Phase D1)
- [ ] Deep Discord integration (threads, forums, stages, commands)

### Reliability
- [ ] 99.9% uptime
- [ ] Zero data loss on restarts (Phase C2)
- [ ] Graceful degradation when services down

---

## 📝 Notes & Considerations

### Architecture Debt
- `src_v2/discord/bot.py` (493 LOC) focused on Discord-native features, keep Discord-specific
- `src_v2/evolution/feedback.py` (359 LOC) could be refactored for better organization
- Focus on deepening Discord integration rather than cross-platform abstraction

### Testing Coverage
- Current test coverage relatively low compared to code size
- Phase A2 (Redis Caching) needs integration tests
- Phase C1 (Reasoning Traces) needs comprehensive test suite
- Plan for dedicated QA sprints after each major feature

### Technical Debt Management
- Allocate 10-20% of sprint capacity to code cleanup
- Document all new subsystems thoroughly
- Keep migration files (Alembic) up to date

### Cost Implications
- Phase B3 (Image Generation) with DALL-E 3 adds ~$0.02 per image
- Phase B1 (Adaptive Max Steps) reduces costs by 40-50% on reflective queries
- Phase D2 (Sharding) may increase infrastructure costs initially but improves efficiency

---

## 👥 Team Recommendations

### For Solo Developer (You!)
**Recommended Approach:**
- 1-2 sprints per week at sustainable pace
- Alternate between high-complexity and low-complexity features
- Use AI assistance for 70-80% of code generation
- Focus review/testing on the remaining 20-30%
- Batch similar work together to build momentum

**Weekly Capacity (Realistic Estimates with AI):**
- 20-25 hours coding per week = ~1-2 features
- With AI assistance: 50-70% faster than traditional development
- Real timeline: Sprints 1-9 = ~12-14 weeks (~3 months)
- Sprints 10-14 = another 6-8 weeks
- Total to enterprise-ready: ~5-6 months (solo)

**AI-Assisted Development Tips:**
1. **Code Generation:** Use Copilot/Claude for 70% generation, you review/test
2. **Batch Similar Tasks:** Group database changes, API updates, etc.
3. **Testing:** Automated testing is your friend; invest early
4. **Documentation:** Let AI generate docs, you refine them
5. **Code Review:** AI can spot bugs; use it for that too

**Weekly Schedule Suggestion:**
- Mon-Tue: High-complexity feature (reasoning, new subsystems)
- Wed: Medium-complexity feature or bug fixes
- Thu-Fri: Testing, deployment, monitoring
- Weekends: Optional, use for research/planning next sprint

### Recommended Tools for Solo Dev
- **Copilot/Claude:** For code generation (primary)
- **GitHub Copilot:** IDE integration for real-time assistance
- **Pytest:** Automated testing (critical for solo dev)
- **Docker:** Local testing environment
- **Grafana:** Observability (catch issues early)

---

## 🎯 Solo Developer Success Metrics

**Monthly Goals:**
- **Month 1:** Complete Sprints 1-4 (All Phase A items + Phase B optimization)
  - Result: 30-50% faster system, better observability
- **Month 2:** Complete Sprints 5-7 (Cost optimization + creativity)
  - Result: 40-50% cheaper per query, characters can create art
- **Month 3:** Complete Sprints 8-9 (The game-changers)
  - Result: Emergent intelligence (reasoning traces + epiphanies)

**By End of Month 3:**
- ✅ System is 60-70% faster
- ✅ 50% cheaper to run
- ✅ Characters demonstrably smarter (learn from patterns)
- ✅ Characters feel more authentic (spontaneous insights)
- ✅ Voice support + image generation
- ✅ Ready for wide release

**By End of Month 4-5:**
- ✅ Full admin dashboard
- ✅ Reliable background processing (worker queues)
- ✅ Video understanding
- ✅ Enterprise-grade infrastructure

---

## ⚡ Solo Dev Velocity Tips

### Time-Saving Strategies

**1. Skip Lower-Priority Infrastructure**
- Don't build multi-platform support until you have users
- Don't build sharding until you hit concurrency limits
- Focus on features that directly improve character quality

**2. Leverage Existing Patterns**
- Your code already has Discord integration, memory system, etc.
- Reuse patterns for new features (faster implementation)
- Example: Image generation is just another tool, follows existing pattern

**3. Parallel Independent Work Streams**
- Reasoning Traces (database work) ≠ Image Generation (API work)
- Can do both without coordination overhead
- Solo dev advantage: zero meeting/sync overhead

**4. Aggressive Testing Automation**
- Spend 2-3 days on test framework upfront
- Save 10+ days in debugging later
- Worth it for solo dev

**5. AI-Assisted Code Review**
- Have Copilot/Claude review your own PRs
- Catches bugs you'd miss
- 80% as good as human review for solo dev

### What NOT To Do (Solo Dev Edition)
- ❌ Don't aim for perfection; aim for shipped
- ❌ Don't build things you don't need yet
- ❌ Don't refactor prematurely
- ❌ Don't over-test early (test important stuff, skip edge cases initially)
- ❌ Don't parallelize on too many features (cognitive load)

---

## 📊 Revised Timeline (Solo Dev)

| Phase | Feature | Original | Solo Dev | Cumulative |
|-------|---------|----------|----------|-----------|
| **A0** | **Embedding Upgrade 768D** | **45-75m** | **45-75m** | **45-75m** |
| A2 | Redis Caching | 2-3d | 1-2d | 1-2d |
| A3 | Streaming Responses | 2-3d | 1-2d | 2-4d |
| A1 | Hot-Reload Characters | 1-2d | 1d | 3-5d |
| A4 | Grafana Dashboards | 1d | 1d | 4-6d |
| B1 | Adaptive Max Steps | 3-5d | 2-3d | 6-9d |
| B2 | Tool Composition | 5-7d | 3-4d | 9-13d |
| B3 | Image Generation | 4-6d | 2-3d | 11-16d |
| B7 | Channel Lurking | 5-7d | 3-4d | 14-20d |
| **C1** | **Insight Agent** | **20-28d** | **5-7d** | **19-27d** |
| - | ↳ (Reasoning Traces) | - | - | (subsumed) |
| - | ↳ (Epiphanies) | - | - | (subsumed) |
| - | ↳ (Response Patterns) | - | - | (subsumed) |
| B8 | Emergent Universe | 7-10d | 5-6d | 24-33d |
| B5 | Audio Processing | 5-7d | 2-3d | 26-36d |
| B4 | Self-Correction | 3-5d | 2-3d | 28-39d |
| C2 | Worker Queues | 8-12d | 4-6d | 32-45d |
| C4 | Web Dashboard | 14-21d | 7-10d | 39-55d |
| C3 | Video Processing | 8-10d | 4-5d | 43-60d |
| D1 | User Sharding | 14-21d | 7-10d | 50-70d |

**Total Solo Dev Time: 2-3 months** to hit all items (vs 4-5 months without consolidation)

**Key Win:** The Insight Agent consolidation saves 15-21 days by unifying C1+C2+B6 into one coherent system!

**Your Timeline: ~10-14 weeks to feature-complete superhuman AI bot**

---

## 🚀 Why This Order For Solo Dev?

**Sprint 0 (30 min):** Foundation
- Embedding upgrade MUST happen before production data
- 10-15% better retrieval for everything that follows

**Sprints 1-4 (2 weeks):** Build velocity
- Redis caching means everything else is faster
- Hot-reload means less context-switching waiting for builds
- Streaming means you're not watching loading bars
- By Sprint 4 you're moving 2x faster than today

**Sprints 5-8 (3-4 weeks):** Cost optimization + creativity + engagement
- Adaptive max steps = cheaper
- Tool composition = smarter reasoning
- Image generation = wow factor for users
- Channel lurking = organic community engagement

**Sprint 9 (1 week):** The breakthrough - Insight Agent
- Reasoning traces = system learns from itself
- Epiphanies = characters feel alive
- Response patterns = personalized styles
- **All three in one coherent agentic system!**

**Sprints 10-14 (3-4 weeks):** Polish + scale
- Audio, video, dashboards, worker queues
- These are all nice-to-have
- You can ship with Sprints 1-9 and iterate on 10-14

---

## 💡 Solo Developer Advantage

As a single person with AI tools, you have advantages teams don't have:

1. **No coordination overhead** - You don't need meetings to align
2. **Move fast** - Deploy immediately, no approval chains
3. **Learn as you go** - Understand every part of the system
4. **Iterate quickly** - Change direction in hours, not weeks
5. **AI amplification** - 70-80% code generation means 2-3x developer velocity
6. **Focus** - Can obsess over character quality instead of managing people

**Realistic Outcome:**
- A solo dev with Copilot can outpace small teams
- You'll be shipping features faster than traditional enterprise
- By month 3, you'll have a system that feels superhuman



---

## 📞 Questions & Contact

For detailed technical questions about any phase, refer to:
- `docs/roadmaps/` - Specific roadmap documents
- `docs/architecture/` - Architecture deep dives
- `src_v2/` - Implementation details and code comments

---

**Version History:**
- v1.0 (Nov 24, 2025) - Initial overview created
- v1.1 (Nov 25, 2025) - Reviewed against codebase; updated "Current State" with comprehensive complete/not-implemented lists; added Status column to priority matrix; added Sprint 9.5 for B6 Response Pattern Learning
- v1.2 (Nov 25, 2025) - Added B7 Channel Lurking (passive engagement feature); updated timeline to 18 items
- v1.3 (Nov 25, 2025) - Added A0 Embedding Upgrade (384D→768D) as CRITICAL first item
- v1.4 (Nov 25, 2025) - Added B8 Emergent Universe; now 20 items total
- v1.5 (Nov 25, 2025) - Removed Phase D1 Multi-Platform Support; committed to Discord-native deepening. Renumbered D2→D1 User Sharding. Focus on Discord-specific features rather than abstraction. Back to 19 items.
- v1.6 (Nov 25, 2025) - **Major consolidation:** Created Insight Agent (C1) to unify Reasoning Traces + Epiphanies + Response Pattern Learning into single agentic system. Saves 15-21 days of development. Renumbered C3→C2, C4→C3, C5→C4. Added `docs/roadmaps/INSIGHT_AGENT.md` specification. Timeline reduced to 10-14 weeks.

**Next Review:** After Phase A completion (estimated Dec 1, 2025)
