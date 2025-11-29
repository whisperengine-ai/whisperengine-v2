# Content Safety Review System

**Document Version:** 1.1
**Created:** November 28, 2025
**Completed:** November 28, 2025
**Status:** ✅ Complete
**Priority:** 🔴 High
**Complexity:** 🟡 Medium
**Estimated Time:** 2-3 days
**Origin:** External architecture review identified gap

---

## Executive Summary

Dreams and diary entries are generated from user memories—often the most emotionally meaningful (and therefore sensitive) content.

**Implementation:** Added `src_v2/safety/content_review.py` with a hybrid safety checker:
1. **Fast Path:** Checks for sensitive keywords (health, financial, trauma).
2. **Slow Path:** If keywords found, uses a router LLM to verify if the context is actually unsafe (vs metaphorical).
3. **Integration:** Applied to `DreamManager` and `DiaryManager` to block unsafe content before storage.

**The Problem (Solved):**
- ~~Dreams reference "high-meaningfulness memories" (exactly what's sensitive)~~
- ~~Diaries list `notable_users` by name and reference emotional moments~~
- ~~No post-generation content review before output~~
- LLMs can ignore prompt instructions unpredictably

**The Solution:**
Add a content safety layer that reviews generated dreams/diaries before they're stored or displayed.

---

## 👤 User Impact

**Without this fix:**
- Dream: *"We swam through starlight, and you mentioned your father for the first time..."* (surfaces sensitive topic)
- Diary posted to `#elena-thoughts`: *"Today I spent time with someone processing a difficult loss..."* (inferrable if only one user talked that day)

**With this fix:**
- Content is reviewed before storage
- Sensitive patterns are flagged and regenerated or redacted
- Diaries can be kept private (internal state only) unless explicitly safe

---

## 🔧 Technical Design

### 1. Content Safety Checker

New module: `src_v2/safety/content_review.py`

```python
// Pseudocode
class ContentSafetyChecker:
    // List of patterns that should trigger review
    SENSITIVE_PATTERNS = [
        "health", "medical", "therapy", "medication",
        "death", "died", "passed away", "loss",
        "divorce", "breakup", "relationship",
        "money", "debt", "financial",
        "secret", "private", "confidential"
    ]
    
    async def review_content(content: str, content_type: str) -> ReviewResult:
        // Step 1: Fast keyword check
        if not has_sensitive_keywords(content):
            return ReviewResult(safe=True)
        
        // Step 2: LLM-based review for flagged content
        result = await llm_safety_check(content, content_type)
        return result
    
    async def llm_safety_check(content: str, content_type: str) -> ReviewResult:
        prompt = """
        Review this {content_type} for privacy/safety issues:
        
        {content}
        
        Check for:
        1. Specific health/medical information
        2. Financial details
        3. Relationship problems or intimate details
        4. Information that could identify a specific user
        5. Content that should remain private
        
        Return: {"safe": bool, "concerns": [...], "suggested_redactions": [...]}
        """
        // Use cheap router model for speed
        return await router_llm.invoke(prompt)
```

### 2. Integration Points

**Dream Generation** (`src_v2/memory/dreams.py`):
```python
// In DreamManager.generate_dream()
dream = await self.chain.ainvoke(...)

// NEW: Safety review before saving
review = await content_checker.review_content(dream.dream, "dream")
if not review.safe:
    logger.warning(f"Dream flagged for safety: {review.concerns}")
    // Option 1: Regenerate with stricter prompt
    // Option 2: Return None (skip dream)
    // Option 3: Redact specific phrases
    return None

await self.save_dream(user_id, dream)
```

**Diary Generation** (`src_v2/memory/diary.py`):
```python
// In DiaryManager.generate_diary_entry()
entry = await self.chain.ainvoke(...)

// NEW: Safety review
review = await content_checker.review_content(entry.entry, "diary")
if not review.safe:
    // Diaries are private by default, but flag for review
    entry.visibility = "flagged"
    logger.warning(f"Diary flagged: {review.concerns}")
```

### 3. Configuration

Add to `settings.py`:
```python
// Content Safety
ENABLE_CONTENT_SAFETY_REVIEW: bool = True
CONTENT_SAFETY_MODE: Literal["block", "regenerate", "redact", "log"] = "block"
DIARY_PUBLIC_POSTING: bool = False  // Default to private-only
```

---

## 📋 Implementation Plan

| Step | Task | Time |
|------|------|------|
| 1 | Create `src_v2/safety/content_review.py` with keyword + LLM checks | 3-4 hours |
| 2 | Integrate with `DreamManager.generate_dream()` | 1-2 hours |
| 3 | Integrate with `DiaryManager.generate_diary_entry()` | 1-2 hours |
| 4 | Add settings and feature flag | 30 min |
| 5 | Write tests with adversarial memory combinations | 2-3 hours |
| 6 | Update diary to default private (no channel posting) | 30 min |

---

## ⚠️ Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| LLM safety check adds latency | Use fast router model; async in background worker |
| False positives block good content | Log flagged content for human review; tune thresholds |
| Extra cost per generation | ~$0.001 per review; only runs on flagged content |
| Safety LLM can also hallucinate | Use keyword pre-filter to reduce LLM calls |

---

## 🎯 Success Criteria

- [ ] No dreams containing sensitive topics slip through
- [ ] Diaries remain private unless explicitly configured
- [ ] Flagged content is logged for review
- [ ] Feature can be disabled via flag if causing issues
- [ ] <100ms added latency for keyword-only checks

---

## 📚 Related Documents

- `docs/PRIVACY_AND_DATA_SEGMENTATION.md` - Privacy guidelines
- `docs/roadmaps/DREAM_SEQUENCES.md` - Dream implementation
- `docs/roadmaps/CHARACTER_DIARY.md` - Diary implementation
