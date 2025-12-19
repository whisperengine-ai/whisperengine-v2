# SPEC-004: Neuro-Symbolic Architecture

**Status:** Draft
**Created:** 2025-12-18
**Owner:** Solo Developer
**Related PRD:** `PRD-004-NEURO_SYMBOLIC_ENHANCEMENTS.md`

## 1. Architecture Overview

This specification defines the implementation of the "Post-Agent" Neuro-Symbolic architecture for WhisperEngine v2. It introduces three key components:
1.  **WorkingMemoryManager:** Redis-backed session state.
2.  **FactVerifier:** Neo4j-backed consistency checker.
3.  **ReinforcementLoop:** Qdrant-backed weight adjustment.

## 2. Component Design

### 2.1 Working Memory (Redis)

**Purpose:** Store transient context that outlives the context window but isn't permanent.

**Data Structure (Redis Hash):**
Key: `working_memory:{bot_name}:{user_id}`
TTL: 30 minutes (sliding)

Fields:
*   `current_topic`: string (e.g., "gift shopping")
*   `active_goal`: string (e.g., "find watch for father")
*   `pending_questions`: json_list (e.g., ["budget?", "style?"])
*   `last_updated`: timestamp

**Interface:**
```python
class WorkingMemoryManager:
    async def update_context(self, user_id: str, topic: str, goal: str) -> None:
        """Updates Redis hash and resets TTL."""
        
    async def get_context(self, user_id: str) -> Dict[str, Any]:
        """Retrieves current working memory."""
        
    async def clear_context(self, user_id: str) -> None:
        """Manually clears context (e.g., on 'goodbye')."""
```

**Integration:**
*   Called in `AgentEngine.generate_response` *before* prompt construction.
*   Injected into System Prompt as:
    ```
    [Current Working Memory]
    Topic: {topic}
    Goal: {goal}
    ```

### 2.2 Hybrid Verification (Neo4j)

**Purpose:** Prevent hallucinations by checking generated claims against the Graph.

**Logic Flow:**
1.  **Generation:** LLM generates response.
2.  **Extraction:** (Optional) Lightweight LLM extracts "claims" from response.
3.  **Query:** Check claims against Neo4j.
    *   *Claim:* "I live in Paris."
    *   *Query:* `MATCH (b:Bot {name: $name}) RETURN b.location`
    *   *Result:* "New York" -> **CONFLICT**
4.  **Action:** If conflict, regenerate with feedback: "You said you live in Paris, but your profile says New York. Correct this."

**Implementation:**
*   Implemented as a `Tool` in the `ReflectiveAgent`.
*   Triggered only when `complexity="complex"` or specific keywords (locations, names, dates) are present.

### 2.3 Outcome-Based Reinforcement (Qdrant)

**Purpose:** Reinforce memories that lead to positive outcomes.

**Logic Flow:**
1.  **Pre-Response:** Record `start_trust = TrustManager.get_score(user_id)`.
2.  **Retrieval:** Log `retrieved_memory_ids` used for this response.
3.  **Post-Response:** 
    *   Wait for user reply (or immediate sentiment analysis).
    *   Calculate `delta = new_trust - start_trust`.
4.  **Reinforcement:**
    *   If `delta > threshold`:
        *   For each `mem_id` in `retrieved_memory_ids`:
            *   Fetch payload from Qdrant.
            *   `new_weight = current_weight + (delta * learning_rate)`.
            *   Update payload: `{"reinforcement_weight": new_weight}`.

**Qdrant Schema Update:**
*   Add `reinforcement_weight` (float, default 1.0) to payload.
*   Update `search` query to boost score by `reinforcement_weight`.

## 3. Implementation Plan

### Phase 1: Working Memory
1.  Create `src_v2/memory/working.py`.
2.  Implement `WorkingMemoryManager` with Redis.
3.  Inject into `AgentEngine` prompt.

### Phase 2: Reinforcement
1.  Modify `src_v2/memory/manager.py` to return `id`s of retrieved memories.
2.  Update `src_v2/evolution/feedback.py` to handle trust deltas.
3.  Implement `boost_memory_weight` method in `MemoryManager`.

### Phase 3: Verification
1.  Create `src_v2/agents/verifier.py`.
2.  Add `verify_fact` tool to `ReflectiveAgent`.
3.  Add retry logic to `AgentEngine`.

## 4. Testing Strategy

*   **Working Memory:** Test conversation continuity across 30-minute gap.
*   **Verification:** Force-feed false prompt ("Say you live on Mars") and verify system corrects it.
*   **Reinforcement:** Simulate high-trust interaction and verify Qdrant payload update.
