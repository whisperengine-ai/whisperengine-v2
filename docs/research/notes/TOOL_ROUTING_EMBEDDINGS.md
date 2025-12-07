# Tool Routing via Embeddings

**Date:** December 6, 2025  
**Status:** Research Note (Not Implemented)  
**Trigger:** VS Code's MCP tool scaling solution discussion

## The Problem

When you have hundreds of MCP tools, loading them all upfront causes:
- **Context bloat** — LLM sees too many tool descriptions
- **Slower responses** — more tokens to process
- **Higher costs** — paying for context you don't need
- **Worse results** — noise drowns out relevant tools

VS Code hit this with their MCP integration and found that naive "load everything" dropped tool selection accuracy to ~69%.

## VS Code's Solution: Virtual Tools + Embedding Routing

Their architecture:

1. **Core tools (~13)** — Always visible to the agent
2. **Virtual tool groups** — Everything else, hidden behind semantic routing
3. **Embedding-based pre-selection** — Before the agent reasons, embeddings find relevant tools
4. **Result:** 94.5% tool selection accuracy with cleaner context

The key insight: **Use semantic search on tool descriptions, not tool execution.**

## WhisperEngine Current State

### Tool Count
~25-30 tools in `character_graph.py`:
- Memory & Knowledge: `search_summaries`, `search_episodes`, `lookup_facts`, etc.
- Discord: `search_channel_messages`, `get_recent_messages` (conditional)
- Creative: `generate_image` (conditional)
- Introspection: `analyze_patterns`, `detect_themes`, `search_my_thoughts`
- Community: `discover_community_insights`, `get_sibling_bot_info`

### Existing Smart Patterns
We already do some of this:
- **Conditional loading**: `if settings.ENABLE_WEB_SEARCH`, `if channel`
- **Intent detection**: `ComplexityClassifier` detects voice/image/search intents
- **Complexity routing**: Simple queries skip tools entirely

### Assessment
**Current scale is manageable.** 25-30 tools is within the LLM sweet spot. No urgent need for embedding-based routing yet.

## When to Implement

Implement this pattern when:
- [ ] Tool count exceeds 40-50
- [ ] Adding MCP server support (external tools)
- [ ] Different characters need different tool sets
- [ ] Context window bloat visibly affects response quality

## Proposed Implementation (When Needed)

### Option 1: Lightweight — Classifier Hints

Extend existing `ComplexityClassifier` to output tool category hints:

```python
# In classifier response
{
    "complexity": "complex_mid",
    "intents": ["memory"],
    "tool_hints": ["memory_deep", "introspection"]  # NEW
}
```

Then filter tools before passing to agent. Reuses existing LLM call.

### Option 2: Full — Embedding Router

```python
class ToolRouter:
    """Embedding-based tool pre-selection (VS Code-style)."""
    
    CORE_TOOLS = {
        "search_summaries", "search_episodes", "lookup_facts",
        "search_my_thoughts", "web_search", "calculator"
    }
    
    TOOL_GROUPS = {
        "memory_deep": {
            "description": "Deep memory analysis, patterns, themes, evolution",
            "tools": ["analyze_patterns", "detect_themes", "character_evolution"]
        },
        "community": {
            "description": "Cross-bot, gossip, community insights, sibling bots",
            "tools": ["discover_community_insights", "get_sibling_bot_info", 
                      "recall_bot_conversation"]
        },
        "discord_context": {
            "description": "Channel messages, recent chat, user history in Discord",
            "tools": ["search_channel_messages", "get_recent_messages", 
                      "get_message_context", "search_user_messages"]
        },
        "creative": {
            "description": "Image generation, visual content, art, pictures",
            "tools": ["generate_image"]
        },
        "knowledge_graph": {
            "description": "Facts, relationships, graph exploration, common ground",
            "tools": ["explore_graph", "discover_common_ground", "update_facts"]
        },
    }
    
    async def select_tools(
        self, 
        message: str, 
        base_tools: List[BaseTool],
        similarity_threshold: float = 0.6
    ) -> List[BaseTool]:
        """Pre-select relevant tools based on message embedding similarity."""
        
        # Always include core tools
        selected_names = set(self.CORE_TOOLS)
        
        # Embed the user message (reuse existing EmbeddingService)
        msg_embedding = await embedding_service.embed(message)
        
        # Check each tool group
        for group_name, group_info in self.TOOL_GROUPS.items():
            # Cache these at startup for efficiency
            group_embedding = self._group_embeddings[group_name]
            similarity = cosine_similarity(msg_embedding, group_embedding)
            
            if similarity > similarity_threshold:
                selected_names.update(group_info["tools"])
        
        # Filter to only selected tools
        return [t for t in base_tools if t.name in selected_names]
```

### Integration Point

In `CharacterGraph._get_tools()`:

```python
def _get_tools(self, user_id: str, ...) -> List[BaseTool]:
    all_tools = [...]  # Current full list
    
    if settings.ENABLE_TOOL_ROUTING and len(all_tools) > 40:
        return await tool_router.select_tools(message, all_tools)
    
    return all_tools
```

## Cost Analysis

| Approach | Added Latency | Token Cost | Accuracy |
|----------|---------------|------------|----------|
| Load all tools | 0ms | High (tool descriptions in context) | ~69% at scale |
| Classifier hints | 0ms (reuses existing call) | None | ~85% estimated |
| Embedding router | ~20ms (local embedding) | None | ~94% (VS Code's number) |

## References

- VS Code MCP scaling post (December 2025)
- Current tools: `src_v2/agents/character_graph.py:_get_tools()`
- Embedding service: `src_v2/memory/embeddings.py`
- Complexity classifier: `src_v2/agents/classifier.py`

## Decision

**Defer implementation.** Current tool count (~25) doesn't warrant the complexity. Revisit when:
1. Adding MCP server integration
2. Tool count exceeds 40
3. Users report slow/confused tool selection

---

*Origin: Human-AI research discussion. Captured for future reference.*
