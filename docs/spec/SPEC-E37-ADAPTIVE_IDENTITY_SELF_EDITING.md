# SPEC-E37: Adaptive Identity (Self-Editing)

**Document Version:** 1.0
**Created:** December 11, 2025
**Status:** 📋 Proposed
**Priority:** ⚪ Low (Experimental)
**Dependencies:** SPEC-E34 (Reverie)

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
"Adaptive Identity" introduces a mechanism for **Character Evolution**. Currently, a bot's personality is hardcoded in YAML/Markdown. This spec allows the `ReverieGraph` (SPEC-E34) to propose "Pull Requests" to the character's own configuration (e.g., becoming bolder, shyer, or more curious) based on recent experiences, subject to an immutable "Constitution."

## Problem Statement
### Current State (v2.0)
*   **Static Identity:** Elena is defined in `elena/core.yaml`. If she has a traumatic experience or a great success, her `shyness` parameter remains `0.8` forever.
*   **Drift:** Over time, the vector memory might reflect a change, but the system prompt forces the old personality, creating dissonance.

### Desired State (v2.5)
*   **Dynamic Identity:** If Elena has many positive social interactions, she should "feel" more confident.
*   **Self-Editing:** The system should update `shyness` from `0.8` to `0.6`.

## Technical Implementation

### 1. The Layered Identity Model
Instead of editing the YAML files directly (which requires git commits), we use a **Layered Model**:

1.  **Base Layer (Git/YAML):** The `core.yaml` defines the *Baseline Personality*. This is version-controlled and immutable at runtime.
2.  **Evolution Layer (Database):** A Postgres table stores *Trait Overrides* (diffs).
3.  **Runtime Identity:** `Effective Traits = Baseline + Overrides`.

```yaml
# core.yaml (Base Layer - Immutable)
constitution:
  - "You are an AI assistant."
  - "Maintain 'kindness' above 0.5."

persona:
  shyness: 0.8
  curiosity: 0.9
```

### 2. The Evolution Loop (Dreaming)
During the Reverie Cycle (SPEC-E34):
1.  **Analysis:** The Dreamer analyzes recent memories. *"I've been talking to a lot of people lately and enjoying it."*
2.  **Proposal:** The Dreamer proposes a delta. `SET shyness = 0.7`.
3.  **Validation:** Check against Constitution. (Is `0.7` allowed? Yes.)
4.  **Commit:** Update the `trait_overrides` in Postgres.

### 3. Persistence Strategy
We will use a Postgres table `character_evolution` to store the mutable state.

**Schema:**
```sql
CREATE TABLE character_evolution (
    character_name VARCHAR(50) PRIMARY KEY,
    trait_overrides JSONB,  -- e.g., {"shyness": 0.6, "mood": "contemplative"}
    last_updated TIMESTAMP,
    evolution_history JSONB -- Log of changes for debugging
);
```

**Loading Logic:**
On startup (or reload), `CharacterManager`:
1.  Loads `core.yaml` (Base).
2.  Fetches `trait_overrides` from DB.
3.  Merges them to create the `EffectiveCharacter` object.

## Risks & Mitigations
*   **Character Drift:** The bot becomes unrecognizable. **Mitigation:** "Elasticity" - traits have a "baseline" and a "current" value. They snap back to baseline over time unless reinforced.
*   **Safety:** The bot edits itself to be unsafe. **Mitigation:** The **Constitution** is hardcoded in code/env vars and cannot be touched by the LLM.

## Value Analysis
*   **Long-term Engagement:** Users can watch the character grow. "I remember when you were shy!"
*   **Realism:** Characters feel like they have a trajectory.

## Implementation Plan
1.  **Schema:** Create `character_evolution` table in Postgres (Alembic migration).
2.  **Refactor:** Update `CharacterManager` to load from YAML + DB (Layered Loading).
3.  **Tooling:** Create `update_persona_trait(trait, value)` tool for the Dream Agent.
4.  **Safety:** Implement the Constitution Validator.
