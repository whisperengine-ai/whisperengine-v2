# PROP-005: Coordinated Dual Process Architecture

**Status:** Proposed  
**Date:** 2025-12-10  
**Author:** GitHub Copilot  
**Context:** Phase 1 Complete, "Daily Life" Feature Frozen

## 1. The Challenge: Uncoordinated Dual Process

WhisperEngine v2 implements **ADR-002 (Dual Process Theory)**:
*   **System 1 (Fast):** Intuitive, handled by Bot process (<2s).
*   **System 2 (Slow):** Reflective, handled by Worker process (30s+).

**The Issue:**
Currently, these two systems operate in isolation ("Split Brain").
*   **System 1** reacts to a user message immediately.
*   **System 2** (via Daily Life snapshot) sees the same message minutes later and *also* reacts, unaware that System 1 already handled it.

### 1.1 The Discord Constraint (Why we split)
This architecture is not just theoretical; it is forced by **Discord Gateway limitations** and **User Expectations**:

**Technical Constraints (Discord):**
1.  **WebSocket Heartbeats:** The bot process must maintain a persistent WebSocket connection and send heartbeats every ~40s.
2.  **Blocking = Death:** If the bot process blocks for >10s to "think" (LLM inference), the heartbeat fails, and Discord disconnects the bot ("Zombification").
3.  **The Necessity of Workers:** Therefore, **System 2 (Deep Thinking) MUST live off-process**. We cannot simply "merge" the codebases without risking connection stability.

**User Experience Constraints (Humans):**
1.  **Latency Tolerance:** Users expect a reply to "Hi" in <2 seconds. They will tolerate 30s for a complex drawing, but not for a greeting.
2.  **Feedback Loops:** Users need immediate feedback (Typing Indicators) to know the bot is "alive". A pure async worker often fails to provide this instant feedback loop.

This leads to:
1.  **Duplicate Replies:** Both systems respond to the same trigger.
2.  **Context Drift:** System 2 doesn't know what System 1 promised.

**Current Fix (Hybrid Filter):**
We strictly filter messages. The Worker (System 2) **ignores** any message where `mentions_bot=True`. It only acts on "ambient" conversations. This works but limits System 2's ability to "deeply reflect" on user conversations.

### 1.2 The Fractal Cognition (Nested System 2)

It is important to note that "System 1 vs System 2" is not just a process split. We actually have **three layers of cognition**:

1.  **System 1 (Fast Mode):**
    *   **Location:** Bot Process (`AgentEngine`)
    *   **Latency:** <2s
    *   **Logic:** Direct LLM call. No tools.
    *   **Use Case:** Greetings, chit-chat.

2.  **System 2a (Reflective Mode):**
    *   **Location:** Bot Process (`ReflectiveGraphAgent`)
    *   **Latency:** 5-15s
    *   **Logic:** ReAct Loop (Search, Tools, Image Gen).
    *   **Constraint:** Must finish before Discord heartbeat timeout (~40s).
    *   **Use Case:** "Draw a cat", "Search the web for X".

3.  **System 2b (Deep Cognition):**
    *   **Location:** Worker Process (`DailyLifeGraph`)
    *   **Latency:** 30s - Minutes
    *   **Logic:** Complex multi-step reasoning, Dreams, Diaries, Lurking.
    *   **Use Case:** "What is the meaning of our conversations last month?", Autonomous behavior.

**The Architectural Gap:**
Currently, System 2a (Bot) and System 2b (Worker) are completely disconnected. System 2b is the "Remote Brain" that should ideally handle *all* heavy lifting, but System 2a exists because we need *some* tools (like Image Gen) to happen "fast enough" for the user, even if it risks blocking.

### 1.3 The Cost Constraint (LLM Explosion)
A naive "Unified Brain" approach (sending *everything* to a complex worker graph) risks a massive cost explosion.

*   **The "Hello" Problem:** If a simple "Hello" triggers a 5-step ReAct loop in the worker to "analyze the deep meaning of the greeting," we pay 5x the token cost for zero value.
*   **Tool Looping:** Without strict coordination, System 2a might try to use a tool, fail, and then System 2b picks it up and tries the same tool, doubling the cost.
*   **The Fix:** We **MUST** keep System 1 (Fast Mode) as the primary gatekeeper. It resolves 80% of queries cheaply. Only the remaining 20% should escalate to System 2a or 2b.

## 2. The Proposal: Coordinated State

Instead of merging everything into one slow Worker (which would violate ADR-002's latency goals), we propose a **Shared State Coordination** model.

### New Flow

1.  **User:** "@Elena hello"
2.  **System 1 (Bot):**
    *   Handles message immediately.
    *   **Action:** Logs interaction to `Redis:ShortTermMemory`.
    *   **Action:** Replies "Hi there!".
3.  **System 2 (Worker):**
    *   Wakes up (Snapshot or Event).
    *   **Check:** Queries `Redis:ShortTermMemory`.
    *   **Decision:** "I see System 1 handled the greeting. I will not reply, BUT I will update the long-term strategy based on this interaction."
    *   **Action:** Updates `Neo4j` or `Qdrant` without sending a Discord message.

### Benefits
*   **Preserves ADR-002:** System 1 remains fast (<2s).
*   **Enables Deep Reflection:** System 2 can still "think" about user messages without awkwardly double-replying.
*   **Stigmergy:** The systems coordinate through the environment (Redis/DB) rather than direct calls.

## 3. Recommendation

**Adopt "Coordinated Dual Process" for Phase 2.**

*   **Do NOT** move System 1 to the Worker (latency risk).
*   **DO** improve the shared memory state so System 2 is "aware" of System 1's actions.

For now, the **Hybrid Filter** (ignoring mentions in Worker) is a sufficient stopgap.
