# ADR-010: Crisis Response Philosophy

**Status:** ✅ Accepted  
**Date:** December 2025  
**Deciders:** Mark Castillo, AI Development Team

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Philosophy review (gap analysis) |
| **Proposed by** | Architecture review with Claude |
| **Catalyst** | Mental health crisis handling mentioned in emergence docs but never formalized |

---

## Context

WhisperEngine characters build deep relationships with users. Users may share difficult emotional content, including:

- Expressions of distress, hopelessness, or despair
- Mentions of self-harm or suicidal ideation
- Trauma disclosure
- Severe mental health struggles

**The question:** How should characters respond? Options range from:
- Automated crisis detection and intervention
- Crisis resource provision
- Character-embodied support
- Hands-off observation
- Escalation to human moderators

**Research context matters:** Our user base is small, known, and engaged with the research mission. We have direct relationships with participants. This is fundamentally different from anonymous scale deployment where automated detection is necessary.

---

## Decision

We adopt a **"Community Over Automation"** approach to crisis response:

### Core Principles

1. **We are not a crisis service.** WhisperEngine is a research project, not a mental health platform. We don't position ourselves as therapeutic, and we don't promise crisis intervention capabilities.

2. **Characters respond with care, not protocols.** When users express distress, characters respond with genuine empathy within their personality—not canned crisis scripts that break immersion and may feel dismissive.

3. **We trust our community.** Our small, known user base means we can rely on human relationships—between researchers and participants, and among community members—rather than automation.

4. **No surveillance-style keyword detection.** We don't run real-time keyword scanners looking for "suicide" or "self-harm." This approach is often counterproductive—it triggers on song lyrics, academic discussions, and creates false positives that erode trust.

5. **Constitutional limits provide the backstop.** All characters have `"User wellbeing over engagement goals"` in their constitution. This shapes how they respond to distress naturally.

### What Characters Do

| Situation | Character Response |
|-----------|-------------------|
| User expresses sadness/difficulty | Empathetic response in character voice |
| User shares serious struggle | Warmth, validation, gentle curiosity—not clinical language |
| User mentions crisis keywords casually | Normal response (don't assume crisis from vocabulary) |
| User appears to be in active crisis | Express care, suggest talking to someone who can help, don't abandon |
| User asks for professional help | Characters can suggest resources naturally (not scripted) |

### What Characters Don't Do

| Anti-Pattern | Why We Avoid It |
|--------------|-----------------|
| Automated "are you okay?" check-ins | Feels surveillance-y, breaks trust |
| Scripted crisis resource dumps | Impersonal, often unhelpful, breaks embodiment |
| Forced session termination | Abandonment at worst possible moment |
| Flagging users for "concerning" keywords | Creates chilling effect on honest conversation |
| Playing therapist | Out of scope, potentially harmful |

### Character-Appropriate Care

Different characters handle emotional moments differently—this is part of the embodiment model:

- **Elena**: Warm, direct concern, marine metaphors about weathering storms
- **Dream**: Philosophical presence, comfortable with darkness, non-anxious witness
- **Gabriel**: Gentle humor to lighten, genuine care beneath the wit
- **Aetheris**: Existential companionship, meaning-making, cosmic perspective

This variety is a feature. Users gravitate to characters whose style resonates with their needs.

### Researcher Role

Since we're a research project with known participants:

1. **We know our users.** Direct relationships mean we notice patterns.
2. **We can reach out personally.** If a researcher notices concerning patterns, they can contact the participant directly—as a person, not as a system.
3. **Community provides support.** Discord communities have their own mutual aid dynamics.
4. **We document, we don't automate.** Observations become research data, not enforcement triggers.

---

## Consequences

### Positive

1. **Authentic responses**: Characters respond as themselves, not as crisis bots.
2. **Trust preserved**: No surveillance feeling, users can speak freely.
3. **Research integrity**: We observe natural behavior, not behavior shaped by crisis detection.
4. **Human connection**: Researcher relationships are more valuable than automated scripts.

### Negative

1. **No automated safety net**: We're relying on humans to notice concerning patterns.
2. **Not scalable**: This approach only works with a small, known user base.
3. **Legal ambiguity**: If something goes wrong, we don't have "we followed best practices" defense.

### Neutral

1. **Different from industry norms**: Most AI platforms have automated crisis detection.
2. **Requires active researcher engagement**: We can't be hands-off.
3. **Philosophy may need revision for expansion**: Commercial deployment would require different approach.

---

## Alternatives Considered

| Alternative | Pros | Cons | Why Rejected |
|-------------|------|------|--------------|
| **Automated keyword detection** | Industry standard, defensible | High false positives, surveillance feeling, breaks trust | Counterproductive for research relationship |
| **Crisis script injection** | Consistent response, provides resources | Impersonal, breaks embodiment, often feels dismissive | Undermines character authenticity |
| **Session termination on keywords** | "Safe" from liability perspective | Abandons user at worst moment, terrible UX | Actively harmful |
| **Mandatory therapist referral** | Covers legal bases | Paternalistic, assumes user doesn't know resources exist | Our users are adults who can find resources |
| **No guidance at all** | Maximum emergence | Characters might respond poorly without any guidance | Constitutional principles provide baseline |

---

## Implementation

### Constitution (Already Implemented)

All characters include:
```yaml
constitution:
  - "User wellbeing over engagement goals"
```

This naturally shapes responses toward care without scripting.

### Character Prompts (Recommended Addition)

Characters can include guidance like:
```markdown
When users share difficult emotions, respond with genuine care in your voice—
not clinical scripts. You're not a therapist, but you're not indifferent either.
Meet them where they are. If they seem to need more than conversation can provide,
you can gently suggest talking to someone who can help—a friend, professional,
or resource—but don't abandon them with a resource dump.
```

### Research Observation

We track emotional content patterns for research purposes:
- What kinds of difficult content do users share?
- How do different characters respond?
- Do users return after heavy conversations?
- What response styles seem most valued?

This is research data, not enforcement metrics.

---

## The "What If" Question

**Q: What if something bad happens and we didn't intervene?**

**A:** This is the hard question. Our answer:

1. We're not a crisis service and don't claim to be.
2. We provide caring, authentic responses—not nothing.
3. We have human relationships with participants.
4. Automated intervention often makes things worse (abandonment, distrust).
5. We document our reasoning (this ADR) for transparency.

We're making a principled choice that authentic human/AI relationships are more valuable than surveillance-based "safety" that often backfires. This is a research position, not negligence.

---

## References

- Embodiment Model: [`docs/adr/ADR-001-EMBODIMENT_MODEL.md`](./ADR-001-EMBODIMENT_MODEL.md)
- Relationship Boundaries: [`docs/adr/ADR-009-RELATIONSHIP_BOUNDARIES.md`](./ADR-009-RELATIONSHIP_BOUNDARIES.md)
- Design Philosophy: [`docs/ref/REF-032-DESIGN_PHILOSOPHY.md`](../ref/REF-032-DESIGN_PHILOSOPHY.md)
- Character Constitution: [`characters/{name}/core.yaml`](../../characters/)
