# Feedback Loops & Learning Pipelines

**Document Version:** 1.0  
**Created:** November 27, 2025  
**Status:** Active Architecture

WhisperEngine v2 is designed not just as a static response engine, but as an adaptive system that learns and optimizes over time. This document details the **5 distinct feedback loops** that operate at different timescales, from milliseconds (during generation) to days (long-term evolution).

## Topology of Learning

| Loop Type | Timescale | Mechanism | Goal |
|-----------|-----------|-----------|------|
| **Cognitive** | Milliseconds | Self-Correction (B4) | Accuracy & Safety |
| **Reinforcement** | Seconds | Response Patterns (B6) | Style Adaptation |
| **Optimization** | Minutes | Adaptive Depth (C4) | Resource Efficiency |
| **Evolutionary** | Session | Trust System | Relational Depth |
| **Insight** | Hours/Days | Insight Agent (C1) | Deep Understanding |

---

## 1. The Cognitive Loop (Real-Time)
**Focus:** Accuracy & Hallucination Prevention

*   **Mechanism:** **Phase B4 (Self-Correction)**
*   **Trigger:** Immediately before sending a response in `ReflectiveAgent`.
*   **Action:** The "Critic" step reviews the draft answer against the user's original prompt and observations.
*   **Logic:**
    ```python
    if complexity == COMPLEX_HIGH:
        draft = generate_answer()
        critique = critic.review(draft, original_query)
        if critique.status == "CORRECTION_NEEDED":
            loop.continue(critique.feedback)
    ```
*   **Learning:** Immediate error correction. It prevents hallucinations in the moment but does not persist the lesson.

## 2. The Reinforcement Loop (Interaction-Based)
**Focus:** Style Alignment (RLHF-Lite)

*   **Mechanism:** **Phase B6 / C1 (Response Pattern Learning)**
*   **Trigger:** User reacts with positive feedback (e.g., 👍, ❤️) or explicit praise.
*   **Action:** The system captures the interaction tuple and embeds it for future retrieval.
*   **Data Structure:**
    ```json
    {
      "user_message": "Explain quantum physics like I'm 5",
      "bot_response": "Imagine a cat in a box...",
      "score": 1.0,
      "context_tags": ["explanation", "simple"]
    }
    ```
*   **Learning:** When a similar query arrives later, the bot retrieves these "successful patterns" and injects them as few-shot examples. This effectively mimics **RLHF (Reinforcement Learning from Human Feedback)** without model fine-tuning.

## 3. The Optimization Loop (Meta-Cognitive)
**Focus:** Resource Efficiency & Planning

*   **Mechanism:** **Phase C4 (Adaptive Depth)**
*   **Trigger:** Before starting a reasoning chain in `ComplexityClassifier`.
*   **Action:** The system queries the vector store for "Reasoning Traces" of similar past queries.
*   **Logic:**
    *   "Last time I answered a question about 'Neo4j Cypher syntax', it took 12 steps."
    *   **Decision:** Override default heuristic and allocate `COMPLEX_HIGH` (15 steps).
    *   *Conversely:* If a query looked complex but was solved in 2 steps, downgrade to `COMPLEX_LOW`.
*   **Learning:** The system learns to estimate difficulty based on empirical evidence rather than static rules.

## 4. The Evolutionary Loop (Relational)
**Focus:** Relationship Progression

*   **Mechanism:** **Trust & Sentiment System**
*   **Trigger:** Every user message processed by `TrustManager`.
*   **Action:** Updates `trust_score` (-100 to +100) and `emotional_state`.
*   **State Change:**
    *   **Stranger (-10 to 10):** Formal, guarded, reactive.
    *   **Friend (30 to 60):** Casual, proactive, shares opinions.
    *   **Confidant (80+):** Vulnerable, initiates deep topics, shares secrets.
*   **Learning:** This is a **state-based feedback loop**. The bot "learns" to trust the user, unlocking behaviors that were previously gated.

## 5. The Insight Loop (Analytical)
**Focus:** Deep User Understanding

*   **Mechanism:** **Phase C1 (Insight Agent)**
*   **Trigger:** Background worker (post-session or scheduled).
*   **Action:** Analyzes the entire conversation history to find "Epiphanies" or "Themes" that weren't obvious in the moment.
*   **Process:**
    1.  Load recent session transcript.
    2.  Compare with long-term memory.
    3.  Identify patterns (e.g., "User often deflects when asked about family").
    4.  Synthesize new high-level facts.
*   **Learning:** The bot "wakes up" the next day knowing something deep about the user that it didn't know during the chat. It writes these insights to the Knowledge Graph (Neo4j).

---

## Integration Architecture

All loops feed into the central **Context Builder**:

```mermaid
graph TD
    User[User Input] --> Classifier
    
    subgraph "Memory & Context"
        Patterns[Successful Patterns (Loop 2)]
        Traces[Reasoning Traces (Loop 3)]
        Trust[Trust Score (Loop 4)]
        Insights[Deep Insights (Loop 5)]
    end
    
    Classifier -- "Check Difficulty" --> Traces
    Traces --> Strategy[Execution Strategy]
    
    Strategy --> Agent
    Patterns --> Agent
    Trust --> Agent
    Insights --> Agent
    
    Agent -- "Draft Response" --> Critic[Critic (Loop 1)]
    Critic -- "Feedback" --> Agent
    
    Agent --> Response[Final Response]
    
    Response -- "User Reaction" --> Patterns
    Response -- "Session Log" --> Insights
    Response -- "Sentiment Analysis" --> Trust
    Response -- "Execution Stats" --> Traces
```
