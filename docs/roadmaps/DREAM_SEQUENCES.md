# Dream Sequences

**Document Version:** 1.0
**Created:** November 27, 2025
**Status:** 📋 Proposed
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

### 1. Dream Generation (Lazy Load)

Instead of a background worker (to save cost), we generate the dream **on-demand** but *pretend* it happened earlier.

**Trigger:**
- `on_message` detects `last_interaction > 24 hours`.
- Check `dream_cooldown` (don't dream every time).

**Generation:**
1.  Retrieve high-meaningfulness memories from the user's history.
2.  LLM Call: "Generate a surreal dream sequence involving [User] based on these memories: [Memories]. Keep it abstract and emotional."
3.  Inject this "Dream Content" into the context for the *current* response generation.
4.  Instruction: "Mention the dream you just had."

### 2. State Tracking

-   Store `last_dream_timestamp` in Redis/Postgres to prevent spamming dreams.

---

## 📋 Implementation Plan

1.  **Logic Hook**: Add check in `AgentEngine` or `ProactiveScheduler` for "Long Absence".
2.  **Dream Tool**: Create internal helper `generate_dream(user_id, memories)`.
3.  **Prompting**: Update system prompt to allow "sharing dreams" naturally.
4.  **Testing**: Verify dreams aren't repetitive or weirdly specific.

## ⚠️ Risks & Mitigations

-   **Hallucination**: Dreams might be too weird.
    -   *Mitigation*: Dynamic temperature based on server energy (see below).
-   **Repetition**: "I had a dream..." every time.

---

## 🌡️ Dynamic Dream Temperature

**Enhancement (Phase E10):** Dream creativity adapts to server energy observed via Channel Observer.

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
