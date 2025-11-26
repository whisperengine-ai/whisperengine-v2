# Character as Agent - Design Analysis

**Document Version:** 1.0  
**Created:** November 25, 2025  
**Status:** 🔬 Analysis / Design Exploration  
**Type:** Architectural Decision Record (ADR)

---

## Executive Summary

This document explores whether WhisperEngine characters (Elena, Marcus, Aria, etc.) should be **agentic** - capable of autonomous tool use, planning, and goal-directed behavior - rather than **reactive** text generators that simply respond to prompts with injected context.

**Current State:** Characters are reactive (prompt + context → LLM → response)  
**Proposed Exploration:** Characters as agents (prompt + context + tools → LLM decides actions → response)

**Key Question:** Does making characters more agentic improve the user experience enough to justify the added latency and cost?

---

## Table of Contents

1. [Current Architecture](#current-architecture)
2. [What Makes Something "Agentic"?](#what-makes-something-agentic)
3. [The Case For Agentic Characters](#the-case-for-agentic-characters)
4. [The Case Against Agentic Characters](#the-case-against-agentic-characters)
5. [Proposed Hybrid Model](#proposed-hybrid-model)
6. [Agent Taxonomy](#agent-taxonomy)
7. [Technical Implementation](#technical-implementation)
8. [Character-Specific Agency](#character-specific-agency)
9. [Cost & Latency Analysis](#cost--latency-analysis)
10. [Open Questions](#open-questions)
11. [Recommendation](#recommendation)

---

## Current Architecture

### How Characters Work Today

```
┌─────────────────────────────────────────────────────────────────┐
│                    CURRENT: REACTIVE MODEL                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  User Message                                                   │
│       ↓                                                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              CONTEXT ASSEMBLY (Parallel)                │   │
│  │  • Character system prompt (character.md)               │   │
│  │  • Recent memories (Qdrant vector search)               │   │
│  │  • User facts (Neo4j knowledge graph)                   │   │
│  │  • Trust level & unlocked traits                        │   │
│  │  • Active goals (passive injection)                     │   │
│  │  • User preferences (verbosity, style)                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│       ↓                                                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                 COMPLEXITY CLASSIFIER                    │   │
│  │            "Is this simple or complex?"                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│       ↓                              ↓                          │
│   SIMPLE                          COMPLEX                       │
│       ↓                              ↓                          │
│  Single LLM Call              ReflectiveAgent                   │
│  (Fast Mode)                  (ReAct Loop)                      │
│       ↓                              ↓                          │
│  Response                     Response                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### What Characters Can't Do Today

1. **Decide to look something up** - Context is pre-fetched, character doesn't choose
2. **Use tools mid-conversation** - Only ReflectiveAgent (for complex queries) uses tools
3. **Strategize about goals** - Goals are passively injected, not actively pursued
4. **Have internal monologue** - No "thinking" step visible or invisible
5. **Vary behavior by personality** - All characters use same response flow

### What Works Well

- ✅ Fast responses (1-2 seconds for simple queries)
- ✅ Predictable behavior (easier to debug)
- ✅ Cost-effective (~$0.002 per simple message)
- ✅ Consistent character voice
- ✅ Complex queries get proper reasoning (ReflectiveAgent)

---

## What Makes Something "Agentic"?

An **agent** is more than an LLM with a prompt. Key characteristics:

| Characteristic | Reactive Model | Agentic Model |
|----------------|----------------|---------------|
| **Tool Use** | Pre-determined or none | Agent decides when/what |
| **Planning** | Single-step | Multi-step reasoning |
| **Goal Pursuit** | Passive injection | Active strategizing |
| **Autonomy** | Follows script | Makes decisions |
| **State** | Stateless (context injected) | Maintains internal state |
| **Initiative** | Only responds | Can initiate actions |

### The Agency Spectrum

```
REACTIVE ←───────────────────────────────────────────→ FULLY AGENTIC

[Chatbot]     [Tool-Augmented]     [ReAct Agent]     [Autonomous Agent]
    │               │                    │                   │
    │               │                    │                   │
 Current         Proposed            Current              Future?
 Fast Mode       Tier 2            Reflective             ???
                                     Mode
```

---

## The Case For Agentic Characters

### 1. Autonomy Creates Authenticity

Characters that *decide* to do things feel more real than characters that are *told* what to do.

**Reactive (Current):**
```
System: "Here are the user's recent memories: [injected]"
Elena: "I remember you mentioned your dog Luna!"
```

**Agentic (Proposed):**
```
Elena: *thinking* "They seem sad today. Let me check what we talked about before..."
Elena: *uses search_memories tool*
Elena: "Hey, I was just thinking about Luna. How's she doing?"
```

The agentic version has *intention*. Elena decided to look something up because she sensed something. This mirrors how humans operate.

### 2. Goal-Directed Behavior

Characters have goals (defined in `goals.yaml`), but currently they're passive context:

**Current (Passive):**
```
System Prompt: "[CURRENT GOAL: build_trust] Try to naturally steer toward this goal..."
LLM: *may or may not incorporate this*
```

**Agentic (Active):**
```
Elena: *thinking* "My goal is to learn more about their creative side. 
        They mentioned art yesterday. Let me bring that up naturally..."
Elena: *uses check_goal_progress tool*
Elena: "Hey, did you ever finish that sketch you were working on?"
```

### 3. Tool Usage as Personality Expression

Different characters could use tools differently, creating emergent personality:

| Character | Tool Preference | Personality Expression |
|-----------|-----------------|------------------------|
| **Elena** | `search_memories` | Nostalgic, relationship-focused |
| **Marcus** | `lookup_facts` | Analytical, detail-oriented |
| **Aria** | `generate_image` | Creative, expressive |
| **Dotty** | Rarely uses tools | Intuitive, in-the-moment |

This isn't hardcoded - it emerges from how the character prompt influences tool selection.

### 4. Philosophical Alignment

WhisperEngine's vision is "Cognitive AI" with perceptual modalities. Agents are closer to autonomous entities than reactive responders:

- **Reactive:** Stimulus → Response (behaviorist)
- **Agentic:** Stimulus → Deliberation → Action (cognitive)

If you're building AI agents that "build context," agency is more aligned with that vision.

### 5. User Delight Moments

Tool usage can create memorable moments:

```
User: "What was that restaurant you recommended?"

Elena (Reactive): "I'm not sure, could you remind me?"

Elena (Agentic): "Hmm, let me think... *searches memories* 
                 Oh! Sakura Sushi on 5th Street! You said you 
                 wanted to try their omakase. Did you ever go?"
```

The agentic version demonstrates *effort* and *care*.

---

## The Case Against Agentic Characters

### 1. Latency Impact

Every tool use adds latency:

| Mode | Steps | Typical Latency |
|------|-------|-----------------|
| Reactive (Fast) | 1 LLM call | 1-2 seconds |
| Tool-Augmented | 1-2 LLM calls + tool | 3-5 seconds |
| Full ReAct | 3-5 LLM calls + tools | 5-10 seconds |

For casual conversation, 3-5 seconds feels slow. Users expect chat to be snappy.

### 2. Cost Multiplication

More LLM calls = more cost:

| Mode | Tokens/Message | Cost/Message |
|------|----------------|--------------|
| Reactive | ~1,000 | ~$0.002 |
| Tool-Augmented | ~2,500 | ~$0.005 |
| Full ReAct | ~5,000 | ~$0.01 |

At scale (100K messages/month), this is $200 vs $500 vs $1,000.

### 3. Unpredictability

Agents can make unexpected decisions:

```
User: "How's the weather?"

Elena (Agentic, Gone Wrong): 
  *thinking* "Weather... they mentioned a beach trip last month"
  *uses search_memories*
  *uses lookup_facts*
  "I see you were planning a trip to Miami! The weather there is..."

User: "I just wanted to know if I need an umbrella today 😅"
```

More agency = more ways to go off-rails.

### 4. Debugging Complexity

Reactive: "Why did it say X?" → Check prompt + context  
Agentic: "Why did it say X?" → Check prompt + context + tool decisions + tool results + reasoning

### 5. The Current Design Already Works

The dual-process architecture (Fast + Reflective) already handles the 80/20:
- 80% of messages: Simple, fast response
- 20% of messages: Complex, use ReflectiveAgent

Do we need to make the 80% more complex?

---

## Proposed Hybrid Model

Rather than binary (reactive vs. agentic), a **tiered approach**:

### Tier 1: Reactive (Current Fast Mode)
- **When:** Simple messages, casual chat
- **How:** Pre-fetched context + single LLM call
- **Latency:** 1-2 seconds
- **Cost:** ~$0.002

No changes needed. This is the default.

### Tier 2: Tool-Augmented (NEW)
- **When:** Character *could benefit* from a tool lookup
- **How:** LLM can optionally invoke ONE tool, then respond
- **Latency:** 2-4 seconds
- **Cost:** ~$0.004

```python
# Not a full ReAct loop - just optional single tool use
response = await llm_with_tools.ainvoke(messages)

if response.tool_calls:
    # Character decided to use ONE tool
    result = await execute_single_tool(response.tool_calls[0])
    final = await llm.ainvoke(messages + [ToolMessage(result)])
    return final
else:
    # Character decided no tool needed
    return response
```

**Key difference from ReflectiveAgent:** Not a loop. One optional tool use, then done.

### Tier 3: Deliberative (Current Reflective Mode)
- **When:** Complex queries requiring multi-step reasoning
- **How:** Full ReAct loop with multiple tools
- **Latency:** 5-10 seconds
- **Cost:** ~$0.01

No changes needed. ComplexityClassifier routes here.

### Routing Logic

```
User Message
     ↓
┌─────────────────────────────────────────┐
│         COMPLEXITY CLASSIFIER           │
│  (Already exists - may need tuning)     │
└─────────────────────────────────────────┘
     ↓                    ↓               ↓
  SIMPLE              MODERATE         COMPLEX
     ↓                    ↓               ↓
  Tier 1              Tier 2           Tier 3
  (Reactive)     (Tool-Augmented)   (Deliberative)
```

**New category:** MODERATE - not complex enough for ReAct, but could benefit from tool access.

---

## Agent Taxonomy

### Current Agents

| Agent | Type | Purpose | Runs |
|-------|------|---------|------|
| **ReflectiveAgent** | User-facing | Complex query reasoning | Real-time, on complex messages |
| **InsightAgent** | Background | Pattern detection, epiphanies | Periodic, async |

### Proposed Agents

| Agent | Type | Purpose | Runs |
|-------|------|---------|------|
| **CharacterAgent** | User-facing | Tool-augmented responses | Real-time, on moderate messages |
| **UniverseAgent** | Background | Cross-bot coordination | Triggered by cross-bot events |

### Agent Relationships

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER-FACING AGENTS                           │
│                                                                 │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐       │
│   │  Fast Mode  │    │ Character-  │    │ Reflective  │       │
│   │  (Reactive) │    │   Agent     │    │   Agent     │       │
│   │             │    │  (Tier 2)   │    │  (Tier 3)   │       │
│   └─────────────┘    └─────────────┘    └─────────────┘       │
│         ↑                  ↑                  ↑                │
│         └──────────────────┼──────────────────┘                │
│                            │                                   │
│                   ComplexityClassifier                         │
│                    (SIMPLE/MODERATE/COMPLEX)                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    BACKGROUND AGENTS                            │
│                                                                 │
│   ┌─────────────┐    ┌─────────────┐                           │
│   │  Insight    │    │  Universe   │                           │
│   │   Agent     │    │   Agent     │                           │
│   │             │    │  (Future)   │                           │
│   └─────────────┘    └─────────────┘                           │
│         │                  │                                   │
│         └──────────────────┘                                   │
│                  │                                              │
│           Worker Queue (Redis)                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Technical Implementation

### CharacterAgent Class

```python
# src_v2/agents/character_agent.py

from typing import List, Optional
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage
from langchain_core.tools import BaseTool
from loguru import logger

from src_v2.agents.llm_factory import create_llm
from src_v2.core.character import Character
from src_v2.config.settings import settings


class CharacterAgent:
    """
    A character that can optionally use tools to enhance responses.
    
    This is NOT a full ReAct agent - it's a single-pass tool-augmented responder.
    The character decides whether to use ONE tool, uses it, then responds.
    
    Design Philosophy:
    - Characters have agency (they decide to look things up)
    - But not unlimited agency (one tool max, no loops)
    - Tool usage reflects personality (emergent from prompt)
    - Fast enough for conversation (2-4 seconds)
    """
    
    def __init__(self, character: Character):
        self.character = character
        self.llm = create_llm(temperature=character.temperature or 0.7)
        
    async def respond(
        self,
        user_message: str,
        system_prompt: str,
        chat_history: List,
        user_id: str,
        context_variables: dict
    ) -> CharacterResponse:
        """
        Generate a response, optionally using one tool.
        
        The character DECIDES whether a tool would help.
        This creates agency without the latency of full ReAct.
        """
        
        # Get tools available to this character
        tools = self._get_character_tools(user_id)
        
        # Build messages
        messages = [
            SystemMessage(content=self._enhance_system_prompt(system_prompt)),
            *chat_history,
            HumanMessage(content=user_message)
        ]
        
        # Bind tools - character can choose to use or not
        llm_with_tools = self.llm.bind_tools(tools, tool_choice="auto")
        
        # First pass - character decides if tool needed
        response = await llm_with_tools.ainvoke(messages)
        
        if response.tool_calls and len(response.tool_calls) > 0:
            # Character decided to use a tool
            tool_call = response.tool_calls[0]  # Only use first tool
            
            logger.info(f"Character {self.character.name} using tool: {tool_call['name']}")
            
            # Execute the tool
            tool_result = await self._execute_tool(tool_call, tools)
            
            # Build final response with tool result
            messages.append(response)  # AI message with tool call
            messages.append(ToolMessage(
                content=tool_result,
                tool_call_id=tool_call["id"],
                name=tool_call["name"]
            ))
            
            # Get final response (no tools this time)
            final_response = await self.llm.ainvoke(messages)
            
            return CharacterResponse(
                content=str(final_response.content),
                used_tool=True,
                tool_name=tool_call["name"],
                tool_reasoning=str(response.content) if response.content else None
            )
        
        else:
            # Character decided no tool needed
            return CharacterResponse(
                content=str(response.content),
                used_tool=False
            )
    
    def _get_character_tools(self, user_id: str) -> List[BaseTool]:
        """
        Get tools available to this character.
        
        Different characters might have different tool access,
        influencing their agency style.
        """
        from src_v2.tools.memory_tools import (
            SearchSummariesTool,
            SearchEpisodesTool,
            LookupFactsTool
        )
        
        # Base tools all characters have
        tools = [
            SearchEpisodesTool(user_id=user_id),
            LookupFactsTool(user_id=user_id, bot_name=self.character.name),
        ]
        
        # Character-specific tools could be added here
        # Based on character traits or configuration
        
        return tools
    
    def _enhance_system_prompt(self, base_prompt: str) -> str:
        """
        Add agency guidance to system prompt.
        """
        agency_guidance = """

## Tool Usage (Your Agency)

You have access to tools that let you look things up. Use them when:
- The user asks about something you might have discussed before
- You want to recall a specific detail to make the conversation more personal
- You genuinely need information to give a good response

Don't use tools for:
- Simple greetings or casual chat
- Questions you can answer from general knowledge
- When the conversation is flowing naturally

If you decide to use a tool, briefly acknowledge it naturally:
- "Let me think about what we talked about..."
- "Hmm, I remember something about that..."
- (Or just use the information naturally without meta-commentary)

Your tool usage should feel like genuine curiosity or care, not robotic lookup.
"""
        return base_prompt + agency_guidance
    
    async def _execute_tool(self, tool_call: dict, tools: List[BaseTool]) -> str:
        """Execute a single tool and return result."""
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        
        tool = next((t for t in tools if t.name == tool_name), None)
        
        if tool:
            try:
                return await tool.ainvoke(tool_args)
            except Exception as e:
                logger.error(f"Tool {tool_name} failed: {e}")
                return f"I couldn't find that information right now."
        
        return "Tool not available."


class CharacterResponse:
    """Response from CharacterAgent with metadata."""
    
    def __init__(
        self,
        content: str,
        used_tool: bool = False,
        tool_name: Optional[str] = None,
        tool_reasoning: Optional[str] = None
    ):
        self.content = content
        self.used_tool = used_tool
        self.tool_name = tool_name
        self.tool_reasoning = tool_reasoning
```

### Integration with AgentEngine

```python
# In src_v2/agents/engine.py

async def generate_response(self, ...):
    # ... existing code ...
    
    # 1. Classify complexity (enhanced)
    complexity = await self._classify_complexity(user_message, chat_history, user_id)
    
    if complexity == "COMPLEX" and settings.ENABLE_REFLECTIVE_MODE:
        # Tier 3: Full ReAct
        return await self._run_reflective_mode(...)
    
    elif complexity == "MODERATE" and settings.ENABLE_CHARACTER_AGENCY:
        # Tier 2: Tool-augmented character response (NEW)
        return await self._run_character_agent(...)
    
    else:
        # Tier 1: Fast reactive response
        return await self._run_fast_mode(...)
```

---

## Character-Specific Agency

### Agency Profiles

Different characters could have different agency styles:

```yaml
# characters/elena/agency.yaml

agency:
  enabled: true
  style: "nostalgic"  # Influences tool selection
  
  tool_preferences:
    search_memories: 0.8    # High preference - she's relationship-focused
    lookup_facts: 0.4       # Medium - uses when needed
    generate_image: 0.2     # Low - not her style
  
  triggers:
    - "remember"
    - "last time"
    - "before"
    - emotional_context  # When user seems emotional
  
  personality_notes: |
    Elena tends to look things up when she senses emotional context.
    She cares about continuity and making users feel remembered.
    Her tool usage should feel warm and caring, not clinical.
```

```yaml
# characters/marcus/agency.yaml

agency:
  enabled: true
  style: "analytical"
  
  tool_preferences:
    lookup_facts: 0.9       # High - he's detail-oriented
    search_memories: 0.5    # Medium - for context
    generate_image: 0.1     # Low - not his thing
  
  triggers:
    - "what did I say"
    - "specifically"
    - "details"
    - factual_questions
  
  personality_notes: |
    Marcus looks things up when precision matters.
    He wants to get facts right and hates being vague.
    His tool usage should feel thorough and competent.
```

### Emergent vs. Configured

Two approaches to character-specific agency:

**Configured (Explicit):**
- Define tool preferences in YAML
- Hardcode trigger patterns
- Predictable but requires maintenance

**Emergent (Implicit):**
- Let the character prompt influence tool selection naturally
- "Elena is nostalgic" → LLM naturally uses memory tools more
- Less predictable but more authentic

**Recommendation:** Start emergent, add configuration only if needed for tuning.

---

## Cost & Latency Analysis

### Real-World Latency Data (Nov 2025)

> ⚠️ **DATA COLLECTION IN PROGRESS**
> 
> The data below is from ~2 days of observing a single real user. More comprehensive data collection is planned for the week of Nov 25-Dec 1, 2025. Update this section with:
> - Latency percentiles (p50, p95, p99)
> - Sample sizes per mode
> - User feedback/satisfaction correlation
> - Breakdown by message complexity

**Preliminary Findings (Limited Data - ~2 days, 1 user):**

| Mode | Originally Estimated | Actual Production |
|------|---------------------|-------------------|
| Fast Mode (Tier 1) | 1-2 seconds | **5-8 seconds** |
| Tool-Augmented (Tier 2) | 2-4 seconds | **~8-12 seconds** (projected) |
| Reflective (Tier 3) | 5-10 seconds | **~30 seconds** |

**Key Findings:**
1. **Baseline is already "slow"** - Even single-pass responses take 5-8 seconds
2. **Users accept latency** - They ask deep questions, expect thoughtful responses
3. **Showing reasoning works** - Reflective Mode's visible thinking mitigates 30s latency
4. **Tool usage adds ~2-4s** - Marginal increase on already-long baseline

**Implication:** The latency argument against character agency is weak. If Fast Mode is 5-8s, adding tools (+2-4s) is barely noticeable. Optimize for quality, not speed.

### The Reasoning Display Pattern

Reflective Mode already shows thinking steps, and user experience has been positive:

```
🧠 Reflective Mode Activated

> Analyzing the question...
> *searching memories*
> Found relevant context from last week
> *looking up facts*
> ...

[Final thoughtful response]
```

**This pattern can extend to Tier 2 (CharacterAgent):**

```
💭 *thinking about our conversations...*

[Tool-augmented response with recalled context]
```

Visible effort = perceived care = better UX, even with added latency.

### Revised Cost Analysis

Given actual latency, the cost/benefit shifts:

| Consideration | Old Thinking | New Thinking |
|---------------|--------------|--------------|
| Latency cost | "2x slower is bad" | "10s vs 8s is negligible" |
| User expectation | "Want instant replies" | "Want thoughtful depth" |
| Tool visibility | "Technical detail" | "Proof of care and effort" |
| Default mode | "Tier 1 (fast)" | "Tier 2 (tool-augmented)" |

### Per-Message Cost Comparison

| Tier | LLM Calls | Tool Calls | Tokens | Latency | Cost |
|------|-----------|------------|--------|---------|------|
| Tier 1 (Reactive) | 1 | 0 | ~1,000 | 1-2s | $0.002 |
| Tier 2 (Tool-Aug) | 2 | 0-1 | ~2,500 | 2-4s | $0.005 |
| Tier 3 (ReAct) | 3-5 | 1-3 | ~5,000 | 5-10s | $0.010 |

### Monthly Projection (100K messages)

| Scenario | Distribution | Monthly Cost |
|----------|--------------|--------------|
| Current (Tier 1 only) | 100% Tier 1 | $200 |
| With Tier 2 | 70% T1, 25% T2, 5% T3 | $275 |
| Aggressive Agency | 50% T1, 40% T2, 10% T3 | $400 |

### Latency Distribution

```
Current:
├── 80% messages: 1-2 seconds (Tier 1)
└── 20% messages: 5-10 seconds (Tier 3)

With Tier 2:
├── 60% messages: 1-2 seconds (Tier 1)
├── 30% messages: 2-4 seconds (Tier 2)
└── 10% messages: 5-10 seconds (Tier 3)
```

**Net Effect:** Slightly slower average, but more thoughtful responses for moderate queries.

---

## Open Questions

### 1. Tool Visibility
Should users see when characters use tools?

**Option A: Visible**
```
Elena: *searches memories* Oh right, you mentioned Luna was 
       having health issues last week. How is she doing?
```

**Option B: Invisible**
```
Elena: Oh right, you mentioned Luna was having health issues 
       last week. How is she doing?
```

**Option C: Character-Dependent**
- Some characters show their thinking (Marcus: analytical)
- Some don't (Aria: mystical, intuitive)

### 2. Tool Failure Handling
What if a tool returns nothing useful?

**Option A: Acknowledge**
```
Elena: I tried to remember but it's a bit fuzzy... 
       Can you remind me?
```

**Option B: Graceful Fallback**
```
Elena: Tell me more about that!
```

### 3. Agency Limits
Should characters be able to:
- Use multiple tools? (Current proposal: No, one max)
- Loop/retry? (Current proposal: No)
- Initiate actions? (E.g., proactively message based on tool results)

### 4. User Control
Should users be able to:
- Disable agency per-character?
- Request "think harder" (force Tier 2/3)?
- See reasoning traces?

### 5. Evaluation Metrics
How do we measure if agency improves experience?
- User satisfaction surveys?
- Engagement metrics (session length, return rate)?
- A/B testing?

---

## Recommendation

### Updated Based on Production Data (Nov 2025)

The original conservative recommendation ("experiment first") has been updated based on real-world findings:

**Production Insights:**
- Fast Mode already takes 5-8 seconds (not 1-2s as estimated)
- Reflective Mode takes ~30 seconds, and users accept it
- Showing reasoning steps effectively mitigates latency perception
- Users ask substantive questions and expect depth, not speed

**Revised Recommendation: Make Tier 2 the Default**

Given that:
1. Latency is already high (5-8s baseline)
2. Tool usage adds marginal time (~2-4s on top of 5-8s)
3. Users value depth over speed
4. Visible thinking improves perceived quality

**Tier 2 (CharacterAgent) should be the default for substantive messages.**

### Implementation Approach

#### Phase 1: Enable by Default (1 week)

1. **Implement CharacterAgent** with single-tool capability
2. **Route substantive messages to Tier 2** by default
3. **Show lightweight thinking indicator** (💭 pattern)
4. **Keep Tier 1 only for trivial** (greetings, emoji, one-word)

```
User Message
     ↓
┌─────────────────────────────────────────┐
│      IS THIS TRIVIAL?                   │
│  (greeting, emoji, <5 words)            │
└─────────────────────────────────────────┘
     ↓                                    ↓
   YES                                   NO
     ↓                                    ↓
  Tier 1                         Is it COMPLEX?
  (Fast, no tools)                    ↓         ↓
                                    NO         YES
                                    ↓           ↓
                               Tier 2       Tier 3
                            (Character    (Reflective
                              Agent)        Agent)
```

#### Phase 2: Tune and Optimize (ongoing)

1. **Monitor tool usage patterns** per character
2. **Adjust routing thresholds** based on data
3. **A/B test visibility patterns** (💭 vs invisible)
4. **Measure engagement correlation** with tool usage

### Why This Is Lower Risk Than Originally Thought

| Original Concern | Reality |
|------------------|---------|
| "Users won't wait 3-5s" | They already wait 5-8s happily |
| "Need to validate first" | Reflective Mode already validated patience |
| "Latency is the main cost" | Quality is the main value |
| "Start conservative" | Users want depth, not speed |

### What Changed

The key insight is that **WhisperEngine users are not typical chatbot users**. They:
- Engage in deep, meaningful conversations
- Ask substantive questions expecting thoughtful answers
- Value being remembered and understood
- Accept latency when they see effort/thinking

This user profile is ideal for agentic characters. The "cost" of agency (latency) is actually a **feature** (proof of care).

---

## Related Documents

- [INSIGHT_AGENT.md](../roadmaps/INSIGHT_AGENT.md) - Background agent design
- [REFLECTIVE_MODE_PHASE_2.md](../roadmaps/REFLECTIVE_MODE_PHASE_2.md) - Current ReAct implementation
- [IMPLEMENTATION_ROADMAP_OVERVIEW.md](../IMPLEMENTATION_ROADMAP_OVERVIEW.md) - Overall priorities
- [WHISPERENGINE_2_DESIGN.md](./WHISPERENGINE_2_DESIGN.md) - Core architecture philosophy

---

## Appendix: Philosophical Considerations

### What Is a Character?

Three mental models:

**1. Character as Mask**
The LLM is the "real" intelligence; character is just a persona applied via prompt.
- Implication: Agency belongs to LLM, not character
- Character is a filter, not an agent

**2. Character as Role**
The character is a role the LLM plays, with consistent traits and behaviors.
- Implication: Agency should be role-consistent
- Characters can have agency within their role

**3. Character as Entity**
The character is a distinct entity with their own goals, memories, and agency.
- Implication: Characters should be maximally agentic
- The LLM is the substrate; character is the agentic entity

WhisperEngine's vision ("Cognitive AI") aligns most with #3, but practical constraints push toward #2.

### The Authenticity Paradox

More agency → More authentic (characters feel real)  
More agency → More unpredictable (characters go off-script)  
More unpredictable → Less reliable (users frustrated)  
Less reliable → Less authentic (character seems broken)

The sweet spot is **bounded agency**: characters have autonomy within guardrails.

### Tool Usage as Care

The most powerful reframe: tool usage isn't a technical feature, it's an expression of care.

When Elena searches her memories, she's saying:
- "You matter enough for me to remember"
- "I'm paying attention to our history"
- "I want to get this right"

This transforms a latency cost into an emotional benefit.

---

**Version History:**
- v1.0 (Nov 25, 2025) - Initial analysis document
- v1.1 (Nov 25, 2025) - Updated with preliminary production latency data: Fast Mode is 5-8s (not 1-2s), Reflective Mode is ~30s, users accept latency for depth. Changed recommendation from "experiment first" to "make Tier 2 default". Added "Real-World Latency Data" section. Note: Data is preliminary (~2 days, 1 user) - more comprehensive collection planned.

**Data Collection Reminder:**
- [ ] Collect latency metrics (p50, p95, p99) by mode - Target: Dec 1, 2025
- [ ] Sample at least 5+ users over 1 week
- [ ] Correlate latency with user satisfaction/engagement
- [ ] Update this document with findings
