# REF-022: Background Workers & Task Queue

**Status:** Active  
**Last Updated:** December 5, 2025  
**Author:** WhisperEngine Team

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Core architecture design |
| **Purpose** | Document background processing architecture and all async tasks |
| **Key Insight** | Offload expensive LLM operations from the response path to maintain fast UX |

---

## Overview

WhisperEngine uses **arq** (Async Redis Queue) for background task processing. This decouples expensive operations (summarization, fact extraction, diary generation) from the user-facing response path.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         BOT PROCESS                             │
│                                                                 │
│  User Message → Response → Enqueue Background Tasks             │
│                                   │                             │
└───────────────────────────────────┼─────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                          REDIS                                  │
│                                                                 │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐ │
│  │arq:cognition│ │ arq:sensory │ │ arq:action  │ │arq:social │ │
│  │  (slow)     │ │  (fast)     │ │ (outbound)  │ │ (gossip)  │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └───────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                      WORKER PROCESS                             │
│                                                                 │
│  insight-worker (shared across all bots)                        │
│  - Polls queues for jobs                                        │
│  - Executes tasks with bot_name from payload                    │
│  - Writes results to databases                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Queue Types

| Queue | Purpose | Timeout | Examples |
|-------|---------|---------|----------|
| `arq:cognition` | Deep reasoning, slow LLM tasks | 5 min | Diary, Dream, Insight, Reflection |
| `arq:sensory` | Fast analysis | 30 sec | Fact extraction, Goal analysis, Preferences |
| `arq:action` | Outbound effects | 2 min | Image generation, Voice synthesis |
| `arq:social` | Inter-bot communication | 1 min | Gossip dispatch |

---

## All Background Tasks

### Cognition Queue (Slow, Deep Reasoning)

| Task | Trigger | What It Does |
|------|---------|--------------|
| `run_summarization` | Session hits 20+ messages | LLM summarizes conversation, saves to Qdrant + PostgreSQL |
| `run_insight_analysis` | Volume/time threshold | Detects patterns, generates epiphanies |
| `run_reflection` | Post-summarization | Analyzes user patterns across sessions |
| `run_diary_generation` | Scheduled (nightly) | Character writes diary entry about their day |
| `run_dream_generation` | Scheduled (nightly) | Character generates dream sequence |
| `run_drift_observation` | Scheduled | Monitors character behavior drift |

### Sensory Queue (Fast Analysis)

| Task | Trigger | What It Does |
|------|---------|--------------|
| `run_knowledge_extraction` | Every user message | Extracts facts to Neo4j |
| `run_preference_extraction` | Every user message | Detects style preferences ("be concise") |
| `run_goal_analysis` | After each response | Checks if interaction advances goals |
| `run_relationship_update` | After each response | Updates familiarity score in universe |
| `run_graph_enrichment` | Session threshold | Discovers implicit graph edges |

### Action Queue (Outbound Effects)

| Task | Trigger | What It Does |
|------|---------|--------------|
| `run_image_generation` | Image intent detected | Generates image via BFL/Replicate |
| `run_voice_generation` | Voice intent detected | Generates TTS via ElevenLabs |
| `run_posting` | Scheduled/proactive | Posts to Discord channels |

### Social Queue (Inter-Bot)

| Task | Trigger | What It Does |
|------|---------|--------------|
| `run_gossip_dispatch` | Significant event detected | Shares event with other bots |

---

## Task Queue API

### Enqueuing Tasks

```python
from src_v2.workers.task_queue import task_queue

# Basic enqueue
await task_queue.enqueue("run_summarization", 
    user_id=user_id,
    character_name=bot_name,
    session_id=session_id,
    messages=messages
)

# With delay (defer by 60 seconds)
await task_queue.enqueue("run_reflection",
    _defer_by=60,
    user_id=user_id,
    character_name=bot_name
)

# With job deduplication (prevents duplicate jobs)
await task_queue.enqueue("run_insight_analysis",
    _job_id=f"insight_{user_id}_{bot_name}",  # Same ID = skip if already queued
    user_id=user_id,
    character_name=bot_name
)

# To specific queue
await task_queue.enqueue("run_knowledge_extraction",
    _queue_name=task_queue.QUEUE_SENSORY,  # Fast queue
    user_id=user_id,
    message=content
)
```

### Convenience Methods

```python
# These handle queue routing and validation automatically:
await task_queue.enqueue_summarization(user_id, bot_name, session_id, messages)
await task_queue.enqueue_insight_analysis(user_id, bot_name, trigger="volume")
await task_queue.enqueue_knowledge_extraction(user_id, message, bot_name)
await task_queue.enqueue_goal_analysis(user_id, bot_name, interaction_text)
await task_queue.enqueue_gossip(event)
await task_queue.enqueue_graph_enrichment(session_id, user_id, channel_id, bot_name)
```

---

## Worker Configuration

### Starting Workers

```bash
# Start the shared insight-worker
./bot.sh start workers

# Or manually
arq src_v2.workers.worker.WorkerSettings
```

### Worker Settings

```python
# src_v2/workers/worker.py
class WorkerSettings:
    functions = [
        run_summarization,
        run_insight_analysis,
        run_reflection,
        run_knowledge_extraction,
        run_goal_analysis,
        run_gossip_dispatch,
        # ... all task functions
    ]
    
    redis_settings = TaskQueue.get_redis_settings()
    queue_name = TaskQueue.QUEUE_COGNITION
    max_jobs = 5           # Concurrent jobs
    job_timeout = 300      # 5 minute timeout
    keep_result = 3600     # Keep results for 1 hour
```

---

## Task Flow Examples

### Summarization Flow

```
User sends 20th message in session
         │
         ▼
┌─────────────────────────────────────┐
│  message_handler.py                 │
│  - Counts messages in session       │
│  - Threshold reached (20+)          │
│  - Enqueues summarization           │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Redis: arq:cognition queue         │
│  Job: run_summarization             │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Worker picks up job                │
│  1. Load messages from payload      │
│  2. Call SummaryGraphAgent          │
│  3. LLM generates summary           │
│  4. Score meaningfulness (1-5)      │
│  5. If >= 3, save to PostgreSQL     │
│  6. Embed and save to Qdrant        │
└─────────────────────────────────────┘
```

### Knowledge Extraction Flow

```
User message: "I work at Google as an engineer"
         │
         ▼
┌─────────────────────────────────────┐
│  Background learning pipeline       │
│  - Enqueue to SENSORY queue (fast)  │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Worker picks up job                │
│  1. LLM extracts facts              │
│  2. Creates Neo4j nodes/edges:      │
│     (User) -[:WORKS_AT]-> (Google)  │
│     (User) -[:HAS_ROLE]-> (Engineer)│
└─────────────────────────────────────┘
```

---

## Scheduled Tasks (Cron)

Some tasks run on a schedule rather than being triggered by events:

| Task | Schedule | What It Does |
|------|----------|--------------|
| Diary Generation | Nightly (configurable) | Each bot writes a diary entry |
| Dream Generation | Nightly (configurable) | Each bot generates a dream |
| Goal Strategist | Nightly | Analyzes goals and generates strategies |
| Graph Pruning | Weekly | Cleans up stale graph edges |
| Drift Observation | Daily | Monitors character behavior drift |

---

## Key Files

| File | Purpose |
|------|---------|
| `src_v2/workers/task_queue.py` | `TaskQueue` class — enqueue interface |
| `src_v2/workers/worker.py` | Worker configuration and settings |
| `src_v2/workers/tasks/*.py` | Task implementations |
| `src_v2/workers/strategist.py` | Goal strategist task |

### Task Implementation Files

| File | Tasks |
|------|-------|
| `summary_tasks.py` | `run_summarization` |
| `insight_tasks.py` | `run_insight_analysis` |
| `knowledge_tasks.py` | `run_knowledge_extraction` |
| `analysis_tasks.py` | `run_reflection`, `run_goal_analysis` |
| `diary_tasks.py` | `run_diary_generation` |
| `dream_tasks.py` | `run_dream_generation` |
| `social_tasks.py` | `run_gossip_dispatch`, `run_relationship_update` |
| `enrichment_tasks.py` | `run_graph_enrichment` |
| `action_tasks.py` | `run_image_generation`, `run_voice_generation` |
| `posting_tasks.py` | `run_posting` |

---

## Configuration

| Setting | Default | Purpose |
|---------|---------|---------|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `SUMMARY_MESSAGE_THRESHOLD` | 20 | Messages before summarization |
| `ENABLE_RUNTIME_FACT_EXTRACTION` | true | Enable fact extraction |
| `ENABLE_GOAL_STRATEGIST` | true | Enable nightly goal analysis |
| `ENABLE_CHARACTER_DIARY` | true | Enable diary generation |
| `ENABLE_DREAM_SEQUENCES` | true | Enable dream generation |

---

## Monitoring

### Check Queue Status

```bash
# Connect to Redis
redis-cli

# Check queue lengths
LLEN arq:cognition
LLEN arq:sensory
LLEN arq:action
LLEN arq:social

# Check pending jobs
KEYS arq:job:*
```

### Worker Logs

```bash
./bot.sh logs insight-worker -f
```

---

## Related Documentation

- [REF-017: Conversation Sessions](./REF-017-CONVERSATION_SESSIONS.md) — Summarization triggers
- [REF-018: Message Storage & Retrieval](./REF-018-MESSAGE_STORAGE_RETRIEVAL.md) — Database writes
- [REF-017-AGENTIC_QUEUE](./REF-017-AGENTIC_QUEUE.md) — Philosophy of queue-based agents
