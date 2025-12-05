# Product Requirements Documents (PRDs)

**Purpose:** Define *what* we're building and *why* from a user/product perspective.

PRDs focus on:
- User problems being solved
- Feature requirements and acceptance criteria
- User experience flows
- Success metrics
- Non-functional requirements (performance, privacy, etc.)

---

## Document Index

| Document | Status | Description |
|----------|--------|-------------|
| [PRD-001: Trust & Evolution System](./PRD-001-TRUST_EVOLUTION.md) | ✅ Implemented | Dynamic relationship development with users |
| [PRD-002: Privacy & Data Handling](./PRD-002-PRIVACY.md) | ✅ Implemented | How user data is stored, segmented, and protected |
| [PRD-003: Character Experience](./PRD-003-CHARACTER_EXPERIENCE.md) | ✅ Implemented | Dreams, diaries, artifacts, and character depth |
| [PRD-004: Multi-Modal Perception](./PRD-004-MULTI_MODAL.md) | 🔄 Partial | Vision, voice, and multi-sensory interactions |
| [PRD-005: Autonomous Agency](./PRD-005-AUTONOMOUS_AGENCY.md) | ✅ Implemented | Lurking, reacting, and autonomous posting |
| [PRD-006: Knowledge Graph Evolution](./PRD-006-KNOWLEDGE_GRAPH_EVOLUTION.md) | ✅ Implemented | Enrichment, temporal graph, and user transparency |
| [PRD-007: System Scalability](./PRD-007-SYSTEM_SCALABILITY.md) | ✅ Implemented | Advanced queues, metrics, and observability |

---

## PRD Format

Each PRD follows this structure:

```markdown
# PRD-XXX: Feature Name

**Status:** 📋 Proposed | 🔄 In Progress | ✅ Implemented
**Owner:** [who owns this]
**Created:** [date]
**Updated:** [date]

## Origin

> **How did this need emerge?** Document the provenance—user requests, AI insights, or observed patterns.

| Field | Value |
|-------|-------|
| **Origin** | [e.g., "User feedback", "Support tickets", "AI collaboration", "Analytics insight"] |
| **Proposed by** | [e.g., "Mark", "Claude (collaborative)", "User community"] |
| **Catalyst** | [What surfaced the need? e.g., "Repeated user confusion about X"] |

## Problem Statement
What user problem are we solving?

## User Stories
- As a [user type], I want [goal] so that [benefit]

## Requirements
### Must Have (P0)
### Should Have (P1)
### Nice to Have (P2)

## User Experience
How does the user interact with this?

## Success Metrics
How do we measure success?

## Privacy & Safety
What are the privacy/safety implications?

## Dependencies
What needs to exist first?

## Open Questions
What's still undecided?
```

---

## Relationship to Other Docs

| Doc Type | Purpose | Location |
|----------|---------|----------|
| **PRD** | What & Why (user perspective) | `docs/prd/` |
| **ADR** | Why we chose X (technical decisions) | `docs/adr/` |
| **Spec** | How to build it (implementation details) | `docs/roadmaps/` |
| **Architecture** | How it works (system design) | `docs/architecture/` |
| **Features** | How to use it (user guides) | `docs/features/` |
