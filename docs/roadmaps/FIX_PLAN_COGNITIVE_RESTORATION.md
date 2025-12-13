# FIX PLAN: Cognitive Restoration (Post v2.5.1 Regression)

**Date:** December 13, 2025  
**Origin:** Architecture review of changes since commit `35923da1e725cff2b5b9df2271f336886a3fb2d1`  
**Problem:** System feels "flat", "dumber". Daily diary quality dropped. Bot-to-bot conversation quality dropped.

---

## Executive Summary

The recent v2.5.1 changes implemented **Unified Memory** (good) but introduced aggressive gating mechanisms and simplified the cognitive loop for autonomous behavior, effectively "lobotomizing" the bots' creative and emergent capabilities.

**Root Causes:**
1. **Social Battery** drains too fast (`0.15` per post), blocking proactive behavior after ~3 posts
2. **Rich Context Retrieval** was removed from proactive posts (Stigmergy, Diary, Knowledge, Dreams)
3. **Fatigue Exemption** was removed for bot conversation channels
4. **Tool Gating** prevents SIMPLE complexity queries from using tools (image gen, search)
5. **Diary Weighting** treats bot's own output as equally important as external interactions

---

## Fix #1: Social Battery Drain Rate (CRITICAL)

### Problem
Social Battery drains `0.15` per proactive post and `0.05` per reply. At 100% battery:
- After 3 proactive posts: Battery = `0.55` (near 0.5 threshold)
- After 6 posts: Battery = `0.10` (all autonomy disabled)

**Result:** Bots become "socially exhausted" too quickly and stop initiating.

### Solution
Reduce drain rates and add passive recharge:

**File:** `src_v2/agents/daily_life/graph.py`

```python
# OLD (aggressive):
drain = (proactive_count * 0.15) + (reactive_count * 0.05)

# NEW (balanced):
drain = (proactive_count * 0.05) + (reactive_count * 0.02)
```

**File:** `src_v2/evolution/drives.py`

Add passive battery recharge (call from Daily Life Graph at end of cycle):
```python
async def recharge_social_battery(self, character_name: str, amount: float = 0.03):
    """Passive recharge every cycle (7 min). Full recharge in ~4 hours of quiet."""
    await self.update_social_battery(character_name, amount)
```

### Settings to Add
```python
# In settings.py
SOCIAL_BATTERY_DRAIN_PROACTIVE: float = 0.05  # Per proactive post
SOCIAL_BATTERY_DRAIN_REACTIVE: float = 0.02   # Per reply/react
SOCIAL_BATTERY_PASSIVE_RECHARGE: float = 0.03 # Per idle cycle (~7 min)
```

---

## Fix #2: Restore Rich Context for Proactive Posts (CRITICAL)

### Problem
The old proactive post logic explicitly fetched:
1. **Knowledge Graph**: "What do I know about {topic}?"
2. **Broadcast Memories**: Past public posts about topic
3. **Diary Context**: Current mood/theme
4. **Stigmergy**: What other bots are dreaming/thinking about

The new code just sends `"I am thinking about {topic}"` to MasterGraphAgent without this pre-fetched context. The bot has "thoughts" but no "memory" backing them up.

### Solution
Restore the rich context injection before calling MasterGraphAgent for proactive posts.

**File:** `src_v2/agents/daily_life/graph.py`

In `execute_actions_node`, for `plan.intent == "post"`:

```python
# RESTORE: Rich Context Fetching for Proactive Posts
from src_v2.agents.context_builder import ContextBuilder

cb = ContextBuilder()
context_tasks = [
    knowledge_manager.query_graph(
        user_id="daily_life_proactive", 
        question=f"What do I know or feel about {topic}?"
    ),
    memory_manager.search_memories(
        query=topic, 
        user_id="__broadcast__", 
        limit=3,
        collection_name=f"whisperengine_memory_{snapshot.bot_name}"
    ),
    cb.get_diary_context(snapshot.bot_name),
    cb.get_stigmergy_context(
        user_message=topic,
        user_id="daily_life_proactive",
        character_name=snapshot.bot_name
    )
]

results = await asyncio.gather(*context_tasks, return_exceptions=True)

# Build rich_context string from results...
rich_context = self._format_proactive_context(results, topic)

# THEN call MasterGraphAgent with this context injected
response = await master_graph_agent.run(
    user_input=internal_stimulus,
    user_id="internal_monologue",
    character=character,
    chat_history=chat_history,
    context_variables={
        "user_name": "Internal Monologue",
        "channel_name": plan.channel_id,
        "additional_context": f"[GROUNDING]\n{rich_context}\n\n[GOAL] Express your thought about {topic} naturally."
    },
    image_urls=None
)
```

---

## Fix #3: Restore Fatigue Exemption for Bot Channels (HIGH)

### Problem
The `social_battery_limit` (default 5 msgs/15 min) now applies globally. Bot conversation channels used to be exempt. Now bots exchange 5 messages and hard-stop.

### Solution
Use `watch_channels` as the signal for "high engagement" channels where fatigue limits are relaxed.

**File:** `src_v2/agents/daily_life/graph.py`

In `plan_actions_node`, modify the fatigue check:

```python
# Get watch channels for exemption
watch_channels = getattr(snapshot, "watch_channels", []) or []

filtered_scored = []
for sm in scored:
    channel_id = sm.message.channel_id
    is_watch_channel = channel_id in watch_channels
    
    if not is_watch_channel:
        # Standard fatigue check for regular channels
        recent_count = await memory_manager.get_recent_activity_count(...)
        if recent_count >= social_limit:
            continue
    else:
        # Relaxed limit for watch channels (allow deeper conversations)
        recent_count = await memory_manager.get_recent_activity_count(...)
        if recent_count >= social_limit * 3:  # 15 instead of 5
            continue
    
    filtered_scored.append(sm)
```

---

## Fix #4: Tool Availability for Proactive Posts (MEDIUM)

### Problem
`MasterGraphAgent.build_prompt_node` determines `tools_available` based on complexity classification. Proactive posts like "I am thinking about life" get classified as SIMPLE → no tools → bot can't generate images or search.

### Solution
Option A (Recommended): Force `COMPLEX_LOW` for internal monologue user_ids
Option B: Add `tools_available` override in `context_variables`

**File:** `src_v2/agents/master_graph.py`

```python
# In build_prompt_node, add override for internal monologue
user_id = state.get("user_id")
if user_id == "internal_monologue":
    # Proactive posts should have full tool access
    tools_available = True
```

---

## Fix #5: Diary Material Weighting (LOW-MEDIUM)

### Problem
Autonomous actions (the bot's own posts) are scored at 3 points each, same as conversation summaries. This inflates diary content with the bot's own output rather than external interactions.

### Solution
Reduce autonomous action weight:

**File:** `src_v2/memory/diary.py`

```python
# OLD:
return (
    len(self.summaries) * 3 +
    len(self.autonomous_actions) * 3 +  # Bot's own activity is equally important
    ...
)

# NEW:
return (
    len(self.summaries) * 3 +
    len(self.autonomous_actions) * 1 +  # Reduced: Own output is less important than interactions
    ...
)
```

Also cap autonomous actions in diary content:

```python
# In format_for_llm(), limit autonomous actions displayed
for action in self.autonomous_actions[:5]:  # Was [:10]
```

---

## Fix #6: "Absence" Detection Robustness (LOW)

### Problem
The absence detection changed from metadata-filtered search to semantic search on "absence of diary material". This is fuzzy and may fail.

### Solution
Restore metadata filter OR use a more specific semantic query:

**File:** `src_v2/workers/tasks/diary_tasks.py`

```python
# Option A: Use a cleaner semantic query
recent_absences = await memory_manager.search_memories(
    user_id=character_name,
    query="diary generation absence no material quiet day",  # More specific
    limit=1,
    collection_name=target_collection
)

# Option B: Add a dedicated method for absence lookup
# This would require a memory_manager method that filters by type="absence"
```

---

## Implementation Order

| Priority | Fix | Effort | Impact |
|----------|-----|--------|--------|
| 🔴 P0 | #2 Rich Context Restoration | ~2 hrs | HIGH - Restores "depth" to posts |
| 🔴 P0 | #1 Social Battery Tuning | ~30 min | HIGH - Restores proactive behavior |
| 🟠 P1 | #3 Fatigue Exemption | ~30 min | HIGH - Restores bot conversations |
| 🟡 P2 | #4 Tool Availability | ~15 min | MEDIUM - Allows image gen in posts |
| 🟢 P3 | #5 Diary Weighting | ~15 min | LOW - Improves diary quality |
| 🟢 P3 | #6 Absence Detection | ~30 min | LOW - Edge case fix |

**Total Estimated Time:** ~4 hours

---

## Validation Checklist

After implementing fixes, validate:

1. [ ] **Social Battery**: Watch for 2+ hours. Bot should remain active (battery > 0.5)
2. [ ] **Proactive Posts**: Posts should reference memories, diary, or stigmergy context
3. [ ] **Bot Conversations**: Two bots in watch channel should sustain 10+ message exchanges
4. [ ] **Image Generation**: Proactive post about art should trigger image tool
5. [ ] **Diary Quality**: Diary should prioritize user interactions over bot's own posts
6. [ ] **Dream State**: After 2 days of silence, absence streak should increment

---

## Philosophy Alignment Check

| Principle | Status After Fix |
|-----------|-----------------|
| Emergent Behavior | ✅ Social Battery allows natural rhythm, not artificial caps |
| Rich Interiority | ✅ Stigmergy/Diary/Knowledge injected into proactive thoughts |
| Bot Autonomy | ✅ Watch channels allow deep engagement |
| Unified Memory | ✅ Already implemented, preserved |
| Minimal Schema | ✅ No new fields, just tuned behavior |

---

## Rollback Plan

If fixes cause issues, revert to commit `35923da1e725cff2b5b9df2271f336886a3fb2d1` and apply Unified Memory changes selectively.

```bash
git checkout 35923da1e725cff2b5b9df2271f336886a3fb2d1 -- src_v2/agents/daily_life/graph.py
```
