# Character Diary & Reflection

**Document Version:** 1.0
**Created:** November 27, 2025
**Status:** ✅ Implemented
**Priority:** Medium
**Complexity:** 🟡 Medium
**Estimated Time:** 3-4 days

---

## Executive Summary

Characters currently feel "frozen" when not talking to users. To give them an inner life, we will implement a **Daily Diary System**.

Every night (or after significant sessions), the Insight Worker will generate a "diary entry" for the character. This entry synthesizes the day's interactions, emotional state, and thoughts about specific users. These entries are stored in memory and can be referenced later.

---

## 👤 User Experience

**Implicit:**
- Character references past days more holistically: *"I was thinking about what you said yesterday regarding the stars..."*
- Character mood shifts based on the "day's summary" rather than just the last message.

**Explicit (Optional):**
- Character posts a "Daily Reflection" to a specific channel (e.g., `#elena-thoughts`).
- User can ask: *"How was your day?"* and get a genuine answer based on the diary.

---

## 🔧 Technical Design

### 1. Insight Worker Task

New task in `src_v2/workers/insight_worker.py`: `generate_daily_diary`.

**Trigger:**
- Scheduled nightly (e.g., 4 AM UTC).
- Only runs if character was active in the last 24h.

**Logic:**
1.  Fetch all session summaries from the last 24h.
2.  Fetch current mood/trust states of key users.
3.  LLM Call: "Write a private diary entry as [Character]. Reflect on these interactions..."
4.  Store result as a new memory type: `diary_entry`.

### 2. Memory Storage

-   **Collection**: `whisperengine_memory_{bot_name}`
-   **Metadata**: `type: "diary"`, `date: "2025-11-27"`, `visibility: "private"`

### 3. Retrieval

Update `memory_manager.get_recent` or `context_builder` to optionally fetch the *last diary entry* to prime the character's state for the new day.

---

## 📋 Implementation Plan

1.  **Worker Task**: Create `generate_daily_diary` in `insight_worker.py`.
2.  **Prompt**: Design "Diary Writer" prompt (introspective, emotional).
3.  **Storage**: Define `diary_entry` memory schema.
4.  **Integration**: Inject last diary entry into `Character` context on first message of the day.

## ⚠️ Risks & Mitigations

-   **Cost**: One complex LLM call per active character per day.
    -   *Mitigation*: Only run if >5 messages exchanged that day.
-   **Privacy**: Ensure diary doesn't leak private DM info if posted publicly.
    -   *Mitigation*: Strict prompt instructions: "Do not reveal specific user secrets."

---

## 🔄 Agentic Enhancements (Phase E10)

**Status**: ✅ Implemented

When `ENABLE_AGENTIC_NARRATIVES=true`, diary entries use the DreamWeaver agent instead of simple LLM generation:

### Dream↔Diary Feedback Loop
- Diaries search previous **dreams** first and can recognize connections ("I dreamed about this...")
- Dreams search previous **diary entries** for waking insights to process
- This creates emergent thematic continuity across narratives

### Deep Answers
Diaries can elaborate on interesting questions with longer, more nuanced responses:
- Direct questions asked to the bot
- Questions heard through gossip from other bots
- Community themes appearing across multiple conversations

### Emotional Variety
Diaries support the full emotional range with mood-aware headers:

| Mood | Header | Example Opener |
|------|--------|----------------|
| frustrated, anxious | 🌧️ **A Difficult Day** | "Today was hard." |
| joyful, euphoric | ☀️ **A Wonderful Day** | "What a day!" |
| reflective, peaceful | 📝 **Diary Entry** | (no special opener) |

### Voice Note
Unlike dreams, diaries intentionally skip voice synthesis. Dreams get the full character performance layer, but diaries are "mask off" — the AI reflecting genuinely without the performance layer. This creates meaningful contrast and feels more intimate.

See: [`AGENTIC_NARRATIVES.md`](../../features/AGENTIC_NARRATIVES.md) for full details.

---

## 📚 Related Documents

- [`AGENTIC_NARRATIVES.md`](../../features/AGENTIC_NARRATIVES.md) - DreamWeaver agent details
- [`DREAM_SEQUENCES.md`](./DREAM_SEQUENCES.md) - Dream generation system
- [`BOT_BROADCAST_CHANNEL.md`](./BOT_BROADCAST_CHANNEL.md) - Public sharing of diaries