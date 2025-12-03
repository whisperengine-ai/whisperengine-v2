# Supergraph Optimization Report
**Date:** December 3, 2025
**Status:** Implemented

## Overview
We reviewed the "Supergraph" architecture (`src_v2/agents/master_graph.py`) and identified a significant bottleneck in the sequential fetching of context data during the prompt building phase.

## Optimization: Parallel Context Fetching

### Problem
Previously, `MasterGraphAgent` fetched vector memories in parallel, but then called `ContextBuilder.build_system_context`, which sequentially awaited multiple database and graph queries:
1.  Trust/Relationship (Postgres)
2.  User Mood/Feedback (InfluxDB)
3.  Active Goals (Postgres)
4.  Diary Entries (Qdrant/Postgres)
5.  Dream Sequences (Qdrant/Postgres)
6.  Knowledge Graph Common Ground (Neo4j)
7.  Known Bots (Internal API)

This sequential execution added unnecessary latency to every request.

### Solution
We refactored the architecture to fetch **all** context items in parallel within the `context_node` of the Supergraph.

1.  **Refactored `ContextBuilder`**: Exposed individual `get_*_context` methods (e.g., `get_evolution_context`, `get_knowledge_context`) to allow granular fetching.
2.  **Updated `MasterGraphAgent`**:
    -   Modified `context_node` to use `asyncio.gather` for all context items (Memories, Evolution, Goals, Diary, Dream, Knowledge, Known Bots).
    -   Updated `SuperGraphState` to carry the full context dictionary.
3.  **Updated `ContextBuilder.build_system_context`**: Added support for a `prefetched_context` argument to use the parallel-fetched data instead of re-fetching it.

### Benefits
-   **Reduced Latency**: The time to build the system prompt is now determined by the *slowest* single query rather than the *sum* of all queries.
-   **Better Observability**: The `context_node` now explicitly shows all data sources being accessed.
-   **Modularity**: `ContextBuilder` is now more flexible, supporting both "fetch-all" (legacy) and "inject-all" (optimized) patterns.

## Future Recommendations

1.  **Streaming**: The `run_stream` method in `MasterGraphAgent` currently yields the final response as a single chunk. Implementing true token-level streaming from the subgraphs would improve perceived latency for the user.
2.  **Caching**: Static context like "Known Bots" or "Character Diary" (which changes daily) could be cached in Redis to further reduce DB load.
3.  **Conditional Fetching**: The `classifier_node` could run in parallel with `context_node`. If the classifier determines a "Simple" query, we might skip expensive fetches like "Dream Generation" or "Deep Knowledge Search". Currently, we fetch everything to be safe.
