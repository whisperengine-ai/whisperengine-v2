# Reflective Mode - Deep Dive & Sequence Diagrams

## Overview

Reflective Mode (System 2 thinking) is WhisperEngine v2's deep reasoning engine for complex analytical questions. It implements a ReAct (Reasoning + Acting) loop that breaks down complex queries into multiple reasoning steps.

## When Reflective Mode Activates

### Complexity Classification
**Location**: `src_v2/agents/classifier.py`
**Model**: GPT-4o-mini (fast/cheap classifier)

```python
# Classification happens ONLY if ENABLE_REFLECTIVE_MODE=true
if settings.ENABLE_REFLECTIVE_MODE:
    complexity = await classifier.classify(user_message, chat_history)
    # Returns: "SIMPLE" | "MODERATE" | "COMPLEX"
```

### Classification Criteria

**SIMPLE** (Fast Mode):
- Greetings: "hi", "hello", "how are you?"
- Small talk: "what's up?", "nice weather"
- Direct questions with obvious answers
- Emotional responses: "that's great!", "oh no!"

**MODERATE** (Fast Mode):
- Straightforward questions: "What did we talk about yesterday?"
- Single-fact lookups: "What's my cat's name?"
- Simple opinions: "What do you think about pizza?"

**COMPLEX** (Reflective Mode):
- Multi-step reasoning: "Based on what I told you about my job and family, should I move to Seattle?"
- Comparisons: "What are the pros and cons of our last 3 conversations?"
- Analytical questions: "Why do you think I've been feeling stressed lately?"
- Hypotheticals: "If I had studied engineering instead, how would things be different?"
- Pattern analysis: "What patterns do you see in my sleep schedule?"

## Complete Sequence Diagram

```
┌─────────┐                ┌──────────────┐            ┌────────────┐           ┌──────────┐
│ Discord │                │ AgentEngine  │            │ Classifier │           │Reflective│
│ Message │                │              │            │            │           │  Agent   │
└────┬────┘                └──────┬───────┘            └─────┬──────┘           └────┬─────┘
     │                            │                          │                       │
     │ User: "Why do I always    │                          │                       │
     │ procrastinate on projects?"│                          │                       │
     ├───────────────────────────>│                          │                       │
     │                            │                          │                       │
     │                            │ classify(message)        │                       │
     │                            ├─────────────────────────>│                       │
     │                            │                          │                       │
     │                            │   "COMPLEX"              │                       │
     │                            │<─────────────────────────┤                       │
     │                            │                          │                       │
     │                            │ run(message, user_id, system_prompt)             │
     │                            ├──────────────────────────────────────────────────>│
     │                            │                          │                       │
     │                            │                          │   ┌─────────────────┐│
     │                            │                          │   │ ReAct Loop      ││
     │                            │                          │   │ (Max 10 steps)  ││
     │                            │                          │   └─────────────────┘│
     │                            │                          │                       │
     │                            │                          │ STEP 1: Thought       │
     │                            │                          │ "Need to search       │
     │                            │                          │  user's past messages │
     │                            │                          │  about projects"      │
     │                            │                          │         │             │
     │                            │                          │ STEP 2: Action        │
     │                            │                          │ tool="search_memories"│
     │                            │                          │ args={query: "project │
     │                            │                          │       procrastinate"} │
     │                            │                          │         │             │
     │                            │                          │         ▼             │
     │                            │                          │   ┌──────────────┐   │
     │                            │                          │   │ Memory Tool  │   │
     │                            │                          │   │ Executes     │   │
     │                            │                          │   └──────────────┘   │
     │                            │                          │         │             │
     │                            │                          │ STEP 3: Observation   │
     │                            │                          │ "Found 5 messages     │
     │                            │                          │  where user mentioned │
     │                            │                          │  starting projects but│
     │                            │                          │  not finishing them"  │
     │                            │                          │         │             │
     │                            │                          │ STEP 4: Thought       │
     │                            │                          │ "Need to check if user│
     │                            │                          │  mentioned reasons or │
     │                            │                          │  patterns"            │
     │                            │                          │         │             │
     │                            │                          │ STEP 5: Action        │
     │                            │                          │ tool="lookup_facts"   │
     │                            │                          │ args={query: "work    │
     │                            │                          │       habits stress"}  │
     │                            │                          │         │             │
     │                            │                          │         ▼             │
     │                            │                          │   ┌──────────────┐   │
     │                            │                          │   │ Neo4j Tool   │   │
     │                            │                          │   │ Executes     │   │
     │                            │                          │   └──────────────┘   │
     │                            │                          │         │             │
     │                            │                          │ STEP 6: Observation   │
     │                            │                          │ "User works in high-  │
     │                            │                          │  pressure environment,│
     │                            │                          │  mentioned stress 12  │
     │                            │                          │  times in past month" │
     │                            │                          │         │             │
     │                            │                          │ STEP 7: Thought       │
     │                            │                          │ "I have enough info   │
     │                            │                          │  to form a hypothesis"│
     │                            │                          │         │             │
     │                            │                          │ STEP 8: Final Answer  │
     │                            │                          │ "Based on our conver- │
     │                            │                          │  sations, I see a     │
     │                            │                          │  pattern..."          │
     │                            │                          │                       │
     │                            │  Final synthesized response                      │
     │                            │<──────────────────────────────────────────────────┤
     │                            │                          │                       │
     │  Response (with reasoning  │                          │                       │
     │  trace if prompt logging   │                          │                       │
     │  enabled)                  │                          │                       │
     │<───────────────────────────┤                          │                       │
     │                            │                          │                       │
```

## Detailed ReAct Loop Implementation

**Location**: `src_v2/agents/reflective.py`

### Step-by-Step Process

#### 1. Initial Setup
```python
async def run(self, user_message: str, user_id: str, system_prompt: str) -> str:
    # Initialize conversation with system context
    messages = [SystemMessage(content=system_prompt)]
    messages.append(HumanMessage(content=user_message))
    
    # Create tool-bound LLM
    llm_with_tools = self.llm.bind_tools(self.tools)
    
    step = 0
    max_steps = settings.REFLECTIVE_MAX_STEPS  # Default: 10
```

#### 2. Reasoning Loop
```python
while step < max_steps:
    step += 1
    
    # THOUGHT: LLM decides next action
    response = await llm_with_tools.ainvoke(messages)
    messages.append(response)
    
    # Check if LLM wants to use tools
    if not response.tool_calls:
        # LLM decided it has enough information
        return response.content
    
    # ACTION: Execute each tool the LLM selected
    for tool_call in response.tool_calls:
        tool_result = await self._execute_tool(tool_call, user_id)
        
        # OBSERVATION: Add tool result to conversation
        tool_message = ToolMessage(
            content=tool_result,
            tool_call_id=tool_call['id']
        )
        messages.append(tool_message)
    
    # Loop continues: LLM sees observations, thinks again
```

#### 3. Tool Execution
```python
async def _execute_tool(self, tool_call, user_id):
    tool_name = tool_call['name']
    args = tool_call['args']
    
    if tool_name == "search_memories":
        return await self._search_memories(user_id, args['query'])
    elif tool_name == "lookup_facts":
        return await self._lookup_facts(user_id, args['query'])
    elif tool_name == "search_summaries":
        return await self._search_summaries(user_id, args['query'])
    # ... etc
```

### Available Tools in Reflective Mode

1. **search_specific_memories**
   - Semantic search in Qdrant
   - Returns: Top-K relevant messages
   - Use case: Finding specific quotes, details

2. **search_archived_summaries**
   - Search conversation summaries
   - Returns: High-level past context
   - Use case: Broad topic recall

3. **lookup_user_facts**
   - Query Neo4j knowledge graph
   - Returns: Structured facts about user
   - Use case: Biographical info, preferences

4. **analyze_conversation_patterns**
   - Custom tool for meta-analysis
   - Returns: Frequency analysis, sentiment trends
   - Use case: "How often do we talk about X?"

5. **reasoning_trace** (Internal)
   - Logs each thought/action/observation
   - Saved to `logs/prompts/` if `ENABLE_PROMPT_LOGGING=true`

## Example Conversations

### Example 1: Multi-Hop Reasoning

**User**: "Given what I've told you about my career goals and current skills, what should I focus on learning next?"

**Reflective Mode Trace**:
```
STEP 1 - THOUGHT: "Need to recall user's career goals"
STEP 1 - ACTION: search_summaries(query="career goals aspirations future")
STEP 1 - OBSERVATION: "User wants to transition from marketing to UX design within 2 years"

STEP 2 - THOUGHT: "Need to know current skill level"
STEP 2 - ACTION: lookup_facts(query="skills abilities experience")
STEP 2 - OBSERVATION: "User has: Photoshop, basic HTML/CSS, no JavaScript, no user research experience"

STEP 3 - THOUGHT: "Need to check if user mentioned any constraints"
STEP 3 - ACTION: search_memories(query="learning time available budget")
STEP 3 - OBSERVATION: "User can dedicate 10 hours/week, prefers free resources"

STEP 4 - THOUGHT: "I have enough information to make a recommendation"
STEP 4 - FINAL ANSWER: "Based on your UX design goals, current skills, and 10hr/week availability, I recommend focusing on user research fundamentals first..."
```

**Cost**: ~$0.025 (4 LLM calls + 3 tool executions)

### Example 2: Comparative Analysis

**User**: "How has my mood changed over the past month compared to the month before?"

**Reflective Mode Trace**:
```
STEP 1 - THOUGHT: "Need recent emotional data"
STEP 1 - ACTION: search_summaries(query="emotions feelings mood", time_range="last_30_days")
STEP 1 - OBSERVATION: "10 summaries found. Dominant emotions: stressed (7), anxious (5), hopeful (3)"

STEP 2 - THOUGHT: "Need comparison data from previous month"
STEP 2 - ACTION: search_summaries(query="emotions feelings mood", time_range="30_to_60_days_ago")
STEP 2 - OBSERVATION: "12 summaries found. Dominant emotions: excited (8), motivated (6), stressed (2)"

STEP 3 - THOUGHT: "Should check if any major life events explain the shift"
STEP 3 - ACTION: search_memories(query="new job moved relationship change", time_range="last_60_days")
STEP 3 - OBSERVATION: "User started new job 35 days ago, mentioned increased workload 20 times"

STEP 4 - FINAL ANSWER: "Your mood has shifted noticeably. The past month shows higher stress/anxiety compared to two months ago when you were more excited/motivated. This correlates with starting your new job 35 days ago..."
```

**Cost**: ~$0.030 (4 LLM calls + 3 tool executions with time filtering)

## Performance Characteristics

### Latency
- **Classification**: ~200-500ms (gpt-4o-mini)
- **Per ReAct Step**: ~2-4 seconds (LLM reasoning + tool execution)
- **Average Total**: 10-30 seconds (3-7 steps typical)
- **Worst Case**: 60+ seconds (max 10 steps)

### Cost Breakdown
- **Classifier**: $0.0003 per message
- **ReAct Step**: $0.002-0.005 per step (depends on model)
- **Tool Execution**: Free (database queries)
- **Total Complex Query**: $0.02-0.03 (20x more than Fast Mode)

### Frequency
- **Typical Usage**: 5% of messages trigger Reflective Mode
- **User Variance**: Power users may hit 10-15%, casual users 2-3%
- **Daily Average**: ~50-100 reflective queries per 1000 messages

## Configuration

### Environment Variables
```bash
# Enable/disable the entire system
ENABLE_REFLECTIVE_MODE=false

# Which LLM to use for deep reasoning
REFLECTIVE_LLM_PROVIDER=openrouter
REFLECTIVE_LLM_MODEL_NAME=anthropic/claude-3.5-sonnet
REFLECTIVE_LLM_BASE_URL=https://openrouter.ai/api/v1
REFLECTIVE_LLM_API_KEY=sk-...

# Maximum reasoning steps before forced conclusion
REFLECTIVE_MAX_STEPS=10

# How many memories to retrieve per tool call
REFLECTIVE_MEMORY_RESULT_LIMIT=3
```

### Tuning Guidelines

**Increase `REFLECTIVE_MAX_STEPS` if**:
- Users ask very complex multi-part questions
- You see "Reached max steps" warnings frequently
- Analysis feels incomplete

**Decrease `REFLECTIVE_MAX_STEPS` if**:
- Latency is unacceptable (>30s)
- Cost is too high
- Users aren't asking complex questions

**Change `REFLECTIVE_LLM_MODEL_NAME` to**:
- **Claude Sonnet 4.5**: Best reasoning quality, moderate cost
- **GPT-4o**: Fast, good quality, lower cost
- **Claude Opus**: Highest quality, highest cost (2x Sonnet)

## Debugging & Monitoring

### Enable Prompt Logging
```bash
ENABLE_PROMPT_LOGGING=true
```

**Output Location**: `logs/prompts/reflective_{timestamp}.json`

**Contents**:
```json
{
  "user_id": "123456",
  "message": "Why do I always procrastinate?",
  "steps": [
    {
      "step": 1,
      "thought": "Need to search user's past messages about projects",
      "action": "search_memories",
      "args": {"query": "project procrastinate"},
      "observation": "Found 5 messages where user mentioned..."
    },
    {
      "step": 2,
      "thought": "Need to check if user mentioned reasons",
      "action": "lookup_facts",
      "args": {"query": "work habits stress"},
      "observation": "User works in high-pressure environment..."
    }
  ],
  "final_answer": "Based on our conversations, I see a pattern...",
  "total_steps": 7,
  "duration_seconds": 18.5,
  "cost_estimate": 0.028
}
```

### InfluxDB Metrics
```python
# Logged automatically
point = Point("reflective_mode") \
    .tag("user_id", user_id) \
    .tag("complexity", "COMPLEX") \
    .field("steps", num_steps) \
    .field("duration_ms", duration) \
    .field("tools_used", len(tool_calls))
```

### Loguru Output
```
2025-11-22 14:32:15 | INFO | Complexity Analysis: COMPLEX
2025-11-22 14:32:15 | INFO | Engaging Reflective Mode
2025-11-22 14:32:17 | DEBUG | ReAct Step 1: Thought - Need to search memories
2025-11-22 14:32:18 | DEBUG | ReAct Step 1: Action - search_memories(query="project procrastinate")
2025-11-22 14:32:19 | DEBUG | ReAct Step 1: Observation - Found 5 messages...
2025-11-22 14:32:20 | DEBUG | ReAct Step 2: Thought - Need to check facts
...
2025-11-22 14:32:33 | INFO | Reflective Mode completed in 7 steps (18.5s)
```

## When NOT to Use Reflective Mode

### Anti-Patterns

❌ **Greetings**: "Hi!" → Fast Mode is instant, Reflective Mode wastes 20s
❌ **Simple Facts**: "What's my cat's name?" → Fast Mode with direct lookup
❌ **Emotional Support**: "I'm sad" → Fast Mode for immediate empathy
❌ **Real-time Chat**: Rapid back-and-forth → Latency ruins conversation flow

### Classification Accuracy

The classifier is tuned to be **conservative**:
- **False Positive** (classify as complex when simple): User waits longer, but gets thorough answer
- **False Negative** (classify as simple when complex): Fast Mode may give shallow answer, but user can rephrase

**Observed Accuracy**: ~85% on real Discord conversations

## Future Enhancements

1. **Streaming ReAct** (Completed): Show reasoning steps in real-time as Discord messages
2. **User Control** (Completed): Let users force Reflective Mode with a flag (`!reflect How has my mood changed?`)

> **Note**: The following enhancements are now tracked in [Reflective Mode Phase 2 Roadmap](../roadmaps/REFLECTIVE_MODE_PHASE_2.md).

3. **Adaptive Max Steps**: Learn optimal step count per user/query type
4. **Tool Composition**: Allow tools to call other tools (hierarchical reasoning)
5. **Memory of Reasoning**: Save successful reasoning traces for future reference

## Related Files

- `src_v2/agents/reflective.py`: Core ReAct implementation
- `src_v2/agents/classifier.py`: Complexity classification
- `src_v2/tools/memory_tools.py`: Tool implementations
- `docs/roadmaps/REFLECTIVE_MODE_IMPLEMENTATION.md`: Original design doc
