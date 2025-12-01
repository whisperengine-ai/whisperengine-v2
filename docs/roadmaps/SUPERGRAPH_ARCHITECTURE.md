# Supergraph Architecture: The Unified Agent Orchestrator

**Status:** Proposed
**Target Phase:** E17
**Dependencies:** LangGraph Implementation (Complete)

## 1. The Vision

Currently, `AgentEngine` is a Python class that orchestrates calls to various sub-systems (Memory, Knowledge, Trust) and then delegates execution to specific agents (`ReflectiveGraphAgent`, `CharacterGraphAgent`) based on logic.

The **Supergraph** architecture elevates `AgentEngine` from a Python controller to a **Master StateGraph**. This unifies the entire request lifecycle—from reception to response—into a single, observable graph structure.

### Current vs. Future State

**Current (Python Orchestration):**
```python
# AgentEngine.generate_response()
context = await gather_context()  # Hidden from LangSmith
classification = await classify() # Hidden from LangSmith
if classification.is_complex:
    return await reflective_graph.invoke() # Visible in LangSmith
else:
    return await character_graph.invoke()  # Visible in LangSmith
```

**Future (Supergraph):**
```python
# Supergraph
START -> ContextNode -> ClassifierNode -> RouterNode
RouterNode -> ReflectiveSubgraph
RouterNode -> CharacterSubgraph
ReflectiveSubgraph -> END
CharacterSubgraph -> END
```

## 2. Architecture Components

The Supergraph will act as the parent graph, with existing agents becoming **subgraphs**.

### 2.1 The Master Graph Structure

```python
class SuperGraphState(TypedDict):
    input: str
    user_id: str
    context: AgentContext
    classification: ComplexityResult
    response: str
    
# Nodes
async def context_node(state):
    # Parallel fetch of Memory, Knowledge, Trust
    return {"context": await gather_all()}

async def classifier_node(state):
    # Determine complexity and intent
    return {"classification": await classify(state)}

async def router_node(state):
    # Route to appropriate subgraph
    if state["classification"].complexity == "complex":
        return "reflective_agent"
    return "character_agent"
```

### 2.2 Subgraph Integration

The existing `ReflectiveGraphAgent` and `CharacterGraphAgent` will be compiled as subgraphs and added as nodes to the Supergraph.

```python
workflow = StateGraph(SuperGraphState)

# Add standard nodes
workflow.add_node("context_fetcher", context_node)
workflow.add_node("classifier", classifier_node)

# Add subgraphs as nodes
workflow.add_node("reflective_agent", reflective_graph_agent.compiled_graph)
workflow.add_node("character_agent", character_graph_agent.compiled_graph)

# Edges
workflow.add_edge(START, "context_fetcher")
workflow.add_edge("context_fetcher", "classifier")
workflow.add_conditional_edges("classifier", router_node)
workflow.add_edge("reflective_agent", END)
workflow.add_edge("character_agent", END)
```

## 3. Benefits

1.  **Total Observability**: The *entire* lifecycle, including context retrieval and classification, becomes visible in LangSmith traces.
2.  **Global State**: Context (memories, facts) is passed cleanly through the graph state, reducing the need for global singletons or complex dependency injection.
3.  **Dynamic Routing**: Easier to implement complex routing logic (e.g., "Try Character Agent, if confidence low, escalate to Reflective Agent").
4.  **Unified Error Handling**: A global "Safety/Error" node can catch failures from any subgraph.

## 4. Implementation Plan

### Phase 1: The Wrapper (Non-Breaking)
Create `MasterGraphAgent` that wraps the existing logic but doesn't replace `AgentEngine` yet.
- [ ] Define `SuperGraphState`
- [ ] Create `ContextNode` (wraps `db_manager` calls)
- [ ] Create `ClassifierNode` (wraps `ComplexityClassifier`)

### Phase 2: Subgraph Integration
- [ ] Import compiled graphs from `ReflectiveGraphAgent` and `CharacterGraphAgent`
- [ ] Wire them into `MasterGraphAgent`

### Phase 3: Migration
- [ ] Add `ENABLE_SUPERGRAPH` feature flag
- [ ] Switch `AgentEngine` to delegate to `MasterGraphAgent` instead of manual orchestration

## 5. Future Possibilities

Once the Supergraph is in place, we can add new top-level capabilities:
- **Moderation Node**: Check inputs before they even reach the classifier.
- **Post-Processing Node**: Handle artifact generation (images, voice) as a graph step rather than a post-hook.
- **Multi-Agent Debate**: Route to *both* Reflective and Character agents and have a "Judge" node pick the best response.
