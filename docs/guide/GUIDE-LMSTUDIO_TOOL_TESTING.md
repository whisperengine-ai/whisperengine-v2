# LM Studio Tool Calling Compatibility Testing

**Version:** 1.0  
**Last Updated:** December 8, 2025  
**Origin:** Created to validate local LLM models for WhisperEngine tool calling compatibility

## Overview

WhisperEngine uses LangChain's `bind_tools()` pattern for agent workflows. Not all local LLMs support tool calling properly—some truncate tool names, others fail to follow the OpenAI-compatible format. This script tests any model running in LM Studio against WhisperEngine's exact requirements.

## Prerequisites

1. **LM Studio** running with at least one model loaded
2. **Python environment** with dependencies:
   ```bash
   source .venv/bin/activate
   ```
3. **LM Studio server** running (default: `http://localhost:1234/v1`)

## Quick Start

```bash
# Activate environment
source .venv/bin/activate

# Test currently loaded model
python scripts/test_lmstudio_tools.py

# List all available models
python scripts/test_lmstudio_tools.py --list-models

# Test all models at endpoint
python scripts/test_lmstudio_tools.py --all-models
```

## Command Options

| Option | Description |
|--------|-------------|
| `--endpoint URL` | LM Studio endpoint (default: `http://localhost:1234/v1`). Alias: `--base-url` |
| `--model NAME` | Specific model to test (default: auto-detect loaded model) |
| `--list-models` | Just list available models, don't run tests |
| `--all-models` | Test ALL models at the endpoint |
| `--all` | Run all test types (OpenAI + LangChain + parallel + stress) |
| `--langchain` | Include LangChain bind_tools() tests |
| `--parallel` | Include parallel tool calling test |
| `--stress` | Run stress test with large context (~4k tokens) |
| `--stress-tokens N` | Custom token count for stress test (default: 4000) |
| `--json` | Output results as JSON |

## Usage Examples

### Basic Test (OpenAI API format)
```bash
python scripts/test_lmstudio_tools.py
```

### Full Test Suite on Single Model
```bash
python scripts/test_lmstudio_tools.py --all
```

### Test Specific Model
```bash
python scripts/test_lmstudio_tools.py --model qwen2.5-7b-instruct --all
```

### Test All Available Models
```bash
python scripts/test_lmstudio_tools.py --all-models
```

### Custom Endpoint
```bash
python scripts/test_lmstudio_tools.py --endpoint http://192.168.1.100:1234/v1
```

### Stress Test (Realistic Context Load)
```bash
# Default 4k tokens of context
python scripts/test_lmstudio_tools.py --stress

# Custom context size (8k tokens)
python scripts/test_lmstudio_tools.py --stress --stress-tokens 8000
```

## What Gets Tested

### OpenAI API Tests (5 cases)
1. **Memory Recall** - Can the model call `search_memories` for past conversations?
2. **Fact Lookup** - Can it call `get_user_facts` to retrieve user info?
3. **Image Generation** - Can it call `generate_image` with proper args?
4. **No Tool Needed** - Does it correctly skip tools for simple greetings?
5. **Complex Query** - Can it handle multi-step queries requiring tool selection?

### LangChain Tests (4 cases + agent loop)
1. **Memory Search** - `bind_tools()` with memory tool
2. **Fact Retrieval** - `bind_tools()` with fact lookup tool
3. **Image Generation** - `bind_tools()` with image tool
4. **No Tool Needed** - Correct behavior without tool calls
5. **Agent Loop Pattern** - Full invoke → tool_call → tool_result → final response cycle

### Parallel Tool Calling (optional)
Tests if the model can request multiple tools in a single response.

### Stress Test (optional)
Simulates real WhisperEngine conditions by injecting ~4k tokens of context (memories, facts, chat history) before the tool call. Many models pass basic tests but fail under realistic load. Tests:
1. **Memory Search** - Tool calling with full context
2. **Fact Lookup** - Tool selection accuracy under load
3. **No Tool Needed** - Avoiding false positives with large context

## Example Output

### Listing Models
```
$ python scripts/test_lmstudio_tools.py --list-models

Available models at http://localhost:1234/v1:
  • qwen2.5-7b-instruct
  • meta-llama-3.1-8b-instruct
  • ministral-8b-instruct-2410
  • text-embedding-nomic-embed-text-v1.5
```

### Single Model Test
```
$ python scripts/test_lmstudio_tools.py --all

======================================================================
🧪 LM STUDIO TOOL CALLING COMPATIBILITY TEST
======================================================================

📡 Endpoint: http://localhost:1234/v1
🤖 Model: qwen2.5-7b-instruct

──────────────────────────────────────────────────────────────────────
Running tests...

  Testing: Memory Recall... ✅ PASS
  Testing: Fact Lookup... ✅ PASS
  Testing: Image Generation... ✅ PASS
  Testing: No Tool Needed... ✅ PASS
  Testing: Complex Query (Multiple Potential Tools)... ✅ PASS

──────────────────────────────────────────────────────────────────────
📊 RESULTS SUMMARY
──────────────────────────────────────────────────────────────────────

  ✅ Passed:  5/5
  ⚠️ Partial: 0/5
  ❌ Failed:  0/5

======================================================================
🎉 VERDICT: FULLY COMPATIBLE
   This model works great with WhisperEngine tool calling!
======================================================================

======================================================================
🔗 LANGCHAIN bind_tools() COMPATIBILITY TEST
======================================================================

──────────────────────────────────────────────────────────────────────
Running LangChain tool binding tests...

  Testing: Memory Search (bind_tools)... ✅ PASS
  Testing: Fact Retrieval (bind_tools)... ✅ PASS
  Testing: Image Generation (bind_tools)... ✅ PASS
  Testing: No Tool Needed (bind_tools)... ✅ PASS (responded without tools)

──────────────────────────────────────────────────────────────────────
🔄 Testing Agent Loop Pattern (invoke → tool_call → tool_result → final)
──────────────────────────────────────────────────────────────────────
  Step 1: Tool requested ✅
          → mem_search({"query": "talked about yesterday"...})
  Step 2: Tool executed ✅
          → Result: Found 3 memories from yesterday...
  Step 3: Final response ✅
          → "From yesterday, we discussed the weather..."

======================================================================
🎉 LANGCHAIN VERDICT: FULLY COMPATIBLE
   This model works with WhisperEngine's LangChain agent workflows!
======================================================================
```

### All Models Summary
```
$ python scripts/test_lmstudio_tools.py --all-models

======================================================================
📊 ALL MODELS SUMMARY
======================================================================

Model                                    OpenAI API      LangChain       Status    
────────────────────────────────────────────────────────────────────────────────
qwen2.5-7b-instruct                      5/5             4/4             ✅ PASS    
meta-llama-3.1-8b-instruct               4/5             3/4             ✅ PASS    
ministral-8b-instruct-2410               5/5             4/4             ✅ PASS    
text-embedding-nomic-embed-text-v1.5     0/5             0/4             ❌ FAIL    

────────────────────────────────────────────────────────────────────────────────

✅ Fully Compatible: 3
   • qwen2.5-7b-instruct
   • meta-llama-3.1-8b-instruct
   • ministral-8b-instruct-2410

❌ Not Compatible: 1
   • text-embedding-nomic-embed-text-v1.5
```

## Interpreting Results

### Verdicts

| Verdict | Meaning |
|---------|---------|
| 🎉 FULLY COMPATIBLE | All tests pass. Model is ready for WhisperEngine. |
| ⚡ MOSTLY COMPATIBLE | Minor issues (e.g., unnecessary tool calls). Usually works fine. |
| ❌ NOT COMPATIBLE | Critical failures. Do not use with WhisperEngine. |

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Tool name truncated | Model cuts names >15 chars | WhisperEngine tools already use short names |
| Tool called when not needed | Model over-eager | Usually harmless, may increase latency |
| No tool_calls in response | Model doesn't support function calling | Use a different model |
| Agent loop fails | Model can't process tool results | Try larger model or different family |

## Recommended Models

Based on testing, these models work well with WhisperEngine:

| Model Family | Sizes Tested | Tool Calling | Notes |
|--------------|--------------|--------------|-------|
| **Qwen2.5-Instruct** | 7B, 14B, 32B | ✅ Excellent | Best overall, native function calling |
| **Llama 3.1/3.2/3.3-Instruct** | 8B, 70B | ✅ Good | Occasional over-calling |
| **Ministral-Instruct** | 8B | ✅ Excellent | Mistral's small model, great tool support |
| **Mistral Nemo** | 12B | ✅ Good | Solid performer |
| **Hermes 3** | Various | ✅ Good | Fine-tuned for function calling |

### Models to Avoid

- **Embedding models** (e.g., nomic-embed) - Not LLMs
- **Base models** (non-instruct) - No instruction following
- **Very small models** (<3B) - Unreliable tool selection

## Troubleshooting

### "Connection refused"
LM Studio server isn't running. Start it and load a model.

### "Model is not llm"
You're testing an embedding model. Skip it or use `--model` to specify an LLM.

### All tests fail with parse errors
Model doesn't support OpenAI-compatible tool calling format. Try a different model.

### LangChain tests fail but OpenAI tests pass
Model may have issues with the specific message format LangChain uses. Check for:
- Tool result message formatting
- Multi-turn conversation handling

## Integration with WhisperEngine

Once a model passes testing, you can use it in WhisperEngine by setting:

```bash
# In .env.{botname}
OPENROUTER_MODEL=openai/local-model  # Or your provider format
LLM_BASE_URL=http://localhost:1234/v1
```

Or for router/reflective models:
```bash
ROUTER_MODEL=local/qwen2.5-7b-instruct
ROUTER_BASE_URL=http://localhost:1234/v1
```

## See Also

- `docs/ref/REF-XXX-LOCAL_LLM_SETUP.md` - Full local LLM configuration guide
- `src_v2/agents/llm_factory.py` - LLM initialization code
- `src_v2/tools/` - All WhisperEngine tools (already using short names)
