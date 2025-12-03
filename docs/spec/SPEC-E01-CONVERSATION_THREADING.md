# Conversation Threading

**Document Version:** 1.0
**Created:** November 27, 2025
**Status:** 📋 Proposed
**Priority:** High
**Complexity:** 🟢 Low
**Estimated Time:** 2 days

---

## Executive Summary

Currently, WhisperEngine treats every message as a standalone input (plus recent history). However, Discord users often use the "Reply" feature to respond to specific past messages. The bot currently ignores this metadata, leading to context loss if the user replies to an older message or if the chat is moving fast.

This feature adds **explicit thread awareness** by fetching the referenced message content and injecting it into the context window.

---

## 👤 User Experience

**Current Behavior:**
```
User: (Replies to a message from 5 mins ago about pizza) "I actually prefer pineapple on it"
Bot: "Prefer pineapple on what?" (Context lost)
```

**New Behavior:**
```
User: (Replies to a message from 5 mins ago about pizza) "I actually prefer pineapple on it"
Bot: "Bold choice! Pineapple on pizza is controversial, but I respect the sweet and savory mix."
```

---

## 🔧 Technical Design

### 1. Discord Event Handling

In `src_v2/discord/bot.py`, update `on_message`:

```python
async def on_message(self, message):
    # ... existing checks ...

    reply_context = None
    if message.reference and message.reference.message_id:
        try:
            # Fetch the message being replied to
            ref_msg = await message.channel.fetch_message(message.reference.message_id)
            reply_context = {
                "author": ref_msg.author.name,
                "content": ref_msg.content,
                "id": ref_msg.id
            }
        except discord.NotFound:
            pass # Message deleted
```

### 2. Context Injection

Pass `reply_context` to `agent_engine.generate_response`.

In `src_v2/agents/engine.py`:
- If `reply_context` exists, format it explicitly in the prompt.
- "User is replying to [Author]: '[Content]'"

### 3. Session Storage

Update `src_v2/memory/session.py` to store thread links if needed, though purely prompt-based injection is likely sufficient for V1.

---

## 📋 Implementation Plan

1.  **Update Bot Logic**: Modify `on_message` to fetch references.
2.  **Update Engine Interface**: Add `reply_context` parameter to `generate_response`.
3.  **Prompt Engineering**: Update system prompt to understand reply context.
4.  **Testing**: Verify bot understands replies to old messages.

## ⚠️ Risks & Mitigations

-   **Latency**: Fetching the referenced message adds an API call (~50-100ms).
    -   *Mitigation*: Fire-and-forget or parallelize if possible, but usually fast enough.
-   **Deleted Messages**: Handle `discord.NotFound` gracefully.
