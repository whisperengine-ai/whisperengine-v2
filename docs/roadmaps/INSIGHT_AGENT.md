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
| InsightWorker | ✅ Complete | `src_v2/workers/insight_worker.py` |
| InsightAgent | ✅ Complete | `src_v2/agents/insight_agent.py` |
| InsightTools | ✅ Complete | `src_v2/tools/insight_tools.py` |
| Bot Triggers | ✅ Complete | `src_v2/discord/bot.py` |
| Docker Config | ✅ Complete | `docker-compose.yml` |
| Unit Tests | ✅ Complete | `tests_v2/test_insight_agent.py` |

---

## Shared Worker Architecture

A single `insight-worker` container serves **all bot instances**:

```
┌─────────────────────────────────────────────────────────────────────┐
│                     MULTI-BOT ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Bot: Elena ─┐                                                     │
│               │                                                     │
│   Bot: Ryan ──┼──→ Redis Queue (arq) ──→ Single Insight Worker     │
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

```python
def calculate_priority(user_id: str) -> float:
    """Higher score = analyze sooner."""
    score = 0.0
    
    # Recent activity boost
    messages_last_hour = get_message_count(user_id, hours=1)
    score += min(messages_last_hour * 0.1, 1.0)  # Cap at 1.0
    
    # Positive feedback boost
    recent_reactions = get_positive_reactions(user_id, hours=24)
    score += min(recent_reactions * 0.2, 1.0)
    
    # Time since last analysis penalty
    hours_since_analysis = get_hours_since_last_analysis(user_id)
    if hours_since_analysis > 24:
        score += 0.5
    
    # Trust level boost (invest in high-trust users)
    trust_score = get_trust_score(user_id)
    if trust_score > 50:
        score += 0.3
    
    return score
```

---

## Insight Tools

### Data Gathering Tools

#### `analyze_conversation_patterns`
```python
class AnalyzeConversationPatternsTool(BaseTool):
    """
    Analyzes recent conversation for patterns in:
    - Message timing (when does user engage?)
    - Topic flow (how do conversations evolve?)
    - Engagement signals (message length, questions asked)
    """
    name = "analyze_conversation_patterns"
    description = "Analyzes recent conversations for behavioral patterns."
    
    async def _arun(self, time_range: str = "last_week") -> str:
        # Query chat history, compute statistics
        # Return structured analysis
```

#### `detect_emotional_themes`
```python
class DetectEmotionalThemesTool(BaseTool):
    """
    Detects recurring emotional themes across sessions:
    - Topics that correlate with positive/negative sentiment
    - Emotional triggers (what makes user happy/sad?)
    - Mood patterns over time
    """
    name = "detect_emotional_themes"
    description = "Identifies emotional patterns and correlations in conversations."
```

#### `find_recurring_topics`
```python
class FindRecurringTopicsTool(BaseTool):
    """
    Identifies topics the user returns to repeatedly:
    - Explicit interests (stated preferences)
    - Implicit interests (topics they keep bringing up)
    - Seasonal patterns (topics tied to time of year)
    """
    name = "find_recurring_topics"
    description = "Finds topics the user discusses repeatedly across sessions."
```

#### `compare_with_past_sessions`
```python
class CompareWithPastSessionsTool(BaseTool):
    """
    Compares current session with past sessions to detect:
    - Mood shifts (better/worse than usual?)
    - New interests vs old interests
    - Relationship evolution signals
    """
    name = "compare_with_past_sessions"
    description = "Compares current session patterns with historical baseline."
```

#### `check_goal_progress`
```python
class CheckGoalProgressTool(BaseTool):
    """
    Checks progress on active character goals:
    - Which goals are advancing?
    - Which goals are stalled?
    - Opportunities to advance goals naturally
    """
    name = "check_goal_progress"
    description = "Evaluates progress on active character goals for this user."
```

### Action Tools

#### `generate_epiphany`
```python
class GenerateEpiphanyTool(BaseTool):
    """
    Generates an epiphany (sudden insight) about the user.
    Only call this when you've discovered something genuinely non-obvious.
    
    Example epiphanies:
    - "I just realized you always mention space when you're feeling down"
    - "You seem to open up more in the evenings"
    - "Your taste in music has shifted a lot since we first talked"
    """
    name = "generate_epiphany"
    description = "Stores a genuine insight about the user for future reference."
    
    async def _arun(self, insight: str, confidence: float, evidence: List[str]) -> str:
        # Validate insight isn't trivial
        # Store in v2_epiphanies table
        # Return confirmation
```

#### `store_reasoning_trace`
```python
class StoreReasoningTraceTool(BaseTool):
    """
    Stores a successful reasoning trace for future reuse.
    Only store traces that:
    - Solved a genuinely complex problem
    - Could help with similar future problems
    - Had a positive outcome (user satisfied)
    """
    name = "store_reasoning_trace"
    description = "Saves a reasoning pattern that worked well for future reference."
    
    async def _arun(self, question: str, reasoning_steps: List[str], 
                    answer: str, quality_score: float) -> str:
        # Embed the question for future similarity search
        # Store in v2_reasoning_traces table
```

#### `learn_response_pattern`
```python
class LearnResponsePatternTool(BaseTool):
    """
    Records a response pattern that resonated with the user.
    Used for RLHF-style adaptation without fine-tuning.
    
    Pattern includes:
    - The type of message that prompted this response
    - The response style (length, tone, structure)
    - Feedback signal (reactions, follow-up engagement)
    """
    name = "learn_response_pattern"
    description = "Records a response style that worked well with this user."
    
    async def _arun(self, message_type: str, response_style: str,
                    example_response: str, feedback_score: float) -> str:
        # Store in v2_response_patterns table
        # Embed for future retrieval
```

---

## Core Implementation

### InsightAgent Class

```python
# src_v2/agents/insight_agent.py

from typing import List, Optional, Tuple
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage
from langchain_core.tools import BaseTool
from loguru import logger

from src_v2.agents.llm_factory import create_llm
from src_v2.config.settings import settings


class InsightResult(BaseModel):
    """Result of an insight analysis run."""
    epiphanies: List[dict]  # Generated epiphanies
    patterns: List[dict]     # Learned response patterns
    traces: List[dict]       # Stored reasoning traces
    insights: List[str]      # General observations
    tools_used: int
    steps_taken: int


class InsightAgent:
    """
    Background agent that reflects on user conversations and generates insights.
    Runs periodically or triggered after significant interaction volume.
    
    Unlike ReflectiveAgent (real-time, user-facing), InsightAgent:
    - Runs in background (no latency concerns)
    - Focuses on cross-session patterns
    - Generates persistent artifacts (epiphanies, traces, patterns)
    - Uses lighter model (cost optimization)
    """
    
    def __init__(self):
        # Use utility model (cheaper) since this runs in background
        self.llm = create_llm(temperature=0.3, mode="utility")
        self.max_steps = 5  # Lighter than reflective mode
        
    async def run(self, user_id: str, character_name: str) -> InsightResult:
        """
        Analyze recent interactions and generate insights.
        
        Args:
            user_id: Discord user ID to analyze
            character_name: Character name for context
            
        Returns:
            InsightResult with generated artifacts
        """
        tools = self._get_tools(user_id, character_name)
        llm_with_tools = self.llm.bind_tools(tools)
        
        system_prompt = self._build_system_prompt(character_name)
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Analyze recent interactions with user {user_id}. "
                                 f"Look for patterns, generate insights, and store any "
                                 f"valuable reasoning traces or response patterns.")
        ]
        
        steps = 0
        tools_used = 0
        
        logger.info(f"InsightAgent starting analysis for user {user_id}")
        
        while steps < self.max_steps:
            steps += 1
            
            response = await llm_with_tools.ainvoke(messages)
            messages.append(response)
            
            if response.tool_calls:
                tools_used += len(response.tool_calls)
                
                for tool_call in response.tool_calls:
                    result = await self._execute_tool(tool_call, tools)
                    messages.append(ToolMessage(
                        content=result,
                        tool_call_id=tool_call["id"],
                        name=tool_call["name"]
                    ))
            else:
                # No more tool calls - agent is done
                break
        
        logger.info(f"InsightAgent finished for {user_id}: {steps} steps, {tools_used} tools")
        
        return self._collect_results(messages, steps, tools_used)
    
    def _get_tools(self, user_id: str, character_name: str) -> List[BaseTool]:
        """Returns tools available to the insight agent."""
        return [
            # Data gathering
            AnalyzeConversationPatternsTool(user_id=user_id),
            DetectEmotionalThemesTool(user_id=user_id),
            FindRecurringTopicsTool(user_id=user_id),
            CompareWithPastSessionsTool(user_id=user_id),
            CheckGoalProgressTool(user_id=user_id, character_name=character_name),
            # Actions
            GenerateEpiphanyTool(user_id=user_id, character_name=character_name),
            StoreReasoningTraceTool(user_id=user_id, character_name=character_name),
            LearnResponsePatternTool(user_id=user_id, character_name=character_name),
        ]
    
    def _build_system_prompt(self, character_name: str) -> str:
        return f"""You are a reflective agent analyzing conversations between {character_name} and a user.

Your goal is to discover meaningful patterns and generate valuable insights.

## What to Look For:
1. **Behavioral patterns** - When does the user engage? How do conversations flow?
2. **Emotional correlations** - What topics correlate with positive/negative sentiment?
3. **Recurring themes** - What does the user keep coming back to?
4. **Relationship signals** - Is the relationship deepening, stagnating, or cooling?

## What to Generate:
1. **Epiphanies** - Sudden realizations that feel genuinely insightful
   - Only generate if you discover something non-obvious
   - Example: "I just realized you always talk about space when you're feeling down"
   
2. **Reasoning traces** - Successful problem-solving patterns worth remembering
   - Only store if the reasoning could help similar future problems
   
3. **Response patterns** - Styles that resonated with this user
   - Note what worked so future responses can be tailored

## Guidelines:
- Use tools to gather data BEFORE drawing conclusions
- Be selective - quality over quantity
- Don't force insights if nothing meaningful emerges
- Consider the user's privacy and comfort

Start by analyzing conversation patterns, then dig deeper based on what you find."""

    async def _execute_tool(self, tool_call: dict, tools: List[BaseTool]) -> str:
        """Execute a tool and return its result."""
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        
        selected_tool = next((t for t in tools if t.name == tool_name), None)
        
        if selected_tool:
            try:
                return await selected_tool.ainvoke(tool_args)
            except Exception as e:
                logger.error(f"InsightAgent tool {tool_name} failed: {e}")
                return f"Error: {e}"
        else:
            return f"Error: Tool {tool_name} not found"
    
    def _collect_results(self, messages: List, steps: int, tools_used: int) -> InsightResult:
        """Collect results from the message history."""
        # Parse tool results to extract generated artifacts
        epiphanies = []
        patterns = []
        traces = []
        insights = []
        
        for msg in messages:
            if isinstance(msg, ToolMessage):
                # Parse tool outputs for artifacts
                # (Implementation depends on tool output format)
                pass
            elif isinstance(msg, AIMessage) and msg.content:
                # Final message may contain summary insights
                insights.append(str(msg.content))
        
        return InsightResult(
            epiphanies=epiphanies,
            patterns=patterns,
            traces=traces,
            insights=insights,
            tools_used=tools_used,
            steps_taken=steps
        )
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

```python
# src_v2/workers/insight_worker.py

from arq import cron
from src_v2.agents.insight_agent import InsightAgent

insight_agent = InsightAgent()

async def analyze_user(ctx, user_id: str, character_name: str):
    """Worker task to analyze a specific user."""
    result = await insight_agent.run(user_id, character_name)
    logger.info(f"Insight analysis complete: {result.epiphanies} epiphanies, "
                f"{result.patterns} patterns, {result.traces} traces")

class WorkerSettings:
    functions = [analyze_user]
    cron_jobs = [
        # Run insight analysis for active users every hour
        cron(analyze_active_users, hour=None, minute=0)  # Every hour
    ]
```

Until C3 is implemented, can use simple `asyncio.create_task` with in-memory scheduling:

```python
# Temporary implementation before Worker Queues
async def schedule_insight_analysis(user_id: str, character_name: str):
    """Schedule insight analysis in background."""
    async def run_analysis():
        await asyncio.sleep(60)  # Delay to batch with other messages
        await insight_agent.run(user_id, character_name)
    
    asyncio.create_task(run_analysis())
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
- [ ] Create `InsightAgent` class with ReAct loop
- [ ] Implement data gathering tools (analyze patterns, detect themes, etc.)
- [ ] Basic scheduling via `asyncio.create_task`
- [ ] Unit tests for agent logic

### Phase 2: Action Tools (2-3 days)
- [ ] Create database migrations for new tables
- [ ] Implement `generate_epiphany` tool
- [ ] Implement `store_reasoning_trace` tool
- [ ] Implement `learn_response_pattern` tool
- [ ] Integration tests

### Phase 3: Integration (1-2 days)
- [ ] Wire into `AgentEngine` for trace/pattern injection
- [ ] Wire into character prompts for epiphany references
- [ ] Add trigger logic in `bot.py`
- [ ] End-to-end testing

### Phase 4: Worker Queue (After C3)
- [ ] Migrate to arq/Redis scheduling
- [ ] Add monitoring/alerting
- [ ] Add admin API endpoints

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
