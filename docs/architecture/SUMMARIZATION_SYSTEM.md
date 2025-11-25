# Summarization System - Memory Consolidation

## Multi-Modal Context: Sleep for AI

Summarization is **memory consolidation** - the analog of what human brains do during sleep. Just as humans compress daily experiences into long-term memories, characters compress conversation histories into dense summaries.

| Human Process | Character Process |
|---------------|-------------------|
| Sleep/dreaming | Summarization trigger |
| Memory consolidation | Raw messages → compressed summary |
| Forgetting details | Individual messages pruned |
| Retaining meaning | Semantic essence preserved |

This is how characters develop genuine **continuity of experience** - they don't just store raw data, they *process* it into meaningful memories.

For full philosophy: See [`MULTI_MODAL_PERCEPTION.md`](./MULTI_MODAL_PERCEPTION.md)

---

## Overview

WhisperEngine v2's summarization system automatically compresses long conversation histories into dense, semantically-rich summaries. This prevents context window overflow, reduces LLM costs, and enables long-term memory spanning months or years of conversation.

## Architecture

### Core Components

1. **SummaryManager** (`src_v2/memory/summarizer.py`): Orchestrates summarization
2. **PostgreSQL**: Stores conversation summaries in `v2_conversation_summaries` table
3. **Qdrant**: Stores summary embeddings for semantic search
4. **Trigger System**: Automatic summarization based on message count thresholds

## When Summarization Triggers

### Automatic Triggers

**Location**: `src_v2/memory/summarizer.py:_check_and_summarize()`

```python
# Called after every message save
await summary_manager._check_and_summarize(
    session_id=session_id,
    user_id=user_id
)

# Threshold logic
messages_since_summary = await self._count_messages_since_last_summary(session_id)

if messages_since_summary >= self.threshold:  # Default: 20 messages
    await self._create_summary(session_id, user_id)
```

### Manual Triggers

Users can also manually trigger summarization:
```python
await summary_manager.create_summary(session_id, user_id)
```

### Configuration

```bash
# In .env files
SUMMARY_THRESHOLD=20           # Messages before auto-summarization
SUMMARY_MAX_MESSAGES=50        # Max messages to include in one summary
SUMMARY_OVERLAP=5              # Messages to overlap between summaries
```

## Complete Summarization Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                  MESSAGE COUNT THRESHOLD HIT                     │
│                  (20 messages since last summary)                │
└───────────────────────┬──────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 1: MESSAGE COLLECTION                                     │
│  Location: src_v2/memory/summarizer.py:_create_summary()         │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 1.1 Query PostgreSQL for Recent Messages                  │ │
│  │                                                             │ │
│  │ SELECT * FROM v2_chat_history                              │ │
│  │ WHERE session_id = $session_id                             │ │
│  │   AND id > (SELECT last_message_id                         │ │
│  │              FROM v2_conversation_summaries                │ │
│  │              WHERE session_id = $session_id                │ │
│  │              ORDER BY created_at DESC LIMIT 1)             │ │
│  │ ORDER BY timestamp ASC                                     │ │
│  │ LIMIT $SUMMARY_MAX_MESSAGES  -- Default: 50                │ │
│  └────────────────────────────────────────────────────────────┘ │
│                        │                                          │
│                        ▼                                          │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 1.2 Format Messages for LLM                                │ │
│  │                                                             │ │
│  │ conversation_text = ""                                     │ │
│  │ for msg in messages:                                       │ │
│  │     role = "User" if msg.role == "user" else "Bot"        │ │
│  │     conversation_text += f"{role}: {msg.content}\n"       │ │
│  │                                                             │ │
│  │ Example output:                                            │ │
│  │ User: Hey, how are you?                                    │ │
│  │ Bot: I'm doing well! How about you?                        │ │
│  │ User: Pretty good. I got a new job!                        │ │
│  │ Bot: That's amazing! Congratulations! ...                  │ │
│  │ [... 17 more messages ...]                                 │ │
│  └────────────────────────────────────────────────────────────┘ │
└───────────────────────┬──────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 2: LLM SUMMARIZATION                                      │
│  Location: src_v2/memory/summarizer.py:_generate_summary()       │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 2.1 Construct Summarization Prompt                         │ │
│  │                                                             │ │
│  │ System Prompt:                                             │ │
│  │ "You are a memory compression system for an AI character.  │ │
│  │  Your task is to create a dense, semantic summary of       │ │
│  │  conversation history.                                     │ │
│  │                                                             │ │
│  │  Requirements:                                             │ │
│  │  - Capture key facts, events, and emotional context       │ │
│  │  - Preserve important details (names, dates, numbers)      │ │
│  │  - Note relationship developments or mood shifts          │ │
│  │  - Identify topics discussed                               │ │
│  │  - Rate conversation meaningfulness (1-5)                  │ │
│  │  - Keep summary under 500 words                            │ │
│  │                                                             │ │
│  │  Format:                                                   │ │
│  │  ## Metadata                                               │ │
│  │  - Meaningfulness: [1-5]                                   │ │
│  │  - Emotions: [Emotion 1], [Emotion 2]                      │ │
│  │                                                             │ │
│  │  ## Topics                                                 │ │
│  │  - [Topic 1]                                               │ │
│  │  - [Topic 2]                                               │ │
│  │                                                             │ │
│  │  ## Key Events                                             │ │
│  │  - [Event 1]                                               │ │
│  │  - [Event 2]                                               │ │
│  │                                                             │ │
│  │  ## Emotional Context                                      │ │
│  │  User was [mood/emotion]. [Details]                        │ │
│  │                                                             │ │
│  │  ## Important Details                                      │ │
│  │  - [Detail 1]                                              │ │
│  │  - [Detail 2]"                                             │ │
│  │                                                             │ │
│  │ User Message:                                              │ │
│  │ "Summarize this conversation:\n\n{conversation_text}"     │ │
│  └────────────────────────────────────────────────────────────┘ │
│                        │                                          │
│                        ▼                                          │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 2.2 LLM Generation                                         │ │
│  │                                                             │ │
│  │ Model: GPT-4o-mini (fast + cheap for summaries)           │ │
│  │ Temperature: 0.3 (factual, consistent)                     │ │
│  │ Max Tokens: 1000                                           │ │
│  │                                                             │ │
│  │ Cost: ~$0.001-0.003 per summary                            │ │
│  │ Latency: ~2-5 seconds                                      │ │
│  └────────────────────────────────────────────────────────────┘ │
└───────────────────────┬──────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 3: METADATA EXTRACTION                                    │
│  Location: src_v2/memory/summarizer.py:_extract_metadata()       │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 3.1 Parse Summary for Structured Data                      │ │
│  │                                                             │ │
│  │ topics = extract_topics(summary_text)                      │ │
│  │ # Uses regex or LLM to find topic headings                 │ │
│  │ # Example: ["work", "hobbies", "weekend plans"]            │ │
│  │                                                             │ │
│  │ key_facts = extract_key_facts(summary_text)                │ │
│  │ # Example: ["User got new job", "User has cat named        │ │
│  │ #            Whiskers", "User planning trip to Japan"]     │ │
│                                                             │
│  meaningfulness = extract_score(summary_text)               │
│  # 1 (Small talk) -> 5 (Deep/Life-changing)                 │
│                                                             │
│  emotions = extract_emotions(summary_text)                  │
│  # ["excited", "nervous", "hopeful"]                        │ │
│  └────────────────────────────────────────────────────────────┘ │
│                        │                                          │
│                        ▼                                          │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 3.2 Calculate Time Range                                   │ │
│  │                                                             │ │
│  │ start_time = messages[0].timestamp                         │ │
│  │ end_time = messages[-1].timestamp                          │ │
│  │ duration = end_time - start_time                           │ │
│  └────────────────────────────────────────────────────────────┘ │
└───────────────────────┬──────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────┐
│  PHASE 4: STORAGE                                                │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 4.1 Save to PostgreSQL                                     │ │
│  │                                                             │ │
│  │ INSERT INTO v2_conversation_summaries (                    │ │
│  │     session_id,                                            │ │
│  │     user_id,                                               │ │
│  │     summary_text,                                          │ │
│  │     start_message_id,                                      │ │
│  │     end_message_id,                                        │ │
│  │     message_count,                                         │ │
│  │     topics,           -- JSONB array                       │ │
│  │     key_facts,        -- JSONB array                       │ │
│  │     sentiment,                                             │ │
│  │     time_range_start,                                      │ │
│  │     time_range_end,                                        │ │
│  │     created_at                                             │ │
│  │ ) VALUES (...)                                             │ │
│  └────────────────────────────────────────────────────────────┘ │
│                        │                                          │
│                        ▼                                          │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 4.2 Generate Embedding                                     │ │
│  │                                                             │ │
│  │ embedding = await embedding_service.embed_query_async(     │ │
│  │     summary_text                                           │ │
│  │ )                                                           │ │
│  │ # 384D vector from all-MiniLM-L6-v2                        │ │
│  └────────────────────────────────────────────────────────────┘ │
│                        │                                          │
│                        ▼                                          │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 4.3 Store in Qdrant                                        │ │
│  │                                                             │ │
│  │ await qdrant_client.upsert(                                │ │
│  │     collection_name="whisperengine_memory_{bot_name}",     │ │
│  │     points=[PointStruct(                                   │ │
│  │         id=summary_id,                                     │ │
│  │         vector=embedding,                                  │ │
│  │         payload={                                          │ │
│  │             "type": "summary",                             │ │
│  │             "summary_text": summary_text,                  │ │
│  │             "topics": topics,                              │ │
│  │             "key_facts": key_facts,                        │ │
│  │             "meaningfulness_score": meaningfulness,        │ │
│  │             "emotions": emotions,                          │ │
│  │             "time_range": {                                │ │
│  │                 "start": start_time.isoformat(),           │ │
│  │                 "end": end_time.isoformat()                │ │
│  │             },                                              │ │
│  │             "message_count": len(messages)                 │ │
│  │         }                                                   │ │
│  │     )]                                                      │ │
│  │ )                                                           │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

## Summary Retrieval

### During Context Building

**Location**: `src_v2/discord/bot.py:on_message()` (Phase 2: Context Retrieval)

```python
# Retrieve past summaries for context
past_summaries = await memory_manager.search_summaries(
    user_id=user_id,
    query=user_message,
    limit=3,
    time_range="all"
)

# Add to system prompt
context_vars["past_summaries"] = "\n\n".join([
    f"[{s.time_range_start.strftime('%Y-%m-%d')}] {s.summary_text}"
    for s in past_summaries
])
```

### Search Methods

**1. Semantic Search** (Most common):
```python
# Find summaries related to query
summaries = await memory_manager.search_summaries(
    user_id=user_id,
    query="work stress",  # Embedded and compared to summary vectors
    limit=5
)
```

**2. Time-Based Retrieval**:
```python
# Get summaries from specific period
summaries = await memory_manager.get_summaries_by_timerange(
    user_id=user_id,
    start_date=datetime(2025, 10, 1),
    end_date=datetime(2025, 10, 31)
)
```

**3. Topic Filtering**:
```python
# Find summaries about specific topic
summaries = await memory_manager.get_summaries_by_topic(
    user_id=user_id,
    topic="relationships"
)
```

## Example Summary

### Input Conversation (20 messages)
```
User: Hey Elena, I got some news today
Elena: Oh? What happened?
User: I got the promotion I applied for!
Elena: That's amazing! Congratulations! I know you worked hard for that
User: Thanks! I'm excited but also nervous
Elena: That's totally normal. What are you nervous about?
User: The new responsibilities. I'll be managing a team of 5 people
Elena: That's a big step! Have you managed people before?
User: Not really. Just small projects with 1-2 people
Elena: You'll do great. What does the role involve?
User: Leading the marketing team, bigger budget, reporting to the CMO
Elena: That sounds like a great opportunity. When do you start?
User: In two weeks. They're giving me time to wrap up current projects
Elena: Smart. Are you worried about anything specific?
User: Yeah, I'm worried about being too young. I'm only 28
Elena: Age doesn't define leadership ability. Your skills got you here
User: You're right. Thanks for the pep talk
Elena: Anytime! We should celebrate. What are you thinking?
User: Maybe dinner with friends this weekend
Elena: Perfect! You deserve it 🎉
```

### Generated Summary
```markdown
## Topics
- Career advancement (promotion)
- New leadership role
- Self-doubt and confidence

## Key Events
- User received promotion to team lead role in marketing
- New position involves managing 5-person team with larger budget
- Reports to CMO starting in two weeks
- User is 28 years old
- Planning celebration dinner with friends this weekend

## Emotional Context
User was excited and proud about the promotion but also experiencing nervousness about new responsibilities. Primary concern is feeling "too young" for leadership role at age 28. Elena provided encouragement and validation, helping user reframe self-doubt. Conversation ended on positive note with celebration plans.

## Important Details
- Promotion is in marketing department
- Previous experience: managed 1-2 people on small projects
- Start date: 2 weeks from conversation date
- Team size: 5 people
- Has transition period to wrap up current projects
```

## Database Schema

### PostgreSQL: `v2_conversation_summaries`
```sql
CREATE TABLE v2_conversation_summaries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES v2_chat_sessions(id),
    user_id TEXT NOT NULL,
    summary_text TEXT NOT NULL,
    start_message_id BIGINT NOT NULL,
    end_message_id BIGINT NOT NULL,
    message_count INTEGER NOT NULL,
    topics JSONB,           -- ["work", "hobbies", "relationships"]
    key_facts JSONB,        -- ["User got promotion", "Managing 5 people"]
    meaningfulness_score INTEGER, -- 1-5 score (1=Small talk, 5=Deep)
    emotions JSONB,         -- ["excited", "nervous"]
    time_range_start TIMESTAMP NOT NULL,
    time_range_end TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_summaries_user_id (user_id),
    INDEX idx_summaries_session_id (session_id),
    INDEX idx_summaries_time_range (time_range_start, time_range_end),
    INDEX idx_summaries_topics USING GIN (topics)
);
```

### Qdrant: Summary Vectors
```python
# Point structure
{
    "id": "summary_uuid",
    "vector": [0.123, -0.456, ...],  # 384D embedding
    "payload": {
        "type": "summary",
        "user_id": "123456",
        "summary_text": "...",
        "topics": ["work", "hobbies"],
        "meaningfulness_score": 4,
        "emotions": ["excited", "nervous"],
        "time_range": {
            "start": "2025-10-15T10:00:00",
            "end": "2025-10-15T12:30:00"
        },
        "message_count": 20
    }
}
```

## Overlapping Summaries

To prevent information loss at boundaries:

```python
# When creating new summary
previous_summary = await get_last_summary(session_id)

if previous_summary:
    # Include last N messages from previous summary
    overlap_messages = await get_messages(
        session_id,
        start_id=previous_summary.end_message_id - SUMMARY_OVERLAP,
        end_id=previous_summary.end_message_id
    )
    
    messages = overlap_messages + new_messages
```

**Effect**: Each summary includes 5 messages from the previous summary's end, ensuring continuity.

## Performance Characteristics

### Latency
- **Summary Generation**: 2-5 seconds (LLM call)
- **Storage**: <100ms (PostgreSQL + Qdrant)
- **Retrieval**: 50-200ms (semantic search)
- **Total**: ~3-5 seconds added to every 20th message

### Cost
- **Per Summary**: $0.001-0.003 (GPT-4o-mini)
- **Per 1000 Messages**: ~$0.05-0.15 (50 summaries)
- **Annual (1 user, 100 msgs/day)**: ~$18-55

### Compression Ratio
- **Input**: 20 messages × ~100 tokens = 2,000 tokens
- **Output**: 1 summary × ~500 tokens = 500 tokens
- **Compression**: 4:1 ratio
- **Effect**: After 1000 messages, only 250 message tokens + 12,500 summary tokens = 12,750 tokens (vs 100,000 raw)

## Advanced Features

### Hierarchical Summarization

For very long conversations (1000+ messages):

```python
# Level 1: Message summaries (every 20 messages)
l1_summaries = [summary1, summary2, ...]  # 50 summaries

# Level 2: Meta-summaries (every 10 L1 summaries)
l2_summary = await summarize_summaries(l1_summaries[:10])
# "User discussed career transition over 200 messages. Key themes: ..."

# Level 3: Ultra-compressed (entire conversation arc)
l3_summary = await summarize_summaries(l2_summaries)
# "Multi-month journey from uncertainty to career change"
```

**Status**: Not yet implemented, planned for future

### Differential Summaries

Track changes between summaries:

```python
# Compare consecutive summaries
def generate_diff_summary(prev_summary, new_summary):
    """
    Returns:
    - New topics introduced
    - Topics no longer discussed
    - Sentiment shifts
    - New facts discovered
    """
    pass
```

**Use Case**: "What's changed in our conversations over the past month?"

## Configuration & Tuning

### Threshold Tuning

**Too Low** (e.g., 5 messages):
- ❌ Frequent LLM calls (higher cost)
- ❌ Summaries capture little content
- ✅ Near-real-time compression

**Too High** (e.g., 100 messages):
- ✅ Fewer LLM calls (lower cost)
- ❌ Risk of information loss
- ❌ Large context windows needed

**Recommended**: 20-30 messages (tested sweet spot)

### Summary Length

```python
# In summarization prompt
max_summary_words = 500  # Default

# For verbose users
max_summary_words = 1000

# For terse conversations
max_summary_words = 250
```

### Topic Granularity

```python
# Broad topics (easier to categorize)
topics = ["work", "personal", "hobbies"]

# Granular topics (more searchable)
topics = ["marketing career", "team management", "self-doubt", "celebration plans"]
```

## Error Handling

```python
try:
    summary = await self._generate_summary(conversation_text)
except LLMException as e:
    logger.error(f"Summary generation failed: {e}")
    # Fallback: Store simple concatenation
    summary = f"Conversation summary unavailable. {len(messages)} messages exchanged."
    
try:
    await self._store_summary(summary, metadata)
except DatabaseException as e:
    logger.error(f"Summary storage failed: {e}")
    # Retry with exponential backoff
    await retry_with_backoff(self._store_summary, summary, metadata)
```

## Monitoring

### InfluxDB Metrics
```python
point = Point("summarization") \
    .tag("user_id", user_id) \
    .tag("bot_name", bot_name) \
    .field("message_count", message_count) \
    .field("summary_length", len(summary_text)) \
    .field("generation_time_ms", generation_time) \
    .field("compression_ratio", compression_ratio)
```

### Loguru Output
```
2025-11-22 15:30:00 | INFO | Summarization triggered (22 messages)
2025-11-22 15:30:02 | DEBUG | Summary generated (487 tokens)
2025-11-22 15:30:02 | DEBUG | Topics extracted: work, hobbies, relationships
2025-11-22 15:30:02 | INFO | Summary stored (compression: 4.1x, cost: $0.002)
```

## Future Enhancements

1. **Streaming Summaries**: Update summary incrementally as messages arrive
2. **User-Customizable**: Let users control summary frequency and detail level
3. **Visual Summaries**: Generate charts/graphs of conversation patterns
4. **Cross-User Summaries**: Summarize group conversations with multiple participants
5. **Summary Export**: Allow users to download/view their conversation archives

## Related Files

- `src_v2/memory/summarizer.py`: Core summarization logic
- `src_v2/memory/manager.py`: Summary retrieval and integration
- `src_v2/discord/bot.py`: Automatic summarization triggers
- `migrations_v2/versions/*_conversation_summaries.py`: Database schema
