# SPEC-E35: The Synapse (Graph Unification)

**Document Version:** 1.0
**Created:** December 11, 2025
**Status:** ✅ Complete (Phase 1)
**Priority:** 🔴 Critical
**Dependencies:** Existing Qdrant & Neo4j setup

> ✅ **Emergence Check:** This feature does not dictate *what* the bot remembers, but *how* it associates memories. It enables emergent associations by allowing the bot to traverse from a semantic match (Vector) to a structural neighborhood (Graph).

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Roadmap v2.5 Evolution |
| **Proposed by** | Claude & Mark |
| **Catalyst** | The "Context Window Problem": Vector search returns disconnected snippets; Graph search requires knowing the exact keywords. We needed both. |
| **Goal** | Unify Vector Memory (Qdrant) and Knowledge Graph (Neo4j) into a single traversable structure. |
| **Key insight** | "Unified Memory": A single vector point can be the "address" of a complex graph structure. |
| **Status** | ✅ **COMPLETED** (Dec 11, 2025) |

---

## Executive Summary
"The Synapse" unifies the previously separate Vector Database (Qdrant) and Knowledge Graph (Neo4j). It implements a **Dual-Write** pattern where every memory saved to Qdrant is also created as a node in Neo4j. This enables **Vector-First Traversal**: searching for meaning (Vector) to find structure (Graph).

## Problem Statement
### Current State (v2.0)
*   **Siloed Memory:** `MemoryManager` talks to Qdrant. `KnowledgeManager` talks to Neo4j. They rarely interact.
*   **Flat Retrieval:** Searching for "coffee" returns 5 isolated strings. The bot doesn't know that "coffee" is connected to "Sarah" unless "Sarah" is explicitly in the string.

### Desired State (v2.5)
*   **Unified Memory:** Every memory is a node in the graph.
*   **Associative Retrieval:** Searching for "coffee" returns the *Memory Node*, which we then expand to find "Sarah" (who was present) and "Central Park" (where it happened).

## Technical Implementation

### 1. Dual-Write Architecture
Modified `MemoryManager.add_message()` and `_save_vector_memory()`:
1.  **Save to Qdrant:** Generate embedding, save payload. Get `vector_id`.
2.  **Save to Neo4j:** Call `knowledge_manager.add_memory_node()`.
    *   Create `(:Memory {id: vector_id})`.
    *   Link to User: `(:User)-[:HAS_MEMORY]->(:Memory)`.

### 2. Vector-First Traversal
New method `knowledge_manager.get_memory_neighborhood(vector_ids)`:
1.  **Input:** List of `vector_id`s from Qdrant search.
2.  **Query:**
    ```cypher
    MATCH (m:Memory)<-[:HAS_MEMORY]-(u:User)
    WHERE m.id IN $vector_ids
    OPTIONAL MATCH (u)-[r:FACT]->(e:Entity)
    RETURN m, u, e
    ```
3.  **Output:** A structured "Neighborhood" containing the memory + related facts/entities.

### 3. Scope (Phase 1)
*   **Included:** Conversation Memories (`role='user'`, `role='assistant'`).
*   **Excluded (for now):** Dreams, Diaries, Summaries (these remain Vector-only until we define a `(:Bot)` node schema).

## Data Model

### Neo4j Node: `Memory`
*   `id`: UUID (matches Qdrant ID) - **Unique Constraint**
*   `content`: String (truncated if necessary)
*   `timestamp`: ISO8601
*   `source_type`: String ("human_direct", "inference")
*   `bot_name`: String

### Neo4j Edge: `HAS_MEMORY`
*   `(:User)-[:HAS_MEMORY]->(:Memory)`

## Success Metrics
*   **Consistency:** 100% of new conversation memories exist in both DBs.
*   **Retrieval:** `get_memory_neighborhood` returns non-empty results for users with facts.
*   **Latency:** Overhead of dual-write < 50ms.

## Verification
Run `tests_v2/test_synapse_dual_write.py`.
