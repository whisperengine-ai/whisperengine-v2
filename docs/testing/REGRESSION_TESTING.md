# WhisperEngine Regression Testing Guide

This guide explains how to run automated regression tests across all bots without needing to interact via Discord.

## Overview

The regression test suite tests bot functionality through the REST API, enabling:
- **Automated testing** without manual Discord interaction
- **Cross-model comparison** testing same prompts across different LLMs
- **CI/CD integration** for continuous quality assurance
- **Feature flag validation** ensuring consistent behavior

## Prerequisites

1. **Bots must be running**:
   ```bash
   ./bot.sh up all          # Start all bots
   # or
   ./bot.sh infra up        # Start just infrastructure
   python run_v2.py elena   # Start individual bot
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

## Test Categories

| Category | Description | Tests |
|----------|-------------|-------|
| `health` | API health and diagnostics | Health endpoint, DB connections, model config verification |
| `chat` | Basic chat functionality | Greetings, questions, context injection |
| `character` | Character consistency | Self-description, personality across questions |
| `memory` | Memory system | Storage, recall, user state |
| `conversation` | Multi-turn conversations | Coherence across multiple messages |
| `complexity` | Complexity routing | Simple→fast, complex→reflective mode routing |
| `comparison` | Cross-model comparison | Same prompt to all bots |
| `production` | Production stability | Rapid requests, long messages |

## Bot Configuration

### Active Bots & Ports

| Bot | Port | Model | Status |
|-----|------|-------|--------|
| elena | 8000 | openai/gpt-4o | Production |
| ryan | 8001 | meta-llama/llama-3.3-70b-instruct | Test |
| dotty | 8002 | openai/gpt-4o | Production |
| aria | 8003 | google/gemini-2.5-flash | Test |
| dream | 8004 | deepseek/deepseek-r1 | Test |
| jake | 8005 | anthropic/claude-3.5-sonnet | Test |
| sophia | 8006 | google/gemini-2.5-pro | Test |
| marcus | 8007 | mistralai/mistral-large | Test |
| nottaylor | 8008 | openai/gpt-4o | Production |

### Feature Flags (Should Be Consistent)

All bots should have these flags set identically for consistent testing:

```bash
ENABLE_REFLECTIVE_MODE=true
ENABLE_RUNTIME_FACT_EXTRACTION=true
ENABLE_PROACTIVE_MESSAGING=true
ENABLE_PROMPT_LOGGING=true
ENABLE_CHANNEL_LURKING=true
ENABLE_MANIPULATION_TIMEOUTS=false
ENABLE_GOAL_STRATEGIST=true
ENABLE_TRACE_LEARNING=true
ENABLE_AUTONOMOUS_DRIVES=true
ENABLE_UNIVERSE_EVENTS=true
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
