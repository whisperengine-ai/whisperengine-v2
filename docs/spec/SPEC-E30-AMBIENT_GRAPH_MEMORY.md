# Ambient Graph Memory Retrieval (Phase E30)

**Document Version:** 1.0
**Created:** December 7, 2025
**Status:** 📋 Proposed (Design Phase)
**Type:** Feature Specification
**Priority:** 🟡 Medium (Memory Quality Enhancement)
**Dependencies:** E19 (Graph Walker Agent) ✅, E25 (Graph Enrichment) ✅

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Ambient Graph Memory Proposal (external design doc) |
| **Proposed by** | Mark + Claude (collaborative) |
| **Catalyst** | Tool-based retrieval feels like "checking notes" rather than remembering |
| **Key insight** | Memory should be something a character *has*, not something they *do* |

---

> ⚠️ **Emergence Check:** This design shifts retrieval from explicit tool calls to automatic context assembly. This is a *mechanism* change, not a new data structure. The graph walker already exists (E19); this reuses it in the perception layer rather than the action layer.

---

## Executive Summary

**Problem:** Characters currently retrieve graph context via explicit tool calls. This creates visible "checking notes" seams—the character decides to remember, queries, then incorporates results. Human memory doesn't work this way.

**Solution:** Surface relevant graph connections during context assembly (before generation), so characters find themselves *knowing* things rather than *looking them up*.

**Approach:** Lightweight entity extraction from incoming messages → 1-hop graph traversal → inject top results into context window alongside existing memory/knowledge retrieval.

---

## The Core Question

> Should memory feel like something a character *does*, or something a character *has*?

Human memory doesn't require deciding to remember. The smell of salt air activates beach memories without conscious retrieval. Ambient graph walking aims to create that same quality—context surfacing because it's relevant, not because the character performed a lookup.

The trade-off is control: ambient retrieval means the system decides what's relevant, not the character. But if the goal is making memory feel *owned* rather than *accessed*, that's the direction to move.

---

## Current State Analysis

### What Already Exists

Looking at the codebase, we already have significant infrastructure:

| Component | Location | What It Does |
|-----------|----------|--------------|
| **ContextBuilder** | `src_v2/agents/context_builder.py` | Parallel context assembly (trust, goals, diary, dream, knowledge, etc.) |
| **MasterGraphAgent** | `src_v2/agents/master_graph.py` | Orchestrates context_node → classifier_node → prompt_builder_node |
| **GraphWalker** | `src_v2/knowledge/walker.py` | BFS traversal with scoring heuristics (recency, frequency, trust, novelty) |
| **KnowledgeManager** | `src_v2/knowledge/manager.py` | `get_user_knowledge()`, `find_common_ground()`, `query_graph()` |
| **FactExtractor** | `src_v2/knowledge/extractor.py` | LLM-based entity extraction (used for writing to graph) |
| **GraphEnrichmentAgent** | `src_v2/knowledge/enrichment.py` | Background edge creation (DISCUSSED, CONNECTED_TO, RELATED_TO) |
| **explore_for_context()** | `src_v2/knowledge/walker.py:930` | Already exists—purpose-built for query context enrichment |

### Current Context Assembly Flow

```
User message arrives
    → master_graph_agent.context_node() runs in parallel:
        - memory_manager.search_memories(query)      ← Vector similarity
        - knowledge_manager.find_common_ground()     ← Static Neo4j query
        - context_builder.get_knowledge_context()    ← Static Neo4j query (background match)
        - context_builder.get_evolution_context()    ← Trust/mood
        - context_builder.get_goal_context()         ← Active goals
        - context_builder.get_diary_context()        ← Recent diary
        - context_builder.get_dream_context()        ← Dream if applicable
        - context_builder.get_stigmergy_context()    ← Shared artifacts
    → Assembled into system prompt
    → Classification → Prompt building → Response generation
```

### The Gap

The current `get_knowledge_context()` does:
1. `find_common_ground()` — finds shared facts between user and character (hardcoded query)
2. `search_bot_background()` — keyword match against character background

**What's missing:** Entity-driven graph traversal from the *incoming message*. We have `GraphWalker.explore_for_context()` but it's only used in the `ExploreGraphTool` (explicit tool call), not in ambient context assembly.

---

## Proposed Architecture

### New Flow

```
User message arrives
    → master_graph_agent.context_node() runs in parallel:
        - [existing retrievals]
        - **NEW: ambient_graph_context(user_message, user_id, character_name)**
            → Fast entity extraction (regex + known entities, no LLM)
            → GraphWalker.explore() with entities as seeds
            → Score and filter to top 3-5 nodes
            → Format as prose context
    → Assembled into system prompt (invisible to character)
    → Character generates response (retrieval invisible)
```

### Design Principles

1. **Retrieval at intake, not generation** — Before the character LLM sees the message, context is pre-loaded
2. **Entity extraction drives traversal** — Extract entities from message, use as graph seeds
3. **No LLM for extraction** — Use regex + cached known entities (fast)
4. **LLM only for interpretation** — Optional: Single LLM call to narrate findings (or just format as prose)
5. **Strict token budget** — Max ~200 tokens for ambient context
6. **Graceful degradation** — If nothing found, just proceed with existing context

---

## Implementation Plan

### Phase 1: Instrument Current State (1-2 hours)

**Goal:** Measure what we have before building anything new.

**Tasks:**
- [ ] Add logging to `get_knowledge_context()` to track:
  - What `find_common_ground()` returns (or doesn't)
  - What `search_bot_background()` matches
  - Time taken for each query
- [ ] Create test cases: "User mentions X, character should know Y"
  - Pet names that are in the graph
  - Shared interests that are in common ground
  - Previously discussed topics

**Metrics to capture:**
- % of messages where common_ground returns something useful
- % of messages where background match fires
- Latency of current knowledge retrieval

**Deliverable:** Baseline understanding of current retrieval effectiveness.

### Phase 2: Known Entity Matching (1-2 hours)

**Goal:** Find mentions of entities we already know about from the graph.

**Key Insight:** This is a **lookup problem**, not an NLP problem. We're not discovering new entities—we're checking if the message mentions things already in the user's graph.

**Approach:**
```python
# src_v2/knowledge/entity_matcher.py

class EntityMatcher:
    """
    Fast entity matching for ambient retrieval.
    No LLM, no spaCy — just cached graph lookup + string matching.
    """
    
    def __init__(self):
        self._entity_cache: Dict[str, Tuple[Set[str], float]] = {}  # user_id -> (entities, timestamp)
        self._cache_ttl = 300  # 5 min cache
    
    async def find_mentioned_entities(
        self, 
        text: str, 
        user_id: str
    ) -> List[str]:
        """
        Check if message mentions any entities we already have in the graph.
        Pure string matching against cached known entities.
        
        Example:
            User says: "How's Luna doing in the cold?"
            Known entities: {"Luna", "Seattle", "marine biology"}
            Returns: ["Luna"]
        """
        known = await self._get_user_entities(user_id)
        
        text_lower = text.lower()
        matches = [e for e in known if e.lower() in text_lower]
        
        return matches[:5]  # Cap at 5 entities
    
    async def _get_user_entities(self, user_id: str) -> Set[str]:
        """
        Get entities connected to this user in Neo4j (cached).
        
        Query: MATCH (u:User {id: $user_id})-[:FACT]->(e:Entity) RETURN e.name
        """
        # Check cache
        if user_id in self._entity_cache:
            entities, timestamp = self._entity_cache[user_id]
            if time.time() - timestamp < self._cache_ttl:
                return entities
        
        # Query Neo4j
        entities = await self._fetch_from_graph(user_id)
        self._entity_cache[user_id] = (entities, time.time())
        
        return entities
```

**Why this works:**
- We're not *discovering* new entities (that's what `FactExtractor` does in background)
- We're asking: *"Did the user mention something we already know?"*
- String matching against a small set (~10-50 entities per user) is fast

**Why no spaCy/NLP:**
- We don't need NER to find "Luna" if we already have "Luna" in the graph
- Coreference resolution ("she" → "Luna") would be nice but not essential
- The overhead isn't worth it for this use case

**Deliverable:** `EntityMatcher` class that returns matches in <20ms.

### Phase 3: Ambient Graph Context (3-4 hours)

**Goal:** Wire entity extraction to graph walker in context assembly.

**Approach:**
```python
# src_v2/agents/context_builder.py

async def get_ambient_graph_context(
    self, 
    user_message: str, 
    user_id: str, 
    character_name: str
) -> str:
    """
    Surface relevant graph connections from the incoming message.
    
    Unlike get_knowledge_context (which uses static queries),
    this uses entity-driven graph traversal.
    """
    if not settings.ENABLE_AMBIENT_GRAPH_RETRIEVAL:
        return ""
    
    try:
        # 1. Fast entity extraction (no LLM)
        entities = await entity_recognizer.extract_entities(user_message, user_id)
        
        if not entities:
            return ""
        
        # 2. Graph walk from entities
        from src_v2.knowledge.walker import GraphWalker
        walker = GraphWalker()
        
        result = await walker.explore(
            seed_ids=entities,
            user_id=user_id,
            bot_name=character_name,
            max_depth=1,       # 1-hop only for speed
            max_nodes=10,      # Small budget
            serendipity=0.0    # No random walks for focused retrieval
        )
        
        if not result.nodes:
            return ""
        
        # 3. Format as natural prose (not metadata)
        return self._format_ambient_context(result, entities)
        
    except Exception as e:
        logger.debug(f"Ambient graph context failed: {e}")
        return ""

def _format_ambient_context(
    self, 
    result: GraphWalkResult, 
    seed_entities: List[str]
) -> str:
    """
    Format graph walk results as natural prose.
    
    NOT: "[Memory context - not visible to user]"
    YES: Natural sentences the character can internalize.
    """
    if not result.nodes:
        return ""
    
    lines = []
    for node in result.nodes[:5]:  # Top 5 by score
        # Format based on node type and relationship
        # e.g., "Mark has mentioned Luna (his cat) several times"
        # e.g., "Mark and you both enjoy marine biology"
        pass
    
    if not lines:
        return ""
    
    context = "\n\n[RELEVANT CONNECTIONS]\n"
    context += "\n".join(lines)
    context += "\n(These came up naturally in your memory. You can reference them if relevant.)\n"
    
    return context
```

**Integration point:** Add to `master_graph_agent.context_node()` task list.

**Deliverable:** Ambient context appearing in system prompts when entities match.

### Phase 4: Observe and Tune (ongoing)

**Goal:** Measure impact and iterate.

**Metrics to track:**
- Does the character reference ambient context naturally?
- Does it feel continuous (not "checking notes")?
- Any cases where surfaced memory was wrong/inappropriate?
- Latency impact on response time

**Tuning knobs:**
- `max_depth`: 1-hop vs 2-hop
- `max_nodes`: How many nodes to retrieve
- Token budget: How much context to inject
- Scoring weights: Recency vs frequency vs character affinity

---

## Context Budget Management

**Hard constraints:**
- Ambient context: max 200 tokens
- Only include nodes above score threshold (0.5)
- Deduplicate against existing context (common_ground already surfaces some of this)

**Format guidelines:**
- Natural prose, not metadata
- No "[Memory context]" markers visible to character
- Phrased as things the character "noticed" or "recalled"

---

## Hybrid Approach: Keep Both Systems

**Ambient retrieval** handles:
- Automatic surfacing of relevant context
- Maintaining conversational continuity
- Character "just knowing" established facts

**Tool-based retrieval** (existing) handles:
- Deep dives when character wants to explore
- Explicit "let me think about what I know" moments
- User-requested memory exploration ("what do you remember about X?")

This preserves character agency for intentional retrieval while ensuring baseline continuity is automatic.

---

## Character-Specific Considerations

Different characters might have different "access" patterns:

| Character | Ambient Focus | Rationale |
|-----------|---------------|-----------|
| **elena** | Marine themes, scientific connections | Anchored in marine biology |
| **dotty** | Emotional/relational nodes | Art and connection focused |
| **dream** | Symbolic/thematic connections | Mythological, abstract |
| **gabriel** | Historical/adventure nodes | Rugged explorer |

Implementation: Use existing `GraphWalker.thematic_anchors` to weight scores.

---

## Questions to Resolve

1. **Should the character *know* they're remembering?** Ambient retrieval makes memory invisible, but humans have metacognition about remembering. Consider occasionally phrasing as "something about that reminds me of..." rather than just knowing.

2. **Cross-character memory:** If Elena learned something, should Dotty know it ambientally? Current design: No—each character has their own ambient context. Cross-bot knowledge requires explicit graph walk or gossip system.

3. **Contradictory information:** What if ambient retrieval surfaces outdated facts? Mitigation: Recency scoring should prioritize recent edges. Monitor for confusion.

4. **Refresh mid-conversation:** Should ambient context refresh as new entities emerge? Initial design: Only at conversation start (per message). Could add session-level caching.

---

## Success Criteria

| Metric | Baseline (Estimate) | Target |
|--------|---------------------|--------|
| % of messages with relevant graph context | ~20% (common_ground only) | ~50% |
| Response continuity ("remembers" appropriately) | Qualitative: "sometimes" | Qualitative: "usually" |
| Latency impact | 0ms (no ambient) | <100ms added |
| "Checking notes" feel | Common (tool calls visible) | Rare |

---

## Implementation Timeline

| Phase | Description | Time | Status |
|-------|-------------|------|--------|
| 1 | Instrument current state | 1-2 hours | ✅ Complete |
| 2 | Known entity matching | 1-2 hours | 📋 Not started |
| 3 | Ambient graph context | 3-4 hours | 📋 Not started |
| 4 | Observe and tune | Ongoing | 📋 Not started |

**Total:** ~6-8 hours of implementation + ongoing observation

---

## Appendix: Comparison with Original Proposal

| Original Proposal | This Spec | Rationale |
|-------------------|-----------|-----------|
| "Entity extraction drives traversal" | Same | ✅ Core principle retained |
| "Weighted relevance scoring" | Use existing GraphWalker scoring | ✅ Already implemented in E19 |
| "Context budget management" | 200 token limit | ✅ Concrete limit |
| "Option A: BFS from entities" | 1-hop from entities | ✅ Simplest approach first |
| "Hybrid: ambient + tool" | Keep existing tools | ✅ Preserves agency |
| "LLM at interpretation" | Skip LLM, format as prose | Simpler, faster |
| "Semantic similarity + graph" | Defer to Phase 2 | Start simple |

---

## References

- [`docs/spec/SPEC-E19-GRAPH_WALKER_AGENT.md`](./SPEC-E19-GRAPH_WALKER_AGENT.md) — Graph Walker implementation
- [`docs/spec/SPEC-E25-GRAPH_WALKER_EXTENSIONS.md`](./SPEC-E25-GRAPH_WALKER_EXTENSIONS.md) — Graph enrichment
- [`src_v2/agents/context_builder.py`](../../src_v2/agents/context_builder.py) — Current context assembly
- [`src_v2/knowledge/walker.py`](../../src_v2/knowledge/walker.py) — Graph walker with scoring
- Original proposal: `ambient-graph-memory-proposal.md` (external document)
