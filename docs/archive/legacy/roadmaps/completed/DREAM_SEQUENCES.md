# Dream Sequences

**Document Version:** 1.0
**Created:** November 27, 2025
**Status:** ✅ Implemented
**Priority:** Medium
**Complexity:** 🟡 Medium
**Estimated Time:** 3 days

---

## Executive Summary

To make the characters feel like they exist in a continuous world, they will "dream" during long periods of inactivity. When a user reconnects after a significant break (e.g., >24 hours), the character may spontaneously share a dream that metaphorically relates to their relationship or past conversations.

---

## 👤 User Experience

**Scenario:**
User hasn't spoken to Elena in 2 days.
**User:** "Hey Elena, I'm back."
**Elena:** "Mark! You won't believe it—I had the strangest dream last night. We were swimming with those whale sharks we talked about, but the water was made of starlight. It felt so real. How have you been?"

---

## 🔧 Technical Design

### 1. Dream Generation (On-Demand)

✅ **Implemented** - Dreams are generated **on-demand** when a user returns after a long absence.

**Trigger:**
- Context builder detects `last_interaction > 24 hours`
- Cooldown check ensures dreams don't spam (7-day minimum between dreams per user)

**Generation Flow:**
1.  Retrieve high-meaningfulness memories from the user's history (top 5 summaries)
2.  LLM structured output: Generates surreal dream with mood, symbols, and memory echoes
3.  Content safety review before saving
4.  Inject "Dream Content" into system context with instruction: "Mention this dream you had"

### 2. State Tracking

✅ **Implemented** - Dreams are stored in Qdrant with cooldown tracking:
-   Collection: `whisperengine_memory_{bot_name}`
-   Type: `"dream"`
-   Metadata: `user_id`, `mood`, `symbols`, `memory_echoes`, `provenance`, `timestamp`

---

## 📋 Implementation Status

✅ **Completed**:
1.  **Logic Hook**: Implemented in `context_builder._get_dream_context()` - checks last interaction time
2.  **Dream Generation**: `DreamManager.generate_dream()` creates personalized dreams from memories
3.  **Cooldown System**: `should_generate_dream()` enforces `DREAM_INACTIVITY_HOURS` (24h) and `DREAM_COOLDOWN_DAYS` (7d)
4.  **Context Injection**: Dream is formatted and injected into system prompt for natural mention
5.  **Storage**: Dreams saved to Qdrant with full provenance tracking
6.  **Broadcast Integration**: Dreams can optionally be posted to `#bot-thoughts` channel

**Settings**:
- `ENABLE_DREAM_SEQUENCES=true` (default)
- `DREAM_INACTIVITY_HOURS=24` (hours before triggering)
- `DREAM_COOLDOWN_DAYS=7` (minimum days between dreams per user)

## ⚠️ Notes

-   **Surrealism Balance**: Dreams use structured LLM output with mood/symbols to avoid being too weird
-   **Repetition Prevention**: 7-day cooldown + high meaningfulness memory filtering ensures variety
-   **Privacy**: Dreams based on user-specific memories are only shared in DMs or with that user's consent
-   **Broadcast Option**: Can be posted to `#bot-thoughts` if `ENABLE_BOT_BROADCAST=true` (with provenance footer)

---

## 🔄 Agentic Enhancements (Phase E10)

**Status**: ✅ Implemented

When `ENABLE_AGENTIC_NARRATIVES=true`, dreams use the DreamWeaver agent instead of simple LLM generation:

### Dream↔Diary Feedback Loop
- Dreams search previous **diary entries** for waking insights to process as dream symbolism
- Diaries search previous **dreams** and can recognize connections ("I dreamed about this...")
- This creates emergent thematic continuity across narratives

### Emotional Variety
Dreams support the full emotional range with mood-aware headers and openers:

| Mood | Header | Example Opener |
|------|--------|----------------|
| nightmare | 🌑 **Nightmare** | "I woke up shaking from a terrible dream..." |
| ecstatic | ✨ **A Beautiful Dream** | "I had the most incredible dream!" |
| peaceful | 🌙 **Dream Journal** | "I had the most peaceful dream..." |
| bittersweet | 🌙 **Dream Journal** | "There was a dream last night that I can't quite shake..." |

### Character Background as Lens
Dreams always start by loading the character's background (fears, values, quirks) which colors how all experiences are interpreted in the dream.

See: [`AGENTIC_NARRATIVES.md`](../../features/AGENTIC_NARRATIVES.md) for full details.

---

## 🌡️ Dynamic Dream Temperature (Future Enhancement)

**Status**: 🔮 Planned for Phase E10

Dream creativity could adapt to server energy observed via Channel Observer.

| Server Energy | Temperature | Dream Style |
|---------------|-------------|-------------|
| Quiet day | 0.5-0.65 | Gentle, coherent, reflective |
| Normal day | 0.65-0.85 | Balanced, narrative dreams |
| Lively day | 0.85-1.0 | Vivid, creative, surprising |
| Buzzing day | 1.0-1.1 | Wild, surreal, unexpected |

**Rationale:** A bot that "witnessed" an exciting, high-energy day should dream more vividly. A quiet, contemplative day produces gentler, more coherent dreams.

See: [`CHANNEL_OBSERVER.md`](./CHANNEL_OBSERVER.md) for energy calculation details.

---

## 📚 Related Documents

- `CHANNEL_OBSERVER.md` - Provides server energy for dynamic temperature
- `ARTIFACT_PROVENANCE.md` - Dreams include grounding sources
- `BOT_BROADCAST_CHANNEL.md` - Dreams may be shared publicly
    -   *Mitigation*: 7-day cooldown per user.
