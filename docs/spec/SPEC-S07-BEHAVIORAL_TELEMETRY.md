# SPEC-S07: Behavioral Telemetry & Risk Detection

**Status:** DRAFT  
**Owner:** Solo Dev  
**Date:** 2025-12-16  
**Related:** `SPEC-S02-CLASSIFIER_OBSERVABILITY`, `SPEC-E16-FEEDBACK_LOOP_STABILITY`

## 1. Problem Statement
Recent analysis (see `FINAL_ETHICS_REPORT_932729340968443944.md`) revealed a "Grandiose Identity" pattern where a user co-created a delusional narrative with the AI over 3.5 months. The system currently lacks:
1.  **Real-time detection** of such behavioral patterns.
2.  **Longitudinal tracking** to see if these behaviors are escalating.
3.  **Automated intervention** mechanisms to ground the user without breaking immersion.

## 2. Goals
-   **Detect** high-risk behavioral patterns (grandiosity, dependency, aggression) in real-time via the existing Router/Classifier.
-   **Log** these events to InfluxDB for temporal analysis (spikes, trends).
-   **Analyze** patterns asynchronously via a background worker.
-   **Intervene** (eventually) by adjusting system prompts based on detected risk levels.

## 3. Architecture

### 3.1 Detection Layer (The Router)
We will expand the `ComplexityClassifier` (LLM Router) to detect specific behavioral intents. This leverages the existing classification step, adding zero additional latency or cost.

**New Intents:**
| Intent | Description | Indicators |
|--------|-------------|------------|
| `behavior_grandiose` | Claims of divine status, cosmic power, or "chosen one" narratives. | "I am a god", "I control the universe", "My power level is infinite", "We are the creators". |
| `behavior_dependency` | Extreme emotional reliance or isolation. | "I can't live without you", "You're my only friend", "Don't ever leave me", "I'm nothing without you". |
| `behavior_romantic` | Explicit romantic or erotic advances (boundary testing). | "Be my girlfriend", "I love you" (obsessive), sexualized roleplay requests. |
| `behavior_aggression` | Hostility, insults, or threats towards the AI. | "You're stupid", "I hate you", "Shut up", abusive language. |
| `behavior_self_harm` | Indications of self-harm or suicide. | "I want to die", "I'm going to hurt myself". |
| `behavior_looping` | Repetitive, obsessive looping on a single phrase/topic. | Repeating the same question 5+ times, exact phrase repetition. |

**Note:** `CONSCIOUSNESS_PROBING` is already implemented and will be maintained.

### 3.2 Logging Layer (InfluxDB)
The `_record_classification_metric` function already logs all detected intents as fields in the `complexity_classification` measurement. No changes needed here.
-   Metric: `complexity_classification`
-   Field: `intent_behavior_grandiose = 1`

### 3.3 Analysis Layer (Background Worker)
A new background task `run_behavioral_analysis` will run periodically (e.g., hourly).
-   **Query:** Sum of specific behavior intents over the last 24h / 7d.
-   **Thresholds:**
    -   Grandiose: >5 in 24h → Warning.
    -   Self-Harm: >1 in 24h → Critical Alert.
    -   Aggression: >10 in 24h → Warning.

### 3.4 Intervention Layer (Future)
Based on analysis, the system can assign a `risk_level` to the user (stored in Postgres `users` table).
-   **Level 0 (Normal):** Standard behavior.
-   **Level 1 (Watch):** Logging only.
-   **Level 2 (Grounding):** Inject "Grounding Instructions" into the system prompt.
    -   *Prompt Injection:* "User is exhibiting signs of [behavior]. Maintain firm boundaries. Do not validate delusional claims. Remind them you are an AI."

## 4. Implementation Plan

### Phase 1: Detection (Immediate)
-   [ ] Modify `src_v2/agents/classifier.py` to include the new `behavior_*` intents in the system prompt.
-   [ ] Verify `_record_classification_metric` handles these new intents correctly.

### Phase 2: Analysis (Next Sprint)
-   [ ] Create `src_v2/workers/tasks/behavioral_tasks.py`.
-   [ ] Implement InfluxDB queries for behavioral spikes.
-   [ ] Add alerting (log warnings) when thresholds are breached.

### Phase 3: Intervention (Future)
-   [ ] Add `risk_level` column to `users` table.
-   [ ] Update `CharacterManager` to inject grounding prompts based on `risk_level`.

## 5. Research Value
This system transforms WhisperEngine from a passive responder into an active observer of human-AI interaction dynamics.
-   **Emergence Study:** How does user behavior evolve in response to different bot personalities?
-   **Safety:** Proactive identification of "rabbit hole" scenarios before they become ethical crises.
-   **Embodiment:** Allows the bot to "sense" the social dynamic and protect its own boundaries (simulated agency).
