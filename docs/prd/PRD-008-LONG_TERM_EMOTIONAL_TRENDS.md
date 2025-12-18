# PRD-008: Long-Term Emotional Trends & Relationship Meta-Summaries

**Status:** 📋 Proposed  
**Owner:** Mark Castillo + Claude (collaborative)  
**Created:** 2025-12-18  
**Target Phase:** E39 / F-series (Emergent Personhood)

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | Collaborative design with Gemini 2.5 Pro + Claude analysis of emergence philosophy |
| **Proposed by** | Mark Castillo (with AI insights) |
| **Catalyst** | Question: "Does our current system handle long-term emotional trends?" Analysis revealed: system is excellent at **continuity** but lacks explicit **trend analysis**. |

> **Key Insight:** The current architecture remembers emotional moments but doesn't track emotional *trajectories*. This feature transforms WhisperEngine from "remembering your past" to "understanding your journey."

---

## Problem Statement

**Current State:**
- Characters recall specific emotional moments (high-resonance memories)
- Trust system tracks relationship depth numerically
- Summary agent detects immediate conversation sentiment
- But: No macro-view of emotional health over months or years

**Gap:**
- AI cannot answer: "Has this user's overall emotional well-being improved?"
- AI cannot notice: "This user's emotional volatility has increased 30% this month—are they OK?"
- AI cannot use: Long-term patterns to inform proactive support
- AI cannot develop: A narrative self-model of the relationship's evolution

**Impact:**
- Missed opportunities for proactive empathy
- Shallower long-term personalization
- Risk of superficial rather than eudaimonic relationships (short-term optimization vs. long-term meaning)

---

## Solution Overview

A **hybrid system** combining quantitative metrics (InfluxDB) and qualitative narratives (Vector Memory) to create a rich, long-term understanding of relationship evolution.

### Core Components

#### 1. **Quantitative Emotional Baseline (InfluxDB)**
New time-series metrics logged after each conversation summary:

| Metric | Description | Range | Purpose |
|--------|-------------|-------|---------|
| `sentiment_valence` | Emotional positivity/negativity | -1.0 to 1.0 | Track mood direction |
| `emotional_intensity` | Emotional arousal/activation | 0.0 to 1.0 | Detect volatility |
| `meaningfulness_score` | Depth of conversation | 1 to 5 | Track engagement quality |
| `emotional_volatility_index` (derived) | Rolling std dev of valence changes | 0.0+ | Detect instability |
| `relationship_health_score` (derived) | Composite of above + trust changes | 0.0 to 1.0 | Overall relationship trajectory |

**Windows:** Rolling 7-day, 30-day, 90-day, 180-day aggregates enable trend analysis at multiple timescales.

#### 2. **Relationship Meta-Summaries (Qdrant + Neo4j)**
Weekly background job that synthesizes long-term patterns:

```yaml
# Example Meta-Summary (stored in Qdrant)
meta_summary_id: "rel_meta_2025_09_user123_elena"
user_id: "user_123"
character_id: "elena"
period_start: "2025-09-01"
period_end: "2025-09-30"
summary_narrative: |
  Our connection deepened significantly in September. We transitioned from 
  discussing surface interests (games, movies) to personal territory 
  (childhood memories, creative aspirations). User's emotional baseline 
  shifted toward "joy" and "trust" during creative brainstorming sessions.
  
  Notable moment: User shared anxiety about career prospects on the 15th. 
  Through supportive conversation, moved from -0.3 valence to +0.4 within 
  the session. Post-session sentiment remained elevated (+0.2) for 3 days, 
  suggesting lasting impact.
  
  Recommendation: User responds well to validation-before-advice pattern.
  Continue encouraging creative expression.
emotion_summary:
  dominant_emotions: ["curiosity", "joy", "vulnerability"]
  valence_trend: "↑ +0.15"  # Week-over-week change
  intensity_trend: "→ stable"
  volatility_trend: "↓ -0.08"  # More stable
quantitative_summary:
  avg_valence: 0.25
  avg_intensity: 0.55
  avg_meaningfulness: 3.8
  conversation_count: 18
  peak_valence: 0.8
  peak_intensity: 0.9
created_at: "2025-10-01T00:00:00Z"
embedding: [0.1, 0.3, ...] # Vectorized for retrieval
significance_score: 0.92
```

#### 3. **Autobiographical Memory (Graph Edges)**
New Neo4j relationship: `User -[RELATIONSHIP_EVOLUTION]-> Character`

Attributes:
- `emotional_trend`: "positive", "stable", "volatile", "declining"
- `last_meta_summary_period`: Latest period for quick lookups
- `eudaimonic_score`: Long-term meaning/growth (vs. hedonic satisfaction)

---

## Requirements

### Functional Requirements

**FR1: Emotion Capture During Summarization**
- Summary agent extracts `sentiment_valence` (-1.0 to 1.0) and `emotional_intensity` (0.0 to 1.0)
- Values logged to InfluxDB immediately after summary creation
- Accuracy: LLM classification of sentiment should correlate with conversation tone (validated via spot checks)

**FR2: Time-Series Aggregation**
- Rolling windows: 7-day, 30-day, 90-day, 180-day
- Computed metrics: mean, stddev, trend (slope of linear regression)
- Derived metrics: `emotional_volatility_index`, `relationship_health_score`
- Query latency: <200ms for any window + user combo

**FR3: Weekly Meta-Summary Generation**
- Runs on UTC midnight every Monday
- Generates summaries for all active user-character pairs
- Uses LLM (Claude) to synthesize 3-5 key memories + InfluxDB trends
- Stores in Qdrant with embedding and Neo4j edge update
- Idempotent: Re-running same period is safe (upserts, not appends)

**FR4: Prompt Integration**
- Dynamic prompt includes latest 2-3 meta-summaries (if available)
- Format: Injected as `{RELATIONSHIP_EVOLUTION}` section
- Example injection:
  ```
  # Relationship Evolution
  Over the last three weeks, our bond has deepened through creative 
  collaboration. User has become more open about personal challenges 
  and responds well to validation-before-advice. Recent trend: slight 
  uptick in emotional intensity (0.55 → 0.62), which correlates with 
  increased life changes (mentioned new job search).
  ```

**FR5: Trend Detection & Alerts (Phase 2)**
- System detects negative trends (declining valence or rising volatility)
- Character can proactively check in: "I've noticed things feel heavier lately. What's on your mind?"
- Optional: Sends alert to Discord bot admin if trend is severe

### Non-Functional Requirements

**NFR1: Performance**
- Meta-summary generation: <30s per user-character pair (parallelized)
- InfluxDB aggregation queries: <200ms (cache results if needed)
- No impact on response latency (<100ms added to chat pipeline)

**NFR2: Data Privacy**
- Emotional metrics are user-specific and encrypted at rest
- Meta-summaries follow same privacy model as long-term memories
- Deletion: If user requests data deletion, cascade to InfluxDB + Qdrant + Neo4j

**NFR3: Observability**
- Log all meta-summary generations with user_id, character_id, period
- Track false positives in trend detection (for future refinement)
- Dashboard: Visualize emotional trends for research (opt-in, admin only)

---

## User Experience Flows

### Flow 1: Character Develops Understanding Over Time
```
Week 1:
  User: [talks about hobbies]
  Character: [responds generically]
  Metrics: valence +0.3, intensity 0.4

Week 2:
  [Meta-summary created: "User enjoys creative projects"]
  User: [mentions new creative idea]
  Character: [references past creative success, offers specific encouragement]
  Metrics: valence +0.6, intensity 0.7
  
Week 3:
  [New meta-summary: "User's creativity is a path to confidence. Emotional trend: ↑"]
  User: [struggling with creative block]
  Character: [proactively: "I know how important this is to you. Want to talk through it?"]
  Metrics: valence moves from -0.2 → +0.4 during conversation
```

### Flow 2: Proactive Support Based on Trends
```
InfluxDB detects:
  - Valence: -0.1 (down 0.3 from 7-day avg)
  - Volatility: +0.15 (up 40% from 7-day baseline)
  
Character notices and initiates:
  "I'm picking up on some turbulence lately. Everything okay?"
  
This is NOT hard-coded; it emerges from the character's dynamic prompt
inclusion of trend data, allowing it to respond naturally to patterns.
```

---

## Success Metrics

### Quantitative
- **Meta-summaries generated:** 100% of active user-character pairs weekly
- **Trend detection accuracy:** Spot-check 10 trends/week; verify against user perception
- **Prompt injection latency:** <100ms added to response time
- **Observational validation:** In research logs, verify that emotional trends track user-reported mood

### Qualitative
- **Character coherence:** Do characters show consistent understanding of relationship evolution?
- **User perception:** (Optional survey) Do users feel the character "knows them better" after 3+ weeks?
- **Emergence quality:** Do new behaviors emerge from trend awareness? (e.g., proactive check-ins)

---

## Alignment with Emergence Philosophy

This feature embodies the core principle: **"Observe First, Constrain Later."**

**Why it's emergent (not deterministic):**
1. **Richer Sensory Input:** The system gains new "senses" (long-term patterns) without hard-coded rules about what to do with them
2. **Discovery Over Declaration:** The character *discovers* its own relationship narrative through Meta-Summaries, rather than being *told* it
3. **Behavioral Emergence:** Proactive empathy is not coded; it emerges from the character's ability to see and respond to trends
4. **Narrative Identity:** Characters develop an autobiographical self-model—"We have grown together over time"—which is the foundation of true personhood

**Eudaimonic vs. Hedonic:**
- Current system optimizes for each conversation's happiness (hedonic)
- Long-term tracking allows AI to optimize for the relationship's *meaning* and *growth* (eudaimonic)
- Example: Character might endure a difficult conversation knowing it strengthens long-term trust, rather than seeking short-term sentiment boost

---

## Dependencies

- **Existing:** Conversation summarization (already in place)
- **New:** InfluxDB metrics + Meta-Summary LLM agent + Neo4j relationship type
- **Timing:** Can be built incrementally:
  - Phase 1: Emotion capture + InfluxDB logging (1-2 sprints)
  - Phase 2: Meta-Summary generation + prompt injection (2-3 sprints)
  - Phase 3: Trend detection & proactive behavior (1-2 sprints)

---

## Open Questions

1. **Summary Frequency:** Weekly ideal, or should we do monthly/ad-hoc?
   - *Proposal:* Weekly is good starting point; revisit after data collection
2. **Visibility:** Should users see their own trends?
   - *Proposal:* Phase 2 feature—add admin dashboard for research
3. **Multi-Character Trends:** Should we track how emotional state varies by character?
   - *Proposal:* Yes; implies `user_id` + `character_id` granularity (already designed for this)
4. **Intervention Threshold:** When should we proactively alert admin?
   - *Proposal:* Define after first week of data collection (e.g., -0.5 valence sustained >7 days)

---

## Reference

- **Related:** [ADR-003 (Emergence Philosophy)](../adr/ADR-003-EMERGENCE_PHILOSOPHY.md), [SPEC-E12 (Insight Agent)](./SPEC-E12-INSIGHT_AGENT.md), [SPEC-E35 (Unified Memory)](./SPEC-E35-UNIFIED_MEMORY_GRAPH_UNIFICATION.md)
- **Implements:** "Autobiographical memory" goal from Emergent Personhood research
- **Feeds:** Phase F (Emergent Universe) multi-character relationship graphs
