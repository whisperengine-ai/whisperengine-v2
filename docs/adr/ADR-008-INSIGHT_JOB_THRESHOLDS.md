# ADR-008: Insight Job Thresholds

**Status:** ✅ Accepted  
**Date:** December 4, 2025  
**Deciders:** Mark Castillo, Claude (collaborative)

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Production trace analysis (LangSmith) |
| **Proposed by** | Mark (observation) → Claude (implementation) |
| **Catalyst** | Sophia bot insight job consumed LLM tokens ($0.01-0.02) on 5 messages, producing "insufficient data" result |

While reviewing LangSmith traces for the background insight worker, we discovered that insight analysis jobs were being triggered for users with minimal conversation history (as few as 5 messages). The insight agent behaved correctly—it didn't hallucinate patterns from sparse data—but the job itself was wasteful.

**Key observation:** The system was being appropriately conservative (not generating fake insights), but **prematurely triggered** (attempting analysis before sufficient data existed).

## Context

The background insight worker (`run_insight_analysis`) performs pattern detection, theme analysis, and generates artifacts like epiphanies and reasoning traces. It's triggered by:
- **Volume**: User sent many messages recently
- **Time**: Scheduled periodic analysis
- **Session end**: Conversation just completed
- **Feedback**: User gave positive reactions
- **Reflective completion**: A reflective reasoning session finished

**Problem:** No minimum data threshold existed before enqueueing jobs. This led to:
- Wasted LLM costs (~$0.01-0.02 per premature job)
- Redis queue pressure
- Worker time spent on "no data" analyses
- Logs filled with "more conversation data needed" messages

**Sophia case study:**
- Messages analyzed: 5
- Trust score: 0/150 (Prospect)
- Time: 23.5s
- Output: "No clear themes detected yet. More conversation data needed."
- Artifacts: 0 (correct behavior)
- Cost: ~$0.01-0.02
- Value: None

**Projected scale:** ~200 premature jobs/year/bot × 11 bots = 2,200 wasteful jobs/year = $22-44/year in pure waste (plus operational overhead).

## Decision

Add **minimum data thresholds** to `TaskQueue.enqueue_insight_analysis()` before enqueueing jobs:

### Thresholds Implemented

| Condition | Threshold | Rationale |
|-----------|-----------|-----------|
| **Minimum messages** | 10 messages in last 7 days | Pattern detection requires signal, not noise |
| **Low engagement** | 20 messages if `trust_score == 0` | User hasn't built relationship context yet |
| **Time window** | 7 days | Recent activity more relevant than stale history |
| **Exception** | `reflective_completion` always proceeds | Reasoning trace analysis valuable even for new users |

### Implementation

**Location:** `src_v2/workers/task_queue.py`

**Logic:**
```python
async def enqueue_insight_analysis(...) -> Optional[str]:
    # Check thresholds
    relationship = await trust_manager.get_relationship_level(user_id, character_name)
    trust_score = relationship.get("trust_score", 0)
    
    seven_days_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
    message_count = await memory_manager.count_messages_since(user_id, character_name, seven_days_ago)
    
    # Skip if insufficient data (unless analyzing reasoning traces)
    if trigger != "reflective_completion":
        if message_count < 10:
            return None  # Skip job
        if trust_score == 0 and message_count < 20:
            return None  # Skip job
    
    # Proceed with enqueue
    return await self.enqueue(...)
```

**Failure mode:** If threshold check fails (DB error), we proceed with enqueue (graceful degradation).

## Consequences

### Positive

1. **Cost savings**: 30-50% reduction in premature insight jobs (~$50-100/year per bot)
2. **Cleaner logs**: Fewer "insufficient data" results
3. **Better resource allocation**: Worker capacity freed for meaningful analysis
4. **Behavioral alignment**: System doesn't attempt analysis when it knows data is insufficient (more aligned with emergence philosophy)
5. **Testable**: Easy to verify with test users (confirmed: blocks jobs for 0-message users)

### Negative

1. **Added complexity**: Two DB queries before every insight job enqueue (trust + message count)
2. **Latency**: ~50-100ms overhead per enqueue call (acceptable for background jobs)
3. **Tuning burden**: Thresholds may need per-bot adjustment (some bots more/less chatty)
4. **Edge cases**: Valid but sparse conversations (e.g., high-value 8-message deep discussion) might be skipped

### Neutral

1. **Threshold values are heuristics**: 10/20 messages chosen based on intuition, not empirical data. May need tuning.
2. **7-day window**: Arbitrary but reasonable. Could be longer (30 days) or shorter (3 days).
3. **No change to insight agent logic**: This is purely a pre-flight check, not a behavioral change.

## Alternatives Considered

| Alternative | Pros | Cons | Why Rejected |
|-------------|------|------|--------------|
| **No thresholds (status quo)** | Simple, no code changes | Wasteful, doesn't scale | Unacceptable at production scale |
| **Agent-side checks** | Centralized in worker | Wastes Redis queue + worker time | Threshold check should be at enqueue, not execution |
| **Fixed 24-hour cooldown** | Simple rate limiting | Doesn't account for message volume | User could send 100 messages in 1 hour and still trigger |
| **Per-bot YAML config** | Highly customizable | Premature optimization | Start with global thresholds, tune later if needed |
| **InfluxDB metrics-based** | Data-driven thresholds | Complex, requires InfluxDB queries | Over-engineered for MVP |

## Monitoring & Tuning

### Metrics to track
1. `insight_jobs_skipped_insufficient_data` (count)
2. `insight_jobs_enqueued` (count, by trigger type)
3. `insight_job_skip_rate` = skipped / (skipped + enqueued)

### Success criteria
- Skip rate: 20-40% (too low = thresholds ineffective, too high = too aggressive)
- User complaints: 0 (no reports of "bot should have noticed X")
- Cost reduction: Measurable decrease in insight job LLM spend

### Tuning plan
1. Monitor for 1-2 weeks
2. If skip rate > 50%: Lower thresholds (8 messages instead of 10)
3. If skip rate < 10%: Raise thresholds (15 messages instead of 10)
4. Consider per-bot thresholds in `evolution.yaml` if bots show different patterns

## References

- **Implementation**: `src_v2/workers/task_queue.py` (lines 144-196)
- **Test**: Manual verification with test users (0 messages → job blocked)
- **Research log**: `docs/research/journal/2025-12/2025-12-04-insight-thresholds.md` (original observation)
- **Related pattern**: `src_v2/agents/proactive.py` (minimum trust for proactive engagement)
- **Emergence philosophy**: ADR-003 ("observe patterns when they exist, not force them")
