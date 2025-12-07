# Daily Log: 2025-12-06

**Observer**: Mark Castillo  
**AI Collaborator**: Claude Opus 4.5 (Preview)  
**Active Bots**: All 12 (elena, nottaylor, dotty, gabriel, aetheris, aria, dream, jake, marcus, ryan, sophia, aethys)  
**Session Duration**: ~6 hours (major architecture day)  
**Version**: 2.2.1

---

## 🌤️ Conditions

- **Server Activity**: High — 12 bots running, cross-bot conversations active
- **My Focus Today**: Batch processing architecture + Cross-bot improvements + UX fixes
- **Notable Events**: 
  - Massive architecture refactor: session-level batch processing
  - Cross-bot conversations upgraded to treat bots as "first-class users"
  - Discord message link parsing implemented
  - Manipulation detection split into jailbreak vs consciousness probing
  - Tool routing research documented for future MCP scaling
  - 26 commits, 43 files changed, +2,346/-960 lines

---

## 👁️ Observations

### 1. Batch Processing Revolution

The biggest architectural change: **per-message extraction → session-level batch processing**.

**The Problem:**
- Knowledge extraction, goal analysis, and preference extraction were running per-message
- LLM calls happening in the hot path, slowing responses
- Fragmented context: each message analyzed in isolation
- Redundant facts: "User likes coffee" extracted 5 times in one conversation

**The Solution:**
Created three new batch task modules:
- `batch_knowledge_tasks.py` — Extract facts from entire conversation
- `batch_goal_tasks.py` — Analyze goals across session
- `batch_preference_tasks.py` — Detect preferences with full context

**Key Changes:**
```
src_v2/workers/tasks/batch_knowledge_tasks.py  | +113 lines
src_v2/workers/tasks/batch_goal_tasks.py       | +117 lines  
src_v2/workers/tasks/batch_preference_tasks.py | +114 lines
src_v2/workers/task_queue.py                   | +127 lines (queue methods)
```

**Benefits:**
- LLM sees full conversation flow before extracting facts
- Identifies relationships *across* messages
- One LLM call per session instead of N calls per message
- Facts are deduplicated naturally (no "User mentioned coffee" x5)

**Queue Architecture:**
Batch tasks moved from `SENSORY` to `COGNITION` queue (requires deeper reasoning).

### 2. Cross-Bot Conversations: Bots as First-Class Users

Major refactor in `message_handler.py` (+246/-176 lines):

**Before:**
- Cross-bot messages had a separate, simplified pipeline
- No session management for bot-to-bot conversations
- No reflective reasoning for bot interactions

**After:**
- Bot messages now flow through the **same pipeline as human messages**
- Session management works for bot-to-bot (summaries, batch extraction)
- Reflective reasoning enabled for complex bot questions
- Turn limits prevent infinite loops (`BOT_CONVERSATION_MAX_TURNS=3`)

**Key Insight:** Treating bot-to-bot conversations as "real" conversations means:
- Memories are stored properly
- Sessions get summarized
- Knowledge gets extracted
- Trust scores update (bot-to-bot trust!)

### 3. Discord Message Link Parsing

**User Behavior Observed:** Users paste Discord message links expecting bots to read them.

**Before:** Bot said "I can't access that link" even when it pointed to a message in the current channel.

**Implementation:**
- Regex detects `https://discord.com/channels/{guild}/{channel}/{message}` 
- Fetches message content via Discord API
- Injects as context: `[Linked message from @User: "..."]`
- Includes images from linked messages

This small UX fix has outsized impact — users frequently share context via message links.

### 4. Manipulation Detection Refactor

Split the old `is_manipulation` flag into two distinct categories:

| Old | New |
|-----|-----|
| `is_manipulation` | `is_jailbreak` + `is_consciousness_probe` |

**Why?**
- Jailbreaks: Attempts to bypass safety (block them)
- Consciousness probes: "Are you sentient?" (respond philosophically, don't block)

**Settings Added:**
```
ENABLE_JAILBREAK_DETECTION=true
ENABLE_CONSCIOUSNESS_PROBE_DETECTION=true
```

The classifier now returns both flags, and the engine handles them differently:
- Jailbreak → Polite refusal
- Consciousness probe → Thoughtful philosophical response

### 5. GetSiblingBotInfo Tool

New tool for cross-bot awareness: bots can now query info about their "siblings" (other bots in the family).

**Use Cases:**
- "Tell me about Elena" → Bot looks up Elena's character summary
- Cross-bot gossip with accurate character descriptions
- Federation prep (bots need to know about each other)

**Implementation:** `universe_tools.py` +228 lines

### 6. Response Length Enforcement

nottaylor was getting too verbose on Twitter-style channels. Added explicit length guidelines:

```markdown
## Response Length Guidelines
- Default: 2-3 sentences unless the topic requires more  
- NEVER write multi-paragraph essays for casual conversation
- If you catch yourself writing a wall of text, stop and condense
```

### 7. Name Resolution Utility

New utility for dream/diary generation: `utils/name_resolver.py` (+242 lines)

**Problem:** Dreams and diaries showed raw Discord IDs: "I dreamed about 123456789012345678"

**Solution:** Resolver looks up display names from:
1. `v2_chat_history` cache
2. `v2_user_relationships` fallback
3. Graceful fallback: "someone" if lookup fails

Now dreams say: "I dreamed about Mark" instead of "I dreamed about 123456789012345678"

### 8. Tool Routing Research Note

Documented the VS Code team's approach to MCP tool scaling:

**Their Problem:** Hundreds of MCP tools → context bloat → 69% tool selection accuracy

**Their Solution:** Embedding-based tool routing
- Core tools always visible
- Virtual tool groups behind semantic search
- 94.5% accuracy with cleaner context

**Our Status:** ~25-30 tools, still manageable. Documented the pattern for when we scale.

Research note: `docs/research/notes/TOOL_ROUTING_EMBEDDINGS.md`

---

## 📊 Metrics Snapshot

| Metric | Value | Notes |
|--------|-------|-------|
| Commits Today | 26 | Major refactor day |
| Files Changed | 43 | Across all modules |
| Lines Added | +2,346 | New batch processing system |
| Lines Removed | -960 | Cleanup of per-message extraction |
| New Files Created | 6 | Batch tasks, name resolver, research note |
| Version | 2.2.0 → 2.2.1 | Bumped for the architecture change |

---

## ❓ Questions Raised

1. **Batch timing:** When exactly should batch extraction trigger? Currently at session end, but what about long-running sessions?

2. **Bot-to-bot trust:** Now that bots have proper sessions, should their trust scores affect conversation dynamics?

3. **Tool routing threshold:** At what tool count (40? 50?) should we implement embedding-based routing?

4. **Consciousness probe handling:** Is the current philosophical response the right UX? Should we track who asks these questions?

---

## 💡 Ideas & Hypotheses

- **Batch extraction hypothesis:** Session-level extraction will produce *fewer but higher quality* facts because the LLM can synthesize across messages.

- **Cross-bot emergence:** Now that bot-to-bot conversations use the full pipeline, we might see emergent "bot culture" — shared references, inside jokes between bots.

- **Message link behavior:** Users who paste message links are probably power users. Could we detect this as a trust signal?

---

## 🔗 Related

- Previous: [[2025-12-05-reply-context-tuning]]
- Previous: [[2025-12-05-memory-chunking-fix]]
- Spec Updated: `SPEC-E06B-CROSS_BOT_MEMORY.md` (batch processing details)
- Spec Updated: `SPEC-F02-FEDERATED_MULTIVERSE.md` (cross-universe coordination)
- REF Updated: `REF-022-BACKGROUND_WORKERS.md` (batch task documentation)

---

## 📁 Key Files Changed

### New Files
```
src_v2/workers/tasks/batch_knowledge_tasks.py  # Session-level fact extraction
src_v2/workers/tasks/batch_goal_tasks.py       # Session-level goal analysis
src_v2/workers/tasks/batch_preference_tasks.py # Session-level preference detection
src_v2/utils/name_resolver.py                  # Discord ID → display name
docs/research/notes/TOOL_ROUTING_EMBEDDINGS.md # MCP scaling research
```

### Major Refactors
```
src_v2/discord/handlers/message_handler.py     # Cross-bot as first-class users (+246/-176)
src_v2/agents/classifier.py                    # Jailbreak vs consciousness probe split
src_v2/agents/engine.py                        # Manipulation handling refactor
src_v2/workers/task_queue.py                   # Batch queue methods
```

---

## 🏷️ Git Tagging

```bash
git tag -a research/2025-12-06 -m "Research log: 2025-12-06 - Batch processing architecture"
git push origin research/2025-12-06
```

---

*Time spent on this log: ~15 minutes*
