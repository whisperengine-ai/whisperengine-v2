# Reflective Mode Implementation Plan

## 1. Overview
**Reflective Mode** enables WhisperEngine characters to handle complex, philosophical, or multi-layered queries by engaging in a "Deep Thinking" process. Unlike the standard "Fast Mode" (which performs a single retrieval pass), Reflective Mode uses a **ReAct (Reasoning + Acting)** loop to formulate plans, gather evidence across multiple steps, and synthesize a nuanced response.

## 2. Architecture Comparison

### Fast Mode (Current)
*   **Goal**: Low latency (<2s), conversational flow.
*   **Flow**: `User Input` -> `Cognitive Router` -> `Tool Execution (Parallel)` -> `Response Generation`.
*   **Use Case**: Greetings, simple facts ("What is my name?"), small talk.

### Reflective Mode (New)
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

```python
# Pseudo-code for generate_response
async def generate_response(self, ...):
    # 1. Classify Intent
    is_complex = await self.classifier.is_complex(user_message)
    
    if is_complex:
        logger.info("Engaging Reflective Mode")
        # Run the ReAct loop
        response = await self.reflective_agent.run(user_message, user_id, character)
        return response
    else:
        logger.info("Engaging Fast Mode")
        # Existing Router -> RAG -> Response flow
        return await self._run_fast_mode(...)
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

**Next Steps**:
- Monitor Elena usage patterns
- Gather user feedback on response quality
- Consider enabling for other bots based on results
