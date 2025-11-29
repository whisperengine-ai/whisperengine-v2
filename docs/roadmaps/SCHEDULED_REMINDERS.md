# Scheduled Reminders

**Document Version:** 1.1
**Created:** November 27, 2025
**Status:** ✅ Complete
**Priority:** Medium
**Complexity:** 🟡 Medium
**Estimated Time:** 3-4 days

---

## Executive Summary

Users often treat AI companions as assistants. "Remind me to call mom in 2 hours." Currently, the bot agrees but fails to deliver. This feature adds **functional reminders**.

---

## 👤 User Experience

**User:** "Remind me to take the pizza out in 20 minutes."
**Bot:** "Got it. I'll remind you about the pizza at 6:40 PM."
...(20 mins later)...
**Bot:** "Hey! 🍕 Time to take the pizza out!"

---

## 🔧 Technical Design

### 1. Intent Detection & Parsing

-   Use `dateparser` library for natural language time parsing.
-   In `Classifier` or `Router`, detect `REMINDER` intent.
-   Extract: `content` ("take pizza out") and `time` ("20 minutes").

### 2. Storage

New Postgres table `reminders`:
-   `id`, `user_id`, `channel_id`, `content`, `deliver_at`, `created_at`, `status`

### 3. Delivery System

Update `ProactiveScheduler` (`src_v2/discord/scheduler.py`):
-   Poll `reminders` table every minute for `deliver_at <= now() AND status = 'pending'`.
-   Send message to `channel_id`.
-   Mark as `delivered`.

### 4. Tool Definition

New tool `set_reminder(content: str, time_string: str)`:
-   LLM calls this when user asks.
-   Tool parses time, saves to DB, returns confirmation string.

---

## 📋 Implementation Plan

1.  ✅ **Database**: Create `reminders` table migration.
2.  ✅ **Tool**: Implement `SetReminderTool` with `dateparser`.
3.  ✅ **Scheduler**: Add polling loop to `ProactiveScheduler`.
4.  ✅ **Testing**: Verify timezones (assume UTC or store user offset).

## ⚠️ Risks & Mitigations

-   **Timezones**: "Remind me at 5 PM" - 5 PM whose time?
    -   *Mitigation*: Ask user for timezone if unknown, or assume UTC/Server time and clarify. (Phase E1 "User Timezone Storage" helps here).
