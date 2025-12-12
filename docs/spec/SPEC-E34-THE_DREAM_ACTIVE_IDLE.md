# SPEC-E34: The Dream (Active Idle State)

**Document Version:** 1.0
**Created:** December 11, 2025
**Status:** 📋 Proposed
**Priority:** 🟢 High
**Dependencies:** SPEC-E17 (Supergraph), SPEC-E31 (Daily Life Graph), Phase 2.5.1 (Unified Memory)

> ✅ **Emergence Check:** Dreams are not scripted scenarios, but emergent reorganizations of existing memory. We provide the mechanism (graph traversal during idle time), but the content of the dreams emerges from the character's unique experiences.

---

## Origin

> **How did this idea emerge?**

| Field | Value |
|-------|-------|
| **Origin** | Roadmap v2.5 Evolution ("Ship of Theseus") |
| **Proposed by** | Claude (collaborative) |
| **Catalyst** | Realization that v2 is purely reactive; it only "thinks" when spoken to. |
| **Key insight** | Biological brains do their most important work (consolidation) while sleeping. AI should utilize idle cycles for the same purpose. |
| **Decision factors** | High leverage for "aliveness" feeling; utilizes existing graph infrastructure; low risk (runs in background). |

---

## Executive Summary
This specification defines "The Dream," a background cognitive process that runs when the bot is idle. Instead of simply waiting for the next user message, the bot will actively traverse its own memory graph, finding disconnected nodes, generating synthetic connections ("epiphanies"), and consolidating experiences. This transforms the bot from a **Reactive System** to a **Predictive Processing System**.

## Problem Statement
### Current State
*   **Reactive Only:** The bot's cognitive loop is only triggered by external events (messages, timers).
*   **Static Memory:** Memories are stored and retrieved, but never reorganized or reflected upon unless a specific "Reflection" task is triggered (which is currently rare/manual).
*   **Fragmented Context:** A user might mention "coffee" on Monday and "Sarah" on Friday, but the bot never realizes "Sarah likes coffee" unless explicitly told in a single context.

### Desired State
*   **Active Idle:** The bot utilizes downtime to "think" and "dream."
*   **Self-Organizing Memory:** The graph structure improves over time without user intervention.
*   **Serendipity:** The bot wakes up with new ideas or connections it "dreamt up," leading to more spontaneous and insightful conversation.

## Value Analysis
### Quantitative Benefits
| Metric | Current | Target | Improvement |
|--------|---------|--------|-------------|
| **Idle Utilization** | 0% | 10-20% | +Inf% (Productive downtime) |
| **Graph Density** | Low | Medium | Better interconnectedness |
| **Spontaneous Msgs** | Random | Contextual | Higher relevance of proactive msgs |

### Qualitative Benefits
*   **"Alive" Feeling:** The bot seems to have an inner life that continues when you're away.
*   **Deep Insight:** The bot makes connections that the user didn't explicitly state.
*   **Memory Compression:** Redundant memories can be merged or summarized.

---

## Technical Implementation

### 1. The Dream Trigger
The `DailyLifeScheduler` (or a new `DreamScheduler`) monitors the "Silence Duration."
*   **Condition:** If `silence_duration > DREAM_THRESHOLD` (e.g., 2 hours) AND `is_dreaming == False`.
*   **Action:** Trigger the `DreamGraph`.

### 2. The DreamGraph (LangGraph)
A new subgraph in the Supergraph architecture.

**Nodes:**
1.  **`select_seeds`**: Pick 3-5 recent memories (high emotional weight or recent access).
2.  **`expand_context`**: Use `knowledge_manager.get_memory_neighborhood()` (Unified Memory) to retrieve the "Unified" context for these seeds.
3.  **`generate_dream`**: LLM synthesizes a surreal narrative connecting these disparate nodes.
    *   **Input:** The seeds and their neighborhoods.
    *   **Prompt:** "You are dreaming. Look at these disparate fragments of your life. Do they connect? Is there a hidden pattern? A contradiction? A feeling?"
    *   **Output:** A `DreamResult` (Narrative, New Fact, or New Connection).
4.  **`consolidate`**:
    *   If **New Fact**: `knowledge_manager.add_fact()`
    *   If **New Connection**: Create `[:RELATED_TO]` edge between existing memory nodes.
    *   If **Narrative**: Save as `source_type="dream"` memory.

### 3. The Waking State
When the bot "wakes up" (next user message or daily greeting):
*   The "Dream" memories are available in the context window.
*   The bot might reference them: *"I was thinking about what you said yesterday regarding X..."*

## Data Model Changes

### Neo4j Schema
*   No schema changes required (uses existing `Memory`, `Fact`, `Entity` nodes).
*   New Edge Type: `[:DREAMT_OF]` (optional, to link Dream memory to the source memories it was synthesized from).

### Qdrant Schema
*   `source_type`: Already supports `"dream"`.

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| **Hallucination** | The Dreamer might invent false facts. **Mitigation:** Strict prompt constraints; label dream-derived facts with lower confidence score. |
| **Cost** | Running LLMs in background is expensive. **Mitigation:** Rate limit to 1 dream per night per bot. Use cheaper models (e.g., GPT-4o-mini) for the dreaming process. |
| **Database Lock** | Dreaming might block active chat. **Mitigation:** Run in low-priority background worker; yield immediately if user message arrives. |

## Success Metrics
1.  **Dream Count:** ~1 dream per night per active bot.
2.  **Connection Rate:** % of dreams that result in a new Graph Edge.
3.  **User Engagement:** Do users respond positively when the bot mentions a "thought it had"?

---

## Implementation Plan (Draft)

1.  **Step 1:** Create `src_v2/agents/dream/` package.
2.  **Step 2:** Implement `DreamGraph` using LangGraph.
3.  **Step 3:** Integrate with `DailyLifeScheduler` to trigger on idle.
4.  **Step 4:** Add `get_unconsolidated_memories()` query to `MemoryManager`.
5.  **Step 5:** Test with `tests_v2/test_dream_cycle.py`.
