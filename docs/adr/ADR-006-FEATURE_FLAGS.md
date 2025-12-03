# ADR-006: Feature Flags for LLM Cost Control

**Status:** ✅ Accepted  
**Date:** November 2025  
**Deciders:** Mark Castillo

---

## Context

WhisperEngine uses multiple LLM calls per user message:
- Classification (~$0.001)
- Context retrieval (free, but latency)
- Main response (~$0.01-0.05)
- Reflective mode tools (~$0.02-0.10 for complex queries)
- Fact extraction (~$0.005)
- Image generation (~$0.04-0.10)
- Voice synthesis (~$0.01-0.05)

**The problems:**
1. **Runaway Costs**: A popular bot with reflective mode + image gen could cost $100+/day
2. **Development Surprises**: Testing with all features on burns through credits
3. **Per-Bot Customization**: Some bots need image gen, others don't
4. **A/B Testing**: Hard to compare cost/quality tradeoffs without toggles

---

## Decision

**All expensive LLM operations are gated by feature flags** in settings.

### Flag Categories

| Category | Flag | Default | Cost Impact |
|----------|------|---------|-------------|
| **Cognitive** | `ENABLE_REFLECTIVE_MODE` | `false` | $0.02-0.10/complex query |
| **Cognitive** | `ENABLE_RUNTIME_FACT_EXTRACTION` | `true` | $0.001/message |
| **Generation** | `ENABLE_IMAGE_GENERATION` | `true` | $0.04-0.10/image |
| **Generation** | `ENABLE_VOICE_RESPONSES` | `false` | $0.01-0.05/audio |
| **Engagement** | `ENABLE_PROACTIVE_MESSAGING` | `false` | $0.01-0.03/proactive |
| **Background** | `ENABLE_GRAPH_WALKER` | `false` | $0.01-0.02/walk |

### Implementation Pattern

```python
# Always check flag before expensive operation
if settings.ENABLE_REFLECTIVE_MODE and complexity >= "COMPLEX_MID":
    return await self.reflective_agent.process(message)
else:
    return await self.fast_response(message)  # Cheap fallback
```

---

## Consequences

### Positive

1. **Cost Predictability**: Disable expensive features to cap daily spend.

2. **Per-Bot Configuration**: Production bot (nottaylor) can have different flags than dev bot (elena).

3. **Graceful Degradation**: System works with any combination of flags.

4. **Easy A/B Testing**: Enable reflective mode for elena, disable for aria, compare quality.

5. **Development Safety**: Run with minimal flags during development.

### Negative

1. **Configuration Complexity**: More settings to manage across 10+ bots.

2. **Feature Drift**: Easy to forget a feature is disabled and wonder why it doesn't work.

3. **Testing Matrix**: Should test with various flag combinations.

### Neutral

1. **Documentation Overhead**: Must document which flags affect which behaviors.

2. **Per-Environment Files**: Each bot has `.env.{bot_name}` with its flags.

---

## Alternatives Considered

| Alternative | Pros | Cons | Why Rejected |
|-------------|------|------|--------------|
| **No Flags** | Simpler config | No cost control | Unacceptable cost risk |
| **Global On/Off** | Simple | All-or-nothing | Can't customize per bot |
| **Quota System Only** | Still get features, just limited | Complex to implement | Flags are simpler, quotas can layer on top |
| **Per-User Flags** | Granular control | Database queries, complexity | Overkill for solo developer |

---

## Implementation

### Settings Definition

```python
# src_v2/config/settings.py

class Settings(BaseSettings):
    # --- Cost Control Feature Flags ---
    
    # Cognitive features
    ENABLE_REFLECTIVE_MODE: bool = False  # ReAct loop for complex queries
    ENABLE_RUNTIME_FACT_EXTRACTION: bool = True  # Extract facts during conversation
    ENABLE_PREFERENCE_EXTRACTION: bool = True  # Detect "be concise" style hints
    
    # Generation features
    ENABLE_IMAGE_GENERATION: bool = True  # Generate images on request
    ENABLE_VOICE_RESPONSES: bool = False  # TTS audio responses
    
    # Engagement features
    ENABLE_PROACTIVE_MESSAGING: bool = False  # Bot initiates contact
    
    # Background processing
    ENABLE_GRAPH_WALKER: bool = False  # Graph exploration for dreams/diaries
    ENABLE_GRAPH_ENRICHMENT: bool = False  # Proactive edge creation
    
    # Quotas (layer on top of flags)
    DAILY_IMAGE_QUOTA: int = 5  # Max images per user per day
    DAILY_AUDIO_QUOTA: int = 10  # Max audio clips per user per day
```

### Per-Bot Configuration

```bash
# .env.elena (development primary)
ENABLE_REFLECTIVE_MODE=true
ENABLE_IMAGE_GENERATION=true
ENABLE_VOICE_RESPONSES=true
ENABLE_GRAPH_WALKER=true

# .env.nottaylor (production)
ENABLE_REFLECTIVE_MODE=true
ENABLE_IMAGE_GENERATION=true
ENABLE_VOICE_RESPONSES=false  # Cost control
ENABLE_GRAPH_WALKER=false     # Cost control

# .env.aria (test bot)
ENABLE_REFLECTIVE_MODE=false  # Testing fast mode only
ENABLE_IMAGE_GENERATION=false
```

### Usage Pattern

```python
# In classifier
if settings.ENABLE_VOICE_RESPONSES:
    prompt += "\n- voice: User wants audio response"

# In response generation
if settings.ENABLE_IMAGE_GENERATION and "image" in intents:
    complexity = max(complexity, "COMPLEX_MID")  # Promote to tool-enabled mode

# In dreams
if settings.ENABLE_GRAPH_WALKER:
    connections = await graph_walker.explore_for_dream(seeds)
else:
    connections = []  # Fallback: no graph exploration
```

---

## Cost Monitoring

Feature flags work with cost observability:

```python
# Log cost per operation to InfluxDB
await influxdb.write("llm_cost", {
    "bot_name": bot_name,
    "operation": "reflective_response",
    "model": "gpt-4o",
    "tokens_in": tokens.input,
    "tokens_out": tokens.output,
    "cost_usd": estimated_cost,
})
```

Dashboard shows:
- Cost by bot
- Cost by operation type
- Cost by feature flag combination

---

## References

- Settings: [`src_v2/config/settings.py`](../../src_v2/config/settings.py)
- Bot configurations: [`.env.{bot_name}`](../../) files
- Cost tracking: [`docs/architecture/OBSERVABILITY.md`](../architecture/OBSERVABILITY.md)
