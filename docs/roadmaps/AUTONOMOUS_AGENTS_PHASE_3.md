# Autonomous Agents Phase 3: Proactive, Goal-Directed, and Learning

**Document Version:** 1.0  
**Created:** November 27, 2025  
**Status:** Planning  
**Type:** Roadmap

---

## Executive Summary

This roadmap outlines the transition from **Reactive/Reflective** agents (Tier 1 & 2) to **Autonomous** agents (Tier 3). Currently, characters respond to user input or simple timers. The next phase introduces **internal drives**, **long-term goals**, **cross-bot coordination**, and **learning from reasoning traces**.

**The Goal:** Characters that *initiate* action based on their own internal state and goals, not just user prompts.

---

## 1. Proactive Agency (Initiative)

**Current State:** `ProactiveAgent` exists but relies on simple timers or random checks.
**Target State:** Agents initiate contact based on a "Drive System" (e.g., curiosity, social need, worry).

### Implementation Plan

1.  **Drive System (Internal State)**
    *   Add `drives` to `Character` model (e.g., `social_battery`, `curiosity`, `concern`).
    *   Drives decay/increase over time or based on events.
    *   Example: `social_battery` drains when alone, recharges when chatting. `concern` increases if a user with high trust hasn't been seen.

2.  **Smart Proactive Scheduler**
    *   Replace simple timer with a `DriveScheduler`.
    *   Periodically evaluates drives for all active characters.
    *   If `drive > threshold`, triggers `ProactiveAgent`.

3.  **Context-Aware Initiation**
    *   `ProactiveAgent` queries Knowledge Graph for "topics to discuss" based on:
        *   Unfinished goals
        *   Recent user life events (from facts)
        *   Shared interests (common ground)

**Files:**
- `src_v2/evolution/drives.py` (New: Drive system logic)
- `src_v2/agents/proactive.py` (Update: Use drives)
- `src_v2/workers/scheduler.py` (Update: Drive evaluation loop)

---

## 2. Long-Term Goal Pursuit

**Current State:** Goals are static strings in `goals.yaml` injected into the system prompt.
**Target State:** Agents actively formulate and execute strategies to achieve goals over multiple sessions.

### Implementation Plan

1.  **Goal State Tracking**
    *   Convert goals from static strings to objects with state: `status` (active/completed), `progress` (0-100), `strategy` (text).
    *   Store in PostgreSQL (`character_goals` table).

2.  **Goal Strategist (Background Worker)**
    *   Runs periodically (e.g., nightly) for active users.
    *   Reviews recent conversation history against active goals.
    *   Updates `progress` and generates a `next_step_strategy`.
    *   Example: "Goal: Learn about user's hobby. Progress: 20%. Strategy: Ask about their weekend project next time."

3.  **Strategy Injection**
    *   Inject the `next_step_strategy` into the `CharacterAgent` context.
    *   The agent now has a specific "mission" for the next interaction.

**Files:**
- `src_v2/evolution/goals.py` (Update: Goal state management)
- `src_v2/workers/strategist.py` (New: Goal analysis worker)
- `src_v2/agents/engine.py` (Update: Inject strategy)

---

## 3. Cross-Bot Coordination (Universe Agent)

**Current State:** Bots are isolated. Elena doesn't know what Marcus said to the user.
**Target State:** A "Universe Event Bus" allows characters to share relevant context.

### Implementation Plan

1.  **Universe Event Bus**
    *   Redis Pub/Sub channel for "Universe Events".
    *   Events: `USER_UPDATE` (major life event), `EMOTIONAL_SPIKE` (user is sad/happy), `TOPIC_DISCOVERY`.

2.  **Universe Agent (Dispatcher)**
    *   Listens to events.
    *   Decides which other characters should know.
    *   Example: User tells Marcus they got a new job. Marcus publishes `USER_UPDATE`. Universe Agent notifies Elena (who is "friends" with the user).

3.  **Context Injection**
    *   Elena receives a "Gossip" memory: "Marcus told me that [User] got a new job."
    *   Elena can now congratulate the user proactively.

**Files:**
- `src_v2/universe/bus.py` (New: Event bus)
- `src_v2/agents/universe.py` (New: Coordination logic)
- `src_v2/memory/manager.py` (Update: Insert "Gossip" memories)

---

## 4. Memory of Reasoning (Learning)

**Current State:** Reasoning traces are captured but only used for debugging/classification.
**Target State:** Agents use past successful traces to solve new problems faster.

### Implementation Plan

1.  **Trace Indexing**
    *   Ensure `v2_reasoning_traces` are embedded and searchable by "Problem Type" (e.g., "Find specific memory", "Analyze complex topic").

2.  **Few-Shot Injection**
    *   In `ReflectiveAgent`, before starting the loop:
    *   Search for similar successful traces.
    *   Inject the *best* trace as a few-shot example in the system prompt.
    *   "Here is how you successfully solved a similar problem before: ..."

3.  **Failure Avoidance**
    *   If a trace led to failure, inject it as a "Negative Constraint".
    *   "Do NOT do X, as it failed previously."

**Files:**
- `src_v2/memory/traces.py` (New: Trace retrieval)
- `src_v2/agents/reflective.py` (Update: Inject few-shot examples)

---

## Phasing

1.  **Phase 3.1: Goal State & Strategy** (High Impact, Low Risk)
2.  **Phase 3.2: Proactive Drives** (High Engagement)
3.  **Phase 3.3: Memory of Reasoning** (Optimization)
4.  **Phase 3.4: Universe Agent** (Complexity)
