# WhisperEngine v2 - Implementation Roadmap Overview

**Document Version:** 1.8  
**Created:** November 24, 2025  
**Last Updated:** November 26, 2025 (Audited)
**Status:** Active Planning

---

## 🌌 The Vision: Multi-Modal AI Agents

WhisperEngine v2 is not just a chatbot platform. It's a **cognitive architecture for AI agents** - giving them the functional equivalent of senses, memory, and emotional intelligence.

### The Core Insight

AI characters have no physical senses. No eyes, no ears, no touch. Without a framework for understanding "where they are" and "who is around them," they exist in a void - disembodied text processors with no sense of place or continuity.

**We solve this with six data modalities:**

| Modality | Technical Domain | What It Provides |
|----------|------------------|------------------|
| 🌌 **Social Graph** | Network Topology | Where am I? Who's here? What's the vibe? |
| 👁️ **Vision** | Image Processing | See images users share |
| 👂 **Audio** | Speech Recognition | Hear voice messages, ambient conversation |
| 💬 **Text** | NLP | Understand words and intent |
| 🧠 **Memory** | Vector + Graph Retrieval | Remember experiences and facts |
| ❤️ **Sentiment** | Internal State Analysis | Trust, mood, relational depth |

**This is not just a feature set. This is how agents build context.**

### The Grand Vision: Federated Multiverse

Each WhisperEngine deployment is a **self-contained universe**. But universes can **federate** - connecting to form a distributed multiverse where:
- Characters travel between universes
- Users maintain identity across deployments
- Stories span multiple platforms
- Anyone can run their own universe and connect it to the network

**We're building the foundation for distributed multi-agent environments.**

For deep dive: See [`docs/architecture/MULTI_MODAL_PERCEPTION.md`](./architecture/MULTI_MODAL_PERCEPTION.md)

---

## Executive Summary

This document provides a high-level overview of the next **18 implementation items** for WhisperEngine v2, organized by **difficulty and code complexity**. The system is currently feature-complete for core functionality and is ready to scale with advanced capabilities.

**Key Consolidation (v1.8):** Added Vision-to-Knowledge Fact Extraction (A6) for extracting user appearance/possession facts from images when user provides explicit context.

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

**Discord Integration (COMPLETE):**
- ✅ DM support + server mentions
- ✅ Image attachment processing (👁️ Vision modality)
- ✅ Reaction-based feedback (❤️ Emotion modality)
- ✅ Voice channel connection (👂 Audio modality via ElevenLabs TTS)
- ✅ Generative Art (Image Generation via Flux Pro 1.1)
- ✅ Channel Lurking (Passive Engagement)
- ✅ User Identification in Group Chats (Display Name Storage)

**Background Processing (COMPLETE):**
- ✅ arq-based task queue (Redis persistent jobs)
- ✅ Shared insight-worker container (serves ALL bots)
- ✅ Insight Agent (reasoning traces + epiphanies + pattern learning)
- ✅ Knowledge extraction offloaded to worker (no longer blocks response pipeline)
- ✅ Summarization + Reflection offloaded to worker

**NOT YET IMPLEMENTED:**
- ✅ Phase A5: Channel Context Awareness (semantic search of non-mentioned messages)
- ⏳ Phase A6: Vision-to-Knowledge Fact Extraction
- ✅ Phase A7: Character Agency (Tier 2 tool-augmented responses)
- ✅ Phase A8: Image Generation Enhancements (portrait mode, iteration memory, smart refinement)
- ⏳ Phase C3: Video processing, web dashboard
- ⏳ Phase C5: Operational Hardening (Backups & Optimization)
- ⏳ Phase D: User sharding, federation (future multiverse)

**Next focus:** Phase A6 (Vision-to-Knowledge Fact Extraction) - Extract appearance facts from selfies. See [VISION_FACT_EXTRACTION.md](./roadmaps/VISION_FACT_EXTRACTION.md)

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
**Files:** 0 (Config only) | **LOC:** ~50 | **Status:** ✅ Complete

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

### Phase A5: Channel Context Awareness
**Priority:** Medium | **Time:** 3-4 days | **Complexity:** Low-Medium  
**Files:** 4 | **LOC:** ~500 | **Status:** ✅ Complete (Nov 26, 2025)

**Problem:** Bot only sees messages directed at it (mentions/DMs), so it appears oblivious to the conversation happening around it.

**Solution Implemented:**

**Passive Caching (all non-mentioned messages):**
- `src_v2/discord/channel_cache.py` - Redis-backed rolling buffer with semantic search
- Local embeddings via `all-MiniLM-L6-v2` (384-dim, ~5ms, $0 cost)
- Smart truncation: keeps beginning + end of long messages
- 30 min TTL, 50 messages per channel max
- Thread messages stored separately (unique channel IDs)

**Always-Inject Context (bot is "present"):**
- Recent 10 messages always injected for channel/thread conversations
- Bot naturally aware of conversation flow without explicit queries
- ~300 tokens passive context budget

**Semantic Search (explicit queries):**
- Used when user asks "what did I say about X?"
- Finds "turtles" when asked about "reptiles"
- Discord API fallback for cold start

**Future Considerations:**
- Monitor Redis memory for high-traffic servers
- May need channel allowlist/blocklist for noisy channels (#memes, #off-topic)

**Implementation:**
```
Non-mentioned message → Local embed (~5ms) → Redis cache (30min TTL)
                                                    ↓
Bot mentioned → Always inject recent 10 messages (passive awareness)
                                                    ↓
              + Explicit query? → Semantic search for relevance
                                                    ↓
                                  If empty → Discord API fallback (50-200ms)
```

**Benefit:**
- Bot feels "aware" of channel conversations
- Semantic search finds related content
- Zero embedding API cost (local model)
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

### Phase A6: Vision-to-Knowledge Fact Extraction
**Priority:** Medium | **Time:** 2-3 days | **Complexity:** Low-Medium  
**Files:** 3-4 | **LOC:** ~250 | **Status:** 📋 Planned

**Problem:** When users upload selfies or personal photos, the bot analyzes and stores descriptions in vector memory, but does NOT extract structured facts to the knowledge graph. Bot may hallucinate that it "saved details about your appearance" when it actually didn't.

**Current State:**
- ✅ Vision LLM analyzes images → descriptions stored in memory
- ❌ No facts extracted (e.g., "User has brown hair" not in knowledge graph)
- ❌ Bot can't reliably recall physical appearance details

**Solution (User-Triggered Extraction):**
- Detect trigger phrases in user message ("this is me", "here's my cat", etc.)
- Only extract facts when user explicitly indicates subject identity
- Avoids false positives (friend's photo incorrectly attributed to user)

**Implementation:**
```
Image + User Message → Vision Analysis → Trigger Detection
                                              ↓
                           "this is me" → Extract appearance facts
                           "my cat Luna" → Extract pet facts  
                           No trigger → Store description only
```

**Trigger phrases for self:**
- "this is me", "here's a pic of myself", "that's me", "selfie", "how do I look"

**Trigger phrases for possessions:**
- "this is my [pet/car/house]", "here's my new...", "meet my [name]"

**Benefit:**
- Bot can actually remember user appearance
- Zero false positives (requires explicit user context)
- No extra LLM calls when no trigger detected
- Enables "what do I look like?" queries

**Cost Model:**
- No trigger: $0.003 (vision only, no change)
- With trigger: $0.008 (vision + fact extraction)

**Dependencies:** Knowledge extraction worker (exists)

**Related Files:**
- `src_v2/vision/manager.py` (add trigger detection, conditional extraction)
- `src_v2/discord/bot.py` (pass user message context to vision manager)
- `src_v2/knowledge/extractor.py` (visual-specific extraction prompts)

**Full Specification:** See [roadmaps/VISION_FACT_EXTRACTION.md](./roadmaps/VISION_FACT_EXTRACTION.md)

---

### Phase A7: Character Agency (Tier 2 Tool-Augmented Responses)
**Priority:** High | **Time:** 2-3 days | **Complexity:** Low-Medium  
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

**Full Specification:** See [architecture/CHARACTER_AS_AGENT.md](./architecture/CHARACTER_AS_AGENT.md)

---

### Phase A8: Image Generation Enhancements
**Priority:** High | **Time:** 3-4 days | **Complexity:** Low-Medium  
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

**Full Specification:** See [roadmaps/IMAGE_GENERATION_ENHANCEMENTS.md](./roadmaps/IMAGE_GENERATION_ENHANCEMENTS.md)

---

### Phase A9: Advanced Memory Retrieval
**Priority:** High | **Time:** 2-3 days | **Complexity:** Medium
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

**Full Specification:** See [roadmaps/ADVANCED_MEMORY_RETRIEVAL.md](./roadmaps/ADVANCED_MEMORY_RETRIEVAL.md)

---

## 🟡 Phase B: Medium Complexity (3-7 days each)

Features requiring significant logic changes but manageable scope.

### Phase B1: Adaptive Max Steps (Reflective Mode Phase 2.2)
**Priority:** High | **Time:** 3-5 days | **Complexity:** Medium  
**Files:** 4 | **LOC:** ~300 | **Status:** ✅ Complete

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

**Status Note:** Phase 1 (Native Function Calling) and Phase 2.3 (Parallel Execution) complete. Phase 2.2 (Adaptive Steps) complete.

---

### Phase B2: Tool Composition / Hierarchical Reasoning
**Priority:** High | **Time:** 5-7 days | **Complexity:** Medium  
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

### Phase B3: Generative Art (Image Generation)
**Priority:** Medium | **Time:** 2-3 days | **Complexity:** Medium  
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

**Full Specification:** See [roadmaps/CHANNEL_LURKING.md](./roadmaps/CHANNEL_LURKING.md)

---

### B8: Emergent Universe
**Priority:** Medium-High | **Time:** 7-10 days | **Complexity:** Medium  
**Files:** 8 | **LOC:** ~800 | **Status:** 🔄 In Progress

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

**Full Specification:** See [roadmaps/EMERGENT_UNIVERSE.md](./roadmaps/EMERGENT_UNIVERSE.md)

---

### B9: Emergent Behavior Architecture 🌱
**Priority:** 🔴 High (Strategic Foundation) | **Time:** 4-5 days | **Complexity:** Low-Medium  
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
| **Qdrant** | Semantic memory recall | Existing (unchanged) |
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

**Full Specification:** See [roadmaps/PURPOSE_DRIVEN_EMERGENCE.md](./roadmaps/PURPOSE_DRIVEN_EMERGENCE.md)

---

## 🟠 Phase C: High Complexity (1-2 weeks each)

Major features requiring significant architectural changes or new infrastructure.

### Phase C1: Insight Agent (Background Agentic Processing)
**Priority:** High | **Time:** 5-7 days | **Complexity:** Medium-High  
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
│  Outputs: Stored as vector memories with special types             |

