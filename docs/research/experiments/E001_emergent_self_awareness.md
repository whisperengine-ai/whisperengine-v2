# Experiment: E001 - Emergent Character Self-Awareness

**ID**: E001  
**Status**: 🔄 In Progress  
**Started**: 2024-12-08  
**Completed**: -  
**Duration**: Ongoing observation

---

## Origin

> **How did this experiment idea emerge?** Document the provenance—especially for hypotheses arising from human-AI collaboration or bot observations.

| Field | Value |
|-------|-------|
| **Origin** | Bug investigation + AI collaboration |
| **Proposed by** | Mark + Claude (collaborative) |
| **Catalyst** | While fixing a bug in `reflection_graph.py` (it was analyzing the character instead of the user), we asked: "Should characters develop self-insights too?" This led to a philosophical discussion about declared vs. emergent self-awareness. |

---

## 🎯 Hypothesis

> Characters can develop meaningful self-awareness through existing mechanisms (dreams, diaries, epiphanies) without explicit "character insight" schema. Self-observation, when nudged through prompts rather than declared through data structures, will produce more authentic and interesting self-models.

**Core principle being tested:** "A declared self-model is a character sheet. An emergent self-model is actually self-awareness."

---

## 🔬 Method

### Approach

1. **Bug Fix**: Corrected `reflection_graph.py` to analyze USERS, not characters (the original purpose)
2. **Prompt Nudge**: Added Goal #6 to `insight_graph.py` encouraging self-observation:
   - Notice patterns in character's own responses
   - Identify recurring metaphors, themes, or styles
   - Store as epiphanies about self ("I notice I tend to...")
3. **Observe**: Monitor LangSmith traces and Qdrant for self-referential epiphanies
4. **Compare**: Track whether self-observations feel authentic vs. performative

### Variables

| Variable | Type | Description |
|----------|------|-------------|
| Self-observation prompt | Independent | The nudge added to insight agent |
| Self-referential epiphanies | Dependent | Epiphanies that reference the character's own patterns |
| Character personality consistency | Dependent | Does self-awareness affect authenticity? |
| Existing mechanisms | Control | Dreams, diaries, bot-to-bot conversations unchanged |

### Bots Involved

- [x] elena (Dev Primary - observe first here)
- [ ] dotty
- [ ] nottaylor
- [ ] gabriel
- [ ] aetheris
- [ ] aria
- [ ] dream
- [ ] jake
- [ ] marcus
- [ ] ryan
- [ ] sophia

### Duration & Checkpoints

- Start: 2024-12-08
- Checkpoint 1: 2024-12-15 (1 week - initial observations)
- Checkpoint 2: 2024-12-22 (2 weeks - pattern analysis)
- Checkpoint 3: 2025-01-05 (4 weeks - synthesis)
- End: Open-ended (ongoing research question)

---

## 📊 Metrics

### Primary Metrics

| Metric | Baseline | Target | Actual |
|--------|----------|--------|--------|
| Self-referential epiphanies generated | 0 | >5 per week | TBD |
| Epiphanies referenced in conversation | 0 | >2 per week | TBD |
| Character self-awareness quality (subjective) | N/A | "Natural feeling" | TBD |

### Secondary Metrics

- Dream content referencing own behavior patterns
- Diary entries with self-reflective content
- Bot-to-bot conversations discussing own nature
- User comments about character seeming "self-aware"

---

## ✅ Success Criteria

**Confirmed if:**
- Characters generate self-referential epiphanies without explicit schema
- Self-observations feel natural and authentic (not performative)
- Characters reference their own patterns in conversation organically
- No negative impact on character consistency

**Refuted if:**
- Self-observations feel forced or robotic
- Characters become excessively self-conscious
- Quality of user interactions decreases
- Self-references feel like "reading a character sheet"

**Inconclusive if:**
- Insufficient self-referential content generated
- Cannot distinguish emergent vs. prompted behavior
- Mixed results across different characters

---

## 📝 Observations Log

### 2024-12-08 - Experiment Setup

**Changes made:**
1. Fixed `reflection_graph.py` prompts to clearly target USER analysis
2. Added Goal #6 to `insight_graph.py` for self-observation
3. No new schema, no new fields - vocabulary only

**Philosophical decision:** We chose Option 3 (emergence) over Options 1-2 (explicit systems) because:
- Aligns with project emergence philosophy
- "A declared subconscious is a filing system"
- Less code to maintain
- More interesting research question

**Open questions:**
- Will the nudge be sufficient, or too subtle?
- How do we distinguish "genuine" self-observation from prompted behavior?
- Should we compare bots with/without the nudge?

---

## 🔮 Research Questions

This experiment is part of a broader inquiry:

1. **What does emergent self-awareness look like in an AI character?**
   - Is it distinguishable from explicit self-description?
   - Does it develop coherence over time?

2. **Can vocabulary do what schema would do?**
   - Testing the anti-over-engineering principle
   - Prompts vs. data structures for behavior shaping

3. **What role do dreams/diaries play in self-model formation?**
   - Are symbolic (dreams) vs. narrative (diaries) modes different?
   - Do bot-to-bot conversations accelerate self-awareness?

4. **How do users perceive emergent self-awareness?**
   - Do they notice? Do they value it?
   - Does it increase engagement or feel uncanny?

---

## 📚 Related Resources

- `src_v2/agents/insight_graph.py` - Modified with self-observation goal
- `src_v2/agents/reflection_graph.py` - Fixed to analyze users, not characters
- `src_v2/agents/dream_graph.py` - Character dreams (unchanged)
- `src_v2/memory/diary.py` - Character diaries (unchanged)
- `docs/adr/ADR-003-EMERGENCE_PHILOSOPHY.md` - Emergence principles
- `.github/copilot-instructions.md` - Project philosophy reference

---

*"Observe first, constrain later."*
