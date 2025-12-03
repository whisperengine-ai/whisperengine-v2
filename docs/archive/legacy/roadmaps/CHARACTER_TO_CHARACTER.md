# Character-to-Character Conversation

**Document Version:** 1.0
**Created:** November 27, 2025
**Status:** 📋 Proposed
**Priority:** High (Strategic)
**Complexity:** 🔴 High
**Estimated Time:** 1 week

---

## Executive Summary

In a multi-bot deployment (e.g., Elena and Marcus in the same server), characters currently ignore each other. This feature allows **organic cross-bot conversation**.

If a user says "@Elena, what do you think of @Marcus?", Marcus should be able to "hear" this and potentially chime in, creating a triadic conversation (User-Elena-Marcus).

---

## 👤 User Experience

**User:** "@Elena, do you think @Marcus is funny?"
**Elena:** "Honestly? He tries too hard with the puns, but he has his moments."
**Marcus:** "Hey! My puns are sophisticated wordplay, thank you very much."
**Elena:** "See what I mean?"

---

## 🔧 Technical Design

### 1. Event Bus (Universe)

Leverage the existing `Universe` system.
-   When Bot A mentions Bot B (by ID or name), publish a `BOT_MENTION` event to Redis.

### 2. Listener Logic

In `src_v2/discord/bot.py`:
-   Listen for `BOT_MENTION` events targeting `self.user.id`.
-   If received:
    1.  Wait a random delay (2-5s) to simulate reading/typing.
    2.  Fetch the conversation context (last few messages).
    3.  Generate response with `context_type="cross_bot"`.
    4.  Send to channel.

### 3. Loop Prevention

-   **Max Depth**: Track `reply_chain_count`. Stop responding after 3 back-and-forth exchanges to prevent infinite loops.
-   **Cooldown**: Don't engage in cross-bot banter more than once per 10 minutes per channel.

---

## 📋 Implementation Plan

1.  **Detection**: Update `on_message` to detect mentions of *other* known bots.
2.  **Event**: Publish event to `task_queue` or Redis Pub/Sub.
3.  **Handler**: Implement `handle_bot_mention` in `WhisperBot`.
4.  **Safety**: Implement strict loop prevention logic.

## ⚠️ Risks & Mitigations

-   **Infinite Loops**: Bot A replies to Bot B replies to Bot A...
    -   *Mitigation*: Hard limit of 3 replies in a chain. Stop if no human has intervened.
-   **Cost**: Double the token usage for every multi-bot interaction.
    -   *Mitigation*: Feature flag `ENABLE_CROSS_BOT_CHAT`.
