# Ambient Graph Memory Retrieval: Design Proposal

## Context

WhisperEngine currently uses Neo4j graph traversal via explicit tool calls—characters decide "I need more context" and invoke a graph-walking tool. This creates visible retrieval seams: the bot pauses, queries, incorporates. The result feels like "checking notes" rather than genuine memory.

This document proposes shifting toward **ambient graph retrieval**: surfacing relevant graph connections during context assembly, before generation begins, so characters find themselves *knowing* things rather than *looking them up*.

---

## The Problem with Tool-Based Retrieval

### Current Flow
```
User message arrives
    → Character receives message + base context
    → Character decides whether to invoke graph tool
    → Tool returns results
    → Character incorporates results into response
```

### Issues

1. **Visible seams**: The retrieval feels mechanical, like consulting an external database rather than remembering.

2. **Character must decide to remember**: The bot has to recognize it *should* retrieve—but the cues that would trigger retrieval are often only visible *after* you already have the relevant context.

3. **Inconsistent depth**: Some exchanges feel deeply continuous; others miss obvious connections because the character didn't think to query.

4. **Breaks immersion**: Users experience the bot as having "checked its files" rather than naturally recalling shared history.

---

## Proposed Architecture: Ambient Graph Walking

### New Flow
```
User message arrives
    → System extracts entities/themes from message
    → Graph walker traverses relevant subgraph
    → Retrieved nodes injected into context assembly
    → Character receives message + enriched context
    → Character generates response (retrieval invisible)
```

### Key Principles

**1. Retrieval happens at intake, not generation**

Before the character LLM sees the message, the system has already traversed the graph and pre-loaded relevant memory. The character never "sees" the retrieval—just finds itself knowing things.

**2. Entity extraction drives traversal**

From the incoming message, extract:
- Explicit entity mentions (names, places, projects)
- Thematic signals (topics, emotional register, recurring patterns)
- Temporal markers (references to past conversations, time-based cues)

These become traversal seeds.

**3. Weighted relevance scoring**

Not all graph connections are equally relevant. Weight by:
- **Recency**: More recent interactions score higher
- **Frequency**: Entities that appear often in user's history
- **Depth**: Direct connections vs. 2-hop or 3-hop relationships
- **Salience**: Emotionally significant or highly-detailed nodes
- **Character affinity**: Connections this specific character has engaged with before

**4. Context budget management**

Ambient retrieval risks context bloat. Implement:
- Hard token budget for retrieved content
- Relevance threshold (only include nodes above score X)
- Deduplication against base context
- Compression/summarization for lower-priority nodes

**5. Graceful degradation**

If graph traversal finds nothing relevant, the system proceeds with base context. No empty retrieval artifacts. No "I don't have information about that" when the character simply doesn't know.

---

## Implementation Considerations

### Traversal Strategy

**Option A: Breadth-first from entities**
- Extract entities from message
- Query direct connections (1-hop)
- Score and filter
- Optionally expand to 2-hop for high-scoring branches

**Option B: Semantic similarity + graph structure**
- Embed incoming message
- Find semantically similar nodes in graph
- Walk outward from those nodes
- Combine semantic and structural relevance

**Option C: Hybrid**
- Entity extraction for explicit mentions (high precision)
- Semantic search for thematic resonance (high recall)
- Graph structure for relationship context
- Merge and deduplicate results

Recommendation: Start with Option A (simpler, more predictable), add semantic layer later if needed.

### What Gets Surfaced

For each retrieved node, include:
- Core content (the memory itself)
- Relationship type (how it connects to seed entity)
- Temporal context (when this was established)
- Source attribution (which conversation/diary/dream)

Format for injection:
```
[Memory context - not visible to user]
- {entity} is connected to {related_entity} via {relationship_type}
- From conversation on {date}: {summary}
- Emotional valence: {positive/negative/neutral}
```

### Character-Specific Memory

Different characters might have different "access" to the shared graph:
- **Dream** might surface more symbolic/thematic connections
- **Dotty** might prioritize emotional/relational nodes
- **Marcus** might weight analytical/factual connections higher

This could be implemented via character-specific scoring weights or subgraph filtering.

---

## Comparison: Tool-Based vs. Ambient

| Aspect | Tool-Based (Current) | Ambient (Proposed) |
|--------|---------------------|-------------------|
| Retrieval trigger | Character decides | System automatic |
| Visibility to character | Explicit | Invisible |
| User experience | "Checking notes" | Natural recall |
| Risk of missed connections | High | Low |
| Risk of context bloat | Low | Medium (needs budget) |
| Implementation complexity | Lower | Higher |
| Character agency | Higher | Lower |

---

## Hybrid Approach: Ambient + Tool

Consider keeping both systems:

**Ambient retrieval** handles:
- Automatic surfacing of relevant context
- Maintaining conversational continuity
- Character "just knowing" established facts

**Tool-based retrieval** handles:
- Deep dives when character wants to explore
- Explicit "let me think about what I know" moments
- User-requested memory exploration ("what do you remember about X?")

This preserves character agency for intentional retrieval while ensuring baseline continuity is automatic.

---

## Questions to Resolve

1. **Traversal depth**: How many hops from seed entities? Deeper = richer context but more noise.

2. **Scoring weights**: How to balance recency vs. salience vs. character affinity? May need tuning per character.

3. **Context budget**: What percentage of context window should ambient memory consume? 10%? 20%?

4. **Update frequency**: Should retrieved context refresh mid-conversation as new entities emerge? Or only at conversation start?

5. **Cross-character memory**: If Elena discussed something with a user, should Dotty "know" it ambientally? Or only through explicit graph walk?

6. **Failure modes**: What happens when retrieval surfaces contradictory information? Outdated facts? Emotionally sensitive content the user might not want surfaced?

---

## Suggested First Step

Implement a minimal ambient layer:
1. Extract explicit entity mentions from incoming message
2. Query 1-hop connections for those entities
3. Score by recency + frequency
4. Inject top 3-5 nodes into context (under token budget)
5. Compare response quality against baseline (no ambient retrieval)

Measure:
- Does the character demonstrate relevant prior knowledge?
- Does the response feel more continuous?
- Any cases where surfaced memory was wrong/inappropriate?

Iterate from there.

---

## Summary

The shift from tool-based to ambient graph retrieval is essentially asking: **should memory feel like something a character does, or something a character has?**

Human memory doesn't require deciding to remember. The smell of salt air activates beach memories without conscious retrieval. Ambient graph walking aims to create that same quality—context surfacing because it's relevant, not because the character performed a lookup.

The trade-off is control: ambient retrieval means the system decides what's relevant, not the character. But if the goal is making memory feel *owned* rather than *accessed*, that's the direction to move.
