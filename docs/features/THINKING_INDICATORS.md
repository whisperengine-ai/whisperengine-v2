# Understanding Thinking Indicators

When you chat with the bot, you might sometimes see status messages appear before the response. These show you what's happening behind the scenes!

## What Do They Mean?

### 🧠 **Deep Thinking**

You'll see this when you ask something complex—like questions about your past conversations, philosophical topics, or requests that need the bot to search through memories and piece things together.

```
🧠 **Deep Thinking**

> 💭 Let me think about what we discussed before...
> 🛠️ *Using search_memories...*
> ✅ *search_memories*: Found 3 relevant conversations
> 💭 I see a pattern here...
```

**What's happening:** The bot is going through multiple steps of reasoning, searching memories, and connecting dots. This might take 5-30 seconds depending on complexity.

---

### 💭 **Looking something up...**

You'll see this for simpler lookups—when the bot just needs to quickly check something before responding.

```
💭 **Looking something up...**

> 🔍 *Checking my memory...*
> 🛠️ *Using lookup_facts...*
```

**What's happening:** A quick one-step lookup. Usually takes just a few seconds.

---

### No Indicator

Most of the time, you won't see any indicator at all! The bot just responds directly. This happens for:
- Casual conversation
- Simple questions
- Reactions and banter
- Anything that doesn't need memory lookup

---

## Step-by-Step Breakdown

| Icon | Meaning |
|------|---------|
| 💭 | The bot is thinking/reasoning |
| 🔍 | Checking memory |
| 🛠️ | Using a specific tool |
| ✅ | Got a result back |

---

## Why Show This?

We show thinking steps so you know the bot is actively working on your question—not just frozen! For complex questions, seeing the reasoning process helps you understand:

1. **The bot heard you** - It's not stuck
2. **It's putting in effort** - Searching through your history
3. **It cares about accuracy** - Taking time to get it right

---

## Tips

- **Be patient with Deep Thinking** - Complex questions are worth the wait!
- **The steps are real** - You're seeing actual tool calls, not fake loading
- **Longer isn't always better** - Simple questions get fast answers

---

## Questions?

If you're curious about how the bot works or want to force deep thinking mode, you can use `!reflect` before your message:

```
!reflect Why do I always feel stressed on Mondays?
```

This bypasses the automatic detection and forces the bot to do a thorough analysis.
