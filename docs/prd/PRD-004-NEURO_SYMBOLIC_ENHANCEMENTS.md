# PRD-004: Neuro-Symbolic Enhancements (Post-Agent Architecture)

**Status:** Draft
**Created:** 2025-12-18
**Owner:** Solo Developer
**Related Docs:** `TRANSFORMER_EVOLUTION_ADDENDUM.md`, `SPEC-004-NEURO_SYMBOLIC_ARCHITECTURE.md`

## 1. Executive Summary

This PRD outlines the next evolutionary step for WhisperEngine v2, moving beyond standard "Agent" architectures toward a **Neuro-Symbolic System**. 

Current agents suffer from three specific limitations exposed by the "Post-Agent" research:
1.  **Statelessness:** They lack a "working memory" scratchpad for immediate, transient context (relying only on the sliding context window).
2.  **Hallucination:** LLMs are great generators but poor judges; they often contradict established facts in the Knowledge Graph.
3.  **Open Loops:** The system does not explicitly "learn" which strategies worked; successful interactions don't reinforce the memories that generated them.

We will implement **Working Memory**, **Hybrid Verification**, and **Outcome-Based Reinforcement** to address these gaps.

## 2. Problem Statement

### 2.1 The "Scratchpad" Gap
When a user says "I'm looking for a gift," and 10 messages later says "maybe a watch," the bot often loses the thread if the context window is crowded. It lacks a persistent, short-term place to store "Current Goal: Help user find a gift."

### 2.2 The Verification Gap
The bot might hallucinate "I remember we went to Paris" even if the Knowledge Graph explicitly stores `(User)-[:LOCATED_IN]->(New York)`. The LLM generates text, but the system doesn't validate it against known truth.

### 2.3 The Feedback Gap
If a specific memory retrieval leads to a massive increase in Trust Score, the system currently treats that memory the same as any other. It doesn't "learn" that *this specific memory* is high-value for *this specific user*.

## 3. Proposed Features

### 3.1 Feature A: Working Memory (Redis)
A transient, session-based memory store that persists for ~30 minutes.
*   **Function:** Stores current topics, active goals, and temporary variables.
*   **Behavior:** "Short-term RAM" that bridges the gap between the Context Window (L1 Cache) and Qdrant/Neo4j (Hard Drive).
*   **Expiration:** Auto-expires after inactivity.

### 3.2 Feature B: Hybrid Verification (Neo4j)
A "Fact Check" step for the Reflective Agent.
*   **Function:** Before sending a response containing factual claims about the user or self, query the Knowledge Graph to verify consistency.
*   **Behavior:** If the LLM generates a claim that contradicts the Graph, the Verifier blocks it and requests a regeneration.

### 3.3 Feature C: Outcome-Based Reinforcement
A feedback loop that modifies memory weights.
*   **Function:** Monitor `trust_score` deltas after interactions.
*   **Behavior:** If `trust_score` increases significantly, identify the memories retrieved for that response and boost their `importance` or `reinforcement_weight` in Qdrant.
*   **Result:** The bot "learns" which memories resonate with the user.

## 4. User Stories

*   **As a user**, I want the bot to remember what we were talking about 20 minutes ago even if we went on a tangent, so I don't have to repeat my goal.
*   **As a developer**, I want the bot to stop making up facts that contradict what it already knows, so I can trust its long-term consistency.
*   **As a researcher**, I want to see the bot's personality "optimize" over time, favoring memories and behaviors that actually build trust.

## 5. Success Metrics

*   **Hallucination Rate:** Reduction in responses that contradict Neo4j facts (measured via `run_regression.py --category consistency`).
*   **Task Completion:** Improvement in multi-turn goal completion (e.g., "Find a gift") without restating the goal.
*   **Trust Velocity:** Faster accumulation of Trust Score due to reinforced successful strategies.

## 6. Risks & Mitigations

*   **Latency:** Adding a Verification step adds LLM + DB time.
    *   *Mitigation:* Only run Verification on `complex` queries or when specific entity types are mentioned.
*   **Complexity:** Managing three layers of memory (Context, Working, Long-term) is hard.
    *   *Mitigation:* Keep Working Memory strictly transient (Redis with TTL). It is not a system of record.
