# ADR-018: Deferral of Reverie Self-Reflection Enhancement

**Status:** ✅ Accepted  
**Date:** December 14, 2025  
**Deciders:** Mark Castillo

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Enhancement proposal for SPEC-E34 (Reverie) |
| **Proposed by** | External proposal review |
| **Catalyst** | Observation that Marcus's effective interventions (IcePickle) weren't captured as reusable patterns |
| **Key insight** | Reverie could analyze bot's own reasoning traces to develop self-awareness |

---

## Context

A proposal was submitted to extend Reverie (Phase E34) with **self-reflection capabilities**. During idle time, bots would analyze their own reasoning traces to identify behavioral patterns, learning things like:

- "I tend to use Socratic questioning with defensive users" (effective)
- "I over-apologize — users want more directness" (ineffective)
- "Music metaphors work for creative topics but confuse in technical contexts" (mixed)

These self-patterns would be stored as memories and referenced naturally in future responses.

### Technical Approach

**Proposed Implementation:**
- Add `reflect_on_self` node to ReverieGraph after `generate_reverie`
- Fetch recent reasoning traces (from Phase B5 - Trace Learning)
- LLM analyzes: "What patterns do I see in my own problem-solving?"
- Store as `self_pattern` memory type (no schema changes)
- Inject into character context for natural reference

**Cost:** ~$0.003 per reverie cycle, ~$0.15/month per bot (11 bots = $1.65/month total)

**Time:** 3-4 days implementation (add node, context integration, trace integration, rollout)

### Alignment with Design Philosophy

**Strengths (passes emergence checks):**
- ✅ **Emergence over declaration:** Patterns *discovered* from traces, not predefined
- ✅ **Vocabulary over schema:** Uses existing `memory_type` field, no new columns
- ✅ **Observe first:** Bot learns through data analysis, not configuration
- ✅ **Cost-effective:** Extremely low cost for potential value

**Concerns:**
- ⚠️ **Self-delusion risk:** LLMs are pattern-seekers; may invent patterns from noise
- ⚠️ **Personality lock-in:** Bot might become rigid about its own style
- ⚠️ **Speculative:** No observed need yet; solving a hypothetical problem

---

## Decision

**We defer self-reflection enhancement until after multi-party schema work (ADR-014/017).**

### Rationale

#### 1. **Observe First, Constrain Later**
From ADR-003: *"Don't prevent emergence—observe it. Add constraints only when observation proves them necessary."*

We haven't observed bots struggling with pattern reuse yet. Let's watch bot-to-bot interactions first to see if self-reflection is actually needed.

#### 2. **Critical Path Priority**
Multi-party schema (ADR-014) is blocking:
- Bot-to-bot conversation storage (can't properly attribute messages)
- Cross-bot learning (broken without `author_id`)
- Trust evolution in multi-agent contexts

Self-reflection is valuable but not blocking user-facing features.

#### 3. **Better Data After Bot-to-Bot**
Once bots interact with each other (ADR-017), we'll see:
- Do they repeat ineffective approaches?
- Do they learn from each other organically?
- Do they develop distinct styles without self-reflection?

This observation will inform whether self-reflection is actually valuable.

#### 4. **Synergy with Adaptive Identity**
If we implement Adaptive Identity (Phase 2.6 - self-editing persona), self-reflection becomes more valuable:
- Self-knowledge → informed self-editing
- "I notice I over-apologize" → edit personality to be more direct
- Creates a feedback loop: observe self → modify self → observe change

**Better to implement together if we pursue Adaptive Identity.**

---

## Consequences

### Accepted

1. **Self-reflection capability documented as future extension** in SPEC-E34
2. **Full proposal preserved** for reference (December 14, 2025 submission)
3. **Decision can be revisited** after bot-to-bot observation period

### Benefits of Deferral

1. **Focus on critical path** (multi-party schema enables multiple features)
2. **Evidence-based decision** (observe real behavior before engineering)
3. **Avoid premature optimization** (solve observed problems, not hypothetical)
4. **Better timing** (synergy with Adaptive Identity if we pursue it)

### If We Implement Later

**Pre-conditions for reconsideration:**
- ✅ ADR-014/017 complete (multi-party schema + bot-to-bot)
- ✅ Observed bot behavior patterns (repetition of ineffective approaches, lack of specialization)
- ✅ Adaptive Identity work active (creates natural synergy)

**OR:**
- Clear user value observed ("Marcus always does X" - users notice consistency)
- Research value (studying how self-models develop in AI)

---

## Related Documentation

- [SPEC-E34-REVERIE.md](../spec/SPEC-E34-REVERIE.md) — Base Reverie spec (now includes self-reflection as future extension)
- [SPEC-B05-TRACE_LEARNING.md](../spec/SPEC-B05-TRACE_LEARNING.md) — Trace storage (data source for self-reflection)
- [ADR-003-EMERGENCE_PHILOSOPHY.md](./ADR-003-EMERGENCE_PHILOSOPHY.md) — "Observe First, Constrain Later" principle
- [ADR-014-MULTI_PARTY_DATA_MODEL.md](./ADR-014-MULTI_PARTY_DATA_MODEL.md) — Current priority (multi-party schema)
- [ADR-017-BOT_TO_BOT_SIMPLIFIED.md](./ADR-017-BOT_TO_BOT_SIMPLIFIED.md) — Bot-to-bot interactions (observation opportunity)
- `/reverie-self-reflection-enhancement.md` — Full proposal (December 14, 2025)

---

## Notes

### Why This is Good Emergence Practice

This decision demonstrates our research methodology:
1. **Received interesting proposal** (self-reflection could enable self-awareness)
2. **Evaluated against philosophy** (passes emergence checks)
3. **Asked: "Have we observed the problem?"** (no)
4. **Chose observation over engineering** (defer until we see bot-to-bot behavior)
5. **Documented as option** (preserved for later consideration)

This is exactly the "Observe First" principle in action.

### Future Consideration Triggers

**Implement self-reflection if we observe:**
- Bots repeating ineffective approaches without learning
- Lack of personality differentiation (all bots feel similar)
- Users asking "why do you always respond this way?"
- Bot-to-bot interactions revealing need for self-coordination

**OR if we pursue:**
- Adaptive Identity (Phase 2.6) - self-knowledge enables self-editing
- Research goal shift toward studying self-model development

---

**Version History:**
- v1.0 (December 14, 2025) - Initial decision to defer self-reflection enhancement
