# SPEC-S07: Redis TTL Reminder Delivery

**Document Version:** 1.1  
**Created:** December 7, 2025  
**Updated:** December 7, 2025  
**Status:** 📋 Proposed  
**Priority:** 🔴 High  
**Dependencies:** Redis, PostgreSQL

> ✅ **Emergence Check:** "Remind me in 5 minutes" should fire at exactly 5 minutes, not "somewhere between 5-6 minutes depending on cron." Precision is part of trust.

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Architecture review of time-based events |
| **Proposed by** | Mark + Claude (collaborative) |
| **Catalyst** | Reminders are user-facing—precision matters for trust |
| **Key insight** | User-facing timing should be exact, not poll-dependent |
| **Decision factors** | User trust, precision expectations, clean architecture |

---

## Executive Summary

**Current:** Reminders use cron-based polling. Every minute, the system queries Postgres for reminders where `deliver_at <= NOW()`. This creates up to 60 seconds of jitter between requested delivery time and actual delivery.

**Problem:** When a user says "remind me in 5 minutes," they expect precision. A 60-second jitter is noticeable and erodes trust in the bot's reliability.

**Solution:** Use Redis TTL with keyspace notifications to deliver reminders at exactly the requested time. PostgreSQL remains the source of truth; Redis provides precise timing.

---

## Problem Statement

### Current Implementation

```
User: "Remind me to call mom in 10 minutes"
                    ↓
ReminderManager.create_reminder(deliver_at=now+10min)
                    ↓
INSERT INTO v2_reminders (deliver_at=..., status='pending')
                    ↓
                (wait)
                    ↓
Cron runs every 60 sec → SELECT * WHERE deliver_at <= NOW() AND status='pending'
                    ↓
If found → deliver reminder → mark as 'delivered'
```

**Timing Analysis:**
- User requests: 10 minutes
- Cron interval: 60 seconds
- Worst case: Reminder due at 10:00:01, cron runs at 10:01:00 → **59 second delay**
- Average case: ~30 second delay
- Best case: <1 second (cron happens to run at exact moment)

### Desired State

```
User: "Remind me to call mom in 10 minutes"
                    ↓
ReminderManager.create_reminder(deliver_at=now+10min)
                    ↓
1. INSERT INTO v2_reminders (status='pending')     ← Source of truth
2. SET reminder:{id} {data} EX 600                 ← Precision timing
                    ↓
            (exactly 600 seconds pass)
                    ↓
Redis TTL expires → __keyevent@0__:expired fires
                    ↓
ReminderTimer.on_expire() → deliver_reminder(id)
                    ↓
Mark as 'delivered' in Postgres
```

**Timing Analysis:**
- User requests: 10 minutes
- Redis precision: sub-second
- Delivery: exactly at requested time (±1 second)

---

## Value Analysis

### Quantitative Benefits

| Metric | Current (Cron) | Target (Redis TTL) | Improvement |
|--------|----------------|---------------------|-------------|
| Average delivery jitter | ~30 sec | <1 sec | 30x more precise |
| Worst-case jitter | 60 sec | 2 sec | 30x more precise |
| Polling overhead | 1 query/min | 0 (event-driven) | Reduced DB load |
| CPU usage | Constant polling | Event-only | More efficient |

### Qualitative Benefits

- **User trust**: "This bot is reliable—it reminded me exactly when I asked"
- **Natural interaction**: No mental adjustment for "I should say 9 minutes if I want 10"
- **Scalability**: No polling overhead as reminder count grows

### Cost Analysis

| Component | Cost |
|-----------|------|
| Redis TTL overhead | 1 key per pending reminder |
| Keyspace notifications | Shared with session listener |
| Development | ~2-3 hours (pattern already established) |
| Migration | Zero downtime (add parallel, switch over) |

---

## Architecture

### Design Philosophy

- **Postgres = Source of Truth**: All reminder data lives in Postgres
- **Redis = Precision Timer**: Only handles timing, not storage
- **Event-Driven**: No polling; react to TTL expiry
- **Idempotent**: Duplicate expiry events don't duplicate deliveries
- **Belt & Suspenders**: Cron fallback catches anything Redis misses

### Pattern Application

```python
class ReminderListener:
    """
    Redis TTL listener for precise reminder delivery.
    
    Key format: reminder:{reminder_id}
    Value: {user_id}:{channel_id}
    """
    
    async def on_expire(self, reminder_id: int) -> None:
        await deliver_reminder(reminder_id)
```

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                  REDIS TTL REMINDER DELIVERY                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  CREATE REMINDER                                                 │
│  ───────────────                                                 │
│  1. Insert into Postgres (source of truth)                       │
│  2. Calculate TTL: (deliver_at - now).total_seconds()           │
│  3. SET reminder:{id} {user_id}:{channel_id} EX {ttl}           │
│                                                                  │
│  DELIVER REMINDER (on TTL expiry)                               │
│  ─────────────────────────────────                              │
│  1. Redis fires __keyevent@0__:expired                          │
│  2. ReminderTimer.on_expire(reminder_id)                        │
│  3. Fetch reminder from Postgres                                 │
│  4. Check status == 'pending' (idempotency)                     │
│  5. Deliver to Discord channel                                   │
│  6. Mark status = 'delivered' in Postgres                       │
│                                                                  │
│  CANCEL REMINDER                                                 │
│  ───────────────                                                 │
│  1. DELETE reminder:{id} from Redis                             │
│  2. UPDATE status = 'cancelled' in Postgres                     │
│                                                                  │
│  FALLBACK (cron, runs every 5 min)                              │
│  ─────────────────────────────────                              │
│  SELECT * FROM v2_reminders                                      │
│  WHERE deliver_at <= NOW() - INTERVAL '2 minutes'               │
│    AND status = 'pending'                                        │
│  → Deliver any missed reminders                                  │
│                                                                  │
│  STARTUP RECOVERY                                                │
│  ────────────────                                                │
│  SELECT * FROM v2_reminders WHERE status = 'pending'            │
│  → Recreate Redis TTL keys with remaining time                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Data Model

**Existing table (no changes):**
```sql
CREATE TABLE v2_reminders (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    channel_id VARCHAR NOT NULL,
    character_name VARCHAR NOT NULL,
    content TEXT NOT NULL,
    deliver_at TIMESTAMP WITH TIME ZONE NOT NULL,
    status VARCHAR DEFAULT 'pending',  -- 'pending', 'delivered', 'cancelled', 'failed'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**Redis keys:**
- `reminder:{reminder_id}` → `{user_id}:{channel_id}` with TTL = seconds until deliver_at

---

## Implementation Plan

### Phase 1: ReminderTimer Class (~30 min)

**File:** `src_v2/workers/timers/reminder_timer.py`

```python
from typing import Optional
from loguru import logger
from src_v2.workers.event_timer import RedisEventTimer
from src_v2.core.database import db_manager


class ReminderTimer(RedisEventTimer):
    """
    Redis TTL timer for precise reminder delivery.
    
    Key format: reminder:{reminder_id}
    Value: {user_id}:{channel_id}
    """
    prefix = "reminder"
    
    async def on_expire(self, key_parts: tuple, stored_value: Optional[str]) -> None:
        """Called when a reminder TTL expires."""
        try:
            reminder_id = int(key_parts[0])
            await self._deliver_reminder(reminder_id)
        except (ValueError, IndexError) as e:
            logger.error(f"Invalid reminder key parts: {key_parts}")
    
    async def _deliver_reminder(self, reminder_id: int) -> None:
        """Fetch reminder from Postgres and deliver it."""
        if not db_manager.postgres_pool:
            logger.error("Cannot deliver reminder: no database connection")
            return
        
        async with db_manager.postgres_pool.acquire() as conn:
            # Fetch and lock the reminder
            row = await conn.fetchrow("""
                SELECT id, user_id, channel_id, character_name, content, status
                FROM v2_reminders
                WHERE id = $1
                FOR UPDATE
            """, reminder_id)
            
            if not row:
                logger.warning(f"Reminder {reminder_id} not found")
                return
            
            if row['status'] != 'pending':
                logger.debug(f"Reminder {reminder_id} already {row['status']}, skipping")
                return
            
            # Mark as delivered first (idempotency)
            await conn.execute("""
                UPDATE v2_reminders SET status = 'delivered' WHERE id = $1
            """, reminder_id)
        
        # Deliver to Discord
        await self._send_to_discord(
            user_id=row['user_id'],
            channel_id=row['channel_id'],
            character_name=row['character_name'],
            content=row['content']
        )
        
        logger.info(f"Delivered reminder {reminder_id} to {row['user_id']}")
    
    async def _send_to_discord(
        self, 
        user_id: str, 
        channel_id: str, 
        character_name: str, 
        content: str
    ) -> None:
        """Send the reminder message to Discord."""
        # Import here to avoid circular dependency
        from src_v2.discord.client import get_bot_client
        
        bot = get_bot_client(character_name)
        if not bot:
            logger.error(f"No bot client for {character_name}")
            return
        
        channel = bot.get_channel(int(channel_id))
        if not channel:
            logger.warning(f"Channel {channel_id} not found")
            return
        
        # Format reminder message
        message = f"<@{user_id}> ⏰ **Reminder:** {content}"
        await channel.send(message)
```

### Phase 2: Update ReminderManager (~30 min)

**File:** `src_v2/intelligence/reminder_manager.py`

```python
import datetime
from typing import List, Optional, Dict, Any
from loguru import logger
from src_v2.core.database import db_manager, retry_db_operation
from src_v2.core.cache import redis_client
from src_v2.config.settings import settings


class ReminderManager:
    """
    Manages scheduling and retrieval of user reminders.
    
    Uses PostgreSQL as source of truth and Redis TTL for precise delivery timing.
    """
    
    @retry_db_operation(max_retries=3)
    async def create_reminder(
        self, 
        user_id: str, 
        channel_id: str, 
        character_name: str, 
        content: str, 
        deliver_at: datetime.datetime
    ) -> int:
        """
        Create a new reminder.
        
        1. Insert into Postgres (source of truth)
        2. Set Redis TTL key for precise timing
        """
        if not db_manager.postgres_pool:
            raise RuntimeError("Database not connected")
        
        async with db_manager.postgres_pool.acquire() as conn:
            reminder_id = await conn.fetchval("""
                INSERT INTO v2_reminders (user_id, channel_id, character_name, content, deliver_at, status)
                VALUES ($1, $2, $3, $4, $5, 'pending')
                RETURNING id
            """, user_id, channel_id, character_name, content, deliver_at)
        
        # Calculate TTL and set Redis key
        now = datetime.datetime.now(datetime.timezone.utc)
        ttl_seconds = max(1, int((deliver_at - now).total_seconds()))
        
        redis_key = f"reminder:{reminder_id}"
        redis_value = f"{user_id}:{channel_id}"
        await redis_client.setex(redis_key, ttl_seconds, redis_value)
        
        logger.info(f"Created reminder {reminder_id} for user {user_id}, TTL={ttl_seconds}s")
        return reminder_id

    @retry_db_operation(max_retries=3)
    async def cancel_reminder(self, reminder_id: int, user_id: str) -> bool:
        """
        Cancel a pending reminder.
        
        1. Delete Redis TTL key
        2. Update status in Postgres
        """
        if not db_manager.postgres_pool:
            return False
        
        async with db_manager.postgres_pool.acquire() as conn:
            # Verify ownership and pending status
            row = await conn.fetchrow("""
                SELECT id FROM v2_reminders
                WHERE id = $1 AND user_id = $2 AND status = 'pending'
            """, reminder_id, user_id)
            
            if not row:
                return False
            
            # Cancel in both systems
            await redis_client.delete(f"reminder:{reminder_id}")
            await conn.execute("""
                UPDATE v2_reminders SET status = 'cancelled' WHERE id = $1
            """, reminder_id)
        
        logger.info(f"Cancelled reminder {reminder_id}")
        return True

    @retry_db_operation(max_retries=3)
    async def get_due_reminders(self, character_name: str) -> List[Dict[str, Any]]:
        """
        FALLBACK: Get pending reminders that Redis may have missed.
        
        Only returns reminders that are:
        - Past due by at least 2 minutes (give Redis time)
        - Still pending (not already delivered)
        
        This should rarely return results if Redis TTL is working.
        """
        if not db_manager.postgres_pool:
            return []
        
        # 2 minutes grace period for Redis
        threshold = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=2)
        
        async with db_manager.postgres_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, user_id, channel_id, character_name, content, deliver_at
                FROM v2_reminders
                WHERE character_name = $1 
                  AND status = 'pending'
                  AND deliver_at <= $2
                ORDER BY deliver_at ASC
                LIMIT 20
            """, character_name, threshold)
            
            if rows:
                logger.warning(f"Fallback found {len(rows)} missed reminders - check Redis health")
            
            return [dict(row) for row in rows]

    async def recover_redis_keys(self) -> int:
        """
        STARTUP: Recreate Redis TTL keys for any pending reminders.
        
        Called on worker startup to handle Redis restart scenarios.
        Returns count of recovered reminders.
        """
        if not db_manager.postgres_pool:
            return 0
        
        now = datetime.datetime.now(datetime.timezone.utc)
        recovered = 0
        expired = 0
        
        async with db_manager.postgres_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, user_id, channel_id, deliver_at
                FROM v2_reminders
                WHERE status = 'pending'
            """)
            
            for row in rows:
                reminder_id = row['id']
                deliver_at = row['deliver_at']
                
                # Calculate remaining TTL
                remaining = (deliver_at - now).total_seconds()
                
                if remaining > 1:
                    # Still in the future - set TTL
                    redis_key = f"reminder:{reminder_id}"
                    redis_value = f"{row['user_id']}:{row['channel_id']}"
                    await redis_client.setex(redis_key, int(remaining), redis_value)
                    recovered += 1
                else:
                    # Already past due - will be caught by fallback cron
                    expired += 1
        
        logger.info(f"Startup recovery: {recovered} reminders restored, {expired} past due")
        return recovered


# Global instance
reminder_manager = ReminderManager()
```

### Phase 3: Register Timer in Worker (~15 min)

**File:** `src_v2/workers/worker.py`

```python
from src_v2.workers.event_timer import RedisEventListener
from src_v2.workers.timers.session_timer import SessionTimer
from src_v2.workers.timers.reminder_timer import ReminderTimer
from src_v2.intelligence.reminder_manager import reminder_manager

async def startup(ctx: Dict[str, Any]):
    """Worker startup - initialize connections and start listeners."""
    # ... existing startup code ...
    
    # Recover any pending reminders (in case Redis restarted)
    await reminder_manager.recover_redis_keys()
    
    # Start unified event listener
    listener = RedisEventListener(redis_client)
    listener.register(SessionTimer(redis_client))
    listener.register(ReminderTimer(redis_client))
    
    ctx["event_listener_task"] = asyncio.create_task(listener.listen())
    logger.info("Event listener started with session + reminder timers")
```

### Phase 4: Update Fallback Cron (~15 min)

Reduce cron frequency since it's now just a backup:

**File:** `src_v2/workers/tasks/cron_tasks.py`

```python
# Change from 1 minute to 5 minutes (it's just a fallback now)
REMINDER_FALLBACK_INTERVAL = 300  # 5 minutes

async def process_missed_reminders(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    FALLBACK: Deliver any reminders that Redis TTL missed.
    
    This should rarely find anything if Redis is healthy.
    Alerts if it does find missed reminders.
    """
    from src_v2.intelligence.reminder_manager import reminder_manager
    from src_v2.workers.timers.reminder_timer import ReminderTimer
    
    character_name = ctx.get("character_name", settings.DISCORD_BOT_NAME)
    timer = ReminderTimer(redis_client)
    
    missed = await reminder_manager.get_due_reminders(character_name)
    
    stats = {"delivered": 0, "failed": 0}
    for reminder in missed:
        try:
            await timer._deliver_reminder(reminder["id"])
            stats["delivered"] += 1
        except Exception as e:
            stats["failed"] += 1
            logger.error(f"Failed to deliver missed reminder {reminder['id']}: {e}")
    
    if stats["delivered"] > 0:
        logger.warning(
            f"Fallback delivered {stats['delivered']} missed reminders - "
            "investigate Redis listener health"
        )
    
    return {"success": True, **stats}
```

---

## Configuration

| Setting | Default | Purpose |
|---------|---------|---------|
| `ENABLE_REDIS_REMINDER_TTL` | `true` | Use Redis TTL for reminders |
| `REMINDER_FALLBACK_INTERVAL` | `300` | Cron interval in seconds (5 min) |
| `REMINDER_FALLBACK_GRACE` | `120` | Seconds before fallback considers missed |

---

## Migration Strategy

**Zero-downtime migration:**

1. **Deploy Phase 1-3**: New code with Redis TTL alongside existing cron
2. **Both systems run in parallel**: Redis handles new reminders, cron catches any Redis misses
3. **Monitor for 1 week**: Verify fallback finds zero (or near-zero) reminders
4. **Reduce cron frequency**: Change from 1 min to 5 min
5. **Monitor for 1 week**: Confirm stability
6. **Optional**: Remove cron entirely if Redis proves 100% reliable

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Reminders via Redis TTL | >99% | Count by delivery method |
| Reminders via fallback | <1% | Alert if >5/day |
| Delivery precision | ±2 sec | Compare deliver_at vs actual |
| User satisfaction | Improved | Qualitative feedback |

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Redis down | Low | Delayed reminders | Fallback cron catches them |
| Redis restart | Medium | Lost TTL keys | Startup recovery recreates them |
| Duplicate delivery | Low | Annoying UX | Idempotent status check |
| Long-running reminders (days) | Medium | Redis TTL limits | Max 7 days, warn user for longer |

### Long Reminder Limitation

Redis TTL precision degrades for very long durations. For reminders > 7 days:

```python
MAX_REDIS_TTL_DAYS = 7

async def create_reminder(..., deliver_at):
    ttl = (deliver_at - now).total_seconds()
    
    if ttl > MAX_REDIS_TTL_DAYS * 86400:
        # Don't use Redis for very long reminders
        # Fallback cron will handle them
        logger.info(f"Reminder {reminder_id} > 7 days, using cron-only")
    else:
        await redis_client.setex(f"reminder:{reminder_id}", int(ttl), value)
```

---

## Testing

```python
async def test_reminder_delivered_at_exact_time():
    """Test that reminders fire at the exact requested time."""
    deliver_at = datetime.now(timezone.utc) + timedelta(seconds=5)
    
    reminder_id = await reminder_manager.create_reminder(
        user_id="test",
        channel_id="123",
        character_name="elena",
        content="Test reminder",
        deliver_at=deliver_at
    )
    
    # Wait for delivery
    await asyncio.sleep(6)
    
    # Verify delivered
    async with db_manager.postgres_pool.acquire() as conn:
        status = await conn.fetchval(
            "SELECT status FROM v2_reminders WHERE id = $1", reminder_id
        )
    
    assert status == "delivered"


async def test_fallback_catches_missed_reminder():
    """Test that fallback cron catches reminders Redis missed."""
    # Create reminder directly in Postgres (bypassing Redis)
    async with db_manager.postgres_pool.acquire() as conn:
        reminder_id = await conn.fetchval("""
            INSERT INTO v2_reminders (user_id, channel_id, character_name, content, deliver_at, status)
            VALUES ('test', '123', 'elena', 'Missed', NOW() - INTERVAL '5 minutes', 'pending')
            RETURNING id
        """)
    
    # Run fallback
    missed = await reminder_manager.get_due_reminders("elena")
    
    assert len(missed) == 1
    assert missed[0]["id"] == reminder_id


async def test_cancel_reminder():
    """Test that cancelling removes from both Redis and Postgres."""
    deliver_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    
    reminder_id = await reminder_manager.create_reminder(
        user_id="test",
        channel_id="123",
        character_name="elena",
        content="Cancel me",
        deliver_at=deliver_at
    )
    
    # Verify Redis key exists
    ttl = await redis_client.ttl(f"reminder:{reminder_id}")
    assert ttl > 0
    
    # Cancel
    success = await reminder_manager.cancel_reminder(reminder_id, "test")
    assert success
    
    # Verify Redis key gone
    ttl = await redis_client.ttl(f"reminder:{reminder_id}")
    assert ttl <= 0
    
    # Verify Postgres status
    async with db_manager.postgres_pool.acquire() as conn:
        status = await conn.fetchval(
            "SELECT status FROM v2_reminders WHERE id = $1", reminder_id
        )
    assert status == "cancelled"
```

---

## References

- [SPEC-S06-SHORT_SESSION_PROCESSING.md](SPEC-S06-SHORT_SESSION_PROCESSING.md) - RedisEventTimer pattern
- `src_v2/intelligence/reminder_manager.py` - Current reminder manager
- [Redis Keyspace Notifications](https://redis.io/docs/manual/keyspace-notifications/)
