# WhisperEngine v2 - Phase 2 Roadmap (2026)

**Focus:** Deepening agent autonomy, multi-agent collaboration, and production-grade evaluation.
**Reference:** [Agentic Learning Roadmap](./AGENTIC_LEARNING_ROADMAP.md)

---

## 🚀 Phase 2: Advanced Agentic Capabilities

### 📋 Phase A1: Emergent Goal Decomposition
**Priority:** 🟢 High | **Time:** 3-4 days | **Complexity:** High
**Status:** 📋 Planned
**Dependencies:** E18 (Goal Strategist) ✅

**Problem:** Agents currently have static goals. They cannot break down complex objectives (e.g., "Research this topic") into actionable sub-steps autonomously.

**Solution:**
- Enhance `GoalStrategist` to support hierarchical goals (Parent -> Children) stored in the **Knowledge Graph**.
- Allow agents to "plan" by creating new goal nodes in the graph, rather than running a rigid "planning loop".
- Agents self-assign sub-goals based on their current context and capabilities.

**Emergence Alignment:** Complex long-term behavior emerges from the execution of small, self-derived sub-goals stored in the graph.

### 📋 Phase A2: Social Problem Solving (Multi-Agent)
**Priority:** 🟡 Medium | **Time:** 4-5 days | **Complexity:** High
**Status:** 📋 Planned
**Dependencies:** E15.3 (Conversation Agent) ✅

**Problem:** Bots can chat with each other, but they don't *work* together effectively on tasks.

**Solution:**
- Implement a "Help Request" behavior where a bot can autonomously decide to ask another bot for input (e.g., Elena asks Sage for code review).
- Treat other bots as "Tools" in the `ReflectiveAgent` toolkit.
- Use the existing "Universe" bus for coordination, avoiding a central "Swarm Controller".

### 📋 Phase A3: Evolutionary Prompt Optimization
**Priority:** 🟡 Medium | **Time:** 2-3 days | **Complexity:** Medium
**Status:** 📋 Planned
**Dependencies:** E16 (Feedback Loop) ✅

**Problem:** We collect user reactions (👍/👎), but they only affect trust scores, not the agent's actual generation patterns.

**Solution:**
- Create a "Persona Evolution" job that analyzes highly-rated responses vs. poorly-rated ones.
- Automatically adjust the `ux.yaml` or system prompt nuances based on successful interaction patterns.
- Allow the persona to "drift" towards traits that users respond well to (Evolutionary RLHF).

### 📋 Phase A4: Trace Evaluation Pipeline (LangSmith)
**Priority:** ⚪ Low | **Time:** 1-2 days | **Complexity:** Low
**Status:** 📋 Planned
**Dependencies:** None

**Problem:** We have LangSmith integrated, but we aren't using it for systematic evaluation.

**Solution:**
- Enable LangSmith tracing in production for a sample of requests.
- Create a dataset of "golden runs" (ideal responses) within LangSmith.
- Set up automated regression testing to compare new model versions against these golden runs.

### 📋 Phase A5: Containerized Code Execution
**Priority:** 🔴 Critical (for coding agents) | **Time:** 3-4 days | **Complexity:** High
**Status:** 📋 Planned
**Dependencies:** Docker ✅

**Problem:** The agent cannot safely execute code it writes, limiting its ability to perform data analysis or complex math.

**Solution:**
- Create a `CodeExecutionTool` that spins up an ephemeral Docker container.
- Allow the agent to write Python scripts, run them, and capture stdout/stderr.
- **Security:** Strictly isolated network and filesystem access.
