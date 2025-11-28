# Proactive Messaging: Timezone Awareness

**Document Version:** 1.0
**Created:** November 28, 2025
**Status:** 📋 Proposed
**Priority:** 🟡 Medium
**Complexity:** 🟢 Low
**Estimated Time:** 1-2 days
**Origin:** External architecture review identified gap

---

## Executive Summary

The proactive messaging system can reach out to users based on drives (concern, curiosity, connection). **It has no awareness of the user's local time.**

**The Problem:**
- User in Tokyo, bot server in UTC
- Bot's "concern" drive triggers at 4 AM UTC
- User gets pinged at 1 PM Tokyo time ✓ (lucky)
- OR: User gets pinged at 4 AM Tokyo time ✗ (creepy/annoying)

**The Solution:**
Store user timezone (inferred or explicit) and respect quiet hours before proactive outreach.

---

## 👤 User Impact

**Without timezone awareness:**
- *3 AM notification*: "Hey, I was thinking about our conversation..."
- User wakes up annoyed
- Disables all bot notifications
- Trust decreases

**With timezone awareness:**
- Bot waits until user's local 9 AM
- Message arrives during reasonable hours
- User appreciates thoughtful timing

---

## 🔧 Technical Design

### 1. Timezone Storage

Add to user preferences in Postgres:

```sql
// Add to v2_user_relationships or new v2_user_preferences table
ALTER TABLE v2_user_relationships 
ADD COLUMN timezone VARCHAR(50) DEFAULT NULL,
ADD COLUMN quiet_hours_start INT DEFAULT 22,  // 10 PM local
ADD COLUMN quiet_hours_end INT DEFAULT 8;     // 8 AM local
```

### 2. Timezone Inference

Infer timezone from Discord activity patterns:

```python
// Pseudocode
class TimezoneInferrer:
    async def infer_timezone(self, user_id: str) -> Optional[str]:
        """
        Infer user timezone from message timestamps.
        
        Logic:
        - Get last 100 messages with timestamps
        - Find "peak activity" hours
        - Assume peak = daytime in their timezone
        - Map to likely timezone
        """
        messages = await get_user_message_times(user_id, limit=100)
        
        // Count messages by UTC hour
        hour_counts = Counter(msg.created_at.hour for msg in messages)
        
        // Find peak hours (most active)
        peak_hours = sorted(hour_counts.keys(), 
                           key=lambda h: hour_counts[h], 
                           reverse=True)[:4]
        
        // If peak is 14-18 UTC, user is likely in EST/EDT (UTC-5)
        // If peak is 22-02 UTC, user is likely in PST/PDT (UTC-8)
        // etc.
        
        return estimate_timezone_from_peak(peak_hours)
```

### 3. Quiet Hours Check

Update `src_v2/discord/scheduler.py`:

```python
// In ProactiveScheduler.check_user()
async def check_user(self, user_id: str, ...) -> None:
    // ... existing drive evaluation ...
    
    // NEW: Check if it's quiet hours for user
    if not await self._is_appropriate_time(user_id):
        logger.debug(f"Skipping proactive for {user_id}: quiet hours")
        return
    
    // ... continue with message generation ...

async def _is_appropriate_time(self, user_id: str) -> bool:
    """Check if current time is within user's active hours."""
    settings = await self._get_user_time_settings(user_id)
    
    if not settings.timezone:
        // No timezone known - default to allowing
        // But log for later inference
        return True
    
    // Get current hour in user's timezone
    user_tz = pytz.timezone(settings.timezone)
    user_time = datetime.now(user_tz)
    user_hour = user_time.hour
    
    // Check quiet hours (handles overnight ranges like 22-8)
    if settings.quiet_hours_start <= settings.quiet_hours_end:
        // Simple range: e.g., 1-6 (1 AM to 6 AM)
        in_quiet = settings.quiet_hours_start <= user_hour < settings.quiet_hours_end
    else:
        // Overnight range: e.g., 22-8 (10 PM to 8 AM)
        in_quiet = user_hour >= settings.quiet_hours_start or user_hour < settings.quiet_hours_end
    
    return not in_quiet
```

### 4. User Commands (Optional)

Allow users to set timezone explicitly:

```python
// Discord command
@app_commands.command(name="timezone")
async def set_timezone(self, interaction: discord.Interaction, timezone: str):
    """Set your timezone for proactive messages. Example: America/New_York"""
    try:
        // Validate timezone string
        pytz.timezone(timezone)
        await save_user_timezone(str(interaction.user.id), timezone)
        await interaction.response.send_message(
            f"Timezone set to {timezone}. I'll respect your quiet hours!",
            ephemeral=True
        )
    except pytz.exceptions.UnknownTimeZoneError:
        await interaction.response.send_message(
            "Unknown timezone. Use format like: America/New_York, Europe/London, Asia/Tokyo",
            ephemeral=True
        )
```

### 5. Configuration

Add to `settings.py`:

```python
// Proactive Timezone Settings
PROACTIVE_DEFAULT_QUIET_START: int = 22  // 10 PM
PROACTIVE_DEFAULT_QUIET_END: int = 8     // 8 AM
ENABLE_TIMEZONE_INFERENCE: bool = True
```

---

## 📋 Implementation Plan

| Step | Task | Time |
|------|------|------|
| 1 | Add timezone columns to database | 30 min |
| 2 | Create Alembic migration | 30 min |
| 3 | Implement `_is_appropriate_time()` in scheduler | 1-2 hours |
| 4 | Implement timezone inference from activity | 2-3 hours |
| 5 | Add `/timezone` command | 1 hour |
| 6 | Write tests for quiet hours logic | 1 hour |

---

## ⚠️ Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Timezone inference wrong | Allow explicit override; default to permissive |
| User travels, timezone changes | Periodic re-inference; trust explicit setting |
| Edge cases (DST transitions) | Use `pytz` which handles DST correctly |
| Privacy: storing timezone | It's operational data, not sensitive; respect deletion requests |

---

## 🎯 Success Criteria

- [ ] No proactive messages during user's quiet hours (10 PM - 8 AM local)
- [ ] Users can set timezone explicitly via command
- [ ] Timezone inferred for 80%+ of active users within 1 week
- [ ] Zero 3 AM pings to users who have timezone set

---

## 📊 Metrics to Track

```python
proactive_timing = {
    measurement: "proactive_timing",
    tags: {
        bot_name: "elena",
        timezone_source: "inferred",  // or "explicit", "unknown"
        blocked_by_quiet: "true",
    },
    fields: {
        user_local_hour: 14,
    }
}
```

---

## 🔮 Future Enhancements

1. **Smart Timing**: Learn user's actual responsive hours (not just awake hours)
2. **Activity Prediction**: Use ML to predict when user will next be online
3. **Urgency Override**: High-urgency messages can break quiet hours
4. **Sync with E7**: Merge with `USER_TIMEZONE_SUPPORT.md` roadmap

---

## 📚 Related Documents

- `src_v2/discord/scheduler.py` - Proactive scheduler implementation
- `docs/roadmaps/USER_TIMEZONE_SUPPORT.md` - General timezone support (E7)
- `docs/roadmaps/completed/ROADMAP_V2_PHASE13.md` - Proactive engagement phase
