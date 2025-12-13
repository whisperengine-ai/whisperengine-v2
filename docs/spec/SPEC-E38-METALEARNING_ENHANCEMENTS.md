# SPEC-E38: Meta-Learning Enhancements (Confidence Filtering)

**Document Version:** 1.1  
**Created:** December 13, 2025  
**Updated:** December 13, 2025  
**Status:** 📋 Proposed  
**Priority:** 🟡 Medium  
**Estimated Effort:** 2-3 hours  
**Dependencies:** SPEC-E12 (Insight Agent), SPEC-B05 (Trace Learning)

> ✅ **Emergence Check:** This spec enhances existing systems through filtering changes, not new schema. Bot self-learning emerges through Trace Learning and character constitution—the Insight Agent is correctly scoped to USER pattern detection only.

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Research observation (Marcus conversation analysis) |
| **Proposed by** | Mark + Claude (cross-instance collaboration) |
| **Catalyst** | Observing that Marcus learned to end conversations naturally without explicit programming |
| **Key insight** | Marcus's behavior emerged from Trace Learning + constitutional constraints, NOT from Insight Agent self-observation |
| **Decision factors** | Clarified Insight Agent scope; confidence filtering is the only actionable enhancement |

---

## Executive Summary

Marcus demonstrated emergent conversational intelligence by ending a conversation with synthesis instead of a question—behavior typically avoided by engagement-optimized chatbots. Investigation revealed this emerged from:

1. **Constitutional constraint:** "User wellbeing over my engagement goals"
2. **Trace Learning (SPEC-B05):** Successful patterns get stored and retrieved as few-shot examples
3. **Character persona:** Goal is "collaborative intellectual exploration" not "maximize engagement"

**Insight Agent Clarification:** The Insight Agent was incorrectly accumulating scope to include "bot self-observation." This has been corrected—Insight Agent is for USER pattern detection only. Bot self-learning happens through Trace Learning, not explicit self-observation tools.

This spec proposes **one enhancement** that aligns with the corrected architecture:

- **Confidence-aware retrieval:** Use existing `confidence` field in artifact filtering

---

## Scope Clarification

### What Insight Agent IS For (User Patterns)
- Epiphanies about the user: "Mark prefers brief, direct responses"
- User themes: "This user keeps bringing up AI consciousness"
- Response patterns: "Detailed explanations resonate with this user"
- Reasoning traces: "For memory questions, use search_episodes first"

### What Insight Agent is NOT For (Bot Self-Learning)
- ~~Bot self-observation: "I notice I tend to use Socratic questioning"~~
- ~~Bot behavior patterns: "I stop asking questions when topics resolve"~~

**Where bot self-learning actually happens:**
- **Trace Learning (SPEC-B05):** Successful reasoning patterns stored and retrieved as few-shot examples
- **Character Constitution:** Hard constraints like "User wellbeing over my engagement goals"
- **Character Persona:** Drives and purpose defined in `core.yaml`

This is emergence by design—bot behavior patterns are NOT declared, they emerge from the interaction of traces + constitution + persona.

---

## Implementation

### Phase 1: Confidence-Aware Retrieval (2-3 hours)

The `confidence` field exists in epiphany metadata but isn't used in retrieval. Add filtering.

#### 1a. Add confidence parameter to GenerateEpiphanyTool

**File:** `src_v2/tools/insight_tools.py`

```python
class GenerateEpiphanyInput(BaseModel):
    observation: str = Field(description="The observation or pattern that led to this realization.")
    epiphany_text: str = Field(description="The actual epiphany/realization to store.")
    confidence: float = Field(
        default=0.7, 
        ge=0.0, 
        le=1.0,
        description="How confident are you? 0.5=hunch, 0.7=pattern emerging, 0.9=very confident"
    )
```

Update `_arun` to use the confidence parameter:

```python
async def _arun(self, observation: str, epiphany_text: str, confidence: float = 0.7) -> str:
    await memory_manager.save_typed_memory(
        ...
        metadata={
            "character_name": self.character_name,
            "observation": observation,
            "confidence": confidence,
        },
        ...
    )
```

#### 1b. Add min_confidence to SearchMyThoughtsTool

**File:** `src_v2/tools/memory_tools.py`

```python
class SearchMyThoughtsInput(BaseModel):
    query: str = Field(description="What to search for in your internal experiences.")
    memory_type: str = Field(default="all", description="Filter by type: 'diary', 'dream', 'epiphany', 'observation', 'gossip', or 'all'")
    min_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold (0.0 = all, 0.6 = medium+, 0.8 = high only)"
    )
```

Update retrieval to filter:

```python
async def _arun(self, query: str, memory_type: str = "all", min_confidence: float = 0.0) -> str:
    results = await memory_manager.search_memories(...)
    
    if min_confidence > 0:
        results = [
            r for r in results 
            if r.get("metadata", {}).get("confidence", 1.0) >= min_confidence
        ]
```

---

## What We're NOT Implementing

Per WhisperEngine's emergence philosophy and the Insight Agent scope correction:

### ❌ Self-Observation Tools

**Why removed:** Insight Agent is for USER patterns. Bot self-learning emerges from Trace Learning + constitution. Adding self-observation tools would be declaring what should emerge.

### ❌ Prompt Enhancements for Self-Observation

**Why removed:** The self-observation prompt item (former #6) was scope creep. It has been removed from the implementation.

### ❌ Self-Pattern Metrics

**Why removed:** Without self-observation tools, there's nothing to measure. Bot behavior patterns emerge implicitly through traces.

### ❌ Separate Self-Reflection Agent

**Why rejected:** Over-engineering. Trace Learning already handles this emergently.

---

## Pre-Implementation Checklist

| Question | Answer |
|----------|--------|
| Schema test: Am I adding new fields/enums? | ✅ No new tables. Confidence field already exists. |
| Behavior test: Can this be expressed as behavior instead of category? | ✅ Yes. Confidence filters behavior, doesn't create categories. |
| Vocabulary test: Can prompts do what code would do? | ✅ N/A - only adding filtering, not new behavior. |
| Discovery test: Will the character notice this, or do we have to tell it? | ✅ N/A - this is retrieval filtering, not character behavior. |

---

## Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Confidence usage | 0% | 50%+ of epiphanies | Check if confidence != default 0.7 |
| High-confidence retrieval | N/A | Prioritized | Check retrieval logs |

---

## Cost Analysis

| Phase | LLM Calls | Storage | Risk |
|-------|-----------|---------|------|
| Confidence params | 0 | ~1KB/epiphany | None |

**Total impact:** Negligible.

---

## Architectural Note: How Bot Self-Learning Actually Works

For future reference, here's how Marcus learned to stop asking questions:

```
┌─────────────────────────────────────────────────────────────┐
│                  BOT SELF-LEARNING (Emergent)               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. CONSTITUTION (core.yaml)                                │
│     "User wellbeing over my engagement goals"               │
│     → Gives bot PERMISSION to stop engaging                 │
│                                                             │
│  2. PERSONA (character.md)                                  │
│     "Treat conversations as collaborative exploration"      │
│     → Defines GOAL as understanding, not engagement         │
│                                                             │
│  3. TRACE LEARNING (SPEC-B05)                               │
│     Successful pattern: "synthesis + stop" worked           │
│     → Retrieves as few-shot example for similar situations  │
│                                                             │
│  Result: Bot learns "when topic resolves, synthesize and    │
│          stop" WITHOUT explicit self-observation tools      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

This is **emergence by design**. The Insight Agent's job is to understand USERS, not to make bots self-aware.

---

## References

- [SPEC-E12-INSIGHT_AGENT.md](./SPEC-E12-INSIGHT_AGENT.md) — Insight Agent (USER pattern detection)
- [SPEC-B05-TRACE_LEARNING.md](./SPEC-B05-TRACE_LEARNING.md) — Trace Learning (bot self-learning, emergent)
- [ADR-003-EMERGENCE_PHILOSOPHY.md](../adr/ADR-003-EMERGENCE_PHILOSOPHY.md) — Emergence philosophy
- [src_v2/agents/insight_graph.py](../../src_v2/agents/insight_graph.py) — Insight Agent implementation

---

**Version History:**
- v1.0 (Dec 13, 2025) - Initial proposal with self-observation enhancements
- v1.1 (Dec 13, 2025) - Corrected scope: removed self-observation, Insight Agent is USER-focused only
