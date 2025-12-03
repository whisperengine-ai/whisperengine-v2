# LLM-Based Sensitivity Detection

**Document Version:** 1.1
**Created:** November 28, 2025
**Completed:** November 28, 2025
**Status:** ✅ Complete
**Priority:** 🟡 Medium
**Complexity:** 🟡 Medium
**Estimated Time:** 2-3 days
**Origin:** External architecture review identified gap

---

## Executive Summary

Cross-bot knowledge sharing (stigmergy) uses keyword-based filtering for sensitive topics. Keywords miss context-dependent sensitivity.

**Implementation:** Added `src_v2/safety/sensitivity.py` with LLM-based context checker:
- Uses router model (fast/cheap) for classification
- Integrated into `EventDetector.analyze_and_publish()` before `event_bus.publish()`
- Blocks events where LLM detects personal/sensitive context that keywords missed
- Fails closed (private) if check fails

**The Problem (Solved):**
```python
// Before: Keyword-based only
SENSITIVE_TOPICS = ["health", "relationship", "finance", ...]

// Example that slips through:
"I finally told my mom about the situation"
// Keywords: "mom", "situation" - not flagged
// Reality: Could be deeply personal context
```

**The Solution:**
Add LLM-based sensitivity detection as a second layer for content that passes keyword checks.

---

## 👤 User Impact

**Without LLM detection:**
- User tells Elena about a personal situation (no sensitive keywords)
- Elena stores observation in shared graph
- Marcus discovers via stigmergy: *"Elena mentioned you had a situation with your mom..."*
- User feels surveilled

**With LLM detection:**
- LLM reviews context: "This appears to be personal family matter"
- Observation marked as sensitive, not shared
- User privacy preserved

---

## 🔧 Technical Design

### 1. Two-Layer Detection

```
Message Content
     │
     ▼
┌─────────────────┐
│ Keyword Filter  │ ◄── Fast, catches obvious cases
│ (existing)      │
└────────┬────────┘
         │ passes
         ▼
┌─────────────────┐
│ LLM Sensitivity │ ◄── Context-aware, catches nuance
│ Check           │
└────────┬────────┘
         │
         ▼
    Share/Block
```

### 2. LLM Sensitivity Checker

New function in `src_v2/universe/bus.py` or new module `src_v2/safety/sensitivity.py`:

```python
// Pseudocode
class SensitivityChecker:
    def __init__(self):
        // Use fast, cheap model for classification
        self.llm = create_llm(temperature=0.0, mode="router")
    
    async def is_sensitive(self, content: str, topic: str) -> Tuple[bool, str]:
        """
        LLM-based sensitivity check for content that passed keyword filter.
        
        Returns: (is_sensitive: bool, reason: str)
        """
        prompt = """
        Analyze if this content should be kept private between the user and this bot,
        or if it's safe to share with other AI characters.
        
        Content: {content}
        Topic: {topic}
        
        Consider:
        1. Personal family matters (even without "family" keyword)
        2. Emotional struggles or vulnerabilities
        3. Workplace/school conflicts
        4. Relationship dynamics (friendships, not just romantic)
        5. Health-adjacent topics (stress, sleep, energy)
        6. Financial stress (without money keywords)
        7. Anything the user might not want repeated
        
        Return JSON: {"sensitive": bool, "reason": "brief explanation"}
        """
        
        result = await self.llm.ainvoke(prompt.format(
            content=content,
            topic=topic
        ))
        
        return result.sensitive, result.reason
```

### 3. Integration with Event Bus

Update `src_v2/universe/bus.py`:

```python
// In UniverseEventBus.publish()
async def publish(self, event: UniverseEvent) -> bool:
    // ... existing checks ...
    
    // Block sensitive topics (keyword check - fast)
    if event.is_sensitive():
        self._log_blocked_metric("sensitive_topic")
        return False
    
    // NEW: LLM sensitivity check for borderline cases
    if settings.ENABLE_LLM_SENSITIVITY_CHECK:
        is_sensitive, reason = await sensitivity_checker.is_sensitive(
            event.summary, 
            event.topic
        )
        if is_sensitive:
            logger.info(f"LLM blocked sensitive event: {reason}")
            self._log_blocked_metric("llm_sensitive")
            return False
    
    // ... continue to enqueue ...
```

### 4. Caching for Efficiency

```python
// Cache LLM decisions to avoid repeated calls
class SensitivityChecker:
    def __init__(self):
        self.cache = {}  // Simple in-memory cache
        self.cache_ttl = 3600  // 1 hour
    
    async def is_sensitive(self, content: str, topic: str) -> Tuple[bool, str]:
        cache_key = hashlib.md5(f"{content}:{topic}".encode()).hexdigest()
        
        if cache_key in self.cache:
            entry = self.cache[cache_key]
            if time.time() - entry["timestamp"] < self.cache_ttl:
                return entry["sensitive"], entry["reason"]
        
        // ... LLM call ...
        
        self.cache[cache_key] = {
            "sensitive": result.sensitive,
            "reason": result.reason,
            "timestamp": time.time()
        }
```

### 5. Configuration

Add to `settings.py`:

```python
// LLM Sensitivity Detection
ENABLE_LLM_SENSITIVITY_CHECK: bool = True
LLM_SENSITIVITY_CACHE_TTL: int = 3600  // seconds
```

---

## 📋 Implementation Plan

| Step | Task | Time |
|------|------|------|
| 1 | Create `src_v2/safety/sensitivity.py` with LLM checker | 2-3 hours |
| 2 | Add caching layer | 1 hour |
| 3 | Integrate with `UniverseEventBus.publish()` | 1 hour |
| 4 | Add InfluxDB metrics for LLM blocks | 30 min |
| 5 | Write tests with edge cases | 2-3 hours |
| 6 | Add settings and feature flag | 30 min |

---

## ⚠️ Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| LLM adds latency to event publishing | Events already async via worker; no user-facing impact |
| LLM costs per check | Use cheap router model (~$0.0001); cache responses |
| False positives block harmless content | Log all blocks; tune prompt based on patterns |
| LLM can be inconsistent | Use temperature=0.0; cache identical queries |

---

## 🎯 Success Criteria

- [ ] Context-dependent sensitive content blocked (e.g., "mom situation")
- [ ] Keyword-safe but emotionally vulnerable content caught
- [ ] <5% false positive rate on benign content
- [ ] Metrics show what's being blocked and why
- [ ] No increase in user-facing latency

---

## 📊 Metrics to Track

```python
// InfluxDB points
sensitivity_check = {
    measurement: "sensitivity_check",
    tags: {
        bot_name: "elena",
        check_type: "llm",  // or "keyword"
        result: "blocked",  // or "passed"
    },
    fields: {
        reason: "personal family matter",
        check_time_ms: 150,
    }
}
```

---

## 🔮 Future Enhancements

1. **User Preference Learning**: If user says "don't share work stuff", remember and apply
2. **Topic-Specific Models**: Fine-tune sensitivity for specific domains
3. **Retroactive Review**: Scan existing graph for previously-missed sensitive content
4. **User Audit**: Let users see what was/wasn't shared about them

---

## 📚 Related Documents

- `src_v2/universe/bus.py` - Event bus implementation
- `docs/PRIVACY_AND_DATA_SEGMENTATION.md` - Privacy guidelines
- `docs/roadmaps/EMERGENT_UNIVERSE.md` - Stigmergy architecture
