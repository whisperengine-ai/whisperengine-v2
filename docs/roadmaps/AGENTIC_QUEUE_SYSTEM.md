# Agentic Queue System: The Stigmergic Nervous System

**Status:** Proposed
**Target Phase:** E18
**Dependencies:** Supergraph Architecture (E17)

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

| Queue | Purpose | Examples |
|-------|---------|----------|
| `queue:sensory` | Fast, real-time analysis | Sentiment, Intent Detection, Fact Extraction |
| `queue:cognition` | Deep reasoning, slow tasks | Dreams, Diaries, Reflection, Strategy |
| `queue:social` | Inter-agent communication | Gossip, Observations, Trust Updates |
| `queue:action` | Outbound effects | Image Gen, Voice Gen, Proactive Messages |

### 2.2 The Worker Swarm

Instead of a monolithic worker, we can deploy specialized workers that listen to specific queues.

```python
# Pseudocode for Worker Configuration
class SensoryWorker(Worker):
    queues = ["queue:sensory"]
    concurrency = 10  # Fast tasks, high concurrency

class CognitiveWorker(Worker):
    queues = ["queue:cognition"]
    concurrency = 2   # Heavy tasks, low concurrency
```

## 3. Implementation Plan

### Phase 1: Decouple Scheduling (The "Heartbeat")
Refactor the existing `cron_tasks.py` to stop executing logic and start posting events.

```python
# src_v2/workers/tasks/cron_tasks.py

async def run_nightly_diary_check():
    # OLD: run_diary_generation()
    # NEW:
    await redis.enqueue_job("run_agentic_diary", queue="queue:cognition")
```

### Phase 2: Specialized Queues
Update `TaskQueue` and `WorkerSettings` to support multiple named queues.

```python
# src_v2/workers/task_queue.py
class TaskQueue:
    async def enqueue(self, func_name, queue_name="default", **kwargs):
        # ...
```

### Phase 3: Inter-Agent Triggers
Update agents to post to the queue instead of returning passive strings.

```python
# InsightAgent (running in Worker)
if user_is_sad:
    # OLD: return "User is sad"
    # NEW:
    await task_queue.enqueue(
        "schedule_proactive_message", 
        queue="queue:action", 
        delay="4h"
    )
```

## 4. Benefits

1.  **Scalability**: Scale "Dreaming" (Cognition) independently of "Chatting" (Sensory).
2.  **Resilience**: A crash in the Dream module doesn't kill the Scheduler.
3.  **Emergence**: Agents can trigger each other. An Insight Agent can trigger a Proactive Agent, creating a feedback loop that feels like organic behavior.
4.  **Observability**: We can inspect the Redis Queue to see what the "Subconscious" is thinking about (pending tasks).
