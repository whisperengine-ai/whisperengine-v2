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

### Phase 1: Classification
- [ ] Create `src_v2/agents/classifier.py`.
- [ ] Implement `ComplexityClassifier` using `create_llm()`.
- [ ] Unit test with examples:
    *   "Hi!" -> Simple
    *   "What is the meaning of life?" -> Complex
    *   "Do you remember when we first met and how that compares to now?" -> Complex

### Phase 2: The Reflective Agent
- [ ] Create `src_v2/agents/reflective.py`.
- [ ] Define the **ReAct Prompt** tailored for roleplay (ensuring the final answer stays in character).
- [ ] Implement the loop: `LLM -> Parse Action -> Execute Tool -> Append Observation -> Repeat`.
- [ ] Reuse existing tools from `src_v2/tools/memory_tools.py`.

### Phase 3: Integration
- [ ] Update `AgentEngine` to initialize `ComplexityClassifier` and `ReflectiveAgent`.
- [ ] Refactor `generate_response` to handle the branching logic.
- [ ] Ensure "Thought Traces" are logged for debugging (Reasoning Transparency).

### Phase 4: Tuning
- [ ] Test latency impact.
- [ ] Tune the Classifier to avoid over-triggering Reflective Mode (which is slower/more expensive).
- [ ] Ensure the final response maintains the character's voice, even after a robotic reasoning process.
