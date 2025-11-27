# Understanding Thinking Indicators

When you chat with the bot, you might sometimes see status messages appear before the response. These show you what's happening behind the scenes!

## What Do They Mean?

### Character-Specific Indicators

Each character has their own unique way of showing they're thinking or using tools. This reflects their personality and makes interactions more authentic.

**Example - Elena (nostalgic, warm):**
```
🌙 **Lost in thought...**

> 💭 Let me think about what we discussed before...
> 🛠️ *Using search_memories...*
> ✅ *search_memories*: Found 3 relevant conversations
> 💭 I see a pattern here...
```

**Example - Marcus (analytical):**
```
🔍 **Analyzing this...**

> 🛠️ *Using lookup_facts...*
> ✅ *lookup_facts*: Found relevant information
```

**Example - Aria (creative, mystical):**
```
🔮 **Channeling inspiration...**

> 🛠️ *Using generate_image...*
> ✅ Image created!
```

### Two Types of Thinking

**Deep/Complex Thinking (Reflective Mode):**
When you ask something complex—like questions about your past conversations, philosophical topics, or requests that need the bot to search through memories and piece things together. Takes 5-30 seconds depending on complexity.

**Quick Tool Use:**
When the bot uses one of its tools—like searching memories, looking up facts, or generating images. Usually takes just a few seconds.

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

- **Be patient with Reflective Mode** - Complex questions are worth the wait!
- **The steps are real** - You're seeing actual tool calls, not fake loading
- **Longer isn't always better** - Simple questions get fast answers

---

## Questions?

If you're curious about how the bot works or want to force reflective mode, you can use `!reflect` before your message:

```
!reflect Why do I always feel stressed on Mondays?
```

This bypasses the automatic detection and forces the bot to do a thorough analysis.
