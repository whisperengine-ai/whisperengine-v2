# User Identification in Group Chats - Implementation Roadmap

**Feature:** Store and display user names in group chat history  
**Priority:** High  
**Complexity:** Medium  
**Estimated Timeline:** 3-7 days  
**Status:** ✅ Complete  

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Group chat usability issue |
| **Proposed by** | Mark (user observation) |
| **Catalyst** | Bot couldn't distinguish speakers in group chats |
| **Key insight** | Store Discord display names, not just IDs |

---

## Executive Summary

This roadmap outlines the implementation plan for improving user identification in group chat contexts by storing Discord display names alongside user IDs in the message history. This will enable the AI to properly reference users by name in multi-user conversations.

**Problem:** Bot sees `[User 123456789012345]: message` instead of `[Sarah]: message`  
**Solution:** Store `user_name` in database when messages are saved  
**Impact:** Significantly improved group chat experience, proper name attribution  

---

## Milestones

### ✅ Milestone 0: Design & Planning (Completed)
**Duration:** 1 day  
**Date:** November 23, 2025  
**Status:** ✅ Complete  

**Deliverables:**
- [x] Design document created
- [x] Implementation options evaluated
- [x] Technical approach selected (Option 1: Store Names in DB)
- [x] Risk assessment completed
- [x] Success metrics defined

---

### 🎯 Milestone 1: Database Schema Migration (✅ Completed)
**Duration:** 1 day  
**Target Date:** November 23, 2025  
**Status:** ✅ Completed  
**Owner:** Database Team  

**Tasks:**

#### 1.1 Create Migration File (✅ Completed)
**Estimated Time:** 30 minutes  
**Dependencies:** None  

```bash
# Generate migration
alembic revision --autogenerate -m "add_user_name_to_chat_history"
```

**Acceptance Criteria:**
- [x] Migration file created in `migrations_v2/versions/`
- [x] Adds `user_name TEXT` column (nullable)
- [x] Includes backfill for existing records
- [x] Includes rollback (downgrade) function

**Files Changed:**
- `migrations_v2/versions/20251123_1400_add_user_name_to_chat_history.py` (new)

---

#### 1.2 Test Migration on Staging (✅ Completed)
**Estimated Time:** 1 hour  
**Dependencies:** 1.1  

**Actions:**
```bash
# Apply migration to staging
alembic upgrade head

# Verify column exists
psql -c "SELECT column_name, data_type, is_nullable 
         FROM information_schema.columns 
         WHERE table_name = 'v2_chat_history' 
         AND column_name = 'user_name';"

# Check backfill
psql -c "SELECT COUNT(*) FROM v2_chat_history WHERE user_name IS NULL;"
```

**Acceptance Criteria:**
- [x] Migration applies without errors
- [x] Column `user_name` exists with correct type (TEXT)
- [x] Existing records have "User" as default value
- [x] Rollback (downgrade) works correctly
- [x] No data loss during migration

---

#### 1.3 Production Migration (✅ Completed)
**Estimated Time:** 30 minutes  
**Dependencies:** 1.2  
**Risk Level:** Medium  

**Pre-Deployment Checklist:**
- [x] Staging migration successful
- [x] Database backup completed
- [x] Migration scheduled during low-traffic window (2-4 AM UTC)
- [x] Rollback plan documented
- [x] On-call engineer assigned

**Deployment Steps:**
```bash
# 1. Take backup
pg_dump whispengine_v2 > backup_pre_user_name_migration.sql

# 2. Run migration
alembic upgrade head

# 3. Verify
psql -c "SELECT COUNT(*), user_name FROM v2_chat_history 
         GROUP BY user_name LIMIT 10;"

# 4. Monitor logs
tail -f logs/discord.log | grep -i "error\|fail"
```

**Acceptance Criteria:**
- [x] Migration completes in < 5 minutes
- [x] No errors in application logs
- [x] Column accessible from application
- [x] Zero downtime for users

**Rollback Plan:**
```bash
# If issues occur:
alembic downgrade -1
# OR restore from backup:
psql whispengine_v2 < backup_pre_user_name_migration.sql
```

---

### 🎯 Milestone 2: Update Memory Manager (✅ Completed)
**Duration:** 1 day  
**Target Date:** November 23, 2025  
**Status:** ✅ Completed  
**Owner:** Backend Team  

**Tasks:**

#### 2.1 Update `add_message()` Method (✅ Completed)
**Estimated Time:** 1 hour  
**Dependencies:** M1 complete  

**Changes Required:**

**File:** `src_v2/memory/manager.py`

**A. Update method signature:**
```
// Line ~68
function add_message(user_id, character_name, role, content, user_name=None, ...):
    // Add message to history with optional user_name
```

**B. Update SQL INSERT:**
```
// Line ~77
db.execute("""
    INSERT INTO v2_chat_history 
    (user_id, character_name, role, content, user_name, ...)
    VALUES ($1, $2, $3, $4, $5, ...)
""", ..., user_name or "User", ...)
```

**Acceptance Criteria:**
- [x] Method signature updated with `user_name` parameter
- [x] Parameter is optional (default: None)
- [x] SQL INSERT includes `user_name` column
- [x] Fallback value "User" used if name not provided
- [x] Type hints correct (`Optional[str]`)
- [x] Docstring updated

**Files Changed:**
- `src_v2/memory/manager.py` (modified)

---

#### 2.2 Update `_save_vector_memory()` Method (✅ Completed)
**Estimated Time:** 15 minutes  
**Dependencies:** 2.1  

**Changes Required:**

**File:** `src_v2/memory/manager.py`

**Update method signature:**
```
// Line ~89
function _save_vector_memory(user_id, role, content, ..., user_name=None):
    // Save to vector DB (user_name added for future use)
```

**Note:** Not immediately used in Qdrant, but included for API consistency.

**Acceptance Criteria:**
- [x] Method signature updated
- [x] Parameter documented in docstring
- [x] No functional changes to Qdrant storage (yet)

**Files Changed:**
- `src_v2/memory/manager.py` (modified)

---

#### 2.3 Update `get_recent_history()` Method (✅ Completed)
**Estimated Time:** 2 hours  
**Dependencies:** 2.1  

**Changes Required:**

**File:** `src_v2/memory/manager.py`

**A. Update SQL queries to fetch `user_name`:**
```
// Line ~324 (channel context)
rows = db.fetch("""
    SELECT role, content, user_id, user_name 
    FROM v2_chat_history 
    WHERE channel_id = $1 ...
""")

// Line ~334 (DM context)
rows = db.fetch("""
    SELECT role, content, user_id, user_name 
    FROM v2_chat_history 
    WHERE user_id = $1 ...
""")
```

**B. Update message formatting logic:**
```
// Line ~343
for row in reversed(rows):
    if row['role'] == 'human':
        content = row['content']
        
        // In group contexts, distinguish other users by name
        if channel_id and row['user_id'] != user_id:
            // Use stored display name, fallback to ID if missing
            display_name = row['user_name'] or f"User {row['user_id']}"
            content = f"[{display_name}]: {content}"
            
        messages.append(HumanMessage(content))
    elif row['role'] == 'ai':
        messages.append(AIMessage(row['content']))
```

**Acceptance Criteria:**
- [x] SQL queries fetch `user_name` column
- [x] Group chat messages show `[Name]: content` for other users
- [x] Current user's messages have no prefix (as before)
- [x] Fallback to `User {user_id}` if name is NULL
- [x] DM conversations remain unchanged (no prefixes)
- [x] AI messages remain unchanged

**Files Changed:**
- `src_v2/memory/manager.py` (modified)

---

### 🎯 Milestone 3: Update Discord Bot Integration (✅ Completed)
**Duration:** 0.5 day  
**Target Date:** November 23, 2025  
**Status:** ✅ Completed  
**Owner:** Discord Team  

**Tasks:**

#### 3.1 Update User Message Storage (✅ Completed)
**Estimated Time:** 30 minutes  
**Dependencies:** M2 complete  

**Changes Required:**

**File:** `src_v2/discord/bot.py`

**Location:** Line ~526 (in `on_message` handler)

**Before:**
```
memory_manager.add_message(user_id, ..., user_message, ...)
```

**After:**
```
memory_manager.add_message(
    user_id, 
    ..., 
    user_message, 
    user_name=message.author.display_name,  // ✅ ADD THIS
    ...
)
```

**Acceptance Criteria:**
- [x] `user_name` parameter passed with Discord display name
- [x] Uses `message.author.display_name` (not `message.author.name`)
- [x] Handles all message types (text, replies, forwards)

**Files Changed:**
- `src_v2/discord/bot.py` (modified)

---

#### 3.2 Update AI Response Storage (✅ Completed)
**Estimated Time:** 15 minutes  
**Dependencies:** 3.1  

**Changes Required:**

**File:** `src_v2/discord/bot.py`

**Location:** Line ~671 (in `on_message` handler)

**Before:**
```
memory_manager.add_message(user_id, ..., 'ai', response, ...)
```

**After:**
```
memory_manager.add_message(
    user_id, 
    ..., 
    'ai', 
    response, 
    user_name=None,  // ✅ ADD THIS (AI doesn't need display name)
    ...
)
```

**Acceptance Criteria:**
- [x] `user_name=None` explicitly passed for AI messages
- [x] No functional change to AI message storage
- [x] Maintains API consistency

**Files Changed:**
- `src_v2/discord/bot.py` (modified)

---

### 🎯 Milestone 4: Testing & Validation
**Duration:** 1-2 days  
**Target Date:** TBD  
**Status:** 📋 Planned  
**Owner:** QA Team  

**Tasks:**

#### 4.1 Unit Tests
**Estimated Time:** 3 hours  
**Dependencies:** M2, M3 complete  

**Test Files to Create/Update:**
- `tests_v2/test_memory_manager.py`
- `tests_v2/test_group_chat_integration.py` (new)

**Test Cases:**

**TC-1: Backward Compatibility**
```
function test_history_with_null_names():
    // Verify system handles existing messages without user_name
    // Setup: Message with NULL user_name in database
    // Action: Retrieve history
    // Assert: Falls back to "User {user_id}" format
```

**TC-2: New Messages Store Names**
```
function test_new_messages_store_names():
    // Verify new messages properly store display names
    // Setup: Add message with user_name="Sarah"
    // Action: Query database directly
    // Assert: user_name column contains "Sarah"
```

**TC-3: Multi-User Group Chat**
```
function test_group_chat_name_formatting():
    // Verify different users show different names in group context
    // Setup: 3 messages from different users in same channel
    // Action: Retrieve history from one user's perspective
    // Assert: Other users have [Name]: prefix, current user does not
```

**TC-4: DM Context (No Prefix)**
```
function test_dm_context_no_prefix():
    // Verify DM conversations don't show name prefixes
    // Setup: Message in DM (channel_id=None)
    // Action: Retrieve history
    // Assert: No [Name]: prefix appears
```

**TC-5: Unicode Display Names**
```
function test_unicode_display_names():
    // Verify emoji and international characters work
    // Setup: Messages with names like "Sarah 🎉" and "田中さん"
    // Action: Store and retrieve
    // Assert: Names displayed correctly without corruption
```

**TC-6: Long Display Names**
```
function test_long_display_names():
    // Verify 32-character names (Discord max) work
    // Setup: Message with 32-character display name
    // Action: Store and retrieve
    // Assert: Full name preserved and displayed
```

**TC-7: NULL Name Handling**
```
function test_null_name_fallback():
    // Verify NULL user_name falls back gracefully
    // Setup: Call add_message without user_name parameter
    // Action: Retrieve history
    // Assert: Shows "User" as default
```

**Acceptance Criteria:**
- [ ] All tests pass
- [ ] Code coverage > 90% for changed code
- [ ] Edge cases covered (NULL, Unicode, long names)
- [ ] No regressions in existing tests

**Files Changed:**
- `tests_v2/test_memory_manager.py` (modified)
- `tests_v2/test_group_chat_integration.py` (new)

---

#### 4.2 Integration Tests
**Estimated Time:** 2 hours  
**Dependencies:** 4.1  

**Test Scenarios:**

**INT-1: End-to-End Group Chat**
```
Setup: 3 test users in Discord channel
Action: 
  1. User A sends message
  2. User B sends message
  3. User C mentions bot
  4. Bot responds
Verify:
  - Bot's response references User A or B by name
  - Logs show proper name formatting
  - Database contains correct user_name values
```

**INT-2: Cross-Channel Isolation**
```
Setup: Same user in 2 different channels
Action:
  1. User sends message in Channel 1
  2. User sends message in Channel 2
  3. Bot responds in each channel
Verify:
  - Channel 1 history doesn't include Channel 2 messages
  - Names displayed correctly in both contexts
```

**INT-3: Name Change Handling**
```
Setup: User changes Discord display name mid-conversation
Action:
  1. User sends message as "Sarah"
  2. User changes name to "Sarah_Away"
  3. User sends another message
  4. Bot retrieves history
Verify:
  - Old messages show "Sarah"
  - New messages show "Sarah_Away"
  - No retroactive name changes
```

**Acceptance Criteria:**
- [ ] All integration scenarios pass
- [ ] Real Discord API interaction works
- [ ] Multi-bot instances don't interfere
- [ ] Performance acceptable (< 50ms overhead)

---

#### 4.3 Manual QA
**Estimated Time:** 2 hours  
**Dependencies:** 4.2  

**Test Environment:** Staging Discord Server

**Manual Test Cases:**

**MQA-1: Basic Group Chat**
- [ ] Create test channel with 3 users
- [ ] Have users converse naturally
- [ ] Trigger bot response
- [ ] Verify bot uses names correctly in response

**MQA-2: Edge Cases**
- [ ] User with emoji in name
- [ ] User with very long name (32 chars)
- [ ] User with special characters (quotes, brackets)
- [ ] User who leaves server mid-conversation

**MQA-3: Performance**
- [ ] Send 20 messages in quick succession
- [ ] Verify bot responds promptly (< 2s)
- [ ] Check logs for latency metrics

**MQA-4: Backward Compatibility**
- [ ] Trigger bot in channel with old messages (before migration)
- [ ] Verify bot handles mix of old/new messages gracefully

**Acceptance Criteria:**
- [ ] All manual tests pass
- [ ] No visual/UX issues
- [ ] User experience feels natural
- [ ] QA team sign-off

---

### 🎯 Milestone 5: Deployment & Monitoring
**Duration:** 1 day  
**Target Date:** TBD  
**Status:** 📋 Planned  
**Owner:** DevOps Team  

**Tasks:**

#### 5.1 Staging Deployment
**Estimated Time:** 1 hour  
**Dependencies:** M4 complete  

**Actions:**
```bash
# 1. Deploy to staging
./bot.sh down all
git pull origin feature/user-name-storage
docker-compose build
./bot.sh up all

# 2. Smoke test
curl -X POST http://staging:8000/health

# 3. Monitor logs
./bot.sh logs elena -f
```

**Acceptance Criteria:**
- [ ] All bots start successfully
- [ ] No errors in startup logs
- [ ] Health check endpoints respond
- [ ] Test conversation works end-to-end

---

#### 5.2 Production Deployment
**Estimated Time:** 2 hours  
**Dependencies:** 5.1  
**Risk Level:** Medium  

**Pre-Deployment Checklist:**
- [ ] All tests passing in CI/CD
- [ ] Staging deployment successful
- [ ] Database migration completed (from M1.3)
- [ ] Rollback plan documented
- [ ] Team availability confirmed

**Deployment Steps:**
```bash
# 1. Create release tag
git tag -a v2.1.0 -m "Add user name storage for group chats"
git push origin v2.1.0

# 2. Deploy code
ssh production-server
cd /opt/whisperengine-v2
git pull origin main
docker-compose build
./bot.sh restart all

# 3. Verify deployment
./bot.sh ps
./bot.sh logs elena --tail 100

# 4. Test in production
# Send test message in low-traffic channel
```

**Acceptance Criteria:**
- [ ] All bot instances restart successfully
- [ ] No errors in production logs
- [ ] Test message processed correctly
- [ ] Names displayed properly in first response

**Rollback Plan:**
```bash
# If critical issues:
git revert HEAD
docker-compose build
./bot.sh restart all
```

---

#### 5.3 Post-Deployment Monitoring
**Estimated Time:** Ongoing (1 week intensive)  
**Dependencies:** 5.2  

**Monitoring Tasks:**

**Day 1-3: Intensive Monitoring**
- [ ] Check logs every 2 hours
- [ ] Monitor error rates in Sentry/logging platform
- [ ] Track database query performance
- [ ] Collect user feedback from Discord

**Day 4-7: Reduced Monitoring**
- [ ] Daily log review
- [ ] Weekly performance report
- [ ] User feedback summary

**Metrics to Track:**

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| Error Rate | < 0.1% | TBD | 🟡 Pending |
| p95 Response Time | < 2s | TBD | 🟡 Pending |
| Messages with user_name | > 95% | TBD | 🟡 Pending |
| User Complaints | 0 | TBD | 🟡 Pending |

**Acceptance Criteria:**
- [ ] Error rate remains low (< 0.1%)
- [ ] No performance regression
- [ ] 95%+ messages have user_name populated
- [ ] Positive user feedback

---

### 🎯 Milestone 6: Documentation & Cleanup
**Duration:** 0.5 day  
**Target Date:** TBD  
**Status:** 📋 Planned  
**Owner:** Documentation Team  

**Tasks:**

#### 6.1 Update Technical Documentation
**Estimated Time:** 1 hour  
**Dependencies:** M5 complete  

**Documents to Update:**

**A. Architecture Documentation**
- [ ] Update `docs/ref/REF-003-MEMORY_SYSTEM.md`
- [ ] Add section on user name storage
- [ ] Update database schema diagrams

**B. API Documentation**
- [ ] Update `src_v2/memory/manager.py` docstrings
- [ ] Document new `user_name` parameter
- [ ] Add usage examples

**C. Migration Log**
- [ ] Document migration process
- [ ] Record any issues encountered
- [ ] List lessons learned

**Files to Update:**
- `docs/ref/REF-003-MEMORY_SYSTEM.md` (if exists)
- `README.md` (update feature list)
- `CHANGELOG.md` (add entry for v2.1.0)

**Acceptance Criteria:**
- [ ] All documentation updated
- [ ] Code comments added where needed
- [ ] Examples provided for new parameters

---

#### 6.2 Clean Up Development Artifacts
**Estimated Time:** 30 minutes  
**Dependencies:** 6.1  

**Cleanup Tasks:**
- [ ] Remove debug logging added during development
- [ ] Delete temporary test data from staging
- [ ] Archive design documents
- [ ] Close related GitHub issues/tickets

**Acceptance Criteria:**
- [ ] No debug code left in production
- [ ] Clean git history
- [ ] All issues marked as resolved

---

#### 6.3 Post-Mortem / Retrospective
**Estimated Time:** 1 hour  
**Dependencies:** 6.2  

**Retrospective Meeting Agenda:**
1. What went well?
2. What could be improved?
3. What did we learn?
4. Action items for next similar project

**Deliverable:** Retrospective document in `docs/retrospectives/`

**Acceptance Criteria:**
- [ ] Team meeting held
- [ ] Notes documented
- [ ] Action items assigned

---

## Timeline Summary

```
Day 1: ┌─────────────────┐
       │ M1: Migration   │
       │ (Database)      │
       └─────────────────┘

Day 2: ┌─────────────────┐ ┌─────────────────┐
       │ M2: Memory Mgr  │ │ M3: Discord Bot │
       └─────────────────┘ └─────────────────┘

Day 3: ┌─────────────────────────────────────┐
       │ M4: Testing & Validation            │
       └─────────────────────────────────────┘

Day 4: ┌─────────────────────────────────────┐
       │ M4: Testing (continued)             │
       └─────────────────────────────────────┘

Day 5: ┌─────────────────┐ ┌─────────────────┐
       │ M5: Staging     │ │ M5: Production  │
       └─────────────────┘ └─────────────────┘

Day 6-7: ┌─────────────────────────────────┐
         │ M5: Monitoring                  │
         │ M6: Documentation               │
         └─────────────────────────────────┘
```

**Total Duration:** 5-7 days (depending on testing thoroughness)

---

## Risk Register

| Risk | Probability | Impact | Mitigation | Owner |
|------|------------|--------|------------|-------|
| Migration fails in production | Low | High | Test on staging; backup before migration | DevOps |
| Performance degradation | Low | Medium | Benchmark before/after; monitor metrics | Backend |
| Unicode encoding issues | Medium | Low | Test with international characters | QA |
| Backward compatibility break | Low | High | Make parameter optional; fallback logic | Backend |
| User confusion (name changes) | Low | Low | Document behavior; it's actually accurate | Product |

---

## Dependencies

### External Dependencies
- ✅ PostgreSQL 14+ (already in use)
- ✅ Alembic migration framework (already in use)
- ✅ Discord.py library (already in use)

### Internal Dependencies
- Database team availability for migration support
- QA team availability for testing
- DevOps team for deployment support

### Blocking Issues
- None currently identified

---

## Success Criteria

### Must Have (P0)
- [x] Design document completed
- [ ] Database migration successful (zero data loss)
- [ ] User names stored for all new messages (100%)
- [ ] Group chat history shows names instead of IDs
- [ ] No performance regression (< 10ms overhead)
- [ ] Zero critical bugs in 7-day monitoring period

### Should Have (P1)
- [ ] Test coverage > 90% for new code
- [ ] Documentation updated
- [ ] User feedback collected
- [ ] Retrospective completed

### Nice to Have (P2)
- [ ] Backfill old messages with "User" (if time permits)
- [ ] Add index on `user_name` column (if query patterns emerge)
- [ ] Rich user context (avatar, roles) - defer to future

---

## Rollout Plan

### Phase 1: Alpha (Internal Testing)
**Duration:** Days 1-3  
**Users:** Development team only  
**Goal:** Validate functionality in controlled environment

### Phase 2: Beta (Staging)
**Duration:** Days 4-5  
**Users:** QA team + select power users  
**Goal:** Find edge cases and performance issues

### Phase 3: Production (Gradual)
**Duration:** Day 5  
**Users:** All users  
**Strategy:** Deploy during low-traffic window (2-4 AM UTC)

### Phase 4: Monitoring
**Duration:** Days 5-12  
**Goal:** Ensure stability and collect feedback

---

## Communication Plan

### Stakeholders
- **Development Team:** Daily standup updates
- **QA Team:** Test results shared in Slack
- **DevOps Team:** Deployment schedule coordinated via calendar
- **End Users:** Announcement in Discord community server (if needed)

### Communication Channels
- **Internal:** Slack #whisperengine-dev channel
- **Technical:** GitHub issues/PRs
- **User-Facing:** Discord announcement (optional, low-impact change)

### Milestone Announcements
- M1 Complete: "Database migration successful"
- M4 Complete: "Testing complete, ready for deployment"
- M5 Complete: "Feature live in production"

---

## Post-Launch

### Week 1: Intensive Monitoring
- Daily log reviews
- Hourly error rate checks
- User feedback collection

### Week 2-4: Normal Monitoring
- Weekly performance reports
- Bi-weekly user feedback summary
- Monthly retrospective

### Future Enhancements
See Future Enhancements section below

**Potential Next Steps:**
1. Rich user context (avatar, roles)
2. Name update on display name change
3. Channel-wide memory search (opt-in)

---

## Resources

### Development Resources
- **Backend Engineer:** 3-4 days
- **QA Engineer:** 2 days
- **DevOps Engineer:** 1 day
- **Documentation:** 0.5 day

### Total Effort
**Estimated:** 6.5-7.5 engineer-days  
**Timeline:** 5-7 calendar days (with parallel work)

### Infrastructure Costs
- Minimal (< $1/month additional storage)
- No new services required
- No compute cost increase expected

---

## Approval & Sign-Off

### Approvals Required
- [ ] Technical Lead: Design review
- [ ] Product Manager: Feature acceptance
- [ ] Database Admin: Migration plan approval
- [ ] QA Lead: Test plan approval

### Sign-Off
- [ ] All milestones completed
- [ ] Success criteria met
- [ ] Documentation updated
- [ ] Retrospective held

---

## Appendix: Commands Quick Reference

### Development
```bash
# Create migration
alembic revision --autogenerate -m "add_user_name_to_chat_history"

# Apply migration
alembic upgrade head

# Rollback migration
alembic downgrade -1

# Run tests
pytest tests_v2/test_memory_manager.py -v
pytest tests_v2/test_group_chat_integration.py -v
```

### Deployment
```bash
# Staging
./bot.sh down all
git pull origin feature/user-name-storage
docker-compose build
./bot.sh up all

# Production
git tag v2.1.0
./bot.sh restart all
./bot.sh logs elena -f
```

### Monitoring
```bash
# Check logs
./bot.sh logs elena --tail 100

# Database query
psql -c "SELECT COUNT(*), user_name 
         FROM v2_chat_history 
         WHERE timestamp > NOW() - INTERVAL '1 day' 
         GROUP BY user_name;"

# Error rate
grep ERROR logs/discord.log | wc -l
```

---

**Document Version:** 1.0  
**Created:** November 23, 2025  
**Last Updated:** November 23, 2025  
**Status:** Approved for Implementation  
**Next Review:** After Milestone 3 completion
