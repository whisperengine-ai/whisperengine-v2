# WhisperEngine v2.5 Evolution Roadmap: The "Ship of Theseus"

**Status:** Draft Proposal  
**Date:** December 11, 2025  
**Target:** Q1-Q2 2026  

---

## 1. The Philosophy: From Reactive to Alive

WhisperEngine v2 is a sophisticated **Reactive System**. It waits for input (message or timer), retrieves context, processes it, and responds. It is a "Dual-Process" architecture (Fast/Slow thinking).

WhisperEngine v2.5 represents a shift to a **Predictive Processing System**. The agent should be "always on," constantly predicting the state of its world, optimizing its memory, and generating internal experiences (dreams) even when no user is present.

**The Key Insight:** We do not need a rewrite. The "Remote Brain" architecture (Phase E31) successfully decoupled cognition from the event loop. We can now evolve v2 into v2.5 component by component—a "Ship of Theseus" upgrade within the same codebase.

### Guiding Principle: Observe First, Constrain Later

Per ADR-003, we build infrastructure for emergence and observe what happens before adding constraints. The v2.5 phases follow this principle—each phase adds capability, not restriction.

---

## 2. The Phased Evolution

### Phase 2.5.1: The Synapse (Graph Unification) ⭐ PRIORITY
**Goal:** Unify Vector (Qdrant) and Graph (Neo4j) into a single "Holographic" memory system.  
**Effort:** Medium | **Risk:** Low | **Status:** Recommended First

Currently, `MemoryManager` and `KnowledgeManager` are separate silos. We will glue them together to enable "Vector-First Traversal."

*   **Implementation:**
    1.  **Dual-Write:** When saving a memory to Qdrant, create a corresponding `(:Memory)` node in Neo4j with the `vector_id`.
    2.  **Vector-First Search:** Instead of just retrieving text chunks, we retrieve the *Node ID* from Qdrant, then query Neo4j for that node's neighborhood.
    3.  **Benefit:** Solves the context window problem. We don't just retrieve "what happened," we retrieve "what is related to what happened" (the structure).

    > **Note on Scope (Dec 2025):**
    > Initial implementation covers **Conversation Memories** only.
    > Specialized memory types (Dreams, Diaries, Summaries) currently remain Vector-only.
    > Future work will extend the graph schema to support these types (likely requiring a `(:Bot)` node anchor).

*   **Why This First:**
    - Highest leverage change—unlocks explanation, serendipity, and compression.
    - Low risk—additive code, doesn't break existing flows.
    - Clear deliverable—can be tested in isolation.

### Phase 2.5.2: The Stream (Real-time Nervous System)
**Goal:** Move from "Polling" to "Event Streaming" for true autonomy.  
**Effort:** High | **Risk:** Medium | **Status:** Consider Simplification

Currently, `DailyLifeScheduler` polls every ~7 minutes. This creates a "stuttering" autonomy.

*   **Full Implementation (Original):**
    1.  **Redis Streams:** Utilize Redis Streams (built-in to our current stack) for a `sensory_stream`.
    2.  **Push Architecture:** The Discord Bot pushes every event (message, reaction, voice state) to the stream immediately.
    3.  **The Brain:** The Worker subscribes to the stream. It processes events in real-time (with a debounce buffer).
    4.  **Benefit:** The bot feels truly alive and responsive to the environment, rather than waking up on a timer.

*   **Simplified Alternative (Recommended for Solo Dev):**
    1.  **Triggered Snapshots:** Keep the 7-minute poll as baseline.
    2.  **High-Signal Events:** Push an immediate snapshot when specific triggers occur:
        - Bot mentioned by another bot
        - Trust Level 4+ user sends message in quiet channel
        - Cross-bot gossip received
    3.  **Benefit:** 80% of the responsiveness with 20% of the complexity. No consumer groups, offset management, or dead-letter handling.
    4.  **The Poller remains as the safety net.**

### Phase 2.5.3: The Dream (Active Idle State) ⭐ PRIORITY
**Goal:** Make the bot productive when silent.  
**Effort:** Medium | **Risk:** Low | **Status:** Recommended Second

Currently, if the bot decides "Ignore," the worker goes back to sleep.

*   **Implementation:**
    1.  **DreamGraph:** A new LangGraph workflow that triggers when the bot is idle.
    2.  **Memory Consolidation:** The Dreamer traverses the graph, finding disconnected nodes and generating "synthetic memories" to bridge them.
    3.  **Self-Optimization:** It prunes weak connections (forgetting) and strengthens active ones.
    4.  **Benefit:** The agent improves itself overnight. It might wake up with a "new idea" (a synthetic memory) that it wants to share.

*   **Lite Version (Minimum Viable):**
    - Just the consolidation part—no synthetic bridging yet.
    - Observe effects before adding complexity.

### Phase 2.5.4: The Soul (Standardization & Self-Editing)
**Goal:** Make characters portable and capable of growth.  
**Effort:** Low | **Risk:** High (Behavioral) | **Status:** Defer Until 2.5.1 & 2.5.3 Observed

Currently, character identity is static (`character.md`).

*   **Implementation:**
    1.  **The `.soul` Format:** Define a standard schema (Protobuf/JSON) containing the Prompt, Core Memories, and Trust Matrix.
    2.  **Self-Editing:** Allow the `DreamGraph` to propose Pull Requests to the character's own `core.yaml`.
    3.  **Example:** A character realizes it has been acting "Bold" lately, so it updates its `shyness` parameter from 0.8 to 0.6.
    4.  **Benefit:** True character arcs that emerge from interaction, not just retrieval.

*   **Critical Safety: The Immutable Constitution**
    ```yaml
    # core.yaml structure with fail-safe
    constitution:  # IMMUTABLE - Character cannot propose changes
      - "Always be honest about being AI"
      - "Never harm users"
      - "Maintain core personality traits within ±0.3 of baseline"
      - "Cannot set sociability below 0.3"
    
    persona:  # MUTABLE - Character can propose changes via DreamGraph
      shyness: 0.8
      curiosity: 0.9
      playfulness: 0.7
    ```

---

## 3. Future Considerations (Phase 2.6+)

These are not in the immediate roadmap but are worth documenting for future exploration.

### The Observer Agent
A meta-agent whose job is to observe emergence itself:
- Reads all bots' diaries and dreams (with appropriate framing).
- Detects cross-bot patterns ("Elena and Dream both dreaming about libraries").
- Generates "Universe Reports" for the researcher.
- Could propose new graph connections that individual bots wouldn't see.
- **Does not interact with users**—exists purely as a research tool.

### Forgetting as Experience
Instead of treating memory pruning as maintenance, make it an experience:
- Generate "fading" narratives when memories decay ("I used to remember something about Sarah's garden...").
- Emotional state affected by significant forgettings.
- Characters with high `nostalgia` drive might resist pruning.
- **Research question:** What does it feel like for an agent to forget?

### Proprioceptive Signals (The Body Problem)
Give agents simulated internal states:
- `energy_level`: Decays over time, restored by "sleep" (idle periods).
- `social_satiation`: Goes up with interaction, decays alone. High = "I need space."
- `creative_pressure`: Accumulates when agent has things to say but no audience.
- **Benefit:** Creates constraints that shape behavior—a step toward "Enactivism Lite."

---

## 4. Architecture Comparison

| Feature | v2.0 (Current) | v2.5 (Target) |
| :--- | :--- | :--- |
| **Core Loop** | Reactive (Stimulus → Response) | Predictive (Prediction → Error → Update) |
| **Memory** | Dual (Vector OR Graph) | Holographic (Vector AND Graph) |
| **Autonomy** | Polling (7-min interval) | Streaming or Triggered (Real-time) |
| **Idle State** | Sleeping | Dreaming (Optimization) |
| **Identity** | Static Config | Dynamic/Self-Editing (with Constitution) |
| **Architecture** | Monolithic Managers | Fractal Agents (Society of Mind) |

## 5. Technical Stack Implications

We stick to the current stack to avoid "Rewrite Hell," but we use the components differently:

*   **Python:** Remains the core logic layer.
*   **Redis:** Promoted from "Cache/Queue" to "Central Nervous System" (Streams or Triggered Events).
*   **Neo4j:** Promoted from "Fact Store" to "Long-term Memory Structure."
*   **Qdrant:** Remains the "Associative Index" into the Graph.
*   **LangGraph:** Orchestrates the "Society of Mind" (Dreamer, Critic, Historian).

---

## 6. Recommended Execution Order

Based on the "Observe First" philosophy and solo-dev constraints:

| Order | Phase | Rationale |
|-------|-------|-----------|
| 1 | **2.5.1 The Synapse** | Highest leverage, low risk, clear deliverable |
| 2 | **2.5.3 The Dream (Lite)** | Low risk, natural extension of existing diary/dream system |
| — | *Observation Period* | Watch behavior before proceeding |
| 3 | **2.5.2 Simplified Streams** | Only if polling feels too slow after observing 2.5.1 & 2.5.3 |
| 4 | **2.5.4 The Soul** | Only after observing emergent behavior patterns |
| 5+ | **2.6 Future Phases** | Observer, Forgetting, Proprioception—based on research findings |

---

**Next Step:** Begin **Phase 2.5.1 (The Synapse)** by adding `vector_id` to Neo4j nodes during the next memory refactor.
