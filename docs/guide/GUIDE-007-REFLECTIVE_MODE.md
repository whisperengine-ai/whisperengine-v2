# Reflective Mode: Controls & UX

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Dual-process architecture |
| **Proposed by** | Mark (cognitive architecture) |
| **Catalyst** | Complex queries needed deeper reasoning |

---

This document outlines the user-facing controls and user experience features for **Reflective Mode** (System 2 Reasoning).

**For architecture details**, see [Cognitive Engine Architecture](../architecture/COGNITIVE_ENGINE.md#6-reflective-agent) which explains the three-tier system: Fast Mode → Character Agency → Reflective Mode.

## 1. Streaming Reasoning (Streaming ReAct)

When Reflective Mode is triggered (either automatically by the complexity classifier or manually via `!reflect`), the bot provides real-time visibility into its reasoning process.

### User Experience
Instead of a "typing..." indicator for 10-30 seconds, the user sees a dynamic status message that updates in real-time as the bot thinks.

**Status Message Format:**
```markdown
🧠 **Reflective Mode**

> 💭 Need to check user's past conversations about "stress".
> 🛠️ *Using search_memories...*
> ✅ *search_memories*: Found 5 recent messages mentioning deadlines.
> 💭 I see a pattern. Checking for physiological symptoms.
...
```

### Technical Behavior
1.  **Real-time Updates**: The bot edits the status message as each step (Thought/Action/Observation) occurs.
2.  **Truncation**: To prevent hitting Discord's message limit (2000 chars), the log is truncated if it gets too long, preserving the header.
3.  **Final Output**: Once reasoning is complete, the status message remains (showing the work), and the final answer is sent as a new, separate message.

---

## 2. User Control (`!reflect`)

Users can bypass the automatic complexity classifier and force the bot to use Reflective Mode for any query.

### Usage
Prefix any message with `!reflect`.

**Syntax:**
```
!reflect <your question>
```

**Examples:**
*   `!reflect Why is the sky blue?` (Forces deep reasoning on a simple fact)
*   `!reflect What should I eat?` (Forces deep analysis of preferences/history for a simple decision)

### Behavior
1.  **Bypass Classifier**: The system skips the GPT-4o-mini classification step (saving cost/latency).
2.  **Force Complex**: The query is treated as `COMPLEX` regardless of content.
3.  **Memory Safety**: The `!reflect` prefix is stripped before saving to vector memory, ensuring the command itself doesn't pollute the semantic search index.

### Edge Cases
*   **Empty Command**: Typing just `!reflect` without a message (and without replying to one) triggers a usage hint.
*   **Replies**: You can reply to a previous message with `!reflect` to force reasoning on that specific context.
*   **Disabled Mode**: If `ENABLE_REFLECTIVE_MODE=false` in settings, the command returns a warning message.
