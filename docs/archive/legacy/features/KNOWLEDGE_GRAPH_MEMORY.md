# Knowledge Graph Memory & Proactive Connection

**Status**: ✅ Implemented & Verified  
**Version**: 2.2  
**Last Updated**: December 1, 2025

## Multi-Modal Context: The Semantic Web of Memory

The Knowledge Graph is part of the **Memory modality** (🧠) - specifically the **semantic memory** component. While vector search provides fuzzy episodic recall ("we talked about this"), the graph provides precise factual knowledge ("your dog is named Luna").

| Memory Type | Implementation | Human Analog |
|-------------|----------------|---------------|
| Episodic | Qdrant vectors + PostgreSQL history | "I remember that conversation" |
| Semantic | Neo4j graph + Qdrant summaries | "I know this fact about you" |

**Note:** These are cognitive *types* of memory, not strict database mappings. PostgreSQL stores verbatim chat history (raw episodic record), Qdrant stores searchable vectorized memories (both types), and Neo4j stores extracted facts (semantic). See [GRAPH_SYSTEMS_DESIGN.md](../architecture/GRAPH_SYSTEMS_DESIGN.md) for details.

The Knowledge Graph also forms the foundation for the **Universe modality** (🌌) - social relationships are stored as graph edges, enabling characters to understand their social context.

For full philosophy: See [`../architecture/MULTI_MODAL_PERCEPTION.md`](../architecture/MULTI_MODAL_PERCEPTION.md)

---

This feature offloads static character background data (facts, history, preferences) from the system prompt into a Neo4j Knowledge Graph. It enables the bot to "remember" deep details without bloating the context window and allows for proactive "Common Ground" detection with users.

---

## 🏗️ Architecture

### 1. Data Ingestion (YAML → Neo4j)
Character backgrounds are defined in `characters/<name>/background.yaml`.

- **Source**: `characters/<name>/background.yaml`
- **Automatic Ingestion**: The `KnowledgeManager` automatically checks for and ingests this file on bot startup.
- **Manual Script**: `scripts/ingest_character_facts.py` (optional, for manual updates without restart).
- **Storage**: Neo4j `(:Character)` nodes linked to `(:Entity)` nodes via `[:FACT]` relationships.

### 2. Dual-Mode Retrieval

The system retrieves this information in two ways:

#### A. Reactive (Reflective Agent)
When a user asks a specific question (e.g., *"Do you have any scars?"*), the **Reflective Agent** uses the `lookup_user_facts` tool.
- **Tool**: `LookupFactsTool`
- **Logic**: The tool now searches **BOTH** User and Character nodes simultaneously if the query is ambiguous (e.g., "pinky callus").
- **Cypher**:
  ```cypher
  MATCH (n)-[r:FACT]->(o:Entity)
  WHERE ((n:User AND n.id = $user_id) OR (n:Character AND n.name = $bot_name))
  AND ...
  RETURN ...
  ```

#### B. Proactive (Common Ground)
At the start of a conversation turn, the **Agent Engine** proactively scans for shared interests.
- **Trigger**: Every message (if `ENABLE_PROACTIVE_MESSAGING` or similar flags allow).
- **Logic**: Finds entities connected to both the User and the Bot (1-hop) or shared categories (2-hop).
- **Injection**: If a strong connection is found, it is injected into the system prompt:
  ```text
  [COMMON GROUND DETECTED]
  You both connect to 'Lo-fi hip hop' (User: LISTENS_TO, You: LISTENS_TO).
  Mention this naturally if relevant.
  ```

---

## 🛠️ Implementation Details

### Key Components

| Component | File | Description |
|-----------|------|-------------|
| **Ingestion Script** | `scripts/ingest_character_facts.py` | ETL pipeline for `background.yaml`. |
| **Knowledge Manager** | `src_v2/knowledge/manager.py` | Updated `query_graph` to handle ambiguous targets and `find_common_ground` for proactive search. |
| **Memory Tools** | `src_v2/tools/memory_tools.py` | `LookupFactsTool` now accepts `bot_name` and queries the graph. |
| **Agent Engine** | `src_v2/agents/engine.py` | Injects `[COMMON GROUND]` and `[RELEVANT BACKGROUND]` context. |
| **Reflective Agent** | `src_v2/agents/reflective.py` | Uses tools to answer deep background questions. |

### Data Schema (`background.yaml`)

```yaml
facts:
  - predicate: "HAS_PHYSICAL_TRAIT"
    object: "Callus on right pinky"
  - predicate: "GREW_UP_IN"
    object: "Seattle"
```

---

## 🧪 Verification

The feature has been verified using `tests_v2/test_background_integration.py`.

### Test Coverage
1.  **Common Ground**: Verified detection of shared interests (User & Bot both linked to same Entity).
2.  **Background Relevance**: Verified context injection when user input matches bot background keywords.
3.  **Reflective Lookup**: Verified the agent can "think" to look up its own background to answer questions.

### Known Issues & Fixes
- **Ambiguous Queries**: Fixed by updating Cypher generation to search `(:User) OR (:Character)` when the target is unclear.
- **Reflective Loops**: Fixed by implementing stop sequences (`Observation:`) to prevent the LLM from hallucinating tool outputs.

---

## 🚀 Usage

### Adding New Facts
1.  Edit `characters/<bot_name>/background.yaml`.
2.  **Option A (Automatic)**: Restart the bot. The new facts will be ingested automatically.
3.  **Option B (Manual)**: Run the ingestion script to update without restarting:
    ```bash
    # For a specific bot (e.g., ryan)
    DISCORD_BOT_NAME=ryan python scripts/ingest_character_facts.py
    ```

### Debugging
Use the test script to verify graph state:
```bash
NEO4J_URL=bolt://localhost:7687 DISCORD_BOT_NAME=ryan .venv/bin/python tests_v2/test_background_integration.py
```
