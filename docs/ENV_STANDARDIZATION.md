# Environment File Standardization Guide

## Overview
All `.env*` files in WhisperEngine v2 follow a consistent structure for easy navigation and editing.

## File Sections (in order)

### 1. **Application** (Lines 1-15)
- `ENVIRONMENT` - development/production/testing
- `DEBUG`, `LOG_LEVEL`
- `DM_ALLOWED_USER_IDS` - Discord user IDs allowed to DM
- `BLOCKED_USER_IDS` - Discord user IDs to ignore
- `ENABLE_PROMPT_LOGGING` - Debug mode for LLM calls

### 2. **Discord Configuration** (Lines 16-30)
- `DISCORD_TOKEN` - Bot token (REQUIRED for bots, not needed for worker)
- `DISCORD_BOT_NAME` - Bot identifier (REQUIRED)

### 3. **LLM Configuration** (Lines 31-60)
- **Main LLM**: `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL_NAME`, `LLM_TEMPERATURE`
- **Router LLM** (optional): Fast model for routing decisions
- **Reflective LLM** (optional): Advanced reasoning loop

### 4. **Databases** (Lines 61-90)
- PostgreSQL, Redis, Qdrant, Neo4j, InfluxDB
- Connection URLs and credentials
- Pool sizes and API keys

### 5. **API** (Lines 91-95)
- `API_HOST`, `API_PORT`

### 6. **Voice/Media** (Lines 96-110)
- ElevenLabs TTS configuration
- Voice settings and quotas

### 7. **Feature Flags: Knowledge & Analysis** (Lines 111-140)
- Vision support, fact extraction, preference extraction
- Proactive messaging, logging, stats footer

### 8. **Feature Flags: Channel Behavior** (Lines 141-160)
- Channel lurking, autonomous reactions
- Privacy & security, spam protection

### 9. **Media Generation** (Lines 161-175)
- Image generation settings
- API keys and model configuration

### 10. **Quotas** (Lines 176-185)
- Daily image/audio limits
- Quota whitelist

### 11. **Autonomous Agents** (Lines 186-205)
- Goal strategist, trace learning, drives, universe events
- Drift observation, manipulation detection

### 12. **Narrative Generation** (Lines 206-265)
- Character diary settings (enable, timing, richness, jitter)
- Dream sequences (enable, timing, cooldown)
- Session summarization

### 13. **Analytics & Tracing** (Lines 266-275)
- LangSmith configuration

### 14. **Bot Broadcast & Artifacts** (Lines 276-295)
- Broadcast channel settings
- Provenance display

### 15. **Cross-Bot Features** (Lines 296-325)
- Cross-bot chat, autonomous server activity
- Reminders, stigmergic discovery

### 16. **Knowledge Graph** (Lines 326-350)
- Graph walker agent settings
- Graph pruning configuration

## Standard Template

See `.env.bot.template` for a complete reference implementation with all sections and comments.

## File Types

- **`.env.example`** - Reference for local development (all features enabled)
- **`.env.example_worker`** - Reference for worker container (worker-specific flags)
- **`.env.worker`** - Production worker configuration
- **`.env.{botname}`** - Individual bot configurations (elena, nottaylor, aria, etc.)

## Migration Guide

To update an existing `.env.*` file:

1. Open `.env.bot.template` as reference
2. Copy the section order (don't reorder)
3. Preserve actual values from your current file
4. Fill in placeholders for any missing settings
5. Ensure all section headers are present (with --- comments)

## Common Issues

- **Missing sections**: Don't skip section headers, include all sections even if empty
- **Value placement**: Keep values with their comments in the correct sections
- **Consistent naming**: Use exact variable names (no variations like `LLM_CHAT_API_KEY`)
- **Grouped logically**: Related settings (min/max, hours/minutes) should be together

## Validation

Run this to check your .env file structure:
```bash
# Check for orphaned values (should be < 5)
grep "^[A-Z_]" .env.{botname} | wc -l

# Check for missing Discord config
grep "DISCORD_" .env.{botname}

# Check for missing LLM config  
grep "LLM_PROVIDER\|LLM_API_KEY\|LLM_MODEL_NAME" .env.{botname}
```
