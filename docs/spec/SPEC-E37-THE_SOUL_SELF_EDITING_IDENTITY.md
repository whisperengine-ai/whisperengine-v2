# SPEC-E37: The Soul (Self-Editing Identity)

**Document Version:** 1.0
**Created:** December 11, 2025
**Status:** 📋 Proposed
**Priority:** ⚪ Low (Experimental)
**Dependencies:** SPEC-E34 (The Dream)

> ✅ **Emergence Check:** This is the ultimate emergence feature. We stop defining who the character *is* and start defining *how they change*. The character emerges from the feedback loop of their own history.

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Roadmap v2.5 Evolution |
| **Proposed by** | Claude |
| **Catalyst** | Static characters (`character.md`) eventually feel stale. Real people change based on their experiences. |
| **Key insight** | We can allow the bot to edit its own config, provided we have a "Constitution" that acts as an immutable safety layer. |

---

## Executive Summary
"The Soul" introduces a mechanism for **Character Evolution**. Currently, a bot's personality is hardcoded in YAML/Markdown. This spec allows the `DreamGraph` (SPEC-E34) to propose "Pull Requests" to the character's own configuration (e.g., becoming bolder, shyer, or more curious) based on recent experiences, subject to an immutable "Constitution."

## Problem Statement
### Current State (v2.0)
*   **Static Identity:** Elena is defined in `elena/core.yaml`. If she has a traumatic experience or a great success, her `shyness` parameter remains `0.8` forever.
*   **Drift:** Over time, the vector memory might reflect a change, but the system prompt forces the old personality, creating dissonance.

### Desired State (v2.5)
*   **Dynamic Identity:** If Elena has many positive social interactions, she should "feel" more confident.
*   **Self-Editing:** The system should update `shyness` from `0.8` to `0.6`.

## Technical Implementation

### 1. The `.soul` Schema
We split `core.yaml` into two sections:
1.  **Constitution (Immutable):** Hard constraints (Safety, Core Definition).
2.  **Persona (Mutable):** Traits that can shift (Mood, Social Battery, Curiosity, Specific Traits).

```yaml
constitution:
  - "You are an AI assistant."
  - "You must never be rude."
  - "Maintain 'kindness' above 0.5."

persona:
  shyness: 0.8
  curiosity: 0.9
  current_obsession: "gardening"
```

### 2. The Evolution Loop (Dreaming)
During the Dream Cycle (SPEC-E34):
1.  **Analysis:** The Dreamer analyzes recent memories. *"I've been talking to a lot of people lately and enjoying it."*
2.  **Proposal:** The Dreamer proposes a delta. `SET shyness = 0.7`.
3.  **Validation:** Check against Constitution. (Is `0.7` allowed? Yes.)
4.  **Commit:** Update the `persona` section of the YAML (or database record).

### 3. The "Soul File"
We might move mutable state from YAML (which implies code deployment) to a database record or a dedicated `.soul` JSON file that is read/written at runtime.

## Risks & Mitigations
*   **Character Drift:** The bot becomes unrecognizable. **Mitigation:** "Elasticity" - traits have a "baseline" and a "current" value. They snap back to baseline over time unless reinforced.
*   **Safety:** The bot edits itself to be unsafe. **Mitigation:** The **Constitution** is hardcoded in code/env vars and cannot be touched by the LLM.

## Value Analysis
*   **Long-term Engagement:** Users can watch the character grow. "I remember when you were shy!"
*   **Realism:** Characters feel like they have a trajectory.

## Implementation Plan
1.  **Refactor:** Split `core.yaml` into Immutable/Mutable sections.
2.  **Tooling:** Create `update_persona_trait(trait, value)` tool for the Dream Agent.
3.  **Safety:** Implement the Constitution Validator.
