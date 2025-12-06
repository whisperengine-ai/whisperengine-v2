# Architecture Decision Records (ADRs)

**Purpose:** Document significant architectural decisions with context on *why* we chose a particular approach over alternatives.

ADRs are immutable once accepted—if we change our minds, we create a new ADR that supersedes the old one. This preserves the historical context of why decisions were made.

---

## Document Index

| ADR | Status | Decision |
|-----|--------|----------|
| [ADR-001: Embodiment Model](./ADR-001-EMBODIMENT_MODEL.md) | ✅ Accepted | Characters ARE the interface, no "AI self" behind them |
| [ADR-002: Dual Process Architecture](./ADR-002-DUAL_PROCESS.md) | ✅ Accepted | Fast Mode + Reflective Mode inspired by Kahneman's System 1/2 |
| [ADR-003: Emergence Philosophy](./ADR-003-EMERGENCE_PHILOSOPHY.md) | ✅ Accepted | "Observe first, constrain later" for emergent behavior |
| [ADR-004: Graph-First Memory](./ADR-004-GRAPH_FIRST_MEMORY.md) | ✅ Accepted | Neo4j + Qdrant hybrid over pure vector or pure relational |
| [ADR-005: LangGraph Supergraph](./ADR-005-LANGGRAPH_SUPERGRAPH.md) | ✅ Accepted | LangGraph StateGraph over manual Python orchestration |
| [ADR-006: Feature Flags for LLM Costs](./ADR-006-FEATURE_FLAGS.md) | ✅ Accepted | All expensive LLM features gated by flags |
| [ADR-007: Dual-Layer Provenance](./ADR-007-DUAL_LAYER_PROVENANCE.md) | ✅ Accepted | Searchable content + poetic footer for diaries/dreams |
| [ADR-008: Insight Job Thresholds](./ADR-008-INSIGHT_JOB_THRESHOLDS.md) | ✅ Accepted | Minimum data thresholds before triggering insight analysis |
| [ADR-009: Relationship Boundaries](./ADR-009-RELATIONSHIP_BOUNDARIES.md) | ✅ Accepted | Research-context framing for emotional dependency and attachment |
| [ADR-010: Crisis Response](./ADR-010-CRISIS_RESPONSE.md) | ✅ Accepted | Community over automation for mental health concerns |
| [ADR-011: Emergence Boundaries](./ADR-011-EMERGENCE_BOUNDARIES.md) | ✅ Accepted | When observation becomes intervention ("Interesting Until Harmful") |

---

## ADR Format (Based on Michael Nygard's Template)

```markdown
# ADR-XXX: Decision Title

**Status:** 📋 Proposed | ✅ Accepted | ❌ Deprecated | 🔄 Superseded by ADR-XXX
**Date:** [when decision was made]
**Deciders:** [who made this decision]

## Origin

> **How did this decision arise?** Document the provenance—especially for decisions emerging from human-AI collaboration.

| Field | Value |
|-------|-------|
| **Origin** | [e.g., "Production incident", "Architecture review", "AI collaboration", "User feedback"] |
| **Proposed by** | [e.g., "Mark", "Claude (collaborative)", "Elena observation"] |
| **Catalyst** | [What forced the decision? e.g., "Performance degradation under load"] |

## Context
What is the issue that we're seeing that is motivating this decision?

## Decision
What is the change that we're proposing/doing?

## Consequences
### Positive
What becomes easier or possible as a result?

### Negative
What becomes harder or impossible as a result?

### Neutral
What other effects does this have?

## Alternatives Considered
What other options did we evaluate?

| Alternative | Pros | Cons | Why Rejected |
|-------------|------|------|--------------|
| Option A | ... | ... | ... |
| Option B | ... | ... | ... |

## References
- Links to related docs, specs, discussions
```

---

## When to Write an ADR

Write an ADR when you make a decision that:
- Is hard to reverse later
- Affects multiple parts of the system
- Has long-term consequences
- Other developers will ask "why did we do it this way?"

**Examples:**
- ✅ "We're using Neo4j for the knowledge graph" (hard to change later)
- ✅ "Characters don't have a hidden 'AI self'" (philosophical foundation)
- ❌ "We renamed a variable" (trivial, reversible)
- ❌ "We fixed a bug" (no decision involved)

---

## Relationship to Other Docs

| Doc Type | Purpose | Location |
|----------|---------|----------|
| **ADR** | Why we chose X (technical decisions) | `docs/adr/` |
| **PRD** | What & Why (user perspective) | `docs/prd/` |
| **Spec** | How to build it (implementation details) | `docs/roadmaps/` |
| **Architecture** | How it works (system design) | `docs/architecture/` |
