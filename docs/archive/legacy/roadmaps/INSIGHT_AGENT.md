# Insight Agent - Background Agentic Processing

**Document Version:** 2.0  
**Created:** November 25, 2025  
**Last Updated:** November 25, 2025  
**Status:** ✅ Complete  
**Priority:** HIGH  
**Time Taken:** ~4 hours (AI-assisted)  
**Complexity:** Medium-High

---

## Implementation Status

| Component | Status | File |
|-----------|--------|------|
| TaskQueue | ✅ Complete | `src_v2/workers/task_queue.py` |
| Worker | ✅ Complete | `src_v2/workers/worker.py` |
| InsightAgent | ✅ Complete | `src_v2/agents/insight_agent.py` |
| InsightTools | ✅ Complete | `src_v2/tools/insight_tools.py` |
| Bot Triggers | ✅ Complete | `src_v2/discord/bot.py` |
| Docker Config | ✅ Complete | `docker-compose.yml` |
| Unit Tests | ✅ Complete | `tests_v2/test_insight_agent.py` |

---

## Shared Worker Architecture

A single `worker` container serves **all bot instances**:

```
┌─────────────────────────────────────────────────────────────────────┐
│                     MULTI-BOT ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Bot: Elena ─┐                                                     │
│               │                                                     │
│   Bot: Ryan ──┼──→ Redis Queue (arq) ──→ Single Worker (Shared)    │
│               │         ↑                        ↓                  │
│   Bot: Dotty ─┘         │              InsightAgent.analyze()       │
│                         │                        ↓                  │
│                    Job Payload:          Store insights to          │
│                    {                     Qdrant/Neo4j/Postgres      │
│                      bot_name: "elena",                            │
│                      user_id: "123",                               │
│                      session_id: "abc",                            │
│                      trigger: "positive_feedback"                  │
│                    }                                                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Why shared?**
- Resource efficient (1 container vs N containers)
- Simpler deployment (no 1:1 bot-to-worker mapping)
- Jobs include `bot_name` so worker loads correct character context
- Worker can process jobs from any bot concurrently

---

## Overview

The Insight Agent is a **background agentic system** that periodically reflects on user conversations to generate epiphanies, store reasoning traces, and learn response patterns. Unlike simple fire-and-forget tasks, this agent uses a ReAct loop with specialized introspection tools to synthesize insights across multiple data sources.

### Why Agentic?

Current background processing uses simple fire-and-forget `asyncio.create_task` calls:
- ✅ Good for: Fact extraction, preference detection, trust updates (single-purpose, no decisions)
- ❌ Bad for: Pattern detection, cross-source synthesis, emergent insights (requires reasoning)

The Insight Agent consolidates three roadmap items into one coherent system:
- **C1: Reasoning Traces** - Store successful reasoning for future reuse
- **C2: Epiphanies** - Spontaneous realizations about users
- **B6: Response Pattern Learning** - Learn which response styles resonate

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     BACKGROUND INSIGHT AGENT                        │
│  (Runs every 30 min OR triggered after 10+ messages from user)     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────┐      ┌──────────────────────────────────┐   │
│  │  PRIORITY QUEUE  │      │         INSIGHT AGENT            │   │
│  │  (Redis/arq)     │─────▶│  • ReAct loop (like reflective)  │   │
│  │                  │      │  • Tools for introspection       │   │
│  │  - user_id       │      │  • Generates insights/epiphanies │   │
│  │  - last_analyzed │      │  • Stores reasoning traces       │   │
│  │  - priority      │      └──────────────────────────────────┘   │
│  └──────────────────┘                     │                        │
│                                           ▼                        │
│                          ┌────────────────────────────────────┐   │
│                          │           INSIGHT TOOLS            │   │
│                          ├────────────────────────────────────┤   │
│                          │ • analyze_conversation_patterns    │   │
│                          │ • detect_emotional_themes          │   │
│                          │ • find_recurring_topics            │   │
│                          │ • compare_with_past_sessions       │   │
│                          │ • check_goal_progress              │   │
│                          │ • generate_epiphany                │   │
│                          │ • store_reasoning_trace            │   │
│                          │ • learn_response_pattern           │   │
│                          └────────────────────────────────────┘   │
│                                           │                        │
│                                           ▼                        │
│                          ┌────────────────────────────────────┐   │
│                          │           OUTPUTS                  │   │
│                          ├────────────────────────────────────┤   │
│                          │ • Epiphanies → v2_epiphanies table │   │
│                          │ • Traces → v2_reasoning_traces     │   │
│                          │ • Patterns → v2_response_patterns  │   │
│                          │ • Insights → user_relationships    │   │
│                          └────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Task Classification

### Keep Simple (Fire-and-Forget)

These tasks remain as simple `asyncio.create_task` calls - no agentic reasoning needed:

| Task | Reason |
|------|--------|
| Fact extraction | Straightforward LLM extraction, single prompt |
| Preference extraction | Pattern matching / structured output |
| Trust updates | Simple math, no LLM needed |
| Metrics logging | Just writes to InfluxDB |
| Summarization | Single LLM call with clear input/output |

### Make Agentic (Insight Agent)

These tasks benefit from multi-step reasoning and cross-source synthesis:

| Task | Why Agentic? |
|------|-------------|
| Epiphanies (C2) | Requires connecting patterns across memories, facts, and sessions |
| Reasoning Traces (C1) | Needs to evaluate which traces are worth storing |
| Response Patterns (B6) | Must correlate response styles with feedback signals |
| User Insights | Synthesizes multiple data sources into coherent observations |

---

## Trigger Conditions

The Insight Agent doesn't run on every message. It triggers based on:

| Trigger | Condition | Priority |
|---------|-----------|----------|
| **Time-based** | 30-60 minutes since last analysis for active user | Medium |
| **Volume-based** | 10+ messages in current session | High |
| **Session-end** | After summarization completes | High |
| **Feedback-based** | 3+ reactions from same user in short period | High |
| **Manual** | Admin trigger via API endpoint | Low |

### Prioritization Logic

```
function calculate_priority(user_id) -> float:
    // Higher score = analyze sooner
    score = 0.0
    
    // Recent activity boost
    messages_last_hour = get_message_count(user_id, hours=1)
    score += min(messages_last_hour * 0.1, 1.0)
    
    // Positive feedback boost
    recent_reactions = get_positive_reactions(user_id, hours=24)
    score += min(recent_reactions * 0.2, 1.0)
    
    // Time since last analysis penalty
    hours_since_analysis = get_hours_since_last_analysis(user_id)
    if hours_since_analysis > 24:
        score += 0.5
    
    // Trust level boost (invest in high-trust users)
    trust_score = get_trust_score(user_id)
    if trust_score > 50:
        score += 0.3
    
    return score
```

---

## Insight Tools

### Data Gathering Tools

#### `analyze_conversation_patterns`
```
class AnalyzeConversationPatternsTool(BaseTool):
    // Analyzes recent conversation for patterns in:
    // - Message timing (when does user engage?)
    // - Topic flow (how do conversations evolve?)
    // - Engagement signals (message length, questions asked)
    
    function _arun(time_range="last_week") -> str:
        history = get_chat_history(time_range)
        stats = compute_statistics(history)
        return format_analysis(stats)
```

#### `detect_emotional_themes`
```
class DetectEmotionalThemesTool(BaseTool):
    // Detects recurring emotional themes across sessions:
    // - Topics that correlate with positive/negative sentiment
    // - Emotional triggers (what makes user happy/sad?)
    // - Mood patterns over time
```

#### `find_recurring_topics`
```
class FindRecurringTopicsTool(BaseTool):
    // Identifies topics the user returns to repeatedly:
    // - Explicit interests (stated preferences)
    // - Implicit interests (topics they keep bringing up)
    // - Seasonal patterns (topics tied to time of year)
```

#### `compare_with_past_sessions`
```
class CompareWithPastSessionsTool(BaseTool):
    // Compares current session with past sessions to detect:
    // - Mood shifts (better/worse than usual?)
    // - New interests vs old interests
    // - Relationship evolution signals
```

#### `check_goal_progress`
```
class CheckGoalProgressTool(BaseTool):
    // Checks progress on active character goals:
    // - Which goals are advancing?
    // - Which goals are stalled?
    // - Opportunities to advance goals naturally
```

### Action Tools

#### `generate_epiphany`
```
class GenerateEpiphanyTool(BaseTool):
    // Generates an epiphany (sudden insight) about the user.
    // Only call this when you've discovered something genuinely non-obvious.
    
    function _arun(insight, confidence, evidence) -> str:
        if is_trivial(insight):
            return "Error: Insight too trivial"
            
        store_epiphany(insight, confidence, evidence)
        return "Epiphany stored successfully"
```

#### `store_reasoning_trace`
```
class StoreReasoningTraceTool(BaseTool):
    // Stores a successful reasoning trace for future reuse.
    // Only store traces that:
    // - Solved a genuinely complex problem
    // - Could help with similar future problems
    // - Had a positive outcome (user satisfied)
    
    function _arun(question, reasoning_steps, answer, quality_score) -> str:
        embedding = embed(question)
        store_trace(question, reasoning_steps, answer, embedding)
        return "Trace stored"
```

#### `learn_response_pattern`
```
class LearnResponsePatternTool(BaseTool):
    // Records a response pattern that resonated with the user.
    // Used for RLHF-style adaptation without fine-tuning.
    
    function _arun(message_type, response_style, example_response, feedback_score) -> str:
        store_pattern(message_type, response_style, example_response, feedback_score)
        return "Pattern learned"
```

---

## Core Implementation

### InsightAgent Class

```
class InsightAgent:
    // Background agent that reflects on user conversations and generates insights.
    // Runs periodically or triggered after significant interaction volume.
    
    function run(user_id, character_name) -> InsightResult:
        tools = get_tools(user_id, character_name)
        system_prompt = build_system_prompt(character_name)
        
        messages = [
            SystemMessage(system_prompt),
            HumanMessage("Analyze recent interactions...")
        ]
        
        steps = 0
        while steps < max_steps:
            response = llm.invoke(messages, tools=tools)
            messages.append(response)
            
            if response.has_tool_calls:
                for call in response.tool_calls:
                    result = execute_tool(call, tools)
                    messages.append(ToolMessage(result))
            else:
                break  // Done
                
        return collect_results(messages)
```

---

## Database Schema

### v2_epiphanies
```sql
CREATE TABLE v2_epiphanies (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    character_name VARCHAR NOT NULL,
    insight TEXT NOT NULL,
    confidence FLOAT CHECK (confidence >= 0 AND confidence <= 1),
    supporting_evidence JSONB,  -- List of memory IDs, facts, etc.
    created_at TIMESTAMP DEFAULT NOW(),
    referenced_count INT DEFAULT 0,  -- How often this was used in responses
    last_referenced_at TIMESTAMP,
    
    INDEX idx_epiphanies_user_char ON v2_epiphanies(user_id, character_name),
    INDEX idx_epiphanies_confidence ON v2_epiphanies(confidence DESC)
);
```

### v2_reasoning_traces
```sql
CREATE TABLE v2_reasoning_traces (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR,  -- NULL for general traces
    character_name VARCHAR NOT NULL,
    question TEXT NOT NULL,
    scratchpad JSONB NOT NULL,  -- Full reasoning steps
    final_answer TEXT NOT NULL,
    embedding VECTOR(768),  -- For similarity search
    quality_score FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    reuse_count INT DEFAULT 0,
    
    INDEX idx_traces_embedding ON v2_reasoning_traces USING hnsw (embedding vector_cosine_ops)
);
```

### v2_response_patterns
```sql
CREATE TABLE v2_response_patterns (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    character_name VARCHAR NOT NULL,
    message_embedding VECTOR(768),  -- Embedded user message
    message_type VARCHAR,  -- e.g., "question", "venting", "joke"
    response_style JSONB,  -- {length: "short", tone: "playful", structure: "direct"}
    example_response TEXT,
    feedback_score FLOAT,  -- Derived from reactions
    created_at TIMESTAMP DEFAULT NOW(),
    
    INDEX idx_patterns_user ON v2_response_patterns(user_id, character_name),
    INDEX idx_patterns_embedding ON v2_response_patterns USING hnsw (message_embedding vector_cosine_ops)
);
```

---

## Integration with Worker Queue

When C3 (Worker Queues) is implemented, the Insight Agent will be scheduled via Redis/arq:

```
// src_v2/workers/worker.py

function analyze_user(ctx, user_id, character_name):
    // Worker task to analyze a specific user
    result = insight_agent.run(user_id, character_name)
    log_result(result)

class WorkerSettings:
    functions = [analyze_user]
    cron_jobs = [
        // Run insight analysis for active users every hour
        cron(analyze_active_users, hour=None, minute=0)
    ]
```

Until C3 is implemented, can use simple `asyncio.create_task` with in-memory scheduling:

```
// Temporary implementation before Worker Queues
function schedule_insight_analysis(user_id, character_name):
    // Schedule insight analysis in background
    
    function run_analysis():
        wait(60 seconds)  // Delay to batch with other messages
        insight_agent.run(user_id, character_name)
    
    create_background_task(run_analysis())
```

---

## Cost Analysis

### Per Analysis Run
- **Model**: Utility/Router model (e.g., GPT-4o-mini, Claude Haiku)
- **Steps**: 3-5 tool calls average
- **Tokens**: ~2,000-4,000 per run
- **Cost**: ~$0.002-0.008 per analysis

### Monthly Estimate (100 active users)
- Analyses per user: ~30/month (once per day average)
- Total analyses: 3,000/month
- **Total cost: $6-24/month**

### Comparison to Alternatives
- Running this logic per-message: $60-240/month (10x more expensive)
- Not having insights at all: $0 but much lower engagement

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Epiphany quality | >70% referenced in future conversations | `referenced_count > 0` |
| Trace reuse | >30% of stored traces reused | `reuse_count > 0` |
| Pattern accuracy | Response patterns improve feedback scores | A/B test |
| Cost per insight | <$0.01 per meaningful artifact | Track tool usage |
| Processing time | <30s per analysis | Log timestamps |

---

## Implementation Phases

### Phase 1: Core Agent (3-4 days)
- [x] Create `InsightAgent` class with ReAct loop
- [x] Implement data gathering tools (analyze patterns, detect themes, etc.)
- [x] Basic scheduling via `asyncio.create_task`
- [x] Unit tests for agent logic

### Phase 2: Action Tools (2-3 days)
- [x] Create database migrations for new tables
- [x] Implement `generate_epiphany` tool
- [x] Implement `store_reasoning_trace` tool
- [x] Implement `learn_response_pattern` tool
- [x] Integration tests

### Phase 3: Integration (1-2 days)
- [x] Wire into `AgentEngine` for trace/pattern injection
- [x] Wire into character prompts for epiphany references
- [x] Add trigger logic in `bot.py`
- [x] End-to-end testing

### Phase 4: Worker Queue (After C3)
- [x] Migrate to arq/Redis scheduling
- [x] Add monitoring/alerting

### Phase 5: Refinement (Post-Launch)
- [x] Explicitly expose `epiphany` type in `SearchMyThoughtsTool` (allow bot to reflect on realizations)
- [x] Add `search_diaries` semantic search method to `DiaryManager`
- [x] Include epiphanies in diary generation material

---

## Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| PostgreSQL with pgvector | ✅ Exists | For embedding storage |
| Embedding service | ✅ Exists | 768D embeddings |
| LLM factory | ✅ Exists | Utility mode |
| Tool infrastructure | ✅ Exists | BaseTool pattern |
| Worker Queues (C3) | ⏳ Planned | Can start without, migrate later |

---

## Related Documents

- [IMPLEMENTATION_ROADMAP_OVERVIEW.md](../IMPLEMENTATION_ROADMAP_OVERVIEW.md) - Overall prioritization
- [CHARACTER_AS_AGENT.md](../architecture/CHARACTER_AS_AGENT.md) - User-facing character agency analysis
- [RESPONSE_PATTERN_LEARNING.md](./RESPONSE_PATTERN_LEARNING.md) - B6 detailed spec (subsumed by this)
- [REFLECTIVE_MODE_PHASE_2.md](./REFLECTIVE_MODE_PHASE_2.md) - Similar ReAct architecture
- [MESSAGE_FLOW.md](../architecture/MESSAGE_FLOW.md) - Where this integrates

---

## Open Questions

1. **Epiphany surfacing**: How should characters naturally reference epiphanies? Inject into system prompt? Dedicated retrieval?

2. **Privacy controls**: Should users be able to opt out of insight analysis? Delete epiphanies?

3. **Cross-character insights**: Should insights be shared across characters? Or per-character isolation?

4. **Feedback loop**: How do we measure if generated insights are actually useful?

---

**Version History:**
- v1.0 (Nov 25, 2025) - Initial architecture design
