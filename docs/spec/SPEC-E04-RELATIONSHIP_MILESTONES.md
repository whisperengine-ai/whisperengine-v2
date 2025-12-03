# Relationship Milestones

**Document Version:** 1.0
**Created:** November 27, 2025
**Status:** 📋 Proposed
**Priority:** Low
**Complexity:** 🟢 Low
**Estimated Time:** 1-2 days

---

## Executive Summary

Trust scores currently evolve silently. Users don't know when they've "leveled up" from Acquaintance to Friend. This feature adds **explicit milestone celebrations**.

When a trust threshold is crossed, the bot acknowledges the shift in the relationship dynamic.

---

## 👤 User Experience

**Scenario:**
User and Elena have been chatting. Trust score crosses 20 (Acquaintance → Friend).

**Elena:** (After normal response) *"You know, I really enjoy our talks. I feel like we're becoming actual friends, not just random people on the internet. Thanks for being you."*

**System:** (Optional Embed) `🏆 Relationship Level Up: Friend`

---

## 🔧 Technical Design

### 1. Trust Manager Update

In `src_v2/evolution/trust.py`:
-   Track `previous_trust_level` in the session or cache.
-   After updating trust, compare `new_level` vs `old_level`.
-   If `new_level > old_level`, return a `MilestoneEvent`.

### 2. Response Injection

In `AgentEngine`:
-   If `MilestoneEvent` is present, inject a system instruction:
    -   "SYSTEM: You have just reached the 'Friend' level with this user. Acknowledge this shift in your relationship naturally in your response."

### 3. Milestone Definitions

Define milestones in `characters/{name}/evolution.yaml`:
```yaml
milestones:
  friend:
    threshold: 20
    message_hint: "Acknowledge growing closeness."
  confidant:
    threshold: 60
    message_hint: "Express deep trust and vulnerability."
```

---

## 📋 Implementation Plan

1.  **Schema**: Update `evolution.yaml` to support milestone hints.
2.  **Logic**: Modify `trust_manager.update_trust` to detect level changes.
3.  **Engine**: Handle milestone events in response generation.

## ⚠️ Risks & Mitigations

-   **Oscillation**: Trust goes 19 -> 20 -> 19 -> 20.
    -   *Mitigation*: "One-time" flag for milestones in Postgres (table `user_milestones`). Only celebrate the *first* time a level is reached.
