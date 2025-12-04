# ADR-007: Dual-Layer Provenance (Searchable Content, Poetic Footer)

**Status:** ✅ Accepted
**Date:** December 3, 2025
**Deciders:** Mark, Claude (collaborative)

## Origin

| Field | Value |
|-------|-------|
| **Origin** | UX review during diary/dream enrichment |
| **Proposed by** | Mark (questioned UX), Claude (proposed solution) |
| **Catalyst** | Elena couldn't search diaries for specific people because names were anonymized; when we added explicit names to the footer, it felt "like a bibliography" |
| **Key insight** | Searchability and aesthetics have different requirements—separate them |

## Context

Diaries and dreams are generated from the bot's memories, observations, and cross-bot gossip. Originally:
- **Problem 1:** Names were anonymized ("3 different people") → bot couldn't search "What did I dream about Mark?"
- **Problem 2:** When we added explicit names to the provenance footer ("memories with Mark, Sarah, Jake"), it felt clinical and report-like, breaking the dreamlike aesthetic

We needed both:
1. **Searchability** – Bot can find diaries/dreams by person name
2. **Aesthetics** – Public footer feels authentic, not like a citation list

## Decision

**Separate the layers:**

| Layer | Content | Style | Purpose |
|-------|---------|-------|---------|
| **LLM Input** | Explicit names | "With Mark: discussed guitars" | LLM knows who to write about |
| **Artifact Content** | Names in narrative | "Mark mentioned learning guitar..." | Searchable via memory system |
| **Display Footer** | Poetic phrases | "echoes of today's conversations" | Aesthetic presentation |

**Footer vocabulary:**

| Source Type | Diary | Dream |
|-------------|-------|-------|
| Conversations/Memories | "echoes of today's conversations" | "traces of the day" |
| Observations | "fragments overheard" | "things half-noticed" |
| Cross-Bot Gossip | "whispers between friends" | "murmurs from elsewhere" |
| Epiphanies/Facts | "quiet realizations" | "what was known" |

## Consequences

### Positive
- ✅ Bot can search "What did I dream about Mark?" and find it in the narrative
- ✅ Public presentation maintains dreamlike/diary aesthetic
- ✅ No new storage schema—content is naturally searchable
- ✅ Aligns with emergence philosophy: meaning is in the content, not metadata

### Negative
- ⚠️ Footer provides less transparency about specific sources
- ⚠️ Users can't easily see which specific conversations inspired the dream
- ⚠️ Debugging requires reading the content, not just the footer

### Neutral
- The explicit footer style remains supported via configuration (for communities preferring transparency)

## Alternatives Considered

### 1. Explicit Everywhere
- **Footer:** "memories with Mark, Sarah, Jake"
- **Rejected:** Feels like a bibliography, breaks immersion

### 2. Vague Everywhere (Original)
- **Footer:** "whispers of the day"
- **Content:** "talked to someone about something"
- **Rejected:** Bot can't search for specific people

### 3. Separate Provenance Storage
- Store explicit provenance in separate field, query it directly
- **Rejected:** Over-engineering; content is already searchable

## Implementation

Files modified:
- `src_v2/workers/tasks/diary_tasks.py` – Poetic provenance for diaries
- `src_v2/workers/tasks/dream_tasks.py` – Poetic provenance for dreams
- `src_v2/memory/manager.py` – Returns `user_name` for LLM context
- `src_v2/memory/dreams.py` – Includes names in dream prompt text

See: `docs/spec/SPEC-E09-ARTIFACT_PROVENANCE.md` for full specification.

## Related ADRs

- [ADR-003: Emergence Philosophy](./ADR-003-EMERGENCE_PHILOSOPHY.md) – "meaning in behavior, not labels"
- [ADR-001: Embodiment Model](./ADR-001-EMBODIMENT_MODEL.md) – characters maintain authentic presentation
