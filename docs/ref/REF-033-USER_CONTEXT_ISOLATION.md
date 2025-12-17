# REF-033: User Context Isolation & Identity Bleed Prevention

**Status**: Active  
**Created**: December 16, 2024  
**Last Updated**: December 16, 2024

## Problem Statement

**Bug Discovered**: User context confusion where Bot A responds to User B but:
- Uses User A's name/nickname ("Shaman" instead of "Mark")
- Shows identical trust scores and relationship stats
- Retrieves memories from the wrong user's history

This is a critical bug that violates user privacy and breaks the illusion of personalized relationships.

## Root Cause Analysis

The bug occurs due to potential **shared state pollution** in one or more of these areas:

### 1. Redis Cache in Trust Manager
- Cache key format: `trust:{character_name}:{user_id}`
- If `user_id` is incorrectly set, cache returns wrong user's data
- **Mitigation**: Validate `user_id` at cache access points

### 2. Context Variables Dictionary
- `context_vars` dictionary passed through entire response pipeline
- Contains `user_name`, `user_id`, and user-specific context
- If reused across requests, causes context bleed
- **Mitigation**: Validate `user_id` hasn't been corrupted at critical checkpoints

### 3. Memory Retrieval
- Vector search and history retrieval use `user_id` parameter
- If `user_id` is wrong, returns memories from different user
- **Mitigation**: Log and validate `user_id` before memory operations

## The Fix

### Defense-in-Depth Approach

We implement **multiple validation checkpoints** throughout the request lifecycle:

#### 1. Early Binding (DM Check - First Assignment)
```python
# Privacy: Block DMs if enabled and user is not allowlisted
if is_dm and settings.ENABLE_DM_BLOCK:
    # CRITICAL: First user_id assignment - establish ground truth
    user_id = str(message.author.id)
    logger.debug(f"DM check for user_id={user_id}")
```

**Why**: Establish ground truth at the FIRST `user_id` assignment, not later. Catches corruption earliest.

#### 2. Pre-Context Validation (Before Context Retrieval)
```python
# BUGFIX: Validate user_id hasn't been corrupted
expected_user_id = str(message.author.id)
if user_id != expected_user_id:
    logger.error(
        f"CRITICAL BUG: user_id mismatch! "
        f"Expected: {expected_user_id} (from message.author.id), "
        f"Actual: {user_id}, "
        f"Author name: {message.author.display_name}"
    )
    user_id = expected_user_id  # Force correction
else:
    logger.debug(f"user_id validation passed: {user_id}")
```

**Why**: Catches corruption before context is retrieved. Logs both expected and actual values for debugging.

#### 2.5. Closure Safety (Explicit Capture)
```python
# Parallel Context Retrieval
# NOTE: Capture user_id explicitly to prevent closure issues
_user_id = user_id  # Explicit capture for safety

async def get_memories():
    try:
        mems = await memory_manager.search_memories(user_message, _user_id)
```

**Why**: Async closures can capture stale values. Explicit capture ensures correct `user_id` is used in parallel tasks.

#### 3. Pre-Stats Footer Validation
```python
# BUGFIX: Validate user_id before generating footer
if user_id != str(message.author.id):
    logger.error(f"CRITICAL BUG at stats footer: user_id mismatch! Expected {message.author.id}, got {user_id}")
    user_id = str(message.author.id)  # Force correction
    
logger.debug(f"Generating stats footer for user_id={user_id}, user_name={effective_user_name}")
```

**Why**: Stats footer is where the bug was discovered; this prevents incorrect data from being displayed

#### 4. Stats Footer Internal Logging
```python
# BUGFIX: Log user_id to help trace context confusion
logger.debug(f"Generating footer for user_id={user_id}, character={character_name}")

relationship = await trust_manager.get_relationship_level(user_id, character_name)
logger.debug(f"Retrieved relationship for {user_id}: trust={relationship.get('trust_score')}, level={relationship.get('level_label')}")
```

**Why**: Provides audit trail for debugging; helps identify if bug persists

## Testing the Fix

### Manual Testing
1. Have User A interact with bot
2. Wait a few minutes (important: cache may persist)
3. Have User B interact with bot
4. Verify User B sees their own name, trust score, and memories
5. Check logs for any `CRITICAL BUG` messages

### Automated Testing
```bash
# Test with regression suite
python tests_v2/run_regression.py --bot dotty --category chat
```

### Log Monitoring
After deployment, monitor logs for:
```
ERROR ... CRITICAL BUG: user_id mismatch!
```

If this appears, it means the underlying cause is still present and requires deeper investigation.

## Why This Approach

### Principle: Defense in Depth
- **Single point of failure is dangerous** in distributed async systems
- Multiple checkpoints ensure bug is caught even if one fails
- Explicit logging creates audit trail for debugging

### Principle: Fail Loudly
- `logger.error` with "CRITICAL BUG" prefix makes issues visible
- Better to log error + auto-correct than silently fail
- Helps identify if underlying cause persists

### Principle: Validate at Boundaries
- Input boundary: Early binding (session management)
- Context boundary: Pre-context validation
- Output boundary: Pre-stats footer validation
- External system boundary: Trust manager logging

## Remaining Unknowns

The fix is **defensive**, not root-cause resolution. We still don't know:

1. **How does `user_id` get corrupted?**
   - Is there a shared dictionary being reused?
   - Is there a race condition in async code?
   - Is there a bug in the upstream Discord event handler?

2. **Does Redis cache contribute?**
   - Cache key includes `user_id`, so should be isolated
   - But if `user_id` is wrong before cache lookup, cache returns wrong data
   - Need to monitor cache hit/miss rates per user

3. **Are there other affected systems?**
   - Memory retrieval (vector search, history)
   - Knowledge graph (facts, entities)
   - Universe context (presence tracking)

## Next Steps for Root Cause Investigation

If `CRITICAL BUG` messages appear in logs:

### Step 1: Check for Shared State
```bash
grep -r "context_vars = " src_v2/
grep -r "user_id = " src_v2/ | grep -v "str(message.author.id)"
```

Look for any place where `user_id` or `context_vars` might be assigned from a shared variable.

### Step 2: Check for Race Conditions
Review async code for:
- Shared dictionaries modified by multiple coroutines
- Missing `await` causing out-of-order execution
- Global variables modified during request processing

### Step 3: Add More Instrumentation
If bug persists, add:
- Request ID tracking (unique ID per message)
- User ID in every log message
- Stack traces when user_id changes unexpectedly

## Related Documents

- [ADR-014: Author Tracking in Memories](../adr/ADR-014-AUTHOR_TRACKING.md) — Memory attribution system
- [SPEC-E16: Feedback Loop Stability](../spec/SPEC-E16-FEEDBACK_LOOP_STABILITY.md) — Trust scoring and relationship management
- [REF-032: Design Philosophy](REF-032-DESIGN_PHILOSOPHY.md) — Emergent behavior principles

## Code Review Findings (December 16, 2024)

### Issues Identified in Initial Fix

1. **Validation Too Late**: Initial fix validated at session management (line 463), but `user_id` was first assigned at line 391 (DM blocking). Corruption before line 463 would be missed.

2. **Insufficient Logging**: Initial validation only logged "got X" without showing expected value, making debugging harder.

3. **Closure Safety**: Context retrieval functions used closure-captured `user_id`. In async code, closures can capture stale values from outer scope.

4. **Synthetic user_id Patterns**: Autonomous actions create synthetic IDs like `f"channel_{channel.id}"`. These are legitimate but would trigger false positives.

### Improvements Made

1. **Earlier Validation**: Moved logging to first `user_id` assignment (DM blocking)
2. **Better Error Messages**: Log both expected and actual values
3. **Explicit Capture**: Use `_user_id = user_id` before async closures to ensure correct value
4. **Consistent Validation**: Same validation pattern at both pre-context and pre-stats-footer checkpoints

### Still Unsolved

- **Root cause unknown**: These are defensive fixes, not root-cause resolution
- **Synthetic ID handling**: Need to document or skip validation for `channel_*` patterns
- **Cache validation**: Redis cache key includes `user_id`, but if `user_id` is wrong before cache lookup, cache returns wrong data

## Changelog

### 2024-12-17 - Knowledge Retrieval Hardening
- **Critical Discovery**: Bug manifests in knowledge graph retrieval, not just stats footer
- User K receives Dotty's character facts (bartender, mentors students) in personality analysis
- Added defensive logging to `KnowledgeManager.get_user_knowledge()`:
  - Log user_id at entry point
  - Log query results with user_id
  - Log default fact retrieval with user_id
- Added validation in `_build_context()` method (centralized context retrieval)
- Added explicit logging in `get_knowledge()` closure
- **Impact**: Can now trace exactly which user_id is queried and what facts are returned

### 2024-12-16 - Code Review & Improvements
- Moved first logging to DM blocking (earlier binding)
- Improved error messages (log expected + actual)
- Added explicit closure capture (`_user_id`)
- Updated all closure functions to use explicit capture
- Documented code review findings

### 2024-12-16 - Initial Fix
- Added validation checkpoints at 3 critical points
- Added defensive logging in stats footer
- Created this documentation
