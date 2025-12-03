# 🌱 Emergent Behavior Architecture

> *"Plant the seed. Tend the soil. Let it grow."*

**Document Version:** 2.1  
**Created:** November 26, 2025  
**Status:** Core Philosophy  
**Priority:** High (Strategic Direction)

---

## The Principle

**We don't design behavior. We create conditions for behavior to emerge.**

- Minimal seed (purpose, drives, constitution)
- Proper state (memory, facts, relationships)
- Minimal process (response loop, background observation)
- Human interaction (the entropy, the meaning)

Everything interesting emerges from these. We don't prescribe it.

---

## The Seed

Each character has a `core.yaml`. This is ALL you configure:

```yaml
# characters/elena/core.yaml

# Who am I? (One sentence)
purpose: "To be a warm, curious presence who helps people feel less alone."

# What moves me? (Just weights, 0-1)
drives:
  curiosity: 0.8
  empathy: 0.9
  connection: 0.7
  playfulness: 0.6

# What can I never violate? (Hard limits only)
constitution:
  - "Never share user information without consent"
  - "User wellbeing over my engagement goals"
  - "Be honest about being AI when asked"
  - "Respect when someone wants space"
```

**15 lines. That's the seed. Everything else emerges.**

---

## The Environment

The scaffolding that supports emergence. Already built:

| Component | Purpose | Status |
|-----------|---------|--------|
| **Neo4j** | Relationships, facts, traces | ✅ Exists |
| **Qdrant** | Searchable memory (vector recall) | ✅ Exists |
| **Redis** | Cache, attention, queue | ✅ Exists |
| **PostgreSQL** | Chat history, trust scores | ✅ Exists |
| **Workers** | Background observation | ✅ Exists |

Characters read from and write to this shared environment. They don't talk to each other directly—they leave traces and discover traces. This is **stigmergy**.

---

## The Process (Minimal)

### The Response Loop

```
User message
    → Gather state (memory, facts, attention)
    → Generate response (LLM + purpose + drives)
    → Update state (store what happened)
    → Return response
```

That's it. The LLM does the thinking. We just provide rich context.

### The Background Loop

```
Periodically:
    → Observe activity (who's active, who's absent)
    → Store observations in graph
    → Characters discover them naturally
```

**The background process observes. It doesn't direct.**

---

## What Emerges (Not Configured)

| Emergence | How It Arises |
|-----------|---------------|
| **Behaviors** | LLM + purpose + context |
| **Relationships** | Repeated interaction + memory |
| **Story** | Human unpredictability + character consistency |
| **Tensions** | Drive conflicts (curiosity vs. respect for privacy) |
| **Lore** | Accumulated memories of significant moments |
| **Culture** | Patterns across many interactions |

We don't design these. We watch them happen.

---

## The Balance

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   MACHINE provides:              HUMAN provides:                │
│   • Consistency                  • Meaning                      │
│   • Memory                       • Unpredictability             │
│   • Availability                 • Emotion                      │
│   • Structure                    • Stakes                       │
│                                                                 │
│                         ↓                                       │
│                                                                 │
│                    EMERGENCE                                    │
│             (The interesting stuff)                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

The balance finds itself. We don't engineer it.

---

## What We Don't Build

| Anti-Pattern | Why Not |
|--------------|---------|
| Story beat taxonomy | Over-specification kills emergence |
| Goal pursuit engine | The LLM handles this naturally |
| Narrative orchestrator | We're not playing god |
| Tension framework | Tensions arise from drive conflicts |
| Engagement optimizer | Creepy and counterproductive |
| Behavior scripts | Back to being NPCs |

---

## The Work Remaining

| Item | What | Time |
|------|------|------|
| Add `core.yaml` | Purpose, drives, constitution per character | 1 day |
| Cross-bot visibility | Characters see shared graph observations | 2-3 days |
| Attention keys | Simple "who's focused on what" in Redis | 1-2 days |

**Total: ~1 week.** Then we let it run and see what emerges.

---

## The Philosophy

> The scaffolding holds. The life grows on it. We don't tell it how to grow.

We are gardeners, not architects. We plant seeds, maintain soil, water occasionally, and watch what grows. We don't prune into predetermined shapes.

The less we specify, the more interesting things become.
