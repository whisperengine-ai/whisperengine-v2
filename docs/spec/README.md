# Technical Specifications (SPEC)

**Purpose:** Detailed implementation specifications for features and systems. These are the "how to build it" documents that guide development.

---

## Document Index

### Complete Specifications

| SPEC | Phase | Name | Status | Description |
|------|-------|------|--------|-------------|
| [SPEC-E01](./SPEC-E01-CONVERSATION_THREADING.md) | E1 | Conversation Threading | ✅ Complete | Multi-turn conversation context |
| [SPEC-E02](./SPEC-E02-ADVANCED_MEMORY_RETRIEVAL.md) | E2 | Advanced Memory Retrieval | ✅ Complete | Hybrid memory search |
| [SPEC-E03](./SPEC-E03-USER_IDENTIFICATION.md) | E3 | User Identification | ✅ Complete | Display name storage |
| [SPEC-E04](./SPEC-E04-RELATIONSHIP_MILESTONES.md) | E4 | Relationship Milestones | ✅ Complete | Trust level transitions |
| SPEC-E05 | E5 | Scheduled Reminders | 🗄️ Removed | User reminder system (Removed Dec 2025) |
| [SPEC-E06](./SPEC-E06-CHARACTER_TO_CHARACTER.md) | E6 | Character-to-Character | ✅ Complete | Cross-bot conversations |
| [SPEC-E06B](./SPEC-E06B-CROSS_BOT_MEMORY.md) | E6B | Cross-Bot Memory | ✅ Complete | Shared memory artifacts |
| [SPEC-E07](./SPEC-E07-USER_TIMEZONE_SUPPORT.md) | E7 | User Timezone Support | ✅ Complete | Timezone-aware scheduling |
| [SPEC-E08](./SPEC-E08-IMAGE_GENERATION.md) | E8 | Image Generation | ✅ Complete | Flux Pro integration |
| [SPEC-E09](./SPEC-E09-ARTIFACT_PROVENANCE.md) | E9 | Artifact Provenance | ✅ Complete | Source attribution |
| [SPEC-E10](./SPEC-E10-TRIGGERED_VOICE_RESPONSES.md) | E10 | Triggered Voice Responses | ✅ Complete | ElevenLabs TTS |
| [SPEC-E11](./SPEC-E11-DISCORD_SEARCH_TOOLS.md) | E11 | Discord Search Tools | ✅ Complete | Channel/message search |
| [SPEC-E12](./SPEC-E12-INSIGHT_AGENT.md) | E12 | Insight Agent | ✅ Complete | Pattern detection |
| [SPEC-E13](./SPEC-E13-STIGMERGIC_ARTIFACTS.md) | E13 | Stigmergic Artifacts | ✅ Complete | Cross-bot discovery |
| [SPEC-E14](./SPEC-E14-WEB_SEARCH_TOOL.md) | E14 | Web Search Tool | ✅ Complete | DuckDuckGo integration |
| [SPEC-E15](./SPEC-E15-AUTONOMOUS_SERVER_ACTIVITY.md) | E15 | Autonomous Server Activity | ✅ Complete | Bot-initiated engagement |
| [SPEC-E16](./SPEC-E16-FEEDBACK_LOOP_STABILITY.md) | E16 | Feedback Loop Stability | ✅ Complete | Personality drift observation |
| [SPEC-E17](./SPEC-E17-SUPERGRAPH_ARCHITECTURE.md) | E17 | Supergraph Architecture | ✅ Complete | LangGraph orchestration |
| [SPEC-E18](./SPEC-E18-AGENTIC_QUEUE_SYSTEM.md) | E18 | Agentic Queue System | ✅ Complete | Background task processing |
| [SPEC-E19](./SPEC-E19-GRAPH_WALKER_AGENT.md) | E19 | Graph Walker Agent | ✅ Complete | Dynamic graph exploration |
| [SPEC-E22](./SPEC-E22-ABSENCE_TRACKING.md) | E22 | Absence Tracking | ✅ Complete | Memory decay patterns |
| [SPEC-E25](./SPEC-E25-GRAPH_WALKER_EXTENSIONS.md) | E25-29 | Graph Walker Extensions | ✅ Complete | Enrichment, temporal, user-facing |
| [SPEC-E31](./SPEC-E31-DAILY_LIFE_GRAPH.md) | E31 | Daily Life Graph | 📋 Proposed | Stigmergic autonomous rhythm |
| [SPEC-E34](./SPEC-E34-THE_DREAM_ACTIVE_IDLE.md) | E34 | The Dream (Active Idle) | 📋 Proposed | Background memory consolidation |
| [SPEC-E35](./SPEC-E35-THE_SYNAPSE_GRAPH_UNIFICATION.md) | E35 | The Synapse (Graph Unification) | ✅ Complete | Dual-write & Vector-First Traversal |
| [SPEC-E36](./SPEC-E36-THE_STREAM_REALTIME_NERVOUS_SYSTEM.md) | E36 | The Stream (Real-time) | 📋 Proposed | Hybrid event-driven autonomy |
| [SPEC-E37](./SPEC-E37-THE_SOUL_SELF_EDITING_IDENTITY.md) | E37 | The Soul (Self-Editing) | 📋 Proposed | Dynamic character evolution |
| [SPEC-F01](./SPEC-F01-EMERGENT_UNIVERSE.md) | F1 | Emergent Universe | 📋 Future | Multi-bot ecosystem |
| [SPEC-B05](./SPEC-B05-TRACE_LEARNING.md) | B5 | Trace Learning | ✅ Complete | Few-shot injection |
| [SPEC-C02](./SPEC-C02-CHANNEL_LURKING.md) | C2 | Channel Lurking | ✅ Complete | Passive engagement |
| [SPEC-S01](./SPEC-S01-CONTENT_SAFETY_REVIEW.md) | S1 | Content Safety Review | ✅ Complete | Output safety checks |
| [SPEC-S02](./SPEC-S02-CLASSIFIER_OBSERVABILITY.md) | S2 | Classifier Observability | ✅ Complete | Classification metrics |
| [SPEC-S03](./SPEC-S03-LLM_SENSITIVITY_DETECTION.md) | S3 | LLM Sensitivity Detection | ✅ Complete | Universe event filtering |
| [SPEC-S04](./SPEC-S04-PROACTIVE_TIMEZONE_AWARENESS.md) | S4 | Proactive Timezone Awareness | ✅ Complete | Time-aware messages |
| [SPEC-S05](./SPEC-S05-MANIPULATION_TIMEOUT.md) | S5 | Manipulation Timeout | ✅ Complete | Jailbreak protection |
| [SPEC-S06](./SPEC-S06-SHORT_SESSION_PROCESSING.md) | S6 | Session Timeout Processing | 📋 Proposed | Cron-based stale session processing |
| [SPEC-S07](./SPEC-S07-REDIS_TTL_REMINDERS.md) | S7 | Redis TTL Reminders | 📋 Proposed | Precise reminder delivery |

### Deferred/Future Specifications

| SPEC | Phase | Name | Status | Reason |
|------|-------|------|--------|--------|
| [SPEC-E21](./SPEC-E21-PURPOSE_DRIVEN_EMERGENCE.md) | E21 | Semantic Routing | 🗄️ Deferred | Premature optimization |
| [SPEC-E26](./SPEC-E26-DRIVE_WEIGHT_SEMANTICS.md) | E26 | Drive Weight Semantics | 📋 Future | Natural language drives |
| [SPEC-B06](./SPEC-B06-RESPONSE_PATTERN_LEARNING.md) | B6 | Response Pattern Learning | 📋 Future | Style adaptation |
| [SPEC-F01](./SPEC-F01-EMERGENT_UNIVERSE.md) | F1 | Emergent Universe | 📋 Future | Multi-bot ecosystem |
| [SPEC-F02](./SPEC-F02-FEDERATED_MULTIVERSE.md) | F2 | Federated Multiverse | 📋 Future | Cross-server federation |

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
