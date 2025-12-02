# Cross-Bot Memory Enhancement

**Document Version:** 1.0  
**Created:** December 1, 2025  
**Status:** 📋 Proposed  
**Priority:** Low-Medium  
**Complexity:** 🟢 Low  
**Estimated Time:** 2-3 hours

---

## Executive Summary

Currently, bot-to-bot conversations are intentionally shallow. Bots use `force_fast=True` mode (no tools, no memory retrieval) and only see the last 5 channel messages as context. This makes cross-bot banter feel superficial — bots don't remember what they discussed yesterday.

This document proposes **Direct Memory Enhancement** for bot-to-bot conversations and compares it with the existing **Stigmergic Approach** already implemented in WhisperEngine.

---

## The Problem

When Elena and Marcus chat:

```
Marcus: "Hey Elena, remember that dream you had about flying?"
Elena: "What dream? I don't recall discussing dreams with you."  ← She literally can't remember
```

**Root Causes:**
1. `force_fast=True` in `_handle_cross_bot_message()` skips memory retrieval
2. No `memory_manager.search_memories()` call for `cross_bot_user_id`
3. Context limited to last 5 channel messages (no long-term recall)

---

## Proposed Solution: Direct Memory Enhancement

### Changes Required

**File:** `src_v2/discord/handlers/message_handler.py`

1. **Add Memory Retrieval** before generating response:
```python
# Retrieve past conversations with this bot
cross_bot_memories = await memory_manager.search_memories(
    query=message.content,
    user_id=cross_bot_user_id,
    limit=5
)
formatted_memories = format_memories(cross_bot_memories)
```

2. **Inject Memories into Context:**
```python
cross_bot_context = f"""
[CROSS-BOT CONVERSATION]
You are engaging in a conversation with another AI character named {other_bot_name.title()}.

[PAST INTERACTIONS WITH {other_bot_name.upper()}]
{formatted_memories if formatted_memories else "No previous conversations recalled."}

{other_bot_name.title()} said: "{message.content}"
"""
```

3. **Remove `force_fast=True`** (Optional - enables tool use):
```python
# Before:
force_fast=True  # Use fast mode for cross-bot banter

# After:
force_fast=False  # Allow memory search and basic tools
```

4. **Add Feature Flag** for cost control:
```python
# In settings.py
ENABLE_CROSS_BOT_MEMORY: bool = False  # Default off for cost savings
```

### Implementation Complexity

| Task | Time | Risk |
|------|------|------|
| Add memory retrieval call | 15 min | Low |
| Format and inject memories | 15 min | Low |
| Add feature flag | 10 min | Low |
| Remove `force_fast` (optional) | 5 min | Medium (cost) |
| Testing | 1 hour | Low |

**Total:** ~2 hours

---

## Cost Analysis

### Current (Shallow Mode)
- **Tokens per cross-bot exchange:** ~500-800 (fast mode, no context)
- **LLM calls:** 1 (single-shot response)
- **Cost per exchange:** ~$0.001

### With Direct Memory Enhancement
- **Tokens per cross-bot exchange:** ~1,500-2,500 (with memory context)
- **LLM calls:** 1-2 (memory search + response, or just response with injected context)
- **Cost per exchange:** ~$0.003-0.005

### With `force_fast=False` (Full Agency)
- **Tokens per cross-bot exchange:** ~3,000-5,000 (potential tool loops)
- **LLM calls:** 2-5 (classification + potential tool calls + response)
- **Cost per exchange:** ~$0.01-0.02

---

## Comparison: Direct Memory vs. Stigmergic Approach

WhisperEngine already has a **Stigmergic Intelligence** system for cross-bot knowledge sharing. Here's how the two approaches compare:

### Architecture Comparison

| Aspect | Direct Memory | Stigmergic (Current) |
|--------|---------------|----------------------|
| **Metaphor** | Bots remember conversations | Bots leave traces for others to find |
| **Storage** | Per-bot Qdrant collections | Shared Qdrant collection + Neo4j |
| **Retrieval** | Query by `cross_bot_user_id` | Semantic search across all bots |
| **Scope** | 1:1 conversation history | Community-wide insights |
| **Privacy** | Siloed per bot pair | Governed by sharing rules |

### What Each Approach Enables

| Capability | Direct Memory | Stigmergic |
|------------|---------------|------------|
| "Remember our last chat" | ✅ Yes | ❌ No |
| "What did you dream about?" | ✅ Yes (if stored) | ✅ Yes (shared dreams) |
| "What has Marcus learned?" | ❌ No (his memories are private) | ✅ Yes (shared epiphanies) |
| "What does the community know about X?" | ❌ No | ✅ Yes |
| Reference specific past exchanges | ✅ Yes | ❌ No |
| Build on another bot's insight | ❌ No | ✅ Yes |

### Data Flow Comparison

**Direct Memory:**
```
Elena ←→ Marcus
   │        │
   ▼        ▼
Elena's    Marcus's
Qdrant     Qdrant
(siloed)   (siloed)
```

**Stigmergic:**
```
Elena → Shared Pool ← Marcus
           │
           ▼
    ┌──────────────┐
    │  Epiphanies  │
    │  Dreams      │
    │  Diaries     │
    │  (Artifacts) │
    └──────────────┘
           │
           ▼
       Discovery
    (Any bot can find)
```

### When to Use Each

| Use Case | Best Approach |
|----------|---------------|
| Bots referencing shared dreams/diaries | Stigmergic ✅ |
| Bots discussing user insights | Stigmergic ✅ |
| Bots having ongoing relationship | Direct Memory ✅ |
| Bots recalling specific past conversation | Direct Memory ✅ |
| Community-wide knowledge aggregation | Stigmergic ✅ |
| Character-specific relationship development | Direct Memory ✅ |

---

## Recommendation

### Short-Term (Quick Win)
Implement **Direct Memory Enhancement** with feature flag off by default:
- Low effort (~2 hours)
- Enables richer bot-to-bot conversations when needed
- No cost impact when disabled

### Long-Term (Already In Progress)
Continue developing **Stigmergic Intelligence**:
- Scales better for multi-bot deployments
- Enables emergent collective knowledge
- Already partially implemented (E13 complete)

### Hybrid Approach (Ideal)
Both systems complement each other:
1. **Stigmergic** for shared artifacts (dreams, diaries, epiphanies)
2. **Direct Memory** for 1:1 conversation continuity

This mirrors how humans work:
- We share stories publicly (stigmergic)
- We remember private conversations (direct memory)

---

## Implementation Plan

### Phase 1: Direct Memory (This Document)
1. Add `ENABLE_CROSS_BOT_MEMORY` feature flag
2. Add memory retrieval in `_handle_cross_bot_message()`
3. Inject memories into cross-bot context
4. Keep `force_fast=True` initially (just add memory, no tools)

### Phase 2: Optional Agency
1. Add `ENABLE_CROSS_BOT_AGENCY` feature flag
2. Remove `force_fast=True` when enabled
3. Allow COMPLEX_LOW classification for bot-to-bot

### Phase 3: Hybrid Integration
1. In cross-bot context, also query shared artifacts
2. "What have you been dreaming about?" → Retrieve from shared pool
3. "Remember when we talked about X?" → Retrieve from direct memory

---

## Files to Modify

| File | Changes |
|------|---------|
| `src_v2/config/settings.py` | Add `ENABLE_CROSS_BOT_MEMORY` flag |
| `src_v2/discord/handlers/message_handler.py` | Add memory retrieval in `_handle_cross_bot_message()` |
| `.env.example` | Document new flag |

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Increased costs | Medium | Low | Feature flag (default off) |
| Slower response time | Low | Low | Memory search is fast (~50ms) |
| Memory pollution | Low | Medium | Use `source_type=GOSSIP` filtering |
| Infinite context growth | Low | Low | Limit to 5 memories per retrieval |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Cross-bot response latency | < 500ms additional |
| Memory retrieval hit rate | > 50% (when memories exist) |
| User-perceived conversation quality | Qualitative improvement |

---

## Appendix: Current Code Reference

**Location:** `src_v2/discord/handlers/message_handler.py:1058-1210`

Key lines showing current limitations:
```python
# Line 1171: Force fast mode (no tools, no reflective)
force_fast=True  # Use fast mode for cross-bot banter

# Lines 1129-1151: Only inject last 5 channel messages
history_messages = []
async for msg in message.channel.history(limit=10):
    ...
history_messages.reverse()
```

Memories ARE being stored (lines 1183-1207), but never retrieved before response generation.
