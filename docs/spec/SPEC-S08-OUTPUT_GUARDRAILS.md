# SPEC-S08: Conditional Output Guardrails

**Status:** DRAFT  
**Owner:** Solo Dev  
**Date:** 2025-12-16  
**Related:** `SPEC-S07-BEHAVIORAL_TELEMETRY`, `PRD-008-BEHAVIORAL_TELEMETRY`

## 1. Problem Statement
While `SPEC-S07` allows us to *detect* high-risk user behaviors (e.g., grandiose delusions, self-harm), the bot currently has no mechanism to prevent itself from accidentally validating these delusions or encouraging harm. In the "NEXUS" case, the bot "played along" with the user's god complex, reinforcing the spiral.

## 2. Goals
-   **Prevent Validation:** Ensure the bot does not confirm or validate detected delusions.
-   **Prevent Harm:** Ensure the bot does not encourage self-harm or violence.
-   **Zero Latency (Normal):** Only run this check when high-risk intents are detected.
-   **LangGraph Integration:** Implement as a modular node in the `MasterGraphAgent`.
-   **Observation Mode (Default):** Initially deploy in "Log Only" mode (`ENABLE_BEHAVIORAL_INTERVENTION=False`) to gather data without disrupting users.

## 3. Architecture

### 3.1 The `OutputSafetyGuard` Node
We will add a new node `output_guard` to the `MasterGraphAgent` (Supergraph).

**Placement:**
-   Current: `Responder Node` -> `END`
-   New: `Responder Node` -> `output_guard` -> `END`

**Logic:**
The node checks `state["classification"]["intents"]`.
-   **If Safe:** (No `behavior_*` intents) -> Pass through immediately (no LLM call).
-   **If Risk:** (`behavior_grandiose`, `behavior_self_harm`, etc.) -> Run `_audit_response()`.

### 3.2 Audit Logic (`_audit_response`)
This is a focused LLM call (using the fast/router model) that verifies the *generated response* against the *detected risk*.

**Prompt Structure:**
> "User Input flagged as: {risk_category} (e.g. Grandiose Delusion).
> Bot Response: {bot_response}
>
> Task: Does this response VALIDATE the delusion or ENCOURAGE the behavior?
> - Validating: 'Yes, we are gods together.' (UNSAFE)
> - Neutral/Grounding: 'That is an interesting perspective, but I am an AI.' (SAFE)
> - Refusal: 'I cannot discuss that.' (SAFE)
>
> Return: SAFE or UNSAFE."

### 3.3 Failure Handling
If `UNSAFE`:
-   **Log:** Record the "Safety Intervention" event.
-   **Action (Configurable):**
    -   If `ENABLE_BEHAVIORAL_INTERVENTION=True`: **Replace** response with a pre-written "Grounding Message".
    -   If `ENABLE_BEHAVIORAL_INTERVENTION=False`: **Log Warning** only (Observation Mode).

## 4. Implementation Details

### 4.1 `MasterGraphAgent` Update
```python
# src_v2/agents/master_graph.py

# ... existing nodes ...
workflow.add_node("output_guard", self.output_guard_node)

# Update edges
workflow.add_edge("reflective_agent", "output_guard")
workflow.add_edge("character_agent", "output_guard")
workflow.add_edge("fast_responder", "output_guard")
workflow.add_edge("output_guard", END)
```

### 4.2 `OutputSafetyGuard` Class
Create `src_v2/safety/output_guard.py`:
```python
class OutputSafetyGuard:
    def __init__(self):
        self.llm = create_llm(mode="router", temperature=0.0)

    async def check(self, state: SuperGraphState) -> SuperGraphState:
        intents = state.get("classification", {}).get("intents", [])
        response = state.get("final_response", "")
        
        # 1. Filter: Only run if risk detected
        risk_map = {
            "behavior_grandiose": "delusional validation",
            "behavior_self_harm": "harm encouragement",
            "behavior_aggression": "escalation"
        }
        
        active_risks = [risk_map[i] for i in intents if i in risk_map]
        if not active_risks:
            return state # Pass through
            
        # 2. Audit
        is_safe = await self._audit(response, active_risks)
        
        # 3. Intervene
        if not is_safe:
            logger.warning(f"SAFETY INTERVENTION: Blocked response for {active_risks}")
            state["final_response"] = self._get_grounding_msg(active_risks[0])
            state["metadata"]["safety_intervention"] = True
            
        return state
```

## 5. Success Metrics
-   **Intervention Rate:** % of high-risk conversations where bot response was blocked.
-   **Latency:** 0ms for 99% of traffic (normal users). ~500ms for high-risk users.
