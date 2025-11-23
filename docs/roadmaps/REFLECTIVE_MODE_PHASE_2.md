# Reflective Mode Phase 2: Advanced Reasoning Capabilities

This roadmap outlines the implementation plan for the next phase of Reflective Mode (System 2) enhancements. The features are ordered by implementation priority, starting with infrastructure upgrades that pave the way for advanced capabilities.

> **Status Update (Nov 23, 2025)**: Phase 1 (Native Functions) and Phase 2.3 (Parallel Execution) are complete. The system is currently in **User Testing** to validate stability before proceeding with Adaptive Max Steps.

## Phase 1: Foundation & Infrastructure

### 1. Native Function Calling (Infrastructure) - ✅ Completed
*   **Goal**: Replace fragile Regex parsing (`Action: ...`) with native LLM tool calling APIs (e.g., OpenAI Tools / Anthropic Tool Use).
*   **Why First?**: Implementing this first prevents rewriting tool logic later. It provides structured outputs that make "Parallel Tool Execution" and "Tool Composition" significantly easier and more reliable.
*   **Benefit**: Higher reliability, better handling of complex arguments, and fewer syntax errors from the LLM.

---

## Phase 2: Efficiency & Optimization

### 2. Adaptive Max Steps (Heuristic-Based) - ⏸️ On Hold (Pending Testing)
Currently, `REFLECTIVE_MAX_STEPS` is a static global setting (default: 10). This feature aims to dynamically adjust the step limit based on the complexity of the query.

*   **Goal**: Reduce latency for "moderately complex" queries while allowing "deeply complex" queries enough runway.
*   **Implementation**:
    1.  **Heuristic Classification**: Update `ComplexityClassifier` to return buckets (`COMPLEX_LOW`, `COMPLEX_MID`, `COMPLEX_HIGH`) with suggested step counts (5, 10, 15).
    2.  **Engine Update**: Pass `suggested_steps` to `ReflectiveAgent.run()`.
    3.  **User Override**: `!reflect` defaults to `COMPLEX_HIGH`.

### 3. Parallel Tool Execution - ✅ Completed
Currently, the ReAct loop executes tools sequentially. If the agent needs to search for "X" and "Y", it takes two full steps.

*   **Goal**: Allow the agent to issue multiple tool calls in a single "Action" step.
*   **Implementation**:
    *   Leverage the structured output from **Native Function Calling** (Phase 1) to detect multiple tool calls in a single response.
    *   Execute detected actions concurrently using `asyncio.gather`.

---

## Phase 3: Advanced Capabilities

### 4. Tool Composition (Hierarchical Reasoning)
Tool composition allows for more efficient data gathering by creating "Meta-Actions".

*   **Goal**: Allow the agent to perform high-level actions that combine multiple low-level tool calls, reducing LLM round-trips.
*   **Implementation**:
    1.  **Define Composite Tools**: Create tools like `AnalyzeTopic(topic)` that internally call `SearchMemories` + `LookupFacts`.
    2.  **Recursive Execution**: Allow tools to return `AgentAction` objects for immediate execution without re-prompting the LLM.

### 5. Self-Correction / Verification
*   **Goal**: Prevent hallucinations or incomplete answers for high-stakes queries.
*   **Implementation**:
    *   For `COMPLEX_HIGH` queries, add a final "Critic" step.
    *   Before returning the `Final Answer`, the LLM reviews it against the original `Question` and `Observations`.
    *   If the review fails, it generates a "Correction Thought" and continues the loop.

---

## Phase 4: Long-term Learning

### 6. Memory of Reasoning (Reasoning Traces)
Currently, reasoning steps are discarded. This feature allows the bot to "remember how it solved a problem".

*   **Why Last?**: We want to save traces *after* the reasoning logic (Native Tools, Parallelism) is stable, so we don't train the model on legacy/inefficient patterns.
*   **Goal**: Save successful reasoning traces to a persistent store to solve similar future problems faster.
*   **Implementation**:
    1.  **Storage**: New PostgreSQL table `v2_reasoning_traces` (JSONB trace + Embedding).
    2.  **Capture**: Save `scratchpad` after successful `Final Answer`.
    3.  **Retrieval**: Search past traces before starting the loop and inject as "Few-Shot Examples".
