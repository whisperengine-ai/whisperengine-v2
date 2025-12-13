# WhisperEngine v2.5 Bot Configuration Audit

**Date:** December 11, 2025  
**Version:** 2.5.0  
**Purpose:** Verify all bot .env files have correct feature flags for v2.5 Unified Memory

---

## ✅ Configuration Standards (v2.5)

### Required Flags for Full Functionality

All bots should have these flags enabled for complete v2.5 features:

```bash
# === Core Memory & Knowledge ===
ENABLE_RUNTIME_FACT_EXTRACTION=true      # Extract facts to Neo4j
ENABLE_AMBIENT_GRAPH_RETRIEVAL=true      # Inject graph context (Phase E30)
ENABLE_PREFERENCE_EXTRACTION=true        # Extract user preferences

# === Graph Enrichment (Phase E25) ===
ENABLE_GRAPH_ENRICHMENT=true             # Proactive graph edge creation
ENRICHMENT_MIN_TOPIC_MENTIONS=2          # Topic → DISCUSSED edge threshold
ENRICHMENT_MIN_COOCCURRENCE=2            # Entity → RELATED_TO threshold
ENRICHMENT_MIN_INTERACTION=1             # User → CONNECTED_TO threshold
ENRICHMENT_MIN_MESSAGES=4                # Min messages before enrichment
ENRICHMENT_MAX_MESSAGES=120              # Cap batch size

# === Autonomous Activity (ADR-010) ===
ENABLE_AUTONOMOUS_ACTIVITY=true          # Master switch
ENABLE_DAILY_LIFE_GRAPH=true            # Unified polling system (Phase E31)
DISCORD_CHECK_INTERVAL_MINUTES=7         # Polling frequency
DISCORD_CHECK_RELEVANCE_THRESHOLD=0.4    # Interest threshold

# === Deprecated Flags (Keep but Disabled) ===
ENABLE_CHANNEL_LURKING=true              # DEPRECATED - now via Daily Life
ENABLE_AUTONOMOUS_REPLIES=false          # DEPRECATED - now via Daily Life
ENABLE_CROSS_BOT_CHAT=false              # DEPRECATED - now via Daily Life
ENABLE_AUTONOMOUS_REACTIONS=false        # DEPRECATED - now via Daily Life

# === Reflective Mode ===
ENABLE_REFLECTIVE_MODE=true              # ReAct reasoning loop

# === Advanced Features ===
ENABLE_GOAL_STRATEGIST=true              # Nightly goal analysis
ENABLE_TRACE_LEARNING=true               # Learn from reasoning traces
ENABLE_AUTONOMOUS_DRIVES=true            # Social Battery, Concern, Curiosity
ENABLE_UNIVERSE_EVENTS=true              # Cross-bot gossip
```

### Optional Flags (Per-Bot Customization)

```bash
# === Voice & Media ===
ENABLE_VOICE_RESPONSES=true/false        # TTS audio generation
ENABLE_IMAGE_GENERATION=true/false       # Image generation
LLM_SUPPORTS_VISION=true/false           # Image analysis

# === Observability ===
ENABLE_PROMPT_LOGGING=true/false         # Debug LLM prompts
LANGCHAIN_TRACING_V2=true/false          # LangSmith tracing

# === Safety ===
ENABLE_JAILBREAK_DETECTION=true          # Block harmful prompts
ENABLE_MANIPULATION_TIMEOUTS=true/false  # Timeout bad actors
```

---

## 📊 Bot Configuration Status

### Production Bots

| Bot | Graph Enrichment | Ambient Retrieval | Daily Life | Status |
|-----|-----------------|-------------------|------------|--------|
| **nottaylor** | ✅ | ✅ | ✅ | ✅ Compliant |
| **gabriel** | ✅ | ✅ | ✅ | ✅ Compliant |

### Development/Test Bots

| Bot | Graph Enrichment | Ambient Retrieval | Daily Life | Status |
|-----|-----------------|-------------------|------------|--------|
| **elena** | ✅ | ✅ | ✅ | ✅ Compliant |
| **dotty** | ✅ | ✅ | ✅ | ✅ Compliant |
| **aria** | ✅ | ✅ | ✅ | ✅ Compliant |
| **dream** | ✅ | ✅ | ✅ | ✅ Compliant |
| **jake** | ✅ | ✅ | ✅ | ✅ Compliant |
| **marcus** | ✅ | ✅ | ✅ | ✅ Compliant |
| **ryan** | ✅ | ✅ | ✅ | ✅ Compliant |
| **sophia** | ✅ | ✅ | ✅ | ✅ Compliant |
| **aetheris** | ✅ | ✅ | ✅ | ✅ Compliant |
| **aethys** | ✅ | ✅ | ✅ | ✅ Compliant |

---

## 🔍 Audit Results

### Summary
- **Total Bots Audited:** 12
- **Compliant:** 12
- **Missing Flags:** 0
- **Configuration Errors:** 0

### Changes Applied (Dec 11, 2025)

**Added to all bots except elena:**
```bash
ENABLE_AMBIENT_GRAPH_RETRIEVAL=true
ENABLE_GRAPH_ENRICHMENT=true
ENRICHMENT_MIN_TOPIC_MENTIONS=2
ENRICHMENT_MIN_COOCCURRENCE=2
ENRICHMENT_MIN_INTERACTION=1
ENRICHMENT_MIN_MESSAGES=4
ENRICHMENT_MAX_MESSAGES=120
```

---

## 🎯 v2.5 Unified Memory Configuration

### No New Flags Required

Unified Memory (Graph Memory Unification) is **architectural** — it works automatically with existing flags:

1. ✅ `ENABLE_RUNTIME_FACT_EXTRACTION=true` — Enables fact extraction to Neo4j
2. ✅ `ENABLE_AMBIENT_GRAPH_RETRIEVAL=true` — Injects graph context
3. ✅ `ENABLE_GRAPH_ENRICHMENT=true` — Creates new edges proactively

**The Unified Memory dual-write happens automatically when saving memories.**

### 2. Verification

Check that Unified Memory is working:

```bash
# View logs for Unified Memory activity
./bot.sh logs elena | grep -i "unified\|neighborhood"

# Expected output:
# "Retrieved 8 Unified Memory connections for 5 memories"
```

---

## 🚨 Deprecated Flags (Keep for Backward Compatibility)

These flags are **deprecated** but kept in configs for backward compatibility:

| Flag | Status | Replacement |
|------|--------|-------------|
| `ENABLE_CHANNEL_LURKING` | 🔶 Deprecated | `ENABLE_DAILY_LIFE_GRAPH` |
| `ENABLE_AUTONOMOUS_REPLIES` | 🔶 Deprecated | `ENABLE_DAILY_LIFE_GRAPH` |
| `ENABLE_CROSS_BOT_CHAT` | 🔶 Deprecated | `ENABLE_DAILY_LIFE_GRAPH` |
| `ENABLE_AUTONOMOUS_REACTIONS` | 🔶 Deprecated | `ENABLE_DAILY_LIFE_GRAPH` |

**Why keep them?**
- They're checked in code for backward compatibility
- Setting them to `false` ensures old code paths aren't triggered
- Will be fully removed in v3.0

---

## 📝 Configuration Best Practices

### For Production Bots

1. **Enable Core Features:**
   - Reflective mode: `ENABLE_REFLECTIVE_MODE=true`
   - Fact extraction: `ENABLE_RUNTIME_FACT_EXTRACTION=true`
   - Graph enrichment: `ENABLE_GRAPH_ENRICHMENT=true`

2. **Tune Autonomous Activity:**
   - Start with: `DISCORD_CHECK_RELEVANCE_THRESHOLD=0.4`
   - Increase if bot is too chatty: `0.5-0.6`
   - Decrease if bot is too quiet: `0.3-0.35`

3. **Enable Observability:**
   - `LANGCHAIN_TRACING_V2=true` for production monitoring
   - `ENABLE_PROMPT_LOGGING=false` (generates large files)

4. **Set Quotas:**
   - `DAILY_IMAGE_QUOTA=5` (cost control)
   - `DAILY_AUDIO_QUOTA=10` (cost control)
   - Add trusted users to `QUOTA_WHITELIST`

### For Development Bots

1. **Enable Everything:**
   - All features enabled for testing
   - `ENABLE_PROMPT_LOGGING=true` for debugging

2. **Lower Thresholds:**
   - `DISCORD_CHECK_RELEVANCE_THRESHOLD=0.3` (more responsive)
   - `LURK_CONFIDENCE_THRESHOLD=0.6` (legacy, but present)

3. **Full Tracing:**
   - `LANGCHAIN_TRACING_V2=true`
   - Separate `LANGCHAIN_PROJECT` per bot

---

## 🔄 Update Checklist

When adding a new bot:

- [ ] Copy `.env.bot.template` to `.env.newbot`
- [ ] Set `DISCORD_BOT_NAME=newbot`
- [ ] Set `DISCORD_TOKEN=...`
- [ ] Set LLM API keys
- [ ] Verify all flags match this audit document
- [ ] Test with: `python run_v2.py newbot`
- [ ] Add to `docker-compose.yml` with unique port

---

## 📚 Related Documentation

- `docs/spec/SPEC-E35-UNIFIED_MEMORY_GRAPH_UNIFICATION.md` — Unified Memory architecture
- `docs/adr/ADR-015-DAILY_LIFE_UNIFIED_AUTONOMY.md` — Daily Life Graph
- `docs/spec/SPEC-E25-GRAPH_WALKER_EXTENSIONS.md` — Graph enrichment
- `.env.example` — Reference configuration
- `docs/ENV_STANDARDIZATION.md` — Environment variable standards

---

**Last Updated:** December 11, 2025  
**Audited By:** AI Development Assistant  
**Next Audit:** v3.0 Release
