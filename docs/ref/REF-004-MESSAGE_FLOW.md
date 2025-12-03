# WhisperEngine v2 - Complete Message Flow Architecture

**Version**: 2.2  
**Last Updated**: December 1, 2025

## Multi-Modal Context

Message flow is **perceptual processing** - the pipeline through which raw input becomes unified conscious experience. Each message passes through the character's perceptual system, gathering context from all six modalities before response generation.

| Phase | Modalities Engaged |
|-------|-------------------|
| Input | 💬 Text, 👁️ Vision (images), 👂 Audio (voice) |
| Context | 🧠 Memory, ❤️ Emotion (trust), 🌌 Universe (spatial) |
| Output | 💬 Text, 👂 Audio (TTS) |

This is how characters **process** each interaction.

For full philosophy: See [`MULTI_MODAL_PERCEPTION.md`](./MULTI_MODAL_PERCEPTION.md)

---

## Overview

This document traces the complete lifecycle of a Discord message through WhisperEngine v2's cognitive architecture, from initial reception through response generation and memory consolidation.

## High-Level Flow

```
Discord Message → Session Management → Perceptual Assembly → Response Generation → Memory Storage → Post-Processing
                                       (All 6 Modalities)
```

## Detailed Message Flow

### Phase 1: Message Reception & Initial Processing
**Location**: `src_v2/discord/bot.py:on_message()`

#### 1.1 Message Validation
```python
# Filter conditions
- Ignore own messages (bot.user.id)
- Ignore other bots
- Check for bot mention OR direct message
- Validate character loaded
```

#### 1.2 Session Management
```python
session_id = await session_manager.get_active_session(user_id, character_name)
if not session_id:
    session_id = await session_manager.create_session(user_id, character_name)
```
**Database**: PostgreSQL `v2_sessions` table

#### 1.3 Message Preprocessing
- **Reply Context Injection**: If replying to another message, inject reference as context
- **Attachment Processing**:
  - **Images**: Collect URLs, trigger background vision analysis if `LLM_SUPPORTS_VISION=true`
  - **Documents**: Extract text from PDFs/TXT files (max 5 files, 5MB each)

```python
# Context injection example
if message.reference:
    ref_msg = await channel.fetch_message(message.reference.message_id)
    user_message = f"[Replying to {ref_author}: \"{ref_text}\"]\n{user_message}"
```

---

### Phase 2: Perceptual Assembly (Context Retrieval)
**Location**: `src_v2/discord/bot.py:on_message()` (lines 300-340)

This phase gathers information from all perceptual modalities in parallel.

**Critical Pattern**: Retrieve context BEFORE saving current message to prevent:
- **Echo Chamber**: Finding current message in vector search
- **Double Speak**: Finding current message in chat history

#### 2.1 Memory Modality (🧠) - Vector Memory Search
```python
memories = await memory_manager.search_memories(user_message, user_id)
# Uses: Qdrant vector search with 384D embeddings
# Returns: Top-K relevant past messages/interactions
```
**Database**: Qdrant collection `whisperengine_memory_{bot_name}`

#### 2.2 Chat History Retrieval
```python
chat_history = await memory_manager.get_recent_history(user_id, character_name, channel_id)
# Returns: Last N messages for conversational context
```
**Database**: PostgreSQL `v2_chat_history` table

#### 2.3 Knowledge Graph Retrieval
```python
knowledge_facts = await knowledge_manager.get_user_knowledge(user_id)
# Returns: Structured facts about user (name, pets, location, preferences)
# Fallback: Uses Discord display name if name not in graph
```
**Database**: Neo4j with `:User` and `:Entity` nodes, `:FACT` relationships

#### 2.4 Summary Retrieval (Long-Term Context)
```python
summaries = await memory_manager.search_summaries(user_message, user_id, limit=3)
# Returns: Past conversation summaries with meaningfulness scores
```
**Database**: Qdrant (same collection, type="summary" in payload)

---

### Phase 3: Message Storage & Knowledge Extraction
**Location**: `src_v2/discord/bot.py:on_message()` (lines 340-390)

#### 3.1 Save User Message
```python
await memory_manager.add_message(user_id, character_name, 'human', user_message, channel_id, message_id)
```
**Storage Locations**:
1. **PostgreSQL**: `v2_chat_history` (relational record)
2. **Qdrant**: Vector embedding with metadata (semantic search)

#### 3.2 InfluxDB Metrics Logging
```python
point = Point("message_event") \
    .tag("user_id", user_id) \
    .tag("bot_name", character_name) \
    .field("length", len(user_message))
influxdb_write_api.write(bucket, org, record=point)
```
**Database**: InfluxDB `metrics` bucket

#### 3.3 Knowledge Extraction (Fire-and-Forget)
**Feature Flag**: `ENABLE_RUNTIME_FACT_EXTRACTION` (default: true)
```python
await knowledge_manager.process_user_message(user_id, original_message)
# Extracts: Names, locations, pets, hobbies, relationships
# Uses: LLM-based entity extraction → Neo4j storage
```
**Cost**: 1 LLM call per message

#### 3.4 Preference Extraction (Fire-and-Forget)
**Feature Flag**: `ENABLE_PREFERENCE_EXTRACTION` (default: true)
```python
prefs = await preference_extractor.extract_preferences(message)
# Detects: "be concise", "use emojis", "call me Captain"
# Stores: PostgreSQL v2_user_preferences via trust_manager
```
**Cost**: 1 LLM call per message

#### 3.5 Background Summarization Check
```python
self.loop.create_task(self._check_and_summarize(session_id, user_id))
# Checks if session has enough messages (threshold: 10-20)
# Generates: Summary with meaningfulness score, emotion tags
```

---

### Phase 4: Response Generation (Cognitive Engine)
**Location**: `src_v2/agents/engine.py:generate_response()`

#### 4.1 Complexity Classification & Intent Detection
**Feature Flag**: Always runs (even if `ENABLE_REFLECTIVE_MODE=false`)

```python
complexity, detected_intents = await classifier.classify(user_message, chat_history)
# Returns: 
#   complexity: "SIMPLE" | "COMPLEX_LOW" | "COMPLEX_MID" | "COMPLEX_HIGH" | "MANIPULATION"
#   detected_intents: ["voice", "image", "search"]  # based on enabled features
```

**Intent Detection** (v2.0 - November 2025):
The classifier uses LangChain structured output to detect intents alongside complexity:
- `"voice"`: Only detected if `ENABLE_VOICE_RESPONSES=true`
- `"image"`: Only detected if `ENABLE_IMAGE_GENERATION=true`  
- `"search"`: Always available

This replaces the old regex-based trigger detection (e.g., `VoiceTriggerDetector`).

**Model**: `gpt-4o-mini` via router mode (fast/cheap)  
**Cost**: 1 extra LLM call per message

#### 4.2 System Prompt Construction
**Base Layers**:
1. **Character Personality** (`characters/{name}/character.md`)
2. **Past Summaries** (long-term context)
3. **Relationship State** (trust level, unlocked traits)
4. **Current Mood** (from feedback analyzer)
5. **User Insights** (psychological observations)
6. **User Preferences** (verbosity, style, custom settings)
7. **Active Goals** (`characters/{name}/goals.yaml`)

```python
system_content = character.system_prompt
if context_variables.get("past_summaries"):
    system_content += f"\n\n[RELEVANT PAST CONVERSATIONS]\n{past_summaries}"

# Inject Relationship State
relationship = await trust_manager.get_relationship_level(user_id, character_name)
evolution_context = f"Trust Level: {trust_level} ({level_label})"
if trust_level >= 5:
    # Inject unlocked traits (Vulnerable, Sarcastic, Affectionate, etc.)
system_content += evolution_context
```

#### 4.3 Orchestration: Supergraph vs Legacy

**A. Supergraph Path (Primary - E17 Complete)**
**Condition**: `user_id is provided` (Discord messages, most API calls)
**Location**: `src_v2/agents/engine.py:generate_response()` → `src_v2/agents/master_graph.py:master_graph_agent.run()`

```python
if user_id:
    logger.info("Delegating to Master Supergraph")
    response = await master_graph_agent.run(
        user_input=user_message,
        user_id=user_id,
        character=character,
        chat_history=chat_history,
        context_variables=context_variables,
        image_urls=image_urls
    )
```

**Process** (LangGraph StateGraph):
1. **Context Node**: Parallel retrieval (memories, facts, trust, goals)
2. **Classifier Node**: Complexity + intent detection
3. **Prompt Builder**: System prompt construction with context injection
4. **Router Logic**: Routes to appropriate subgraph:
   - `SIMPLE` → Fast Responder (direct LLM)
   - `COMPLEX_LOW` → Character Subgraph (one-shot tool)
   - `COMPLEX_MID+` → Reflective Subgraph (ReAct loop)
5. **Post-Processing**: Facts, voice, images, reactions

**B. Legacy Python Orchestration (Fallback)**
**Condition**: `user_id is None` (stateless API calls without user context)
**Location**: `src_v2/agents/engine.py:generate_response()` remainder

This path preserves the original Python-based flow for backward compatibility with API clients that don't provide user context.

##### 4.3.1 Cognitive Router (Optional)
```python
if user_id and not context_variables.get("memory_context"):
    router_result = await router.route_and_retrieve(user_id, user_message, chat_history)
```
**Process** (`src_v2/agents/router.py`):
1. **LLM Decision**: Analyzes if memory retrieval needed
2. **Tool Selection**: Chooses from 5 tools:
   - `search_archived_summaries`: Broad topics, past events
   - `search_specific_memories`: Specific details, quotes
   - `lookup_user_facts`: Biographical info from knowledge graph
   - `update_user_facts`: Correct/update facts
   - `update_user_preferences`: Change config settings
3. **Tool Execution**: Runs selected tools, gathers context

##### 4.3.2 LLM Invocation
```python
messages = [SystemMessage(content=system_content)]
messages.extend(chat_history)
messages.append(HumanMessage(content=user_message))

response = await llm.ainvoke(messages)
```
**Model**: Configured via `LLM_PROVIDER` (e.g., gpt-4o, claude-sonnet-4.5)

---

### Phase 5: Response Post-Processing
**Location**: `src_v2/discord/bot.py:on_message()` (lines 420-550)

#### 5.1 Voice Response Generation (Intent-Based)
**Feature Flag**: `ENABLE_VOICE_RESPONSES`
```python
if settings.ENABLE_VOICE_RESPONSES and "voice" in detected_intents:
    # Synchronous generation (awaits TTS API)
    # Returns True if successful, stores file in ArtifactRegistry
    await voice_response_manager.generate_voice_response(
        text=response_text,
        character=character,
        user_id=user_id
    )
```
**Process** (`src_v2/voice/response.py`):
1. Check user quota (`DAILY_AUDIO_QUOTA`)
2. Generate TTS via ElevenLabs (awaited)
3. Store in `ArtifactRegistry`

**Trigger**: LLM intent detection (replaces old regex/keyword matching)

#### 5.2 Image Attachment (Intent-Based)
**Feature Flag**: `ENABLE_IMAGE_GENERATION`
```python
# Images are generated during Phase 4 (Agent Tool Execution)
# They are stored in ArtifactRegistry
# Here we extract them for attachment to the final message
response_text, image_files = await extract_pending_images(response_text, user_id)
```

#### 5.3 Stats Footer Generation (Optional)
```python
if await stats_footer.is_enabled_for_user(user_id, character_name):
    footer_text = await stats_footer.generate_footer(
        user_id, character_name, memory_count, processing_time_ms
    )
    full_response = f"{response}\n\n{footer_text}"
```
**Shows**: Relationship level, active goals, memory count, insights, performance

#### 5.4 Message Chunking
```python
message_chunks = self._chunk_message(full_response, max_length=2000)
# Splits on sentence boundaries if >2000 chars (Discord limit)
```

#### 5.5 Send & Save Response
```python
for chunk in message_chunks:
    sent_msg = await message.channel.send(chunk, files=files)

await memory_manager.add_message(user_id, character_name, 'ai', response, channel_id, message_id)
```
**Storage**: PostgreSQL + Qdrant (same as user message)

#### 5.6 Goal Analysis (Fire-and-Forget)
```python
interaction_text = f"User: {user_message}\nAI: {response}"
self.loop.create_task(goal_analyzer.check_goals(user_id, character_name, interaction_text))
```
**Process**: Checks if interaction made progress toward active goal

#### 5.7 Trust Update (Engagement Reward)
```python
self.loop.create_task(trust_manager.update_trust(user_id, character_name, +1))
```
**Effect**: Small trust increase for every positive interaction

---

### Phase 6: Feedback Loop (Reactions)
**Location**: `src_v2/discord/bot.py:on_reaction_add()`

#### Reaction Processing
```python
# User reacts with 👍, ❤️, 👎, etc.
feedback_score = await feedback_analyzer.get_feedback_score(message_id, user_id)

# Adjust memory importance in Qdrant
score_delta = feedback_score * 0.2
await feedback_analyzer.adjust_memory_score_by_message_id(message_id, collection_name, score_delta)

# Update trust based on feedback
trust_delta = 5 if feedback_score > 0 else -5
await trust_manager.update_trust(user_id, character_name, trust_delta)
```

**Effects**:
- **Positive reactions**: Boost memory importance, increase trust
- **Negative reactions**: Decrease memory importance, reduce trust
- **Logged to InfluxDB**: For engagement analytics

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        DISCORD MESSAGE                          │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 1: INITIAL PROCESSING                                    │
│  - Session Management (PostgreSQL)                              │
│  - Attachment Processing (Images → Vision, Docs → Text)         │
│  - Reply Context Injection                                      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 2: CONTEXT RETRIEVAL (RAG)                               │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐ │
│  │   Qdrant     │  PostgreSQL  │    Neo4j     │   Qdrant     │ │
│  │   Memories   │   History    │  Knowledge   │  Summaries   │ │
│  │  (semantic)  │  (recent)    │   (facts)    │  (long-term) │ │
│  └──────────────┴──────────────┴──────────────┴──────────────┘ │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 3: MESSAGE STORAGE & EXTRACTION                          │
│  ┌──────────────────────┬─────────────────────────────────────┐│
│  │ PostgreSQL + Qdrant  │  Background Tasks (Fire-and-Forget) ││
│  │ (user message saved) │  - Knowledge Extraction → Neo4j     ││
│  │                      │  - Preference Extraction → PostgreSQL││
│  │                      │  - Summarization Check               ││
│  │                      │  - InfluxDB Metrics                  ││
│  └──────────────────────┴─────────────────────────────────────┘│
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 4: COGNITIVE ENGINE (RESPONSE GENERATION)                │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 1. Complexity Classification (if enabled)               │   │
│  │    - SIMPLE/MODERATE/COMPLEX                            │   │
│  └─────────────────────────┬───────────────────────────────┘   │
│                            │                                    │
│                ┌───────────┴───────────┐                        │
│                ▼                       ▼                        │
│    ┌───────────────────┐   ┌──────────────────────┐           │
│    │   FAST MODE       │   │  REFLECTIVE MODE     │           │
│    │ (System 1)        │   │  (System 2)          │           │
│    │                   │   │                      │           │
│    │ - Cognitive Router│   │ - ReAct Loop         │           │
│    │ - Tool Selection  │   │ - Multi-Step Reasoning│          │
│    │ - LLM Invocation  │   │ - Deep Analysis      │           │
│    │ Cost: ~$0.001-005 │   │ Cost: ~$0.02-0.03    │           │
│    └───────────────────┘   └──────────────────────┘           │
│                            │                                    │
│  ┌─────────────────────────▼───────────────────────────────┐   │
│  │ 2. System Prompt Construction                           │   │
│  │    - Character Personality + Evolution State            │   │
│  │    - Retrieved Context (memories, facts, summaries)     │   │
│  │    - User Preferences + Active Goals                    │   │
│  └─────────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 5: RESPONSE POST-PROCESSING                              │
│  1. Stats Footer (optional)                                     │
│  2. Message Chunking (Discord 2000 char limit)                  │
│  3. Send to Discord                                             │
│  4. Save to PostgreSQL + Qdrant                                 │
│  5. Background Tasks:                                           │
│     - Goal Analysis                                             │
│     - Trust Update (+1)                                         │
│     - Voice Playback (if in voice channel)                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Architectural Patterns

### 1. Echo Chamber Prevention
**Problem**: Vector search might return the message we just sent.
**Solution**: Retrieve all context BEFORE saving current message.

```python
# ✅ CORRECT ORDER
memories = await memory_manager.search_memories(user_message, user_id)  # Search first
await memory_manager.add_message(user_id, character_name, 'human', user_message)  # Save after
```

### 2. Fire-and-Forget Tasks
**Pattern**: Non-blocking background processing for expensive operations.
```python
self.loop.create_task(knowledge_manager.process_user_message(user_id, message))
self.loop.create_task(goal_analyzer.check_goals(user_id, character_name, interaction))
```
**Benefits**: Reduces response latency, prevents blocking Discord interactions.

### 3. Feature Flag Gates
**Pattern**: Resource management via boolean flags.
```python
if settings.ENABLE_REFLECTIVE_MODE:
    complexity = await classifier.classify(message)  # +1 LLM call

if settings.ENABLE_RUNTIME_FACT_EXTRACTION:
    await knowledge_manager.process_user_message(user_id, message)  # +1 LLM call
```
**Cost Savings**: ~$0.0006 per message with all flags disabled.

### 4. Dual-Process Cognition
**Fast Mode (System 1)**: 
- Direct LLM response with pre-fetched context
- Used for 95% of messages
- Latency: ~1-3 seconds

**Reflective Mode (System 2)**:
- Multi-step reasoning with tool usage
- Used for complex analytical questions
- Latency: ~10-30 seconds

### 5. Reasoning Transparency
**Cognitive Router Logging**:
```python
logger.info(f"Router decided to call {len(tool_calls)} tools: {[tc['name'] for tc in tool_calls]}")
logger.debug(f"Executing {tool_name} with args: {tool_args}")
```
**Purpose**: Debugging, explainability, trust.

---

## Database Interaction Summary

| Database   | Port | Purpose | Access Pattern |
|------------|------|---------|----------------|
| PostgreSQL | 5432 | Chat history, sessions, user preferences, relationships | Read/Write on every message |
| Qdrant     | 6333 | Vector embeddings for semantic search | Read (retrieval), Write (storage) |
| Neo4j      | 7687 | Knowledge graph (facts, entities, relationships) | Read (lookup), Write (extraction) |
| InfluxDB   | 8086 | Time-series metrics (engagement, performance) | Write-only (fire-and-forget) |

---

## Performance Characteristics

### Latency Breakdown (Fast Mode)
1. **Context Retrieval**: 200-500ms (parallel DB queries)
2. **Message Storage**: 50-100ms (async writes)
3. **LLM Generation**: 1-2 seconds (depends on model/load)
4. **Background Tasks**: 0ms (non-blocking)

**Total Response Time**: ~1.5-3 seconds

### Cost Per Message (Default Config)
- **Fast Mode**: $0.001-0.005 (single LLM call)
- **With Fact Extraction**: +$0.0003 (1 extra call)
- **With Preference Extraction**: +$0.0003 (1 extra call)
- **Reflective Mode**: $0.02-0.03 (10-20x cost, 5% of messages)

---

## Error Handling & Resilience

### Database Unavailability
```python
if not db_manager.postgres_pool:
    logger.warning("Postgres unavailable, memory persistence disabled.")
    # Continue with degraded functionality
```

### LLM Failures
```python
try:
    response = await llm.ainvoke(messages)
except Exception as e:
    logger.error(f"LLM invocation failed: {e}")
    await message.channel.send("I'm having trouble processing that right now.")
```

### Graceful Degradation
- **No Qdrant**: No semantic search, uses only recent history
- **No Neo4j**: No fact-based context, relies on memory
- **No InfluxDB**: No metrics, core functionality unaffected

---

## Configuration Flags Impact

| Flag | Default | Impact on Flow | Cost/Message |
|------|---------|----------------|--------------|
| `ENABLE_REFLECTIVE_MODE` | false | Adds complexity classification + ReAct loop | +$0.0003 (classifier), +$0.02 (if complex) |
| `ENABLE_RUNTIME_FACT_EXTRACTION` | true | Adds Neo4j knowledge extraction | +$0.0003 |
| `ENABLE_PREFERENCE_EXTRACTION` | true | Adds preference detection | +$0.0003 |
| `ENABLE_PROACTIVE_MESSAGING` | false | Enables bot-initiated messages | Variable |
| `LLM_SUPPORTS_VISION` | false | Enables image analysis | +$0.01-0.05 per image |

---

## Future Optimization Opportunities

1. **Context Caching**: Cache frequently accessed user data (trust level, preferences) in Redis
2. **Batch Knowledge Extraction**: Process multiple messages together in a single LLM call
3. **Streaming Responses**: Use LLM streaming to reduce perceived latency
4. **Smarter Summarization**: Trigger summarization based on conversation complexity, not just message count
5. **Vector Search Optimization**: Use Qdrant's filters to narrow search before vector comparison

---

## Related Documentation

- **Cognitive Engine**: `docs/architecture/COGNITIVE_ENGINE.md`
- **Memory System**: `docs/architecture/MEMORY_SYSTEM_V2.md`
- **Data Models**: `docs/architecture/DATA_MODELS.md`
- **Reflective Mode**: `docs/roadmaps/REFLECTIVE_MODE_IMPLEMENTATION.md`
