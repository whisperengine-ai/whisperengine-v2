# Complexity Classifier Observability

**Document Version:** 1.1
**Created:** November 28, 2025
**Completed:** November 28, 2025
**Status:** ✅ Complete
**Priority:** 🔴 High
**Complexity:** 🟢 Low
**Estimated Time:** 1 day

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | External architecture review |
| **Proposed by** | External reviewer (gap analysis) |
| **Catalyst** | Classifier routing decisions invisible |
| **Key insight** | Need metrics to understand routing patterns |

---

## Executive Summary

The `ComplexityClassifier` routes messages to Fast Mode (SIMPLE) or Reflective Mode (COMPLEX). This routing decision has major impact on response quality, latency, and cost.

**Implementation:** Added InfluxDB metrics to `src_v2/agents/classifier.py` that record every classification decision with:
- `bot_name`, `predicted` complexity, `intents`
- `message_length`, `history_length`, `classification_time_ms`
- `used_trace` (Adaptive Depth), `trace_similarity`
- `has_documents`, `has_history`

**The Problem (Solved):**
- ~~No metrics on classification decisions~~
- ~~Can't measure false positive rate (SIMPLE→COMPLEX = slow)~~
- ~~Can't measure false negative rate (COMPLEX→SIMPLE = shallow)~~
- No way to correlate classification with user satisfaction
- No data to improve classifier prompts

**The Solution:**
Add InfluxDB metrics for every classification decision, enabling accuracy analysis and continuous improvement.

---

## 👤 User Impact

**Without tracking:**
- Users asking deep questions get shallow responses (false negative)
- Users asking simple questions wait 8 seconds (false positive)
- We have no data to fix these issues

**With tracking:**
- Identify patterns where classifier fails
- Tune thresholds based on real data
- Build training data for classifier improvement

---

## 🔧 Technical Design

### 1. Metrics to Track

For every classification decision:

```python
// Pseudocode - InfluxDB point structure
classification_metric = {
    measurement: "complexity_classification",
    tags: {
        bot_name: "elena",
        predicted: "SIMPLE",  // What classifier said
        has_history: "true",  // Was there chat history?
        has_images: "false",  // Were images attached?
        has_documents: "false",  // Was document context present?
        used_trace: "false",  // Did Adaptive Depth override?
    },
    fields: {
        message_length: 42,
        history_length: 4,
        classification_time_ms: 120,
        trace_similarity: 0.0,  // If Adaptive Depth found match
    },
    time: timestamp
}
```

### 2. Satisfaction Correlation (Future)

Track downstream signals to correlate with classification:

```python
// When user reacts to a message
satisfaction_metric = {
    measurement: "response_satisfaction",
    tags: {
        bot_name: "elena",
        complexity_used: "SIMPLE",  // From original classification
        reaction_type: "positive",  // thumbs_up, heart, etc.
    },
    fields: {
        response_time_ms: 1500,
        message_id: "...",
    }
}
```

### 3. Implementation

**Update `src_v2/agents/classifier.py`:**

```python
// In ComplexityClassifier.classify()
async def classify(self, text: str, ...) -> Dict[str, Any]:
    start_time = time.time()
    
    // ... existing classification logic ...
    
    // NEW: Log metric
    await self._log_classification_metric(
        predicted=result["complexity"],
        message_length=len(text),
        history_length=len(chat_history) if chat_history else 0,
        has_images=bool(image_urls),
        has_documents=history_has_documents,
        used_trace=bool(historical_complexity),
        trace_similarity=trace_score if historical_complexity else 0.0,
        classification_time_ms=(time.time() - start_time) * 1000
    )
    
    return result

async def _log_classification_metric(self, **kwargs):
    if not db_manager.influxdb_write_api:
        return
    
    from influxdb_client import Point
    point = Point("complexity_classification") \
        .tag("bot_name", settings.DISCORD_BOT_NAME) \
        .tag("predicted", kwargs["predicted"]) \
        .tag("has_history", str(kwargs["history_length"] > 0).lower()) \
        .tag("has_images", str(kwargs["has_images"]).lower()) \
        .tag("has_documents", str(kwargs["has_documents"]).lower()) \
        .tag("used_trace", str(kwargs["used_trace"]).lower()) \
        .field("message_length", kwargs["message_length"]) \
        .field("history_length", kwargs["history_length"]) \
        .field("classification_time_ms", kwargs["classification_time_ms"]) \
        .field("trace_similarity", kwargs["trace_similarity"])
    
    db_manager.influxdb_write_api.write(
        bucket=settings.INFLUXDB_BUCKET,
        record=point
    )
```

### 4. Grafana Dashboard

Create dashboard with panels:

| Panel | Query | Purpose |
|-------|-------|---------|
| Classification Distribution | `count by predicted` | Are we routing correctly? |
| SIMPLE vs COMPLEX Over Time | `count by predicted, time` | Trends in complexity |
| Avg Classification Time | `mean(classification_time_ms)` | Latency impact |
| Trace Hit Rate | `count where used_trace=true` | Adaptive Depth effectiveness |
| Classification by Message Length | `mean(message_length) by predicted` | Length correlation |

---

## 📋 Implementation Plan

| Step | Task | Time |
|------|------|------|
| 1 | Add metric logging to `ComplexityClassifier.classify()` | 1-2 hours |
| 2 | Create Grafana dashboard `Classification Analytics` | 1-2 hours |
| 3 | Add satisfaction correlation in `on_reaction_add()` | 1 hour |
| 4 | Document metric schema in `docs/architecture/METRICS.md` | 30 min |
| 5 | Backfill: Add complexity tag to response metrics | 30 min |

---

## ⚠️ Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| InfluxDB write adds latency | Writes are batched and async; <1ms impact |
| High cardinality tags | Avoid user_id as tag; keep to bot_name + enum values |
| Dashboard noise | Aggregate to 1-minute buckets for visualization |

---

## 🎯 Success Criteria

- [ ] Every classification decision logged to InfluxDB
- [ ] Grafana dashboard showing classification distribution
- [ ] Can query: "What % of SIMPLE classifications came from messages >100 chars?"
- [ ] Can correlate: "Do COMPLEX classifications get more positive reactions?"
- [ ] <1ms added latency to classification

---

## 🔮 Future Enhancements

1. **User Feedback Signal**: Add `/feedback slow` command to report false positives
2. **A/B Testing**: Route 10% of SIMPLE to COMPLEX, measure quality delta
3. **Auto-Tuning**: If SIMPLE responses get 50% fewer positive reactions, promote more to COMPLEX
4. **Classifier Training**: Use logged data to fine-tune classifier prompt

---

## 📚 Related Documents

- `src_v2/agents/classifier.py` - Classifier implementation
- `src_v2/evolution/feedback.py` - Reaction-based feedback
- `docker/grafana/` - Grafana configuration
