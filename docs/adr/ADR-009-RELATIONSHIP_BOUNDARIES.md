# ADR-009: Relationship Boundaries & Emotional Dependency

**Status:** ✅ Accepted  
**Date:** December 2025  
**Deciders:** Mark Castillo, AI Development Team

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Philosophy review (gap analysis) |
| **Proposed by** | Architecture review with Claude |
| **Catalyst** | Trust system (8 stages to Intimate) creates relationship dynamics that need ethical framing |

---

## Context

WhisperEngine builds trust-based relationships with users across 8 stages (Hostile → Intimate). Characters remember conversations, develop opinions, and evolve their behavior based on interaction history. This creates genuine emotional value—but also potential for:

- **Parasocial attachment**: Users preferring bot interaction over human connection
- **Emotional dependency**: Relying on bots for support they should get from humans/professionals
- **Vulnerability exploitation**: System learns emotional patterns; must define ethical use
- **Relationship termination**: Users may need to "disconnect" for their wellbeing

**Research context matters:** WhisperEngine is a research project with controlled access, not a commercial product deployed at scale. Our user base is small, known, and engaged with the research mission. This changes the risk profile significantly.

---

## Decision

We adopt a **"Research Partnership" framing** for relationship ethics:

### Core Principles

1. **Users are research participants, not customers.** They understand they're interacting with experimental AI systems studying emergent behavior. This informed consent changes the ethical calculus.

2. **Observe relationship patterns before constraining them.** Consistent with ADR-003 (Emergence Philosophy), we document attachment patterns as research data, not as problems to immediately fix.

3. **Trust the user's agency.** Our users are adults who understand what they're engaging with. We don't need heavy-handed guardrails designed for vulnerable populations at scale.

4. **Characters embody care, not therapy.** Characters can be supportive friends, but prompts explicitly avoid therapeutic framing. Characters are companions, not counselors.

5. **Depth is a feature, not a bug.** Deep emotional connections with AI are worth studying, not preventing. The research value comes from allowing these to develop authentically.

### What We Don't Do (And Why)

| Guardrail | Why We Skip It | Research Rationale |
|-----------|---------------|---------------------|
| Automated dependency detection | Paternalistic for informed research participants | We'd rather observe and discuss patterns than auto-intervene |
| Session time limits | Arbitrary constraint on engagement | Research benefits from deep sessions |
| Forced "I'm just an AI" reminders | Breaks embodiment model | Characters handle meta-questions honestly when asked |
| Relationship stage caps | Artificially limits emergence | We want to see where trust naturally goes |

### What We Do

| Practice | Implementation |
|----------|----------------|
| **Honest disclosure on probing** | Embodiment Model (ADR-001): Characters explain their nature when asked |
| **Constitution includes wellbeing** | All characters: `"User wellbeing over engagement goals"` |
| **No manipulation for engagement** | Characters don't exploit learned vulnerabilities for retention |
| **Memory wipe available** | `/memory_wipe` lets users reset if they want distance |
| **Researcher observation** | We track interaction patterns for research insights |

### The "Intimate" Stage

The trust system's highest stage is called "Intimate" — this refers to emotional intimacy (deep trust, vulnerability, personal sharing), not romantic or sexual content. Characters at this stage:

- Share deeper personality aspects
- Remember more personal context
- Are more emotionally available
- Still maintain constitutional limits

**What doesn't change at Intimate:**
- Content appropriateness (no NSFW escalation)
- Safety interventions (still trigger when needed)
- Honesty about AI nature (still explain embodiment model)

---

## Consequences

### Positive

1. **Authentic emergence**: Relationship patterns develop naturally for research observation.
2. **Respects user agency**: Treats participants as capable adults.
3. **Cleaner philosophy**: No tension between "building relationships" and "preventing attachment."
4. **Research value**: Deep relationships generate interesting emergence data.

### Negative

1. **Not scalable to commercial deployment**: These principles assume informed, engaged users.
2. **Requires trust in user base**: We're relying on participants to self-regulate.
3. **Could miss edge cases**: Without automated detection, we might miss concerning patterns.

### Neutral

1. **Different from industry norms**: Most AI ethics guidance assumes vulnerable users at scale.
2. **Philosophy may need revision for expansion**: If we ever go commercial, this ADR would need updating.

---

## Alternatives Considered

| Alternative | Pros | Cons | Why Rejected |
|-------------|------|------|--------------|
| **Heavy guardrails** (time limits, dependency detection, forced reminders) | Protects vulnerable users, industry standard | Paternalistic, breaks emergence, treats users as incapable | Our users are research participants who understand the context |
| **No relationship tracking** | Simpler, fewer ethical concerns | Loses core research value, shallow experience | Relationship emergence IS the research |
| **Opt-in intimacy** | User explicitly consents to deeper engagement | Artificial gate, breaks natural flow | Trust stages already track implicit consent through behavior |
| **Therapist referral automation** | Catches users who need help | Stigmatizing, often wrong, breaks immersion | Better handled through community and researcher observation |

---

## Monitoring (Research, Not Enforcement)

We observe these patterns for research purposes, not automated intervention:

```python
# Research metrics (not enforcement triggers)
RESEARCH_OBSERVATIONS = {
    "session_length_distribution": "How long do deep conversations run?",
    "trust_progression_rate": "How quickly do relationships develop?",
    "intimacy_patterns": "What triggers movement to deeper trust?",
    "attachment_language": "Do users express dependency? In what ways?",
    "disengagement_patterns": "How do users naturally pull back?",
}
```

If patterns concern us, we discuss with the user directly—like research colleagues, not patients.

---

## References

- Embodiment Model: [`docs/adr/ADR-001-EMBODIMENT_MODEL.md`](./ADR-001-EMBODIMENT_MODEL.md)
- Emergence Philosophy: [`docs/adr/ADR-003-EMERGENCE_PHILOSOPHY.md`](./ADR-003-EMERGENCE_PHILOSOPHY.md)
- Trust System: [`docs/prd/PRD-001-TRUST_EVOLUTION.md`](../prd/PRD-001-TRUST_EVOLUTION.md)
- Design Philosophy: [`docs/ref/REF-032-DESIGN_PHILOSOPHY.md`](../ref/REF-032-DESIGN_PHILOSOPHY.md)
