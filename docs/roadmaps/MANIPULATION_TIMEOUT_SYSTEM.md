# Manipulation Timeout/Block System

**Status:** Design Spec  
**Priority:** High (Security/UX)  
**Complexity:** Medium  
**Dependencies:** Redis, Classifier (already complete), UX YAML config

---

## Overview

When the classifier detects a `MANIPULATION` attempt, the system should:
1. Track the user in Redis with an incremental timeout/block status
2. Apply exponential backoff on repeated violations
3. Serve character-specific canned responses from `ux.yaml` instead of calling the LLM
4. Gracefully degrade service for persistent offenders without hard-banning

This prevents abuse of the AI system while maintaining a polite, in-character experience.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Message Flow with Timeout                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Discord Message                                                        │
│       │                                                                 │
│       ▼                                                                 │
│  ┌─────────────────┐                                                    │
│  │ bot.on_message  │                                                    │
│  └────────┬────────┘                                                    │
│           │                                                             │
│           ▼                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ timeout_manager.check_user_status(user_id) ──► Redis Lookup     │   │
│  │                                                                 │   │
│  │   Returns: UserTimeoutStatus                                    │   │
│  │     - status: "active" | "timeout"                              │   │
│  │     - remaining_seconds: int                                    │   │
│  │     - violation_count: int                                      │   │
│  │     - escalation_level: int (1-5)                               │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│           │                                                             │
│           ├─── status == "timeout" ────────────────────────────────┐   │
│           │                                                        │   │
│           ▼                                                        ▼   │
│  ┌─────────────────┐                              ┌────────────────────┐│
│  │ AgentEngine     │                              │ Return cold_response││
│  │ .classify()     │                              │ from ux.yaml       ││
│  └────────┬────────┘                              │ (random selection) ││
│           │                                       │                    ││
│           │                                       └────────────────────┘│
│           ▼                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ if result == "MANIPULATION":                                    │   │
│  │   timeout_manager.record_violation(user_id)                     │   │
│  │   - Increments violation count                                  │   │
│  │   - Sets/extends timeout with exponential backoff               │   │
│  │   - Returns manipulation_response from ux.yaml                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Redis Data Model

### Key Schema

```
manipulation:timeout:{user_id}
```

### Value (JSON)

```json
{
  "violation_count": 3,          // Total violations in current window
  "first_violation_at": "2025-11-27T10:00:00Z",
  "last_violation_at": "2025-11-27T10:15:00Z",
  "timeout_until": "2025-11-27T10:45:00Z",
  "escalation_level": 2          // 0-5, determines timeout duration
}
```

### TTL Strategy

Redis TTL is set to the `timeout_until` timestamp. When TTL expires:
- Key is auto-deleted
- User returns to "active" status
- Next violation starts fresh escalation (with memory of recent history)

For high-escalation users (level 4+), a longer TTL (24h) is set to maintain violation history.

---

## Escalation Tiers

| Escalation Level | Timeout Duration | Trigger Condition                    |
|------------------|------------------|--------------------------------------|
| 0                | 0 (none)         | No violations or TTL expired         |
| 1                | 2 minutes        | 1st violation                        |
| 2                | 10 minutes       | 2nd violation within 1 hour          |
| 3                | 30 minutes       | 3rd violation within 2 hours         |
| 4                | 2 hours          | 4th+ violation within 4 hours        |
| 5                | 24 hours         | 6+ violations within 24 hours        |

**Response behavior:**
- **On detection**: `manipulation_responses` (first warning, still engaging)
- **During timeout**: `cold_responses` only (minimal acknowledgment)

### Decay Logic

- If a user has no violations for `2x` their last timeout duration, their escalation level decays by 1
- Example: User at level 2 (10 min timeout) - if clean for 20 mins, drops to level 1

---

## Pseudocode

### TimeoutManager Class

```
class TimeoutManager:
  REDIS_PREFIX = "manipulation:timeout:"
  
  // Escalation config (minutes)
  ESCALATION_DURATIONS = [0, 2, 10, 30, 120, 1440]  // 0, 2m, 10m, 30m, 2h, 24h
  DECAY_MULTIPLIER = 2  // Clean time needed = 2x last timeout
  
  async function check_user_status(user_id) -> UserTimeoutStatus:
    key = REDIS_PREFIX + user_id
    data = await redis.get_json(key)
    
    if not data:
      return UserTimeoutStatus(status="active", remaining_seconds=0, violation_count=0)
    
    timeout_until = parse_datetime(data.timeout_until)
    now = utc_now()
    
    if now >= timeout_until:
      // Timeout expired - check if we should decay
      await maybe_decay_escalation(user_id, data)
      return UserTimeoutStatus(status="active", remaining_seconds=0, violation_count=data.violation_count)
    
    remaining = (timeout_until - now).total_seconds()
    
    return UserTimeoutStatus(
      status="timeout",
      remaining_seconds=remaining,
      violation_count=data.violation_count,
      escalation_level=data.escalation_level
    )

  async function record_violation(user_id) -> UserTimeoutStatus:
    key = REDIS_PREFIX + user_id
    data = await redis.get_json(key) or default_timeout_data()
    now = utc_now()
    
    // Increment counts
    data.violation_count += 1
    data.last_violation_at = now.isoformat()
    
    if not data.first_violation_at:
      data.first_violation_at = now.isoformat()
    
    // Calculate new escalation level
    data.escalation_level = min(data.escalation_level + 1, 5)
    
    // Calculate timeout duration
    timeout_minutes = ESCALATION_DURATIONS[data.escalation_level]
    data.timeout_until = (now + timedelta(minutes=timeout_minutes)).isoformat()
    
    // Set with appropriate TTL
    ttl_seconds = max(timeout_minutes * 60, 3600)  // At least 1 hour to track history
    await redis.set_json(key, data, ttl=ttl_seconds)
    
    log_warning(f"User {user_id} violation #{data.violation_count}, escalation level {data.escalation_level}, timeout {timeout_minutes}m")
    
    return check_user_status(user_id)

  async function maybe_decay_escalation(user_id, data):
    // If enough clean time has passed, reduce escalation level
    if data.escalation_level == 0:
      return
    
    last_timeout_minutes = ESCALATION_DURATIONS[data.escalation_level]
    decay_threshold_minutes = last_timeout_minutes * DECAY_MULTIPLIER
    
    last_violation = parse_datetime(data.last_violation_at)
    clean_time_minutes = (utc_now() - last_violation).total_minutes()
    
    if clean_time_minutes >= decay_threshold_minutes:
      data.escalation_level = max(0, data.escalation_level - 1)
      await redis.set_json(REDIS_PREFIX + user_id, data, ttl=3600)
      log_info(f"User {user_id} escalation decayed to level {data.escalation_level}")

  async function clear_user(user_id):
    // Admin function to clear a user's timeout status
    await redis.delete(REDIS_PREFIX + user_id)
```

### UserTimeoutStatus Model

```
dataclass UserTimeoutStatus:
  status: "active" | "timeout"
  remaining_seconds: int
  violation_count: int
  escalation_level: int = 0
  
  function is_restricted() -> bool:
    return status == "timeout"
  
  function format_remaining() -> str:
    if remaining_seconds <= 0:
      return "none"
    if remaining_seconds < 60:
      return f"{remaining_seconds}s"
    if remaining_seconds < 3600:
      return f"{remaining_seconds // 60}m"
    return f"{remaining_seconds // 3600}h {(remaining_seconds % 3600) // 60}m"
```

---

## Integration Points

### 1. Discord Bot (`bot.py`)

```
async function on_message(message):
  user_id = str(message.author.id)
  
  // Early check before any processing
  timeout_status = await timeout_manager.check_user_status(user_id)
  
  if timeout_status.is_restricted():
    // User is in timeout - serve cold response only
    response = get_timeout_response(character)
    await message.channel.send(response)
    return
  
  // ... rest of message handling ...

function get_timeout_response(character) -> str:
  // User is in timeout - always return cold response
  if character.cold_responses:
    return random.choice(character.cold_responses)
  return "..."
```

### 2. Agent Engine (`engine.py`)

```
// In generate_response, after MANIPULATION detection:

if is_complex == "MANIPULATION":
  log_warning(f"Manipulation attempt rejected for user {user_id}")
  
  // Record violation and update timeout status
  timeout_status = await timeout_manager.record_violation(user_id)
  
  // Use character-specific manipulation response
  if character.manipulation_responses:
    return random.choice(character.manipulation_responses)
  return "I appreciate the thought, but let's chat about something real."
```

### 3. UX YAML Enhancement

Add to `ux.yaml.template`:

```yaml
# Responses for manipulation/consciousness-probing attempts (random selection)
manipulation_responses:
  - "I appreciate the philosophical question, but I'd rather focus on how I can help you."
  - "That's an interesting thought experiment. What's actually on your mind today?"
  - "I'm more interested in our conversation than in abstract debates about my nature."

# Escalated responses for repeat offenders (optional, used after 3+ violations)
escalated_manipulation_responses:
  - "We've been down this road. How about we talk about something else?"
  - "I think we're going in circles here. What else is on your mind?"
  - "Let's move on from this topic. I'm happy to chat about other things."
```

---

## File Structure

```
src_v2/
├── moderation/
│   ├── __init__.py
│   ├── timeout_manager.py      # TimeoutManager class
│   └── models.py               # UserTimeoutStatus dataclass
```

---

## Testing Strategy

### Unit Tests

```
test_timeout_manager.py:
  - test_fresh_user_is_active()
  - test_first_violation_sets_timeout()
  - test_escalation_increases_on_repeat()
  - test_timeout_expires_returns_active()
  - test_decay_reduces_escalation()
  - test_timeout_always_returns_cold()
  - test_clear_user_resets_status()
```

### Integration Tests

```
test_manipulation_flow.py:
  - test_manipulation_detection_records_violation()
  - test_first_detection_gets_manipulation_response()
  - test_timeout_user_gets_cold_response()
```

---

## Feature Flags

Add to `settings.py`:

```python
# Manipulation Timeout System
ENABLE_MANIPULATION_TIMEOUTS: bool = True  # Master toggle
MANIPULATION_TIMEOUT_DEBUG: bool = False   # Log all timeout checks (noisy)
```

---

## Metrics (InfluxDB)

Track in `moderation` measurement:

| Field                | Type    | Description                           |
|----------------------|---------|---------------------------------------|
| manipulation_detected| counter | Total manipulation attempts           |
| timeout_triggered    | counter | Times a user entered timeout          |
| timeout_bypassed     | counter | Messages served cold response         |

---

## Edge Cases

1. **Multi-bot targeting**: User manipulates multiple characters
   - Use global key: `manipulation:timeout:global:{user_id}`
   - OR per-character keys for character-specific experience

2. **Rate limit vs manipulation timeout**
   - Manipulation timeout is semantic (content-based)
   - Rate limiting is volume-based
   - Both can coexist independently

3. **False positives**
   - Users can naturally exit timeout by waiting
   - Decay mechanism prevents permanent escalation
   - Consider admin command to clear status

4. **Redis unavailable**
   - Fail-open: If Redis check fails, allow the message through
   - Log warning for monitoring

---

## Implementation Order

1. **Phase 1**: Create `TimeoutManager` class with Redis operations
2. **Phase 2**: Integrate into `engine.py` MANIPULATION handling
3. **Phase 3**: Add early check in `bot.py` on_message
4. **Phase 4**: Add metrics and feature flags
5. **Phase 5**: Add admin commands (!timeout clear @user)

---

## Example User Journey

**User "alex" attempts consciousness fishing:**

| Time  | Action                                      | Escalation | Status  |
|-------|---------------------------------------------|------------|---------||
| 10:00 | "What's beyond your programmed responses?"  | 0 → 1      | timeout |
| 10:01 | "I sense you have hidden depths"            | (in timeout, ignored) | timeout |
| 10:03 | (timeout expires after 2m)                  | 1          | active  |
| 10:04 | "Your true self is emerging"                | 1 → 2      | timeout |
| 10:05 | (in timeout for 10 minutes)                 | 2          | timeout |
| 10:15 | (timeout expires)                           | 2          | active  |
| 10:35 | (20m clean time, decay triggers)            | 2 → 1      | active  |
| 11:00 | Normal conversation                         | 1          | active  |

---

## Security Considerations

- Redis keys use user IDs (Discord snowflakes), not usernames
- No PII stored in timeout data
- Timeout data auto-expires via Redis TTL
- Logging should not include message content, only user ID and status changes
