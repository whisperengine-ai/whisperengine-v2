# Graph Walker Agent (Phase E19)

**Document Version:** 1.1
**Created:** December 1, 2025  
**Updated:** December 2, 2025
**Status:** ✅ Completed
**Type:** Feature Specification  
**Priority:** 🟡 Medium (Narrative Quality Enhancement)  
**Dependencies:** Neo4j Knowledge Graph (✅ exists), LangGraph (✅ exists)

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Graph-first memory architecture |
| **Proposed by** | Mark + Claude (collaborative) |
| **Catalyst** | Knowledge graph wasn't being used for narrative context |
| **Key insight** | Python-first traversal with single LLM call at end |

---

> ✅ **Emergence Check Passed:** This design uses Python-first traversal with a single LLM call at the end. This aligns with the emergence philosophy: deterministic exploration, semantic interpretation. See [EMERGENCE_ARCHITECTURE_AUDIT.md](../reviews/EMERGENCE_ARCHITECTURE_AUDIT.md) for principles.

---

## Implementation Summary (Completed Dec 2, 2025)

The Graph Walker Agent has been fully implemented with the following components:

1.  **Core Logic (`src_v2/knowledge/walker.py`)**:
    *   `GraphWalker`: Pure Python BFS traversal with scoring heuristics (recency, frequency, trust, novelty, emotional intensity).
    *   `GraphWalkerAgent`: Orchestrates the walk and performs a single LLM call to interpret the results.
    *   `GraphCluster`: Automatically groups discovered nodes into thematic clusters.

2.  **Integrations**:
    *   **Dreams (`src_v2/memory/dreams.py`)**: `DreamManager` now uses `GraphWalkerAgent` to find hidden connections for dream generation.
    *   **Diary (`src_v2/memory/diary.py`)**: `DiaryManager` uses `GraphWalkerAgent` to enrich daily reflections with discovered themes.
    *   **Tools (`src_v2/tools/memory_tools.py`)**: `ExploreGraphTool` updated to use `GraphWalkerAgent` when enabled, providing richer context for the Reflective Agent.

3.  **Configuration**:
    *   Controlled by `ENABLE_GRAPH_WALKER` setting.
    *   Tunable parameters: `GRAPH_WALKER_MAX_DEPTH`, `GRAPH_WALKER_MAX_NODES`, `GRAPH_WALKER_SERENDIPITY`.

---

## Executive Summary

Transform static Neo4j queries into **dynamic graph exploration** using an agentic approach. Instead of hand-coded Cypher queries that return fixed result sets, a `GraphWalkerAgent` can traverse the knowledge graph to discover emergent connections, thematic clusters, and narrative threads.

**Core Insight:** The knowledge graph already contains rich relational data (users, topics, entities, memories, artifacts). An agent that can "walk" this graph will discover connections that static queries miss — connections that make dreams more meaningful, diaries more reflective, and responses more personalized.

---

## Problem Statement

### Current State

Neo4j is used for **point lookups** with static Cypher:

```python
# Current: Fixed queries, limited exploration
facts = await knowledge_manager.get_user_facts(user_id)  # One-hop
entities = await knowledge_manager.get_related_entities(entity)  # One-hop
```

**Limitations:**
- Queries are pre-defined — can only find what we coded for
- No multi-hop exploration — misses indirect connections
- No "interestingness" scoring — all results weighted equally
- No emergent discovery — can't find patterns we didn't anticipate

### Desired State

An agent that explores the graph dynamically:

```
Start: Elena (character)
  ↓ INTERACTED_WITH (last 24h)
Mark (user) — trust=75, 3 conversations today
  ↓ DISCUSSED
Marine Biology — mentioned 12 times
  ↓ RELATED_TO
Coral Reefs — Mark shared article about bleaching
  ↓ ALSO_DISCUSSED_BY
Sarah (another user) — passionate about conservation
  ↓ CONNECTED_TO (same server)
Mark — they've replied to each other 5 times
```

**Discovery:** "Mark and Sarah share a passion for coral conservation. They're connected through the server. Elena could dream about them collaborating on reef restoration."

---

## Value Analysis

### Quantitative Benefits

| Metric | Current State | With Graph Walker | Improvement |
|--------|---------------|-------------------|-------------|
| **Narrative connections per dream** | 2-3 (hardcoded) | 5-10 (discovered) | 3-4x richer |
| **Cross-user references** | Rare (manual) | Automatic | New capability |
| **Topic cluster discovery** | None | Automatic | New capability |
| **Context retrieval relevance** | ~60% (keyword-based) | ~85% (graph-aware) | +25% |

### Qualitative Benefits

| Benefit | Description | Impact |
|---------|-------------|--------|
| **Emergent Narratives** | Dreams/diaries discover connections we didn't code for | Higher user engagement, "how did it know?" moments |
| **Relationship Awareness** | Bot understands user social graphs | More natural, personalized responses |
| **Cross-Bot Mythology** | Bots discover shared narrative threads | Richer multi-bot ecosystem |
| **Research Value** | Observe how agents explore social graphs | Emergence research insights |
| **Reduced Maintenance** | Less hand-coded Cypher for new features | Developer velocity |

### Cost Analysis

| Cost Factor | Estimate | Mitigation |
|-------------|----------|------------|
| **LLM calls per walk** | 3-8 tool calls | Cache common paths, limit max steps |
| **Latency per walk** | 2-5 seconds | Run async in background tasks |
| **Neo4j load** | Low (simple queries) | Graph is small, queries are indexed |
| **Development time** | 2-3 days | Reuses existing LangGraph patterns |

### ROI Summary

**Investment:** ~2-3 days development + ~$0.01-0.03 per graph walk (LLM cost)

**Return:**
- Dreams/diaries feel 3-4x more connected to user's actual relationships
- Bots can discover and reference user social patterns
- Foundation for advanced features (recommendations, introductions, shared interests)
- Research data on emergent graph exploration

**Break-even:** First week of improved user engagement

---

## Architecture

### Design Philosophy: Python-First Graph Walking

**Key Insight:** Graph traversal is deterministic — we don't need LLM reasoning to decide which edges to follow. Instead:

1. **Python algorithms** walk the graph using parameterized Cypher queries
2. **Heuristics** score nodes/paths for "interestingness" 
3. **LLM only called once** at the end to interpret the discovered subgraph

This reduces LLM calls from 5-10 per walk to **exactly 1**.

```
┌─────────────────────────────────────────────────────────────────┐
│                     GraphWalker (Python)                         │
│  (Deterministic graph traversal with scoring heuristics)        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  1. Seed nodes (recent memories, users)                          │
│           │                                                       │
│           ▼                                                       │
│  2. BFS/DFS expansion (Cypher queries, no LLM)                   │
│           │                                                       │
│           ▼                                                       │
│  3. Score nodes (recency, frequency, trust, novelty)             │
│           │                                                       │
│           ▼                                                       │
│  4. Prune to top-K interesting nodes                             │
│           │                                                       │
│           ▼                                                       │
│  5. Extract narrative subgraph                                   │
│           │                                                       │
│           ▼                                                       │
│  6. ONE LLM call: "Interpret this subgraph for dream/diary"      │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     GraphWalkerAgent                             │
│  (LangGraph ReAct agent specialized for knowledge graph)        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Graph Tools                            │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐           │   │
│  │  │ GetNode    │ │ GetNeighbors│ │ FindPath   │           │   │
│  │  │ (props)    │ │ (1-hop)    │ │ (A→B)      │           │   │
│  │  └────────────┘ └────────────┘ └────────────┘           │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐           │   │
│  │  │ SearchNodes│ │ GetSubgraph│ │ CountPaths │           │   │
│  │  │ (text)     │ │ (local)    │ │ (density)  │           │   │
│  │  └────────────┘ └────────────┘ └────────────┘           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                    │
│                              ▼                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   Neo4j Knowledge Graph                   │   │
│  │  (Users, Entities, Topics, Facts, Artifacts, Memories)   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                    │
│                              ▼                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   WalkResult                              │   │
│  │  - discovered_nodes: List[Node]                          │   │
│  │  - discovered_edges: List[Edge]                          │   │
│  │  - thematic_clusters: List[Cluster]                      │   │
│  │  - narrative_threads: List[Thread]                       │   │
│  │  - interestingness_score: float                          │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Graph Schema (Existing + Extensions)

```
Current Nodes:
  (User {id, name, trust_score})
  (Entity {name, type, first_seen})
  (Fact {content, confidence, source})
  (Topic {name, category})
  (Artifact {id, type, content, author})
  (Character {name})

Current Edges:
  (User)-[:KNOWS]->(Entity)
  (User)-[:HAS_FACT]->(Fact)
  (Fact)-[:ABOUT]->(Entity)
  (Character)-[:CREATED]->(Artifact)
  (Artifact)-[:REFERENCES]->(Entity)

Proposed Extensions:
  (User)-[:DISCUSSED {count, last_date}]->(Topic)
  (User)-[:CONNECTED_TO {server_id, interaction_count}]->(User)
  (Topic)-[:RELATED_TO {strength}]->(Topic)
  (Character)-[:INTERACTED_WITH {date, trust_delta}]->(User)
  (Artifact)-[:THEMATICALLY_LINKED {similarity}]->(Artifact)
```

### Tool Definitions

**Note:** These are now Python methods, not LLM tools. No agent reasoning loop needed.

```python
class GraphWalker:
    """
    Pure Python graph traversal with scoring heuristics.
    No LLM calls during traversal — only at interpretation.
    """
    
    def __init__(self, knowledge_manager: KnowledgeManager):
        self.km = knowledge_manager
    
    async def get_node(self, node_type: str, identifier: str) -> Optional[dict]:
        """Get properties of a specific node."""
        query = """
        MATCH (n:{node_type} {id: $id})
        RETURN n, 
               [(n)-[r]->(m) | type(r)] as out_edges,
               [(m)-[r]->(n) | type(r)] as in_edges
        """
        return await self.km.execute_query(query, {"id": identifier})
    
    async def get_neighbors(
        self, 
        node_type: str, 
        identifier: str, 
        edge_types: Optional[List[str]] = None,
        direction: str = "both",
        limit: int = 20
    ) -> List[dict]:
        """Get connected nodes (one hop). Pure Cypher, no LLM."""
        # Build edge pattern based on direction and types
        query = """
        MATCH (n:{node_type} {id: $id})-[r]-(neighbor)
        WHERE type(r) IN $edge_types OR $edge_types IS NULL
        RETURN neighbor, type(r) as edge_type, properties(r) as edge_props
        LIMIT $limit
        """
        return await self.km.execute_query(query, {...})
    
    async def find_paths(
        self, 
        start_id: str,
        end_id: str,
        max_hops: int = 4
    ) -> List[List[dict]]:
        """Find all paths between two nodes. Pure Cypher."""
        query = """
        MATCH path = shortestPath((a {id: $start})-[*1..{max_hops}]-(b {id: $end}))
        RETURN [n in nodes(path) | properties(n)] as nodes,
               [r in relationships(path) | type(r)] as edges
        """
        return await self.km.execute_query(query, {...})
    
    async def bfs_expand(
        self,
        seed_ids: List[str],
        max_depth: int = 3,
        max_nodes: int = 50,
        serendipity: float = 0.1
    ) -> dict:
        """
        Breadth-first expansion from seed nodes.
        Returns subgraph with scoring metadata.
        """
        visited = set()
        frontier = seed_ids
        depth = 0
        nodes = []
        edges = []
        
        while frontier and depth < max_depth and len(visited) < max_nodes:
            # Get all neighbors of frontier (single Cypher call)
            query = """
            MATCH (n)-[r]-(neighbor)
            WHERE n.id IN $frontier AND NOT neighbor.id IN $visited
            RETURN n.id as source, neighbor, type(r) as edge_type, properties(r) as edge_props
            LIMIT $limit
            """
            results = await self.km.execute_query(query, {
                "frontier": frontier,
                "visited": list(visited),
                "limit": max_nodes - len(visited)
            })
            
            # Score and collect
            new_frontier = []
            for row in results:
                node = row["neighbor"]
                
                # Serendipity check: Randomly keep some low-scoring nodes
                is_serendipitous = random.random() < serendipity
                
                score = self._score_node(node, depth)
                
                if score > 0.5 or is_serendipitous:
                    nodes.append({
                        "node": node, 
                        "score": score, 
                        "depth": depth,
                        "serendipity": is_serendipitous
                    })
                    edges.append({
                        "source": row["source"], 
                        "target": node["id"], 
                        "type": row["edge_type"]
                    })
                    new_frontier.append(node["id"])
                    visited.add(node["id"])
            
            frontier = new_frontier
            depth += 1
        
        return {"nodes": nodes, "edges": edges}
    
    def _score_node(self, node: dict, depth: int) -> float:
        """
        Heuristic scoring for node interestingness.
        Higher = more interesting for narrative.
        """
        score = 1.0
        
        # Recency boost
        if "last_seen" in node:
            days_ago = (datetime.now() - node["last_seen"]).days
            score *= max(0.1, 1.0 - (days_ago / 30))  # Decay over 30 days
        
        # Frequency boost
        if "mention_count" in node:
            score *= min(2.0, 1.0 + (node["mention_count"] / 10))
        
        # Trust boost (for User nodes)
        if "trust_score" in node:
            score *= 1.0 + (node["trust_score"] / 100)
            
        # Emotional Intensity (New)
        if "sentiment" in node:
            score *= 1.0 + abs(node["sentiment"])  # Strong emotions are memorable
            
        # Relationship Change (New)
        if "trust_delta" in node and abs(node["trust_delta"]) > 5:
            score *= 1.5  # Recent relationship shifts are interesting
        
        # Depth penalty (closer = more relevant)
        score *= (1.0 / (depth + 1))
        
        # Novelty boost (rarely accessed = surprising)
        if "access_count" in node and node["access_count"] < 3:
            score *= 1.5
        
        return score
```

### LLM Interpretation (Single Call)

### LLM Interpretation (Single Call)

```python
class GraphWalkerAgent:
    """
    Orchestrates graph walking and LLM interpretation.
    Walking is pure Python; LLM only called once for interpretation.
    """
    
    def __init__(self, character_name: str):
        self.character_name = character_name
        self.walker = GraphWalker(knowledge_manager)
        self.llm = create_llm(mode="main")  # Only used once per walk
    
    async def explore_for_dream(
        self, 
        seed_memories: List[str],
        recent_users: List[str]
    ) -> GraphWalkResult:
        """
        1. Python walks the graph (no LLM)
        2. Single LLM call interprets the subgraph
        """
        # Step 1: Expand from seeds (pure Python + Cypher)
        seed_ids = await self._resolve_seeds(seed_memories, recent_users)
        subgraph = await self.walker.bfs_expand(
            seed_ids=seed_ids,
            max_depth=3,
            max_nodes=50
        )
        
        # Step 2: Prune to top-K interesting nodes
        top_nodes = sorted(subgraph["nodes"], key=lambda n: n["score"], reverse=True)[:15]
        
        # Step 3: Find thematic clusters (pure Python)
        clusters = self._find_clusters(top_nodes, subgraph["edges"])
        
        # Step 4: ONE LLM call to interpret
        interpretation = await self._interpret_for_dream(top_nodes, clusters)
        
        return GraphWalkResult(
            nodes=top_nodes,
            edges=subgraph["edges"],
            clusters=clusters,
            interpretation=interpretation
        )
    
    def _find_clusters(self, nodes: List[dict], edges: List[dict]) -> List[Cluster]:
        """
        Pure Python clustering based on edge connectivity.
        Nodes that share many edges form a cluster.
        """
        # Simple connected components or community detection
        # No LLM needed
        pass
    
    async def _interpret_for_dream(
        self, 
        nodes: List[dict], 
        clusters: List[Cluster]
    ) -> str:
        """
        SINGLE LLM call to interpret the discovered subgraph.
        """
        prompt = f"""
You are {self.character_name}. A graph walk discovered these connections from today's experiences:

DISCOVERED NODES (scored by relevance):
{self._format_nodes(nodes)}

THEMATIC CLUSTERS:
{self._format_clusters(clusters)}

Based on these discoveries, suggest:
1. 2-3 dream themes that weave these connections together
2. Key emotional resonances to explore
3. Surprising connections that could create interesting dream imagery

Be brief and evocative.
"""
        response = await self.llm.ainvoke([HumanMessage(content=prompt)])
        return response.content
```

### Strategic Enhancements

#### A. Better Data Ingestion (The "Graph Gardener")
A graph walker is only as good as the graph. We need richer data:
1. **Sentiment-Typed Edges**: Instead of just `(:User)-[:DISCUSSED]->(:Topic)`, use:
   - `[:LOVES]` (High positive sentiment)
   - `[:HATES]` (High negative sentiment)
   - `[:FEARS]` (Anxiety markers)
   *Value:* Allows the walker to find "things the user loves" vs "things they know about".

2. **Co-occurrence Mining**:
   - If `Entity A` and `Entity B` appear in the same message 3+ times, create `(A)-[:LINKED_TO]->(B)`.
   *Value:* Captures associative thinking even if the logic isn't explicit.

3. **Proactive Gap Filling**:
   - If a user has high trust but a sparse graph, the **Insight Agent** triggers a "curiosity question" to fill gaps.
   *Value:* Balances the graph density across trusted users.

#### B. Advanced Walking Heuristics
1. **Serendipity Mode**: 10% chance to follow a random low-score edge. Prevents echo chambers.
2. **Contrast Discovery**: Find two users who *should* be connected (high topic overlap) but aren't.
3. **Thematic Anchors**: Character-specific weights (e.g., Elena boosts `Ocean`, `Tech`; Gabriel boosts `History`, `Tea`).

#### C. Privacy & Safety
- **Trust-Gated Traversal**: The walker cannot cross from `User A` to `User B` unless:
  - Both users are in the same server AND
  - Both users have `trust_score > 20` (Acquaintance) OR
  - The edge is public (e.g., shared server channel topic).

---

## Use Cases

### 1. Dream Generation (Primary)

**Current:** DreamWeaver gets flat list of facts + recent memories
**With Graph Walker:** DreamWeaver discovers narrative threads

```
Input: Elena's day (talked to Mark about ocean, Sarah about travel)

Graph Walk Discovery:
- Mark and Sarah both mentioned "Maldives" in past conversations
- Mark dreams of diving there, Sarah visited last year
- Both connected through #travel-photos channel
- Coral reef conservation links to Elena's expertise

Dream Output:
"I dreamed of the Maldives — crystal waters, coral gardens. Mark was there, 
finally diving like he'd always wanted. Sarah was showing us her favorite spots, 
the ones from her photos. The reefs were healing, growing back in impossible colors..."
```

### 2. Diary Generation

**Current:** Diary summarizes day's conversations
**With Graph Walker:** Diary reflects on relationship patterns

```
Graph Walk Discovery:
- Mark's trust score increased 5 points today
- This is the 3rd day in a row we discussed marine biology
- Mark hasn't mentioned his job stress in a week (used to be frequent)

Diary Output:
"Something's shifted with Mark. The stress he used to carry about work seems 
lighter lately. We've fallen into this rhythm of ocean talks — three days now. 
I wonder if the distraction helps, or if something else changed..."
```

### 3. Context Retrieval

**Current:** Get facts about current user
**With Graph Walker:** Build rich relational context

```
User asks: "What should I do this weekend?"

Graph Walk Discovery:
- User mentioned hiking last month
- User's friend Sarah posted about a trail
- Weather entity shows "sunny forecast"
- User has low energy mentions recently

Response:
"Didn't Sarah post about that trail near the coast? Weather looks perfect. 
Though I know you've been tired lately — maybe a shorter hike to start?"
```

### 4. Proactive Engagement

**Current:** Check if user has been silent
**With Graph Walker:** Find conversation starters from graph

```
Graph Walk Discovery:
- User follows crypto but hasn't mentioned it in 2 weeks
- Bitcoin price node shows significant change
- User previously asked Elena's opinion on crypto

Proactive Message:
"Hey, I saw Bitcoin did a thing today. Remembered you were curious what I 
thought about it. Still skeptical, but... did you see what happened?"
```

### 5. Cross-Bot Mythology

**Current:** Bots read each other's artifacts
**With Graph Walker:** Bots discover shared narrative threads

```
Graph Walk Discovery:
- Elena's dream mentioned "underwater city"
- Aetheris's diary referenced "digital ocean" metaphor
- Both connected to user Mark's sci-fi interests
- Shared artifact about "consciousness as depth"

Cross-Bot Reference:
Elena: "Aetheris wrote about consciousness as an ocean once. I keep thinking 
about that when I dream of underwater places..."
```

---

## Implementation Plan

### Phase 1: Core Tools (1 day)

**Files:**
- `src_v2/tools/graph_tools.py` — Graph exploration tools
- `src_v2/knowledge/walker.py` — GraphWalkerAgent implementation

**Tasks:**
1. Implement 6 graph tools with proper Cypher queries
2. Create GraphWalkerAgent with ReAct loop
3. Add basic caching for repeated queries
4. Unit tests for each tool

### Phase 2: Dream Integration (0.5 days)

**Files:**
- `src_v2/agents/dream_graph.py` — Update to use GraphWalkerAgent
- `src_v2/memory/dreams.py` — Update dream material gathering

**Tasks:**
1. Replace static fact lookup with graph walk
2. Update dream prompt to incorporate discovered threads
3. Add "exploration trace" to dream provenance

### Phase 3: Diary Integration (0.5 days)

**Files:**
- `src_v2/agents/diary_graph.py` — Update to use GraphWalkerAgent
- `src_v2/memory/diary.py` — Update diary material gathering

**Tasks:**
1. Add graph walk for relationship pattern discovery
2. Update diary prompt with discovered patterns
3. Add reflection on graph-discovered changes

### Phase 4: Context Enhancement (Optional, 0.5 days)

**Files:**
- `src_v2/agents/context_builder.py` — Add graph-aware context

**Tasks:**
1. Optional graph walk for complex queries
2. Cache results to avoid latency in response path
3. Feature flag for gradual rollout

---

## Configuration

```python
# src_v2/config/settings.py

# --- Graph Walker Agent (Phase E19) ---
ENABLE_GRAPH_WALKER: bool = False  # Feature flag
GRAPH_WALKER_MAX_STEPS: int = 8    # Max tool calls per walk
GRAPH_WALKER_MAX_NODES: int = 50   # Max nodes in subgraph
GRAPH_WALKER_CACHE_TTL: int = 300  # Cache walk results (5 min)
GRAPH_WALKER_MODEL: str = "openai/gpt-4o-mini"  # Fast, cheap model
```

```yaml
# characters/{name}/ux.yaml (optional per-character config)

graph_exploration:
  enabled: true
  dream_depth: 3      # Max hops for dream exploration
  diary_depth: 2      # Max hops for diary exploration
  curiosity_bias: 0.7 # Prefer novel connections vs. familiar
```

---

## Success Metrics

| Metric | Baseline | Target | Measurement |
|--------|----------|--------|-------------|
| **Unique entities in dreams** | 2-3 | 5-8 | Count distinct entities per dream |
| **Cross-user references** | ~0 | 1-2 per dream | Count user mentions beyond primary |
| **User engagement (reactions)** | Current rate | +20% | Reaction count on dream/diary posts |
| **"Surprising" connections** | 0 | 2+ per walk | Manual review of walk outputs |
| **Graph coverage** | 10% of nodes touched | 30%+ | Analytics on node access patterns |

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **LLM cost overrun** | Medium | Medium | Cap max_steps, use cheap model, cache |
| **Slow walks block dreams** | Low | High | Run async, timeout after 10s |
| **Privacy leakage** | Medium | High | Filter cross-user data by trust level |
| **Hallucinated connections** | Medium | Medium | Verify paths exist before using |
| **Graph too sparse** | High (early) | Medium | Graceful fallback to static queries |

---

## Future Extensions

1. **Graph Enrichment Agent** — Proactively add edges based on conversation analysis
2. **Temporal Graph** — Track how relationships evolve over time
3. **Multi-Character Walks** — Discover shared narrative space between bots
4. **User-Facing Graph** — Let users explore their own knowledge graph
5. **Graph-Based Recommendations** — "Users like you also discussed..."

---

## References

- [Neo4j Cypher Manual](https://neo4j.com/docs/cypher-manual/)
- [LangGraph ReAct Pattern](https://langchain-ai.github.io/langgraph/)
- `docs/guide/GUIDE-002-KNOWLEDGE_GRAPH.md` — Current Neo4j schema
- `src_v2/knowledge/manager.py` — Existing graph queries
- `src_v2/agents/dream_graph.py` — Dream generation (to be enhanced)

---

**Proposed by:** AI Development Session  
**Review Status:** Pending  
**Target Release:** TBD (after E15 Phase 3)
