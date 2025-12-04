# ADR-004: Graph-First Memory Architecture (Neo4j + Qdrant Hybrid)

**Status:** ✅ Accepted  
**Date:** November 2025  
**Deciders:** Mark Castillo, AI Development Team

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Memory architecture decision |
| **Proposed by** | Mark (system architecture) |
| **Catalyst** | Pure vector or relational insufficient for all query patterns |

---

## Context

WhisperEngine needs to store and retrieve different types of information:

| Data Type | Example | Query Pattern |
|-----------|---------|---------------|
| **Semantic memories** | "User loves hiking in Colorado" | "Find memories similar to 'outdoor activities'" |
| **Relational facts** | "User → LIVES_IN → Seattle" | "What city does user live in?" |
| **Conversation history** | Timestamped message log | "Last 10 messages with user" |
| **Cross-entity relationships** | "User A and B both discussed Topic X" | "Who else discussed this topic?" |

**The problem:** No single database excels at all these patterns:
- **Pure vector (Qdrant only)**: Great for semantic search, poor for structured relationships
- **Pure relational (Postgres only)**: Great for structured data, poor for semantic similarity
- **Pure graph (Neo4j only)**: Great for relationships, no native vector search

---

## Decision

We adopt a **Graph-First Hybrid Architecture** using three specialized databases:

| Database | Purpose | Query Pattern |
|----------|---------|---------------|
| **Neo4j** | Knowledge graph (entities, relationships, facts) | Cypher traversal |
| **Qdrant** | Vector memory (semantic search, similarity) | Embedding similarity |
| **PostgreSQL** | Structured data (chat history, users, trust) | SQL queries |

### The "Graph-First" Philosophy

Neo4j is the **primary source of truth** for understanding relationships. Qdrant and Postgres support specific access patterns, but the graph captures the semantic structure of knowledge.

```
                    ┌─────────────────┐
                    │     Neo4j       │  ← Primary: Relationships
                    │  (Knowledge     │     "User LIKES Topic"
                    │   Graph)        │     "Topic RELATED_TO Topic"
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
     ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
     │   Qdrant    │  │  PostgreSQL │  │   Redis     │
     │  (Vectors)  │  │  (History)  │  │  (Cache)    │
     │             │  │             │  │             │
     │ "Similar    │  │ "Last 10    │  │ "Recent     │
     │  memories"  │  │  messages"  │  │  lookups"   │
     └─────────────┘  └─────────────┘  └─────────────┘
```

### Data Distribution

| Data | Primary Store | Why |
|------|---------------|-----|
| User facts ("likes hiking") | Neo4j | Relational structure, traversable |
| Entity relationships | Neo4j | Graph queries |
| Conversation content | Qdrant (vectors) + Postgres (raw) | Semantic search + history |
| User metadata | Postgres | Structured, indexed |
| Trust scores | Postgres | Relational, transactional |
| Session summaries | Qdrant | Semantic retrieval |
| Character artifacts | Neo4j + Qdrant | Relationships + content search |

---

## Consequences

### Positive

1. **Best Tool for Each Job**: Semantic search in Qdrant, relationships in Neo4j, structured data in Postgres.

2. **Rich Traversal**: "Find users who discussed topics similar to what this user likes" spans all three stores.

3. **Graph Walker Agent**: Neo4j enables BFS/DFS exploration of knowledge (see E19).

4. **Scalable**: Each store can scale independently.

5. **Research Value**: Graph structure captures emergent relationship patterns.

### Negative

1. **Operational Complexity**: Three databases to maintain, backup, monitor.

2. **Consistency Challenges**: Data must stay synchronized across stores.

3. **Query Complexity**: Some queries require multiple database calls + aggregation.

4. **Learning Curve**: Team must know Cypher + SQL + vector concepts.

### Neutral

1. **Cost**: More infrastructure, but each component is relatively lightweight.

2. **Docker Compose**: All three run in containers, manageable for solo developer.

---

## Alternatives Considered

| Alternative | Pros | Cons | Why Rejected |
|-------------|------|------|--------------|
| **Qdrant Only** | Simple, good semantic search | No relationship queries, poor structured data | Can't traverse "users who know entity X" |
| **PostgreSQL + pgvector** | Single database, pgvector for embeddings | Limited vector performance, no graph traversal | Scaling limits, no Cypher-like queries |
| **Neo4j Only** | Unified graph model | No native vector search, verbose for simple data | Would need external vector index anyway |
| **MongoDB** | Flexible schema | Poor at both graph and vector | Jack of all trades, master of none |
| **Pinecone** | Managed vector DB | Vendor lock-in, no graph, no SQL | Limited to one query pattern |

---

## Implementation

### Parallel Context Retrieval

```python
# src_v2/agents/engine.py

async def build_context(self, user_id: str, message: str) -> Context:
    """
    Retrieve context from all stores in parallel.
    """
    memories, facts, trust, history = await asyncio.gather(
        memory_manager.search_memories(user_id, message),  # Qdrant
        knowledge_manager.get_user_facts(user_id),         # Neo4j
        trust_manager.get_relationship(user_id),           # Postgres
        db_manager.get_recent_history(user_id, limit=10),  # Postgres
    )
    
    return Context(
        memories=memories,
        facts=facts,
        trust=trust,
        history=history,
    )
```

### Graph Walker Integration

```python
# src_v2/knowledge/walker.py

class GraphWalker:
    """
    BFS traversal of Neo4j knowledge graph.
    Discovers connections that flat queries miss.
    """
    
    async def bfs_expand(self, seed_ids: List[str], max_depth: int = 3):
        query = """
        MATCH (n)-[r]-(neighbor)
        WHERE n.id IN $frontier AND NOT neighbor.id IN $visited
        RETURN n.id as source, neighbor, type(r) as edge_type
        """
        # Pure Python traversal with Cypher queries
        # No LLM calls during exploration
```

---

## References

- Graph systems design: [`docs/architecture/GRAPH_SYSTEMS_DESIGN.md`](../architecture/GRAPH_SYSTEMS_DESIGN.md)
- Memory system: [`docs/architecture/MEMORY_SYSTEM_V2.md`](../architecture/MEMORY_SYSTEM_V2.md)
- Knowledge manager: [`src_v2/knowledge/manager.py`](../../src_v2/knowledge/manager.py)
- Graph Walker: [`docs/roadmaps/GRAPH_WALKER_AGENT.md`](../roadmaps/GRAPH_WALKER_AGENT.md)
