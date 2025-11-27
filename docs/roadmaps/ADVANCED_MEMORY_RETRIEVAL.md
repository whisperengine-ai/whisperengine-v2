# Enhancement: Advanced Memory Retrieval

**Status**: 🔄 In Progress  
**Priority**: High  
**Complexity**: Medium  
**Dependencies**: `MemoryManager`, `Qdrant`, `Neo4j`, `PostgreSQL`

### Implementation Progress

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1 | Summary Boosting (Meaningfulness) | ✅ Complete |
| Phase 2 | Temporal Decay (Recency) | ✅ Complete |
| Phase 3 | Episode Scoring | ✅ Complete |
| Phase 4 | Hybrid Retrieval (ContextBuilder) | ✅ Complete |
| Phase 5 | Neo4j Confidence | ✅ Complete |
| Phase 6 | Continuity Markers | 📋 Planned |

---

## Overview

This document covers a comprehensive upgrade to WhisperEngine's memory retrieval system across **all data stores**. The goal is to make characters recall memories like humans do: prioritizing emotional significance, recent events, and reinforced facts over raw semantic similarity.

### Current Data Stores

| Store | Type | Used For | Current Retrieval | Issue |
|-------|------|----------|-------------------|-------|
| **Qdrant** (Episodes) | Vector | Raw message recall | `search_memories()` | Pure semantic, no priority |
| **Qdrant** (Summaries) | Vector | Session summaries | `search_summaries()` | Has `meaningfulness_score` but unused |
| **Neo4j** | Graph | Structured facts | `query_graph()` | No confidence scoring |
| **PostgreSQL** | Relational | Recent history | `get_recent_history()` | Pure chronology, isolated from semantic |

---

## Problem Statement

Memory retrieval is purely **semantic**. The system retrieves memories based solely on vector cosine similarity.

**Symptoms:**
- Trivial memories ("I like Chipotle") compete equally with profound ones ("My grandmother passed away")
- 6-month-old memories surface as easily as yesterday's
- Facts mentioned once are treated the same as core identity facts mentioned 50 times
- No blending between "what just happened" (Postgres) and "what's relevant" (Qdrant)

**Impact:** Characters feel shallow and fail to prioritize emotionally significant shared history.

---

## Solution: Multi-Signal Ranking

Implement a **composite scoring system** that combines multiple signals:

$$ FinalScore = Semantic \times Meaningfulness \times Recency \times Confidence \times Trust $$

Each factor is a multiplier (≥1.0 for boost, <1.0 for decay).

### Architectural Alignment

This enhancement directly supports WhisperEngine's core principles:

| Principle | How This Helps |
|-----------|----------------|
| **Living Character Paradigm** | Characters recall what *matters*, not just what matches semantically |
| **Multi-Modal Perception** | Upgrades the Memory modality (🧠) to human-like prioritization |
| **Emergent Behavior** | Richer memory context = more authentic emergence |
| **Dual Process Theory** | Ranking happens post-retrieval; no latency impact on Fast Mode |
| **Polyglot Persistence** | Uses each DB for its strength (Qdrant=similarity, Neo4j=confidence, Postgres=recency) |
| **Pipeline Simplification** | Moves complex gathering logic out of `bot.py` into `ContextBuilder` |

---

## Phase 1: Emotional Priority (Summaries)

**Target:** `MemoryManager.search_summaries()`  
**Complexity:** Low  
**Time:** 1-2 hours

Summaries already have `meaningfulness_score` (1-5) in Qdrant payload. We just need to use it.

### Formula
```
MeaningfulnessBoost = 1 + (α × meaningfulness_score / 5)
```
Where α = 0.5 (tunable). A score of 5/5 adds 50% to the vector score.

### Pseudocode
```
function search_summaries(query, user_id, limit):
  // Fetch 3x candidates for re-ranking headroom
  candidates = qdrant.search(query, limit * 3)
  
  for item in candidates:
    base = item.score
    meaning = item.payload.meaningfulness_score or 1
    item.final_score = base * (1 + 0.5 * meaning / 5)
  
  sort_descending(candidates, by=final_score)
  return candidates[0:limit]
```

### Files
- `src_v2/memory/manager.py` → `search_summaries()`

### Optional: Trust-Based Boost
For deeper architectural alignment, memories from high-trust users could receive a boost:
```
TrustBoost = 1 + (0.2 × trust_level / 5)  // Soulmate (5/5) = +20%
```
This reflects the principle that we remember more from people we're close to.

---

## Phase 2: Temporal Decay (Recency Boost)

**Target:** `search_summaries()`, `search_memories()`  
**Complexity:** Low  
**Time:** 1-2 hours

Old memories should naturally fade unless they're emotionally significant.

### Formula
```
// Base decay
RawDecay = e^(-λ × days_ago)

// Floor based on meaningfulness (Important memories never fade completely)
// Score 1/5 -> Floor 0.2
// Score 5/5 -> Floor 0.9
DecayFloor = 0.2 + (0.7 × (meaningfulness_score - 1) / 4)

RecencyBoost = max(RawDecay, DecayFloor)
```
Where λ = 0.02.

### Example Scenarios
1. **Trivial (Score 1) from 90 days ago:**
   - RawDecay: 0.16
   - Floor: 0.2
   - **Result: 0.2** (Faded to background)

2. **Profound (Score 5) from 90 days ago:**
   - RawDecay: 0.16
   - Floor: 0.9
   - **Result: 0.9** (Still highly relevant)

### Interaction with Meaningfulness
This ensures that "core memories" remain accessible forever, while "what I had for lunch" fades quickly.

### Files
- `src_v2/memory/manager.py` → both search methods

---

## Phase 3: Episode Importance Scoring

**Target:** `search_memories()` (raw messages)  
**Complexity:** Medium  
**Time:** 3-4 hours

Raw messages don't have a `meaningfulness_score`. We need to add one.

### Option A: Real-Time Scoring (Recommended)
Score messages as they arrive using a fast heuristic:

```
function score_message_importance(content, metadata):
  score = 1  // baseline
  
  // Emotional indicators
  if contains_emotion_words(content):  // "love", "hate", "scared", "excited"
    score += 1
  
  // Personal disclosure
  if contains_personal_pronouns(content) and length > 50:
    score += 1
  
  // Life events
  if matches_life_event_pattern(content):  // "got married", "lost my job", "new baby"
    score += 2
  
  return min(score, 5)
```

### Option B: Background Retroactive Scoring
Run a worker job to score existing messages:
```
function backfill_importance_scores():
  for message in qdrant.scroll(type="episode", importance=null):
    score = score_message_importance(message.content)
    qdrant.update_payload(message.id, {importance: score})
```

### Files
- `src_v2/memory/manager.py` → `_save_vector_memory()`
- New: `src_v2/memory/importance.py` (scoring logic)
- `src_v2/workers/insight_worker.py` (backfill job)

---

## Phase 4: Hybrid Retrieval (Postgres + Qdrant)

**Target:** Context building in `bot.py`  
**Complexity:** Medium  
**Time:** 2-3 hours

Currently, `get_recent_history()` (Postgres) and `search_memories()` (Qdrant) are called separately with no blending.

### Solution: Unified Context Builder

```
function get_unified_context(user_id, query, limits):
  // 1. Get chronological context (what just happened)
  recent = postgres.get_recent_history(user_id, limit=limits.recent)
  
  // 2. Get semantic context (what's relevant from the past)
  semantic = qdrant.search_memories(query, user_id, limit=limits.semantic)
  
  // 3. Merge and deduplicate (by message_id or content hash)
  merged = deduplicate(recent + semantic)
  
  // 4. Sort by composite score
  for item in merged:
    item.final_score = compute_composite_score(item)
  
  return sorted(merged, by=final_score)[0:limits.total]
```

### Deduplication Strategy
- Use `message_id` if available (stored in Qdrant payload)
- Fallback to content hash for legacy data

### Architectural Benefit
This unifies the "Gather State" step (from *Purpose Driven Emergence*) into a single, testable component. It also simplifies `bot.py` by removing the complex `asyncio.gather` block, aligning with the "Pipeline Simplification" goal of *WhisperEngine 2.0 Design*.

### Files
- New: `src_v2/memory/context_builder.py`
- `src_v2/discord/bot.py` → Refactor `on_message` to use `context_builder`

---

## Phase 5: Neo4j Confidence Scores

**Target:** Knowledge graph facts  
**Complexity:** Medium  
**Time:** 3-4 hours

Facts in Neo4j have no confidence. "User mentioned pizza once" = "User talks about their dog constantly."

### Schema Update
Add `confidence` and `last_reinforced` to relationships:
```cypher
// Current
(u:User)-[:LIKES {value: "pizza"}]->(e:Entity)

// Enhanced
(u:User)-[:LIKES {value: "pizza", confidence: 3, last_reinforced: datetime()}]->(e:Entity)
```

### Reinforcement Logic
When a fact is mentioned again:
```
function reinforce_fact(user_id, fact):
  existing = neo4j.find_fact(user_id, fact.subject, fact.predicate)
  
  if existing:
    // Increment confidence (cap at 10)
    existing.confidence = min(existing.confidence + 1, 10)
    existing.last_reinforced = now()
  else:
    // New fact starts at confidence 1
    neo4j.create_fact(user_id, fact, confidence=1)
```

### Query Prioritization
Modify `query_graph()` to prefer high-confidence facts:
```cypher
MATCH (u:User {id: $user_id})-[r]->(e)
WHERE r.type IN ['LIKES', 'HAS', 'LIVES_IN']
RETURN e.name, r.type, r.confidence
ORDER BY r.confidence DESC
LIMIT 10
```

### Files
- `src_v2/knowledge/manager.py` → `add_fact()`, `query_graph()`
- `src_v2/knowledge/extractor.py` → reinforcement check before insert
- Migration: Add `confidence` property to existing relationships

---

## Phase 6: Cross-Session Continuity Markers

**Target:** Session summarization  
**Complexity:** Low-Medium  
**Time:** 2-3 hours

When summarizing sessions, explicitly tag high-importance topics for future recall.

### Enhanced Summary Schema
```
{
  summary: "User shared excitement about upcoming whale watching trip...",
  meaningfulness_score: 4,
  emotions: ["excited", "hopeful"],
  
  // NEW: Explicit topic markers
  key_topics: [
    {topic: "whale_watching_trip", importance: "high", user_emotion: "excited"},
    {topic: "family_vacation", importance: "medium", user_emotion: "neutral"}
  ]
}
```

### Topic Extraction
During summarization, extract and tag key topics:
```
function extract_key_topics(conversation):
  topics = llm.extract_topics(conversation)  // Existing LLM call
  
  for topic in topics:
    topic.importance = infer_importance(topic, conversation)
    topic.user_emotion = detect_emotion(topic, conversation)
  
  return topics
```

### Retrieval Boost
When searching summaries, boost matches on `key_topics`:
```
function boost_topic_match(item, query):
  for topic in item.key_topics:
    if semantic_match(query, topic.topic) > 0.7:
      if topic.importance == "high":
        return 1.5
      elif topic.importance == "medium":
        return 1.2
  return 1.0
```

### Files
- `src_v2/memory/summarizer.py` → `SummaryResult` schema, extraction
- `src_v2/memory/manager.py` → `search_summaries()` boost logic

---

## Implementation Priority

| Phase | Effort | Impact | Recommendation |
|-------|--------|--------|----------------|
| 1: Emotional Priority | 1-2h | High | **Do First** (uses existing data) |
| 2: Temporal Decay | 1-2h | Medium | Do Second (simple math) |
| 4: Hybrid Retrieval | 2-3h | High | Do Third (better context) |
| 3: Episode Scoring | 3-4h | Medium | Do Fourth (needs new data) |
| 5: Neo4j Confidence | 3-4h | Medium | Do Fifth (schema change) |
| 6: Continuity Markers | 2-3h | Medium | Do Last (enhances summaries) |

**Total Estimated Time:** 12-18 hours

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Profound memory recall rate | ~30% | >70% |
| Recent event mention rate | ~50% | >80% |
| "Who is Max?" accuracy (reinforced facts) | ~60% | >90% |
| User satisfaction (qualitative) | "forgetful" | "remembers what matters" |

---

## Configuration (Feature Flags)

```python
# settings.py
MEMORY_MEANINGFULNESS_WEIGHT = 0.5  # α for meaningfulness boost
MEMORY_RECENCY_DECAY_LAMBDA = 0.02  # λ for temporal decay
MEMORY_CONFIDENCE_THRESHOLD = 3     # Min confidence to surface Neo4j facts
ENABLE_HYBRID_RETRIEVAL = True      # Blend Postgres + Qdrant
ENABLE_EPISODE_SCORING = True       # Score raw messages on save
```
