# Prompt File Logging Coverage

**Origin**: Human-AI collaboration during identity bleed debugging (Dec 4, 2025)  
**Status**: Reference documentation  
**Last Updated**: 2025-12-04

## Overview

WhisperEngine uses two observability systems for LLM prompts:

1. **File-based prompt logs** (`logs/prompts/`) - JSON files with full prompt/response pairs
2. **LangSmith traces** - Cloud-based observability for LangGraph executions

This document maps which code paths use which system, and explains the rationale.

## Prompt Logging Coverage Matrix

| Code Path | File Logging | LangSmith | Rationale |
|-----------|--------------|-----------|-----------|
| **Supergraph** (`master_graph_agent.run`) | ❌ No | ✅ Yes | Graph execution has multiple LLM calls; file logging would be redundant and incomplete |
| **Fast Mode** (direct LLM call) | ✅ Yes | ✅ Yes | Linear path, single prompt/response pair, easy to log |
| **Character Agency** (`CharacterGraphAgent`) | ✅ Yes | ✅ Yes | Has internal logging before graph execution |
| **Reflective Mode** (streaming) | ✅ Yes | ✅ Yes | Linear streaming path, logs before yield |
| **Manipulation blocks** (sycophancy, boundaries) | ✅ Yes | ✅ Yes | Linear LLM calls for safety checks |

## Detailed Path Analysis

### Supergraph Path (Primary)
**Location**: `src_v2/agents/engine.py` lines ~140-160  
**Entry**: `AgentEngine.generate_response()` when `ENABLE_SUPERGRAPH=true`

```python
result = await self.master_graph_agent.run(...)
return result.get("response", "")
```

**Why no file logging**:
- Supergraph executes a LangGraph with multiple nodes (memory retrieval, response generation, fact extraction, etc.)
- Each node may invoke the LLM separately
- Logging "the prompt" doesn't make sense when there are 5+ prompts in one execution
- LangSmith captures the full trace with all intermediate states

### Fast Mode Path
**Location**: `src_v2/agents/engine.py` lines ~370-400  
**Entry**: When complexity is `simple` and no special intents detected

```python
self._log_prompt(user_id, prompt, response, "fast_mode")
```

**Why file logging works**:
- Single LLM call with one prompt → one response
- Easy to serialize to JSON
- Useful for quick debugging without LangSmith access

### Character Agency Path
**Location**: `src_v2/agents/engine.py` lines ~320-360  
**Entry**: When `ENABLE_CHARACTER_AGENCY=true` and autonomous action triggered

```python
# CharacterGraphAgent has internal logging
result = await self.character_agent.run(...)
```

**Why file logging works**:
- The agent logs before executing its graph
- Captures the "decision prompt" even if graph has multiple steps

### Reflective Mode Path
**Location**: `src_v2/agents/engine.py` lines ~290-320  
**Entry**: When complexity is `complex` and `ENABLE_REFLECTIVE_MODE=true`

```python
self._log_prompt(user_id, prompt, response, "reflective")
```

**Why file logging works**:
- Although reflective mode uses ReAct loop internally
- We log the final assembled prompt and response
- Intermediate reasoning is in LangSmith

### Manipulation Blocks
**Location**: `src_v2/agents/engine.py` various safety check locations

```python
self._log_prompt(user_id, prompt, response, "sycophancy_check")
self._log_prompt(user_id, prompt, response, "boundary_check")
```

**Why file logging works**:
- These are simple yes/no LLM calls
- Single prompt, single response
- Critical for auditing safety decisions

## File Log Format

Location: `logs/prompts/{bot_name}_{timestamp}_{user_id}.json`

```json
{
  "timestamp": "2025-12-04T12:13:07.123456",
  "bot_name": "aetheris",
  "user_id": "1419745193577549876",
  "mode": "fast_mode",
  "prompt": "...",
  "response": "...",
  "metadata": {
    "complexity": "simple",
    "model": "anthropic/claude-sonnet-4"
  }
}
```

## When to Use Which System

### Use File Logs When:
- Quick local debugging without internet
- Auditing specific user interactions
- Need to reproduce exact prompt/response pair
- Checking safety decision prompts

### Use LangSmith When:
- Debugging Supergraph execution flow
- Understanding why a particular node failed
- Analyzing token usage across nodes
- Tracing memory retrieval decisions
- Full execution timeline needed

## Adding Logging to New Paths

If you add a new code path:

1. **Linear LLM call** (single prompt → response): Add `self._log_prompt()`
2. **Graph execution** (LangGraph): Rely on LangSmith, don't add file logging
3. **Safety checks**: Always add file logging for audit trail

Example:
```python
# Linear path - add file logging
response = await self.llm.ainvoke(prompt)
self._log_prompt(user_id, prompt, response, "my_new_feature")

# Graph path - skip file logging, LangSmith handles it
result = await self.my_graph.run(state)
# No _log_prompt needed
```

## Known Gaps

| Gap | Impact | Decision |
|-----|--------|----------|
| Supergraph prompts not in files | Must use LangSmith for debugging | Acceptable - LangSmith is primary observability |
| Cross-bot conversation prompts | Logged if via Fast Mode, not if via Supergraph | Same as above |
| Background worker prompts (insights, summarization) | Logged in LangSmith only | Workers use graphs, file logging not appropriate |

## Related Documentation

- `docs/guide/LANGSMITH_SETUP.md` - How to access LangSmith traces
- `src_v2/agents/engine.py` - Main code paths
- `src_v2/agents/master_graph.py` - Supergraph implementation
