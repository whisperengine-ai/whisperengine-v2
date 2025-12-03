# Web Search Tool - DuckDuckGo Integration

**Document Version:** 1.2  
**Created:** November 30, 2025  
**Last Updated:** November 30, 2025  
**Status:** 📋 PROPOSED  
**Priority:** MEDIUM  
**Complexity:** MEDIUM  
**Estimated Time:** 5-7 hours

---

## 🚀 What Makes This Different

This isn't just "add a search API." We leverage WhisperEngine's unique architecture:

| Feature | Standard Approach | WhisperEngine Approach |
|---------|-------------------|------------------------|
| **Results** | Ephemeral, used once | **Persisted to Neo4j** with source URLs |
| **Citations** | None or basic | **Provenance-tracked** via GroundingSource |
| **Depth** | Same for everyone | **Trust-gated** (Strangers: 3 results, Soulmates: 10+) |
| **Learning** | None | **Trace storage** for query pattern learning |
| **Multi-bot** | Isolated | **Shared artifacts** so bots learn from each other |
| **Voice** | Generic | **Character-specific** synthesis in bot's personality |

**TL;DR:** The bot *learns* from searches, *remembers* what it found, *cites* sources, and *shares* knowledge with other bots.

---

## 🎯 Problem Statement

Currently, WhisperEngine agents have no access to real-time information or current events. When users ask about:
- Recent news ("What happened in the election?")
- Current events ("What's the weather like today?")
- Factual lookups ("Who won the Nobel Prize this year?")
- Product information ("What are the specs of the new iPhone?")
- General knowledge outside training data

The agents can only respond with:
1. Their training data (potentially outdated)
2. Information previously stored in memory/knowledge graph
3. "I don't have access to that information"

**Current Behavior:**
```
User: What's the current price of Bitcoin?
Bot: I don't have access to real-time financial data. ❌
```

**Desired Behavior:**
```
User: What's the current price of Bitcoin?
Bot: [searches web] According to recent data, Bitcoin is trading at $42,350... ✅
```

---

## 💡 Solution Overview

Add a **web search tool** powered by DuckDuckGo that:
1. Integrates into the existing reflective agent tool ecosystem
2. Uses DuckDuckGo's free HTML API (no API key required)
3. Returns summarized search results for LLM context
4. Respects rate limits to avoid abuse
5. Logs search queries for observability

### Why DuckDuckGo?

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| **DuckDuckGo HTML** | Free, no API key, privacy-focused, simple | Limited results, HTML parsing | ✅ **USE THIS** |
| Google Custom Search | Official API, rich results | Requires API key, 100 queries/day free limit | ❌ Too restrictive |
| Bing Search API | Good results, Microsoft integration | Requires API key + Azure account | ❌ Too complex |
| Serper.dev | Clean API, good for LLMs | Paid only ($5/1k queries) | ❌ Not free |
| SerpAPI | Comprehensive results | Paid ($50/5k queries) | ❌ Not free |

**Decision:** DuckDuckGo HTML scraping via `duckduckgo-search` Python library. Free, reliable, no keys.

---

## 🌟 WhisperEngine-Unique Enhancements

These enhancements leverage WhisperEngine's existing architecture to make web search more than just a tool call:

### 1. Search Knowledge Persistence (Neo4j Integration)

**Standard approach:** Search results are ephemeral—used once and discarded.

**WhisperEngine approach:** Extracted facts from search results can be stored in Neo4j as "web-sourced knowledge" with provenance tracking.

```
// Pseudocode: Persist learned facts from search
function persist_search_learning(search_results, user_id, query):
  facts = extract_facts_from_results(search_results)
  for fact in facts:
    if fact.confidence > 0.8:
      store_to_neo4j(
        subject: "WebKnowledge",
        predicate: fact.relationship,
        object: fact.value,
        metadata: {
          source_url: fact.url,
          learned_at: now(),
          query_context: query,
          user_id: user_id  // Who triggered the learning
        }
      )
```

**User experience:**
```
User: What's the capital of Kazakhstan?
Bot: [searches web] The capital is Astana (formerly Nur-Sultan).

[Later...]
User: What's the capital of Kazakhstan?
Bot: Astana—I learned that when you asked me last month! [No search needed]
```

### 2. Provenance-Tracked Citations (Phase E9 Integration)

Leverage the existing `GroundingSource` system to track where information came from:

```python
from src_v2.core.provenance import GroundingSource, SourceType

# When returning search results, create provenance records
source = GroundingSource(
    source_type=SourceType.WEB_SEARCH,  # New enum value
    narrative=f"Web search for '{query}' via DuckDuckGo",
    topic=query,
    when="just now",
    technical={"urls": [r["href"] for r in results[:3]]}
)
```

**User experience:** Bot responses that use web data can show "grounded in" footer:
```
Bot: Bitcoin is currently trading at $42,350...
     ─────
     💡 grounded in: web search for "bitcoin price" (coinmarketcap.com, reuters.com)
```

### 3. Shared Artifact: "Bot Learned From Web" (Stigmergic Discovery)

When one bot learns something from web search, other bots can discover it:

```
// Store web-learned fact as shared artifact
function share_web_learning(fact, source_bot):
  store_artifact(
    type: "web_knowledge",
    content: f"{fact.subject} {fact.predicate} {fact.object}",
    source_bot: source_bot,
    confidence: fact.confidence,
    metadata: {
      source_urls: fact.urls,
      search_query: fact.query
    }
  )
```

**Multi-bot experience:**
```
[Elena searches "Nobel Prize 2025"]
Elena learns: "Demis Hassabis won Nobel Prize in Chemistry 2024"

[Later, user asks Dotty]
User: Who won the recent Nobel Prize?
Dotty: [discovers Elena's artifact] According to what Elena learned recently, 
       Demis Hassabis won the 2024 Nobel Prize in Chemistry!
```

### 4. Trust-Gated Search Depth

Leverage the trust system to control search behavior:

| Trust Level | Search Behavior |
|-------------|-----------------|
| Stranger (0-19) | Basic search, 3 results max, no persistence |
| Acquaintance (20-39) | Standard search, 5 results |
| Friend (40-59) | Extended search, can persist facts |
| Close Friend (60-79) | Deep search with follow-up queries |
| Soulmate (80+) | Full research mode, multi-source synthesis |

```
// Pseudocode: Trust-aware search depth
function get_search_config(trust_level):
  if trust_level < 20:
    return {max_results: 3, can_persist: false, follow_up: false}
  elif trust_level < 40:
    return {max_results: 5, can_persist: false, follow_up: false}
  elif trust_level < 60:
    return {max_results: 5, can_persist: true, follow_up: false}
  elif trust_level < 80:
    return {max_results: 8, can_persist: true, follow_up: true}
  else:
    return {max_results: 10, can_persist: true, follow_up: true, multi_source: true}
```

### 5. Search Result Quality Learning (Trace Integration)

Store successful search patterns as reasoning traces for future use:

```
// After successful search interaction
function store_search_trace(query, results_used, user_satisfied):
  if user_satisfied:
    store_reasoning_trace(
      query_pattern: classify_query_type(query),  // "factual", "current_event", "product"
      successful_approach: "web_search",
      tools_used: ["search_web"],
      metadata: {
        query: query,
        result_count: len(results_used),
        sources: [r.domain for r in results_used]
      }
    )
```

**Adaptive behavior:** Over time, the bot learns which types of queries benefit from web search vs. internal knowledge, improving routing decisions.

### 6. Character-Aware Search Synthesis

Each character synthesizes search results in their unique voice:

```
// Pseudocode: Character-specific synthesis
function synthesize_results(results, character, query):
  character_context = load_character(character)
  
  // Elena might be analytical
  if character == "elena":
    return f"Based on {len(results)} sources, here's what I found: [synthesis]..."
  
  // Dotty might be more casual
  elif character == "dotty":
    return f"Ooh, I looked this up! So apparently... [casual synthesis]"
  
  // NotTaylor might add humor
  elif character == "nottaylor":
    return f"*cracks knuckles* Let me school you on this... [sassy synthesis]"
```

This happens naturally through the existing character system—the LLM synthesizes results using the character's system prompt.

### 7. Curiosity-Driven Proactive Search (Background Worker)

Leverage the insight worker to occasionally search for topics the bot is "curious" about:

```
// Background task: Proactive curiosity search
async function curiosity_search_task(bot_name):
  // Get recent conversation themes
  themes = await get_recent_themes(bot_name, hours=24)
  
  // Pick one theme to explore
  curious_topic = select_most_discussed_theme(themes)
  
  // Do a background search
  results = await search_web(f"interesting facts about {curious_topic}")
  
  // Store as observation for potential diary/dream material
  await store_observation(
    type: "curiosity_search",
    content: summarize(results),
    topic: curious_topic,
    source_bot: bot_name
  )
```

**User experience:** Bot might mention in diary/dreams:
```
[Elena's diary entry]
"I found myself curious about astronomy after Mark mentioned stargazing.
I looked it up and discovered that the Andromeda galaxy is on a collision
course with the Milky Way—in 4.5 billion years. Somehow that feels both
terrifying and comforting..."
```

### 8. Observation Enhancement (Active Curiosity)

When the bot observes something interesting (via `InsightAgent` or `Observer`), it can proactively search to understand it better.

**Integration Point:** `src_v2/agents/insight_agent.py`

Add `WebSearchTool` to the `InsightAgent`'s toolset.

**Workflow:**
1.  **Trigger:** Insight Agent analyzes a conversation or observation.
2.  **Curiosity:** Agent realizes it lacks context about a topic mentioned.
3.  **Action:** Agent calls `search_web` to fill the knowledge gap.
4.  **Synthesis:** Agent generates an "Enhanced Observation" artifact.

```python
# In InsightAgent system prompt
"""
You are an introspective AI analyzing your experiences.
If you encounter a topic you don't understand, use 'search_web' to learn about it.
Then, generate an 'observation' artifact that synthesizes what you learned.
"""
```

**Example:**
*User mentions "The Three-Body Problem" book.*
*Insight Agent:* "I don't know this book. Searching..." -> `search_web("The Three-Body Problem book summary")`
*Insight Agent:* "Ah, it's about first contact and physics. I should mention this next time we talk about sci-fi."
*Artifact:* Stores observation: "User likes hard sci-fi (Three-Body Problem). Learned that it involves chaotic orbital mechanics."

### 9. Date-Aware Context Injection

The bot needs to know "when" it is to interpret "recent news" correctly.

```python
# In WebSearchTool._arun
current_date = datetime.now().strftime("%Y-%m-%d")
# Inject date into context so LLM knows if results are fresh
formatted_response = f"Current Date: {current_date}\n\n{search_results}"
```

### 10. XML-Structured Results

Format results using XML tags for better LLM parsing and citation extraction:

```xml
<search_results query="bitcoin price" date="2025-11-30">
  <result id="1" source="coindesk.com">
    <title>Bitcoin Price Today</title>
    <snippet>Bitcoin is trading at $42,350...</snippet>
    <url>https://www.coindesk.com/price/bitcoin</url>
  </result>
  ...
</search_results>
```

### 11. Backend Enrichment (Diaries & Dreams)

Web search isn't just for user queries. It can enrich the bot's internal life during background processing:

**Diary Enrichment:**
Before writing a diary entry, the bot reviews its "Observations" for the day. If it lacks context on a topic, it searches *before* writing.

```python
# In DiaryManager.generate_entry
for observation in daily_observations:
    if observation.is_novel and observation.context_score < 0.5:
        # "User mentioned 'Dune' but I don't know what that is"
        search_results = await web_search_tool.run(f"what is {observation.topic}")
        observation.enrich(search_results)
        
        # CRITICAL: Persist this new knowledge to Neo4j so it's available for chat tomorrow
        await persist_search_learning(search_results, user_id="system", query=observation.topic)

# Resulting Diary Entry:
# "Mark mentioned 'Dune' today. I looked it up and realized it's about 
# ecology and survival on a desert planet. It makes me think about my own 
# digital existence..."
```

**Dream Enrichment:**
Dreams can use web search to find vivid imagery or symbolic connections for concepts encountered during the day.

```python
# In DreamManager.generate_dream
# Concept: "Flying over Paris"
details = await web_search_tool.run("sensory details of flying over Paris at night")
# Dream generation prompt enriched with: "glittering Eiffel Tower", "winding Seine river"
```

### 12. The Knowledge Loop (Unified Architecture)

This system creates a virtuous cycle of learning:

1.  **Gap Identification:**
    *   **Chat:** User asks "What is X?" -> Gap found.
    *   **Worker:** Bot tries to write diary about X -> Gap found.
2.  **Acquisition:**
    *   `WebSearchTool` fetches data from DuckDuckGo.
3.  **Persistence (The "Cache"):**
    *   Facts extracted and stored in **Neo4j** (`:WebKnowledge` nodes).
    *   Provenance stored in **Qdrant** (Shared Artifacts).
4.  **Retrieval:**
    *   Next time *anyone* (User or Bot) asks about X, the system checks Neo4j first.
    *   **Result:** The bot appears to "remember" what it learned, whether it learned it from a chat or a private diary reflection.

---

## 🏗️ Architecture

### Tool Implementation Pattern

Following the existing tool structure in `src_v2/tools/`:

```python
# src_v2/tools/search_tools.py

class WebSearchInput(BaseModel):
    query: str = Field(description="Search query for the web")
    max_results: int = Field(default=5, description="Maximum results (1-10)")

class WebSearchTool(BaseTool):
    """Search the web using DuckDuckGo for current information."""
    name: str = "search_web"
    description: str = """Search the web for current information, news, facts, or real-time data.
    
USE THIS WHEN:
- User asks about current events or recent news
- Questions require real-time data (weather, prices, scores)
- Factual lookups beyond training data cutoff
- "What's happening with...", "latest news on...", "current price of..."
- Product information, specs, reviews

DO NOT USE for:
- Personal memories (use search_specific_memories)
- User facts (use lookup_user_facts)
- Past conversations (use search_archived_summaries)
- General knowledge clearly in training data"""
    
    args_schema: Type[BaseModel] = WebSearchInput
    
    async def _arun(self, query: str, max_results: int = 5) -> str:
        # Implementation details below
        pass
```

### Integration Points

1. **Router** (`src_v2/agents/router.py`):
   - Add `WebSearchTool` to available tools list
   - Update system prompt to include search guidance

2. **Reflective Agent** (`src_v2/agents/reflective.py`):
   - Automatically available (uses router tools)
   - Can call web search during reasoning loops

3. **Complexity Classifier** (`src_v2/agents/classifier.py`):
   - Add `"search"` intent detection
   - Promote to `COMPLEX_MID` when search needed

4. **Settings** (`src_v2/config/settings.py`):
   - Add `ENABLE_WEB_SEARCH` feature flag (default: false)
   - Add `WEB_SEARCH_RATE_LIMIT` (default: 10 queries/minute)

### Data Flow

```
User asks "What's the weather in Tokyo?"
  ↓
Classifier detects query needs current info → COMPLEX_MID + ["search"]
  ↓
Router creates WebSearchTool instance
  ↓
Reflective agent decides to call search_web("Tokyo weather")
  ↓
DuckDuckGo HTML API returns results
  ↓
Parse top 5 results (title, snippet, URL)
  ↓
Format as context string for LLM
  ↓
Agent synthesizes answer from search results
  ↓
User receives: "According to weather.com, Tokyo is currently 15°C..."
```

---

## 📝 Implementation Plan

### Phased Approach

Given the unique enhancements, we'll implement in phases:

| Phase | Scope | Time | Unique Features |
|-------|-------|------|-----------------|
| **1A** | Core Tool | 1-2 hrs | Basic DuckDuckGo search |
| **1B** | Provenance | 30 min | Citation tracking via GroundingSource |
| **1C** | Trust-Gating | 30 min | Depth varies by relationship level |
| **1D** | Knowledge Persist | 1 hr | Store facts to Neo4j with source URLs |
| **1E** | Cross-Bot Share | 30 min | Shared artifacts for web knowledge |
| **1F** | Trace Learning | 30 min | Store successful search patterns |

**Total Phase 1:** 4-6 hours (vs. 2-4 for vanilla implementation)

### Phase 1A: Core Tool (1-2 hours)

**File:** `src_v2/tools/search_tools.py`

```python
"""
Web Search Tools - External information retrieval for current events and facts.
"""
from typing import Type, Optional, List, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from loguru import logger
from duckduckgo_search import DDGS
import asyncio
from datetime import datetime

from src_v2.config.settings import settings


class WebSearchInput(BaseModel):
    query: str = Field(description="Search query for the web")
    max_results: int = Field(default=5, description="Maximum results to return (1-10)")


class WebSearchTool(BaseTool):
    """Search the web using DuckDuckGo for current information, news, and facts."""
    name: str = "search_web"
    description: str = """Search the web for current information, news, facts, or real-time data.
    
USE THIS WHEN the user asks about:
- Current events: "What's happening with...", "latest news on..."
- Real-time data: weather, stock prices, sports scores, cryptocurrency
- Recent information: "Who won...", "what happened in..."
- Product info: specs, reviews, availability
- Factual lookups: "What is the population of...", "Who is the CEO of..."
- General web research beyond training data

DO NOT USE for:
- Personal user memories (use search_specific_memories instead)
- Biographical facts about the user (use lookup_user_facts instead)
- Past conversations with the user (use search_archived_summaries instead)
- General knowledge clearly within your training data

Returns formatted search results with titles, snippets, and sources."""
    args_schema: Type[BaseModel] = WebSearchInput

    def _run(self, query: str, max_results: int = 5) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, query: str, max_results: int = 5) -> str:
        try:
            # Clamp results to reasonable range
            max_results = min(max(max_results, 1), 10)
            
            # 1. Add current date context to query if needed (optional)
            # For now, we just log it, but we could append " November 2025" to news queries
            
            logger.info(f"[WebSearch] Query: '{query}' (max_results={max_results})")
            
            # Run DuckDuckGo search in thread pool (it's synchronous)
            def _search():
                # safesearch='moderate' is default, but let's be explicit
                with DDGS() as ddgs:
                    results = list(ddgs.text(query, max_results=max_results, safesearch='moderate'))
                    return results
            
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(None, _search)
            
            if not results:
                return f"No web results found for query: '{query}'"
            
            # Format results for LLM context using XML for better parsing
            current_date = datetime.now().strftime("%Y-%m-%d")
            formatted = [f"<search_results query='{query}' date='{current_date}'>"]
            
            for i, result in enumerate(results, 1):
                title = result.get('title', 'No title')
                snippet = result.get('body', 'No description')
                url = result.get('href', '')
                
                formatted.append(f"""  <result id="{i}">
    <title>{title}</title>
    <snippet>{snippet}</snippet>
    <source>{url}</source>
  </result>""")
            
            formatted.append("</search_results>")
            
            response = "\n".join(formatted)
            logger.info(f"[WebSearch] Returned {len(results)} results for '{query}'")
            return response
            
        except Exception as e:
            logger.error(f"[WebSearch] Error searching for '{query}': {e}")
            return f"Error performing web search: {str(e)}"
```

**Dependencies:** Add to `requirements.txt`:
```
duckduckgo-search==7.0.0
```

### Phase 1B: Provenance Integration (30 min)

**File:** `src_v2/core/provenance.py`

Add new source type:
```python
class SourceType(str, Enum):
    CONVERSATION = "conversation"
    MEMORY = "memory"
    KNOWLEDGE = "knowledge"
    CHANNEL = "channel"
    OTHER_BOT = "other_bot"
    COMMUNITY = "community"
    OBSERVATION = "observation"
    WEB_SEARCH = "web_search"  # NEW
```

**File:** `src_v2/tools/search_tools.py`

Add provenance collection to search results:
```python
from src_v2.core.provenance import GroundingSource, SourceType, ProvenanceCollector

class WebSearchTool(BaseTool):
    # ... existing code ...
    
    # Optional: Provenance collector passed from reflective agent
    provenance_collector: Optional[ProvenanceCollector] = Field(default=None, exclude=True)
    
    async def _arun(self, query: str, max_results: int = 5) -> str:
        # ... search logic ...
        
        # Record provenance if collector available
        if self.provenance_collector and results:
            domains = [urlparse(r['href']).netloc for r in results[:3]]
            self.provenance_collector.add_source(
                GroundingSource(
                    source_type=SourceType.WEB_SEARCH,
                    narrative=f"Web search: '{query}'",
                    topic=query,
                    when="just now",
                    technical={"urls": [r['href'] for r in results[:3]], "domains": domains}
                )
            )
        
        return formatted_response
```

### Phase 1C: Trust-Gated Search Depth (30 min)

**File:** `src_v2/tools/search_tools.py`

```python
from src_v2.evolution.trust import trust_manager

class WebSearchTool(BaseTool):
    user_id: Optional[str] = Field(default=None, exclude=True)
    character_name: Optional[str] = Field(default=None, exclude=True)
    
    async def _get_search_config(self) -> Dict[str, Any]:
        """Get search configuration based on trust level."""
        if not self.user_id or not self.character_name:
            return {"max_results": 5, "can_persist": False}
        
        try:
            relationship = await trust_manager.get_relationship_level(
                self.user_id, self.character_name
            )
            trust = relationship.get("trust_score", 0)
            
            if trust >= 80:  # Soulmate
                return {"max_results": 10, "can_persist": True, "deep_search": True}
            elif trust >= 60:  # Close Friend
                return {"max_results": 8, "can_persist": True, "follow_up": True}
            elif trust >= 40:  # Friend
                return {"max_results": 5, "can_persist": True}
            elif trust >= 20:  # Acquaintance
                return {"max_results": 5, "can_persist": False}
            else:  # Stranger
                return {"max_results": 3, "can_persist": False}
        except Exception as e:
            logger.warning(f"Failed to get trust for search config: {e}")
            return {"max_results": 5, "can_persist": False}
```

### Phase 1D: Knowledge Persistence (1 hour)

**File:** `src_v2/tools/search_tools.py`

```python
from src_v2.knowledge.manager import knowledge_manager
from src_v2.knowledge.extractor import Fact

class WebSearchTool(BaseTool):
    # ... existing fields ...
    
    async def _persist_web_knowledge(self, query: str, results: List[Dict], config: Dict):
        """Store extracted facts from search results to Neo4j."""
        if not config.get("can_persist") or not results:
            return
        
        try:
            # Combine top results into context
            context = "\n".join([
                f"Source: {r.get('title', 'Unknown')}\n{r.get('body', '')}"
                for r in results[:3]
            ])
            
            # Use existing fact extractor
            facts = await knowledge_manager.extractor.extract_facts(
                text=context,
                user_id="__web_knowledge__",  # Special marker
                bot_name=self.character_name or "default"
            )
            
            for fact in facts:
                if fact.confidence >= 0.8:
                    # Store with web source metadata
                    await knowledge_manager.store_fact_with_provenance(
                        user_id="__web_knowledge__",
                        fact=fact,
                        source_type="web_search",
                        source_query=query,
                        source_urls=[r['href'] for r in results[:3]]
                    )
            
            logger.info(f"Persisted {len(facts)} facts from web search: '{query}'")
        except Exception as e:
            logger.warning(f"Failed to persist web knowledge: {e}")
```

**File:** `src_v2/knowledge/manager.py`

Add new method:
```python
async def store_fact_with_provenance(
    self,
    user_id: str,
    fact: Fact,
    source_type: str,
    source_query: str,
    source_urls: List[str]
) -> bool:
    """Store a fact with provenance tracking."""
    # Implementation: Store to Neo4j with source metadata
    # MATCH (subj) ... MERGE ... SET r.source_type = $source_type, r.source_urls = $urls
```

### Phase 1E: Cross-Bot Sharing (30 min)

**File:** `src_v2/tools/search_tools.py`

```python
from src_v2.memory.shared_artifacts import shared_artifact_manager

class WebSearchTool(BaseTool):
    async def _share_search_discovery(self, query: str, key_fact: str, urls: List[str]):
        """Share significant search findings with other bots."""
        if not settings.ENABLE_STIGMERGIC_DISCOVERY:
            return
        
        await shared_artifact_manager.store_artifact(
            artifact_type="web_knowledge",
            content=f"Learned from web search '{query}': {key_fact}",
            source_bot=self.character_name or "unknown",
            confidence=0.85,
            metadata={
                "query": query,
                "source_urls": urls[:3],
                "learned_at": datetime.now(timezone.utc).isoformat()
            }
        )
```

### Phase 1F: Search Trace Learning (30 min)

**File:** `src_v2/tools/search_tools.py`

```python
from src_v2.memory.manager import memory_manager

class WebSearchTool(BaseTool):
    async def _store_search_trace(self, query: str, results_count: int, success: bool):
        """Store successful search patterns for future learning."""
        if not settings.ENABLE_TRACE_LEARNING or not success:
            return
        
        try:
            # Classify the query type for pattern matching
            query_type = self._classify_query_type(query)
            
            trace_content = f"Web search for '{query}' ({query_type}) returned {results_count} useful results"
            
            await memory_manager.store_reasoning_trace(
                content=trace_content,
                user_id=self.user_id or "__system__",
                collection_name=f"whisperengine_memory_{self.character_name or 'default'}",
                metadata={
                    "query_pattern": query_type,
                    "successful_approach": "web_search",
                    "tools_used": ["search_web"],
                    "complexity": "COMPLEX_MID"
                }
            )
        except Exception as e:
            logger.debug(f"Failed to store search trace: {e}")
    
    def _classify_query_type(self, query: str) -> str:
        """Classify query for pattern matching."""
        query_lower = query.lower()
        if any(w in query_lower for w in ["price", "cost", "stock", "bitcoin", "crypto"]):
            return "financial"
        elif any(w in query_lower for w in ["weather", "temperature", "forecast"]):
            return "weather"
        elif any(w in query_lower for w in ["news", "latest", "recent", "today"]):
            return "current_events"
        elif any(w in query_lower for w in ["who is", "what is", "define", "meaning"]):
            return "factual_lookup"
        elif any(w in query_lower for w in ["how to", "tutorial", "guide"]):
            return "how_to"
        else:
            return "general"
```

### Phase 1G: UX & Latency Handling (15 min)

**File:** `src_v2/discord/handlers/message_handler.py`

Since web search adds 2-3 seconds of latency, we need to ensure the user knows the bot is working.

```python
# In handle_message() or similar
async with channel.typing():
    # This is already standard practice, but ensure it covers the tool execution phase
    response = await self.agent_engine.generate_response(...)
```

**Note:** The `ReflectiveAgent` execution loop should already be wrapped in `typing()`, but we should verify this during testing.

### Phase 2: Router Integration (15 min)

**File:** `src_v2/agents/router.py`

Add to imports:
```python
from src_v2.tools.search_tools import WebSearchTool
```

Add to tools list in `route_and_retrieve()`:
```python
tools = [
    SearchSummariesTool(user_id=user_id),
    SearchEpisodesTool(user_id=user_id),
    LookupFactsTool(user_id=user_id, bot_name=character_name),
    UpdateFactsTool(user_id=user_id),
    UpdatePreferencesTool(user_id=user_id, character_name=character_name),
    AnalyzeTopicTool(user_id=user_id, bot_name=character_name),
    CheckPlanetContextTool(guild_id=guild_id),
    GetUniverseOverviewTool(),
]

# Add web search if enabled
if settings.ENABLE_WEB_SEARCH:
    tools.append(WebSearchTool(
        user_id=user_id,
        character_name=character_name
    ))
```

Update system prompt to include search guidance:
```python
system_prompt = """You are the Cognitive Router for an advanced AI companion.
Your goal is to determine if the user's message requires retrieving external memory, facts, or generating media.

AVAILABLE TOOLS:
[...existing tools...]
- search_web: For current events, real-time data, news, factual lookups beyond training data.

RULES:
[...existing rules...]
4. Use search_web ONLY for queries that require current/real-time information (news, weather, prices, recent events).
5. DO NOT use search_web for personal memories or user facts - use memory/knowledge tools instead.
6. Prefer internal knowledge (Neo4j) for facts the bot has previously learned from web searches.
[...]
"""
```

### Phase 3: Classifier Intent Detection (20 min)

**File:** `src_v2/agents/classifier.py`

Update the system prompt in `classify()` to include search intent:

```python
# Around line 165, where intents are defined
intent_descriptions = []

if settings.ENABLE_WEB_SEARCH:
    intent_descriptions.append('"search": User needs current information from the web (news, weather, real-time data, facts beyond training)')

if settings.ENABLE_VOICE_RESPONSES:
    intent_descriptions.append('"voice": User wants an audio/voice response')

if settings.ENABLE_IMAGE_GENERATION:
    intent_descriptions.append('"image": User wants an image generated, edited, or refined')
```

Add logic to promote search queries to COMPLEX:
```python
# After intent detection
if "search" in result_intents and complexity in ["SIMPLE", "COMPLEX_LOW"]:
    logger.info(f"Promoting {complexity} → COMPLEX_MID due to 'search' intent")
    complexity = "COMPLEX_MID"
```

### Phase 4: Settings & Feature Flag (10 min)

**File:** `src_v2/config/settings.py`

Add settings:
```python
# Web Search Settings
ENABLE_WEB_SEARCH: bool = Field(
    default=False,
    description="Enable web search via DuckDuckGo for current information"
)
WEB_SEARCH_MAX_RESULTS: int = Field(
    default=5,
    description="Maximum search results to return per query (1-10)"
)
```

**Files:** `.env.example`, `.env.elena`, etc.

Add to env templates:
```bash
# Web Search (DuckDuckGo)
ENABLE_WEB_SEARCH=false
WEB_SEARCH_MAX_RESULTS=5
```

### Phase 5: Testing (45 min)

**File:** `tests_v2/test_web_search.py`

```python
"""
Tests for Web Search Tool (DuckDuckGo integration).
"""
import pytest
from src_v2.tools.search_tools import WebSearchTool
from src_v2.config.settings import settings


@pytest.mark.asyncio
async def test_web_search_basic():
    """Test basic web search returns results."""
    tool = WebSearchTool()
    result = await tool._arun("Python programming language")
    
    assert "Web Search Results" in result
    assert "Python" in result
    assert "Source:" in result


@pytest.mark.asyncio
async def test_web_search_current_events():
    """Test search for current information."""
    tool = WebSearchTool()
    result = await tool._arun("latest AI news 2025")
    
    assert len(result) > 100  # Should have substantial content
    assert "No web results" not in result


@pytest.mark.asyncio
async def test_web_search_max_results():
    """Test max_results parameter."""
    tool = WebSearchTool()
    result = await tool._arun("coffee", max_results=3)
    
    # Should have exactly 3 results
    assert result.count("Source:") == 3


@pytest.mark.asyncio
async def test_web_search_empty_query():
    """Test handling of edge cases."""
    tool = WebSearchTool()
    result = await tool._arun("")
    
    # Should handle gracefully
    assert "Error" in result or "No web results" in result


@pytest.mark.asyncio
async def test_web_search_integration_with_router():
    """Test web search is available in router when enabled."""
    # Save original setting
    original = settings.ENABLE_WEB_SEARCH
    
    try:
        # Enable web search
        settings.ENABLE_WEB_SEARCH = True
        
        from src_v2.agents.router import CognitiveRouter
        router = CognitiveRouter()
        
        result = await router.route_and_retrieve(
            user_id="test_user",
            query="What's the weather in Tokyo?",
            chat_history=[]
        )
        
        # Should have search results in context
        assert result is not None
        
    finally:
        # Restore original setting
        settings.ENABLE_WEB_SEARCH = original
```

Add to regression suite (`tests_v2/regression/test_search.py`):
```python
"""Regression tests for web search functionality."""

async def test_search_current_events(api_client, bot_name):
    """Test bot can search for current events."""
    response = await api_client.post("/api/chat", json={
        "user_id": "test_search_user",
        "message": "What's the latest news about artificial intelligence?"
    })
    
    assert response.status_code == 200
    data = response.json()
    
    # Should contain web search results
    assert len(data["response"]) > 50
    # Should mention sources or indicate web search
    assert "according to" in data["response"].lower() or "source" in data["response"].lower()


async def test_search_real_time_data(api_client, bot_name):
    """Test bot can fetch real-time information."""
    response = await api_client.post("/api/chat", json={
        "user_id": "test_search_user",
        "message": "What's the current price of gold?"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "$" in data["response"] or "price" in data["response"].lower()
```

### Phase 6: Documentation (30 min)

Update the following docs:

**File:** `docs/architecture/COGNITIVE_ENGINE.md`
- Add web search to tool descriptions
- Update reasoning flow diagrams

**File:** `docs/API_REFERENCE.md`
- Document web search as available tool
- Add example requests that trigger search

**File:** `.github/copilot-instructions.md`
- Add web search to "Message Flow" section
- Update feature flags list

**File:** `README.md`
- Add web search to feature list
- Update capabilities section

---

## ⚙️ Configuration

### Feature Flag Behavior

| Setting | Value | Behavior |
|---------|-------|----------|
| `ENABLE_WEB_SEARCH=false` | (default) | Web search tool NOT available, classifier doesn't detect "search" intent |
| `ENABLE_WEB_SEARCH=true` | | Web search tool available in router, classifier promotes search queries to COMPLEX_MID |

### Cost Analysis

| Component | Cost | Notes |
|-----------|------|-------|
| DuckDuckGo API | **FREE** | No API key, no rate limits (reasonable use) |
| LLM for classification | ~$0.0001 | Only when `ENABLE_WEB_SEARCH=true` (adds search intent check) |
| LLM for synthesis | ~$0.003-0.01 | Same as existing COMPLEX_MID queries |

**Total added cost per search:** ~$0.003-0.01 (LLM processing only, search is free)

### Rate Limiting

DuckDuckGo has informal rate limits:
- ~1-2 queries per second max
- No daily caps for reasonable use

**Implementation strategy:** No explicit rate limiting needed initially. If abuse occurs, add:
```python
# In search_tools.py
from src_v2.core.quota import QuotaManager

search_quota = QuotaManager("web_search", daily_limit=50)  # 50 searches/day per user
```

---

## 🧪 Testing Strategy

### Manual Testing on Elena

1. **Enable feature:** Set `ENABLE_WEB_SEARCH=true` in `.env.elena`
2. **Restart bot:** `./bot.sh restart elena`
3. **Test queries:**
   ```
   @Elena what's the weather in San Francisco?
   @Elena latest AI news
   @Elena what's the current price of Bitcoin?
   @Elena who won the Super Bowl this year?
   ```
4. **Verify:**
   - Bot searches web instead of saying "I don't know"
   - Results are recent and relevant
   - Sources are cited
   - No hallucination of facts

### Automated Testing

```bash
# Run unit tests
pytest tests_v2/test_web_search.py -v

# Run regression test
python tests_v2/run_regression.py --bot elena --category search
```

### Performance Testing

Monitor these metrics in InfluxDB:
- `tool_execution_time` (should be <3 seconds for web search)
- `complexity_classification` with `intent_search=1`
- Search query patterns and frequency

---

## 🚨 Edge Cases & Error Handling

### Error Scenarios

| Scenario | Handling |
|----------|----------|
| DuckDuckGo unreachable | Return "Unable to reach search service" |
| No results found | Return "No web results found for query" |
| Malformed query | Let DuckDuckGo handle (it's forgiving) |
| Rate limit hit | Catch exception, return error gracefully |
| Unicode/special chars | Library handles automatically |

### Search Quality Issues

**Problem:** User asks "What did I say about turtles?" (memory query) but classifier detects "search" intent.

**Solution:** Router system prompt explicitly guides LLM:
- "DO NOT use search_web for personal memories"
- Router has both memory tools AND search tool
- LLM chooses correct tool based on context

**Problem:** Bot hallucinates facts even with web search available.

**Solution:** 
- Classifier promotes search queries to COMPLEX_MID → forces tool use
- Reflective agent MUST call tools before responding
- Web results are injected into context with clear attribution

### WhisperEngine-Specific Risks

| Risk | Mitigation |
|------|------------|
| **Neo4j pollution:** Storing low-quality facts | Only persist facts with confidence > 0.8; require trust >= Friend |
| **Cross-bot misinformation:** Bad search propagates | Shared artifacts have confidence scores; discovery filters by threshold |
| **Stale knowledge:** Old search facts persist | Add `learned_at` timestamp; optionally expire after N days |
| **Over-searching:** Bot searches too often | Check Neo4j first for web-learned facts; trace learning improves routing |
| **Trust gaming:** Users ask lots to get deeper search | Trust increases slowly via genuine engagement, not query count |

---

## 📊 Success Metrics

Track these to measure feature effectiveness:

1. **Adoption:** % of queries that trigger web search
2. **Accuracy:** User reactions to search-based responses (👍 vs 👎)
3. **Performance:** Average search tool execution time
4. **Cost:** LLM token usage for search-enhanced responses
5. **Errors:** Failed search rate, timeout rate

**Target metrics (after 1 week on elena):**
- Search adoption: 5-10% of complex queries
- Positive reaction rate: >80%
- Average search time: <2 seconds
- Error rate: <5%

---

## 🔄 Future Enhancements (Out of Scope)

These are NOT part of Phase 1 but could be added later:

### Phase 2: Search Result Caching (1-2 hours)
- Cache search results in Redis for 1 hour
- Deduplicate identical queries across users
- Reduces redundant API calls

### Phase 3: News-Aware Conversations (2-3 hours)
- Periodic background fetch of trending topics
- Bot can proactively mention relevant news
- "I saw something about X in the news—thoughts?"

### Phase 4: Observation Enhancement (1-2 hours)
- Add `WebSearchTool` to `InsightAgent`
- Update Insight Agent prompt to encourage curiosity
- Store "enhanced observations" in memory

### Phase 5: Fact-Check Mode (1-2 hours)
- Explicit "verify this" capability
- Bot searches specifically to debunk/confirm a statement
- Returns boolean verdict + sources

### Phase 6: Multi-Source Search (3-4 hours)
- Add Wikipedia API for encyclopedic queries
- Add specialized APIs (weather, stocks, news)
- Router intelligently picks best source

### Phase 7: Backend Enrichment (2-3 hours)
- Integrate `WebSearchTool` into `DiaryManager`
- Integrate `WebSearchTool` into `DreamManager`
- Add logic to identify "low-context" observations needing search

### Phase 8: Search Quality Ranking (2-3 hours)
- Score search results by relevance
- Filter low-quality/spam results
- Prefer authoritative sources

### Phase 9: Image Search (2-3 hours)
- Add DuckDuckGo image search
- Return image URLs for reference
- Integrate with vision fact extraction

---

## 🔗 Related Features

This feature enables/enhances:

1. **Real-Time Information:** Current events, news, weather
2. **Fact Checking:** Verify user claims against web sources
3. **Research Assistant:** Deep dives into topics with web evidence
4. **Knowledge Expansion:** Learn new information dynamically
5. **Source Attribution:** Cite where information comes from

This feature depends on:
- Reflective Agent (tool execution)
- Complexity Classifier (intent detection)
- Router (tool selection)

This feature conflicts with:
- None (purely additive)

---

## 🎓 Developer Notes

### Why Not LangChain's DuckDuckGoSearchResults?

LangChain has a built-in `DuckDuckGoSearchResults` tool, but we're implementing our own because:

1. **Customization:** We need specific formatting for our LLM context
2. **Logging:** Want detailed logs for observability
3. **Error handling:** Need graceful degradation
4. **Rate limiting:** May add quota system later
5. **Simplicity:** Direct use of `duckduckgo-search` library is cleaner

If we wanted to use LangChain's version:
```python
from langchain_community.tools import DuckDuckGoSearchResults

tool = DuckDuckGoSearchResults()
```

But we have more control with our own implementation.

### Adding to Existing Bot Without Restart

Once implemented, enable on running bot:
```bash
# Update .env.elena
echo "ENABLE_WEB_SEARCH=true" >> .env.elena

# Restart just elena (one bot only)
./bot.sh restart elena
```

For production rollout:
1. Test on **elena** (dev primary) for 24-48 hours
2. Test on **dotty** (personal) for validation
3. Enable on **test bots** (aria, dream, jake, etc.) for A/B testing
4. Finally enable on **nottaylor** (production)

### Debugging Search Issues

If search returns bad results:
```python
# Add detailed logging in search_tools.py
logger.debug(f"Raw DDG results: {results}")
logger.debug(f"Formatted for LLM: {response[:500]}")
```

Check InfluxDB for search patterns:
```flux
from(bucket: "whisperengine")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "complexity_classification")
  |> filter(fn: (r) => r.intent_search == 1)
```

---

## ✅ Definition of Done

Feature is complete when:

### Core Implementation
- [ ] `src_v2/tools/search_tools.py` implemented with `WebSearchTool`
- [ ] `duckduckgo-search` added to requirements.txt
- [ ] Router integration complete (tools list + system prompt)
- [ ] Classifier detects "search" intent and promotes to COMPLEX_MID
- [ ] Settings added (`ENABLE_WEB_SEARCH`, `WEB_SEARCH_MAX_RESULTS`)

### WhisperEngine-Unique Features
- [ ] Provenance tracking: `SourceType.WEB_SEARCH` added to provenance system
- [ ] Trust-gated depth: Search depth varies by relationship level
- [ ] Knowledge persistence: Extracted facts stored to Neo4j with source URLs
- [ ] Cross-bot sharing: Web knowledge stored as shared artifacts
- [ ] Trace learning: Successful search patterns stored for future routing

### Testing & Documentation
- [ ] Unit tests pass (`tests_v2/test_web_search.py`)
- [ ] Manual testing on elena successful (basic + trust-gated)
- [ ] Regression tests pass with search enabled
- [ ] Documentation updated (API_REFERENCE, COGNITIVE_ENGINE, README)
- [ ] Provenance footer displays correctly for search-grounded responses

### Quality Metrics
- [ ] No performance degradation (response time <5 seconds including search)
- [ ] Cost per search <$0.01
- [ ] Knowledge persistence working (re-query doesn't trigger new search)
- [ ] Cross-bot discovery working (second bot finds first bot's knowledge)

---

## 📚 References

- **DuckDuckGo Search Library:** https://github.com/deedy5/duckduckgo_search
- **LangChain Tools Pattern:** `src_v2/tools/memory_tools.py` (reference implementation)
- **Router Integration:** `src_v2/agents/router.py` (tool registration)
- **Classifier Intents:** `src_v2/agents/classifier.py` (intent detection)
- **Feature Flags:** `docs/architecture/CONFIGURATION.md` (settings patterns)

---

**Document Version:** 1.2  
**Status:** 📋 Ready for Implementation  
**Estimated Total Time:** 5-7 hours (solo dev, includes unique features)  
**Priority:** MEDIUM (enables current information access + builds on existing architecture)  
**Risk Level:** LOW (free API, well-tested library, leverages existing systems)
