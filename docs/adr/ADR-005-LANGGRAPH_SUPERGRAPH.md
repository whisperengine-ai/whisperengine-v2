# ADR-005: LangGraph Supergraph Architecture

**Status:** ✅ Accepted  
**Date:** December 2025  
**Deciders:** Mark Castillo, AI Development Team

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Architecture unification |
| **Proposed by** | Mark + Claude (collaborative) |
| **Catalyst** | Manual Python orchestration became hard to observe and maintain |

---

## Context

WhisperEngine's cognitive engine grew organically with:
- Manual Python loops for ReAct (Reasoning + Acting)
- Custom tool execution logic
- Hand-coded state management
- Bespoke retry and error handling

**The problems:**
1. **Spaghetti Code**: Tool loops, state management, and flow control intertwined
2. **Hard to Extend**: Adding new agents or tools required touching multiple files
3. **No Visualization**: Couldn't easily debug or visualize agent decision paths
4. **Inconsistent Patterns**: Each agent implemented loops differently

LangChain/LangGraph emerged as a mature framework for exactly this problem.

---

## Decision

We adopt **LangGraph StateGraph** as the orchestration layer for all agent workflows.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      SUPERGRAPH                                  │
│              (Master orchestrator)                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────┐     ┌────────────┐     ┌────────────┐          │
│  │ Classifier │ ──► │   Router   │ ──► │  Response  │          │
│  │   Node     │     │    Node    │     │   Node     │          │
│  └────────────┘     └────────────┘     └────────────┘          │
│         │                  │                                     │
│         │           ┌──────┴──────┐                             │
│         │           ▼             ▼                             │
│         │    ┌────────────┐ ┌────────────┐                      │
│         │    │    Fast    │ │ Reflective │                      │
│         │    │   Graph    │ │   Graph    │                      │
│         │    └────────────┘ └────────────┘                      │
│         │                          │                             │
│         │                   ┌──────┴──────┐                     │
│         │                   ▼             ▼                     │
│         │            ┌────────────┐ ┌────────────┐              │
│         │            │   Tools    │ │  Generate  │              │
│         │            │   Node     │ │   Node     │              │
│         │            └────────────┘ └────────────┘              │
│         │                                                        │
│         └──► END (on MANIPULATION)                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Design Choices

1. **StateGraph over AgentExecutor**: More control over flow, explicit state management.

2. **Subgraph Composition**: Reflective mode is a nested subgraph, not a monolithic loop.

3. **Native Tool Binding**: Tools bound via `llm.bind_tools()`, not manual JSON parsing.

4. **Explicit Edges**: All transitions defined as conditional edges with clear routing logic.

---

## Consequences

### Positive

1. **Clear Separation**: Each node has one job; flow logic is in edges.

2. **Visualization**: LangGraph Studio can visualize execution paths.

3. **Easier Testing**: Test individual nodes in isolation.

4. **Industry Standard**: Team members familiar with LangChain can contribute.

5. **Built-in Features**: Checkpointing, streaming, retry logic come free.

6. **Type Safety**: Pydantic state models catch errors early.

### Negative

1. **Framework Lock-in**: Dependent on LangChain/LangGraph evolution.

2. **Abstraction Overhead**: Simple flows require graph setup boilerplate.

3. **Learning Curve**: Developers must understand StateGraph concepts.

4. **Debugging Complexity**: Errors in graph execution can be opaque.

### Neutral

1. **Migration Effort**: Existing manual loops were refactored (E17 phase).

2. **Dependency Size**: LangChain is a large dependency tree.

---

## Alternatives Considered

| Alternative | Pros | Cons | Why Rejected |
|-------------|------|------|--------------|
| **Continue Manual Loops** | No new deps, full control | Technical debt, hard to maintain | Already causing problems at scale |
| **Custom State Machine** | Tailored to needs | Reinventing the wheel | LangGraph already solved this |
| **Temporal.io** | Durable execution, industry proven | Overkill for our scale, complex setup | Too heavyweight for solo developer |
| **Apache Airflow** | Mature DAG orchestration | Designed for batch, not real-time | Wrong paradigm for chat agents |
| **Raw asyncio + FSM** | Lightweight | No visualization, manual everything | Would rebuild LangGraph features |

---

## Implementation

### State Definition

```python
# src_v2/agents/supergraph.py

class SupergraphState(TypedDict):
    """State passed through the supergraph."""
    # Input
    user_message: str
    user_id: str
    channel_id: str
    
    # Classification
    complexity: Optional[str]
    intents: Optional[List[str]]
    
    # Context
    memories: Optional[List[Memory]]
    facts: Optional[List[Fact]]
    trust_level: Optional[int]
    
    # Execution
    tool_calls: Optional[List[ToolCall]]
    tool_results: Optional[List[ToolResult]]
    
    # Output
    response: Optional[str]
    artifacts: Optional[List[Artifact]]
```

### Graph Construction

```python
from langgraph.graph import StateGraph, END

def build_supergraph() -> StateGraph:
    graph = StateGraph(SupergraphState)
    
    # Add nodes
    graph.add_node("classify", classify_node)
    graph.add_node("build_context", context_node)
    graph.add_node("route", router_node)
    graph.add_node("fast_response", fast_node)
    graph.add_node("reflective", build_reflective_subgraph())
    graph.add_node("finalize", finalize_node)
    
    # Add edges
    graph.set_entry_point("classify")
    graph.add_edge("classify", "build_context")
    graph.add_edge("build_context", "route")
    
    graph.add_conditional_edges(
        "route",
        route_by_complexity,
        {
            "fast": "fast_response",
            "reflective": "reflective",
            "blocked": END,
        }
    )
    
    graph.add_edge("fast_response", "finalize")
    graph.add_edge("reflective", "finalize")
    graph.add_edge("finalize", END)
    
    return graph.compile()
```

### Tool Binding

```python
# Native function calling, no regex parsing
tools = [
    SearchMemoriesTool(),
    GetFactsTool(),
    GenerateImageTool(),
    UpdateFactsTool(),
]

llm_with_tools = llm.bind_tools(tools)
```

---

## References

- LangGraph docs: https://langchain-ai.github.io/langgraph/
- Supergraph architecture: [`docs/roadmaps/SUPERGRAPH_ARCHITECTURE.md`](../roadmaps/SUPERGRAPH_ARCHITECTURE.md)
- Agent graph system: [`docs/architecture/AGENT_GRAPH_SYSTEM.md`](../architecture/AGENT_GRAPH_SYSTEM.md)
- Implementation: [`src_v2/agents/supergraph.py`](../../src_v2/agents/supergraph.py)
