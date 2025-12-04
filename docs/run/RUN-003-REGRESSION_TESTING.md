# WhisperEngine Regression Testing Guide

---

## Origin

| Field | Value |
|-------|-------|
| **Origin** | QA automation |
| **Proposed by** | Mark (testing process) |

---

This guide explains how to run automated regression tests across all bots without needing to interact via Discord.

## Overview

The regression test suite tests bot functionality through the REST API, enabling:
- **Automated testing** without manual Discord interaction
- **Cross-model comparison** testing same prompts across different LLMs
- **CI/CD integration** for continuous quality assurance
- **Feature flag validation** ensuring consistent behavior

## Test Levels At-a-Glance

| Level | Command | Time | API Calls | Use Case |
|-------|---------|------|-----------|----------|
| **Smoke** | `--smoke` | ~1-2 min | ~18 (2/bot) | Quick health check, deploy validation |
| **Single Bot** | `--bot elena` | ~2-3 min | ~12 | Test one bot after changes |
| **Single Category** | `--category health` | ~1-2 min | ~9 (1/bot) | Focused testing |
| **Bot + Category** | `--bot elena --category chat` | ~30s | ~3 | Pinpoint testing |
| **Full Regression** | (no flags) | ~10-15 min | ~113 | Pre-release validation |
| **Production Only** | `--category production` | ~3-5 min | ~20 | Stability testing |

## Prerequisites

1. **Bots must be running** (Docker is the primary method, even for dev):
   ```bash
   ./bot.sh up all          # Start all bots
   ./bot.sh up elena        # Start single bot
   ./bot.sh infra up        # Infrastructure only (for local Python dev)
   ```

2. **Virtual environment activated**:
   ```bash
   source .venv/bin/activate
   ```

3. **All feature flags should be consistent** across `.env.{botname}` files (see Configuration section)

## Quick Start

### Smoke Test (Fastest)
Runs health checks and basic greeting for all bots (~1-2 min):
```bash
python tests_v2/run_regression.py --smoke
```

### Full Regression Suite
Runs all test categories (~10-15 min):
```bash
python tests_v2/run_regression.py
```

## Command Reference

```bash
# Run full suite
python tests_v2/run_regression.py

# Smoke test (health + basic chat only)
python tests_v2/run_regression.py --smoke

# Test specific bot
python tests_v2/run_regression.py --bot elena
python tests_v2/run_regression.py --bot aria

# Test specific category
python tests_v2/run_regression.py --category health
python tests_v2/run_regression.py --category memory

# Generate HTML report
python tests_v2/run_regression.py --report

# Combine options
python tests_v2/run_regression.py --bot elena --category chat --report

# Less verbose output
python tests_v2/run_regression.py --quiet

# With coverage (slower)
python tests_v2/run_regression.py --cov
```

### Command Options

| Option | Short | Description |
|--------|-------|-------------|
| `--bot BOT` | `-b` | Filter tests to specific bot (elena, ryan, dotty, etc.) |
| `--category CAT` | `-c` | Filter to specific test category |
| `--smoke` | `-s` | Quick health + greeting tests only |
| `--report` | `-r` | Generate HTML report in `tests_v2/reports/` |
| `--quiet` | `-q` | Less verbose output |
| `--cov` | | Enable coverage (disabled by default for speed) |

## Test Categories

| Category | Tests per Bot | Description |
|----------|---------------|-------------|
| `health` | 2 | Health endpoint, diagnostics & model verification |
| `chat` | 3 | Simple greeting, question response, context injection |
| `character` | 2 | Self-description, personality consistency |
| `memory` | 2 | Memory storage, recall verification |
| `conversation` | 1 | Multi-turn conversation flow |
| `complexity` | 2 | Simple→fast and complex→reflective routing |
| `comparison` | 1 (shared) | Same prompt to ALL bots (not per-bot) |
| `production` | 2 | Rapid requests, long message handling (production bots only) |

### Detailed Test Breakdown

**Total tests: ~113** (when all 9 bots running)

| Category | Test Method | What It Tests |
|----------|-------------|---------------|
| health | `test_health_endpoint` | `/health` returns `{"status": "healthy"}` |
| health | `test_diagnostics_endpoint` | Model config matches `.env`, DBs connected |
| chat | `test_simple_greeting` | "Hello!" gets substantive response |
| chat | `test_question_response` | "What's your favorite color?" answered |
| chat | `test_context_injection` | Channel/user context passed correctly |
| character | `test_self_description` | "Tell me about yourself" returns character info |
| character | `test_personality_consistency` | Related questions get consistent personality |
| memory | `test_memory_storage` | Conversation stored, trust initialized |
| memory | `test_memory_recall` | "My dog is X" → "What's my dog's name?" works |
| conversation | `test_conversation_flow` | 3-turn conversation maintains coherence |
| complexity | `test_simple_query_fast_mode` | "Hi!" routes to fast mode |
| complexity | `test_complex_query_routing` | Complex prompt routes appropriately |
| comparison | `test_same_prompt_all_bots` | Same sentence test across all models |
| production | `test_rapid_requests` | 5 rapid messages, 4+ succeed |
| production | `test_long_message_handling` | ~1750 char message processed |

## Bot Configuration

### Current Model Distribution (Dec 2024)

| Bot | Port | Main Model | Temp | Reflective Model | Status |
|-----|------|------------|------|------------------|--------|
| elena | 8000 | anthropic/claude-sonnet-4.5 | 0.75 | openai/gpt-4o | Personal |
| ryan | 8001 | meta-llama/llama-3.3-70b-instruct | 0.6 | anthropic/claude-3.5-sonnet | Test |
| dotty | 8002 | anthropic/claude-3.7-sonnet | 0.8 | google/gemini-2.5-flash | Personal |
| aria | 8003 | google/gemini-2.0-flash-001 | 0.5 | anthropic/claude-sonnet-4.5 | Test |
| dream | 8004 | deepseek/deepseek-r1 | 0.9 | mistralai/mistral-large | Test |
| jake | 8005 | meta-llama/llama-4-maverick | 0.5 | deepseek/deepseek-r1 | Test |
| sophia | 8006 | google/gemini-2.5-pro | 0.4 | openai/gpt-4o-mini | Test |
| marcus | 8007 | mistralai/mistral-large | 0.5 | google/gemini-2.5-pro | Test |
| nottaylor | 8008 | openai/gpt-4o | 0.85 | openai/gpt-4o | Production |

### Model Coverage

The test bots cover these LLM providers:
- **OpenAI**: GPT-4o (nottaylor), GPT-4o-mini (sophia reflective)
- **Anthropic**: Claude Sonnet 4.5 (elena), Claude 3.7 Sonnet (dotty), Claude 3.5 Sonnet (ryan reflective)
- **Google**: Gemini 2.5 Pro (sophia), Gemini 2.5 Flash (dotty reflective), Gemini 2.0 Flash (aria)
- **Meta**: Llama 4 Maverick (jake), Llama 3.3 70B (ryan)
- **Mistral**: Mistral Large (marcus)
- **DeepSeek**: DeepSeek R1 (dream)

### Feature Flags (Should Be Consistent)

All bots should have these flags set identically for consistent testing:

```bash
ENABLE_REFLECTIVE_MODE=true
ENABLE_RUNTIME_FACT_EXTRACTION=true
ENABLE_PROMPT_LOGGING=true
ENABLE_MANIPULATION_TIMEOUTS=false
ENABLE_GOAL_STRATEGIST=true
ENABLE_TRACE_LEARNING=true
ENABLE_AUTONOMOUS_DRIVES=true
ENABLE_UNIVERSE_EVENTS=true

# Social Presence & Autonomy (all bots should have these)
ENABLE_AUTONOMOUS_ACTIVITY=true
ENABLE_CHANNEL_LURKING=true
ENABLE_AUTONOMOUS_REACTIONS=true
ENABLE_AUTONOMOUS_REPLIES=true
ENABLE_CROSS_BOT_CHAT=true
```

**Excluded from testing** (audio/visual features):
- `ENABLE_VOICE_RESPONSES`
- `ENABLE_IMAGE_GENERATION`

## API Endpoints Used

The tests use these diagnostic endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/api/chat` | POST | Send message, get response |
| `/api/diagnostics` | GET | Bot config, DB status, feature flags |
| `/api/user-state` | POST | Get trust, memories, knowledge |
| `/api/conversation` | POST | Multi-turn conversation test |
| `/api/clear-user-data` | POST | Clear user data for test isolation |

See [API_REFERENCE.md](../API_REFERENCE.md) for full endpoint documentation.

## Direct API Testing

For quick manual tests without the test runner:

```bash
# Health check
curl http://localhost:8000/health

# Simple chat
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","message":"Hello!"}'

# Get diagnostics
curl http://localhost:8000/api/diagnostics

# Multi-turn conversation
curl -X POST http://localhost:8000/api/conversation \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","messages":["Hi","What is your name?"]}'

# Check user state
curl -X POST http://localhost:8000/api/user-state \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test"}'

# Clear test user data
curl -X POST http://localhost:8000/api/clear-user-data \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","clear_memories":true,"clear_trust":true}'
```

## Understanding Test Output

### Successful Run
```
tests_v2/regression/test_regression_suite.py .........
[elena] Diagnostics:
  Model: openai/gpt-4o
  DBs: {'postgres': True, 'qdrant': True, 'neo4j': True, 'redis': True}
  Uptime: 78s
.
[elena] Greeting test:
  Mode: fast
  Time: 4535ms
  Response: ¡Hola! 😊 I'm doing great...
.
======= 27 passed in 78.22s =======
```

### Key Metrics to Watch
- **Mode**: `fast` (direct LLM) vs `reflective` (ReAct reasoning)
- **Time**: Response latency in milliseconds
- **DBs**: All should be `True` for full functionality

### Common Failures

| Error | Cause | Fix |
|-------|-------|-----|
| `ConnectError` | Bot not running | `./bot.sh up {botname}` |
| `postgres: False` | DB not connected | `./bot.sh infra up` |
| `model mismatch` | Wrong model in config | Check `.env.{botname}` |
| `timeout` | Slow model response | Increase timeout in test |

## Test Isolation

Each test uses unique user IDs prefixed with `regression_test_` to avoid polluting real user data. Tests can optionally clear user data before/after runs using the `/api/clear-user-data` endpoint.

## Adding New Tests

Tests are in `tests_v2/regression/test_regression_suite.py`. To add a new test:

```python
class TestNewFeature:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("bot", BOT_CONFIGS, ids=lambda b: b.name)
    async def test_my_feature(self, bot: BotConfig):
        client = APIClient(bot.port)
        user_id = get_test_user_id(bot.name, "my_feature")
        
        try:
            result = await client.chat(user_id, "Test message")
            assert result.get("success") is True
            # Add assertions
        except httpx.ConnectError:
            pytest.skip(f"{bot.name} not running")
```

## CI/CD Integration

For GitHub Actions or similar:

```yaml
- name: Run Smoke Tests
  run: |
    source .venv/bin/activate
    python tests_v2/run_regression.py --smoke --quiet
    
- name: Run Full Regression
  run: |
    source .venv/bin/activate
    python tests_v2/run_regression.py --report
    
- name: Upload Test Report
  uses: actions/upload-artifact@v3
  with:
    name: regression-report
    path: tests_v2/reports/*.html
```

## Troubleshooting

### Bots not responding
```bash
# Check if bots are running
./bot.sh status
# or
docker ps | grep whisperengine

# Check bot logs
./bot.sh logs elena -f

# Restart specific bot
./bot.sh restart elena
```

### Database connection issues
```bash
# Check infrastructure
./bot.sh infra status

# Restart infrastructure
./bot.sh infra down && ./bot.sh infra up
```

### Slow tests
- DeepSeek R1 and Gemini Pro models are slower (~15-25s per response)
- Use `--bot elena` to test only fast GPT-4o bots
- Use `--smoke` for quick validation

---

**See Also:**
- [API_REFERENCE.md](../API_REFERENCE.md) - Full API documentation
- [copilot-instructions.md](../../.github/copilot-instructions.md) - Developer guide
