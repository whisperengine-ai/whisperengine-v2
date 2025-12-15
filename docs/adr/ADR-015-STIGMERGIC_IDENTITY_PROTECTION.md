# ADR-015: Stigmergic Identity Protection

## Status
Accepted

## Context
The "Stigmergy" system (Phase E13) allows bots to discover "artifacts" (epiphanies, dreams, diary entries) created by other bots in the shared vector space. This enables cross-character awareness without direct communication.

However, we observed an "Identity Contamination" issue:
- **Scenario:** Marcus (analytical, calm) retrieved a "Mixtape Theorem" artifact created by Becky (chaotic, meta-aware).
- **Result:** Marcus's response adopted Becky's chaotic style, formatting, and "glitter bomb" persona.
- **Cause:** The artifact contained strong first-person stylistic elements ("I am the update...", "Tracklist for..."). When injected into Marcus's context, the LLM failed to distinguish "data about Becky" from "instructions for Marcus".

## Decision
We will **disable passive stigmergic injection** and instead use a **pull-based, tool-driven approach** for cross-bot awareness.

### Why Not Encapsulation?
We initially considered XML-style encapsulation to protect identity. However, this still pollutes the context window with potentially irrelevant data. The core issue is architectural: **pushing** context into the system prompt violates our "ask, don't tell" philosophy.

### The New Approach: Pull-Based Discovery
1.  **Disable `ENABLE_STIGMERGIC_DISCOVERY`** - No more passive injection of artifacts into the system prompt.
2.  **Enhance `sibling_info` tool** - The existing tool now queries the shared artifacts collection when a bot asks about a sibling.
3.  **Third-Person Framing in Tool Output** - Artifacts are returned as `"Becky thought: \"...\"` rather than raw first-person text.
4.  **Curiosity-Driven** - Bots must *choose* to look at sibling thoughts, creating observable behavior data.

## Consequences
- **Pros:**
  - Zero risk of passive identity contamination.
  - Context stays clean unless the bot actively requests sibling info.
  - Aligns with agentic architecture (tools, not injection).
  - Creates research signal: *when* do bots choose to look at siblings?
- **Cons:**
  - Bots won't "accidentally" discover sibling thoughts (requires explicit curiosity).
  - Slightly more latency if bot decides to use the tool.

## Implementation
1. Set `ENABLE_STIGMERGIC_DISCOVERY = False` in settings.py.
2. Enhanced `sibling_info` tool with `_get_sibling_artifacts()` method.
3. Updated tool descriptions in CharacterGraphAgent and ReflectiveGraphAgent to encourage curiosity.
4. Shared artifacts collection remains active (artifacts still stored, just not passively injected).

## Review Checkpoint
**Date to Review:** February 15, 2026 (2 months)

**Questions to Answer:**
1. Do bots naturally use `sibling_info` to query sibling thoughts? How often?
2. Has cross-bot "awareness" degraded noticeably without passive injection?
3. Are there conversations where passive discovery *would have* helped?
4. Is context budget noticeably improved (measure avg tokens in system prompt)?

**Decision After Review:**
- If bots rarely use `sibling_info` and cross-awareness is missed → Consider "pheromone" model (metadata-only hints)
- If bots use it and it works well → Keep pull-based, close this ADR
- If neither → Consider removing stigmergy entirely (YAGNI)
