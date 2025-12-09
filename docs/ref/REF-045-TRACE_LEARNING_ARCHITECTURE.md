# REF-045: Trace Learning Architecture

**Version:** 1.0  
**Last Updated:** December 8, 2025  
**Status:** Reference Documentation  
**Author:** WhisperEngine Team (Claude collaboration)

---

## Overview

This document answers architectural questions about WhisperEngine v2's trace-based learning system, bridging the System 1/System 2 cognitive architecture discussion with concrete implementation details.

**Key Insight:** WhisperEngine implements **retrieval-augmented in-context learning** using the system's own execution history. This is NOT fine-tuning — it's agents that accumulate operational knowledge about what works and continuously improve through self-supervised learning from their own execution patterns.

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Architecture discussion between Claude instances |
| **Proposed by** | Mark (system design) + Claude collaboration |
| **Catalyst** | Handoff document bridging System 1/2 conceptual model with implementation |
| **Key insight** | The "transfer mechanism" from System 2 to System 1 is trace injection as few-shot examples |

---

## 1. Trace Storage Implementation

**Storage happens in two stages:**

### Stage 1: Trace Capture

Location: `src_v2/agents/engine.py` → `_format_trace_for_storage()`

When a reflective mode response completes, the method extracts:
- Tools used (deduplicated)
- Reasoning steps (truncated to 200 chars each)
- User query and final response

```python
def _format_trace_for_storage(self, trace, user_query, final_response):
    # Extracts tool calls from AIMessage.tool_calls
    # Extracts reasoning content from AIMessage.content
    # Formats as structured trace for InsightAgent
    return f"""[REFLECTIVE TRACE]
User Query: {user_query}
Tools Used: {', '.join(set(tools_used))}
Reasoning Steps: {len(reasoning_steps)}
Final Response: {final_response[:150]}...
"""
```

### Stage 2: Async Analysis & Storage

The formatted trace is enqueued to InsightAgent via `task_queue.enqueue_insight_analysis()`. The `StoreReasoningTraceTool` (`src_v2/tools/insight_tools.py`) then persists to Qdrant:

```python
await memory_manager.save_typed_memory(
    memory_type="reasoning_trace",
    content=f"[REASONING TRACE] Pattern: {query_pattern}\nApproach: {successful_approach}...",
    metadata={
        "query_pattern": query_pattern,
        "tools_used": tools_used.split(","),
        "complexity": complexity  # e.g., "COMPLEX_LOW"
    },
    collection_name=f"whisperengine_memory_{character_name}"
)
```

### Retrieval

Location: `src_v2/memory/traces.py` → `TraceRetriever.get_relevant_traces()`

1. Performs **semantic search** via `memory_manager.search_reasoning_traces()`
2. Filters by **similarity threshold** (0.75 cosine similarity)
3. Retrieves up to 5 traces, scores them, returns top 2

---

## 2. Success Definition & Measurement

### Quality Scoring Formula

Location: `src_v2/memory/traces.py` → `TraceQualityScorer`

| Factor | Points | Condition |
|--------|--------|-----------|
| Base Success | +10 | All stored traces (implicit success) |
| Efficiency Bonus | +5 | Fewer than 3 tools used |
| Retry Penalty | -5 | Content contains "retry" or "failed" |
| User Feedback | ±5 | From InfluxDB reaction data (if available) |

**Minimum threshold:** Quality score must be ≥5.0 to be used as few-shot example.

### Implicit Success Model

Success is **implicit** — only traces from *completed* reflective sessions get stored. Failed sessions don't reach the storage pipeline. The reasoning:

1. If ReflectiveAgent completed without errors → trace is stored
2. If session failed/errored → no trace storage triggered
3. User reactions (👍/👎) provide post-hoc quality adjustment

---

## 3. Trace Selection Algorithm

Location: `src_v2/memory/traces.py` → `TraceRetriever.get_relevant_traces()`

```
1. SEMANTIC SEARCH via Qdrant (384D embeddings)
   └─ Query: current user message
   └─ Collection: whisperengine_memory_{bot_name}
   └─ Filter: memory_type="reasoning_trace"
   └─ Limit: MAX_TRACES_TO_SCORE (5)

2. FILTER by similarity ≥ 0.75 (cosine)

3. PARSE each trace into ScoredTrace dataclass
   └─ Extracts: query_pattern, successful_approach, tools_used, complexity

4. SCORE using quality formula
   └─ Base success + efficiency bonus - retry penalty + feedback

5. SORT by quality score (descending)

6. LIMIT to MAX_TRACES_TO_INJECT (2)
```

### Configuration Constants

| Constant | Value | Purpose |
|----------|-------|---------|
| `SIMILARITY_THRESHOLD` | 0.75 | Minimum cosine similarity |
| `MAX_TRACES_TO_SCORE` | 5 | Candidates to retrieve |
| `MAX_TRACES_TO_INJECT` | 2 | Traces added to prompt |
| `MIN_QUALITY_THRESHOLD` | 5.0 | Minimum quality score |

---

## 4. Integration with 5-Database Architecture

| Database | Role in Trace Learning |
|----------|----------------------|
| **Qdrant** | Primary storage. Traces stored as `memory_type="reasoning_trace"` in per-bot collections (`whisperengine_memory_{bot_name}`) |
| **PostgreSQL** | Not directly used for traces, but stores chat history that informs trace context |
| **Neo4j** | Not directly used, but facts extracted during trace sessions are stored here |
| **InfluxDB** | Metrics: `trace_reused` point tracks when traces are injected (for observing learning effectiveness) |
| **Redis** | Task queue (`arq`) for async trace analysis jobs |

### Key Architectural Decision

Traces are stored **per-character** in their own Qdrant collection, not in a shared pool. This means:
- Each bot learns its own patterns
- No cross-bot trace contamination
- Different characters can develop different problem-solving styles

---

## 5. Prompt Engineering for Trace Injection

Location: `src_v2/agents/reflective_graph.py` (lines 577-590)

```python
if settings.ENABLE_TRACE_LEARNING:
    traces = await trace_retriever.get_relevant_traces(query=user_input, ...)
    if traces:
        few_shot_section = trace_retriever.format_few_shot_section(traces)
        full_prompt = f"{full_prompt}\n\n{few_shot_section}"
        if callback:
            await callback(f"📚 Found {len(traces)} similar solved problems")
```

### Few-Shot Format

The `format_few_shot_section()` method produces:

```
SIMILAR PROBLEMS YOU'VE SOLVED BEFORE:
[EXAMPLE: Similar problem solved successfully]
Problem Type: Weather request
Approach: Use search then format
Tools Used: search_tool, format_tool
---
[EXAMPLE: Similar problem solved successfully]
Problem Type: Emotional support
Approach: Validate feelings, offer perspective
Tools Used: memory_search
---
```

### Design Rationale

Framed as "here's what you did before that worked" — letting the LLM pattern-match to its own past successes. This leverages:
- In-context learning (no weight updates needed)
- Self-consistency (the LLM trusts its own prior reasoning)
- Transferable patterns (similar problems get similar solutions)

---

## 6. Performance & Scaling Considerations

### Current Limits

| Aspect | Value | Notes |
|--------|-------|-------|
| Traces retrieved | 5 | Per query, for scoring |
| Traces injected | 2 | Added to system prompt |
| Similarity threshold | 0.75 | Cosine similarity |
| Token overhead | ~100-200 | Per few-shot section |

### Cost Analysis

| Operation | Timing | Cost Impact |
|-----------|--------|-------------|
| Trace analysis | Async via arq | Doesn't block response |
| Semantic search | ~10-50ms | Fast (Qdrant optimized) |
| Few-shot injection | Inline | Adds to prompt tokens |
| Quality scoring | ~5ms | In-memory calculation |

### Scaling Notes

1. **Per-bot isolation**: Each bot has its own trace collection → no cross-bot contention
2. **InfluxDB metrics**: Enable monitoring trace reuse rate via `trace_reused` points
3. **Feature gating**: `ENABLE_TRACE_LEARNING=true` allows per-bot control
4. **Background processing**: Trace extraction doesn't block user response

---

## 7. Integration with Other Systems

### Relationship to Other Learning Systems

| System | What It Learns | Scope |
|--------|---------------|-------|
| **Trace Learning** | "How did I solve this type of problem?" | Per-character, reasoning patterns |
| **Universe Event Bus** | "What happened to users I care about?" | Cross-character, life events |
| **Autonomous Drives** | "Should I proactively engage?" | Per-character, social dynamics |

### Current Integration Status

**No direct integration currently**, but systems are complementary:

- Traces from cross-bot conversations are stored with same pipeline
- Universe events don't trigger trace analysis (potential future work)
- Autonomous drives don't consult past traces (potential future work)

### Potential Synergies (Future Work)

1. **Cross-bot trace tagging**: Mark traces from bot-to-bot conversations differently
2. **Event-triggered trace retrieval**: "How did I handle congratulating someone before?"
3. **Drive-informed trace selection**: Prioritize traces matching current social context

---

## 8. System Architecture Diagram

```
USER INPUT
    │
    ▼
┌───────────────────────────────────────────┐
│  SYSTEM 1: ComplexityClassifier (fast)    │
│  - Routes simple → direct LLM response    │
│  - Routes complex → ReflectiveAgent       │
└───────────────────────────────────────────┘
    │ (if complex)
    ▼
┌───────────────────────────────────────────┐
│  SYSTEM 2: ReflectiveAgent (LangGraph)    │
│  - Injected with past successful traces   │◄─── TRACE RETRIEVAL
│  - Runs ReAct loop with tools             │     (Qdrant semantic search)
│  - Generates new traces on completion     │
└───────────────────────────────────────────┘
    │
    ▼
┌───────────────────────────────────────────┐
│  TRACE STORAGE (background via arq)       │
│  - InsightAgent extracts patterns         │
│  - Stores to Qdrant for future retrieval  │───► QDRANT
└───────────────────────────────────────────┘     (per-bot collection)
```

**Transfer Mechanism:** System 2 literally gets smarter by injecting its own past successes as few-shot examples. This is the "muscle memory" that accumulates over time.

---

## 9. Open Questions & Future Work

### Trace Lifecycle

**Current state:** No decay/expiration. Old traces persist indefinitely.

**Questions:**
- Should we add TTL or quality-based pruning?
- Do old traces become less relevant over time?
- How do we handle trace collection growth?

### Failure Tracking

**Current state:** We don't store failed traces as negative examples.

**The spec mentions** `include_negative` parameter but it's not implemented.

**Potential value:**
- "Don't do what failed before"
- Learn from tool errors
- Avoid repeated mistakes

### Meta-Learning

**Current state:** No tracking of *which types of traces* are most useful.

**Potential implementation:**
- InfluxDB metrics: "trace X was injected → user gave 👍 reaction"
- Learn which trace patterns correlate with positive outcomes
- Adjust retrieval weights based on trace effectiveness

### Cross-Character Trace Sharing

**Current state:** Per-bot only.

**Potential implementation:**
- Create `whisperengine_shared_traces` collection
- Store universal patterns (e.g., "how to handle emotional support requests")
- Privacy-aware sharing (similar to gossip system)

---

## 10. Feature Flag & Configuration

### Environment Variable

```bash
ENABLE_TRACE_LEARNING=true  # Default: true
```

### Settings Reference

Location: `src_v2/config/settings.py`

```python
ENABLE_TRACE_LEARNING: bool = True  # Phase B5: Learn from reasoning traces
```

### Monitoring

InfluxDB metrics for trace learning:

| Metric | Tags | Fields |
|--------|------|--------|
| `trace_reused` | bot_name, user_id, problem_type, complexity | quality_score, similarity_score |

---

## Related Documentation

- `docs/spec/SPEC-B05-TRACE_LEARNING.md` — Original specification
- `docs/guide/GUIDE-022-TRACE_LEARNING.md` — Implementation guide
- `docs/ref/REF-001-COGNITIVE_ENGINE.md` — Cognitive engine reference
- `docs/IMPLEMENTATION_ROADMAP_OVERVIEW.md` — Phase B5 status

---

## Implementation Files

| File | Purpose |
|------|---------|
| `src_v2/memory/traces.py` | `TraceRetriever`, `TraceQualityScorer`, `ScoredTrace` |
| `src_v2/agents/engine.py` | `_format_trace_for_storage()`, enqueue logic |
| `src_v2/agents/reflective_graph.py` | Few-shot injection (lines 577+) |
| `src_v2/tools/insight_tools.py` | `StoreReasoningTraceTool` |
| `tests_v2/test_trace_learning.py` | 12 unit tests |
