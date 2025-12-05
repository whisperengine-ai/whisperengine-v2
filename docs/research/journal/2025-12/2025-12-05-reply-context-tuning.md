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

---

## 🔗 Related

- [REF-024: Inter-Bot Communication](../../ref/REF-024-INTER_BOT_COMMUNICATION.md)
- [REF-023: Rate Limiting](../../ref/REF-023-RATE_LIMITING.md)
- Previous: [2025-12-04: Drives Shape Behavior](./2025-12-04-drives-shape-behavior.md)
