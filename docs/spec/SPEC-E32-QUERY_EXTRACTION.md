# SPEC-E32: Query Extraction for Improved Memory Retrieval

**Document Version:** 1.0
**Created:** 2025-12-10
**Updated:** 2025-12-10
**Status:** 📋 Proposed
**Priority:** 🟢 High
**Dependencies:** Classifier (SPEC-S02), Memory System (SPEC-E02)

> ✅ **Emergence Check:** This spec leverages the existing classifier LLM call — no new infrastructure. The extraction is observational (captures what the user is searching for) rather than prescriptive.

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Performance investigation during embedding benchmark |
| **Proposed by** | Claude (collaborative) during embedding upgrade analysis |
| **Catalyst** | Discovered 29% of messages exceed FastEmbed's 256 token limit, causing truncation during query embedding |
| **Key insight** | Context prefetch uses raw user_input for embedding, but LLM tools already get focused queries. We can piggyback on classifier to extract search terms. |
| **Decision factors** | Zero extra LLM calls (uses existing classifier), improves retrieval for long messages, enables temporal filtering |

---

## Executive Summary

When users send long messages (>500 chars), the embedding model truncates them to 256 tokens, losing potentially important search terms. Additionally, temporal queries like "yesterday" or "last week" are not translated into date filters.

This spec adds a `QueryExtraction` model to the existing complexity classifier, extracting:
- **search_terms**: Focused keywords for embedding (max 50 words)
- **time_range**: ISO date range for temporal filtering
- **entity_names**: Specific names for Neo4j lookups
- **memory_type**: Specific memory type (dream, diary, etc.)

**Cost:** ~30-50 extra output tokens when extraction is relevant, $0 when not needed. No additional LLM calls.

---

## Problem Statement

### Current State

1. **Query Truncation**: FastEmbed (all-MiniLM-L6-v2) has a 256 token limit. Messages over ~1024 chars get truncated.
   - Analysis: 29% of production messages (1,148/3,908) exceed this limit
   - Long creative writing, dreams, journal entries lose context

2. **No Temporal Filtering**: "What did we talk about yesterday?" embeds the word "yesterday" but doesn't filter by date.
   - Semantic search might find "yesterday" in text, but won't restrict to actual yesterday

3. **Context Prefetch vs Tools Mismatch**:
   - Context prefetch (master_graph.py line 113): Uses raw `user_input` → truncation
   - Tool execution: LLM generates focused query → works fine

### Desired State

1. Long messages get extracted to focused search terms before embedding
2. Temporal references resolve to actual date ranges
3. Entity names extracted for precise Neo4j lookups
4. Memory type hints enable targeted retrieval

---

## Architecture

### Design Philosophy

**Piggyback, Don't Add:** The classifier already runs on every message. We extend its output rather than adding a new LLM call.

**Extract When Relevant:** Only populate extraction fields when they add value:
- `search_terms`: Only if message > 500 chars
- `time_range`: Only if temporal reference detected
- `entity_names`: Only if specific names mentioned for lookup
- `memory_type`: Only if asking about dreams, diaries, etc.

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     User Message                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  ComplexityClassifier                        │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Router LLM (gemini-flash-lite, $0.10/M tokens)          ││
│  │                                                          ││
│  │ Input: User message + recent history                     ││
│  │                                                          ││
│  │ Output (structured):                                     ││
│  │   - complexity: SIMPLE | COMPLEX_LOW | COMPLEX_MID | ... ││
│  │   - intents: ["voice", "image_self", ...]               ││
│  │   - query: QueryExtraction (NEW)                        ││
│  │       - search_terms: "beach summer dog Max"            ││
│  │       - time_range: {"start": "2025-12-09", "end": ...} ││
│  │       - entity_names: ["Sarah", "Luna"]                 ││
│  │       - memory_type: "dream"                            ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌──────────────────────────┐    ┌──────────────────────────────┐
│   Context Prefetch       │    │   Tool Execution             │
│   (master_graph.py)      │    │   (reflective mode)          │
│                          │    │                              │
│ Uses extracted query:    │    │ LLM generates focused query  │
│ - search_terms for embed │    │ (already works fine)         │
│ - time_range for filter  │    │                              │
│ - entity_names for Neo4j │    │                              │
└──────────────────────────┘    └──────────────────────────────┘
```

### Data Model

```python
from pydantic import BaseModel, Field
from typing import Optional, List, Dict

class QueryExtraction(BaseModel):
    """Extracted query components for improved memory/knowledge retrieval.
    
    Only populated when relevant — most messages won't need extraction.
    """
    search_terms: Optional[str] = Field(
        default=None,
        description="For messages >500 chars: extract key search terms (names, topics, events). Max 50 words."
    )
    time_range: Optional[Dict[str, str]] = Field(
        default=None,
        description="If temporal reference detected (yesterday, last week, 3 days ago), ISO date range {start, end}. Today is {current_date}."
    )
    entity_names: Optional[List[str]] = Field(
        default=None,
        description="Specific names of people, places, pets, or things mentioned that should be looked up in knowledge graph."
    )
    memory_type: Optional[str] = Field(
        default=None,
        description="If user asks about specific memory type: 'dream', 'diary', 'conversation', 'summary', 'epiphany', 'gossip'."
    )


class ClassificationOutput(BaseModel):
    complexity: ClassificationResult = Field(...)
    intents: List[str] = Field(...)
    query: Optional[QueryExtraction] = Field(
        default=None,
        description="Query extraction for improved retrieval. Only populate if message needs extraction."
    )
```

### Prompt Addition

Add to classifier system prompt:

```
QUERY EXTRACTION (for improved memory retrieval):
When relevant, extract query components to help find the right memories:

- search_terms: If message is long (>500 chars), extract the key search terms (names, topics, dates, events mentioned). Max 50 words. Focus on WHAT the user is asking about, not the full message.
  Example: "I had an amazing day at the beach with my dog Max and we built sandcastles..." → "beach dog Max sandcastles"

- time_range: If user references a time period, convert to ISO dates. Today is {current_date}.
  - "yesterday" → {"start": "2025-12-09", "end": "2025-12-10"}
  - "last week" → {"start": "2025-12-03", "end": "2025-12-10"}
  - "3 days ago" → {"start": "2025-12-07", "end": "2025-12-08"}
  - "in November" → {"start": "2025-11-01", "end": "2025-11-30"}

- entity_names: If user mentions specific people, pets, places by name that should be looked up.
  Example: "Do you remember my sister Sarah and her cat Luna?" → ["Sarah", "Luna"]

- memory_type: If user asks about a specific type of memory.
  Example: "What did I dream about?" → "dream"
  Example: "Check your diary" → "diary"

Only include fields that are relevant. Most short messages need no extraction.
```

---

## Implementation Plan

### Phase 1: Classifier Extension (~1 day)

**File: `src_v2/agents/classifier.py`**

1. Add `QueryExtraction` model
2. Add `query` field to `ClassificationOutput`
3. Add extraction instructions to prompt
4. Inject `{current_date}` into prompt for temporal resolution

### Phase 2: Context Prefetch Integration (~1 day)

**File: `src_v2/agents/master_graph.py`**

1. Accept `classification` result in `_build_context()`
2. Use `query.search_terms` for memory search if available
3. Use `query.entity_names` for knowledge graph query if available

**File: `src_v2/memory/manager.py`**

4. Add `time_range` parameter to `search_memories()`
5. Filter results by timestamp if time_range provided (post-retrieval filter initially, Qdrant native filter later)

### Phase 3: Observability (~0.5 days)

1. Add extraction metrics to InfluxDB (which fields were populated, message lengths)
2. Log extraction results at DEBUG level

---

## Configuration

```python
# No new settings needed - uses existing classifier
# Extraction is automatic based on message characteristics
```

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Temporal query accuracy | >90% correct date range | Manual test suite |
| Long message retrieval | Improved relevance scores | A/B test on 29% long messages |
| Extraction overhead | <50 tokens avg when triggered | InfluxDB metrics |
| No latency regression | <50ms added to classification | InfluxDB timing |

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| LLM extraction errors | Medium | Low | Fallback to raw query if extraction fails |
| Temporal ambiguity ("next week" is future, not past) | Medium | Low | Prompt specifies "for memory lookup, use past dates" |
| Increased token cost | Low | Low | Only ~30-50 tokens when extraction needed |
| Router LLM quality for extraction | Medium | Medium | Test with production messages, can tune prompt |

---

## Future Enhancements

1. **Qdrant Native Time Filter**: Store timestamps as Unix epoch, enable Range filter in Qdrant query
2. **Entity Linking**: Use entity_names to boost Neo4j graph traversal
3. **Multi-Query Expansion**: Generate multiple search queries for complex questions
4. **Caching**: Cache extraction for similar messages

---

## References

- SPEC-E02: Advanced Memory Retrieval (current memory system)
- SPEC-S02: Classifier Observability (metrics infrastructure)
- ADR-003: Emergence Philosophy (observe-first principle)
- FastEmbed docs: 256 token limit for all-MiniLM-L6-v2
