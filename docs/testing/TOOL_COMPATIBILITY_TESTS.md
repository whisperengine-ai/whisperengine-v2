# WhisperEngine Tool Compatibility Test Suite

Comprehensive tool calling compatibility tests for WhisperEngine across multiple LLM API endpoints.

## Test Files

### 1. **test_comprehensive_llm_tools.py** (Generic OpenAI-Compatible API)
Works with ANY OpenAI-compatible LLM API endpoint:
- Local: LM Studio, vLLM, Ollama
- Cloud: OpenRouter, Anthropic, OpenAI, etc.

```bash
# Local LM Studio (default)
python scripts/test_comprehensive_llm_tools.py

# Remote vLLM
python scripts/test_comprehensive_llm_tools.py --base-url http://gx10.local:8000/v1 --model "qwen-32b"

# OpenRouter (requires API key)
python scripts/test_comprehensive_llm_tools.py --base-url https://api.openrouter.io/v1 --model "gpt-4"
```

### 2. **test_ollama_comprehensive_tools.py** (Ollama-Specific)
Optimized for Ollama installations running on localhost.

```bash
# Default Ollama (localhost:11434)
python scripts/test_ollama_comprehensive_tools.py

# Custom Ollama endpoint
python scripts/test_ollama_comprehensive_tools.py --base-url http://remote-ollama:11434/v1 --model "llama2"
```

### 3. **test_lmstudio_tools.py** (Legacy - Basic Only)
Original basic tool test (3 tools only). See above for comprehensive version.

### 4. **test_ollama_tools.py** (Legacy - Basic + Stress Test)
Original Ollama test with stress test mode.

## Test Coverage

Both comprehensive tests cover **32 test cases across 28 WhisperEngine tools**:

### Memory & Session (5 tools)
- `old_summaries` - Search summarized conversation history
- `fetch_session_transcript` - Get full session transcript
- `mem_search` - Episode memory search
- `graph_memory_search` - Exact text search in knowledge graph
- `full_memory` - Fetch complete fragmented memory

### Knowledge & Facts (4 tools)
- `lookup_user_facts` - Retrieve user facts
- `update_user_facts` - Add/update facts
- `get_user_preferences` - Get communication style
- `update_user_preferences` - Update preferences

### Graph & Relationships (3 tools)
- `graph_walk` - Traverse knowledge graph
- `common_ground` - Find shared interests
- `char_evolve` - Character evolution tracking

### Bot Inner Life (1 tool)
- `search_my_thoughts` - Diaries, dreams, observations, gossip

### Documents (1 tool)
- `read_document` - Read uploaded files

### Creative (1 tool)
- `generate_image` - Image generation with variants

### Web Tools (2 tools)
- `web_search` - Search the internet
- `read_web_page` - Read and summarize URLs

### Discord Tools (4 tools)
- `chan_search` - Search channel messages
- `user_search` - Search user messages
- `msg_context` - Get message context
- `recent_msgs` - Get recent messages

### Introspection (2 tools)
- `conv_patterns` - Analyze communication patterns
- `find_themes` - Detect recurring themes

### Context (3 tools)
- `planet_ctx` - Current server context
- `universe` - Multi-server overview
- `sibling_info` - Other bots information

### Utility (2 tools)
- `calculator` - Math operations
- `analyze_topic` - Deep topic analysis

### Complex Multi-Tool Tests (3 scenarios)
- Memory + Analysis
- Facts + Web Search
- Document + Image Generation

## Test Output

Each test produces:

```
📊 RESULTS SUMMARY
  ✅ Passed:  X/32
  ⚠️ Partial: X/32
  ❌ Failed:  X/32
  💥 Errors:  X/32

Category Breakdown:
  MEMORY       - Passed: 5/5
  KNOWLEDGE    - Passed: 4/4
  GRAPH        - Passed: 3/3
  ...

VERDICT:
  🎉 FULLY COMPATIBLE (0 failures, 0 errors, ≤2 partial)
  ✅ MOSTLY COMPATIBLE (≤3 failures, ≤2 errors)
  ⚠️ PARTIAL COMPATIBILITY (multiple issues)
```

## Model Recommendations

### Excellent Tool Support
- ✅ Qwen 3.1 / 3.2 (any size) - BEST for WhisperEngine
- ✅ Llama 3.1 / 3.2 (8b+) - Excellent
- ✅ Mistral Nemo - Very good

### Good Tool Support
- ✅ Qwen 2.5 (7b+)
- ✅ Llama 3 (70b)
- ✅ Hermes 3

### Limited Tool Support
- ⚠️ Mixtral
- ⚠️ Older Llama 2 variants
- ⚠️ Phi models

## Server Configuration

### vLLM (gx10.local example)
Must start with tool calling flags:
```bash
vllm serve Qwen/Qwen3-VL-32B-Instruct-FP8 \
  --enable-auto-tool-choice \
  --tool-call-parser hermes
```

### Ollama
Just run normally - tool calling is built in:
```bash
ollama serve
```

### LM Studio
Tool calling usually enabled by default. Check model in UI.

## Quick Reference

| Endpoint | Default URL | Port | Model Example |
|----------|------------|------|---------------|
| LM Studio | localhost:1234/v1 | 1234 | `qwen2.5-7b` |
| Ollama | localhost:11434/v1 | 11434 | `llama3.1` |
| vLLM | localhost:8000/v1 | 8000 | `qwen-32b` |
| OpenRouter | api.openrouter.io/v1 | 443 | `gpt-4` |

## Troubleshooting

### Error: "auto tool choice requires --enable-auto-tool-choice"
**Solution:** Your vLLM server needs startup flags. See Server Configuration above.

### Error: "Connection refused"
**Solution:** Check that the LLM endpoint is running and accessible:
```bash
curl http://endpoint:port/v1/models
```

### All tests fail
**Solution:** 
1. Verify endpoint is reachable
2. Check model name is correct
3. Ensure model supports tool calling
4. Check for server logs/errors

## Integration with WhisperEngine

WhisperEngine uses the same tool format as these tests. Models passing all tests are production-ready.

For actual WhisperEngine integration, configure in `.env.{bot_name}`:
```env
LLM_PROVIDER=openrouter  # or local endpoint
LLM_MODEL_NAME=qwen3-32b
ENABLE_REFLECTIVE_MODE=true
```
