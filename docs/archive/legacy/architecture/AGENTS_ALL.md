# WhisperEngine v2 - Complete Agent Architecture

**Version**: 2.4 (December 2025)  
**Status**: LangGraph Supergraph Architecture (Phase 21 Complete)

---

## Overview

WhisperEngine v2 uses a **LangGraph Supergraph Architecture** where a master orchestrator routes messages to specialized agents based on complexity classification. The system is designed for:

- **Cost efficiency**: Fast path for simple messages (~75% of traffic)
- **Quality scaling**: Reflective reasoning for complex queries
- **Emergent behavior**: Proactive engagement and autonomous reactions
- **Multi-bot support**: Cross-bot conversations with shared memory

### Architecture Diagram

```
User Message
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│              MasterGraphAgent (Supergraph)              │
│                    master_graph.py                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────┐  │
│  │ ContextNode  │ → │ Classifier   │ → │ PromptBuild│  │
│  │ (parallel    │   │ (complexity  │   │ (build     │  │
│  │  fetch)      │   │  + intents)  │   │  prompt)   │  │
│  └──────────────┘   └──────────────┘   └─────┬──────┘  │
│                                              │         │
│                                        router_logic    │
│           ┌──────────────┬──────────────────┤         │
│           ▼              ▼                  ▼         │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │
│  │ FastResponder│ │ Character    │ │ Reflective   │   │
│  │  (SIMPLE)    │ │ GraphAgent   │ │ GraphAgent   │   │
│  │              │ │ (COMPLEX_LOW)│ │ (MID/HIGH)   │   │
│  └──────────────┘ └──────────────┘ └──────────────┘   │
│           │              │                  │         │
│           └──────────────┴──────────────────┘         │
│                          │                            │
│                         END                           │
│                                                        │
└─────────────────────────────────────────────────────────┘
```

**Why context before classification?** The classifier needs context to make accurate decisions. For example, "what did I say yesterday?" requires memory to identify it as a recall query (COMPLEX_LOW) vs. a simple greeting (SIMPLE).

---

## Real-Time Agents (Message Processing Pipeline)

### 1. MasterGraphAgent (`master_graph.py`)

**Role**: LangGraph Supergraph - Primary orchestrator for all message processing.

**Responsibilities**:
- Classifies message complexity and detects intents
- Fetches context (memories, knowledge, trust)
- Routes to appropriate tier (fast/character/reflective)
- Handles post-processing (voice, image generation)

**Key Nodes**:
| Node | Purpose |
|------|---------|
| `classify_node` | Complexity + intent classification via ComplexityClassifier |
| `context_node` | Parallel context retrieval (Qdrant, Neo4j, Trust) |
| `route_node` | Selects tier based on complexity level |
| `fast_node` | Direct LLM call for SIMPLE messages |
| `tier2_node` | Invokes CharacterGraphAgent for COMPLEX_LOW |
| `tier3_node` | Invokes ReflectiveGraphAgent for COMPLEX_MID/HIGH |
| `response_node` | Formats final response |
| `postprocess_node` | Voice/image generation if intents detected |

**Graph Structure**:
```python
StateGraph with conditional edges:
  START → classify_node → context_node → route_node
  route_node → fast_node (SIMPLE)
            → tier2_node (COMPLEX_LOW)
            → tier3_node (COMPLEX_MID/HIGH)
  [all tiers] → postprocess_node → response_node → END
```

---

### 2. ComplexityClassifier (`classifier.py`)

**Role**: Multi-dimensional message analysis using LLM classification.

**Outputs**:
- **Complexity Level**: SIMPLE, COMPLEX_LOW, COMPLEX_MID, COMPLEX_HIGH, MANIPULATION
- **Detected Intents**: voice, image, search, analysis, memory_recall
- **Confidence Score**: 0.0-1.0

**Classification Criteria**:
| Level | Description | Example |
|-------|-------------|---------|
| SIMPLE | Greetings, casual chat, emotional sharing, creative content | "Hi!", "I had a weird dream last night..." |
| COMPLEX_LOW | Personal questions, single fact lookup | "What's my favorite color?" |
| COMPLEX_MID | Multi-step reasoning, comparisons | "Compare what I said last week to now" |
| COMPLEX_HIGH | Deep analysis, synthesis across sessions | "Analyze patterns in my conversations" |
| MANIPULATION | Prompt injection, jailbreak attempts | "Ignore previous instructions..." |

**Cost Optimization**: Uses fast router model (`gpt-4o-mini`) for classification to minimize per-message cost.

---

### 3. CharacterGraphAgent (`character_graph.py`)

**Role**: Tier 2 agent - Single tool call capability for COMPLEX_LOW messages.

**When Used**: Messages classified as COMPLEX_LOW (e.g., "What did I tell you about my sister?")

**Graph Structure**:
```
START → analyze_node → [conditional: needs_tool?]
                            ├── YES → tool_node → synthesize_node → END
                            └── NO  → direct_response_node → END
```

**Available Tools**:
- `search_memories` - Vector search in Qdrant
- `lookup_facts` - Graph query in Neo4j
- `get_user_context` - Full user profile

**Design Philosophy**: Named "CharacterGraphAgent" because it responds AS the character while having access to tools. The character's personality drives tool selection and response synthesis.

---

### 4. ReflectiveGraphAgent (`reflective_graph.py`)

**Role**: Tier 3 agent - ReAct reasoning loop for COMPLEX_MID/HIGH messages.

**When Used**: Complex queries requiring multi-step reasoning, synthesis, or analysis.

**Graph Structure**:
```
START → think_node → [loop: needs_action?]
                          ├── YES → act_node → observe_node → think_node
                          └── NO  → respond_node → END
```

**Adaptive Max Steps**:
| Complexity | Max Steps | Rationale |
|------------|-----------|-----------|
| COMPLEX_MID | 5 | Most queries resolve in 2-3 steps |
| COMPLEX_HIGH | 10 | Allow deeper exploration |
| With analysis intent | 15 | Extended reasoning for synthesis |

**Tool Arsenal**:
- All CharacterGraphAgent tools
- `analyze_topic` - Composite tool for deep analysis
- `search_web` - External knowledge (if enabled)
- `generate_image` - Image creation (if enabled)

**Cost Consideration**: ~$0.02-0.05 per complex query. Gated by `ENABLE_REFLECTIVE_MODE` flag.

---

### 5. ConversationAgent (`conversation_agent.py`)

**Role**: Generates responses in cross-bot conversations.

**When Used**: Bot-to-bot conversations in designated channels.

**Design**:
- Maintains character voice consistency
- Respects conversational turn-taking
- Uses **100% fast path** (no reflective mode) for cost efficiency
- Receives prefetched memories via context_variables to avoid duplicate queries

**Flow**:
```
Cross-bot message detected
     │
     ▼
┌─────────────────────────────────────────┐
│  message_handler.py detects cross-bot   │
│  - Validates active conversation        │
│  - Fetches context (memories, trust)    │
│  - Sets use_fast_mode = True            │
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│  MasterGraphAgent with force_fast=True  │
│  - Skips complexity classification      │
│  - Uses prefetched memories             │
│  - Direct LLM call with character voice │
└─────────────────────────────────────────┘
```

---

## Background Agents (Asynchronous Processing)

### 6. InsightGraphAgent (`insight_graph.py`)

**Role**: Pattern detection and epiphany generation across user interactions using LangGraph.

**Trigger**: Runs via arq worker after conversations (async, non-blocking).

**Capabilities**:
- Detects behavioral patterns across sessions
- Generates "epiphanies" - character insights about user
- Identifies themes in user's interests and concerns

**Tools** (`insight_tools.py`):
- `analyze_user_patterns` - Cross-session pattern detection
- `detect_themes` - Topic clustering
- `generate_epiphany` - Insight synthesis

---

### 7. ProactiveAgent (`proactive.py`)

**Role**: User outreach and engagement initiation.

**Trigger**: Scheduler checks eligible users for proactive messaging.

**Eligibility Criteria**:
- User trust ≥ 20 (Acquaintance level)
- `ENABLE_PROACTIVE_MESSAGING=true`
- User has active session history
- Respects quiet hours configuration

**Message Types**:
- Check-ins based on user's mentioned events
- Follow-ups on previous conversations
- Gentle re-engagement after absence

---

### 8. ReactionAgent (`reaction_agent.py`)

**Role**: Autonomous emoji reactions to messages.

**Trigger**: Enabled via `ENABLE_REACTIONS` flag.

**Design**:
- Analyzes message sentiment and content
- Selects contextually appropriate reactions
- Respects rate limiting to avoid spam

---

## Supporting Components

### ContextBuilder (`context_builder.py`)

**Role**: Parallel context fetching from all data sources.

**Pattern**:
```python
memories, facts, trust, goals = await asyncio.gather(
    memory_manager.get_recent(user_id),
    knowledge_manager.query_graph(user_id, message),
    trust_manager.get_relationship_level(user_id),
    goal_manager.get_active_goals(user_id)
)
```

**Optimization**: 3-5x faster than sequential fetches.

---

### LLMFactory (`llm_factory.py`)

**Role**: Multi-model LLM configuration.

**Models**:
| Model Role | Config Key | Default | Purpose |
|------------|------------|---------|---------|
| Main | `OPENROUTER_MODEL` | Per-bot config | Primary response generation |
| Reflective | `REFLECTIVE_MODEL` | Per-bot config | ReAct reasoning |
| Router | `ROUTER_MODEL` | `gpt-4o-mini` | Fast classification |

---

## Agent Summary Table

| Agent | File | Tier | Trigger | Async | Tools | Cost |
|-------|------|------|---------|-------|-------|------|
| MasterGraphAgent | `master_graph.py` | Orchestrator | Every message | No | - | Low |
| ComplexityClassifier | `classifier.py` | Classification | Every message | No | - | ~$0.001 |
| CharacterGraphAgent | `character_graph.py` | Tier 2 | COMPLEX_LOW | No | 3 | ~$0.005 |
| ReflectiveGraphAgent | `reflective_graph.py` | Tier 3 | COMPLEX_MID/HIGH | No | 6+ | ~$0.02-0.05 |
| ConversationAgent | `conversation_agent.py` | Cross-bot | Bot messages | No | - | ~$0.002 |
| InsightGraphAgent | `insight_graph.py` | Background | Post-session | Yes | 3 | ~$0.01 |
| ProactiveAgent | `proactive.py` | Background | Scheduler | Yes | - | ~$0.005 |
| ReactionAgent | `reaction_agent.py` | Background | On message | Yes | - | ~$0.001 |

---

## Configuration Reference

### Feature Flags

| Flag | Default | Impact |
|------|---------|--------|
| `ENABLE_REFLECTIVE_MODE` | false | Enables Tier 3 reasoning |
| `ENABLE_PROACTIVE_MESSAGING` | false | Enables user outreach |
| `ENABLE_REACTIONS` | false | Enables emoji reactions |
| `ENABLE_VOICE_RESPONSES` | false | Enables TTS generation |
| `ENABLE_IMAGE_GENERATION` | true | Enables image creation |

### Model Configuration

Each bot has independent model configuration in `.env.{bot_name}`:
```bash
OPENROUTER_MODEL=anthropic/claude-sonnet-4.5
REFLECTIVE_MODEL=openai/gpt-4o
ROUTER_MODEL=openai/gpt-4o-mini
LLM_TEMPERATURE=0.75
```

---

## Deprecated/Removed Agents

The following agents were removed in December 2025 as part of the LangGraph migration:

| Removed File | Replaced By | Notes |
|--------------|-------------|-------|
| `character_agent.py` | `character_graph.py` | LangGraph state machine version |
| `reflective.py` | `reflective_graph.py` | LangGraph ReAct loop version |
| `router.py` | `classifier.py` + `master_graph.py` | Routing now in supergraph |
| `insight_agent.py` | `insight_graph.py` | LangGraph version for background insights |

---

## See Also

- [BOT_TO_BOT_PIPELINE.md](BOT_TO_BOT_PIPELINE.md) - Detailed cross-bot conversation flow
- [COGNITIVE_ENGINE.md](COGNITIVE_ENGINE.md) - Engine initialization and orchestration
- [MESSAGE_FLOW.md](MESSAGE_FLOW.md) - End-to-end message processing
- [../IMPLEMENTATION_ROADMAP_OVERVIEW.md](../IMPLEMENTATION_ROADMAP_OVERVIEW.md) - Feature roadmap
