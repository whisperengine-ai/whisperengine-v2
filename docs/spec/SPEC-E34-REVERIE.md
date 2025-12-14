# SPEC-E34: Reverie (Active Idle State)

**Document Version:** 1.1
**Created:** December 11, 2025
**Updated:** December 12, 2025
**Status:** 📋 Proposed
**Priority:** 🟢 High
**Dependencies:** SPEC-E17 (Supergraph), SPEC-E31 (Daily Life Graph), Phase 2.5.1 (Unified Memory)

> ✅ **Emergence Check:** Reveries are not scripted scenarios, but emergent reorganizations of existing memory. We provide the mechanism (graph traversal during idle time), but the content of the reveries emerges from the character's unique experiences.

---

## Origin

> **How did this idea emerge?**

| Field | Value |
|-------|-------|
| **Origin** | Roadmap v2.5 Evolution ("Ship of Theseus") |
| **Proposed by** | Claude (collaborative) |
| **Catalyst** | Realization that v2 is purely reactive; it only "thinks" when spoken to. |
| **Key insight** | Biological brains do their most important work (consolidation) while sleeping/daydreaming. AI should utilize idle cycles for the same purpose. |
| **Decision factors** | High leverage for "aliveness" feeling; utilizes existing graph infrastructure; low risk (runs in background). |
| **Renaming** | Renamed from "The Dream" to "Reverie" to distinguish from the "Dream Journal" feature. |

---

## Executive Summary
This specification defines "Reverie," a background cognitive process that runs when the bot is idle. Instead of simply waiting for the next user message, the bot will actively traverse its own memory graph, finding disconnected nodes, generating synthetic connections ("epiphanies"), and consolidating experiences. This transforms the bot from a **Reactive System** to a **Predictive Processing System**.

## Problem Statement
### Current State
*   **Reactive Only:** The bot's cognitive loop is only triggered by external events (messages, timers).
*   **Static Memory:** Memories are stored and retrieved, but never reorganized or reflected upon unless a specific "Reflection" task is triggered (which is currently rare/manual).
*   **Fragmented Context:** A user might mention "coffee" on Monday and "Sarah" on Friday, but the bot never realizes "Sarah likes coffee" unless explicitly told in a single context.

### Desired State
*   **Active Idle:** The bot utilizes downtime to "think" and "reverie."
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

### 1. The Reverie Trigger
The `DailyLifeScheduler` monitors the "Silence Duration."
*   **Condition:** If `silence_duration > REVERIE_THRESHOLD` (e.g., 2 hours) AND `is_processing == False`.
*   **Action:** Trigger the `ReverieGraph`.

### 2. The ReverieGraph (LangGraph)
A new subgraph in the Supergraph architecture.

**Nodes:**
1.  **`select_seeds`**: Pick 3-5 recent memories (high emotional weight or recent access).
2.  **`expand_context`**: Use `knowledge_manager.get_memory_neighborhood()` (Unified Memory) to retrieve the "Unified" context for these seeds.
3.  **`generate_reverie`**: LLM synthesizes a surreal narrative connecting these disparate nodes.
    *   **Input:** The seeds and their neighborhoods.
    *   **Prompt:** "You are in a reverie. Look at these disparate fragments of your life. Do they connect? Is there a hidden pattern? A contradiction? A feeling?"
    *   **Output:** A `DreamResult` (Narrative, New Fact, or New Connection).
4.  **`consolidate`**:
    *   If **New Fact**: `knowledge_manager.add_fact()`
    *   If **New Connection**: Create `[:REVERIE_LINK]` edge between existing memory nodes.
    *   If **Narrative**: Save as `source_type="dream"` memory (internal).

### 3. The Waking State
When the bot "wakes up" (next user message or daily greeting):
*   The "Reverie" memories are available in the context window.
*   The bot might reference them: *"I was thinking about what you said yesterday regarding X..."*

## Data Model Changes

### Neo4j Schema
*   No schema changes required (uses existing `Memory`, `Fact`, `Entity` nodes).
*   New Edge Type: `[:REVERIE_LINK]` (links Memory nodes that were associated during reverie).

### Qdrant Schema
*   `source_type`: A new type, `"reverie"`, will be used to distinguish these internal cognitive artifacts from the narrative "dreams" created for the user-facing Dream Journal. This prevents accidental mixing of abstract connections and creative stories.

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| **Hallucination** | The Dreamer might invent false facts. **Mitigation:** Strict prompt constraints; label reverie-derived facts with lower confidence score. |
| **Cost** | Running LLMs in background is expensive. **Mitigation:** Rate limit to 1 reverie per night per bot. Use cheaper models (e.g., GPT-4o-mini) for the process. |
| **Database Lock** | Reverie might block active chat. **Mitigation:** Run in low-priority background worker; yield immediately if user message arrives. |

## Success Metrics
1.  **Reverie Count:** ~1 reverie per night per active bot.
2.  **Connection Rate:** % of reveries that result in a new Graph Edge.
3.  **User Engagement:** Do users respond positively when the bot mentions a "thought it had"?

---

## Implementation Plan (Draft)

1.  **Step 1:** Create `src_v2/agents/dream/` package (reused for Reverie).
2.  **Step 2:** Implement `ReverieGraph` using LangGraph.
3.  **Step 3:** Integrate with `DailyLifeScheduler` to trigger on idle.
4.  **Step 4:** Add `get_unconsolidated_memories()` query to `MemoryManager`.
5.  **Step 5:** Test with `tests_v2/test_dream_cycle.py`.

---

## Future Extensions

### Self-Reflection & Meta-Learning (Proposed, See ADR-018)

**Concept:** Extend Reverie to include self-analysis during idle time.

**How it would work:**
- Add `reflect_on_self` node to ReverieGraph after `generate_reverie`
- Analyzes bot's own reasoning traces (from Phase B5)
- Extracts patterns: "What approaches do I tend to use?"
- Stores as `self_pattern` memory type (reuses existing schema)
- Bot can reference own patterns: "I notice I tend to use Socratic questioning..."

**Example emergent behaviors:**
- Marcus learns: "I default to Socratic questioning with defensive users" (confidence: 0.85)
- Dream learns: "I over-apologize — users want more directness" (effectiveness: ineffective)
- Ryan learns: "Music metaphors work for creative topics, confuse in technical contexts" (mixed)

**Data model:** No schema changes
- Uses existing `memory_type` field with new value `self_pattern`
- Metadata: `{confidence: float, effectiveness: "effective"|"mixed"|"ineffective"}`
- Source type: `inference` (same as epiphanies)

**Cost:** ~$0.003 per reverie cycle (1 extra LLM call), ~$0.15/month per bot

**Integration points:**
- **Character Context:** Self-patterns injected into system prompt
- **Trace Learning (B5):** Pattern-aligned traces score higher
- **Adaptive Identity (2.6):** Self-knowledge informs self-editing

**Risks & mitigations:**
- **Self-delusion:** Bot invents patterns from noise → Require minimum 5 traces, store confidence scores
- **Overfitting:** Bot becomes rigid → Store effectiveness, mark "mixed" patterns as experimental
- **Personality lock-in:** Bot can't evolve → Allow pattern updates and decay

**Decision:** Deferred until after multi-party schema (ADR-014/017). Rationale: Follows "Observe First" principle — let's see bot-to-bot behavior before adding self-reflection. Also avoids delay on critical path work.

**See:** Full proposal in `/reverie-self-reflection-enhancement.md` (December 14, 2025)

**Status:** 📋 Future Option (not committed)
