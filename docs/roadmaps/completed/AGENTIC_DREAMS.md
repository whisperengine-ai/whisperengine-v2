# Agentic Dreams (The "DreamWeaver")

**Document Version:** 1.0  
**Created:** November 29, 2025  
**Status:** ✅ Implemented  
**Priority:** MEDIUM  
**Complexity:** High  
**Prerequisites:** Insight Agent (Complete), Worker Queue (Complete)

---

## Overview

Currently, dream generation (`src_v2/memory/dreams.py`) is a **linear pipeline**: it fetches today's summaries, facts, and observations, then asks an LLM to "write a dream about this."

This roadmap proposes upgrading the dream system to an **Agentic ReAct Loop** (the "DreamWeaver"). Instead of being fed a static list of inputs, the DreamWeaver will actively "wander" through the character's memory space, making associative leaps between recent events and distant memories, mimicking the way human REM sleep consolidates memory.

### The Shift
| Feature | Current (Linear) | Proposed (Agentic) |
|---------|------------------|--------------------|
| **Process** | Fetch Data → Generate Text | Think → Search → Associate → Synthesize |
| **Inputs** | Fixed (Today's summaries) | Dynamic (Today's events + associative lookups) |
| **Depth** | Shallow (Recaps the day) | Deep (Connects today to months ago) |
| **Creativity** | Limited by prompt | Emergent from tool usage |

---

## Architecture

### The DreamWeaver Agent

The agent runs nightly (via the existing worker cron job) but uses a loop instead of a single call.

```python
class DreamWeaverAgent:
    """
    An agent that 'hallucinates' by traversing the vector memory graph.
    It starts with 'Day Residue' (today's events) and follows associative threads.
    """
    def __init__(self):
        self.llm = create_llm(temperature=1.2, mode="creative")  # High temp for dreams
        self.tools = [
            WanderMemoryTool(),      # Find semantically related but distant memories
            GetRandomFactTool(),     # Inject random knowledge
            CheckEmotionalEchoTool() # Find past memories with matching sentiment
        ]
```

### The "Wander" Loop

1.  **Seed**: The agent is given "Day Residue" (top 3 events from today).
2.  **Association**: The agent picks one event and uses `WanderMemoryTool` to find a connection.
    *   *Agent Thought*: "User X mentioned 'apples' today. I wonder what else I know about apples or red things from the past?"
    *   *Tool Output*: "6 months ago, User Y talked about a 'red sports car'."
3.  **Synthesis**: The agent weaves these disparate elements together.
    *   *Dream Fragment*: "I was eating an apple, but it tasted like gasoline, and suddenly I was driving a red sports car..."
4.  **Repeat**: This continues for 3-5 steps until a full narrative arc is formed.

---

## New Tools

### `wander_memory_space`
Searches for memories that are **semantically related** but **temporally distant**.
*   **Input**: `query` (e.g., "apples"), `min_age_days` (e.g., 30)
*   **Logic**: Vector search with a time filter to exclude recent events.

### `check_emotional_echo`
Searches for memories that match the **sentiment** of a current event, regardless of topic.
*   **Input**: `emotion` (e.g., "anxiety"), `intensity` (high)
*   **Logic**: Filter by metadata `mood` or `sentiment`.

### `get_random_symbol`
Fetches a random archetype or symbol from a static library or knowledge graph to inject surrealism.

---

## Implementation Plan

### Phase 1: The Tools ✅
- [x] Created tools in `src_v2/tools/dreamweaver_tools.py`
- [x] Implemented `WanderMemoryTool` (vector search + time filter)
- [x] Implemented `CheckEmotionalEchoTool` (metadata filter)

### Phase 2: The Agent ✅
- [x] Created `src_v2/agents/dreamweaver.py`
- [x] Implemented the ReAct loop with configurable temperature
- [x] Designed narrative planning and weaving prompts

### Phase 3: Integration ✅
- [x] Worker tasks use `DreamWeaverAgent` via `run_agentic_dream_generation`
- [x] Feature flag: `ENABLE_AGENTIC_NARRATIVES`

### Phase 4: Tuning (Ongoing)
- [x] Temperature set to 0.7 for balanced creativity
- [x] Voice synthesis pass ensures character consistency

---

## Database Changes
None required. Uses existing `v2_memories` (Qdrant) and `v2_chat_history` (Postgres).

## Cost Implications
*   **Current**: 1 LLM call per night per bot.
*   **Agentic**: 3-5 LLM calls per night per bot (Reasoning steps).
*   **Estimate**: ~3x cost increase for dreams, but still negligible compared to daily chat volume.

---

## Related Documents
- [INSIGHT_AGENT.md](./INSIGHT_AGENT.md) - The analytical counterpart to this creative agent.
- [MEMORY_SYSTEM.md](../architecture/MEMORY_SYSTEM.md) - Underlying vector storage.
