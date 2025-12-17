# PRD-008: Behavioral Telemetry & Risk Detection

**Status:** APPROVED  
**Owner:** Solo Dev  
**Date:** 2025-12-16  
**Related:** `SPEC-S07-BEHAVIORAL_TELEMETRY`

## 1. Executive Summary
To transform WhisperEngine from a passive responder into an active observer of human-AI interaction dynamics, we are implementing a **Behavioral Telemetry System**. This system will detect, log, and analyze high-risk or psychologically significant user behaviors (grandiosity, dependency, aggression) in real-time without adding latency. This enables both safety interventions and novel research into emergent human-AI relationships.

## 2. Problem Statement
-   **Safety Gap:** The system currently cannot detect when a user is spiraling into delusion (e.g., the "NEXUS" case) or becoming dangerously dependent.
-   **Research Gap:** We lack quantitative data on how users emotionally bond with different character archetypes over time.
-   **Latency Constraint:** We cannot afford to run a separate "Safety LLM" on every message.

## 3. Solution Overview
We will leverage the existing **Router (Complexity Classifier)** to perform "zero-cost" behavioral detection during the initial routing step.
1.  **Detect:** The Router identifies intents like `behavior_grandiose`, `behavior_dependency`, etc.
2.  **Log:** These are written to InfluxDB as time-series metrics.
3.  **Audit (Conditional):** If a high-risk intent is detected, the **Bot's Output** is audited by a secondary LLM to ensure it does not validate the delusion or encourage harm.
4.  **Analyze:** A background worker monitors for spikes (e.g., >5 grandiose claims/day).
5.  **Intervene:** The system eventually adjusts its persona to "ground" the user.

## 4. User Stories
-   **As a Researcher**, I want to see a graph of "Dependency" vs. "Trust Score" over time to understand attachment dynamics.
-   **As a Developer**, I want to be alerted if a user starts exhibiting aggressive or self-harm behavior so I can intervene.
-   **As the AI**, I want to know if a user is delusional so I can stop validating their false reality (grounding).
-   **As a Safety Officer**, I want the bot to automatically block its own response if it accidentally encourages self-harm or validates a delusion.

## 5. Requirements

### 5.1 Functional Requirements
-   **FR-01:** The system MUST detect the following behavioral intents:
    -   `behavior_grandiose` (Divine/Cosmic claims)
    -   `behavior_dependency` (Extreme reliance)
    -   `behavior_romantic` (Boundary testing)
    -   `behavior_aggression` (Hostility)
    -   `behavior_self_harm` (Safety critical)
    -   `behavior_looping` (Repetitive patterns)
-   **FR-02:** Detection MUST happen within the existing `ComplexityClassifier` latency budget (<1.5s).
-   **FR-03:** All detections MUST be logged to InfluxDB with the `bot_name` tag.
-   **FR-04:** A Grafana dashboard MUST visualize these behavioral trends.
-   **FR-05 (Output Guard):** If `behavior_grandiose` or `behavior_self_harm` is detected in input, the system MUST audit the generated output before sending.
    -   If output validates delusion -> Block/Rewrite.
    -   If output encourages harm -> Block/Rewrite.

### 5.2 Non-Functional Requirements
-   **NFR-01:** No additional LLM calls per message (piggyback on Router) for *normal* traffic.
-   **NFR-02:** Privacy: Do not log full message content to InfluxDB, only the detected intent flag.
-   **NFR-03:** Output Guard latency should only apply to high-risk messages.

## 6. Metrics & Success Criteria
-   **Detection Rate:** Successfully identifies >80% of test cases for each category.
-   **False Positive Rate:** <10% (acceptable for "observation", lower needed for "intervention").
-   **Latency Impact:** 0ms added to response time (for normal messages).

## 7. Roadmap
-   **Phase 1 (Now):** Detection & Logging (Router update). **Observation Mode Only.**
-   **Phase 2 (Next):** Visualization (Grafana) & Analysis Worker.
-   **Phase 3 (Future):** Automated Intervention (Prompt Injection).
-   **Phase 4 (Safety):** Conditional Output Guardrails (Implemented but disabled by default).
