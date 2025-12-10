# SPEC-E31: Daily Life Graph (Remote Brain Architecture)

**Document Version:** 3.0  
**Created:** December 9, 2025  
**Updated:** December 10, 2025  
**Status:** ✅ Implemented  
**Priority:** 🟢 High  
**Dependencies:** LangGraph infrastructure, arq workers, Discord.py, existing datastores

> ✅ **Emergence Check:** Like ants following pheromone trails, the bot senses its environment and decides what to do. No central scheduler—the environment IS the task list. The character "notices" what needs doing by querying its own history.

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Architecture review / Complexity reduction / Stigmergy inspiration |
| **Proposed by** | Mark Castillo + Claude (collaborative) |
| **Catalyst** | Discussion about simplifying bot-to-bot coordination evolved into unified daily life vision |
| **Key insight** | Bots should have a coherent "daily life" instead of disconnected cron jobs. Like stigmergic agents, they sense the environment and respond to signals. |
| **Decision factors** | Current system has scattered cron jobs, complex Redis locking, no unified life cycle. This consolidates everything into one emergent loop. |
| **Revision v3** | Moved to "Remote Brain" architecture to prevent blocking the bot's event loop with heavy embedding/LLM tasks. |

---

## Executive Summary

Replace the current fragmented autonomous activity system with a **unified Daily Life Graph** that runs in a background worker ("Remote Brain").

The Bot ("Body") periodically snapshots its environment and sends it to the Worker ("Brain"). The Brain decides what to do and sends commands back to the Body.

**Key Principle:** The environment IS the task list. The bot queries its own history and the world around it to discover what needs doing. Stigmergic, not scheduled.

---

## Problem Statement

### Current State

The current autonomous activity system is complex and fragile:

| Component | Purpose | Problems |
|-----------|---------|----------|
| `ActivityOrchestrator` | Timer-based activity triggering | Multiple loops, probability tuning, coordination issues |
| `CrossBotManager` | Redis locks for bot-to-bot turn-taking | Lua scripts, race conditions, complex state machine |
| `ReactionAgent` | Probability-based reaction decisions | Hardcoded rates, no social context awareness |
| `ConversationAgent` | Topic matching for bot-to-bot | Separate from reaction/posting logic |
| `LurkDetector` | Background channel monitoring | Always-on, separate from other agents |
| `on_message` handlers | Event-driven bot-to-bot responses | Race conditions with multiple bots |

**Problems:**
1. **Distributed complexity** - Logic scattered across 10+ files
2. **Redis coordination overhead** - Lua scripts, locks, chain tracking
3. **Probability tuning** - Hardcoded rates don't adapt to context
4. **Race conditions** - Multiple bots responding to same trigger
5. **No unified reasoning** - Each component makes isolated decisions
6. **Blocking Operations** - Running embeddings/LLMs in the bot process freezes the event loop

### Desired State

**Remote Brain Architecture:**

```
Bot (Body) → Snapshot Environment → Redis Queue → Worker (Brain)
                                                      ↓
                                                  Compute Embeddings
                                                  Run Graph (LLM)
                                                  Decide Actions
                                                      ↓
Bot (Body) ← Poll Pending Actions ← Redis Queue ← Dispatch Actions
```

---

## Architecture Overview

The Daily Life Graph handles the bot's autonomous rhythm - specifically social engagement. Internal life (diaries, dreams) remains on reliable cron jobs to ensure consistency, while social behavior is emergent.

### The "Remote Brain" Pattern

We separate the **Body** (Bot Process) from the **Brain** (Worker Process).

#### 1. The Body (Bot Process) - "Senses & Hands"
The bot is dumb but fast. It lives on the Discord Gateway thread.
*   **Role:** I/O only. No thinking. No embeddings.
*   **The "Pulse":** Every ~7 minutes (randomized), the bot "looks around."
    *   **Sense:** Fetches last 50 messages from watched channels.
    *   **Snapshot:** Packages this text data into a JSON object (the "Sensory Input").
    *   **Dispatch:** Pushes a job `process_daily_life` to the Worker queue.
*   **The "Reflex":** It listens to a `pending_actions:{bot_name}` queue.
    *   **Act:** If it sees a "Reply" command, it executes `channel.send()`.

#### 2. The Brain (Worker Process) - "Cognition"
The worker is smart but slow. It lives in the background.
*   **Role:** Heavy lifting. Embeddings, LLM, Database.
*   **Process:**
    1.  **Receive Snapshot:** Gets the JSON from the bot.
    2.  **Perceive:** Runs the **Embeddings** (CPU heavy) on the snapshot text to find relevance.
    3.  **Recall:** Checks Postgres/Neo4j for relationship states.
    4.  **Decide:** Runs the `DailyLifeGraph` (LLM).
    5.  **Output:**
        *   *Social Action (Reply/Post):* Generates the response text (LLM) and pushes a command to `pending_actions:{bot_name}`.

### Why this preserves the Philosophy
The "Stigmergic" philosophy (ants following trails) is about **decisions being driven by the environment**, not about *where* the code runs.

*   **Old Way:** The ant (Bot) stops moving to think for 10 seconds.
*   **New Way:** The ant takes a picture of the trail, sends it to the cloud, keeps walking, and 5 seconds later gets a signal: "Turn left."

The bot still "notices" the environment. It just processes that notice asynchronously.

---

## Data Structures

### Sensory Snapshot (Bot -> Worker)

```python
class SensorySnapshot(BaseModel):
    """Raw text data from Discord environment."""
    bot_name: str
    timestamp: datetime
    channels: List[ChannelSnapshot]
    mentions: List[MessageSnapshot]

class ChannelSnapshot(BaseModel):
    channel_id: str
    channel_name: str
    messages: List[MessageSnapshot]  # Last 50 messages

class MessageSnapshot(BaseModel):
    id: str
    content: str
    author_id: str
    author_name: str
    is_bot: bool
    created_at: datetime
    mentions_bot: bool
    reference_id: Optional[str]
```

### Action Command (Worker -> Bot)

```python
class ActionCommand(BaseModel):
    """Command for the bot to execute."""
    action_type: Literal["reply", "react", "post", "reach_out"]
    channel_id: str
    target_message_id: Optional[str]
    content: Optional[str]  # The text to send
    emoji: Optional[str]
```

---

## Graph Nodes (Worker Side)

### 1. Perceive Node (Embeddings)

Takes the `SensorySnapshot` and computes embeddings to find relevant content.
*   **Input:** Raw text messages.
*   **Process:** FastEmbed (local) to score relevance against character interests.
*   **Output:** `ScoredMessage` list.

### 2. Plan Node (LLM)

Decides *what* to do based on relevant content.
*   **Input:** Scored messages, relationship state.
*   **Process:** LLM reasoning (Router model).
*   **Output:** List of `PlannedAction` (intent only).

### 3. Execute Node (LLM)

Generates the actual content for the actions.
*   **Input:** Planned actions.
*   **Process:** `AgentEngine` or `PostingAgent` to generate text.
*   **Output:** `ActionCommand` list (ready to send).

---

## Bot Implementation Details

### Scheduler (`DailyLifeScheduler`)

Runs in the bot process.
*   **Interval:** Every ~7 minutes (randomized).
*   **Task:**
    1.  `channel.history(limit=50)` for all watched channels.
    2.  Construct `SensorySnapshot`.
    3.  `task_queue.enqueue("process_daily_life", snapshot=snapshot.dict())`.

### Action Poller (`ActionPoller`)

Runs in the bot process.
*   **Interval:** Every 10 seconds.
*   **Task:**
    1.  Pop from Redis list `pending_actions:{bot_name}`.
    2.  Execute action (send message/reaction).

---

## Migration Plan

### Phase 1: Build Remote Brain (1-2 days)
1.  Implement `SensorySnapshot` and `ActionCommand` models.
2.  Implement `DailyLifeGraph` in `src_v2/agents/daily_life/` (Worker side).
3.  Implement `process_daily_life` task in `src_v2/workers/tasks/daily_life_tasks.py`.

### Phase 2: Build Bot Integration (1 day)
1.  Implement `DailyLifeScheduler` in `src_v2/discord/`.
2.  Implement `ActionPoller` in `src_v2/discord/`.
3.  Hook into `bot.py`.

### Phase 3: Cutover (1 day)
1.  Enable new system.
2.  Disable old `ActivityOrchestrator`.
3.  Monitor for lag/blocking.

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Bot Event Loop Block Time | < 100ms |
| Daily Life Check Duration (Worker) | < 10s |
| Actions per Day | 5-15 (Emergent) |
| Redis Keys | Minimal (Queue only) |

---

## Open Questions

1.  **Latency:** How long between "Snapshot" and "Action"?
    *   *Estimate:* 5-10 seconds. Acceptable for autonomous behavior.
2.  **Stale Data:** What if the message is deleted before the bot replies?
    *   *Mitigation:* Bot checks if message exists before replying. If not, discard action.
