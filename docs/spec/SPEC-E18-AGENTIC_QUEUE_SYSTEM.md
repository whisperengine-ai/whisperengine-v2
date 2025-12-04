# Agentic Queue System: The Stigmergic Nervous System

**Status:** ✅ Complete (E18 - December 2025)
**Target Phase:** E18
**Dependencies:** Supergraph Architecture (E17 - Complete)

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Background processing architecture |
| **Proposed by** | Mark + Claude (collaborative) |
| **Catalyst** | Insight generation blocking response pipeline |
| **Key insight** | Async queue enables parallel cognitive processes |

---

> **Implementation Note:** Phase 1 (Shared Worker) is complete. The system uses a single `insight-worker` container serving all bot instances via the `arq:cognition` queue. See [ref/REF-017-AGENTIC_QUEUE.md](../ref/REF-017-AGENTIC_QUEUE.md) for current implementation.

## Current Implementation (Dec 2024)

The queue system is now operational with the following architecture:

### Queue Names (arq-compatible)
| Queue | Purpose | Listener |
|-------|---------|----------|
| `arq:cognition` | Deep reasoning tasks | Single shared worker container |
| `whisper:broadcast:queue:{bot_name}` | Discord broadcasts | Each bot polls its own queue via background task |

### Key Files
- `src_v2/workers/worker.py` - Worker with `queue_name = "arq:cognition"`
- `src_v2/workers/task_queue.py` - TaskQueue with `_queue_name` parameter
- `src_v2/broadcast/manager.py` - Bot-specific broadcast queues

### Usage
```python
# Enqueue a cognitive task
await task_queue.enqueue(
    "run_agentic_diary_generation",
    character_name="elena",
    _queue_name="arq:cognition"
)

# Broadcast queues are automatic - workers push, bots poll
await broadcast_manager.queue_broadcast(content, PostType.DIARY, "elena")
# -> Queues to whisper:broadcast:queue:elena
```

---

## 1. The Vision

Currently, WhisperEngine relies on a procedural "Clock" (Scheduler) that triggers specific scripts at specific times (e.g., "Run `make_diary()` at 10 PM"). This couples the *timing* of an event with the *execution* of that event.

The **Agentic Queue System** decouples these. The Scheduler becomes a simple "Heartbeat" that posts signals to a shared environment (Redis Queue). Autonomous Workers (Agents) pick up these signals and decide how to process them.

This shifts the architecture from **Procedural** to **Stigmergic** (communication via environment modification), enabling a true "Society of Mind" where agents can trigger each other asynchronously.

### Current vs. Future State

**Current (Procedural):**
```python
# Scheduler Loop
if time == "22:00":
    import diary_module
    diary_module.generate_diary(bot_name) # Blocks or runs in specific thread
```

**Future (Stigmergic):**
```python
# Scheduler Loop
if time == "22:00":
    queue.publish("trigger:diary", {"bot": bot_name})

# Worker (The Subconscious)
@worker.listen("trigger:diary")
def on_diary_trigger(event):
    # I have capacity, I will dream now.
    DreamWeaverGraph.invoke(event.bot)
```

## 2. Architecture Components

### 2.1 The Topic Map (Queues)

We organize the collective intelligence into specialized queues (Topics).

| Queue | Purpose | Examples | Status |
|-------|---------|----------|--------|
| `arq:cognition` | Deep reasoning, slow tasks | Dreams, Diaries, Reflection, Strategy | ✅ Implemented |
| `broadcast:queue:{bot}` | Per-bot Discord actions | Diary posts, Dream posts | ✅ Implemented |
| `arq:sensory` | Fast, real-time analysis | Sentiment, Intent, Fact Extraction | 🔮 Future |
| `arq:social` | Inter-agent communication | Gossip, Observations, Trust Updates | 🔮 Future |
| `arq:action` | Outbound effects | Image Gen, Voice Gen, Proactive Messages | 🔮 Future |

### 2.2 The Worker Swarm

Currently using a single worker type with 3 replicas. Future: specialized workers.

```python
# Current Implementation
class WorkerSettings:
    queue_name = "arq:cognition"  # Single queue per worker instance
    # Note: arq only supports one queue_name per worker, not a list

# Future: Multiple specialized worker containers
# - cognition-worker: queue_name = "arq:cognition"
# - sensory-worker: queue_name = "arq:sensory"  
# - action-worker: queue_name = "arq:action"
```

## 3. Implementation Plan

### Phase 1: Decouple Scheduling (The "Heartbeat") ✅ COMPLETE
Refactor the existing `cron_tasks.py` to stop executing logic and start posting events.

```python
# src_v2/workers/tasks/cron_tasks.py

async def run_nightly_diary_generation(ctx):
    # Enqueue to arq:cognition for actual processing
    await ctx['redis'].enqueue_job(
        "run_agentic_diary_generation",
        character_name=char_name,
        _queue_name="arq:cognition"
    )
```

### Phase 2: Bot-Specific Broadcast Queues ✅ COMPLETE
Each bot has its own queue for Discord actions, eliminating race conditions.

```python
# src_v2/broadcast/manager.py
bot_queue_key = f"whisper:broadcast:queue:{character_name.lower()}"
# Each bot polls only its own queue - no more requeuing items for other bots
```

### Phase 3: Specialized Workers (Future)
Deploy separate worker containers for different queue types.

### Phase 4: Inter-Agent Triggers (Future)
Update agents to post to the queue instead of returning passive strings.

```python
# InsightAgent (running in Worker)
if user_is_sad:
    await task_queue.enqueue(
        "schedule_proactive_message", 
        queue="arq:action", 
        delay="4h"
    )
```

---

## 3.5 LangGraph Conversion Status

See [ref/REF-006-AGENT_GRAPH_SYSTEM.md](../ref/REF-006-AGENT_GRAPH_SYSTEM.md) for detailed LangGraph architecture and migration status.

**Summary:**
- ✅ Reflective, Character, Insight, Diary, Dream, Reflection, Strategist agents all have LangGraph versions
- 🔮 Remaining candidates: `run_summarization`, `run_knowledge_extraction` (low priority)

---

## 4. Benefits

1.  **Scalability**: Scale "Dreaming" (Cognition) independently of "Chatting" (Sensory).
2.  **Resilience**: A crash in the Dream module doesn't kill the Scheduler.
3.  **Emergence**: Agents can trigger each other. An Insight Agent can trigger a Proactive Agent, creating a feedback loop that feels like organic behavior.
4.  **Observability**: We can inspect the Redis Queue to see what the "Subconscious" is thinking about (pending tasks).
