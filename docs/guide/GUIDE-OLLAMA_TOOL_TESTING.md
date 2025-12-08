# Ollama Tool Calling Compatibility Testing

**Version:** 1.0  
**Last Updated:** December 8, 2025  
**Origin:** Created to validate local LLM models for WhisperEngine tool calling compatibility

## Overview

WhisperEngine uses LangChain's `bind_tools()` pattern for agent workflows. Not all local LLMs support tool calling properly—some truncate tool names, others fail to follow the OpenAI-compatible format. This script tests any model running in Ollama against WhisperEngine's exact requirements.

## Prerequisites

1. **Ollama** running (`ollama serve`)
2. **Python environment** with dependencies:
   ```bash
   source .venv/bin/activate
   ```
3. **Ollama server** running (default: `http://localhost:11434/v1`)
4. **Models pulled** (e.g., `ollama pull llama3.1`)

## Quick Start

```bash
# Activate environment
source .venv/bin/activate

# Test currently loaded model (or default to first available)
python scripts/test_ollama_tools.py

# List all available models
python scripts/test_ollama_tools.py --list-models

# Test all models at endpoint
python scripts/test_ollama_tools.py --all-models
```

## Command Options

| Option | Description |
|--------|-------------|
| `--endpoint URL` | Ollama endpoint (default: `http://localhost:11434/v1`). Alias: `--base-url` |
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
python scripts/test_ollama_tools.py
```

### Full Test Suite on Single Model
```bash
python scripts/test_ollama_tools.py --all
```

### Test Specific Model
```bash
python scripts/test_ollama_tools.py --model llama3.1 --all
```

### Test All Available Models
```bash
python scripts/test_ollama_tools.py --all-models
```

### Custom Endpoint
```bash
python scripts/test_ollama_tools.py --endpoint http://192.168.1.100:11434/v1
```

### Stress Test (Realistic Context Load)
```bash
# Default 4k tokens of context
python scripts/test_ollama_tools.py --stress

# Custom context size (8k tokens)
python scripts/test_ollama_tools.py --stress --stress-tokens 8000
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
5. **Agent Loop** - Full cycle: Invoke → Tool Call → Tool Result → Final Response

### Advanced Tests
- **Parallel Tool Calling** - Can the model call multiple tools at once? (e.g., "Search memories AND get facts")
- **Stress Test** - Can the model maintain tool calling accuracy with 4k+ tokens of context?

## Recommended Models

Based on testing, these models generally work best with WhisperEngine's tool calling format:

| Model | Size | Tool Support | Notes |
|-------|------|--------------|-------|
| **Llama 3.1** | 8b, 70b | ⭐ Excellent | Native tool calling support, very reliable |
| **Qwen 2.5** | 7b, 14b, 32b | ⭐ Excellent | Best-in-class tool following, handles complex args well |
| **Mistral Nemo** | 12b | ✅ Good | Reliable, good balance of speed/quality |
| **Hermes 3** | 8b, 70b | ✅ Good | Strong instruction following |

## Troubleshooting

**"No models found"**
- Ensure Ollama is running: `ollama serve`
- Ensure you've pulled a model: `ollama pull llama3.1`

**"Connection refused"**
- Check if Ollama is running on port 11434
- If running in Docker, ensure ports are mapped

**"LangChain not installed"**
- Install dependencies: `pip install langchain-openai`

**"Model returns raw text instead of tool calls"**
- The model likely doesn't support tool calling natively. Try a different model (Llama 3.1 or Qwen 2.5).
