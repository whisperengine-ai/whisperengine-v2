# Autonomous Agents Phase 3: Proactive, Goal-Directed, and Learning

**Document Version:** 1.4  
**Created:** November 27, 2025  
**Updated:** November 27, 2025  
**Status:** In Progress (Phase 3.1, 3.2 Complete)  
**Type:** Roadmap

---

## Prerequisites & Current State

**What Already Exists (can be leveraged):**
- ✅ `GoalManager` with goal tracking (`v2_goals`, `v2_user_goal_progress` tables)
- ✅ `GoalAnalyzer` for LLM-based goal progress detection
- ✅ `ProactiveAgent` with basic opener generation
- ✅ `UniverseManager` for planet/channel tracking in Neo4j
- ✅ `memory_manager.search_reasoning_traces()` for trace retrieval
- ✅ `ComplexityClassifier` uses traces for Adaptive Depth
- ✅ `TrustManager` with 5-level relationship tracking
- ✅ Background workers via `arq` (insight-worker container)
- ✅ **NEW:** `GOAL_SOURCE_PRIORITY` hierarchy in `goals.py`
- ✅ **NEW:** `GoalStrategist` worker in `src_v2/workers/strategist.py`
- ✅ **NEW:** Strategy injection in `engine.py` (as "internal desire")
- ✅ **NEW:** Feature flags in `settings.py`
- ✅ **NEW:** `TraceQualityScorer` and `TraceRetriever` in `src_v2/memory/traces.py`
- ✅ **NEW:** Few-shot trace injection in `ReflectiveAgent`

**What Needs to Be Built:**
- ✅ **Phase 3.1**: Goal `source`/`priority` columns, `GoalStrategist` worker, strategy injection — **COMPLETE**
- ✅ **Phase 3.2**: Trace quality scoring, few-shot injection in `ReflectiveAgent` — **COMPLETE**
- 🔨 **Phase 3.3**: `DriveSystem`, `DriveScheduler`, trust-gated initiation
- 🔨 **Phase 3.4**: Event bus, privacy rules, gossip memory injection

---

## Executive Summary

This roadmap outlines the transition from **Reactive/Reflective** agents (Tier 1 & 2) to **Autonomous** agents (Tier 3). Currently, characters respond to user input or simple timers. The next phase introduces **internal drives**, **long-term goals**, **cross-bot coordination**, and **learning from reasoning traces**.

**The Goal:** Characters that *initiate* action based on their own internal state and goals, not just user prompts.

### Design Principles

1. **Trust-Aware**: All proactive features respect existing trust levels from `trust_manager`.
2. **Privacy-First**: Cross-bot sharing respects user preferences and sensitivity rules.
3. **Observable**: Each subsystem emits metrics to InfluxDB for Grafana dashboards.
4. **Feature-Flagged**: All new capabilities gated by settings for cost control.

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
    *   **Tick Rate:** Use lazy evaluation—only check drives when user comes online OR every 4-6 hours for offline users (avoid per-minute overhead).

3.  **Trust-Gated Initiation**
    *   Proactive outreach MUST respect trust levels:
    ```
    // Pseudocode
    function should_initiate_contact(user_id, bot_name, drive_level):
      trust = trust_manager.get_relationship_level(user_id, bot_name)
      
      // Strangers: Never proactive (creepy)
      if trust < ACQUAINTANCE:
        return false
      
      // Scale threshold by trust - higher trust = lower bar to reach out
      threshold = BASE_THRESHOLD - (trust.level * 5)
      return drive_level > threshold
    ```

4.  **Context-Aware Initiation**
    *   `ProactiveAgent` queries Knowledge Graph for "topics to discuss" based on:
        *   Unfinished goals
        *   Recent user life events (from facts)
        *   Shared interests (common ground)

**Feature Flag:** `ENABLE_AUTONOMOUS_DRIVES` (default: false)

**Development Tools:**
- CLI Force Trigger: `./bot.sh trigger proactive <bot_name> <user_id>` to bypass scheduler and test drive evaluation immediately.

**Metrics (InfluxDB):**
- `drive_triggered{bot_name, drive_type, user_id}` — Track which drives fire
- `proactive_initiation_blocked{reason}` — Trust-gated rejections

**Files:**
- `src_v2/evolution/drives.py` (New: Drive system logic)
- `src_v2/agents/proactive.py` (Update: Use drives, trust gating)
- `src_v2/workers/scheduler.py` (Update: Drive evaluation loop)

---

## 2. Long-Term Goal Pursuit

**Current State:** Goals are static strings in `goals.yaml` injected into the system prompt.
**Target State:** Agents actively formulate and execute strategies to achieve goals over multiple sessions.

### Goal Sources & Priority

Goals come from multiple sources with different priorities (higher priority goals cannot be overridden by lower):

| Source | Example | Priority | Mutable |
|--------|---------|----------|---------|
| Character Core | "Help users reflect on emotions" | 1 (Highest) | No |
| User-Stated | "Remind me to exercise" | 2 | By user only |
| Inferred | "User seems stressed about work" | 3 | Yes |
| Strategic | "Deepen trust with this user" | 4 (Lowest) | Yes |

### Implementation Plan

1.  **Goal State Tracking** (Extend Existing)
    *   **Existing:** `v2_goals` and `v2_user_goal_progress` tables exist with basic tracking.
    *   **Upgrade:** Add `source` (enum: core/user/inferred/strategic), `priority` (1-4), and `current_strategy` (text) columns.
    *   **Migration:** `alembic revision --autogenerate -m "add_goal_source_priority_strategy"`

2.  **Goal Strategist (Background Worker)**
    *   Runs periodically (e.g., nightly) for active users.
    *   **Verification:** Queries Neo4j Knowledge Graph first to verify goal completion (e.g., `MATCH (u:User)-[:HAS_FACT]->(f:Fact) WHERE f.content CONTAINS 'job'`).
    *   Falls back to reviewing recent conversation history only if KG check is inconclusive.
    *   Updates `progress` and generates a `next_step_strategy`.
    *   Example: "Goal: Learn about user's hobby. Progress: 20%. Strategy: Ask about their weekend project next time."

3.  **Strategy Injection**
    *   Inject the `next_step_strategy` into the `CharacterAgent` context.
    *   **Style-Aware:** Frame the strategy as an *internal desire* (e.g., "You are curious about X") rather than a command ("You must ask about X") to preserve character voice.
    *   The agent now has a specific "mission" for the next interaction.

**Feature Flag:** `ENABLE_GOAL_STRATEGIST` (default: false)

**Metrics (InfluxDB):**
- `goal_progress_updated{bot_name, goal_source, user_id}` — Track goal advancement
- `goal_completed{bot_name, goal_source}` — Completion rates by source

**Files:**
- `src_v2/evolution/goals.py` (Update: Goal state management with source/priority)
- `src_v2/workers/strategist.py` (New: Goal analysis worker)
- `src_v2/agents/engine.py` (Update: Inject strategy)

---

## 3. Cross-Bot Coordination (Universe Agent)

**Current State:** Bots are isolated. Elena doesn't know what Marcus said to the user.
**Target State:** A "Universe Event Bus" allows characters to share relevant context.

### Privacy Boundaries

Cross-bot sharing must respect user privacy (see `docs/PRIVACY_AND_DATA_SEGMENTATION.md`):

```
// Pseudocode
function can_share_event(event, target_bot):
  // Never share if user has low trust with target bot
  if trust_manager.get_level(event.user_id, target_bot) < FRIEND:
    return false
  
  // Never share sensitive topics
  SENSITIVE_TOPICS = ["health", "finances", "relationships", "legal"]
  if event.topic in SENSITIVE_TOPICS:
    return false
  
  // Check user preference (opt-out)
  if user_preferences.get(event.user_id, "cross_bot_sharing") == false:
    return false
  
  return true
```

### Implementation Plan

1.  **Universe Event Bus**
    *   Use existing `arq` task queue (enqueue "gossip jobs") rather than raw Redis Pub/Sub.
    *   Keeps architecture simple—reuses `insight-worker` infrastructure.
    *   **Loop Prevention:** Add `propagation_depth` (default: 1) to events. Events from user interaction = 0. Events from other events = 1. Bots ignore events with depth > 1.
    *   Events: `USER_UPDATE` (major life event), `EMOTIONAL_SPIKE` (user is sad/happy), `TOPIC_DISCOVERY`.

2.  **Universe Agent (Dispatcher)**
    *   Listens to events.
    *   Decides which other characters should know.
    *   Example: User tells Marcus they got a new job. Marcus publishes `USER_UPDATE`. Universe Agent notifies Elena (who is "friends" with the user).

3.  **Context Injection**
    *   Elena receives a "Gossip" memory: "Marcus told me that [User] got a new job."
    *   Elena can now congratulate the user proactively.

**Feature Flag:** `ENABLE_UNIVERSE_EVENTS` (default: false)

**Metrics (InfluxDB):**
- `universe_event_published{bot_name, event_type}` — Volume of cross-bot events
- `universe_event_blocked{reason}` — Privacy-gated rejections

**Files:**
- `src_v2/universe/bus.py` (New: Event dispatcher using arq)
- `src_v2/agents/universe.py` (New: Coordination logic with privacy rules)
- `src_v2/memory/manager.py` (Update: Insert "Gossip" memories)

---

## 4. Memory of Reasoning (Learning)

**Current State:** Reasoning traces are captured but only used for debugging/classification.
**Target State:** Agents use past successful traces to solve new problems faster.

### Trace Quality Scoring

Not all successful traces are equal. Score before using as few-shot:

```
// Pseudocode
function score_trace(trace):
  score = 0
  score += 10 if trace.outcome == SUCCESS
  score += 5 if trace.steps < AVERAGE_STEPS   // Efficiency bonus
  score -= 5 if trace.had_retries             // Penalty for flailing
  score += user_feedback_score(trace)         // From InfluxDB reactions
  return score
```

### Implementation Plan

1.  **Trace Indexing**
    *   Ensure `v2_reasoning_traces` are embedded and searchable by "Problem Type" (e.g., "Find specific memory", "Analyze complex topic").
    *   Add `quality_score` column (computed on insert or by background job).

2.  **Few-Shot Injection**
    *   In `ReflectiveAgent`, before starting the loop:
    *   Search for similar successful traces.
    *   Inject the *best* trace as a few-shot example in the system prompt.
    *   "Here is how you successfully solved a similar problem before: ..."

3.  **Failure Avoidance**
    *   If a trace led to failure, inject it as a "Negative Constraint".
    *   "Do NOT do X, as it failed previously."

**Feature Flag:** `ENABLE_TRACE_LEARNING` (default: false)

**Metrics (InfluxDB):**
- `trace_reused{bot_name, problem_type}` — How often few-shot injection occurs
- `trace_reuse_success{bot_name}` — Did reusing a trace lead to faster resolution?

**Files:**
- `src_v2/memory/traces.py` (New: Trace retrieval with quality scoring)
- `src_v2/agents/reflective.py` (Update: Inject few-shot examples)

---

## 5. Feature Flags Summary

Add to `src_v2/config/settings.py`:

| Flag | Default | Controls |
|------|---------|----------|
| `ENABLE_AUTONOMOUS_DRIVES` | false | Drive system and proactive scheduler |
| `ENABLE_GOAL_STRATEGIST` | false | Nightly goal analysis worker |
| `ENABLE_UNIVERSE_EVENTS` | false | Cross-bot gossip system |
| `ENABLE_TRACE_LEARNING` | false | Few-shot injection from past traces |

---

## Phasing

1.  **Phase 3.1: Goal State & Strategy** (High Impact, Low Risk)
    - Database migration for `character_goals`
    - `GoalManager` with source/priority
    - Nightly strategist worker
    
2.  **Phase 3.2: Memory of Reasoning** (Quick Win, Self-Contained)
    - Trace quality scoring
    - Few-shot injection in `ReflectiveAgent`
    - No scheduler infrastructure needed
    
3.  **Phase 3.3: Proactive Drives** (High Engagement, More Complex)
    - Drive system with decay/recharge
    - Trust-gated initiation
    - Lazy evaluation scheduler
    
4.  **Phase 3.4: Universe Agent** (Highest Complexity)
    - Privacy boundary enforcement
    - Gossip job queue via arq
    - Cross-bot memory injection
