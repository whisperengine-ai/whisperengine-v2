# Graph Walker Extensions (Phases E25-E29)

**Document Version:** 1.1
**Created:** December 3, 2025
**Last Updated:** December 4, 2025
**Status:** 🔄 In Progress (E25 Complete)
**Type:** Feature Specification (Multi-Phase)
**Priority:** 🟡 Medium (Research & Narrative Enhancement)
**Dependencies:** E19 (Graph Walker Agent) ✅

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Graph Walker success follow-up |
| **Proposed by** | Mark + Claude (collaborative) |
| **Catalyst** | E19 completion opened new graph capabilities |
| **Key insight** | Extend graph with enrichment, temporal, and multi-character walks |

---

> ✅ **Emergence Check Passed:** These extensions follow the "observe first, constrain later" principle. No new Neo4j node types are added—all enhancements work through edge properties, scoring heuristics, and emergent discovery. See [ADR-003-EMERGENCE_PHILOSOPHY.md](../adr/ADR-003-EMERGENCE_PHILOSOPHY.md).

---
Five extensions to the Graph Walker Agent that deepen the knowledge graph's value:

| Phase | Name | Purpose | Time | Status |
|-------|------|---------|------|--------|
| E25 | Graph Enrichment Agent | Proactively add edges from conversation analysis | 2-3 days | ✅ Complete |
| E26 | Temporal Graph | Weight relationships by evolution over time | 1-2 days | ✅ Complete |
| E27 | Multi-Character Walks | Discover shared narrative space between bots | 2-3 days | ✅ Complete |
| E28 | User-Facing Graph | Let users explore their own knowledge graph | 2-3 days | 📋 Proposed |
| E29 | Graph-Based Recommendations | "Users like you also discussed..." | 1-2 days | 📋 Proposed |

**Total Estimated Time:** 8-13 days (non-sequential, can parallelize)

**Core Principle:** These features enhance graph *discovery* without adding schema complexity. The philosophy is:
- **E25**: Let the system *notice* connections, not declare them
- **E26**: Let relationships *age* naturally via scoring, not timestamps
- **E27**: Let bots *discover* shared space, not be told about it
- **E28**: Let users *explore* what exists, not curate a presentation
- **E29**: Let similarity *emerge* from graph structure, not be computed

---

## Phase E25: Graph Enrichment Agent

**Priority:** 🟢 High | **Time:** 2-3 days | **Complexity:** Medium
**Status:** ✅ Complete (December 4, 2025)
**Dependencies:** E19 ✅, Insight Worker ✅

### Problem

The knowledge graph only grows when facts are explicitly extracted. Implicit connections go unnoticed:
- Two users discuss the same topic but aren't linked
- Topics that co-occur repeatedly aren't marked as related
- User-to-user connections through shared servers aren't tracked

### Solution

A background worker that analyzes conversations and proactively enriches the graph with discovered edges.

### Edge Types to Create

| Edge | Pattern | Example |
|------|---------|---------|
| `(User)-[:DISCUSSED {count, last_date}]->(Topic)` | User mentions topic 3+ times | `(Mark)-[:DISCUSSED {count: 7}]->(Marine Biology)` |
| `(User)-[:CONNECTED_TO {server_id, interaction_count}]->(User)` | Users interact in same channel | `(Mark)-[:CONNECTED_TO]->(Sarah)` |
| `(Topic)-[:RELATED_TO {strength}]->(Topic)` | Topics co-occur in 5+ messages | `(Coral Reefs)-[:RELATED_TO]->(Climate Change)` |
| `(Entity)-[:LINKED_TO]->(Entity)` | Entities mentioned together 3+ times | `(Python)-[:LINKED_TO]->(Machine Learning)` |

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Graph Enrichment Agent                        │
│            (Runs as background task in insight-worker)           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Trigger: After conversation ends (5 min inactivity)             │
│           OR scheduled nightly batch                              │
│                                                                   │
│  1. Query recent messages (last 24h or since last run)           │
│  2. Extract entity co-occurrences (Python, no LLM)               │
│  3. Detect topic patterns (keyword + semantic clustering)        │
│  4. Identify user-user interactions (same channel + replies)     │
│  5. Create/update edges with MERGE (idempotent)                  │
│  6. Log enrichment stats to InfluxDB                             │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
# src_v2/knowledge/enrichment.py

class GraphEnrichmentAgent:
    """
    Proactively enriches Neo4j with discovered relationships.
    Runs in background worker, no LLM calls needed.
    """
    
    async def enrich_from_conversation(
        self,
        channel_id: str,
        messages: List[ChatMessage],
        participants: List[str]
    ) -> EnrichmentResult:
        """
        Analyze a conversation and add discovered edges.
        """
        # 1. Extract entities from messages (existing fact_extractor)
        entities = await self._extract_entities(messages)
        
        # 2. Find co-occurrences (pure Python)
        cooccurrences = self._find_cooccurrences(entities, window_size=3)
        
        # 3. Detect topics (semantic clustering of entities)
        topics = self._cluster_into_topics(entities)
        
        # 4. Find user interactions (reply chains, same-message mentions)
        interactions = self._find_user_interactions(messages, participants)
        
        # 5. Create edges (MERGE for idempotency)
        edges_created = await self._create_edges(cooccurrences, topics, interactions)
        
        return EnrichmentResult(edges_created=edges_created)
    
    def _find_cooccurrences(
        self, 
        entities: List[Entity], 
        window_size: int = 3
    ) -> List[Tuple[Entity, Entity, int]]:
        """
        Find entities that appear within N messages of each other.

**Runtime Integration:** `enqueue_post_conversation_tasks` now enqueues `run_graph_enrichment`
automatically after session summaries, so real-time enrichment happens without additional
hooks in bot handlers.
        Returns (entity_a, entity_b, count).
        """
        # Sliding window over message sequence
        # Pure Python, no LLM
        pass
    
    async def _create_edges(self, ...):
        """
        MERGE edges to Neo4j (idempotent).
        """
        # Example: User-Topic edge
        query = """
        MATCH (u:User {id: $user_id})
        MERGE (t:Topic {name: $topic_name})
        MERGE (u)-[r:DISCUSSED]->(t)
        ON CREATE SET r.count = 1, r.first_date = datetime()
        ON MATCH SET r.count = r.count + 1, r.last_date = datetime()
        """
```

### Privacy Considerations

- Only creates edges for users with `trust_score > 0` (not Stranger)
- User-to-user edges only within same server
- All edges respect existing privacy manager rules

### Implementation Details (Complete)

The Graph Enrichment Agent was implemented on December 4, 2025. Here's what was built:

#### Files Created/Modified

| File | Purpose |
|------|---------|
| `src_v2/knowledge/enrichment.py` | Core `GraphEnrichmentAgent` class (~600 LOC) |
| `src_v2/workers/tasks/enrichment_tasks.py` | arq task wrappers for background jobs |
| `src_v2/workers/worker.py` | Task registration + nightly cron (3 AM UTC) |
| `src_v2/config/settings.py` | Feature flags and configuration |
| `tests_v2/test_graph_enrichment.py` | Unit tests (all passing) |

#### Configuration Options

```python
# .env or settings.py
ENABLE_GRAPH_ENRICHMENT=true           # Master switch (default: true)
ENRICHMENT_MIN_COOCCURRENCE=2          # Min co-occurrences to create edge
ENRICHMENT_BATCH_HOURS=24              # Hours of history for batch processing
```

#### Edge Types Created

| Edge Type | Count (Production) | Description |
|-----------|-------------------|-------------|
| `DISCUSSED` | ~5,000 | User → Topic (what users talk about) |
| `CONNECTED_TO` | ~70 | User ↔ User (interaction in same channels) |
| `RELATED_TO` | ~30,000 | Topic ↔ Topic (co-occurring topics) |
| `LINKED_TO` | ~320,000 | Entity ↔ Entity (frequently mentioned together) |

#### How It Works

1. **Topic Extraction**: Heuristic-based keyword extraction (no LLM required)
   - Filters common stopwords and short words
   - Extracts nouns, verbs, and named entities from messages
   
2. **Co-occurrence Detection**: Sliding window analysis
   - Topics appearing in same message → related
   - Entities mentioned together → linked
   
3. **User Interaction Mapping**: Channel-based analysis
   - Users in same channel → potential connection
   - Reply chains → stronger connection
   
4. **Idempotent Edge Creation**: Neo4j MERGE queries
   - Creates edge if not exists
   - Updates weight/count if exists
   - Timestamp tracking for temporal analysis

#### Triggering Enrichment

```python
# Real-time (after conversation)
from src_v2.workers.tasks.enrichment_tasks import run_graph_enrichment
await run_graph_enrichment(
    ctx,
    channel_id=channel_id,
    server_id=server_id,
    messages=messages,
    bot_name="elena"
)

# Batch (nightly cron - automatic)
# Runs at 3 AM UTC, processes last 24 hours

# Manual batch trigger
from src_v2.workers.tasks.enrichment_tasks import run_batch_enrichment
result = await run_batch_enrichment(ctx, hours=24)
```

#### Verified Results

Test run on elena bot (December 4, 2025):
```
Batch enrichment complete: 40 channels, 407,658 total edges
- User-Topic edges: 6,030
- User-User edges: 80  
- Topic-Topic edges: 32,707
- Entity-Entity edges: 368,841
```

### Files

- `src_v2/knowledge/enrichment.py` — GraphEnrichmentAgent class
- `src_v2/workers/tasks/enrichment_tasks.py` — Background task wrappers
- `src_v2/workers/worker.py` — Task registration and cron schedule
- `src_v2/config/settings.py` — `ENABLE_GRAPH_ENRICHMENT`, `ENRICHMENT_MIN_COOCCURRENCE`
- `tests_v2/test_graph_enrichment.py` — Unit tests

---

## Phase E26: Temporal Graph

**Priority:** 🟡 Medium | **Time:** 1-2 days | **Complexity:** Low
**Status:** 📋 Proposed
**Dependencies:** E19 ✅

### Problem

The Graph Walker treats all edges equally. But relationships evolve:
- A friendship that was strong 6 months ago may have faded
- A topic discussed daily is more salient than one mentioned once
- Trust changes over time should affect graph traversal

### Solution

Extend `_score_node()` heuristics to weight by **relationship evolution**, not just static properties. No new schema—use existing `updated_at`, `created_at`, and `trust_delta` fields.

### Temporal Scoring Heuristics

```python
def _score_temporal(self, node: dict, edge: dict, depth: int) -> float:
    """
    Temporal scoring heuristics for graph walking.
    All data from existing edge properties—no new schema.
    """
    score = 1.0
    
    # 1. Recency decay (existing)
    if "updated_at" in edge:
        days_ago = (datetime.now() - edge["updated_at"]).days
        score *= max(0.1, 1.0 - (days_ago / 60))  # Decay over 60 days
    
    # 2. Velocity boost (NEW: rate of change matters)
    if "count" in edge and "created_at" in edge:
        days_active = max(1, (datetime.now() - edge["created_at"]).days)
        velocity = edge["count"] / days_active
        score *= min(2.0, 1.0 + velocity)  # Active relationships score higher
    
    # 3. Trend detection (NEW: is relationship growing or fading?)
    if "count_30d" in edge and "count_60d" in edge:
        # Compare last 30 days to 30-60 days ago
        recent = edge.get("count_30d", 0)
        older = edge.get("count_60d", 0) - recent
        if older > 0:
            trend = recent / max(1, older)
            score *= min(1.5, trend)  # Growing relationships score higher
    
    # 4. Trust trajectory (NEW: was trust rising or falling?)
    if "trust_history" in node:
        # Simple: compare current trust to 30-day average
        current = node.get("trust_score", 0)
        avg_30d = sum(node["trust_history"][-30:]) / 30
        if avg_30d > 0:
            trajectory = current / avg_30d
            score *= min(1.3, max(0.7, trajectory))
    
    return score
```

### InfluxDB Integration

Trust evolution is already logged to InfluxDB. We can query it for temporal patterns:

```python
async def get_trust_trajectory(self, user_id: str, days: int = 30) -> List[float]:
    """
    Query InfluxDB for trust score history.
    """
    query = f'''
    from(bucket: "{settings.INFLUXDB_BUCKET}")
      |> range(start: -{days}d)
      |> filter(fn: (r) => r["_measurement"] == "trust_update")
      |> filter(fn: (r) => r["user_id"] == "{user_id}")
      |> filter(fn: (r) => r["_field"] == "score")
    '''
    # Returns list of scores over time
```

### Emergence Alignment

This approach follows emergence philosophy:
- ❌ NOT: Adding `relationship_phase: "declining"` enum
- ✅ YES: Relationships that haven't been updated naturally score lower
- ❌ NOT: Storing explicit "trend" field
- ✅ YES: Computing trend from existing count data

**The temporal dimension emerges from data patterns, not declared labels.**

### Files

- `src_v2/knowledge/walker.py` — Extend `_score_node()` with temporal heuristics
- `src_v2/knowledge/manager.py` — Add `get_trust_trajectory()` helper

---

## Phase E27: Multi-Character Walks

**Priority:** 🟡 Medium | **Time:** 2-3 days | **Complexity:** Medium
**Status:** ✅ Complete (December 5, 2025)
**Dependencies:** E19 ✅, E6 (Cross-Bot) ✅

### Problem

Each bot walks its own graph in isolation. But bots share a universe—they could discover narrative threads that span multiple characters:
- Elena dreams about the ocean; Aetheris writes about consciousness as depth
- Both talked to Mark about similar themes
- Neither knows about the other's connection

### Solution

Extend `GraphWalkerAgent` to walk across character boundaries, discovering shared narrative space.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   Multi-Character Walk                           │
│          (Discovers shared narrative across bots)                │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Trigger: Dream generation, Cross-bot conversation               │
│                                                                   │
│  1. Start from current character's graph                         │
│  2. Expand to shared entities (Topics, Users)                    │
│  3. Cross into other character's subgraph via shared nodes       │
│  4. Apply trust-gating (both characters must trust the user)     │
│  5. Find thematic clusters that span characters                  │
│  6. Single LLM call to synthesize cross-character narrative      │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Trust-Gating Rules

- **User Privacy**: Cross-character walk only includes User nodes where BOTH characters have `trust_score > 20`
- **Artifact Privacy**: Uses existing `content_review.py` sensitivity detection
- **Server Scope**: Cross-character data only flows within same Discord server

```python
async def multi_character_walk(
    self,
    primary_character: str,
    secondary_characters: List[str],
    seed_ids: List[str]
) -> MultiWalkResult:
    """
    Walk across multiple character subgraphs.
    """
    # 1. Get active bots from Redis registry
    active_bots = await self.cross_bot_manager.get_registered_bots()
    
    # 2. Filter to requested characters
    target_bots = [b for b in active_bots if b.name in secondary_characters]
    
    # 3. Walk primary graph
    primary_result = await self.walker.bfs_expand(seed_ids)
    
    # 4. Find shared nodes (Users, Topics, Entities)
    shared_nodes = await self._find_shared_nodes(
        primary_result.nodes,
        target_bots
    )
    
    # 5. Walk secondary graphs from shared nodes (trust-gated)
    secondary_results = []
    for bot in target_bots:
        gated_seeds = await self._trust_gate(shared_nodes, bot.name)
        result = await self.walker.bfs_expand(gated_seeds, character=bot.name)
        secondary_results.append(result)
    
    # 6. Merge and find cross-character clusters
    merged = self._merge_walks(primary_result, secondary_results)
    
    # 7. Single LLM call: interpret shared narrative
    interpretation = await self._interpret_shared_narrative(merged)
    
    return MultiWalkResult(...)
```

### Use Cases

| Use Case | Trigger | Output |
|----------|---------|--------|
| **Cross-Character Dreams** | Elena's dream generation | "In my dream, I saw what Aetheris wrote about depth. We're both circling the same mystery." |
| **Conversation Handoff** | Bot mentions another bot | "Aetheris and I both talked to Mark about consciousness. Maybe we should compare notes." |
| **Shared Artifact Discovery** | Daily reflection | "Gabriel's story about the sea captain reminded me of my own ocean dreams." |

### Files

- `src_v2/knowledge/walker.py` — Add `multi_character_walk()` method
- `src_v2/cross_bot/manager.py` — Add helper to query other bot's graph
- `src_v2/memory/dreams.py` — Optional integration for cross-character dreams

---

## Phase E28: User-Facing Graph

**Priority:** ⚪ Low | **Time:** 2-3 days | **Complexity:** Medium
**Status:** 📋 Proposed
**Dependencies:** E19 ✅, API Routes ✅

### Problem

Users have no visibility into what the bot knows about them. This creates:
- Surprise when bot recalls obscure details
- No way to correct mistakes
- Missed opportunity for engagement ("Look at your knowledge graph!")

### Solution

Add `/api/user-graph` endpoint that returns the user's discoverable subgraph for visualization.

### API Design

```python
# src_v2/api/routes.py

class UserGraphRequest(BaseModel):
    user_id: str
    depth: int = 2  # Max hops from user node
    include_other_users: bool = False  # Privacy: hide other users by default

class UserGraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    clusters: List[ThematicCluster]
    stats: GraphStats

@router.post("/api/user-graph")
async def get_user_graph(request: UserGraphRequest) -> UserGraphResponse:
    """
    Returns the user's knowledge graph for visualization.
    Respects privacy settings—no data from other users unless opted in.
    """
    # 1. Verify user exists
    # 2. Run graph walk from user node
    # 3. Filter out sensitive nodes (other users, private facts)
    # 4. Format for visualization (D3.js compatible)
    pass
```

### Response Format (D3.js Compatible)

```json
{
  "nodes": [
    {"id": "user:123", "label": "You", "type": "User", "size": 20},
    {"id": "topic:marine-biology", "label": "Marine Biology", "type": "Topic", "size": 15},
    {"id": "entity:python", "label": "Python", "type": "Entity", "size": 10}
  ],
  "edges": [
    {"source": "user:123", "target": "topic:marine-biology", "type": "DISCUSSED", "weight": 7},
    {"source": "user:123", "target": "entity:python", "type": "KNOWS", "weight": 3}
  ],
  "clusters": [
    {"name": "Technical Interests", "nodes": ["entity:python", "topic:ai"]},
    {"name": "Hobbies", "nodes": ["topic:marine-biology", "entity:scuba"]}
  ],
  "stats": {
    "total_nodes": 24,
    "total_edges": 31,
    "oldest_connection": "2025-10-15",
    "most_discussed": "Marine Biology"
  }
}
```

### Privacy Rules

| Data Type | Visibility | Reason |
|-----------|------------|--------|
| User's own nodes | ✅ Visible | It's their data |
| Topics/Entities | ✅ Visible | Non-personal |
| Facts about user | ✅ Visible | Their data |
| Other users | ❌ Hidden by default | Privacy |
| Bot artifacts | ✅ Visible | Public creative works |
| Trust scores | ❌ Hidden | Internal metric |

### Visualization Options

1. **Discord Bot Command**: `/mygraph` returns a link to web visualizer
2. **Web Dashboard**: Standalone page with D3.js force graph
3. **Static Image**: Generate PNG via `pyvis` for Discord embed

### Files

- `src_v2/api/routes.py` — Add `/api/user-graph` endpoint
- `src_v2/api/models.py` — Add request/response models
- `src_v2/knowledge/walker.py` — Add `walk_for_visualization()` method
- (Optional) `web/graph-viewer/` — Simple D3.js visualization

---

## Phase E29: Graph-Based Recommendations

**Priority:** ⚪ Low | **Time:** 1-2 days | **Complexity:** Low-Medium
**Status:** 📋 Proposed
**Dependencies:** E25 (Enrichment) ✅, E19 ✅

### Problem

Bots don't leverage the social graph for recommendations. With enough users and topics, the graph can surface interesting connections:
- "Mark also discusses coral reefs—you might enjoy comparing notes"
- "This topic is popular in the server right now"
- "Based on your interests, you might like..."

### Solution

Extend `bfs_expand()` to find users with similar topic clusters, using graph structure rather than explicit similarity scores.

### Algorithm

```python
async def find_similar_users(
    self,
    user_id: str,
    server_id: str,
    limit: int = 5
) -> List[SimilarUser]:
    """
    Find users with overlapping topic interests.
    Uses graph structure—no explicit similarity computation.
    """
    # 1. Get user's topics
    query = """
    MATCH (u:User {id: $user_id})-[:DISCUSSED]->(t:Topic)
    RETURN t.name as topic, count(*) as weight
    """
    user_topics = await self.km.execute_query(query, {"user_id": user_id})
    
    # 2. Find other users who discuss same topics (same server only)
    query = """
    MATCH (u:User {id: $user_id})-[:DISCUSSED]->(t:Topic)<-[:DISCUSSED]-(other:User)
    WHERE other.id <> $user_id
    AND (u)-[:CONNECTED_TO {server_id: $server_id}]-(other)
    WITH other, count(DISTINCT t) as shared_topics, collect(t.name) as topics
    ORDER BY shared_topics DESC
    LIMIT $limit
    RETURN other.id as user_id, shared_topics, topics
    """
    similar = await self.km.execute_query(query, {
        "user_id": user_id,
        "server_id": server_id,
        "limit": limit
    })
    
    # 3. Apply serendipity: occasionally include a random user
    if random.random() < self.serendipity:
        random_user = await self._get_random_active_user(server_id, exclude=[user_id])
        if random_user:
            similar.append(SimilarUser(
                user_id=random_user,
                shared_topics=0,
                reason="serendipity"
            ))
    
    return similar
```

### Use Cases

| Context | Recommendation | Example |
|---------|----------------|---------|
| **Proactive Message** | Mention shared interest | "By the way, Sarah also loves marine biology. You two might enjoy chatting!" |
| **Topic Introduction** | Reference popular discussion | "A few people in the server have been talking about this lately..." |
| **Dream Weaving** | Cross-user narrative | "In my dream, I saw you and Sarah diving together, discovering something in the reef..." |

### Privacy & Consent

- Only recommends users who have `trust_score > 30` (Friend level)
- Only within same server
- User can opt-out via `/privacy no-recommendations`
- Never reveals private facts about other users

### Emergence Alignment

- ❌ NOT: Computing cosine similarity between user embedding vectors
- ✅ YES: Counting shared edges in the graph (structural similarity)
- ❌ NOT: Storing "similar_users" field on User nodes
- ✅ YES: Discovering similarity at query time via graph traversal

**Similarity emerges from graph structure, not precomputed scores.**

### Files

- `src_v2/knowledge/recommendations.py` — Recommendation logic
- `src_v2/knowledge/walker.py` — Add `find_similar_users()` method
- `src_v2/discord/scheduler.py` — Optional: proactive recommendation messages

---

## Configuration

```python
# src_v2/config/settings.py

# --- Graph Walker Extensions (Phases E25-E29) ---

# E25: Graph Enrichment
ENABLE_GRAPH_ENRICHMENT: bool = False
ENRICHMENT_MIN_COOCCURRENCE: int = 3  # Min times entities must co-occur
ENRICHMENT_RUN_INTERVAL_HOURS: int = 6  # How often to run batch enrichment

# E26: Temporal Graph (no new settings—uses existing updated_at)

# E27: Multi-Character Walks
ENABLE_MULTI_CHARACTER_WALKS: bool = False
MULTI_CHARACTER_TRUST_THRESHOLD: int = 20  # Min trust for cross-bot data

# E28: User-Facing Graph
ENABLE_USER_GRAPH_API: bool = False
USER_GRAPH_MAX_DEPTH: int = 3
USER_GRAPH_MAX_NODES: int = 100

# E29: Graph Recommendations
ENABLE_GRAPH_RECOMMENDATIONS: bool = False
RECOMMENDATION_MIN_SHARED_TOPICS: int = 2
RECOMMENDATION_SERENDIPITY: float = 0.1
```

---

## Success Metrics

| Phase | Metric | Baseline | Target |
|-------|--------|----------|--------|
| E25 | Edges created per day | 0 | 50-100 |
| E25 | Dream connections from enriched edges | 0 | 30% of dreams |
| E26 | Relationship trend detection accuracy | — | 80% match user perception |
| E27 | Cross-bot narrative references | 0 | 1-2 per week per bot |
| E28 | User graph API usage | 0 | 10+ requests/day |
| E29 | Successful introductions | 0 | 5+ per week |

---

## Implementation Order

Recommended sequence based on dependencies and value:

```
E25 (Enrichment) ──► E26 (Temporal) ──► E29 (Recommendations)
                              │
                              └──► E27 (Multi-Character)
                              
E28 (User Graph) can be done independently
```

**Phase 1 (Immediate Value):** E25 — Graph Enrichment Agent
- Adds the most data to the graph
- Powers all other extensions
- High value for dreams/diaries

**Phase 2 (Quality):** E26 — Temporal Graph
- Improves scoring heuristics
- No new infrastructure
- Low effort, high impact

**Phase 3 (Social):** E27 + E29 — Multi-Character & Recommendations
- Requires E25 to have rich graph data
- Social features build on each other

**Phase 4 (Engagement):** E28 — User-Facing Graph
- Nice-to-have for user engagement
- Requires frontend work
- Can be deferred

---

## Related Documents

- [GRAPH_WALKER_AGENT.md](./GRAPH_WALKER_AGENT.md) — Foundation (E19)
- [ADR-003-EMERGENCE_PHILOSOPHY.md](../adr/ADR-003-EMERGENCE_PHILOSOPHY.md) — Design philosophy
- [ref/REF-002-GRAPH_SYSTEMS.md](../ref/REF-002-GRAPH_SYSTEMS.md) — Unified graph architecture
- [CROSS_BOT_MEMORY.md](./CROSS_BOT_MEMORY.md) — Related cross-bot enhancement

---

**Proposed by:** AI Development Session (December 3, 2025)
**Review Status:** 📋 Proposed
