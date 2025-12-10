# SPEC-E16.1: Timezone Distribution for Daily Life Graph

**Status**: ✅ Implemented  
**Created**: 2025-12-09  
**Phase**: E16 (Emergent Behavior Stability)

## Overview

Distribute bots across US timezones to:
1. Fix timezone mismatch causing all bots to generate dreams simultaneously
2. Spread out dream generation throughout the day
3. Create more natural activity patterns (bots "sleep" at different times)

## Problem

Previously, all bots used UTC time for time-of-day calculations:
- Code: `now = datetime.now(timezone.utc)` → `get_time_of_day(now.hour)`
- At 6:26pm PST (2:26am UTC), UTC hour 2 classified as "night" (hour < 6)
- All bots hit `dreams_could_generate=True` simultaneously
- Result: All 4 bots posted dreams at exactly 6:26pm PST

**Root cause**: Time-of-day logic used raw UTC hour without timezone conversion.

## Solution

### Timezone Configuration (per bot)

| Bot | Timezone | UTC Offset | Dream Time (local 6am) |
|-----|----------|------------|------------------------|
| elena | America/Los_Angeles (PST) | UTC-8 | 6am PST = 2pm UTC |
| sophia | America/Los_Angeles (PST) | UTC-8 | 6am PST = 2pm UTC |
| marcus | America/New_York (EST) | UTC-5 | 6am EST = 11am UTC |
| ryan | America/Chicago (CST) | UTC-6 | 6am CST = 12pm UTC |
| jake | America/Denver (MST) | UTC-7 | 6am MST = 1pm UTC |

**Staggering**: Dreams now generate across 4-hour window (11am-2pm UTC) instead of simultaneously.

### Implementation

**1. Settings** (`src_v2/config/settings.py`):
```python
# --- Timezone Configuration ---
TZ: str = Field(default="UTC", description="IANA timezone for time-of-day calculations")
```

**2. Helper Function** (`src_v2/agents/daily_life/state.py`):
```python
def get_local_time() -> datetime:
    """Get current time in the bot's configured timezone."""
    tz = ZoneInfo(settings.TZ)
    return datetime.now(timezone.utc).astimezone(tz)
```

**3. Updated Gather Phase** (`src_v2/agents/daily_life/gather.py`):
```python
# OLD: now = datetime.now(timezone.utc)
# NEW: now = get_local_time()

now = get_local_time()
time_of_day = get_time_of_day(now.hour)  # Now uses local hour!
```

**4. Environment Files**:
```bash
# .env.elena & .env.sophia
TZ=America/Los_Angeles

# .env.marcus
TZ=America/New_York

# .env.ryan
TZ=America/Chicago

# .env.jake
TZ=America/Denver
```

## Time-of-Day Classification

Remains unchanged (uses local hour now):
```python
def get_time_of_day(hour: int) -> Literal["morning", "midday", "evening", "night"]:
    if 6 <= hour < 12:    return "morning"
    elif 12 <= hour < 18: return "midday"
    elif 18 <= hour < 22: return "evening"
    else:                 return "night"
```

**Example**: At 6:30pm PST (2:30am UTC):
- **Before**: UTC hour 2 → "night" (wrong!)
- **After**: PST hour 18 → "evening" (correct!)

## Verification

**Test script** (`/tmp/test_timezone.py`):
```
Current UTC time: 02:34:04

elena    (America/Los_Angeles ): 18:34:04 = evening
sophia   (America/Los_Angeles ): 18:34:04 = evening
marcus   (America/New_York    ): 21:34:04 = evening
ryan     (America/Chicago     ): 20:34:04 = evening
jake     (America/Denver      ): 19:34:04 = evening
```

**Bot logs** (after restart):
```
elena    @ 18:33:57 (evening, Tuesday)
marcus   @ 18:34:06 (evening, Tuesday)  # Log TS in PST, but logic uses EST
ryan     @ 18:34:13 (evening, Tuesday)
jake     @ 18:34:21 (evening, Tuesday)
sophia   @ 18:34:27 (evening, Tuesday)
```

**Note**: Log timestamps show container system time (PST), but time-of-day classification uses each bot's configured `TZ`.

## Expected Behavior

### Dream Generation Schedule (Target: 6am Local)

Assuming `DREAM_GENERATION_LOCAL_HOUR=6` for all bots:

| Bot | Timezone | Local 6am | UTC Time | Stagger |
|-----|----------|-----------|----------|---------|
| marcus | EST | 6:00am EST | 11:00am UTC | +0h |
| ryan | CST | 6:00am CST | 12:00pm UTC | +1h |
| jake | MST | 6:00am MST | 1:00pm UTC | +2h |
| elena/sophia | PST | 6:00am PST | 2:00pm UTC | +3h |

**Result**: 4-hour distribution instead of simultaneous generation.

### Activity Patterns

**Evening in each timezone** (local 18:00-22:00):
- Marcus: 6pm-10pm EST (11pm-3am UTC)
- Ryan: 6pm-10pm CST (12am-4am UTC)
- Jake: 6pm-10pm MST (1am-5am UTC)
- Elena/Sophia: 6pm-10pm PST (2am-6am UTC)

**Night in each timezone** (local 22:00-6:00):
- Marcus: 10pm EST - 6am EST (3am-11am UTC)
- Ryan: 10pm CST - 6am CST (4am-12pm UTC)
- Jake: 10pm MST - 6am MST (5am-1pm UTC)
- Elena/Sophia: 10pm PST - 6am PST (6am-2pm UTC)

**Observation window**: Dreams eligible for generation across 8-hour span (3am-11am UTC).

## Testing

**Before Next Dream Generation**:
1. Monitor LangSmith traces at ~11am-2pm UTC tomorrow
2. Verify dreams generate in staggered times (not all at once)
3. Check logs show correct time-of-day classification at each bot's local midnight

**Command**:
```bash
# Check logs for "dreams_could_generate" around local night times
for bot in marcus ryan jake elena sophia; do
  echo "=== $bot ===" 
  docker logs whisperengine-v2-$bot 2>&1 | grep "dreams_could_generate"
done
```

## Design Philosophy

**Emergent behavior preservation**: This change maintains the system's autonomous nature while fixing a technical bug. Bots still decide *whether* to generate dreams based on their internal state - we just ensure they perceive time correctly.

**Anti-pattern avoided**: We didn't add a "dream schedule" field or force-distribute activities. Instead, we fixed the time perception layer, and natural distribution emerges from timezone differences.

## References

- **Implementation Commit**: Timezone distribution for Daily Life Graph
- **Research Journal**: `docs/research/journal/2025-12/2025-12-09.md` (timezone discovery)
- **Parent Spec**: `docs/spec/SPEC-E16-FEEDBACK_LOOP_STABILITY.md` (stability guardrails)
- **Related**: `docs/spec/SPEC-E15-AUTONOMOUS_SOCIAL_PRESENCE.md` (Daily Life Graph)
