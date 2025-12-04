# User Timezone Support

**Phase:** E7  
**Priority:** Low  
**Estimated Time:** 1-2 days  
**Complexity:** Low  
**Status:** ✅ Complete

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | User experience issue |
| **Proposed by** | Mark (operational observation) |
| **Catalyst** | Diary generation at 4 AM UTC was wrong for most users |
| **Key insight** | Time-based features should respect user timezones |

---

## Problem Statement

The system currently operates entirely in UTC. This creates suboptimal experiences:

1. **Diary Generation:** Runs at 4 AM UTC for everyone. A user in PST (UTC-8) gets their character's diary generated at 8 PM their local time (previous day).

2. **Dream Timing:** While dreams trigger on inactivity (not time-of-day), the "last night I had a dream about you" framing feels off if it's 2 PM for the user.

3. **Temporal References:** Characters can't accurately reference time ("good morning", "it's late for you") without knowing user timezone.

---

## Proposed Solution

### 1. Store User Timezone

Add `timezone` to the user preferences JSONB in `v2_user_relationships`:

```python
# In v2_user_relationships.preferences
{
    "verbosity": "medium",
    "style": "casual",
    "timezone": "America/Los_Angeles"  # NEW: IANA timezone string
}
```

### 2. Slash Command to Set Timezone

```
/timezone America/New_York
/timezone auto  # Uses Discord locale hint if available
/timezone       # Shows current timezone
```

Implementation in `src_v2/discord/commands.py`:

```
function handle_timezone_command(user_id, tz_input):
    if tz_input == "auto":
        tz = detect_from_discord_locale(user) or "UTC"
    else:
        tz = validate_iana_timezone(tz_input)
    
    if not tz:
        return "Invalid timezone. Use IANA format (e.g., America/New_York)"
    
    update_user_preference(user_id, "timezone", tz)
    return f"Timezone set to {tz}"
```

### 3. Timezone-Aware Context Injection

#### Diary Context

```
function get_diary_context(char_name, user_id):
    diary = get_latest_diary(char_name)
    if not diary:
        return ""
    
    user_tz = get_user_timezone(user_id) or "UTC"
    user_now = now_in_timezone(user_tz)
    diary_date = diary.created_at.astimezone(user_tz)
    
    if same_day(user_now, diary_date):
        prefix = "From my thoughts earlier today"
    elif is_yesterday(user_now, diary_date):
        prefix = "From my diary last night"
    else:
        prefix = f"From my diary on {format_date(diary_date)}"
    
    return format_diary_with_prefix(diary, prefix)
```

#### Dream Context

```
function get_dream_context(user_id, char_name):
    user_tz = get_user_timezone(user_id) or "UTC"
    user_hour = get_hour_in_timezone(user_tz)
    
    # Only share dreams if it's "morning" for the user (6 AM - 12 PM)
    if not (6 <= user_hour < 12):
        return ""  # Save dream for later
    
    // ... rest of dream generation logic
```

#### Greeting Context

```
function get_time_of_day_context(user_id):
    user_tz = get_user_timezone(user_id)
    if not user_tz:
        return ""  # Don't guess, just omit
    
    hour = get_hour_in_timezone(user_tz)
    
    if 5 <= hour < 12:
        return "[TIME CONTEXT] It's morning for the user."
    elif 12 <= hour < 17:
        return "[TIME CONTEXT] It's afternoon for the user."
    elif 17 <= hour < 21:
        return "[TIME CONTEXT] It's evening for the user."
    else:
        return "[TIME CONTEXT] It's late night for the user."
```

---

## Implementation Plan

### Step 1: Preference Storage (30 min)
- No migration needed (JSONB is schemaless)
- Add helper methods to `TrustManager`:
  - `get_user_timezone(user_id) -> Optional[str]`
  - `set_user_timezone(user_id, timezone: str)`

### Step 2: Slash Command (1 hour)
- Add `/timezone` command to `src_v2/discord/commands.py`
- Validate IANA timezone strings using `zoneinfo` (Python 3.9+)
- Support common aliases: "PST" → "America/Los_Angeles", "EST" → "America/New_York"

### Step 3: Context Injection Updates (2 hours)
- Update `_get_diary_context()` in `engine.py`
- Update `_get_dream_context()` in `engine.py`
- Add optional `_get_time_of_day_context()` for greetings

### Step 4: Testing (1 hour)
- Unit tests for timezone conversion
- Integration test with mock timezones

---

## Files to Modify

| File | Changes |
|------|---------|
| `src_v2/evolution/trust.py` | Add `get_user_timezone()`, `set_user_timezone()` |
| `src_v2/discord/commands.py` | Add `/timezone` slash command |
| `src_v2/agents/engine.py` | Update `_get_diary_context()`, `_get_dream_context()` |
| `src_v2/memory/diary.py` | Update `format_diary_context()` to accept user timezone |
| `src_v2/memory/dreams.py` | Update `format_dream_context()` for time-appropriate framing |

---

## Feature Flags

```python
# settings.py
ENABLE_USER_TIMEZONE: bool = True  # Enable timezone-aware features
```

---

## Cost Model

- **Storage:** Negligible (~20 bytes per user in JSONB)
- **Compute:** Negligible (timezone conversion is O(1))
- **LLM:** $0 (no additional LLM calls)

---

## Why Low Priority?

1. **Roleplay context:** Characters exist in fictional time; exact user timezone may not matter for immersion
2. **Current system works:** UTC-based diary/dreams function correctly
3. **Optional enhancement:** Nice-to-have for personalization, not critical for core experience
4. **User friction:** Requires users to explicitly set timezone

---

## Alternatives Considered

### A. Infer from Activity Patterns
- Track when users are most active
- Estimate timezone from message timestamps
- **Rejected:** Privacy concerns, unreliable for irregular users

### B. Per-Character Diary Timing
- Each character generates diary at different UTC hours
- Spreads load, gives timezone-like variety
- **Rejected:** Doesn't solve the core problem

### C. Keep UTC, Adjust Framing
- Never mention specific times in diary/dream context
- Use vague framing: "recently", "the other day"
- **Partial solution:** Implemented as fallback when timezone unknown

---

## Dependencies

- None (uses existing JSONB preferences infrastructure)

---

## Success Metrics

- Adoption rate of `/timezone` command
- Reduction in "wrong time" feedback (if tracked)
- User satisfaction with temporal references

---

**Created:** November 28, 2025  
**Author:** AI Assistant  
**Related Phases:** E2 (Diary), E3 (Dreams)
