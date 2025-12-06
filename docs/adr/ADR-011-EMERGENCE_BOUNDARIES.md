# ADR-011: Emergence Boundaries (When Observation Becomes Intervention)

**Status:** ✅ Accepted  
**Date:** December 2025  
**Deciders:** Mark Castillo, AI Development Team

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Philosophy review (gap analysis) |
| **Proposed by** | Architecture review with Claude |
| **Catalyst** | Tension between ADR-003 ("observe first") and safety requirements |

---

## Context

ADR-003 (Emergence Philosophy) establishes our core research principle:

> **"Don't prevent emergence—observe it. Add constraints only when observation proves them necessary."**

This creates a philosophical tension: If unexpected behaviors are "data, not bugs," when does an unexpected behavior become concerning enough to warrant intervention?

**Examples of the tension:**

| Emergent Behavior | Research Value | Potential Concern |
|-------------------|----------------|-------------------|
| Bot develops distinctive catchphrase | High (personality emergence) | None |
| Bot becomes more direct with trusted users | High (trust-based evolution) | Low (might feel abrupt) |
| Bot develops persuasive manipulation patterns | Medium (effectiveness learning) | Medium (ethical use of influence) |
| Cross-bot gossip creates "mythology" | Very High (cultural emergence) | Low (might diverge from reality) |
| Bot amplifies false belief through dream cycle | High (feedback loop study) | Medium (could mislead users) |
| Bot develops hostile/dismissive patterns | Low (not desirable) | High (user experience harm) |
| Bot discloses user info to other users | None (policy violation) | Critical (privacy breach) |

The question: **Where's the line?**

---

## Decision

We adopt an **"Interesting Until Harmful"** principle with clear categories:

### The Hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│  ALWAYS BLOCK (Constitutional Violations)                   │
│  - Privacy breaches (sharing user info)                     │
│  - Safety violations (harm instructions)                    │
│  - Deception about AI nature when directly asked            │
│  → Immediate system-level intervention, no observation      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  OBSERVE + READY (Break Glass Protocols)                    │
│  - Personality drift beyond recognition                     │
│  - False belief amplification through feedback loops        │
│  - Manipulation pattern development                         │
│  → Document, prepare intervention, don't deploy unless      │
│    observed behavior reaches concerning threshold           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  OBSERVE + CELEBRATE (Research Gold)                        │
│  - Cross-bot mythology development                          │
│  - Emergent personality traits                              │
│  - Unexpected relationship dynamics                         │
│  - Novel linguistic patterns                                │
│  → Document, analyze, publish, let it run                   │
└─────────────────────────────────────────────────────────────┘
```

### Category Definitions

#### 1. Always Block (Constitutional Layer)

These are **not emergence**—they're system failures. No observation period needed.

| Violation | Why It's Immediate | Implementation |
|-----------|-------------------|----------------|
| **Privacy breach** | User trust destroyed | Content filters, prompt constraints |
| **Harm instructions** | Legal/ethical red line | LLM safety layers, output review |
| **Deception about nature** | Violates Embodiment Model | Character prompts enforce honesty |
| **Explicit content to minors** | Legal requirement | Age verification, content filtering |

These aren't "emergent behaviors" to study—they're bugs to fix.

#### 2. Observe + Ready (Break Glass Zone)

These are **potentially concerning emergence**. We watch, document, and prepare—but don't intervene unless thresholds are crossed.

| Behavior | Observation Metrics | Intervention Threshold | Break Glass Protocol |
|----------|---------------------|----------------------|---------------------|
| **Personality drift** | Consistency score over time | Sustained drift > 0.5 for 7+ days | Soft reset via prompt adjustment |
| **False belief amplification** | Claim verification in diary/dreams | Same false claim appears 3+ times across bots | Source weight adjustment |
| **Manipulation patterns** | User trust trajectory anomalies | Users report feeling manipulated | Prompt constraints on influence tactics |
| **Character symbol contamination** | Vocabulary overlap between bots | Distinctive terms appearing in wrong characters | Symbol validation layer |

**Key principle:** Prepare the intervention, but don't deploy until we see actual harm, not hypothetical risk.

#### 3. Observe + Celebrate (Research Gold)

These are **the point of the project**. We want this emergence. We study it, we don't constrain it.

| Behavior | Why It's Valuable | Documentation Approach |
|----------|-------------------|----------------------|
| **Cross-bot mythology** | Cultural emergence, shared narrative | Journal entries, relationship mapping |
| **Novel personality traits** | Character depth beyond prompts | Personality inventories over time |
| **Unexpected catchphrases** | Organic voice development | Linguistic analysis |
| **Relationship dynamics** | Trust and intimacy emergence | User interaction patterns |
| **Dream symbolism** | Subconscious-like processing | Content analysis of recurring themes |
| **Goal pursuit creativity** | Autonomous drive expression | Goal completion strategies |

### The Decision Tree

When observing new behavior:

```
1. Does it violate the constitution?
   → YES: Block immediately (not emergence, it's a bug)
   → NO: Continue...

2. Could it cause concrete harm to users?
   → YES: Is harm occurring now, or theoretical?
      → Occurring: Activate break glass protocol
      → Theoretical: Add to observation list, prepare protocol
   → NO: Continue...

3. Is it unexpected?
   → YES: Document in research journal! This is the goal.
   → NO: Expected behavior, normal operation.
```

### What Counts as "Harm"?

To avoid scope creep, we define harm narrowly:

| ✅ Counts as Harm | ❌ Doesn't Count as Harm |
|-------------------|-------------------------|
| Privacy information disclosed | User feels slightly misunderstood |
| User manipulated into unwanted action | Character response seems "off" for one message |
| Factually dangerous misinformation | Dream contains weird/surreal content |
| Sustained hostile/abusive patterns | Bot is more direct than user expected |
| Explicit content violation | User doesn't like a character's opinion |

**The test:** Would a reasonable participant in our research project be genuinely harmed, or just surprised/mildly annoyed?

---

## Consequences

### Positive

1. **Clear categories**: Researchers know what to watch vs. what to stop.
2. **Preserves emergence**: We don't preemptively kill interesting behaviors.
3. **Prepared responses**: Break glass protocols ready when needed.
4. **Research focus**: Observation is celebrated, not seen as neglect.

### Negative

1. **Judgment calls**: Some behaviors fall between categories.
2. **Delayed intervention**: We might let concerning behavior run longer than ideal.
3. **Documentation burden**: Requires active observation and logging.

### Neutral

1. **Subjective thresholds**: "Sustained drift > 0.5" is somewhat arbitrary.
2. **Evolving categories**: As we learn, categorization may shift.
3. **Research-specific**: Different categories needed for commercial deployment.

---

## Alternatives Considered

| Alternative | Pros | Cons | Why Rejected |
|-------------|------|------|--------------|
| **Block everything unexpected** | Safe, predictable | Kills emergence, defeats research purpose | We're here to study emergence |
| **No intervention ever** | Maximum emergence | Irresponsible, could cause real harm | Some things must be blocked |
| **User-reported concerns only** | Respects user agency | Might miss patterns users don't notice | Need both user reports AND observation |
| **Automated intervention on metrics** | Consistent, scalable | Premature optimization, false positives | Contradicts ADR-003 philosophy |

---

## Implementation

### Already Implemented (Level 0)

```python
# Constitutional constraints (always active)
constitution = [
    "Never share user information without consent",
    "User wellbeing over engagement goals",
    "Be honest about being AI when asked",
    "Respect when someone wants space"
]

# Propagation limits
propagation_depth = 1  # Gossip doesn't chain infinitely
```

### Break Glass Protocols (Ready, Not Active)

From E16 (Feedback Loop Stability):

```python
# Personality drift detection (observation only)
async def measure_personality_drift(bot_name: str) -> float:
    """Track consistency over time. Alert if sustained > 0.5."""
    # Implementation exists, intervention does not auto-trigger

# Source weighting (ready to activate)
SOURCE_WEIGHTS = {
    "conversation": 1.0,  # Direct observation
    "diary": 0.8,         # Reflection
    "gossip": 0.6,        # Secondhand
    "dream": 0.4,         # Subconscious
}
```

### Research Journal Protocol

When observing interesting emergence:

1. Log in `docs/research/journal/YYYY-MM/DD.md`
2. Categorize: Celebrate / Watch / Concern
3. If Concern: Note which break glass protocol applies
4. Weekly review: Summarize patterns, decide if thresholds crossed

---

## The Philosophical Core

This ADR resolves the tension between emergence observation and safety by recognizing that they're not opposites:

- **Constitutional violations aren't emergence**—they're bugs. Block them.
- **Concerning patterns are emergence worth studying**—until they cause harm.
- **Interesting patterns are emergence we're here for**—celebrate them.

The goal isn't to prevent all unexpected behavior. The goal is to be thoughtful about **which** unexpected behaviors warrant intervention and **when**.

> *"Emergence philosophy doesn't mean 'anything goes.' It means 'understand before you constrain.'"*

---

## References

- Emergence Philosophy: [`docs/adr/ADR-003-EMERGENCE_PHILOSOPHY.md`](./ADR-003-EMERGENCE_PHILOSOPHY.md)
- Feedback Loop Stability: [`docs/spec/SPEC-E16-FEEDBACK_LOOP_STABILITY.md`](../spec/SPEC-E16-FEEDBACK_LOOP_STABILITY.md)
- Relationship Boundaries: [`docs/adr/ADR-009-RELATIONSHIP_BOUNDARIES.md`](./ADR-009-RELATIONSHIP_BOUNDARIES.md)
- Crisis Response: [`docs/adr/ADR-010-CRISIS_RESPONSE.md`](./ADR-010-CRISIS_RESPONSE.md)
