# Agentic Queue Architecture: The Stigmergic Nervous System

**Version:** 1.0  
**Date:** December 1, 2025  
**Status:** Proposed / In-Progress

## 1. The Vision: From "Scripts" to "Collective Intelligence"

WhisperEngine v2 is evolving from a **Procedural System** (where a central clock triggers scripts) to a **Stigmergic System** (where agents react to signals in the environment).

In this new paradigm, the **Redis Task Queue** becomes the shared "environment" or "nervous system" of the collective intelligence. Agents do not command each other; they post **Signals** (Tasks) to specific **Topics** (Queues), and other agents pick them up asynchronously.

### Core Philosophy
1.  **Decoupling Time from Cognition**: The "Clock" (Scheduler) only knows *when* something should happen, not *how*. It posts a signal. The "Brain" (Worker) decides how to process it.
2.  **Asynchronous Cognition**: "Dreaming", "Reflecting", and "Planning" are heavy cognitive loads that should not block the sensory loop (Discord Bot).
3.  **Stigmergy**: Agents communicate by modifying the environment (the Queue). An Insight Agent leaves a "User is Sad" signal; a Proactive Agent picks it up and schedules a check-in.

---

## 2. The Architecture Shift

### Old Model (Monolithic / Procedural)
*   **Scheduler**: "It is 10:00 PM. I will import the `make_diary` function and run it now."
*   **Problem**: The Scheduler needs to know *how* to make a diary. If the diary logic crashes, the scheduler crashes. Scaling is hard.
*   **Flow**: `Clock -> Function Execution -> Database`

### New Model (Agentic / Event-Driven)
*   **Scheduler**: "It is 10:00 PM. I am posting a `trigger:diary` event to the `queue:cognition` topic."
*   **Worker (The Subconscious)**: "I see a `trigger:diary` event. I have capacity. I will process it using the latest `DreamWeaver` graph."
*   **Flow**: `Clock -> Signal (Queue) -> Agent Pickup -> Graph Execution -> Database`

---

## 3. The Topic Queue Map

We organize the collective intelligence into specialized queues (Topics). This allows us to scale specific cognitive functions independently.

### A. `queue:sensory` (Fast / Real-time)
*   **Purpose**: Processing raw inputs that need quick analysis but aren't blocking the chat UI.
*   **Tasks**:
    *   `analyze_sentiment`: Quick mood check.
    *   `extract_facts`: Fast entity extraction (Neo4j).
    *   `detect_intent`: Is this a voice request? Image request?

### B. `queue:cognition` (Slow / Deep)
*   **Purpose**: Heavy lifting, deep reasoning, narrative generation.
*   **Tasks**:
    *   `run_agentic_diary`: Generating the daily narrative.
    *   `run_agentic_dream`: Processing the day's memories into metaphors.
    *   `run_reflection`: Analyzing long-term user patterns.
    *   `run_goal_strategist`: Updating the character's long-term goals.

### C. `queue:social` (Inter-Agent / Stigmergic)
*   **Purpose**: How bots "talk" to each other or share knowledge without direct DMs.
*   **Tasks**:
    *   `store_observation`: "I saw User X do Y." (Shared Knowledge Graph).
    *   `dispatch_gossip`: "Tell the other bots about this event."
    *   `update_relationship`: Re-calculating trust scores based on recent interactions.

### D. `queue:action` (Outbound)
*   **Purpose**: Things that result in a tangible effect on the world.
*   **Tasks**:
    *   `generate_image`: Stable Diffusion / Flux generation.
    *   `generate_voice`: ElevenLabs TTS.
    *   `schedule_proactive_msg`: "Send a message to User X in 4 hours."

---

## 4. The "Stigmergic Loop" Example

Here is how a complex behavior emerges from simple, decoupled agents using this architecture:

1.  **Sensory Event**: User says "I'm feeling really lonely today" in `#general`.
2.  **Discord Bot**: Posts `analyze_sentiment` to `queue:sensory`.
3.  **Insight Agent (Worker)**: Picks up task. Detects `mood: lonely`.
    *   *Action*: Posts `store_observation` to `queue:social`.
    *   *Action*: Posts `trigger:proactive` to `queue:action` with delay=4h.
4.  **Knowledge Agent (Worker)**: Picks up `store_observation`. Updates Neo4j: `(User)-[:FEELING]->(Lonely)`.
5.  **Proactive Agent (Worker)**: (4 hours later) Picks up `trigger:proactive`.
    *   Checks Neo4j. Sees user was lonely.
    *   Generates a warm "Thinking of you" message.
    *   Sends to Discord.

**Result**: The bot "remembered" to check in, but no single script defined this entire flow. It emerged from the interaction of specialized agents via the queue.

---

## 5. Implementation Roadmap

### Phase 1: Decouple Scheduling (Done/In-Progress)
- [x] Refactor `cron_tasks.py` to enqueue jobs instead of running them.
- [x] Update `trigger_*.py` scripts to use the queue.
- [ ] Verify `TaskQueue` can handle multiple named queues (currently single default queue).

### Phase 2: Specialized Workers
- [ ] Define `WorkerSettings` to listen to specific queues (e.g., `Worker(queues=['cognition'])`).
- [ ] Split the monolithic `worker.py` into `cognitive_worker.py`, `sensory_worker.py`, etc. (Optional, for scaling).

### Phase 3: Inter-Agent Triggers
- [ ] Update `InsightAgent` to post jobs to `TaskQueue` instead of just returning strings.
- [ ] Create `ProactiveWorker` that listens for `trigger:proactive` events.

### Phase 4: The "Hive Mind" Dashboard
- [ ] Build a simple UI (or CLI tool) to view the state of the queues.
- [ ] Visualize the flow of information (Sensory -> Cognition -> Action).

---

## 6. Alignment with Research Goals

This architecture directly supports the **Emergence Research** goals:
*   **Observability**: We can inspect the Queue to see what the "Collective Subconscious" is thinking about.
*   **Intervention**: We can inject signals into the queue (e.g., "simulate:crisis") to see how the agents react, without changing code.
*   **Evolution**: We can A/B test different "Dreamer" agents by having them listen to the same queue and comparing results.
