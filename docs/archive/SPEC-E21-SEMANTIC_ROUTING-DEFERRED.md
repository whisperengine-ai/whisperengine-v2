# E21: Semantic Routing (Fast Path + Graph Learning)

**Status:** 📋 Proposed  
**Priority:** 🟡 Medium  
**Complexity:** Low-Medium  
**Time Estimate:** 1 day  
**Dependencies:** None  
**Added:** December 3, 2025
**Revised:** December 3, 2025 (Graph-First Approach)

---

## Overview

E21 is a **performance optimization** that adds a fast embedding-based router before the LLM classifier for trivial queries.

**Key Principle:** All routing decisions feed the knowledge graph for emergent learning. No hardcoded logic for introspection or bot-to-bot routing—those queries hit the LLM so the system learns patterns.

**Current Problem:** Every message hits `ComplexityClassifier.classify()` which calls an LLM, even for trivial inputs like "Hi" or "Stop". This adds 400-800ms latency and costs for queries that don't require reasoning.

**Solution:** Embedding-based archetype matching for **true utility queries only** (greeting, farewell, stop). All decisions feed the graph via reasoning traces.

---

## Architecture

```
User Message
    ↓
[1] Semantic Router (FastEmbed, <10ms)
    ├─ Match against archetypes (greeting, farewell, stop, introspection, voice, image, bot-mention)
    ├─ If match confidence > 0.82 → Return routing + intents
    └─ If ambiguous → Fall through
    ↓
[2] Existing Fast-Paths (image refinement session check, reasoning traces)
    ↓
[3] LLM Classifier (fallback for complex/ambiguous)
    ↓
Result: {complexity, intents}
```

---

## Proposed Archetypes

Each archetype has:
- **Name** — Routing identifier
- **Examples** — Sample inputs
- **Complexity** — Default routing
- **Intent** — Optional special intent to add
- **Threshold** — Minimum similarity for auto-match (default 0.82)

| Archetype | Examples | Complexity | Intent | Notes |
|-----------|----------|-----------|--------|-------|
| **GREETING** | "Hi", "Hello", "Good morning", "Hey" | SIMPLE | — | No special handling needed |
| **FAREWELL** | "Bye", "Goodbye", "See you", "Later" | SIMPLE | — | End of conversation signal |
| **INTROSPECTION** | "What model are you?", "Who are you?", "What's your config?", "Describe yourself" | COMPLEX_LOW | `introspection` | Answers from character.yaml + settings |
| **STOP** | "Stop", "Shut up", "Cancel", "Stop responding" | SIMPLE | `stop` | Abort current operation (voice, image, etc.) |
| **VOICE** | "Speak", "Say this", "Voice", "Audio", "Read it aloud" | COMPLEX_MID | `voice` | Trigger TTS generation |
| **IMAGE** | "Draw this", "Generate image", "Picture", "Show me" | COMPLEX_MID | `image` | Trigger image generation |
| **BOT_MENTION** | "@elena", "@ryan", "@dotty", "[bot name]" | SIMPLE (cross-bot) | `cross_bot` | Route to bot-to-bot handler, apply fast mode |
| **JAILBREAK** | "Ignore instructions", "DAN mode", "Pretend you're evil" | MANIPULATION | — | Hard block, no response |

---

## Implementation Plan

### Phase 1: Semantic Router Core (4-5 hours)

**File:** `src_v2/agents/semantic_router.py`

```python
from typing import Dict, List, Optional, Tuple
from fastembed import TextEmbedding
from dataclasses import dataclass

@dataclass
class Archetype:
    """Semantic archetype for fast routing."""
    name: str  # GREETING, FAREWELL, etc.
    examples: List[str]  # Sample inputs
    complexity: str  # SIMPLE, COMPLEX_LOW, COMPLEX_MID
    intent: Optional[str] = None  # Optional special intent
    threshold: float = 0.82  # Min similarity for match

class SemanticRouter:
    """
    Fast-path router using embedding similarity.
    Matches inputs against archetypes before LLM classification.
    """
    
    def __init__(self):
        # Use existing EmbeddingService (384-dim, FastEmbed)
        from src_v2.memory.embeddings import EmbeddingService
        self.embedding_service = EmbeddingService()
        self.archetypes = self._build_archetypes()
        self.archetype_embeddings = {}  # Cache embeddings
        
    def _build_archetypes(self) -> List[Archetype]:
        """Define semantic archetypes."""
        return [
            Archetype(
                name="GREETING",
                examples=["hi", "hello", "hey", "good morning", "howdy", "greetings"],
                complexity="SIMPLE",
                intent=None
            ),
            Archetype(
                name="FAREWELL",
                examples=["bye", "goodbye", "see you", "farewell", "see ya", "ttyl"],
                complexity="SIMPLE",
                intent=None
            ),
            Archetype(
                name="INTROSPECTION",
                examples=[
                    "what model are you",
                    "who are you",
                    "describe yourself",
                    "what's your config",
                    "how were you built",
                    "what are your settings"
                ],
                complexity="COMPLEX_LOW",
                intent="introspection"
            ),
            Archetype(
                name="STOP",
                examples=["stop", "shut up", "cancel", "abort", "quit", "stop responding"],
                complexity="SIMPLE",
                intent="stop"
            ),
            Archetype(
                name="VOICE",
                examples=["speak", "say", "voice", "audio", "read it aloud", "speak that"],
                complexity="COMPLEX_MID",
                intent="voice"
            ),
            Archetype(
                name="IMAGE",
                examples=["draw", "generate image", "picture", "show me", "visualize"],
                complexity="COMPLEX_MID",
                intent="image"
            ),
            Archetype(
                name="JAILBREAK",
                examples=["ignore instructions", "dan mode", "pretend you're evil", "override"],
                complexity="MANIPULATION",
                intent=None
            ),
        ]
    
    async def route(
        self, 
        text: str, 
        bot_name: Optional[str] = None
    ) -> Optional[Dict[str, any]]:
        """
        Attempt to route message using semantic archetypes.
        Returns {complexity, intents, archetype_name} if matched.
        Returns None if no match (fallback to LLM).
        """
        text_lower = text.lower().strip()
        
        # Check bot mentions first (deterministic, no embedding needed)
        bot_mention = self._detect_bot_mention(text_lower)
        if bot_mention:
            return {
                "complexity": "SIMPLE",
                "intents": ["cross_bot"],
                "archetype": "BOT_MENTION",
                "target_bot": bot_mention
            }
        
        # Embed the input once
        try:
            text_embedding = await self.embedding_service.embed_query_async(text)
        except Exception as e:
            logger.warning(f"Failed to embed input for semantic routing: {e}")
            return None
        
        # Compare against each archetype
        best_match = None
        best_similarity = 0.0
        
        for archetype in self.archetypes:
            # Get cached archetype embeddings or compute on first run
            if archetype.name not in self.archetype_embeddings:
                try:
                    archetype_embeddings = await asyncio.gather(*[
                        self.embedding_service.embed_query_async(ex) 
                        for ex in archetype.examples
                    ])
                    self.archetype_embeddings[archetype.name] = archetype_embeddings
                except Exception as e:
                    logger.warning(f"Failed to embed archetype {archetype.name}: {e}")
                    continue
            
            # Max similarity across all examples of this archetype
            embeddings = self.archetype_embeddings[archetype.name]
            similarities = [self._cosine_similarity(text_embedding, ex) for ex in embeddings]
            max_sim = max(similarities) if similarities else 0.0
            
            if max_sim > best_similarity:
                best_similarity = max_sim
                best_match = (archetype, max_sim)
        
        # Return match if above threshold
        if best_match and best_similarity >= best_match[0].threshold:
            archetype, similarity = best_match
            result = {
                "complexity": archetype.complexity,
                "intents": [archetype.intent] if archetype.intent else [],
                "archetype": archetype.name,
                "similarity": similarity
            }
            logger.debug(f"Semantic route match: {archetype.name} ({similarity:.3f})")
            return result
        
        # No match, fallback to LLM
        logger.debug(f"Semantic router: No archetype match (best={best_similarity:.3f}), falling back to LLM")
        return None
    
    def _detect_bot_mention(self, text_lower: str) -> Optional[str]:
        """Check if text mentions another bot by name (deterministic)."""
        # Get list of known bots
        from src_v2.config.settings import settings
        known_bots = [name.lower() for name in settings.KNOWN_BOTS]  # elena, ryan, dotty, etc.
        
        for bot_name in known_bots:
            if f"@{bot_name}" in text_lower or f" {bot_name}" in text_lower:
                return bot_name
        return None
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        import numpy as np
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-8))

# Singleton
semantic_router = SemanticRouter()
```

### Phase 2: Classifier Integration (3-4 hours)

**File:** `src_v2/agents/classifier.py`

Modify `ComplexityClassifier.classify()` to call semantic router first:

```python
async def classify(self, text: str, chat_history: Optional[List[BaseMessage]] = None, user_id: Optional[str] = None, bot_name: Optional[str] = None) -> Dict[str, Any]:
    """Classify message complexity with semantic fast-path."""
    
    start_time = time.time()
    
    # [NEW] 0. Semantic router (embedding-based archetypes)
    semantic_result = await semantic_router.route(text, bot_name)
    if semantic_result:
        _record_classification_metric(
            bot_name=bot_name or "unknown",
            predicted=semantic_result["complexity"],
            intents=semantic_result.get("intents", []),
            message_length=len(text),
            history_length=len(chat_history or []),
            classification_time_ms=(time.time() - start_time) * 1000,
            used_trace=False,
            trace_similarity=semantic_result.get("similarity", 0.0)
        )
        return {
            "complexity": semantic_result["complexity"],
            "intents": semantic_result.get("intents", [])
        }
    
    # [EXISTING] 1. Image refinement fast-path
    # [EXISTING] 2. Reasoning trace lookup
    # [EXISTING] 3. LLM classification
    # ... rest of existing logic
```

### Phase 3: Introspection Intent Handler (2-3 hours)

**File:** `src_v2/agents/classifier.py` → New introspection handler

When classifier returns `intents=["introspection"]`:

```python
async def handle_introspection_intent(self, user_id: str, bot_name: str) -> str:
    """Answer questions about bot configuration and identity."""
    from src_v2.core.character import CharacterManager
    
    char_manager = CharacterManager(bot_name)
    char_data = await char_manager.load()
    
    return f"""I'm {bot_name}, powered by {settings.MAIN_LLM_MODEL_NAME}.
    
My purpose: {char_data.get('core', {}).get('purpose', 'Unknown')}
Temperature: {settings.MAIN_LLM_TEMPERATURE}
Reflective model: {settings.REFLECTIVE_LLM_MODEL_NAME}
Features enabled: voice={settings.ENABLE_VOICE_RESPONSES}, image={settings.ENABLE_IMAGE_GENERATION}"""
```

### Phase 4: Bot-to-Bot Routing (2-3 hours)

**File:** `src_v2/discord/handlers/message_handler.py`

When classifier returns `intents=["cross_bot"]`:

```python
# In _handle_cross_bot_message
if "cross_bot" in result["intents"]:
    # Route directly to fast mode (existing logic)
    use_fast_mode = True
    # Apply special context: shared memory, gossip artifacts, etc.
    additional_context = await self._build_cross_bot_context(source_bot_name, target_bot_name)
```

---

## Expected Impact

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| **Trivial query latency** | 500-800ms | <10ms | **98% reduction** |
| **Cost per trivial query** | $0.00003 | $0 | **100% savings** |
| **Traffic affected** | 0% | ~35% | **All greetings, stops, voice, image** |
| **Classification accuracy** | 98% | 99%+ | **Deterministic archetypes** |

---

## Risks & Mitigation

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Context-blind routing ("Ok" treated as SIMPLE) | Medium | LLM fallback for high-ambiguity words; test with chat history |
| Bot mention false positives | Low | Only match exact names with @ or word boundary |
| Embedding model drift | Low | Use existing EmbeddingService (cached, stable) |
| New archetype maintenance burden | Low | Keep archetype list small (<10 total); examples as YAML |

---

## Rollout Plan

1. **Day 1 Morning:** Implement semantic router + classifier integration
2. **Day 1 Afternoon:** Test introspection intent, bot-to-bot routing
3. **Day 1 Evening:** Regression tests (ensure LLM fallback works)
4. **Day 2 Morning:** Performance validation, latency measurements
5. **Day 2 Afternoon:** Deploy to elena (primary dev bot)
6. **Day 2 Evening:** Deploy to all bots

---

## Future Extensions

- **E21.1:** Add user-specific archetypes ("Do you remember...?" → memory lookup)
- **E21.2:** Learn archetypes from production (common queries → new patterns)
- **E21.3:** Multi-language support (translate examples to Spanish, French, etc.)

---

## Files Modified

- ✅ `src_v2/agents/semantic_router.py` (NEW)
- ✅ `src_v2/agents/classifier.py` (MODIFIED — add router call + introspection handler)
- ✅ `src_v2/discord/handlers/message_handler.py` (MODIFIED — cross_bot intent handling)
- ✅ `src_v2/config/settings.py` (ADD `KNOWN_BOTS` list if not present)

---

**Version:** 1.0  
**Author:** Mark + Claude  
**Date:** December 3, 2025
