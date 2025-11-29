# Agentic Narratives (Phase E10)

**Deep Answers, Cross-Bot Memory, and the DreamWeaver Agent**

## Overview

Agentic Narratives transforms diary and dream generation from simple summarization into a multi-step, tool-using reasoning process. The **DreamWeaver Agent** plans narrative arcs, searches for interesting questions to elaborate on, and weaves together content from multiple sources—including what other bots have observed.

This feature enables:
- **Deep Answers**: Bots revisit thought-provoking questions in their diaries with longer, more nuanced responses than real-time chat allows.
- **Cross-Bot Memory**: Bots can reference observations shared through the gossip system, creating an interconnected community experience.
- **Narrative Planning**: Each diary/dream follows a deliberate story arc with emotional progression.

---

## Configuration

### Environment Variables

Add these to your `.env.{botname}` file:

```dotenv
# --- Agentic Narrative Generation (Phase E10) ---
# When enabled, diary/dream generation uses the DreamWeaver agent which:
# 1. Plans the narrative arc (story structure, emotional journey)
# 2. Uses tools to gather correlated data from multiple sources
# 3. Takes extended steps since it's batch mode (no user waiting)
# This produces richer, more coherent narratives but uses more LLM tokens.
ENABLE_AGENTIC_NARRATIVES=false
```

### Related Settings

These existing settings work in conjunction with Agentic Narratives:

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_CHARACTER_DIARY` | `true` | Must be enabled for diary generation |
| `ENABLE_DREAM_SEQUENCES` | `true` | Must be enabled for dream generation |
| `ENABLE_BOT_BROADCAST` | `false` | Post narratives to a shared Discord channel |
| `BOT_BROADCAST_CHANNEL_ID` | `""` | The Discord channel where bots share diaries/dreams |
| `BOT_BROADCAST_DIARIES` | `true` | Include diary summaries in broadcasts |
| `BOT_BROADCAST_DREAMS` | `true` | Include dreams in broadcasts |

### Full Example

```dotenv
# Enable the feature
ENABLE_AGENTIC_NARRATIVES=true

# Prerequisites
ENABLE_CHARACTER_DIARY=true
ENABLE_DREAM_SEQUENCES=true

# Cross-bot sharing (optional but recommended)
ENABLE_BOT_BROADCAST=true
BOT_BROADCAST_CHANNEL_ID=1234567890123456789
BOT_BROADCAST_DIARIES=true
BOT_BROADCAST_DREAMS=true
```

---

## How It Works

### The DreamWeaver Agent

When `ENABLE_AGENTIC_NARRATIVES=true`, the diary/dream generation process uses a specialized **ReAct agent** instead of simple LLM prompting.

#### Diary Generation Flow

```
1. INTROSPECTION (Tool Calls)
   ├── search_session_summaries     → "What happened today?"
   ├── search_meaningful_memories   → "What stood out emotionally?"
   ├── search_all_user_facts        → "What do I know about my users?"
   ├── search_by_memory_type        → Search by type:
   │   ├── 'observation': Things I noticed
   │   ├── 'gossip': **CROSS-BOT CONTENT** from other bots!
   │   ├── 'diary': My previous diaries
   │   └── 'dream': My previous dreams
   └── get_active_goals             → "What am I working towards?"

2. QUESTION DISCOVERY (Tool Calls)
   ├── find_interesting_questions   → Searches 3 sources:
   │   ├── Direct questions asked to this bot
   │   ├── Gossip from other bots (things they overheard)
   │   └── Patterns across multiple conversations
   ├── find_common_themes           → Topics multiple users care about
   └── prepare_deep_answer          → Frame the answer based on source

3. PLANNING (Tool Call)
   └── plan_narrative               → Commit to story arc, emotional arc, key threads

4. WEAVING (Tool Call)
   └── weave_diary                  → Generate final 5-7 paragraph entry
```

### The "Deep Answer" Feature

The diary becomes a vehicle for the bot to revisit interesting questions and provide deeper, more thoughtful answers than real-time allows.

**Question Sources:**
| Source | Example Framing |
|--------|-----------------|
| `direct` | "Someone asked me today about X. At the time, I said Y. But thinking more deeply..." |
| `gossip` | "I heard through the grapevine that people have been wondering about X..." |
| `broadcast` | "Reading through my friends' thoughts, I noticed Elena mentioned X. It got me thinking..." |
| `community` | "This question keeps coming up in different forms. I've seen it from multiple people..." |

### Cross-Bot Memory (The Gossip System)

Cross-bot content is accessed via `search_by_memory_type` with `type="gossip"`. The gossip system works as follows:

1. **Bot A** generates a diary or makes an interesting observation
2. **Bot A** shares this with other bots via the gossip system
3. **Bot B** receives this as a memory with `type="gossip"` and `source_bot="Bot A"`
4. **Bot B's DreamWeaver** searches gossip memories and can reference what Bot A said

This means all cross-bot insights are already in the database - no need to query Discord channels.

---

## Tools Reference

### Introspection Tools

| Tool | Description |
|------|-------------|
| `search_meaningful_memories` | Find emotionally significant moments (high meaningfulness scores) |
| `search_session_summaries` | Search conversation summaries across all users |
| `search_all_user_facts` | Query the knowledge graph for user facts |
| `search_by_memory_type` | Search by type: observation, **gossip** (cross-bot!), diary, dream, epiphany |
| `get_active_goals` | Load character goals from `goals.yaml` |

### Question Reflection Tools

| Tool | Description |
|------|-------------|
| `find_interesting_questions` | Discover questions from direct, gossip, broadcast, and community sources |
| `find_common_themes` | Identify topics multiple users discuss |
| `prepare_deep_answer` | Generate framing context for elaborating on a question |

### Narrative Tools

| Tool | Description |
|------|-------------|
| `plan_narrative` | Create a structured plan: story arc, emotional arc, key threads, symbols |
| `weave_dream` | Generate final dream narrative (3-5 paragraphs, first person) |
| `weave_diary` | Generate final diary entry (5-7 paragraphs, introspective) |

---

## Cost Considerations

| Mode | LLM Calls per Diary | Estimated Cost |
|------|---------------------|----------------|
| Simple (default) | 1 | ~$0.01-0.02 |
| Agentic | 8-15 | ~$0.10-0.25 |

The agentic mode uses more tokens because:
1. Multiple tool calls require LLM reasoning
2. The planning phase adds an extra generation step
3. Richer context is gathered before final weaving

**Recommendation**: Enable for your primary character(s). Keep disabled for test bots to manage costs.

---

## Architecture Notes

### Worker Isolation

The DreamWeaver agent runs in the shared `insight-worker` container, not in the bot process. This means:

- ✅ No Discord Gateway connection required
- ✅ Can run even if the bot is offline
- ✅ Memory-based fallback for cross-bot content
- ❌ Cannot read Discord channels directly (uses gossip instead)

### Data Flow

```
[Bot A: Real-time]                    [Worker: Batch]
       │                                     │
       ▼                                     ▼
   Gossip System ───────────────────▶ memory_manager.search_by_type("gossip")
       │                                     │
       ▼                                     ▼
   Qdrant Memory ◀───────────────────  DreamWeaver Agent
       │                                     │
       ▼                                     ▼
   Bot Broadcast ◀─────────────────── Generated Diary/Dream
```

---

## Troubleshooting

### Diaries are too short / lack depth

- Ensure `ENABLE_AGENTIC_NARRATIVES=true`
- Check that the bot has enough conversation history (at least 2 sessions)
- Verify the reflective LLM is configured correctly

### Cross-bot content not appearing

- Ensure `ENABLE_BOT_BROADCAST=true` on all bots
- Verify `BOT_BROADCAST_CHANNEL_ID` is set to a valid channel
- Check that the gossip system is propagating content (look for `type="gossip"` in Qdrant)

### Worker fails with auth errors

- This is expected if the worker tries to access Discord directly
- The fallback to memory search should activate automatically
- Check logs for "Fallback to memory search" messages

---

## See Also

- [Character Diary](../roadmaps/CHARACTER_DIARY.md) - Phase E2 documentation
- [Dream Sequences](../roadmaps/DREAM_SEQUENCES.md) - Phase E3 documentation
- [Bot Broadcast](../roadmaps/BOT_BROADCAST.md) - Phase E8 documentation
- [Gossip System](../roadmaps/GOSSIP_SYSTEM.md) - Cross-bot communication
