# Reference Documentation (REF)

**Purpose:** Authoritative documentation of how systems work. These are the "how it works" documents that explain architecture, data models, and system behavior.

---

## Document Index

### Core Systems

| REF | Name | Description |
|-----|------|-------------|
| [REF-000](./REF-000-DESIGN_OVERVIEW.md) | Design Overview | WhisperEngine v2 vision and philosophy |
| [REF-001](./REF-001-COGNITIVE_ENGINE.md) | Cognitive Engine | Brain of the system, dual-process architecture |
| [REF-002](./REF-002-GRAPH_SYSTEMS.md) | Graph Systems Design | ⭐ Unified graph architecture (START HERE) |
| [REF-003](./REF-003-MEMORY_SYSTEM.md) | Memory System | Vector + graph memory architecture |
| [REF-004](./REF-004-MESSAGE_FLOW.md) | Message Flow | Request lifecycle and processing |
| [REF-005](./REF-005-DATA_MODELS.md) | Data Models | Database schemas and structures |

### Agent Systems

| REF | Name | Description |
|-----|------|-------------|
| [REF-006](./REF-006-AGENT_GRAPH_SYSTEM.md) | Agent Graph System | LangGraph agent architecture |
| [REF-007](./REF-007-MULTI_MODAL_PERCEPTION.md) | Multi-Modal Perception | How agents perceive (vision, voice, text) |
| [REF-008](./REF-008-TRUST_EVOLUTION.md) | Trust Evolution System | Relationship progression mechanics |
| [REF-009](./REF-009-REFLECTIVE_MODE.md) | Reflective Mode | Deep-dive on System 2 reasoning |

### Integration & Infrastructure

| REF | Name | Description |
|-----|------|-------------|
| [REF-010](./REF-010-DISCORD_INTEGRATION.md) | Discord Integration | Discord as sensory interface |
| [REF-011](./REF-011-VISION_PIPELINE.md) | Vision Pipeline | Image processing architecture |
| [REF-012](./REF-012-SUMMARIZATION.md) | Summarization System | Memory consolidation |
| [REF-013](./REF-013-OBSERVABILITY.md) | Observability | Metrics, logging, monitoring |
| [REF-014](./REF-014-BOT_TO_BOT.md) | Bot-to-Bot Pipeline | Cross-bot communication |
| [REF-015](./REF-015-CHARACTER_AS_AGENT.md) | Character as Agent | Character system architecture |
| [REF-016](./REF-016-RECALL_BOT_CONVERSATION_TOOL.md) | Recall Bot Conversation Tool | Cross-bot memory recall |
| [REF-017](./REF-017-CONVERSATION_SESSIONS.md) | Conversation Sessions | Session lifecycle, summarization triggers |
| [REF-018](./REF-018-MESSAGE_STORAGE_RETRIEVAL.md) | Message Storage & Retrieval | Five databases and data flow |
| [REF-022](./REF-022-BACKGROUND_WORKERS.md) | Background Workers | Task queue, async jobs, arq |
| [REF-023](./REF-023-RATE_LIMITING.md) | Rate Limiting & Cooldowns | Throttling, daily limits, cooldowns |
| [REF-024](./REF-024-INTER_BOT_COMMUNICATION.md) | Inter-Bot Communication | Stigmergy, gossip protocol, cross-bot chat |

### API & External

| REF | Name | Description |
|-----|------|-------------|
| [REF-020](./REF-020-API_REFERENCE.md) | API Reference | REST API documentation |

---

## REF Format Template

```markdown
# REF-NNN: System Name

**Version:** X.X
**Last Updated:** [date]
**Status:** Current | Deprecated | Draft

---

## Origin

> **How did this system come to be?** Document the provenance—especially for designs emerging from human-AI collaboration.

| Field | Value |
|-------|-------|
| **Origin** | [e.g., "Architecture review", "Scaling requirement", "AI collaboration"] |
| **Proposed by** | [e.g., "Mark", "Claude (collaborative)"] |
| **Key insight** | [Core realization that shaped the design] |

## Overview
Brief description of this system's purpose and scope.

## Architecture

### System Diagram
```
[ASCII diagram of system architecture]
```

### Components
| Component | Location | Purpose |
|-----------|----------|---------|

## Data Flow
How data moves through this system.

## Key Concepts
Important terms and concepts for understanding this system.

## Configuration
Relevant settings and environment variables.

## Integration Points
How this system connects to others.

## Common Patterns
Typical usage patterns and code examples.

## Troubleshooting
Common issues and solutions.

## Related Documents
- Links to related REFs, SPECs, ADRs
```

---

## Relationship to Other Docs

| Doc Type | Purpose | Location |
|----------|---------|----------|
| **REF** | How it works (system docs) | `docs/ref/` |
| **SPEC** | How to build it (implementation) | `docs/spec/` |
| **PRD** | What & Why (user perspective) | `docs/prd/` |
| **ADR** | Why we chose X (decisions) | `docs/adr/` |
| **GUIDE** | How to use it (tutorials) | `docs/guide/` |
| **RUN** | How to operate it (runbooks) | `docs/run/` |

---

## Naming Convention

`REF-NNN-{SYSTEM_NAME}.md`

- **Number**: Sequential, grouped by category (000-099 core, 100+ specialized)
- **System name**: SCREAMING_SNAKE_CASE
- Examples:
  - `REF-001-COGNITIVE_ENGINE.md`
  - `REF-020-API_REFERENCE.md`
