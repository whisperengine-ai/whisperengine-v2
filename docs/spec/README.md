# Technical Specifications (SPEC)

**Purpose:** Detailed implementation specifications for features and systems. These are the "how to build it" documents that guide development.

---

## Document Index

### Active Specifications

| SPEC | Phase | Name | Status | Description |
|------|-------|------|--------|-------------|
| [SPEC-E15](./SPEC-E15-AUTONOMOUS_SERVER_ACTIVITY.md) | E15 | Autonomous Server Activity | 🔄 In Progress | Bot-initiated server engagement |
| [SPEC-E17](./SPEC-E17-SUPERGRAPH_ARCHITECTURE.md) | E17 | Supergraph Architecture | ✅ Complete | LangGraph orchestration layer |
| [SPEC-E18](./SPEC-E18-AGENTIC_QUEUE_SYSTEM.md) | E18 | Agentic Queue System | ✅ Complete | Background task processing |
| [SPEC-E19](./SPEC-E19-GRAPH_WALKER_AGENT.md) | E19 | Graph Walker Agent | ✅ Complete | Dynamic graph exploration |
| [SPEC-E16](./SPEC-E16-FEEDBACK_LOOP_STABILITY.md) | E16 | Feedback Loop Stability | ✅ Complete | Emergent behavior guardrails |
| [SPEC-E21](./SPEC-E21-SEMANTIC_ROUTING.md) | E21 | Semantic Routing | 📋 Proposed | Fast-path intent detection |
| [SPEC-E25](./SPEC-E25-GRAPH_WALKER_EXTENSIONS.md) | E25-29 | Graph Walker Extensions | 📋 Proposed | Graph enrichment, temporal, multi-char |

### Archived/On Hold

| SPEC | Phase | Name | Status | Reason |
|------|-------|------|--------|--------|
| [SPEC-A00](./archive/SPEC-A00-EMBEDDING_UPGRADE.md) | A0 | Embedding Upgrade 768D | ⏸️ On Hold | Performance concerns |
| [SPEC-A05](./archive/SPEC-A05-CHANNEL_CONTEXT.md) | A5 | Channel Context Awareness | 🗄️ Archived | Complexity vs value |

---

## SPEC Format Template

```markdown
# SPEC-Exx: Feature Name

**Document Version:** 1.0
**Created:** [date]
**Updated:** [date]
**Status:** 📋 Proposed | 🔄 In Progress | ✅ Complete | ⏸️ On Hold | 🗄️ Archived
**Priority:** 🔴 Critical | 🟢 High | 🟡 Medium | ⚪ Low
**Dependencies:** [list of dependencies]

> ✅ **Emergence Check:** [Brief statement on emergence philosophy alignment]

---

## Origin

> **How did this idea emerge?** Document the provenance of ideas—especially those from human-AI collaboration. This is itself a form of emergence worth tracking.

| Field | Value |
|-------|-------|
| **Origin** | [e.g., "User request", "Bug investigation", "Roadmap review", "Bot conversation"] |
| **Proposed by** | [e.g., "Mark", "Claude (collaborative)", "Elena observation"] |
| **Catalyst** | [What triggered the idea? e.g., "Bug fix → 'what's next?' → critical review"] |
| **Key insight** | [The core realization, e.g., "Absences are behaviors, not declarations"] |
| **Decision factors** | [Why now? e.g., "Low cost, high vision alignment, authenticity gain"] |

---

## Executive Summary
Brief overview of what this spec covers.

## Problem Statement
### Current State
What exists now, limitations.

### Desired State
What we want to achieve.

## Value Analysis
### Quantitative Benefits
| Metric | Current | Target | Improvement |
|--------|---------|--------|-------------|

### Qualitative Benefits
### Cost Analysis
### ROI Summary

## Architecture
### Design Philosophy
### System Overview (ASCII diagrams)
### Data Model / Schema

## Implementation Plan
### Phase 1: [name] (~X days)
### Phase 2: [name] (~X days)

## Configuration
```python
# Settings additions
```

## Success Metrics
| Metric | Target | Measurement |

## Risks & Mitigations
| Risk | Likelihood | Impact | Mitigation |

## References
- Related specs, ADRs, PRDs
```

---

## Relationship to Other Docs

| Doc Type | Purpose | Location |
|----------|---------|----------|
| **SPEC** | How to build it (implementation) | `docs/spec/` |
| **PRD** | What & Why (user perspective) | `docs/prd/` |
| **ADR** | Why we chose X (decisions) | `docs/adr/` |
| **REF** | How it works (system docs) | `docs/ref/` |
| **GUIDE** | How to use it (tutorials) | `docs/guide/` |
| **RUN** | How to operate it (runbooks) | `docs/run/` |

---

## Naming Convention

`SPEC-{phase}-{FEATURE_NAME}.md`

- **Phase prefix**: Matches roadmap phase (E15, E16, A00, etc.)
- **Feature name**: SCREAMING_SNAKE_CASE
- Examples:
  - `SPEC-E19-GRAPH_WALKER_AGENT.md`
  - `SPEC-A00-EMBEDDING_UPGRADE.md`
