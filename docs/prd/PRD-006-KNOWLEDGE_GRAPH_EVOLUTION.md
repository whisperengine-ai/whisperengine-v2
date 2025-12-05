# PRD-006: Knowledge Graph Evolution

**Status:** 🔄 In Progress
**Owner:** Mark Castillo
**Created:** December 4, 2025
**Updated:** December 4, 2025

## Origin

> **How did this need emerge?** As bots interacted more, their "flat" vector memory became insufficient for complex reasoning. They needed structured, interconnected knowledge to understand relationships, time, and shared context.

| Field | Value |
|-------|-------|
| **Origin** | Architecture Review / Emergence Research |
| **Proposed by** | Claude (AI Collaborator) |
| **Catalyst** | The need for "deep" memory where facts are connected, not just retrieved by similarity |

## Problem Statement
Vector memory is good for "fuzzy matching" but bad for structure.
- It doesn't know *when* something happened (Time).
- It doesn't know *how* A relates to B (Structure).
- It doesn't know that User A and User B are talking about the same thing (Shared Context).
- Users have no visibility into what the bot knows (Transparency).

## User Stories
1.  **As a user**, I want the bot to remember that I *used to* like coffee but *now* like tea (Temporal awareness).
2.  **As a user**, I want to see what the bot knows about me so I can correct it (Transparency).
3.  **As a user**, I want the bot to connect my interest in "diving" with another user's interest in "reefs" (Social connection).
4.  **As a developer**, I want the graph to "clean itself" and evolve over time without manual database edits (Enrichment).

## Functional Requirements

### 1. Graph Enrichment
- **Requirement:** Automatically clean, merge, and categorize graph nodes.
- **Mechanism:** `EnrichmentAgent` runs in background to consolidate duplicate nodes and infer new relationships.
- **Roadmap Item:** **E25**

### 2. Temporal Awareness
- **Requirement:** Edges must have time properties to distinguish past vs. present facts.
- **Mechanism:** `TemporalGraph` adds `valid_from`, `valid_until`, and `confidence` to edges.
- **Roadmap Item:** **E26**

### 3. Multi-Character Perspectives
- **Requirement:** Different bots should be able to traverse the same graph but see it through their own "lens" (trust scores, unique relationships).
- **Mechanism:** `MultiCharacterWalks` allow traversing the shared graph with character-specific weights.
- **Roadmap Item:** **E27**

### 4. User Transparency
- **Requirement:** Users must be able to view their own subgraph.
- **Mechanism:** `/my_graph` command and `/api/user-graph` endpoint.
- **Roadmap Item:** **E28**

### 5. Social Recommendations
- **Requirement:** Suggest connections between users based on graph topology.
- **Mechanism:** Graph traversal to find users with high structural similarity (shared topic nodes).
- **Roadmap Item:** **E29**

## Success Metrics
- **Fact Retrieval Accuracy:** % of questions about user facts answered correctly.
- **Graph Density:** Average number of edges per node (higher = richer context).
- **User Corrections:** Frequency of users correcting the bot (should decrease over time).

## Privacy & Safety
- **Isolation:** Users can only see their own graph data.
- **Filtering:** Recommendations must not leak private facts, only shared public interests.
- **Right to Forget:** `/memory_wipe` must cascade deletes through the graph.
