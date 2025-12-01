# WhisperEngine v2 - Agent Architecture

**Version**: 2.2  
**Last Updated**: December 1, 2025

This document provides a comprehensive overview of all agents in the WhisperEngine cognitive system.

**For entry point details**, see [Cognitive Engine Architecture](./COGNITIVE_ENGINE.md) for the main orchestrator (`AgentEngine`) and request routing logic.

## Overview

WhisperEngine uses a **Dual-Process Cognitive Architecture** with multiple specialized agents. The system routes messages through different processing paths based on complexity, with background agents handling learning and creative tasks asynchronously.

## Architecture Diagram

```
User Message
     │
     ▼
┌─────────────────┐
│  AgentEngine    │
│  (orchestrator) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Classifier     │──────────────────┐
│  (complexity)   │                  │
└────────┬────────┘                  │
         │                           │
    ┌────┴────┬───────────┐          │
    │         │           │          │
    ▼         ▼           ▼          ▼
 SIMPLE   COMPLEX_LOW  COMPLEX_MID+  MANIPULATION
    │         │           │          │
    ▼         ▼           ▼          ▼
  Direct  Character   Reflective   Rejection
   LLM     Agent       Agent       Response
    │         │           │
    └────┬────┴───────────┘
         │
         ▼
    Response + Post-processing
    (facts, voice, images, reactions)
```

---

## Real-Time Agents

These agents process user messages during active conversations.

### 1. AgentEngine (`src_v2/agents/engine.py`)

**Role**: Core orchestrator and main entry point

The `AgentEngine` is the central brain that coordinates all response generation.

**Responsibilities**:
- Receives user messages and determines how to process them
- Classifies message complexity (SIMPLE → COMPLEX_HIGH → MANIPULATION)
- Routes to the appropriate agent based on complexity
- Handles image/multimodal inputs
- Injects context (trust level, memories, knowledge graph facts)
- Logs prompts and tracks metrics

**Key Method**: `generate_response()`

**Flow**: `Discord Message → AgentEngine → Classifier → Route to appropriate agent → Response`

---

### 2. ComplexityClassifier (`src_v2/agents/classifier.py`)

**Role**: Intent detection and complexity assessment

Analyzes incoming messages to determine processing requirements.

**Complexity Levels**:
| Level | Description | Processing Path |
|-------|-------------|-----------------|
| `SIMPLE` | Casual chat, greetings | Fast path (single LLM call) |
| `COMPLEX_LOW` | Single lookup needed | CharacterAgent (one tool) |
| `COMPLEX_MID` | Multi-step reasoning | ReflectiveAgent (ReAct loop) |
| `COMPLEX_HIGH` | Deep research required | ReflectiveAgent (extended) |
| `MANIPULATION` | Adversarial probing | Rejection response |

**Detected Intents**:
- `voice` - User wants audio response (TTS)
- `image_self` / `image_refine` - User wants image generation
- `search` - User wants to search memories

**Features**:
- **Adaptive Depth**: Uses historical reasoning traces from Qdrant to skip reclassification for similar queries
- **Fast-path refinement detection**: Recognizes image refinement requests without LLM call

---

### 3. CharacterAgent (`src_v2/agents/character_agent.py`)

**Role**: Tier 2 "Agency Mode" - single tool call + response

Used for `COMPLEX_LOW` queries where a single lookup is needed before responding.

**Two-LLM Approach**:
1. **Router LLM** (fast/cheap): Decides which tool to call
2. **Main LLM** (quality): Generates the character's response with tool results

**Available Tools**:
- `search_archived_summaries` - Past conversations
- `search_specific_memories` - Specific details and quotes
- `lookup_user_facts` - Knowledge graph facts
- `explore_knowledge_graph` - Relationship exploration
- `discover_common_ground` - Shared interests
- `get_character_evolution` - Trust level check
- `check_planet_context` - Server/planet context
- `get_universe_overview` - Cross-server view
- `search_channel_messages` - Channel search
- `generate_image` - Image generation (if enabled)
- `calculator` - Math calculations

**Example Use Case**: 
- User: "What's my cat's name?" 
- Agent calls `lookup_user_facts` → retrieves "User has a cat named Whiskers" → responds naturally

---

### 4. ReflectiveAgent (`src_v2/agents/reflective.py`)

**Role**: Full ReAct (Reasoning + Acting) loop for complex queries

Used for `COMPLEX_MID` and `COMPLEX_HIGH` queries requiring multi-step reasoning.

**ReAct Loop**:
```
Think → Act → Observe → Think → Act → Observe → ... → Final Response
```

**Features**:
- **Parallel tool execution**: Runs independent tools simultaneously
- **Adaptive max steps**: 10 for MID, 15 for HIGH complexity
- **Few-shot trace injection**: Learns from past successful reasoning patterns
- **Full tool suite**: 15+ tools including memory, knowledge graph, Discord search, image generation, reminders, math

**Tool Categories**:
| Category | Tools |
|----------|-------|
| Memory | `SearchSummariesTool`, `SearchEpisodesTool`, `SearchMyThoughtsTool` |
| Knowledge | `LookupFactsTool`, `UpdateFactsTool`, `ExploreGraphTool` |
| Discord | `SearchChannelMessagesTool`, `SearchUserMessagesTool`, `GetMessageContextTool` |
| Universe | `CheckPlanetContextTool`, `GetUniverseOverviewTool` |
| Insight | `AnalyzePatternsTool`, `DetectThemesTool`, `DiscoverCommunityInsightsTool` |
| Media | `GenerateImageTool` |
| Utility | `SetReminderTool`, `CalculatorTool`, `CreateUserGoalTool` |

**Example Use Case**:
- User: "Tell me everything we've discussed about my career goals and recommend next steps"
- Agent: Searches summaries → Searches episodes → Looks up facts → Synthesizes comprehensive response

---

### 5. CognitiveRouter (`src_v2/agents/router.py`)

**Role**: Memory tool selection and context retrieval

The "brain" that decides which memory tools to use for context gathering.

**Characteristics**:
- Low temperature (0.0) for deterministic decisions
- Logs reasoning transparency (why each tool was chosen)
- Can call multiple tools simultaneously

**Note**: Not a standalone agent - used by the engine for context pre-fetching in the response pipeline.

---

### 6. ContextBuilder (`src_v2/agents/context_builder.py`)

**Role**: System prompt construction and context injection

Builds the full context for any agent by assembling:
- Trust/relationship level
- Active goals and strategies
- Knowledge graph facts
- Diary and dream context
- Feedback-derived preferences
- Stigmergic discovery (insights from other bots)

---

## Background Agents

These agents run asynchronously, either in worker containers or on scheduled triggers.

### 7. ProactiveAgent (`src_v2/agents/proactive.py`)

**Role**: Initiates contact with users

Generates proactive opening messages when the bot reaches out first.

**Features**:
- Gathers context (recent memories, knowledge facts, trust level)
- **Privacy-aware**: Sanitizes sensitive topics for public channels
- **Drive-based**: Can be motivated by internal character drives (Phase 3.3)
- **Timezone-aware**: Uses character's timezone for contextual greetings

**Trigger**: Scheduler (`src_v2/discord/scheduler.py`)

**Example Use Case**: Bot DMs a trusted user: "Hey! How did that job interview go?"

---

### 8. ReactionAgent (`src_v2/agents/reaction_agent.py`)

**Role**: Autonomous emoji reactions (Phase E12)

Decides when and what emoji reactions to add in channels.

**Design Philosophy**:
- **No LLM calls** - Keep it fast and cheap
- **Character-specific**: Emoji sets defined in `ux.yaml`
- **Rate-limited**: Per-channel and per-user cooldowns
- **Activity-aware**: Reacts less when many humans are active

**Emoji Categories**:
| Category | Example Emojis |
|----------|----------------|
| Positive | ❤️ ✨ 🔥 💯 |
| Thinking | 🤔 💭 👀 |
| Agreement | 👍 💯 ✅ |
| Excitement | 🎉 🙌 ⭐ |
| Supportive | 💜 🫂 💪 |
| Signature | Character-specific |

**Rate Limits** (configurable):
- `REACTION_CHANNEL_HOURLY_MAX`: 10 per channel per hour
- `REACTION_SAME_USER_COOLDOWN_SECONDS`: 300 seconds
- `REACTION_DAILY_MAX`: 100 per day

---

### 9. InsightAgent (`src_v2/agents/insight_agent.py`)

**Role**: Background learning and pattern detection

Runs asynchronously in a worker container, analyzing conversations to generate learning artifacts.

**Generated Artifacts**:
- **Reasoning traces**: Successful approaches for reuse
- **Epiphanies**: Spontaneous realizations about users
- **Response patterns**: What styles resonate with each user

**Triggers**:
| Trigger | Description |
|---------|-------------|
| `volume` | User has sent many messages recently |
| `time` | Scheduled periodic analysis |
| `session_end` | Conversation session just ended |
| `feedback` | User gave positive reactions recently |
| `reflective_completion` | A reflective reasoning session just completed |

**Example Output**: Stores insight "User prefers technical depth over simplification"

---

### 10. DreamWeaverAgent (`src_v2/agents/dreamweaver.py`)

**Role**: Narrative generation for dreams and diaries

Specialized agent for batch-mode creative writing, generating rich character narratives.

**Two-Phase Approach**:
1. **PLANNING**: Decides story arc, emotional arc, symbols, tone
2. **WEAVING**: Gathers data via tools, synthesizes into narrative

**Narrative Plan Structure**:
```python
class NarrativePlan:
    story_arc: str       # Setup, journey, resolution
    emotional_arc: str   # What feelings to evoke
    key_threads: List[str]  # Main narrative threads
    symbols_to_use: List[str]  # Symbolic imagery
    tone: str            # e.g., "dreamy and hopeful"
```

**Features**:
- Higher temperature (0.7) for creativity
- Extended max steps (15) - batch mode allows more time
- **Voice synthesis**: Rewrites content in the character's authentic voice
- Metrics tracking for dream generation

**Trigger**: Cron job (typically 3 AM in character's timezone)

---

## LLM Factory (`src_v2/agents/llm_factory.py`)

**Role**: Model configuration and multi-LLM support

Creates LangChain chat models based on configuration. Supports multiple LLM modes for cost/quality optimization.

**LLM Modes**:
| Mode | Purpose | Typical Model |
|------|---------|---------------|
| `main` | Character voice | Claude Sonnet, GPT-4o |
| `router` | Fast routing decisions | GPT-4o-mini |
| `reflective` | Deep reasoning | Claude Sonnet, GPT-4o |
| `utility` | Structured tasks | GPT-4o-mini |

**Supported Providers**:
- OpenAI (direct)
- OpenRouter (multi-model gateway)
- Ollama (local)
- LM Studio (local)

---

## Composite Tools (`src_v2/agents/composite_tools.py`)

Meta-tools that compose multiple tool calls into a single operation.

### AnalyzeTopicTool

Comprehensive research tool that searches summaries, episodes, and facts simultaneously.

**Use Case**: "Tell me everything about X" queries

**Output Format**:
```
[ANALYSIS FOR: topic]

--- SUMMARIES ---
Found N Summaries:
- [Score: X/5] content (date)

--- EPISODES ---
Found N Episodes:
- specific memory content

--- FACTS ---
Graph Query Result: relationship data
```

---

## Agent Summary Table

| Agent | File | Mode | LLM Calls | Purpose |
|-------|------|------|-----------|---------|
| AgentEngine | `engine.py` | Real-time | Orchestrator | Main coordinator |
| ComplexityClassifier | `classifier.py` | Real-time | 1 (router) | Intent/complexity detection |
| CharacterAgent | `character_agent.py` | Real-time | 2 (router + main) | Single-tool queries |
| ReflectiveAgent | `reflective.py` | Real-time | N (loop) | Multi-step reasoning |
| CognitiveRouter | `router.py` | Real-time | 1 (router) | Context retrieval |
| ContextBuilder | `context_builder.py` | Real-time | 0 | Prompt assembly |
| ProactiveAgent | `proactive.py` | Scheduled | 1 (main) | Initiate contact |
| ReactionAgent | `reaction_agent.py` | Event-driven | 0 | Emoji reactions |
| InsightAgent | `insight_agent.py` | Background | N (loop) | Pattern learning |
| DreamWeaverAgent | `dreamweaver.py` | Batch | N (loop) | Narrative generation |

---

## Feature Flags

Agents respect feature flags from `settings.py`:

| Flag | Affects | Default |
|------|---------|---------|
| `ENABLE_REFLECTIVE_MODE` | ReflectiveAgent activation | `false` |
| `ENABLE_PROACTIVE_MESSAGING` | ProactiveAgent | `false` |
| `ENABLE_CHARACTER_DIARY` | DreamWeaverAgent (diary) | `false` |
| `ENABLE_DREAM_SEQUENCES` | DreamWeaverAgent (dreams) | `false` |
| `ENABLE_TRACE_LEARNING` | Few-shot trace injection | `true` |
| `ENABLE_IMAGE_GENERATION` | Image tools availability | `true` |
| `ENABLE_VOICE_RESPONSES` | Voice intent detection | `false` |

---

## Related Documentation

- [Cognitive Engine Deep Dive](./COGNITIVE_ENGINE.md)
- [Message Flow](./MESSAGE_FLOW.md)
- [Data Models](./DATA_MODELS.md)
- [API Reference](../API_REFERENCE.md)

---

**Last Updated**: December 2024
