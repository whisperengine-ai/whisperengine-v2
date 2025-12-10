# Code Review: Daily Life Remote Brain (feat/daily-life-remote-brain)

**Date:** December 10, 2025
**Reviewer:** GitHub Copilot
**Status:** ✅ Approved (with minor notes)

## 1. Architecture Overview

The refactor successfully decouples the "Daily Life" cognitive processes from the main Discord bot process, moving them to a shared Worker process ("Remote Brain"). This architecture solves the "Split Brain" problem by ensuring the Worker uses the exact same intelligence pipeline (`MasterGraphAgent`) as the main bot.

**Key Components:**
- **Bot (Local Body):** `DailyLifeScheduler` snapshots the environment (messages, channels) and sends it to Redis. `ActionPoller` listens for commands and executes them (send/react).
- **Worker (Remote Brain):** `DailyLifeGraph` processes snapshots, decides on actions (Reply/Post/React), and uses `MasterGraphAgent` to generate content.
- **Shared Intelligence:** `MasterGraphAgent` and `ReflectiveGraphAgent` are now multi-tenant aware, accepting `character_name` to switch contexts dynamically.

## 2. Code Analysis

### `src_v2/agents/daily_life/graph.py`
- **Logic:** The `execute` node correctly reconstructs `chat_history` from the snapshot and delegates generation to `master_graph_agent.run()`.
- **Consistency:** By using `master_graph_agent`, the worker now has access to all tools (Knowledge Graph, Web Search, Memory) that the main bot has.
- **Safety:** The lookback window was reduced to 15 minutes (in previous steps) to prevent "necromancy" (replying to ancient messages).

### `src_v2/agents/master_graph.py` & `reflective_graph.py`
- **Multi-Tenancy:** Both agents were correctly updated to accept `character_name`.
- **Tooling:** `_get_tools` now initializes tools with the correct `bot_name`, ensuring reads/writes go to the correct Qdrant collection and Neo4j nodes.
- **Trace Learning:** Correctly uses the character-specific collection for retrieving reasoning traces.

### `src_v2/discord/daily_life.py`
- **Persistence:** The `ActionPoller` now saves sent messages to both Postgres (`v2_chat_history`) and Qdrant (`whisperengine_memory_{bot}`). This is critical for maintaining a consistent narrative.
- **Error Handling:** Basic try/except blocks are in place.
- **Linting:** There are some broad `except Exception` clauses that should eventually be narrowed, but they are acceptable for a resilience-focused poller.

## 3. Data Consistency Verification

| Scenario | Data Flow | Consistency Check |
| :--- | :--- | :--- |
| **Autonomous Reply** | Worker -> Redis -> Bot -> Discord -> **Postgres/Qdrant** | ✅ Saved immediately after sending. |
| **User Reply** | User -> Bot -> **Postgres** (Context Lookup) | ✅ Bot sees its own autonomous reply in history. |
| **Summarization** | Worker -> **Postgres** (Session Query) | ✅ Summarizer sees autonomous messages in the session log. |
| **Fact Extraction** | Worker -> **Postgres** (Context) | ✅ Extractor sees autonomous messages as context. |

## 4. Recommendations

1.  **Monitoring:** Add a specific Grafana dashboard for "Autonomous Actions" to track how often bots are posting vs. replying.
2.  **Rate Limiting:** Ensure the `DailyLifeScheduler` interval (5-10 mins) doesn't overwhelm the worker if we scale to 50+ bots.
3.  **Feedback Loop:** Consider adding a "reaction watcher" to see if users like the autonomous posts (upvotes/downvotes) and feed that back into the `DailyLifeGraph` scoring.

## 5. Conclusion

The feature is architecturally sound and ready for testing. The "Remote Brain" now has full parity with the local bot's intelligence.
