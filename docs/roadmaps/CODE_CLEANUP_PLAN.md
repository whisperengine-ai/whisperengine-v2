# Code Cleanup & Technical Debt Plan

**Date:** November 27, 2025
**Status:** In Progress

This document tracks identified "hackish" solutions, technical debt, and areas for improvement in the `src_v2` codebase.

## 🔴 High Priority Issues

### 1. Hardcoded Magic Numbers & Sleep Values
**Status:** ✅ Done
**Location:** Multiple files
- `discord/bot.py:228`: `await asyncio.sleep(300)` (Status update interval)
- `discord/bot.py:1009`: `reading_delay = min(len(user_message) * 0.05, 4.0)` (Typing delay formula)
- `image_gen/service.py:236`: `await asyncio.sleep(1)` (Polling interval)
- `discord/scheduler.py:21-23`: Hardcoded intervals and thresholds

**Fix:** Extract these to `settings.py` as configurable constants.

### 2. Temporary Debug Comments Left in Production Code
**Status:** ✅ Done
**Location:** `knowledge/manager.py:530`
```python
# Note: Removed ORDER BY r.created_at DESC temporarily to debug missing facts issue
```
**Fix:** Restore proper ordering or document why it was intentionally removed.

### 3. Overly Broad Exception Handling
**Status:** 🔴 Open
**Location:** Multiple files (50+ instances)
Most catch blocks catch `Exception` which can hide bugs.
**Fix:** Use specific exception types where possible, and re-raise critical errors.

### 4. Type Ignores Without Comments
**Status:** 🔴 Open
**Location:** Several files (e.g., `scheduler.py`)
**Fix:** Add comments explaining why the type ignore is necessary, or fix the actual typing.

## 🟡 Medium Priority Issues

### 5. Regex-Based Text Cleaning in Response Pipeline
**Status:** ✅ Done
**Location:** `discord/bot.py:1024-1026`
Regex used to strip timestamps leaking from memory.
**Fix:** Fix the timestamp injection point in `memory/manager.py`.

### 6. Duplicate Initialization Pattern Across Managers
**Status:** 🟡 Open
**Location:** `memory/manager.py`, `knowledge/manager.py`, etc.
**Fix:** Create a `@require_db` decorator in `core/database.py`.

### 7. Global Singleton Pattern Inconsistency
**Status:** 🟡 Open
**Location:** Various managers
**Fix:** Standardize on one pattern across all managers.

### 8. Repeated JSON Parsing for Comma-Separated Lists
**Status:** 🟡 Open
**Location:** `config/settings.py`
**Fix:** Extract to a utility function.

### 9. BFL Image URL Stripping Pattern
**Status:** 🟡 Open
**Location:** `discord/bot.py`
**Fix:** Improve LLM prompt or handle at tool level.

## 🟢 Low Priority / Style Issues

### 10. Inconsistent Import Ordering
**Status:** 🟢 Open
**Fix:** Move all imports to top of file.

### 11. Mixed Logging Styles
**Status:** 🟢 Open
**Fix:** Consider structured logging fields.

### 12. Temp Directory Management
**Status:** 🟢 Open
**Fix:** Create shared utility for temp file management.

### 13. Sentence Chunking Algorithm
**Status:** 🟢 Open
**Fix:** Use proper sentence tokenizer.

### 14. Unused Import in Character Manager
**Status:** 🟢 Open
**Fix:** Remove unused import.
