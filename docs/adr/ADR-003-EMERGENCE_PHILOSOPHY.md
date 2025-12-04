# ADR-003: Emergence Philosophy ("Observe First, Constrain Later")

**Status:** ✅ Accepted  
**Date:** November 2025  
**Deciders:** Mark Castillo, Claude Collaboration (see emergence_philosophy/)

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Research philosophy development |
| **Proposed by** | Mark + Claude (collaborative dialogue) |
| **Catalyst** | Need for principled approach to emergent behavior |

---

## Context

WhisperEngine creates recursive feedback loops where AI-generated content feeds back into the system:

```
User Conversation → Memory
        ↓
    Character Diary (processes memories)
        ↓
    Character Dream (processes diary)
        ↓
    Other Bot reads diary (cross-bot gossip)
        ↓
    Other Bot's Diary (references first bot)
        ↓
    First Bot's next Dream (may reference other bot)
```

**The concern:** Information could amplify, distort, or degrade through cycles. Characters might develop "false memories" or drift from their core personality.

**The question:** How much should we constrain this emergence?

---

## Decision

We adopt an **"Observe First, Constrain Later"** philosophy:

> **Don't prevent emergence—observe it. Add constraints only when observation proves them necessary.**

### Core Principles

1. **Document behaviors before deciding if they need correction** — premature optimization prevents discovery

2. **Minimal viable instrumentation** — add only metrics needed to answer current questions

3. **Embrace surprise** — unexpected behaviors are data, not bugs

4. **Character autonomy** — bots are subjects of study, not just objects to control

### Anti-Over-Engineering Principle

Before adding new fields, categories, or configuration:

| Question | Prefer |
|----------|--------|
| "Will this emerge naturally, or must we declare it?" | Behavior over taxonomy |
| "Can vocabulary do what schema would do?" | Prompt language over code |
| "Are we building it, or letting the system notice it?" | Emergent over declared |

**Example:** We don't have a `memory_layer: "subconscious"` field. Instead, memories with high `absence_streak` *behave* as subconscious—the character notices this through retrieval patterns, not labels.

> *"A declared subconscious is a filing system. An emergent subconscious is actually subconscious."*

---

## Consequences

### Positive

1. **Research Value**: We can study how AI systems develop complex behavior patterns.

2. **Richer Narratives**: Cross-bot mythology and emergent connections create depth we couldn't design.

3. **Less Code**: Fewer schema fields, enums, and configuration to maintain.

4. **Authentic Behavior**: Characters that "notice" patterns feel more genuine than those told about them.

5. **Flexibility**: We can respond to observed patterns rather than predicting all possibilities.

### Negative

1. **Risk of Runaway Effects**: Without constraints, feedback loops could amplify errors.

2. **Harder to Debug**: Emergent behavior is less predictable than deterministic logic.

3. **Requires Observation Infrastructure**: We need metrics and dashboards to observe what's emerging.

4. **Delayed Response**: We react to problems instead of preventing them.

### Neutral

1. **Different Development Rhythm**: Less upfront design, more observational iteration.

2. **"Break Glass" Protocols**: We maintain ready-to-implement constraints if observation shows problems.

---

## Escalation Levels

We maintain tiered response protocols:

| Level | Trigger | Response |
|-------|---------|----------|
| **0** | None | Already implemented (propagation_depth=1, privacy filters) |
| **1** | Observation shows pattern | Minimal intervention (temporal decay, source weights, metrics) |
| **2** | Metrics show sustained drift | Soft constraints (prompt nudges, scoring adjustments) |
| **3** | Serious failure observed | Structural changes (full specs, new schema if truly needed) |

**Current State:** Level 1 implemented. Levels 2-3 are documented "break glass" protocols.

---

## Pre-Implementation Checklist

Before implementing new features, answer these questions:

1. **Schema test:** Am I adding new fields/enums? (Prefer no new schema)
2. **Behavior test:** Can this be expressed as behavior instead of category?
3. **Vocabulary test:** Can prompts do what code would do?
4. **Discovery test:** Will the character *notice* this, or do we have to *tell* it?

If answers lean toward "need new schema/code/declarations" — reconsider the approach.

---

## Alternatives Considered

| Alternative | Pros | Cons | Why Rejected |
|-------------|------|------|--------------|
| **Heavy Upfront Constraints** | Predictable, safe | Kills emergence, over-engineered | Research value lost, sterile behavior |
| **No Observation** | Simple, hands-off | Can't detect problems | Irresponsible for production system |
| **User-Controlled Constraints** | User agency | Complexity burden, users don't know system | Users want magic, not configuration |
| **Per-Bot Constraint Policies** | Tailored control | Maintenance nightmare | 10+ bots with unique policies = chaos |

---

## Implementation

### Minimal Safety Net (Level 1)

```python
# Temporal decay: old memories influence less
score *= decay_rate ** age_days

# Source weights: direct observations > gossip > dreams
SOURCE_WEIGHTS = {
    "conversation": 1.0,
    "diary": 0.8,
    "gossip": 0.6,
    "dream": 0.4,
}

# Drift observation: track personality consistency (no correction yet)
await influxdb.write("drift_observation", {
    "bot_name": bot_name,
    "consistency_score": score,
    "measured_at": datetime.now()
})
```

### Break Glass Protocols (Ready, Not Active)

- **Epistemic Chain Tracking**: Track belief provenance if false beliefs amplify
- **Reality Check Worker**: Validate claims against facts if delusions observed
- **Symbol Validation**: Monitor distinctive language if characters merge
- **Personality Drift Correction**: Nudge back to baseline if sustained drift > 0.5

---

## References

- Emergence philosophy archive: [`docs/emergence_philosophy/`](../emergence_philosophy/)
- Feedback loop stability: [`docs/roadmaps/FEEDBACK_LOOP_STABILITY.md`](../roadmaps/FEEDBACK_LOOP_STABILITY.md)
- Architecture audit: [`docs/reviews/EMERGENCE_ARCHITECTURE_AUDIT.md`](../reviews/EMERGENCE_ARCHITECTURE_AUDIT.md)
- Claude collaboration: [`docs/emergence_philosophy/05_EMERGENCE_WITH_GUARDRAILS_SYNTHESIS.md`](../emergence_philosophy/05_EMERGENCE_WITH_GUARDRAILS_SYNTHESIS.md)
