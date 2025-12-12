# WhisperEngine v2.5 Release Notes

**Release Date:** December 11, 2025  
**Version:** 2.5.0  
**Codename:** "The Synapse"

---

## 🧠 The Synapse: Graph Memory Unification

Version 2.5 introduces **The Synapse** — a dual-write architecture that unifies our previously separate Vector Database (Qdrant) and Knowledge Graph (Neo4j) into a single holographic memory system.

### What Changed?

**Before v2.5:**
- Vector search (Qdrant) returned isolated memory snippets
- Graph search (Neo4j) required knowing exact keywords
- Memory and facts lived in separate silos

**After v2.5 (The Synapse):**
- Every memory saved to Qdrant is also a node in the graph
- Vector search finds *meaning*, graph traversal finds *structure*
- A single memory point is an "address" to a complex web of associations

### Technical Architecture

#### Dual-Write Pattern
When a conversation message is saved:
1. **Qdrant**: Vector embedding stored with `vector_id`
2. **Neo4j**: `(:Memory)` node created with same `id`
3. **Link**: `(:User)-[:HAS_MEMORY]->(:Memory)` relationship

#### Vector-First Traversal
When retrieving context for a response:
1. **Vector Search**: Find semantically relevant memories (e.g., "coffee")
2. **Graph Traversal**: Expand each memory to find connected facts/entities
3. **Holographic Recall**: Return both the memory AND its neighborhood

**Example:**
```
User: "Remember when we talked about coffee?"

Vector Search finds: [Memory: "We discussed coffee shops"]
Graph Traversal expands: 
  - Memory → User → Facts → ["LIKES: Sarah", "LOCATION: Central Park"]
  
Bot now knows: "We talked about coffee at that shop near Central Park, 
and Sarah was there."
```

### Implementation Details

**Files Changed:**
- `src_v2/memory/manager.py`: Added dual-write to Neo4j
- `src_v2/knowledge/manager.py`: Added `get_memory_neighborhood()` method
- `src_v2/agents/master_graph.py`: Added Synapse context injection

**Database Schema:**
```cypher
CREATE CONSTRAINT memory_id_unique 
  FOR (m:Memory) REQUIRE m.id IS UNIQUE

(:Memory {
  id: "vector_id",
  content: "message text",
  timestamp: "ISO8601",
  source_type: "human_direct" | "inference",
  bot_name: "character_name"
})

(:User)-[:HAS_MEMORY]->(:Memory)
```

### Configuration

**No Feature Flags Required**: The Synapse is architectural — always active.

**Related Flags** (ensure these are enabled for full functionality):
```bash
ENABLE_RUNTIME_FACT_EXTRACTION=true   # Extract facts to Neo4j
ENABLE_AMBIENT_GRAPH_RETRIEVAL=true   # Inject 1-hop graph context
ENABLE_GRAPH_ENRICHMENT=true          # Proactive edge creation
```

### Performance Impact

- **Latency**: +10-20ms per message (dual-write overhead)
- **Memory Retrieval**: 1.5-2x richer context (graph neighborhood included)
- **Storage**: Minimal (Neo4j nodes are lightweight, ~100 bytes each)

### Verification

**Test the Synapse:**
```bash
# Run integration test
python tests_v2/test_synapse_dual_write.py

# Check logs for Synapse activity
./bot.sh logs elena | grep -i "synapse\|neighborhood"

# Query Neo4j directly
MATCH (m:Memory)<-[:HAS_MEMORY]-(u:User)
RETURN count(m) as memory_count, u.id
LIMIT 10
```

**Expected Log Output:**
```
Retrieved 8 Synapse connections for 5 memories
```

### Migration Notes

**Existing Deployments:**
- **No migration required** — dual-write starts immediately on upgrade
- **Existing memories**: Remain vector-only (new memories get graph nodes)
- **Backfill** (optional): Run `scripts/backfill_synapse.py` to create graph nodes for historical memories

### Research Implications

The Synapse enables new research questions:
- Can associations emerge from retrieval patterns alone?
- Do characters develop "conceptual neighborhoods" over time?
- How does graph structure influence personality coherence?

See `docs/spec/SPEC-E35-THE_SYNAPSE_GRAPH_UNIFICATION.md` for full technical specification.

---

## 🔧 Other Changes

### Worker Compatibility
- Fixed `dream_tasks.py` to use new `get_dream_graph()` factory
- All background workers verified compatible with Synapse architecture

### Documentation Updates
- Updated `IMPLEMENTATION_ROADMAP_OVERVIEW.md` with v2.5 status
- Updated `.github/copilot-instructions.md` with Synapse architecture
- Bumped `VERSION` to 2.5.0

---

## 🚀 Upgrade Instructions

### For Existing Installations

1. **Pull Latest Code:**
   ```bash
   git checkout feat/v2.5-synapse
   git pull origin feat/v2.5-synapse
   ```

2. **Restart Services:**
   ```bash
   ./bot.sh restart workers
   ./bot.sh restart bots
   ```

3. **Verify Synapse Activity:**
   ```bash
   ./bot.sh logs elena | grep -i synapse
   ```

4. **Test Memory Retrieval:**
   Chat with a bot and ask: "What do we have in common?" or "Remember when we talked about X?"

### For New Installations

No special steps — follow standard setup in `README.md`.

---

## 📊 Stats

- **Lines Changed:** ~150
- **New Tests:** 1 integration test
- **Breaking Changes:** None
- **Migration Required:** No

---

## 🙏 Acknowledgments

The Synapse concept emerged from observing how human memory works — we don't retrieve isolated facts, we retrieve *neighborhoods* of related concepts. This release is a step toward more holistic, associative AI memory.

---

## 🐛 Known Issues

None at this time.

---

## 📝 Next Steps

See `docs/roadmaps/ROADMAP_V2.5_EVOLUTION.md` for the full v2.5 evolution path:
- **Phase 2**: Temporal Graph (time-aware traversal)
- **Phase 3**: Multi-Character Walks (cross-bot perspectives)
- **Phase 4**: The Stream (real-time nervous system)

---

**Full Changelog:** https://github.com/whisperengine-ai/whisperengine-v2/compare/v2.2.1...v2.5.0
