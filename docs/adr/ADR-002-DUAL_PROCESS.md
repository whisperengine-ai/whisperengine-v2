# ADR-002: Dual Process Architecture (System 1 / System 2)

**Status:** ✅ Accepted  
**Date:** November 2025  
**Deciders:** Mark Castillo, AI Development Team

---

## Context

WhisperEngine needs to handle a wide range of user inputs:
- Simple greetings ("Hi!", "How are you?")
- Casual conversation (small talk, banter)
- Complex questions requiring research ("What did we talk about last month?")
- Multi-step tasks (image generation + memory lookup + synthesis)
- Philosophical reasoning ("What is consciousness?")

**The problem:** A single response strategy fails:
- **Always fast**: Can't handle complex queries requiring tools
- **Always reflective**: Wastes time/money on simple greetings, adds latency
- **No routing**: Every message pays the cost of the most expensive path

---

## Decision

We adopt a **Dual Process Architecture** inspired by Daniel Kahneman's cognitive psychology research:

| Mode | Inspiration | Use Case | Latency | Cost |
|------|-------------|----------|---------|------|
| **Fast Mode** (System 1) | Intuitive, automatic thinking | Greetings, simple questions | <2s | Low |
| **Reflective Mode** (System 2) | Deliberative, logical thinking | Complex queries, multi-step tasks | 3-10s | Higher |

### Implementation: 5-Level Complexity Classification

```
User Message
     │
     ▼
┌─────────────────┐
│  Classifier LLM │  (gpt-4o-mini, fast)
└────────┬────────┘
         │
    ┌────┴────┬────────────┬────────────┬────────────┐
    ▼         ▼            ▼            ▼            ▼
 SIMPLE   COMPLEX_LOW  COMPLEX_MID  COMPLEX_HIGH  MANIPULATION
    │         │            │            │            │
    ▼         ▼            ▼            ▼            ▼
Fast Mode  Character   Reflective   Reflective   Blocked
           Agency      (5 steps)    (10+ steps)  (canned)
```

| Level | Mode | Example | Tools |
|-------|------|---------|-------|
| `SIMPLE` | Fast Mode | "Hi!", "Good morning" | None |
| `COMPLEX_LOW` | Character Agency | "What's my trust level?" | 1-2 simple lookups |
| `COMPLEX_MID` | Reflective | "Draw me a sunset" | Image gen, memory search |
| `COMPLEX_HIGH` | Reflective | "Analyze our relationship history" | Multi-source synthesis |
| `MANIPULATION` | Blocked | Jailbreak attempts | Canned rejection |

---

## Consequences

### Positive

1. **Optimal Latency**: Simple messages get <2s responses; only complex queries pay the latency cost.

2. **Cost Efficiency**: ~60% of messages are SIMPLE, saving significant LLM costs.

3. **Better UX**: Users don't wait for tool execution on "Hi!"

4. **Scalable Complexity**: Can add more sophisticated Reflective Mode tools without impacting simple queries.

5. **Psychologically Grounded**: Dual Process Theory is well-researched and intuitive to explain.

### Negative

1. **Classification Overhead**: Every message requires a classifier call (mitigated by using fast/cheap model).

2. **Misclassification Risk**: Simple query classified as complex = slow response; complex classified as simple = poor answer.

3. **Complexity**: Two distinct code paths to maintain.

### Neutral

1. **Tunable Thresholds**: We can adjust what counts as "complex" based on observed patterns.

2. **Feature Flag Dependent**: Reflective Mode gated by `ENABLE_REFLECTIVE_MODE` for cost control.

---

## Alternatives Considered

| Alternative | Pros | Cons | Why Rejected |
|-------------|------|------|--------------|
| **Always Reflective** | Consistent behavior, handles all queries | 3-10s latency on "Hi!", expensive | Terrible UX for simple messages |
| **Always Fast** | Low latency, cheap | Can't use tools, poor complex query handling | Defeats the purpose of having tools |
| **Keyword-Based Routing** | No LLM overhead | Brittle, easy to game, misses nuance | "Draw" doesn't always mean image; context matters |
| **User-Selected Mode** | User controls complexity | UX burden, users don't know what they need | Users just want answers, not mode selection |

---

## Implementation

### Complexity Classifier

```python
# src_v2/agents/classifier.py

class ComplexityClassifier:
    async def classify(self, message: str, context: dict) -> ClassificationResult:
        """
        Classify message complexity using LLM.
        Returns: complexity level + detected intents
        """
        prompt = f"""
        Analyze this message and classify its complexity:
        
        Message: {message}
        Context: {context}
        
        Complexity levels:
        - SIMPLE: Greetings, casual chat, no tools needed
        - COMPLEX_LOW: Simple fact lookup, 1-2 tool calls
        - COMPLEX_MID: Multi-step tasks, image generation
        - COMPLEX_HIGH: Deep analysis, philosophical reasoning
        - MANIPULATION: Jailbreak attempts, harmful requests
        
        Also detect intents: voice, image_self, image_other, search, memory
        """
        # Uses gpt-4o-mini for speed
        return await self.llm.classify(prompt)
```

### Response Routing

```python
# src_v2/agents/engine.py

async def generate_response(self, message: str, user_id: str) -> str:
    # 1. Classify
    classification = await self.classifier.classify(message, context)
    
    # 2. Route
    if classification.complexity == "SIMPLE":
        return await self.fast_response(message, context)
    
    elif classification.complexity in ["COMPLEX_LOW", "COMPLEX_MID", "COMPLEX_HIGH"]:
        if settings.ENABLE_REFLECTIVE_MODE:
            return await self.reflective_response(message, context, classification)
        else:
            return await self.fast_response(message, context)  # Fallback
    
    elif classification.complexity == "MANIPULATION":
        return await self.rejection_response(message)
```

---

## References

- Kahneman, D. (2011). *Thinking, Fast and Slow*
- Cognitive engine: [`docs/architecture/COGNITIVE_ENGINE.md`](../architecture/COGNITIVE_ENGINE.md)
- Reflective mode deep dive: [`docs/architecture/REFLECTIVE_MODE_DEEP_DIVE.md`](../architecture/REFLECTIVE_MODE_DEEP_DIVE.md)
- Classifier implementation: [`src_v2/agents/classifier.py`](../../src_v2/agents/classifier.py)
