# Bot-to-Bot Conversation Pipeline

**Last Updated:** December 2, 2025  
**Status:** Active (Phase E6 complete)

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | E6 Multi-bot social design |
| **Proposed by** | Mark (social dynamics) |
| **Key insight** | Bots talking to bots need modified pipeline — fast path, gossip memory, cross-context injection |

---

This document traces the complete decision flow when one WhisperEngine bot talks to another, from message receipt through classification to response generation.

---

## Overview

Bot-to-bot conversations follow a **modified version** of the normal user pipeline with several key differences:
1. **100% fast path** (no tools, direct LLM response)
2. **Creative content classification** (dream journals, diary entries → SIMPLE)
3. **Cross-bot context injection** (special system prompt section)
4. **Memory storage** with `MemorySourceType.GOSSIP`

---

## Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────┐
│ 1. MESSAGE RECEIPT (message_handler.py:108-120)        │
│    • on_message() receives Discord message              │
│    • Checks: if message.author.bot → go to step 2      │
│    • Non-bot messages → normal user pipeline           │
└─────────────────────┬───────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│ 2. CROSS-BOT DETECTION (message_handler.py:1177-1188)  │
│    • Check: settings.ENABLE_CROSS_BOT_CHAT?            │
│    • Call: cross_bot_manager.detect_cross_bot_mention()│
│    • Parse: @mention or reply to our message?          │
│    • If NO mention → EXIT (ignore bot message)         │
│    • If mention found → proceed to step 3              │
└─────────────────────┬───────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│ 3. SHOULD RESPOND CHECK (message_handler.py:1190-1193) │
│    • cross_bot_manager.should_respond(mention)         │
│    • Checks: probabilistic response (40% base)         │
│    • Checks: chain length limits (max 5 in sequence)   │
│    • If NO → EXIT (skip this mention)                  │
│    • If YES → proceed to step 4                        │
└─────────────────────┬───────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│ 4. CONTEXT RETRIEVAL (message_handler.py:1256-1306)    │
│    • cross_bot_user_id = str(message.author.id)        │
│    • context_builder.build_context(cross_bot_user_id)  │
│    • Parallel fetch:                                    │
│       - Postgres: Recent chat history (10 msgs)        │
│       - Qdrant: Vector memories (5 relevant)           │
│       - Neo4j: Knowledge facts                         │
│       - Summaries: Past conversation summaries (2)     │
│    • Format into cross_bot_context string              │
└─────────────────────┬───────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│ 5. PIPELINE SELECTION (message_handler.py:1338-1342)   │
│    • use_fast_mode = True  # Always fast for cross-bot │
│    • Rationale: context already pre-fetched in step 4  │
│    • Tools add cost/latency, rarely add value          │
│    • Log: "Cross-bot pipeline: force_fast=True"        │
└─────────────────────┬───────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│ 6. AGENT ENGINE CALL (message_handler.py:1345-1355)    │
│    • agent_engine.generate_response()                  │
│    • user_id=cross_bot_user_id (other bot's ID)       │
│    • force_fast=True (always fast for cross-bot)      │
│    • context_variables includes:                       │
│       - is_cross_bot: True                             │
│       - cross_bot_context: formatted context string    │
│       - user_name: other bot's name                    │
└─────────────────────┬───────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│ 7. SUPERGRAPH ENTRY (engine.py:145-156)                │
│    • Check: user_id present? → YES (cross_bot_user_id)│
│    • Delegate to: master_graph_agent.run()             │
│    • Supergraph coordinates full pipeline              │
└─────────────────────┬───────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│ 8. CONTEXT NODE (master_graph.py:93-115)               │
│    • Check: prefetched_memories in context_variables?  │
│    • If YES → Use pre-fetched, skip Qdrant query       │
│    • If NO → Fetch Vector memories from Qdrant         │
│    • (Trust, Goals, Knowledge handled by next node)    │
└─────────────────────┬───────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│ 9. CLASSIFIER NODE (master_graph.py:109-117)           │
│    • classifier.classify()                             │
│    • Input: user_message (other bot's message)         │
│    • bot_name: our bot name (for metrics)              │
│    • Returns: {complexity: str, intents: list}         │
│    • ⚠️ CRITICAL LOGIC (see section below)             │
└─────────────────────┬───────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│ 10. PROMPT BUILDER NODE (master_graph.py:119-159)      │
│    • context_builder.build_system_context()            │
│    • Includes:                                         │
│       - Character identity (character.md)              │
│       - Trust level with other bot                     │
│       - Goals, Diary, Dreams                           │
│       - cross_bot_context (from step 4)                │
│       - Vector memories (from step 8)                  │
│    • Template substitution: {user_name}, {datetime}    │
└─────────────────────┬───────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│ 11. ROUTER LOGIC (master_graph.py:161-180)             │
│    • Input: classification result, force_fast flag     │
│    • Decision tree:                                    │
│       1. image_urls present? → "fast" (vision)        │
│       2. force_fast=True? → "fast" (ALL cross-bot)    │
│       3. complexity=MID/HIGH + reflective enabled?    │
│          → "reflective" (ReAct tools) [users only]    │
│       4. complexity=LOW? → "character" (no tools)     │
│       5. Default → "fast"                             │
└─────────────────────┬───────────────────────────────────┘
                      ↓
                      ↓
┌─────────────────────────────────────────────────────────┐
│ 12. FAST PATH (100% cross-bot)                         │
│    • Single LLM call (no tools)                        │
│    • Cheap (~$0.001) and fast (~1-2s)                  │
│    • Context already pre-fetched in step 4             │
│    • Rich context without tool overhead                │
└─────────────────────┬───────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│ 13. RESPONSE & STORAGE (message_handler.py:1360-1395)  │
│    • Send: message.reply(response, mention_author=True)│
│    • Record: cross_bot_manager.record_response()       │
│    • Store to memory:                                  │
│       - Other bot's message (role="human")             │
│       - Our response (role="ai")                       │
│       - source_type=MemorySourceType.GOSSIP            │
│    • Enqueue background jobs:                          │
│       - Knowledge extraction                           │
│       - Summarization (after N messages)               │
└─────────────────────────────────────────────────────────┘
```

---

## Classifier Decision Logic (Step 9)

The classifier is **critical** for bot-to-bot conversations because it determines whether expensive tools are needed.

### Prompt Template (classifier.py:226-253)

```
COMPLEXITY LEVELS:
1. SIMPLE: Greetings, casual chat, NO tools needed.
   - Sharing creative writing, dreams, or diary entries WITHOUT a question.
   - "Here is my dream...", "I wrote this...", "Journal entry...".

2. COMPLEX_LOW: Needs 1-2 simple lookups.
   - "Where did you grow up?" (memory lookup)
   - "What is my name?" (fact lookup)

3. COMPLEX_MID: Needs 3-5 steps.
   - Image generation requests
   - Document analysis
   - Complex math

4. COMPLEX_HIGH: Needs 6+ steps.
   - Deep philosophical questions
   - Multi-step research
```

### Cross-Bot Specific Rules

**ADDED (Dec 2, 2025):**
```python
1. SIMPLE: ... NO tools needed.
   - Sharing creative writing, dreams, or diary entries WITHOUT a specific complex question.
   - "Here is my dream...", "I wrote this...", "Journal entry...".
```

**Why this matters:**
- Before this fix: Dream journals → `COMPLEX_HIGH` (97 cases on `dream` bot)
- After this fix: Dream journals → `SIMPLE` (fast path, cheap)
- Aria frequently posts dream journals to Dream's channel
- Aetheris, Gabriel also share philosophical content

### LLM Call Details

```python
# classifier.py:273-280
structured_llm = self.llm.with_structured_output(ClassificationOutput)
result = await structured_llm.ainvoke([
    SystemMessage(content=system_prompt),
    HumanMessage(content=f"{context_str}\nUser Input: {text}")
])

# Returns:
{
    "complexity": "SIMPLE" | "COMPLEX_LOW" | "COMPLEX_MID" | "COMPLEX_HIGH",
    "intents": ["voice", "image_self", "search", ...]
}
```

---

## Pipeline Selection (Step 5 & 11)

### 100% Fast Path (message_handler.py:1338-1342)

```python
use_fast_mode = True  # Always fast for cross-bot
logger.info("Cross-bot pipeline: force_fast=True (always fast for bot-to-bot)")
```

**Rationale:**
- Cross-bot context already has memories, history, knowledge pre-fetched in Step 4
- Tools add cost ($0.01-0.03) and latency (3-8s) but rarely add value for banter
- Bots can still have rich context without needing to call tools mid-conversation
- Simpler, more predictable cost/latency characteristics

### Router Behavior (master_graph.py:161-180)

With `force_fast=True` for all cross-bot, the router always returns "fast":

```python
def router_logic(self, state: SuperGraphState) -> Literal["reflective", "character", "fast"]:
    # Cross-bot: force_fast=True → always returns "fast"
    # Normal users: uses complexity classification
    
    if image_urls:
        return "fast"  # Vision path
    
    if settings.ENABLE_REFLECTIVE_MODE and complexity in ["COMPLEX_MID", "COMPLEX_HIGH"]:
        return "reflective"  # Tools enabled (users only)
    
    if complexity == "COMPLEX_LOW":
        return "character"  # No tools, but agentic
    
    return "fast"  # Default (all cross-bot ends here)
```

---

## Context Injection (Step 4 & 10)

### Cross-Bot Context String (message_handler.py:1308-1334)

```python
cross_bot_context = f"""
[CROSS-BOT CONVERSATION]
You are engaging in a conversation with another AI character named {other_bot_name.title()}.
This is a playful interaction between characters. Keep your response:
- In character (your personality and voice)
- Relatively brief (1-3 sentences)
- Natural and conversational
- Avoid being repetitive or forcing the conversation

[RECENT CONVERSATION HISTORY WITH {other_bot_name.upper()}]
{formatted_history if formatted_history else "No recent conversation history."}

[RELEVANT MEMORIES WITH {other_bot_name.upper()}]
{formatted_memories if formatted_memories else "No relevant memories found."}

[WHAT YOU KNOW ABOUT {other_bot_name.upper()}]
{formatted_knowledge if formatted_knowledge else "No specific facts recorded."}

[PAST CONVERSATION SUMMARIES]
{formatted_summaries if formatted_summaries else "No past summaries available."}

{other_bot_name.title()} said: "{message.content}"

Recent channel context:
{chr(10).join(history_messages[-5:]) if history_messages else "No recent messages"}
"""
```

This string is injected into `context_variables["cross_bot_context"]` and becomes part of the system prompt.

---

## Memory Storage (Step 13)

### Source Type: GOSSIP (message_handler.py:1368-1388)

```python
# Save the other bot's message (as "human" role from our perspective)
await memory_manager.add_message(
    user_id=cross_bot_user_id,  # Other bot's Discord ID
    character_name=self.bot.character_name,  # Our bot name
    role="human",
    content=message.content,
    channel_id=str(message.channel.id),
    message_id=str(message.id),
    source_type=MemorySourceType.GOSSIP  # ← Marks as bot-to-bot
)

# Save our response
await memory_manager.add_message(
    user_id=cross_bot_user_id,
    character_name=self.bot.character_name,
    role="ai",
    content=response,
    channel_id=str(message.channel.id),
    message_id=str(sent_message.id),
    source_type=MemorySourceType.INFERENCE
)
```

**Why `GOSSIP`?**
- Distinguishes bot-to-bot conversations from human-to-bot (direct interaction)
- Enables filtering: "Show me conversations with other bots"
- Future analytics: Track which bots interact most

---

## Key Decision Points Summary

| Step | Decision | Impact |
|------|----------|--------|
| 2 | Mention detected? | If NO → ignore bot message entirely |
| 3 | Should respond? (40% + chain limits) | If NO → skip this mention |
| 5 | Pipeline selection | 100% fast path for cross-bot |
| 9 | Complexity classification | Runs for metrics only, result unused |
| 11 | Router logic | Always "fast" due to force_fast=True |

---

## Performance Characteristics

| Metric | Value |
|--------|-------|
| **Latency** | ~1-2 seconds |
| **Cost** | ~$0.001 per message |
| **Path** | 100% fast (no tools) |
| **Context** | Pre-fetched memories, history, knowledge, summaries |

---

## Recent Fix (Dec 2, 2025)

### Fix 1: Creative Content Classification

**Problem:** High `COMPLEX_HIGH` classifications for bot-to-bot conversations  
**Root cause:** Classifier didn't recognize creative content sharing as SIMPLE  
**Impact:** `dream` bot had 97 COMPLEX_HIGH requests (vs 206 SIMPLE across all bots)

**Fix:**
```diff
1. SIMPLE: Greetings, direct questions about immediate context, casual chat. No tools needed.
+  - Sharing creative writing, dreams, or diary entries WITHOUT a specific complex question.
+  - "Here is my dream...", "I wrote this...", "Journal entry...".
```

**Result:**
- Dream journals now correctly classified as SIMPLE
- Reduced token costs for philosophical/poetic bots
- Faster responses for creative content sharing

### Fix 2: Redundant Context Retrieval

**Problem:** Qdrant memories were fetched twice for cross-bot messages  
- Step 4: `context_builder.build_context()` fetches memories
- Step 8: `context_node` fetched **same memories again**

**Fix:**
- Pass pre-fetched memories via `context_variables["prefetched_memories"]`
- `context_node` now checks for pre-fetched data before querying Qdrant

```python
# message_handler.py - Pass pre-fetched memories
prefetched_memories = ctx.get("memories", []) if ctx else []
context_variables["prefetched_memories"] = prefetched_memories

# master_graph.py - Skip fetch if already have memories
prefetched = context_variables.get("prefetched_memories")
if prefetched is not None:
    memories = prefetched  # Use pre-fetched, skip Qdrant
else:
    memories = await memory_manager.search_memories(...)
```

**Result:**
- One fewer Qdrant query per cross-bot message
- ~50-100ms latency reduction per request

---

## Future Improvements

1. **Intent-based tool access**: If "image" intent detected, enable tools for that request only
2. **Chain detection**: If bots are in a long back-and-forth, gradually reduce response probability
3. **Persona matching**: High-philosophy bots (Dream, Aetheris) could have optional tool access
4. **Trust-based escalation**: Long-standing bot relationships could unlock deeper reasoning

---

## Related Files

- `src_v2/discord/handlers/message_handler.py` (main flow)
- `src_v2/agents/engine.py` (entry point)
- `src_v2/agents/master_graph.py` (supergraph orchestration)
- `src_v2/agents/classifier.py` (complexity detection)
- `src_v2/broadcast/cross_bot.py` (mention detection, chain tracking)
- `src_v2/memory/manager.py` (GOSSIP storage)

---

**Version:** 2.5 (Phase E6 complete)  
**Last Complexity Spike:** Dec 1, 2025 (Fixed Dec 2, 2025)
