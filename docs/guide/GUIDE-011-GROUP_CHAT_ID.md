# User Identification in Group Chats - Design Document

**Status**: ✅ Implemented  
**Priority**: High  
**Version**: 2.2  
**Last Updated**: December 1, 2025

## Problem Statement

### Current Behavior
In multi-user Discord channels, the bot identifies other participants in conversation history by their raw Discord User ID rather than their display name. This significantly degrades the bot's ability to understand and participate in group conversations.

**Example of Current Output (What the LLM sees):**
```
Recent Conversation History:
[User 123456789012345]: I think we should use React for this project
[User 987654321098765]: I disagree, Vue is better
[User 456789012345678]: What does the bot think?
```

**What the LLM Should See:**
```
Recent Conversation History:
[Sarah]: I think we should use React for this project
[Mike]: I disagree, Vue is better
[Alex]: What does the bot think?
```

### Impact

#### User Experience Issues:
- ❌ Bot cannot reference specific users by name in group contexts
- ❌ Impossible for bot to say "As Sarah mentioned earlier..." 
- ❌ Bot appears context-unaware in multi-user conversations
- ❌ Users must explicitly mention names in their messages for bot to understand
- ❌ Degrades natural conversation flow in channels

#### Technical Limitations:
- Bot cannot correlate user names mentioned in text with speakers in history
- Semantic understanding of "who said what" is broken
- Group chat functionality is severely hampered compared to 1:1 DM experience

### Root Cause

**Code Location:** `src_v2/memory/manager.py:346`

```python
# In get_recent_history():
if channel_id and row['user_id'] != str(user_id):
    content = f"[User {row['user_id']}]: {content}"  # ❌ Uses numeric ID
```

**Why This Happens:**
1. Database table `v2_chat_history` only stores `user_id` (Discord snowflake ID)
2. No `user_name` or `display_name` column exists in schema
3. History retrieval has no access to Discord API to resolve IDs to names
4. Bot assumes all conversations are 1:1 (legacy design from DM-focused prototype)

## Requirements

### Functional Requirements

**FR-1: Display Name Storage**
- System MUST store user display names alongside user IDs when messages are saved
- Display names MUST be captured at the time of message creation
- Storage MUST support NULL values for backward compatibility with existing data

**FR-2: History Formatting**
- Group chat history MUST format messages with human-readable names
- Format MUST clearly distinguish between different speakers
- Format MUST distinguish current user from other participants

**FR-3: Backward Compatibility**
- System MUST continue to work with existing messages that lack display names
- Fallback behavior MUST be defined for NULL or missing names
- No existing functionality may be broken

**FR-4: Performance**
- Name retrieval MUST NOT introduce significant latency (< 10ms overhead)
- No additional network calls to Discord API during history retrieval
- Database queries MUST remain efficient (indexed appropriately)

### Non-Functional Requirements

**NFR-1: Data Consistency**
- Names stored represent the display name at the time of message
- Historical accuracy is preserved (names don't retroactively change)
- Character encoding must support Unicode (emoji, international characters)

**NFR-2: Privacy**
- Existing privacy model (user-scoped memories) remains unchanged
- No new cross-user data leakage vectors introduced
- Display names only visible within the channel context where they were used

**NFR-3: Maintainability**
- Changes must be isolated to memory management subsystem
- Clear migration path for database schema changes
- Tests must be added for new functionality

## Proposed Solution

### Option 1: Store Display Names in Database ⭐ RECOMMENDED

**Architecture:**

```
┌─────────────────────────────────────────────────────────────┐
│                     Discord Message Event                    │
│  message.author.id + message.author.display_name             │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              memory_manager.add_message()                    │
│  Stores: user_id, user_name, content, role, channel_id      │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  PostgreSQL: v2_chat_history                 │
│                                                               │
│  ┌─────────┬─────────────┬──────────┬──────┬─────────────┐ │
│  │ user_id │  user_name  │ content  │ role │ channel_id  │ │
│  ├─────────┼─────────────┼──────────┼──────┼─────────────┤ │
│  │ 123...  │ "Sarah"     │ "Hello"  │ human│ 999...      │ │
│  │ 456...  │ "Mike"      │ "Hi!"    │ human│ 999...      │ │
│  │ NULL    │ NULL        │ "Hey"    │ ai   │ 999...      │ │
│  └─────────┴─────────────┴──────────┴──────┴─────────────┘ │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│           memory_manager.get_recent_history()                │
│  Formats: "[Sarah]: Hello" or "[Mike]: Hi!"                  │
└─────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    Agent Engine (LLM)                        │
│  Receives properly formatted multi-user conversation history │
└─────────────────────────────────────────────────────────────┘
```

**Pros:**
- ✅ **Performance:** No runtime API calls, instant retrieval (< 1ms overhead)
- ✅ **Reliability:** Works even when users leave servers or change nicknames
- ✅ **Simplicity:** Clean implementation, no external dependencies
- ✅ **Historical Accuracy:** Preserves names as they were at message time
- ✅ **Scalability:** Minimal storage cost (~20-50 bytes per message)
- ✅ **Offline Support:** No dependency on Discord API availability

**Cons:**
- ❌ Requires database migration (low risk, standard procedure)
- ❌ Names become "frozen" at message time (feature, not bug)
- ❌ Slight storage overhead (negligible ~0.5% increase)

**Storage Impact:**
- Average display name: 15 characters × 2 bytes (UTF-8) = 30 bytes
- 1 million messages × 30 bytes = 30 MB additional storage
- Current database: ~500 MB → New total: ~530 MB (6% increase)
- Cost: Negligible ($0.01/month on typical cloud PostgreSQL)

---

### Option 2: Runtime Discord API Lookup ❌ NOT RECOMMENDED

**Architecture:**

```
┌─────────────────────────────────────────────────────────────┐
│           memory_manager.get_recent_history()                │
│  Retrieves: user_id, content, role from database            │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              For Each Unique user_id in History:             │
│         discord_client.fetch_member(user_id) ❌              │
│              (50-200ms per API call)                         │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│           Format Messages with Retrieved Names               │
└─────────────────────────────────────────────────────────────┘
```

**Pros:**
- ✅ No database schema changes required
- ✅ Always shows current/updated display names
- ✅ Respects nickname changes immediately

**Cons:**
- ❌ **Performance Penalty:** 50-200ms+ latency per unique user
- ❌ **Rate Limiting:** Discord API has strict limits (50 requests/second)
- ❌ **Failure Cases:** Users who left server become unresolvable
- ❌ **Complexity:** Requires caching layer to avoid repeated lookups
- ❌ **Dependency:** Breaks if Discord API is unavailable
- ❌ **Architecture Violation:** Couples memory layer to Discord API

**Performance Calculation:**
- 10 messages in history with 3 unique users
- 3 API calls × 100ms = 300ms additional latency
- 50x slower than Option 1
- Unacceptable for real-time chat experience

---

### Option 3: In-Memory Cache with Periodic Updates ⚠️ OVER-ENGINEERED

**Architecture:**

```
┌─────────────────────────────────────────────────────────────┐
│                     Redis Cache Layer                        │
│  user_id → display_name mapping (TTL: 1 hour)               │
└───────────────────────┬─────────────────────────────────────┘
                        │
                   Cache Miss? 
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│        Fallback: Discord API fetch_member()                  │
│            (with exponential backoff)                        │
└─────────────────────────────────────────────────────────────┘
```

**Pros:**
- ✅ Fast lookups after cache warm-up (< 5ms)
- ✅ No database schema changes
- ✅ Can update names periodically

**Cons:**
- ❌ **Infrastructure Complexity:** Requires Redis or similar
- ❌ **Cache Invalidation:** Difficult to get right
- ❌ **Cold Start:** Still needs initial API calls
- ❌ **Cache Misses:** Unpredictable performance
- ❌ **Operational Overhead:** Another service to monitor/maintain
- ❌ **Cost:** Additional infrastructure ($10-50/month)
- ❌ **Overkill:** Solving a simple problem with complex infrastructure

---

### Option 4: Hybrid - Store + Update ⚠️ ADDED COMPLEXITY

**Architecture:**
Combines Option 1 (storage) with periodic background updates to keep names current.

**Pros:**
- ✅ Fast retrieval like Option 1
- ✅ Reasonably current names (updated on next message)

**Cons:**
- ❌ Same migration effort as Option 1
- ❌ Additional complexity for minimal benefit
- ❌ Names in old conversations remain outdated until user speaks
- ❌ Update logic adds code maintenance burden

---

## Decision: Option 1 (Store Display Names)

### Rationale

**Performance:** Sub-millisecond retrieval vs. 100-300ms for API calls  
**Reliability:** 100% success rate vs. dependent on external API  
**Simplicity:** Single migration vs. complex caching/API integration  
**Cost:** Negligible storage vs. additional infrastructure  
**Maintainability:** Isolated change vs. distributed complexity  

### Trade-offs Accepted

**Frozen Names:** We accept that display names are captured at message time and don't retroactively update. This is actually desirable for historical accuracy.

**Example:**
```
Monday: User changes name from "Sarah" to "Sarah_Away"
Bot's memory of Monday's messages: Still shows "Sarah"
Bot's memory of Tuesday's messages: Shows "Sarah_Away"
```

This reflects reality: historical conversations show names as they were at the time.

## Implementation Plan

### Phase 1: Database Schema Migration

**Timeline:** Day 1  
**Risk:** Low (standard additive migration)

**Tasks:**
1. Create Alembic migration file: `20251123_XXXX_add_user_name_to_history.py`
2. Add `user_name TEXT` column (nullable for backward compatibility)
3. Backfill existing records with placeholder "User" for NULL values
4. Test migration on staging database
5. Deploy to production during low-traffic window

**Migration Script:**
```python
def upgrade():
    # Add column
    op.add_column('v2_chat_history', 
                  sa.Column('user_name', sa.Text(), nullable=True))
    
    # Backfill existing records
    op.execute("""
        UPDATE v2_chat_history 
        SET user_name = 'User' 
        WHERE user_name IS NULL AND role = 'human'
    """)
    
    # Optional: Add index if querying by name becomes common
    # op.create_index('idx_v2_chat_history_user_name', 
    #                 'v2_chat_history', ['user_name'])

def downgrade():
    op.drop_column('v2_chat_history', 'user_name')
```

---

### Phase 2: Update Memory Manager

**Timeline:** Day 1-2  
**Risk:** Low (backward compatible changes)

**Changes Required:**

**File:** `src_v2/memory/manager.py`

**A. Update `add_message()` signature:**
```python
async def add_message(
    self, 
    user_id: str, 
    character_name: str, 
    role: str, 
    content: str, 
    user_name: Optional[str] = None,  # NEW PARAMETER
    channel_id: Optional[str] = None, 
    message_id: Optional[str] = None, 
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Adds a message to the history.
    
    Args:
        user_id: Discord user ID
        character_name: Character bot name
        role: 'human' or 'ai'
        content: Message content
        user_name: Display name of the user (NEW)
        channel_id: Discord channel ID (for group context)
        message_id: Discord message ID (for reference)
        metadata: Additional metadata for vector storage
    """
```

**B. Update SQL INSERT:**
```python
await conn.execute("""
    INSERT INTO v2_chat_history 
    (user_id, character_name, role, content, user_name, channel_id, message_id)
    VALUES ($1, $2, $3, $4, $5, $6, $7)
""", 
    str(user_id), 
    character_name, 
    role, 
    content, 
    user_name or "User",  # Fallback to "User" if not provided
    str(channel_id) if channel_id else None, 
    str(message_id) if message_id else None
)
```

**C. Update `get_recent_history()` query:**
```python
if channel_id:
    rows = await conn.fetch("""
        SELECT role, content, user_id, user_name 
        FROM v2_chat_history 
        WHERE channel_id = $1 AND character_name = $2
        ORDER BY timestamp DESC
        LIMIT $3
    """, str(channel_id), character_name, limit)
else:
    rows = await conn.fetch("""
        SELECT role, content, user_id, user_name 
        FROM v2_chat_history 
        WHERE user_id = $1 AND character_name = $2
        ORDER BY timestamp DESC
        LIMIT $3
    """, str(user_id), character_name, limit)
```

**D. Update history formatting logic:**
```python
for row in reversed(rows):
    if row['role'] == 'human':
        content = row['content']
        
        # In group contexts, distinguish other users by name
        if channel_id and row['user_id'] != str(user_id):
            display_name = row['user_name'] or f"User {row['user_id']}"
            content = f"[{display_name}]: {content}"
            
        messages.append(HumanMessage(content=content))
    elif row['role'] == 'ai':
        messages.append(AIMessage(content=row['content']))
```

---

### Phase 3: Update Discord Bot Integration

**Timeline:** Day 2  
**Risk:** Low (simple parameter addition)

**File:** `src_v2/discord/bot.py`

**Change 1: User Message Storage (Line ~526)**
```python
# Current:
await memory_manager.add_message(
    user_id, character.name, 'human', user_message, 
    channel_id=channel_id, 
    message_id=str(message.id)
)

# Updated:
await memory_manager.add_message(
    user_id, 
    character.name, 
    'human', 
    user_message, 
    user_name=message.author.display_name,  # ✅ ADD THIS
    channel_id=channel_id, 
    message_id=str(message.id)
)
```

**Change 2: AI Response Storage (Line ~671)**
```python
# Current:
await memory_manager.add_message(
    user_id, 
    character.name, 
    'ai', 
    response, 
    channel_id=channel_id, 
    message_id=str(sent_messages[-1].id)
)

# Updated:
await memory_manager.add_message(
    user_id, 
    character.name, 
    'ai', 
    response, 
    user_name=None,  # AI doesn't need a display name
    channel_id=channel_id, 
    message_id=str(sent_messages[-1].id)
)
```

---

### Phase 4: Testing

**Timeline:** Day 2-3  
**Risk:** Medium (requires comprehensive testing)

**Test Cases:**

**TC-1: Backward Compatibility**
```python
async def test_history_with_null_names():
    """Verify system handles existing messages without user_name"""
    # Retrieve history from before migration
    history = await memory_manager.get_recent_history(
        user_id="123", 
        character_name="elena", 
        channel_id="999"
    )
    # Should show "[User 456]: message" for old messages
    assert "[User" in history[0].content
```

**TC-2: New Messages with Names**
```python
async def test_new_messages_store_names():
    """Verify new messages store display names"""
    await memory_manager.add_message(
        user_id="123",
        character_name="elena",
        role="human",
        content="Hello",
        user_name="Sarah",
        channel_id="999"
    )
    
    history = await memory_manager.get_recent_history(
        user_id="123",
        character_name="elena", 
        channel_id="999"
    )
    # Should show "[Sarah]: Hello" for current user's messages
    # (not prefixed since it's their message)
```

**TC-3: Multi-User Group Chat**
```python
async def test_group_chat_name_formatting():
    """Verify different users show different names in group context"""
    # Simulate 3-user conversation in channel "999"
    await memory_manager.add_message("111", "elena", "human", "Hi", 
                                     user_name="Alice", channel_id="999")
    await memory_manager.add_message("222", "elena", "human", "Hey", 
                                     user_name="Bob", channel_id="999")
    await memory_manager.add_message("333", "elena", "human", "Hello", 
                                     user_name="Charlie", channel_id="999")
    
    # Retrieve from Alice's perspective
    history = await memory_manager.get_recent_history("111", "elena", 
                                                       channel_id="999")
    
    # Alice's message should NOT have prefix
    # Bob and Charlie's messages SHOULD have name prefix
    assert "Hi" in history[0].content and "[" not in history[0].content
    assert "[Bob]: Hey" in history[1].content
    assert "[Charlie]: Hello" in history[2].content
```

**TC-4: DM Context (No Name Prefix)**
```python
async def test_dm_context_no_prefix():
    """Verify DM conversations don't show name prefixes"""
    await memory_manager.add_message("123", "elena", "human", "Hi", 
                                     user_name="Sarah", channel_id=None)
    
    history = await memory_manager.get_recent_history("123", "elena", 
                                                       channel_id=None)
    
    # In DM context, no name prefix should appear
    assert history[0].content == "Hi"
    assert "[Sarah]" not in history[0].content
```

**TC-5: Unicode Display Names**
```python
async def test_unicode_display_names():
    """Verify system handles emoji and international characters"""
    await memory_manager.add_message("123", "elena", "human", "Test", 
                                     user_name="Sarah 🎉", channel_id="999")
    await memory_manager.add_message("456", "elena", "human", "Test", 
                                     user_name="田中さん", channel_id="999")
    
    history = await memory_manager.get_recent_history("123", "elena", 
                                                       channel_id="999")
    
    assert "[田中さん]: Test" in history[1].content
```

**TC-6: Very Long Display Names**
```python
async def test_long_display_names():
    """Verify system handles Discord's max display name length"""
    long_name = "A" * 32  # Discord max is 32 characters
    await memory_manager.add_message("123", "elena", "human", "Test", 
                                     user_name=long_name, channel_id="999")
    
    history = await memory_manager.get_recent_history("456", "elena", 
                                                       channel_id="999")
    
    assert f"[{long_name}]: Test" in history[0].content
```

---

### Phase 5: Deployment

**Timeline:** Day 3  
**Risk:** Low (gradual rollout)

**Deployment Strategy:**

**Step 1: Staging Environment**
- Deploy migration to staging
- Run full test suite
- Manual QA with multi-user test scenarios

**Step 2: Production Migration Window**
- Schedule during low-traffic period (e.g., 2 AM UTC)
- Put bot in maintenance mode (optional)
- Run migration: `alembic upgrade head`
- Verify migration success
- Monitor for errors

**Step 3: Code Deployment**
- Deploy updated bot code
- Monitor logs for errors
- Test with small group of users
- Gradual rollout to all instances

**Rollback Plan:**
If critical issues arise:
1. Revert code to previous version
2. Run migration downgrade: `alembic downgrade -1`
3. Restore from database backup if needed

---

### Phase 6: Monitoring & Validation

**Timeline:** Day 3-7 (ongoing)  
**Risk:** Low

**Metrics to Monitor:**

1. **Database Performance:**
   - Query latency for `get_recent_history()` (should remain < 10ms)
   - Storage growth rate (should be ~6% increase)

2. **Functional Correctness:**
   - Percentage of messages with non-null `user_name` (should trend to 100%)
   - No errors in logs related to name formatting

3. **User Experience:**
   - User feedback in Discord channels
   - Bot's ability to reference users by name in responses

**Success Criteria:**
- ✅ 0 critical errors in 7-day monitoring period
- ✅ 95%+ of new messages have `user_name` populated
- ✅ No performance degradation in response times
- ✅ Positive user feedback on group chat interactions

---

## Future Enhancements

### Enhancement 1: Name Update on Display Name Change

**Concept:** When a user changes their display name, update it in recent messages.

**Implementation:**
```python
# On Discord member_update event:
async def on_member_update(before, after):
    if before.display_name != after.display_name:
        # Update last N messages from this user
        await memory_manager.update_user_name(
            user_id=str(after.id),
            old_name=before.display_name,
            new_name=after.display_name,
            limit=100  # Only update recent messages
        )
```

**Decision:** Defer for now (not critical, adds complexity)

---

### Enhancement 2: Rich User Context

**Concept:** Store additional user metadata (avatar, roles, status).

**Schema:**
```sql
ALTER TABLE v2_chat_history 
ADD COLUMN user_metadata JSONB;

-- Store:
{
  "display_name": "Sarah",
  "avatar_url": "https://...",
  "roles": ["Admin", "Moderator"],
  "status": "online"
}
```

**Use Case:** Bot could say "Sarah (Admin) mentioned..." or format responses differently for admins.

**Decision:** Defer (nice-to-have, not essential)

---

### Enhancement 3: Channel-Wide Memory Search

**Concept:** Allow bot to search memories from all users in a channel (opt-in).

**Current Behavior:**
- Bot searches memories → only retrieves current user's messages
- Bot cannot recall what other users said in the same channel

**Proposed Behavior:**
```python
async def search_memories(
    query: str, 
    user_id: str, 
    channel_id: str = None,
    include_channel_context: bool = False  # NEW
):
    if include_channel_context and channel_id:
        # Search all users' messages in this channel
        search_filter = Filter(
            should=[
                FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                FieldCondition(key="channel_id", match=MatchValue(value=channel_id))
            ]
        )
```

**Privacy Implications:** Must be opt-in per server/channel.

**Decision:** Track in separate design doc (see [CHANNEL_MEMORY_SHARING.md](./CHANNEL_MEMORY_SHARING.md))

---

## Risks & Mitigations

### Risk 1: Migration Failure

**Probability:** Low  
**Impact:** High (bot offline during rollback)

**Mitigation:**
- Test migration thoroughly on staging replica of production DB
- Schedule during low-traffic window
- Have rollback plan ready
- Take database backup before migration

---

### Risk 2: Performance Degradation

**Probability:** Low  
**Impact:** Medium (slower response times)

**Mitigation:**
- Benchmark query performance before/after
- `user_name` column is TEXT (efficient storage)
- No additional joins needed (denormalized design)
- Monitor query latency in production

---

### Risk 3: Unicode/Encoding Issues

**Probability:** Medium  
**Impact:** Low (display issues only)

**Mitigation:**
- PostgreSQL default UTF-8 encoding handles Unicode
- Test with emoji and international characters
- Graceful fallback to user ID if name can't be displayed

---

### Risk 4: Backward Compatibility Break

**Probability:** Low  
**Impact:** High (existing integrations broken)

**Mitigation:**
- `user_name` parameter is optional (default: None)
- Existing code continues to work without changes
- API/test code can adopt gradually
- Fallback to "User" for NULL values

---

## Success Metrics

### Primary Metrics

**M1: Functional Correctness**
- Target: 100% of group chat messages show display names (not IDs)
- Measurement: Sample 100 random messages from logs
- Timeline: Within 7 days of deployment

**M2: User Satisfaction**
- Target: Positive feedback in user channels
- Measurement: Discord reactions, qualitative feedback
- Timeline: Within 14 days of deployment

**M3: No Performance Regression**
- Target: < 10ms overhead for history retrieval
- Measurement: Application Performance Monitoring (APM) metrics
- Timeline: Continuous monitoring for 30 days

### Secondary Metrics

**M4: Data Quality**
- Target: 95%+ of messages have non-null `user_name`
- Measurement: Database query
- Timeline: Within 30 days of deployment

**M5: Zero Critical Bugs**
- Target: 0 P0/P1 bugs related to this feature
- Measurement: Issue tracker
- Timeline: 30 days post-deployment

---

## Appendix A: Database Schema

### Before Migration
```sql
CREATE TABLE v2_chat_history (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    character_name TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    channel_id TEXT,
    message_id TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_v2_chat_history_user_char (user_id, character_name),
    INDEX idx_v2_chat_history_channel (channel_id),
    INDEX idx_v2_chat_history_message_id (message_id) UNIQUE
);
```

### After Migration
```sql
CREATE TABLE v2_chat_history (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    character_name TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    user_name TEXT,  -- ✅ NEW COLUMN
    channel_id TEXT,
    message_id TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_v2_chat_history_user_char (user_id, character_name),
    INDEX idx_v2_chat_history_channel (channel_id),
    INDEX idx_v2_chat_history_message_id (message_id) UNIQUE
);
```

---

## Appendix B: Example Conversations

### Before Fix
```
User: @bot, what did Sarah say about React?
Bot: I don't see anyone named Sarah in our conversation history.

[What the bot actually saw:]
Recent History:
- [User 123456789012345]: I think we should use React
- [User 987654321098765]: I prefer Vue
```

### After Fix
```
User: @bot, what did Sarah say about React?
Bot: Sarah mentioned she thinks we should use React for the project. 
     Mike disagreed and said he prefers Vue. What do you think?

[What the bot now sees:]
Recent History:
- [Sarah]: I think we should use React
- [Mike]: I prefer Vue
```

---

## References

- **Privacy Document:** [docs/PRIVACY_AND_DATA_SEGMENTATION.md](../PRIVACY_AND_DATA_SEGMENTATION.md)
- **Database Schema:** [migrations_v2/versions/](../../migrations_v2/versions/)
- **Memory Manager:** [src_v2/memory/manager.py](../../src_v2/memory/manager.py)
- **Discord Bot:** [src_v2/discord/bot.py](../../src_v2/discord/bot.py)

---

**Document Version:** 1.0  
**Last Updated:** November 23, 2025  
**Status:** Awaiting Approval  
**Next Review:** Before implementation begins
