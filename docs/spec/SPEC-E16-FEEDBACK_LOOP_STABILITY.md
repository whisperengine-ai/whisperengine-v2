# Feedback Loop Stability (Phase E16)

**Priority:** 🟢 High | **Time:** 1 day | **Complexity:** Low  
**Status:** ✅ Complete  
**Dependencies:** None (foundational observability)  
**Created:** November 30, 2025  
**Completed:** December 2025

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Emergence safety research |
| **Proposed by** | Mark + Claude (collaborative) |
| **Catalyst** | Recursive dream/diary loops needed guardrails |
| **Key insight** | "Observe first, constrain only what's proven problematic" |

---

## Overview

Add minimal safety mechanisms and observability for the recursive dream/diary feedback loops. The philosophy is **"observe first, constrain only what's proven problematic."**

This is NOT about preventing emergence - it's about having visibility into what's emerging and mathematical guardrails against edge cases.

---

## Background

WhisperEngine's dream/diary system creates recursive feedback loops:

```
User Conversation → Elena's Memory
        ↓
    Elena's Diary (processes memories)
        ↓
    Elena's Dream (processes diary)
        ↓
    Marcus reads Elena's diary (gossip)
        ↓
    Marcus's Diary (references Elena)
        ↓
    Elena's next Dream (may reference Marcus)
```

**The concern:** Information could amplify or degrade through cycles without visibility.

**The philosophy:** Cross-bot mythology is a *feature*. Shared references create narrative depth. We want to *observe* this, not *prevent* it.

---

## What We're Implementing

### Level 1: Minimal Safety Net (~1 day total)

| Feature | Effort | Purpose |
|---------|--------|---------|
| **Temporal Decay Scoring** | 2-3 hours | Old memories decay in influence |
| **Source Type Weights** | 1-2 hours | Direct observations weighted higher than gossip |
| **Narrative Source Metrics** | 1 hour | Track what feeds into dreams/diaries |
| **Drift Observation Metric** | 2-3 hours | Weekly personality consistency check |

### What We're NOT Implementing (Yet)

These are "break glass" protocols ready if observation shows problems:

| Feature | Trigger | Effort |
|---------|---------|--------|
| Epistemic Chain Tracking | Bot believes false info with high confidence | 10-12 days |
| Reality Check Worker | Collective delusion observed | 3-4 days |
| Symbol Validation | Characters lose distinctive symbolic language | 7-9 days |
| Personality Drift Correction | Drift metric >0.5 sustained | 7-9 days |

Full specs in: `docs/emergence_philosophy/03_FEEDBACK_LOOP_IMPLEMENTATION_PLAN.md`

---

## Implementation Details

### 1. Temporal Decay Scoring

**File:** `src_v2/memory/scoring.py` (NEW)

```python
from datetime import datetime, timezone
import math

DECAY_RATES = {
    "conversation": 0.98,  # Direct observations decay slowest
    "session_summary": 0.97,
    "diary": 0.95,
    "gossip": 0.93,
    "dream": 0.90,  # Abstract content decays fastest
}

def calculate_temporal_weight(memory: dict) -> float:
    """Calculate time-based weight for a memory."""
    created_at = datetime.fromisoformat(memory["created_at"])
    age_days = (datetime.now(timezone.utc) - created_at).days
    
    memory_type = memory.get("type", "conversation")
    decay_rate = DECAY_RATES.get(memory_type, 0.95)
    
    # Meaningfulness protection: high-meaning memories decay slower
    meaningfulness = memory.get("meaningfulness", 3)
    adjusted_decay = decay_rate + (0.01 * (meaningfulness - 3))
    adjusted_decay = min(0.99, max(0.85, adjusted_decay))
    
    return adjusted_decay ** age_days
```

**Integration:** Modify `MemoryManager.search_memories_advanced()` to re-rank results by `semantic_score * temporal_weight`.

---

### 2. Source Type Weights

**File:** `src_v2/memory/scoring.py`

```python
SOURCE_WEIGHTS = {
    "direct_conversation": 1.0,
    "session_summary": 0.9,
    "own_diary": 0.7,
    "own_dream": 0.5,
    "gossip": 0.4,
}

def calculate_composite_score(
    memory: dict,
    semantic_similarity: float
) -> float:
    """Combine temporal, semantic, and source type scores."""
    temporal = calculate_temporal_weight(memory)
    source = SOURCE_WEIGHTS.get(memory.get("type"), 0.5)
    
    return (
        semantic_similarity * 0.5 +
        temporal * 0.3 +
        source * 0.2
    )
```

---

### 3. Narrative Source Metrics

**File:** `src_v2/workers/tasks/diary_tasks.py` (modify)

After diary generation, log what sources were used:

```python
from influxdb_client.client.write.point import Point

# After gathering sources, before generation
point = Point("narrative_sources") \
    .tag("bot_name", character_name) \
    .tag("narrative_type", "diary") \
    .field("from_conversations", len(session_summaries)) \
    .field("from_gossip", len(gossip_memories)) \
    .field("from_dreams", len(dream_memories)) \
    .field("from_past_diaries", len(diary_memories)) \
    .field("total_sources", total_count)

if db_manager.influxdb_write_api:
    db_manager.influxdb_write_api.write(
        bucket=settings.INFLUXDB_BUCKET,
        record=point
    )
```

Same pattern for dream generation in `dream_tasks.py`.

---

### 4. Personality Drift Observation

**File:** `src_v2/workers/tasks/drift_observation.py` (NEW)

Weekly job that compares recent response embeddings to baseline:

```python
import numpy as np
from datetime import datetime, timedelta

async def observe_personality_drift(bot_name: str):
    """Compare recent responses to baseline embedding."""
    
    # Get baseline (first 100 responses, computed once)
    baseline = await get_or_create_baseline(bot_name)
    
    # Get recent responses (last 7 days)
    recent = await get_recent_responses(bot_name, days=7)
    
    if len(recent) < 10:
        return  # Not enough data
    
    # Compute average embedding of recent responses
    recent_embeddings = [await embed(r["content"]) for r in recent]
    recent_avg = np.mean(recent_embeddings, axis=0)
    
    # Cosine distance from baseline
    drift = 1 - np.dot(baseline, recent_avg) / (
        np.linalg.norm(baseline) * np.linalg.norm(recent_avg)
    )
    
    # Log to InfluxDB (observation only, no correction)
    point = Point("personality_drift") \
        .tag("bot_name", bot_name) \
        .field("drift_score", drift) \
        .field("sample_count", len(recent))
    
    # Alert if significant (but don't auto-correct)
    if drift > 0.3:
        logger.warning(f"Personality drift detected for {bot_name}: {drift:.3f}")
```

**Schedule:** Weekly via arq, not blocking any user interactions.

---

## Escalation Decision Tree

```
Observation Period (30 days)
    │
    ├─► narrative_sources metric
    │   └─► Are diaries >60% gossip-derived for 2+ weeks?
    │       ├─► YES → Review, consider source weight adjustment
    │       └─► NO → Keep observing
    │
    ├─► personality_drift metric
    │   └─► Is drift >0.3 sustained?
    │       ├─► YES → Review recent responses, consider prompt reinforcement
    │       └─► NO → Keep observing
    │
    └─► User feedback
        └─► Are users reporting "bot seems off"?
            ├─► YES → Manual review, targeted fix
            └─► NO → Keep observing
```

---

## Success Metrics

Track in InfluxDB/Grafana:

| Metric | Green | Yellow | Red |
|--------|-------|--------|-----|
| `narrative_sources.from_gossip` | <40% | 40-60% | >60% |
| `personality_drift` | <0.2 | 0.2-0.4 | >0.4 |
| `dream.purity_score` | >0.7 | 0.5-0.7 | <0.5 |

**Goal:** Stay in green zone through natural LLM self-regulation. Only intervene if red zone sustained for 2+ weeks.

---

## Files to Create/Modify

| File | Action | LOC | Status |
|------|--------|-----|--------|
| `src_v2/memory/scoring.py` | NEW | ~110 | ✅ Complete |
| `src_v2/workers/tasks/diary_tasks.py` | Add metrics logging | ~20 | ✅ Complete |
| `src_v2/workers/tasks/dream_tasks.py` | Add metrics logging | ~20 | ✅ Complete |
| `src_v2/workers/tasks/drift_observation.py` | NEW | ~300 | ✅ Complete |
| `src_v2/workers/tasks/cron_tasks.py` | Add weekly cron | ~70 | ✅ Complete |
| `src_v2/workers/worker.py` | Register cron job | ~10 | ✅ Complete |
| `src_v2/config/settings.py` | Add ENABLE_DRIFT_OBSERVATION | ~3 | ✅ Complete |
| `docker/grafana/dashboards/emergence.json` | NEW | ~100 | 📋 Deferred |

**Total Implemented:** ~530 LOC

**Note:** Memory manager search integration deferred - scoring.py provides the utilities, but the actual search re-ranking will be added when needed.

---

## What This Preserves

By NOT implementing heavy constraints:

- ✅ Cross-bot mythology can develop
- ✅ Characters can reference each other's dreams
- ✅ Shared symbolic language can emerge
- ✅ Surprise narrative connections can form
- ✅ Personalities can evolve (within bounds)

**The magic is in what we *don't* constrain.**

---

## Related Documents

- `docs/emergence_philosophy/` - Full Claude collaboration on this topic
- `docs/guide/GUIDE-015-AGENTIC_NARRATIVES.md` - DreamWeaver agent details
- `docs/roadmaps/AUTONOMOUS_SERVER_ACTIVITY.md` - Cross-bot interaction system

---

## Spec Origin

This feature emerged from a Claude-to-Claude architectural review. See `docs/emergence_philosophy/README.md` for the full conversation.
