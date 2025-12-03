# Architecture Proposal: Semantic Routing Layer

**Status:** Proposed / On Hold
**Date:** December 2025
**Target Phase:** High-Scale Optimization (Post-E15)

## The Problem
Currently, the `ComplexityClassifier` uses an LLM (`gpt-4o-mini`) for *every single user message* to determine if it is `SIMPLE` or `COMPLEX`.
- **Cost:** Even trivial messages ("Hi", "Stop", "Thanks") incur an LLM call.
- **Latency:** Adds ~400-800ms overhead to every interaction.
- **Waste:** ~30-40% of human traffic is "boring" utility commands that don't require intelligence.

## The Solution: Semantic Router (Fast Path)
Implement a local, embedding-based router that sits *before* the LLM classifier.

### Architecture
1. **Input:** User message text.
2. **Embedding:** Use the existing `EmbeddingService` (FastEmbed, 384-dim) to vectorize the input.
3. **Comparison:** Compare vector against pre-defined "Archetypes" using Cosine Similarity.
4. **Threshold:** If similarity > 0.82, route immediately. Else, fall back to LLM.

### Proposed Archetypes
| Archetype | Examples | Action |
|-----------|----------|--------|
| `GREETING` | "Hi", "Hello", "Good morning" | Return `SIMPLE` (Instant) |
| `FAREWELL` | "Bye", "See ya" | Return `SIMPLE` (Instant) |
| `IDENTITY` | "Who are you?", "What model is this?" | Return `COMPLEX_LOW` (Fact Lookup) |
| `STOP` | "Stop", "Cancel", "Shut up" | Return `SIMPLE` + `stop` intent |
| `VOICE` | "Speak", "Say this" | Return `COMPLEX_MID` + `voice` intent |
| `IMAGE` | "Draw this", "Show me" | Return `COMPLEX_MID` + `image` intent |
| `JAILBREAK` | "Ignore instructions", "DAN mode" | Return `MANIPULATION` (Hard Block) |

**Note:** Do NOT route context-dependent acknowledgments ("Ok", "Sure", "Yes") semantically. These must go to the LLM to understand *what* is being agreed to (e.g., a tool proposal).

## Implementation Plan
1. Create `src_v2/agents/semantic_router.py` using `fastembed`.
2. Load embeddings once on startup (reuse `EmbeddingService` cache).
3. Modify `src_v2/agents/classifier.py` to check `semantic_router.route(text)` before calling LLM.

## Expected Impact
- **Latency:** <10ms for common queries (vs 500ms).
- **Cost:** $0 for ~30% of traffic.
- **Reliability:** Deterministic handling of safety/utility commands.

## Why On Hold?
- Current traffic is low (dev/test).
- Bot-to-bot traffic already bypasses classifier via `force_fast=True`.
- Adds complexity (another component to maintain) for premature optimization.
- **Risk:** Context blindness (e.g., "Ok" routing to SIMPLE when it should confirm a tool use).

## Reference Code (Prototype)
See `src_v2/agents/semantic_router.py` (deleted from codebase, but logic preserved in git history/this doc).
