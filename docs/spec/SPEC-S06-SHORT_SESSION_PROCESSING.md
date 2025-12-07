# SPEC-S06: Session Timeout Processing

**Document Version:** 3.0  
**Created:** December 7, 2025  
**Updated:** December 7, 2025  
**Status:** 📋 Proposed  
**Priority:** 🟡 Medium  
**Dependencies:** PostgreSQL, arq task queue

> ✅ **Emergence Check:** Short conversations are still conversations. A user saying "I'm Alex" in 1 message contains the same signal as in 20 messages—we shouldn't lose that data.

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Documentation review → Architecture discussion |
| **Proposed by** | Mark + Claude (collaborative) |
| **Catalyst** | Reviewing GUIDE-003-GOALS.md revealed gap in goal analysis triggers |
| **Key insight** | Simple cron beats complex event-driven for non-user-facing background processing |
| **Decision factors** | Simplicity, maintainability, "good enough" latency for analytics |

---

## Executive Summary

Currently, post-conversation processing (goal analysis, knowledge extraction, preference extraction) only runs when:
1. Message count ≥ 20 (`SUMMARY_MESSAGE_THRESHOLD`), OR
2. Cross-bot chain ends with `force_processing=True`

**Problem:** Short human conversations (< 20 messages) that timeout are never processed. Session timeout is detected lazily (only when user returns), so processing never triggers.

**Solution:** A single cron job that proactively closes stale sessions and triggers processing. Simple, reliable, and sufficient for non-user-facing background work.

---

## Problem Statement

### Current State

```
User sends 5 messages → Bot responds 5 times → User leaves
                                    ↓
                    (30 min inactivity)
                                    ↓
            User returns → get_active_session() → "Session timed out!"
                                    ↓
                    Session closed (is_active = FALSE)
                                    ↓
                    New session created
                                    ↓
                    ⚠️ Old session: NO processing ever ran
```

**What's lost:**
- Goal progress detection (e.g., `learn_name` if user shared name)
- Knowledge extraction (facts about user)
- Preference extraction (communication style hints)
- Session summary (for reflection engine)

### Desired State

```
User sends 5 messages → Bot responds 5 times → User leaves
                                    ↓
                    (30 min inactivity)
                                    ↓
        Cron runs → finds stale session → closes it → triggers processing
                                    ↓
            Goal analysis, knowledge extraction, summarization all run
```

---

## Design Decision: Cron vs Redis TTL

We considered two approaches:

| Approach | Complexity | Latency | Reliability |
|----------|------------|---------|-------------|
| **Redis TTL + keyspace notifications** | High (6 components) | Immediate | Very high |
| **Cron job (chosen)** | Low (1 job) | ~5 min | High |

**Why cron wins for this use case:**

1. **Not user-facing**: Goal analysis, knowledge extraction, and summarization are background analytics. Users don't notice a 5-minute delay.

2. **Simplicity**: One cron job vs. Redis TTL touch on every message + listener + fallback cron + startup recovery + periodic refresh.

3. **Fewer failure modes**: Cron job fails? It runs again in 5 minutes. No Redis dependency, no listener to die, no TTL keys to lose.

4. **Already have infrastructure**: arq is already running cron jobs.

**When Redis TTL IS appropriate:**
- Reminders (user-facing, precision matters) — see SPEC-S07
- Rate limiting (must be exact)
- Real-time features

---

## Architecture

### Design Philosophy

- **Simple beats clever**: One cron job > event-driven system with 6 moving parts
- **Idempotent**: Re-running the job is safe; already-processed sessions are skipped
- **Self-healing**: Missed a run? Next run catches it
- **Every message matters**: Even 1 message can contain "I'm Alex" or "I'm getting divorced"

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    SESSION TIMEOUT PROCESSING                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  CRON JOB: close_stale_sessions (every 5 min)                   │
│  ─────────────────────────────────────────────                  │
│                                                                  │
│  1. Find sessions where:                                         │
│     - is_active = TRUE                                           │
│     - updated_at < NOW() - 30 minutes                           │
│                                                                  │
│  2. For each stale session:                                      │
│     - Close it (is_active = FALSE, end_time = NOW())            │
│     - Fetch messages                                             │
│     - enqueue_post_conversation_tasks()                          │
│                                                                  │
│  3. Also find unprocessed closed sessions:                       │
│     - is_active = FALSE                                          │
│     - No summary exists                                          │
│     - Closed within last 24 hours                               │
│     (Catches anything the threshold check missed)                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Data Model

**No schema changes needed.** Uses existing:
- `v2_conversation_sessions`: Session state
- `v2_summaries`: Check if already processed
- `v2_chat_history`: Fetch messages

---

## Implementation Plan

### Single File: `src_v2/workers/tasks/session_tasks.py`

```python
"""
Session timeout processing.

Cron job that closes stale sessions and triggers post-conversation processing.
Runs every 5 minutes.
"""
from datetime import datetime, timezone
from typing import Dict, Any, List
from loguru import logger

from src_v2.core.database import db_manager
from src_v2.memory.manager import memory_manager
from src_v2.config.settings import settings


# Use the existing timeout constant
SESSION_TIMEOUT_MINUTES = 30


async def close_stale_sessions(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Find and close sessions that have been inactive for 30+ minutes,
    then trigger post-conversation processing.
    
    Also catches any closed sessions that were never processed
    (e.g., closed by lazy detection but under the message threshold).
    
    Runs every 5 minutes via arq cron.
    """
    from src_v2.discord.handlers.message_handler import enqueue_post_conversation_tasks
    
    stats = {
        "stale_closed": 0,
        "unprocessed_recovered": 0, 
        "skipped_empty": 0,
        "errors": 0
    }
    
    if not db_manager.postgres_pool:
        logger.warning("Database not available for session cleanup")
        return {"success": False, "error": "no_db"}
    
    try:
        # === Part 1: Close stale active sessions ===
        async with db_manager.postgres_pool.acquire() as conn:
            # Find and close in one atomic operation
            stale_rows = await conn.fetch("""
                UPDATE v2_conversation_sessions
                SET is_active = FALSE, end_time = NOW()
                WHERE is_active = TRUE
                  AND updated_at < NOW() - INTERVAL '%s minutes'
                RETURNING id, user_id, character_name, start_time
            """ % SESSION_TIMEOUT_MINUTES)
            
            for row in stale_rows:
                result = await _process_session(conn, row, "stale_timeout")
                if result == "processed":
                    stats["stale_closed"] += 1
                elif result == "empty":
                    stats["skipped_empty"] += 1
                else:
                    stats["errors"] += 1
        
        # === Part 2: Recover unprocessed closed sessions ===
        async with db_manager.postgres_pool.acquire() as conn:
            # Find sessions that are closed but have no summary
            # (missed by the message threshold check)
            unprocessed_rows = await conn.fetch("""
                SELECT 
                    s.id,
                    s.user_id,
                    s.character_name,
                    s.start_time
                FROM v2_conversation_sessions s
                LEFT JOIN v2_summaries sum ON sum.session_id = s.id
                WHERE 
                    s.is_active = FALSE
                    AND s.end_time IS NOT NULL
                    AND s.end_time > NOW() - INTERVAL '24 hours'
                    AND sum.id IS NULL
                ORDER BY s.end_time ASC
                LIMIT 50
            """)
            
            for row in unprocessed_rows:
                result = await _process_session(conn, row, "unprocessed_recovery")
                if result == "processed":
                    stats["unprocessed_recovered"] += 1
                elif result == "empty":
                    stats["skipped_empty"] += 1
                else:
                    stats["errors"] += 1
        
        # Log summary
        total = stats["stale_closed"] + stats["unprocessed_recovered"]
        if total > 0:
            logger.info(
                f"Session cleanup: closed {stats['stale_closed']} stale, "
                f"recovered {stats['unprocessed_recovered']} unprocessed, "
                f"skipped {stats['skipped_empty']} empty"
            )
        
        return {"success": True, **stats}
        
    except Exception as e:
        logger.error(f"Session cleanup failed: {e}")
        return {"success": False, "error": str(e)}


async def _process_session(conn, row: Dict, trigger: str) -> str:
    """
    Process a single session: fetch messages and enqueue tasks.
    
    Returns: "processed", "empty", or "error"
    """
    from src_v2.discord.handlers.message_handler import enqueue_post_conversation_tasks
    from langchain_core.messages import HumanMessage
    
    try:
        session_id = str(row['id'])
        user_id = row['user_id']
        character_name = row['character_name']
        start_time = row['start_time']
        
        # Fetch messages for this session
        messages = await memory_manager.get_history_for_session(
            user_id, character_name, start_time
        )
        
        if not messages:
            logger.debug(f"Session {session_id} had no messages, skipping")
            return "empty"
        
        # Convert to dict format
        msg_dicts = [
            {
                "role": "human" if isinstance(m, HumanMessage) else "ai",
                "content": m.content
            }
            for m in messages
        ]
        
        # Get user display name
        user_name = await conn.fetchval(
            "SELECT display_name FROM v2_users WHERE user_id = $1", 
            user_id
        ) or user_id
        
        # Trigger post-conversation processing
        await enqueue_post_conversation_tasks(
            user_id=user_id,
            character_name=character_name,
            session_id=session_id,
            messages=msg_dicts,
            user_name=user_name,
            trigger=trigger
        )
        
        logger.debug(f"Processed session {session_id}: {len(messages)} messages ({trigger})")
        return "processed"
        
    except Exception as e:
        logger.error(f"Failed to process session {row['id']}: {e}")
        return "error"
```

### Register Cron Job

**File:** `src_v2/workers/worker.py`

```python
from arq.cron import cron
from src_v2.workers.tasks.session_tasks import close_stale_sessions

class WorkerSettings:
    # ... existing settings ...
    
    cron_jobs = [
        # ... existing cron jobs ...
        
        # Session timeout processing - every 5 minutes
        cron(close_stale_sessions, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),
    ]
```

---

## Configuration

| Setting | Default | Purpose |
|---------|---------|---------|
| `SESSION_TIMEOUT_MINUTES` | `30` | Inactivity threshold |
| Cron interval | `5 min` | How often to check for stale sessions |
| `UNPROCESSED_MAX_AGE_HOURS` | `24` | Don't process ancient sessions |
| `UNPROCESSED_BATCH_LIMIT` | `50` | Max sessions per cron run |

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Sessions processed | 100% | All sessions with ≥1 message get processed |
| Processing latency | <5 min after timeout | Cron interval |
| Cron reliability | 99.9% | arq job success rate |

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Cron job fails | Low | Delayed processing | Runs again in 5 min; self-healing |
| Database down | Low | No processing | Job retries; alerts on DB health |
| Large backlog | Low | Slow processing | Batch limit of 50; spreads load |
| Duplicate processing | Low | Wasted LLM calls | Check `v2_summaries` exists |

---

## Testing

```python
async def test_stale_session_closed_and_processed():
    """Test that stale sessions are closed and processed."""
    # 1. Create a session with messages
    session_id = await session_manager.create_session(user_id, character_name)
    await memory_manager.add_message(user_id, character_name, "Hi, I'm Alex!")
    
    # 2. Backdate the session to make it stale
    await conn.execute("""
        UPDATE v2_conversation_sessions 
        SET updated_at = NOW() - INTERVAL '35 minutes'
        WHERE id = $1
    """, session_id)
    
    # 3. Run the cron job
    result = await close_stale_sessions({})
    
    # 4. Verify session was closed
    is_active = await conn.fetchval(
        "SELECT is_active FROM v2_conversation_sessions WHERE id = $1",
        session_id
    )
    assert is_active == False
    
    # 5. Verify processing was triggered (summary created)
    # Note: May need to wait for async task to complete
    summary = await conn.fetchrow(
        "SELECT id FROM v2_summaries WHERE session_id = $1",
        session_id
    )
    assert summary is not None
    
    assert result["stale_closed"] == 1


async def test_unprocessed_session_recovered():
    """Test that closed sessions without summaries are recovered."""
    # 1. Create and manually close a session (simulating lazy detection)
    session_id = await session_manager.create_session(user_id, character_name)
    await memory_manager.add_message(user_id, character_name, "Hi!")
    await session_manager.close_session(session_id)
    
    # 2. Run the cron job
    result = await close_stale_sessions({})
    
    # 3. Verify it was recovered
    assert result["unprocessed_recovered"] == 1


async def test_empty_session_skipped():
    """Test that sessions with no messages are skipped."""
    # 1. Create a stale session with NO messages
    session_id = await session_manager.create_session(user_id, character_name)
    await conn.execute("""
        UPDATE v2_conversation_sessions 
        SET updated_at = NOW() - INTERVAL '35 minutes'
        WHERE id = $1
    """, session_id)
    
    # 2. Run the cron job
    result = await close_stale_sessions({})
    
    # 3. Verify it was skipped
    assert result["skipped_empty"] == 1
    assert result["stale_closed"] == 0
```

---

## References

- [GUIDE-003-GOALS.md](../guide/GUIDE-003-GOALS.md) - Goals system documentation
- [SPEC-S07-REDIS_TTL_REMINDERS.md](SPEC-S07-REDIS_TTL_REMINDERS.md) - Redis TTL for user-facing reminders (where precision matters)
- `src_v2/memory/session.py` - Session manager
- `src_v2/workers/worker.py` - arq worker configuration
