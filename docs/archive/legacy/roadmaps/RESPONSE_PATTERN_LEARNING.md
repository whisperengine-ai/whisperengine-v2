# Response Pattern Learning: RLHF-Style Adaptation Without Fine-Tuning

**Phase:** B6 (New)  
**Priority:** Medium-High  
**Effort:** 3-5 days  
**Complexity:** Medium  
**Dependencies:** Existing FeedbackAnalyzer, Qdrant, PostgreSQL

---

## Multi-Modal Context: Learning to Perceive

Response Pattern Learning is how characters **refine their perception** over time. Just as humans learn to read social cues better through experience, characters learn which responses resonate by associating feedback with context.

| Learning Type | Human Analog |
|---------------|--------------|
| Pattern Storage | "When I said X in situation Y, they liked it" |
| Pattern Retrieval | "This feels like a situation where X worked before" |
| Adaptation | "I've learned to read this person better" |

This is **experiential learning** - not changing the model weights, but building a library of successful interactions that informs future perception.

For full philosophy: See [`../architecture/MULTI_MODAL_PERCEPTION.md`](../architecture/MULTI_MODAL_PERCEPTION.md)

---

## Executive Summary

This feature enables the bot to learn from user feedback (👍/👎 reactions) to improve future responses, without requiring LLM fine-tuning. By storing successful response patterns and injecting them as few-shot examples, the bot can adapt its style, tone, and content to what works for each user.

**This is "RLHF-style" learning via prompt engineering, not weight updates.**

---

## Problem Statement

Currently, user feedback affects:
- ✅ Trust scores (relationship level)
- ✅ Memory importance (which memories surface)
- ✅ Coarse preferences (verbosity, tone)

But feedback does **NOT** affect:
- ❌ What KIND of responses work well for this user
- ❌ Specific phrasing/structure that resonates
- ❌ Topic-specific response patterns

**Result**: The bot can't learn "responses like X worked well for similar questions."

---

## Proposed Solution

### Core Concept

```
User Reacts Positively (👍❤️) to Bot Response
    ↓
Store: (user_message, bot_response, feedback_score, metadata)
    ↓
Embed user_message for semantic search
    ↓
Future Similar Query → Retrieve High-Scoring Past Responses
    ↓
Inject as Few-Shot Examples: "Responses like these have worked well..."
```

### Data Model

```sql
CREATE TABLE v2_response_patterns (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    character_name VARCHAR(255) NOT NULL,
    
    -- The interaction
    user_message TEXT NOT NULL,
    bot_response TEXT NOT NULL,
    
    -- Feedback data
    feedback_score FLOAT NOT NULL,          -- -1.0 to +1.0 (aggregated from reactions)
    positive_reactions INT DEFAULT 0,
    negative_reactions INT DEFAULT 0,
    
    -- Metadata for filtering/analysis
    response_length INT,
    detected_intent VARCHAR(100),           -- "question", "emotional_support", "casual_chat", etc.
    detected_topic VARCHAR(100),            -- "marine_biology", "personal", "advice", etc.
    
    -- For semantic search
    user_message_embedding VECTOR(384),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    last_referenced TIMESTAMP,
    reference_count INT DEFAULT 0,
    
    INDEX ON user_message_embedding USING HNSW,
    INDEX ON (user_id, character_name, feedback_score)
);
```

### Implementation Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Response Pattern Learning                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │   Capture    │    │    Store     │    │   Retrieve   │       │
│  │   Feedback   │───▶│   Pattern    │◀───│   Patterns   │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│         │                   │                   │                │
│         ▼                   ▼                   ▼                │
│  on_reaction_add()   PostgreSQL +        Semantic Search         │
│  feedback_score > 0  pgvector           cosine_similarity        │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Injection Layer                        │   │
│  │  [SUCCESSFUL RESPONSE PATTERNS]                          │   │
│  │  For similar questions, responses like these worked well: │   │
│  │  - "¡Hola! Great question about coral..." (👍👍👍)        │   │
│  │  - "That's so interesting! I love..." (❤️❤️)             │   │
│  │  (Match their energy and structure)                       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Day 1: Data Model & Capture

**Files to create/modify:**
- `migrations_v2/versions/add_response_patterns_table.py` (new)
- `src_v2/evolution/pattern_store.py` (new)
- `src_v2/discord/bot.py` (modify on_reaction_add)

**Tasks:**
1. Create migration for `v2_response_patterns` table
2. Create `PatternStore` class with `save_pattern()` method
3. Hook into `on_reaction_add()` to capture successful responses

```
// src_v2/evolution/pattern_store.py
class PatternStore:
    function save_pattern(user_id, character_name, user_message, bot_response, feedback_score, ...) -> None:
        // Save a response pattern when feedback is positive
        
        // Only save patterns with positive feedback
        if feedback_score <= 0:
            return
            
        // Embed the user message for semantic search
        embedding = embed_text(user_message)
        
        // Detect intent and topic (simple heuristics or LLM call)
        intent = detect_intent(user_message)
        topic = detect_topic(user_message, bot_response)
        
        // Store in PostgreSQL
        db.execute("INSERT INTO v2_response_patterns ...", ...)
```

### Day 2: Retrieval & Ranking

**Files to modify:**
- `src_v2/evolution/pattern_store.py` (add retrieval)

**Tasks:**
1. Implement `get_similar_successful_patterns()` method
2. Add ranking by feedback_score + recency + relevance
3. Add deduplication (don't show near-duplicate responses)

```
function get_similar_successful_patterns(user_id, character_name, current_message, limit=3) -> List[Dict]:
    // Retrieve high-scoring past responses for similar messages
    
    // Embed current message
    query_embedding = embed_text(current_message)
    
    // Search for similar messages with positive feedback
    // Rank by: Semantic Similarity (60%) + Feedback Score (30%) + Recency (10%)
    results = db.fetch("""
        SELECT ... FROM v2_response_patterns
        WHERE user_id = $1 AND character_name = $2 AND feedback_score >= 0.5
        ORDER BY weighted_score DESC
        LIMIT $limit
    """)
    
    return results
```

### Day 3: System Prompt Injection

**Files to modify:**
- `src_v2/agents/engine.py` (add pattern injection)

**Tasks:**
1. Call `get_similar_successful_patterns()` in `_build_system_context()`
2. Format patterns as few-shot examples
3. Add permissive instruction (not mandatory to follow)

```
// In AgentEngine._build_system_context()

function _get_pattern_context(user_id, character_name, user_message) -> str:
    // Retrieve successful response patterns for similar messages
    patterns = pattern_store.get_similar_successful_patterns(
        user_id, character_name, user_message, limit=2
    )
    
    if is_empty(patterns):
        return ""
    
    context = "\n\n[SUCCESSFUL RESPONSE PATTERNS]\n"
    context += "For similar messages, responses like these resonated well with this user:\n"
    
    for i, p in enumerate(patterns):
        reactions = "👍" * p['positive_reactions']
        context += f"\n{i}. User asked: \"{p['user_message']}...\"\n"
        context += f"   Your response: \"{p['bot_response']}...\" ({reactions})\n"
    
    context += "\n(Consider matching this energy, length, and structure. But stay natural—don't copy verbatim.)\n"
    
    return context
```

### Day 4: Testing & Refinement

**Files to create:**
- `tests_v2/test_pattern_store.py` (new)

**Tasks:**
1. Unit tests for pattern storage/retrieval
2. Integration test with mock feedback
3. Tune similarity threshold and ranking weights
4. Add logging for debugging

```
function test_pattern_storage_and_retrieval():
    // Test that positive feedback stores patterns and retrieval works
    
    // Store a pattern
    pattern_store.save_pattern(
        user_id="test_user",
        user_message="What's your favorite ocean creature?",
        bot_response="¡Ay, qué buena pregunta! I have such a soft spot for sea otters...",
        feedback_score=0.8
    )
    
    // Retrieve for similar message
    patterns = pattern_store.get_similar_successful_patterns(
        user_id="test_user",
        current_message="What marine animal do you like best?"
    )
    
    assert count(patterns) >= 1
    assert "sea otters" in patterns[0]['bot_response']
```

### Day 5: Feature Flag & Monitoring

**Files to modify:**
- `src_v2/config/settings.py` (add feature flag)
- `src_v2/evolution/pattern_store.py` (add metrics)

**Tasks:**
1. Add `ENABLE_RESPONSE_PATTERN_LEARNING` feature flag
2. Add InfluxDB metrics for pattern usage
3. Add decay mechanism for old patterns
4. Documentation

```python
# settings.py
ENABLE_RESPONSE_PATTERN_LEARNING: bool = Field(
    default=False,
    description="Enable RLHF-style response pattern learning from user feedback"
)

# Pattern decay (run periodically)
function decay_old_patterns():
    // Reduce scores of old, unreferenced patterns
    db.execute("""
        UPDATE v2_response_patterns
        SET feedback_score = feedback_score * 0.95
        WHERE last_referenced < NOW() - INTERVAL '30 days'
          AND reference_count < 3
    """)
    
    // Archive very low score patterns
    db.execute("DELETE FROM v2_response_patterns WHERE feedback_score < 0.2")
```

---

## System Prompt Injection Example

For a user who previously reacted positively to warm, emoji-filled responses:

```
[SUCCESSFUL RESPONSE PATTERNS]
For similar messages, responses like these resonated well with this user:

1. User asked: "What do you think about climate change?"
   Your response: "¡Ay, this is something so close to my heart! 💙 The reefs I study are like canaries in a coal mine..." (👍👍👍)

2. User asked: "How was your day?"
   Your response: "Cariño! It was amazing—we spotted a juvenile sea turtle near the research site! 🐢✨ How about yours?" (❤️❤️)

(Consider matching this energy, length, and structure. But stay natural—don't copy verbatim.)
```

---

## Comparison with True RLHF

| Aspect | True RLHF | Response Pattern Learning |
|--------|-----------|---------------------------|
| **Mechanism** | Fine-tune model weights | Few-shot prompt injection |
| **Compute Cost** | High (GPU training) | Low (database query) |
| **Latency** | None (at inference) | ~10-20ms (retrieval) |
| **Persistence** | Permanent (in model) | Session-based (in prompt) |
| **Reversibility** | Difficult | Easy (delete patterns) |
| **Risk of Drift** | High | Low (base model unchanged) |
| **Per-User Learning** | Difficult | Native |
| **Works with Hosted LLMs** | ❌ No | ✅ Yes |

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Pattern Hit Rate** | >30% of messages | % of messages where patterns are injected |
| **Feedback Improvement** | +10% positive reactions | Compare before/after enabling |
| **Response Time Impact** | <50ms added latency | Measure retrieval time |
| **Pattern Quality** | >0.6 avg feedback score | Track stored pattern scores |
| **User Satisfaction** | Qualitative | User surveys, engagement metrics |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| **Echo Chamber** | Limit to 2-3 examples; add randomness |
| **Stale Patterns** | Decay mechanism; recency weighting |
| **Privacy Concerns** | Patterns are per-user only; not shared |
| **Prompt Bloat** | Truncate long responses; limit to 2 examples |
| **Gaming/Manipulation** | Require multiple positive reactions; rate limit |

---

## Future Enhancements

### Phase 2: Cross-User Pattern Learning (Optional)

If enabled, anonymized patterns could be shared:
```sql
-- Aggregate patterns across users (anonymized)
SELECT bot_response, AVG(feedback_score) as avg_score, COUNT(*) as count
FROM v2_response_patterns
WHERE character_name = 'elena'
  AND detected_topic = 'marine_biology'
GROUP BY bot_response
HAVING COUNT(*) > 5 AND AVG(feedback_score) > 0.7
```

**Risk**: Requires careful privacy considerations.

### Phase 3: Intent-Specific Patterns

Learn what works for specific intents:
- "emotional_support" → Longer, empathetic responses work
- "quick_question" → Concise, direct responses work
- "casual_chat" → Playful, emoji-heavy responses work

### Phase 4: A/B Testing Framework

Test pattern injection effectiveness:
- 50% of messages get pattern injection
- 50% don't
- Compare feedback scores

---

## Integration with Existing Systems

| System | Integration Point |
|--------|-------------------|
| **FeedbackAnalyzer** | Triggers pattern storage on positive feedback |
| **TrustManager** | High-trust users might weight patterns more |
| **Memory System** | Patterns complement episodic memory |
| **Reasoning Traces (C1)** | Patterns for responses, traces for reasoning |
| **Epiphanies (C2)** | Could generate epiphanies from pattern analysis |

---

## Estimated Effort Breakdown

| Task | Time | Dependencies |
|------|------|--------------|
| Data model + migration | 2-3 hours | None |
| PatternStore.save_pattern() | 2-3 hours | Migration |
| Hook into on_reaction_add | 1-2 hours | PatternStore |
| PatternStore.get_similar_patterns() | 3-4 hours | Embeddings |
| System prompt injection | 2-3 hours | Retrieval |
| Testing | 4-6 hours | All above |
| Feature flag + monitoring | 2-3 hours | All above |
| Documentation | 2-3 hours | All above |
| **Total** | **3-5 days** | |

---

## Conclusion

Response Pattern Learning provides RLHF-style adaptation without the complexity and cost of fine-tuning. By leveraging existing infrastructure (PostgreSQL, pgvector, FeedbackAnalyzer), it can be implemented quickly and provides immediate value:

1. **Bot learns what works** for each user
2. **No model fine-tuning** required
3. **Per-user personalization** at scale
4. **Reversible and debuggable**
5. **Complements existing systems** (trust, memory, goals)

This is a natural evolution of the existing feedback system and a stepping stone toward more sophisticated learning mechanisms.

---

## Related Documents

- [TRUST_AND_EVOLUTION.md](../features/TRUST_AND_EVOLUTION.md) - Current feedback → trust system
- [USER_PREFERENCES.md](../features/USER_PREFERENCES.md) - Current preference detection
- [IMPLEMENTATION_ROADMAP_OVERVIEW.md](../IMPLEMENTATION_ROADMAP_OVERVIEW.md) - Phase C1 Reasoning Traces
- [BOT_SELF_LEARNING_ANALYSIS.md](../features/BOT_SELF_LEARNING_ANALYSIS.md) - Why not learn about self
