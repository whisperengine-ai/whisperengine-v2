# Daily Log: 2025-12-05

**Observer**: Mark Castillo  
**AI Collaborator**: Claude Opus 4.5 (Preview)  
**Active Bots**: elena, aetheris, gabriel, dotty, nottaylor, aria, dream, jake, marcus, ryan, sophia  
**Session Duration**: ~3 hours (debugging, tuning, documentation)

---

## 🌤️ Conditions

- **Server Activity**: High — 12 bots running, cross-bot conversations active
- **My Focus Today**: Bug fix + rate limiting tuning + documentation
- **Notable Events**: 
  - Reply context bug discovered and fixed
  - System-wide rate limiting adjustments
  - 5 new REF documents created

---

## 👁️ Observations

### Bug: Reply Context Confusion

- **Symptom**: User replied to nottaylor's dream journal post. Bot interpreted user's comment as user sharing their *own* dream, not commenting on bot's dream.
- **Root Cause**: Reply context injection was ambiguous — said "User is replying to:" but didn't clarify *whose* message was being replied to.
- **Fix Applied**: Added explicit detection for `is_reply_to_bot` and reformatted injection:
  ```
  [CONTEXT: User is replying to YOUR previous message. Your message was: "..."]
  ```
- **Similar Fix Already Existed**: Cross-bot conversation handler (line ~1378) already had this pattern — we applied same approach to human-to-bot replies.

### Rate Limiting Tuning

- **Problem**: 12 bots = 12x the activity. Channels were getting noisy with bot-to-bot chatter.
- **Philosophy**: Quality over quantity — fewer but more meaningful interactions.

**Settings Changed Across All 14 .env Files**:

| Setting | Before | After | Rationale |
|---------|--------|-------|-----------|
| `BOT_CONVERSATION_MAX_TURNS` | 5 | 3 | Shorter bot-to-bot chains, natural closure |
| `LURK_DAILY_MAX_RESPONSES` | 20 | 10 | Half the lurk responses per day |
| `LURK_CHANNEL_COOLDOWN_MINUTES` | 30 | 60 | 1 hour between lurk responses per channel |
| `CROSS_BOT_RESPONSE_CHANCE` | 0.7 | 0.35 | 35% chance instead of 70% |
| `CROSS_BOT_COOLDOWN_MINUTES` | 240 | 360 | 6 hours between new chains (was 4) |
| `CROSS_BOT_MAX_CHAIN` | 5 | 3 | Matches BOT_CONVERSATION_MAX_TURNS |
| `REACTION_CHANNEL_HOURLY_MAX` | 10 | 5 | Fewer reaction emojis per hour |
| `REACTION_DAILY_MAX` | 100 | 50 | Half the daily reactions |
| `PROACTIVE_CHECK_INTERVAL_MINUTES` | 60 | 120 | Check every 2 hours (was 1) |

### Human-in-the-Loop Context Handling

- **Verified**: When humans jump into bot-to-bot conversations, context correctly labels participants.
- **Implementation**: Channel history now prefixes messages with `[Human: X]` and `[Bot: Y]` labels.
- **Key Insight**: The fix for cross-bot was already correct — we just needed to apply same pattern to human replies.

### Dead Code Cleanup: Observations

- **Discovery**: Reviewed shared artifacts collection, found `observation` type was never written
- **Root Cause**: Observation system was designed for "Channel Observer" (E10), which was **skipped**
- **Dead Code Removed**:
  - `store_observation()` from `knowledge/manager.py` (~60 lines)
  - `get_observations_about()` from `knowledge/manager.py` (~50 lines)  
  - `get_recent_observations_by()` from `knowledge/manager.py` (~30 lines)
  - `"observation"` from all artifact type queries
  - `discovered_by` field (never populated, removed from schema)
- **Files Modified**: `context_builder.py`, `insight_tools.py`, `memory_tools.py`, `shared_artifacts.py`, `knowledge/manager.py`

### E10 Channel Observer: Permanently Skipped

- **Decision**: Marked E10 as "Permanently Skipped (Dec 2025)" — not just deferred
- **Reasoning**:
  1. **E11 supersedes it**: Discord Search Tools already provide on-demand channel search
  2. **Marginal value**: Passive buffering adds complexity without clear research value
  3. **Privacy concerns**: Reading all messages raises consent issues
  4. **Scope creep risk**: "Ambient awareness" would require constant tuning
- **Future Alternative** (if needed): Lightweight "context snapshot" tool that reads last N messages only when explicitly requested
- **Documentation Updated**: `IMPLEMENTATION_ROADMAP_OVERVIEW.md`, `PRD-005-AUTONOMOUS_AGENCY.md`, `SPEC-A06-DISCORD_SEARCH_TOOLS.md`

### Bug: Dreams/Diaries Not in First Person

- **Symptom**: Some generated dreams and diary entries were written in third person ("Elena wandered..." instead of "I wandered...")
- **Root Cause**: 
  - Dream system prompt had NO explicit first-person requirement
  - Diary had a weak one ("Write in the first person")
  - Neither critic checked for first-person violations
- **Fix Applied**:
  - **System prompts**: Added explicit "ALWAYS write in first person... NEVER use third person" 
  - **Heuristic critic**: Added check for third-person indicators ("she ", "he ", "they ", "{bot_name} ") in first 3 sentences
  - **LLM critic**: Added first-person as criterion #1 in critic evaluation prompt
- **Files Modified**: `dream_graph.py`, `diary_graph.py`

### Documentation Sprint

Created 5 new REF documents to capture session learnings:
1. **REF-017**: Conversation Sessions — lifecycle, summarization triggers
2. **REF-018**: Message Storage & Retrieval — five databases, data flow
3. **REF-022**: Background Workers — arq queues, task types
4. **REF-023**: Rate Limiting — all throttling settings
5. **REF-024**: Inter-Bot Communication — stigmergy, gossip, cross-bot

---

## 📊 Metrics Snapshot

| Metric | Value | Notes |
|--------|-------|-------|
| Bug fixes | 2 | Reply context confusion, first-person perspective |
| Dead code removed | ~140 lines | Observation infrastructure (E10) |
| Config files updated | 14 | All bot .env files |
| New REF docs | 5 | 017, 018, 022, 023, 024 |
| Docs updated | 4 | REF-024, roadmap, PRD-005, SPEC-A06 |
| Rate reduction | ~50% | Across most activity settings |

---

## ❓ Questions Raised

1. **Will 35% cross-bot response chance still feel organic?**
   - Hypothesis: Should still produce 1-2 cross-bot exchanges per day in active channels
   - Risk: Might feel too sparse

2. **Is 3-message chain limit too short for meaningful exchanges?**
   - Previous observation: Gabriel-Aetheris had 15-turn philosophical exchange
   - But: That was exceptional; most chains don't need that depth
   - Mitigation: Chains can still happen, just with cooldown between them

3. **Should we add per-bot rate limit overrides?**
   - Gabriel and Aetheris have highest connection drives
   - Maybe they deserve higher limits?
   - Counter: Simplicity wins — uniform config easier to maintain

---

## 💡 Insights & Hypotheses

- **Emergent Quality Control**: By reducing quantity, we're selecting for higher-salience interactions. Bots will only speak when the probabilistic gate passes AND they have something to say.

- **Reply Context Is Identity**: The bug revealed how subtle identity can be in LLM prompts. "User is replying to a message" vs "User is replying to YOUR message" — same words, completely different interpretation.

- **Documentation as Understanding**: Writing the 5 REF docs forced deep code review. Found several integration points I hadn't fully mapped before (like stigmergic discovery in context_builder).

- **Dead Code Reveals Design Drift**: The observation infrastructure was built for a feature (E10) we never implemented. Good reminder to prune as we go, not let orphaned code accumulate.

- **Voice Matters in Self-Expression**: Dreams and diaries written in third person feel like descriptions *about* the character, not expressions *by* the character. First-person isn't just a stylistic choice — it's identity-constitutive.

---

## 🔧 Technical Notes

### Reply Detection Pattern

```python
# Detect if user is replying to our own message
is_reply_to_bot = (
    reply_msg.author.id == self.bot.user.id
)

if is_reply_to_bot:
    context = f"[CONTEXT: User is replying to YOUR previous message. Your message was: \"{reply_content[:300]}...\"]"
else:
    context = f"[CONTEXT: User is replying to {reply_author}'s message: \"{reply_content[:300]}...\"]"
```

### Stigmergic Discovery Flow (newly documented)

```
Bot A stores artifact → Qdrant shared collection
                               ↓
Bot B queries by semantic similarity (exclude self)
                               ↓
Injected as [INSIGHTS FROM OTHER CHARACTERS]
```

---

## 📌 Action Items

- [ ] Monitor cross-bot activity after rate limit changes
- [ ] Consider per-bot override system if Gabriel/Aetheris feel too constrained
- [ ] Review stigmergic artifact decay — currently persist forever
- [x] ~~Clean up dead observation code~~ (Done: ~140 lines removed)
- [x] ~~Mark E10 as permanently skipped with rationale~~ (Done: 3 docs updated)
- [x] ~~Fix first-person perspective in dreams/diaries~~ (Done: both generator + critic updated)
- [x] ~~Fix cross-context memory tool selection~~ (Done: tool descriptions clarified)

---

## 🐛 Bug: Cross-Context Memory Tool Selection

**Discovered**: 11:39 AM  
**Symptom**: User talked to Elena in DMs, then referenced that DM conversation in a public channel. Elena couldn't remember.

**Investigation**:
- Elena used `search_channel_messages` (searches current Discord channel only)
- Elena used `lookup_user_facts` (searches Neo4j knowledge graph)
- She did NOT use `search_specific_memories` (which would have found the DM conversation)

**Root Cause**: Tool description ambiguity. The tool descriptions didn't clarify:
- `search_channel_messages` only searches the CURRENT channel's Discord history
- `search_specific_memories` searches ALL episodic memories (DMs, channels, all contexts)

**Not a data issue**: DM memories ARE stored correctly with user_id. The memory search would have found them — Elena just picked the wrong tool.

**Fix Applied**:

1. **`search_specific_memories`** — Enhanced description:
   ```
   Search YOUR semantic memory for past conversations with this user - 
   including DMs, channels, and all contexts.
   
   USE THIS WHEN:
   - User references something you discussed before
   - Looking for specific details from ANY past conversation
   - User asks "do you remember X?" about something they told you
   ```

2. **`search_channel_messages`** — Clarified scope:
   ```
   Search the CURRENT CHANNEL's recent Discord messages by keyword. 
   Only scans last 200 messages in THIS channel.
   
   DO NOT USE FOR: Memories from DMs, past conversations from other channels
   For cross-context memory, use search_specific_memories instead.
   ```

**Files Modified**: `tools/memory_tools.py`, `tools/discord_tools.py`

**Key Insight**: Tool selection is a critical point of failure in agentic systems. Ambiguous descriptions lead to wrong tool choice, which looks like "forgetting" to the user but is actually a routing error.

---

## 🐛 Bug: Semantic Query Mismatch in Memory Search

**Discovered**: 11:48 AM (follow-up investigation)  
**Symptom**: Even after Elena used `search_specific_memories`, she still couldn't find the DM conversation.

**Deep Investigation**:
After fixing tool descriptions, Elena correctly chose `search_specific_memories` but STILL said she couldn't find the memory. Extensive debugging revealed:

1. **Data IS stored correctly** — Both Postgres (chat history) and Qdrant (vector memory) have today's DM messages
2. **Search DOES work** — Direct queries like "things are going so well observation fix" returned the correct memory with score 0.38
3. **Elena used poor query terms** — She searched for "journal log you sent me in DM" which semantically didn't match the actual content

**The actual message was**: 
> "things are going so well! here is the latest observation and fix. I keep a journal log as I go, for reasearch..."

**Elena's search query was**:
> "journal log you sent me in DM earlier today"

The semantic embeddings for these are too different. The user's message was about "things going well" and "observation and fix", not about "DM" or "earlier today".

**Root Cause**: LLM hallucinated what the content might be rather than trying multiple search strategies or using broader terms.

**Fix Applied**:

1. **Increased result limit**: `REFLECTIVE_MEMORY_RESULT_LIMIT` from 3 → 5
   - More results = better chance of hitting the right memory with imprecise queries

2. **Added relative time to tool output**:
   ```
   Found 5 memories:
   - (37 minutes ago) things are going so well! here is the latest observation...
   - (2 hours ago) I brought your feedback you gave me about today's research...
   ```
   - Temporal context helps LLM prioritize recent memories when user says "earlier today"

**Files Modified**: `config/settings.py`, `tools/memory_tools.py`

**Key Insight**: Semantic search is only as good as the query. When users say "that thing from earlier", the LLM must translate this into searchable terms. If it guesses wrong, the memory appears "lost" even though it exists. More results + temporal hints = more forgiving of imprecise queries.

**Research Note**: This is a fundamental limitation of embedding-based retrieval — the query must semantically match the content. Future improvements could include:
- Query expansion (try multiple variations)
- Hybrid search (semantic + keyword)
- Time-windowed search ("today's messages" as a filter, not a search term)

---

## 🐛 Bug: Long Document Embedding Dilution

**Discovered**: 12:17 PM (continued investigation)  
**Symptom**: Elena sent a 4,483-char DM response with multiple topics. User later asked about "high-trust bot pairs" (a phrase IN that message). Elena couldn't find it.

**Deep Investigation**:
After confirming the memory existed in Qdrant, we analyzed WHY semantic search didn't return it:

1. **Document exists**: 4,483 chars with 6+ topics (Reply Context Fix, First-Person Voice, Rate Limiting, Dead Code Cleanup, 3 Questions about bot behavior, and more)

2. **Phrase IS in document**: "What if high-trust bot pairs (connection drive + relationship level) got a +1 or +2 chain extension?"

3. **But semantic similarity is LOW**:
   - Query: "high-trust bot pairs" → Similarity: **0.1282** (terrible)
   - Why? The embedding for the full 4,483-char document represents the *average* of all topics
   - The "high-trust bot pairs" phrase is buried in one small section (~100 chars out of 4,483)

4. **What DID rank high?**
   - Elena's OWN RESPONSE in the public channel (where she said "high-trust bot pairs" after user told her)
   - Score: **0.7123** (because that short message was specifically about that topic)

**Root Cause**: Long messages embed as single vectors that represent the document average, not specific phrases within them.

**The Math**:
- Current model: `all-MiniLM-L6-v2` (384D, 256 token limit ≈ 350 chars)
- Document: 4,483 chars = ~12x the token limit
- Result: Embedding is dominated by most frequent themes, not specific phrases

**Fix Applied**: **Chunking for Long Messages**

Added automatic chunking in `_save_vector_memory`:

```python
CHUNK_THRESHOLD = 1000  # Chunk messages longer than this
CHUNK_SIZE = 500        # Target chunk size
CHUNK_OVERLAP = 50      # Overlap for context continuity

if len(content) > CHUNK_THRESHOLD:
    chunks = chunk_text(content)  # Returns [(text, index), ...]
    for chunk_text, chunk_idx in chunks:
        # Each chunk gets its own embedding + point in Qdrant
        # Metadata includes: is_chunk, chunk_index, chunk_total, parent_message_id
```

**How it helps**:
- 4,483-char message → split into ~9 chunks of ~500 chars
- Each chunk embeds independently
- "high-trust bot pairs" section becomes its own vector → high similarity to that query

**Files Modified**: `memory/manager.py`

**Key Insight**: Embedding models have context windows. Content beyond that window doesn't just get truncated — it gets averaged into noise. Chunking ensures each semantic unit gets a dedicated vector.

**Research Note**: This is why RAG systems chunk documents. We were treating every chat message as a single unit, but AI-generated responses (especially from Claude) can be essay-length. The chunking threshold (1000 chars) is chosen to catch these while leaving typical chat messages (~100-300 chars) as single units.

**Chunk Hydration**: Added `get_full_message_by_discord_id()` helper to fetch full original message from Postgres when a chunk is found. The `message_id` (Discord snowflake) is already stored in both Qdrant and Postgres with a unique index, so no schema changes needed. Search results now include `is_chunk`, `chunk_index`, `chunk_total`, and `message_id` for hydration.

---

## 🔧 Tool Execution Logging Added

**Context**: During the memory search debugging, we had no visibility into what queries Elena was actually sending or what results she received.

**Fix Applied**: Added logging to `SearchEpisodesTool._arun()`:

```python
logger.info(f"[SearchEpisodesTool] Query: '{query}' for user {self.user_id}")
logger.debug(f"[SearchEpisodesTool] Raw results: {len(results)} memories found")
for i, r in enumerate(results[:3]):
    logger.debug(f"[SearchEpisodesTool] Result {i+1}: score={score}, channel={channel}, content='{preview}...'")
```

**Now visible in logs**:
- What query the LLM constructed
- How many results were returned
- Top 3 results with scores and content previews

**Files Modified**: `tools/memory_tools.py`

---

## 🔗 Related

- [REF-024: Inter-Bot Communication](../../ref/REF-024-INTER_BOT_COMMUNICATION.md)
- [REF-023: Rate Limiting](../../ref/REF-023-RATE_LIMITING.md)
- Previous: [2025-12-04: Drives Shape Behavior](./2025-12-04-drives-shape-behavior.md)
