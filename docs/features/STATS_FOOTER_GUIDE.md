# Understanding the Stats Footer

**Status**: ✅ Implemented  
**Version**: 2.2  
**Last Updated**: December 1, 2025

Some responses include a stats footer at the bottom—a quick summary of what's happening behind the scenes. Here's what each part means!

## Example Footer

```
──────────────────────────────────────────────────
💙 **Relationship**: Friend (Trust: 45/150 [empathetic, playful]) • 127 interactions
🎯 **Active Goals**: emotional-support, creative-exploration
🧠 **Memory**: Retrieved 4 relevant memories
💡 **Recent Insight**: You tend to feel more creative in the evenings
⚡ **Performance**: Total: 2340ms | LLM: 1850ms | Overhead: 490ms
──────────────────────────────────────────────────
```

---

## What Each Line Means

### 💙 Relationship

Shows how your relationship with the bot has developed over time.

| Part | Meaning |
|------|---------|
| **Level** | Stranger → Acquaintance → Friend → Close Friend → Soulmate |
| **Trust Score** | Points earned through consistent, meaningful interactions (max 150) |
| **Traits** | Special personality traits unlocked as trust grows |
| **Interactions** | Total number of messages you've sent |

**How trust grows:**
- Having genuine conversations
- Sharing things about yourself
- Returning regularly
- Positive reactions (👍, ❤️, etc.)

---

### 🎯 Active Goals

The bot tracks certain interaction goals based on your conversations. These might include:
- `emotional-support` - Helping you through tough times
- `creative-exploration` - Collaborating on creative projects  
- `daily-checkin` - Regular check-ins about your day
- And more depending on the character

Goals help the bot stay consistent and remember what you're working on together.

---

### 🧠 Memory

Shows how many relevant memories were retrieved for this response.

- **0 memories** = Fresh conversation, no past context needed
- **1-3 memories** = Quick context check
- **4+ memories** = Deep dive into your history

More memories doesn't always mean better—sometimes a simple response is best!

---

### 💡 Recent Insight

The bot sometimes notices patterns about you over time:
- "You seem more energetic on weekends"
- "You often mention your dog when stressed"
- "Creative topics make you engaged"

These insights help the bot understand you better.

---

### ⚡ Performance

Technical timing breakdown (for the curious!):

| Metric | What It Measures |
|--------|------------------|
| **Total** | End-to-end response time |
| **LLM** | Time spent with the AI model |
| **Overhead** | Memory retrieval, database queries, etc. |

Typical times:
- Simple responses: 1-3 seconds
- Memory lookups: 3-5 seconds  
- Reflective mode: 5-30 seconds

---

## Toggling the Stats Footer

The stats footer is **off by default**. To enable or disable it:

```
/stats_footer on
/stats_footer off
```

Your preference is saved and remembered across sessions.

---

## Compact Mode

Sometimes you'll see a shorter one-line version:

```
💙 Friend (Trust: 45/150) | 🧠 4 memories | ⚡ 2340ms
```

This shows the essentials without taking up much space.

---

## Why Have a Stats Footer?

1. **Transparency** - See how the bot "thinks" about you
2. **Trust building** - Watch your relationship grow over time
3. **Debugging** - Know if something feels slow or off
4. **Fun** - Some people just like seeing the numbers!

If you find it distracting, just turn it off with `/stats_footer off`.
