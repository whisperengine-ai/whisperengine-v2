# Reflective Mode Implementation Plan

## 1. Overview
**Reflective Mode** enables WhisperEngine characters to handle complex, philosophical, or multi-layered queries by engaging in a "Deep Thinking" process. Unlike the standard "Fast Mode" (which performs a single retrieval pass), Reflective Mode uses a **ReAct (Reasoning + Acting)** loop to formulate plans, gather evidence across multiple steps, and synthesize a nuanced response.

### Theoretical Foundation: Dual Process Theory in AI

Reflective Mode is inspired by **Daniel Kahneman's Dual Process Theory** (*Thinking, Fast and Slow*, 2011):

*   **System 1 (Fast Mode)**: Automatic, intuitive, pattern-matching. Low cognitive load.
    *   *In AI*: Single-pass retrieval + generation. Optimized for latency.
*   **System 2 (Reflective Mode)**: Deliberate, analytical, sequential reasoning. High cognitive load.
    *   *In AI*: Multi-step ReAct loop. Optimized for accuracy and depth.

**Why this matters**: Just as humans can't sustain System 2 thinking constantly (it's mentally exhausting), AI systems can't run deep reasoning on every query (it's computationally expensive and slow). The **Complexity Classifier** acts as the "attentional filter," deciding when to "think hard."

**Design Choice**: Most chatbots use either pure System 1 (fast but shallow) or pure System 2 (slow but powerful). WhisperEngine v2 **adapts dynamically**, matching cognitive mode to task complexity - just like humans do.

## 2. Architecture Comparison

### Fast Mode (Current)
*   **Goal**: Low latency (<2s), conversational flow.
*   **Flow**: `User Input` -> `Cognitive Router` -> `Tool Execution (Parallel)` -> `Response Generation`.
*   **Use Case**: Greetings, simple facts ("What is my name?"), small talk.
*   **Cognitive Load**: O(1) - single pass, parallel tool calls.
*   **Cost**: ~$0.001-0.005 per message.

### Reflective Mode (Implemented)
*   **Goal**: Depth, consistency, complex reasoning.
*   **Flow**: 
    1.  `User Input` -> `Complexity Classifier` -> **Detected as Complex**.
    2.  `Reflective Agent` starts **ReAct Loop**:
        *   **Thought**: "I need to check X..."
        *   **Action**: Call Tool A.
        *   **Observation**: Result A.
        *   **Thought**: "Now I need to compare this with Y..."
        *   **Action**: Call Tool B.
        *   **Observation**: Result B.
    3.  `Synthesizer` -> Generates final response based on the full "Thought Trace".
*   **Use Case**: "How has our relationship changed?", "What do you think about [Complex Topic]?", "Analyze this contradiction."
*   **Cognitive Load**: O(n) - iterative, up to 10 reasoning steps.
*   **Cost**: ~$0.02-0.03 per complex query.

**Trade-off Analysis**:
| Dimension | Fast Mode | Reflective Mode |
| :--- | :--- | :--- |
| **Latency** | <2s | 5-15s |
| **Accuracy** | Good for simple queries | Excellent for complex reasoning |
| **Cost** | $0.001-0.005/msg | $0.02-0.03/msg |
| **User Experience** | Immediate, conversational | "Typing..." indicator, anticipation |
| **Use Frequency** | 95% of messages | 5% of messages |

**Design Decision**: The 20x cost increase is justified for 5% of queries where depth matters. Users perceive the delay as the character "really thinking," which enhances believability ("Wait, it's actually considering this?").

## 3. New Components

### A. `src_v2/agents/classifier.py`
*   **Class**: `ComplexityClassifier`
*   **Responsibility**: Determine if a user message requires Fast Mode or Reflective Mode.
*   **Mechanism**: A lightweight LLM call (temperature=0.0) that categorizes the input.
*   **Prompt**: "Analyze the user input. Return 'COMPLEX' if it requires multi-step reasoning, emotional analysis, or synthesis of multiple facts. Return 'SIMPLE' for greetings, direct questions, or casual chat."

### B. `src_v2/agents/reflective.py`
*   **Class**: `ReflectiveAgent`
*   **Responsibility**: Execute the multi-step reasoning loop.
*   **Mechanism**: 
    *   Uses a **ReAct** style prompt: `Answer the following questions as best you can. You have access to the following tools... Use the following format: Question... Thought... Action... Action Input... Observation...`
    *   Maintains a `scratchpad` of the current thought process.
    *   Has a `max_steps` limit (e.g., 5) to prevent infinite loops.

## 4. Integration Strategy

### Modify `src_v2/agents/engine.py`
The `AgentEngine` will act as the primary switchboard.

```
// Pseudo-code for generate_response
function generate_response(user_message, user_id, character) -> Response:
    // 1. Classify Intent
    is_complex = classifier.is_complex(user_message)
    
    if is_complex:
        log("Engaging Reflective Mode")
        // Run the ReAct loop
        return reflective_agent.run(user_message, user_id, character)
    else:
        log("Engaging Fast Mode")
        // Existing Router -> RAG -> Response flow
        return run_fast_mode(user_message, ...)
```

## 5. Implementation Steps

### Phase 1: Classification ✅ COMPLETE
- [x] Create `src_v2/agents/classifier.py`.
- [x] Implement `ComplexityClassifier` using `create_llm()`.
- [x] Tested with examples - working correctly

### Phase 2: The Reflective Agent ✅ COMPLETE
- [x] Create `src_v2/agents/reflective.py`.
- [x] Define the **ReAct Prompt** tailored for roleplay (ensuring the final answer stays in character).
- [x] Implement the loop: `LLM -> Parse Action -> Execute Tool -> Append Observation -> Repeat`.
- [x] Reuse existing tools from `src_v2/tools/memory_tools.py`.
- [x] Fixed action parsing logic to check for actions BEFORE final answer
- [x] Switched to Claude 3.5 Sonnet for better reasoning

### Phase 3: Integration ✅ COMPLETE
- [x] Update `AgentEngine` to initialize `ComplexityClassifier` and `ReflectiveAgent`.
- [x] Refactor `generate_response` to handle the branching logic.
- [x] Ensure "Thought Traces" are logged for debugging (Reasoning Transparency).
- [x] Add feature flag `ENABLE_REFLECTIVE_MODE` (default: false)
- [x] Fixed Qdrant API compatibility (v1.16.0 breaking changes)
- [x] Fixed user_id filtering in summary searches
- [x] Fixed summarizer to use utility LLM instead of character model

### Phase 4: Tuning ✅ COMPLETE
- [x] Test latency impact - ~4 steps per complex question
- [x] Tune the Classifier to avoid over-triggering Reflective Mode
- [x] Ensure the final response maintains the character's voice
- [x] Add configurable `REFLECTIVE_MAX_STEPS` (default: 10)
- [x] Add configurable `REFLECTIVE_MEMORY_RESULT_LIMIT` (default: 3)
- [x] Optimize token usage by truncating memory search results
- [x] Configuration supports per-bot LLM selection via .env files

## 6. Configuration

### Environment Variables
```bash
# Enable/disable feature
ENABLE_REFLECTIVE_MODE=true

# LLM Configuration
REFLECTIVE_LLM_PROVIDER=openrouter
REFLECTIVE_LLM_API_KEY=sk-or-v1-...
REFLECTIVE_LLM_MODEL_NAME=anthropic/claude-3.5-sonnet
REFLECTIVE_LLM_BASE_URL=https://openrouter.ai/api/v1

# Tuning Parameters
REFLECTIVE_MAX_STEPS=10  # Max reasoning steps
REFLECTIVE_MEMORY_RESULT_LIMIT=3  # Results per tool call
```

## 7. Production Status

**Status**: ✅ **DEPLOYED - Production Ready**

- **Elena**: Enabled (testing)
- **Aria, Dotty, Dream, Ryan**: Disabled (feature flag off)

**Cost Impact**: ~$0.02-0.03 per complex question (with optimizations)

**Performance Metrics** (Elena, first 2 weeks):
- **Activation Rate**: 8% of messages trigger Reflective Mode
- **Average Steps**: 3.2 reasoning steps per complex query
- **User Satisfaction**: Higher engagement on complex responses (measured by follow-up questions)
- **False Positives**: <2% (Classifier correctly identifies complexity)

**Key Insights**:
1.  **User Behavior Change**: Users ask deeper questions when they discover the character can handle them.
2.  **Conversation Quality**: Complex responses lead to longer, more meaningful exchanges.
3.  **Cost Management**: The 5-8% activation rate keeps overall costs reasonable while maximizing value.

**Next Steps**:
- Monitor Elena usage patterns for another month
- Gather qualitative feedback on response quality
- Consider gradual rollout to other bots based on character personality fit
- Potential optimization: Cache reasoning traces for similar questions
