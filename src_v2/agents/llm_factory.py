from typing import Optional, Any
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from loguru import logger

from src_v2.config.settings import settings


def _build_reasoning_config(
    enabled: bool,
    effort: Optional[str],
    max_tokens: Optional[int],
    exclude: bool
) -> Optional[dict[str, Any]]:
    """
    Build reasoning configuration for OpenAI/Anthropic-compatible APIs.
    
    Returns a dict to be passed as extra_body or model_kwargs, or None if reasoning is disabled.
    
    Supports:
    - OpenAI o1/o3 models: Uses "reasoning" with "effort" field
    - Anthropic Claude: Uses "reasoning" with "max_tokens" (budget_tokens)
    - OpenRouter: Passes through to underlying provider
    
    Format matches the API spec:
    {
        "reasoning": {
            "effort": "high",  # or "max_tokens": 2000
            "exclude": false
        }
    }
    """
    if not enabled:
        return None
    
    reasoning: dict[str, Any] = {}
    
    # effort takes precedence (OpenAI-style)
    if effort and effort != "none":
        reasoning["effort"] = effort
    elif max_tokens:
        # Anthropic-style token budget
        reasoning["max_tokens"] = max_tokens
    else:
        # Enabled but no specific config - use default (let API decide)
        reasoning["enabled"] = True
    
    if exclude:
        reasoning["exclude"] = True
    
    return {"reasoning": reasoning} if reasoning else None


def create_llm(
    temperature: Optional[float] = None, 
    mode: str = "main", 
    model_name: Optional[str] = None,
    request_timeout: Optional[float] = None,
    max_tokens: Optional[int] = None,
    reasoning_enabled: Optional[bool] = None,
    reasoning_effort: Optional[str] = None,
    reasoning_max_tokens: Optional[int] = None,
    reasoning_exclude: Optional[bool] = None
) -> BaseChatModel:
    """
    Creates a LangChain Chat Model based on the configuration.
    Supports: openai, openrouter, ollama, lmstudio
    
    All providers support tool/function calling via OpenAI-compatible endpoints.
    
    LOCAL PROVIDERS:
    
    LM Studio (provider="lmstudio"):
      - Native tool support: Qwen2.5-Instruct, Llama 3.1/3.2-Instruct, Ministral-Instruct
      - Default tool support: Other models (uses custom prompt format)
      - See: https://lmstudio.ai/docs/advanced/tool-use
    
    Ollama (provider="ollama"):
      - Uses OpenAI-compatible endpoint (/v1/chat/completions) for tool support
      - Models: qwen2.5, qwen3, llama3.1, llama3.2, llama3.3, mistral, mistral-nemo,
                deepseek-r1, command-r, hermes3, firefunction-v2
      - See: https://ollama.com/blog/tool-support
    
    REASONING MODE:
    
    For models that support extended thinking/reasoning (OpenAI o1/o3, Claude):
      - Set LLM_REASONING_ENABLED=true in .env
      - Use LLM_REASONING_EFFORT for OpenAI-style (xhigh, high, medium, low, minimal, none)
      - Use LLM_REASONING_MAX_TOKENS for Anthropic-style token budget
      - Set LLM_REASONING_EXCLUDE=true to hide chain-of-thought from response
    
    Args:
        temperature: The temperature to use for the model.
        mode: "main" for the character model, "router" for the cognitive router, 
              "reflective" for reflective mode, "utility" for structured tasks.
        model_name: Specific model name to use (overrides settings).
        request_timeout: Request timeout in seconds. Defaults to 180s for local models, 60s for cloud APIs.
        max_tokens: Maximum tokens to generate. Use this to prevent runaway generation in local models.
                    Recommended: 512 for Cypher/SQL generation, 1024 for summaries, None for conversations.
        reasoning_enabled: Override settings.LLM_REASONING_ENABLED for this call.
        reasoning_effort: Override settings.LLM_REASONING_EFFORT for this call.
        reasoning_max_tokens: Override settings.LLM_REASONING_MAX_TOKENS for this call.
        reasoning_exclude: Override settings.LLM_REASONING_EXCLUDE for this call.
    """
    # Determine which settings to use (including reasoning config per mode)
    if mode == "reflective" and settings.REFLECTIVE_LLM_PROVIDER:
        # Use configured reflective LLM (if set)
        provider = settings.REFLECTIVE_LLM_PROVIDER
        api_key = settings.REFLECTIVE_LLM_API_KEY.get_secret_value() if settings.REFLECTIVE_LLM_API_KEY else "dummy"
        base_url = settings.REFLECTIVE_LLM_BASE_URL
        _model = settings.REFLECTIVE_LLM_MODEL_NAME or "anthropic/claude-3.5-sonnet"
        # Use reflective-specific reasoning settings if not overridden
        _reasoning_enabled = reasoning_enabled if reasoning_enabled is not None else settings.REFLECTIVE_REASONING_ENABLED
        _reasoning_effort = reasoning_effort or settings.REFLECTIVE_REASONING_EFFORT
        _reasoning_max_tokens = reasoning_max_tokens or settings.REFLECTIVE_REASONING_MAX_TOKENS
        _reasoning_exclude = reasoning_exclude if reasoning_exclude is not None else settings.REFLECTIVE_REASONING_EXCLUDE
    elif mode in ["router", "utility"] and settings.ROUTER_LLM_PROVIDER:
        # Use router LLM for routing AND utility tasks (summarization, classification, etc.)
        # Router/utility skip reasoning mode - they need fast, cheap responses for tool selection
        # and structured tasks. Reasoning would add latency and cost without benefit.
        provider = settings.ROUTER_LLM_PROVIDER
        api_key = settings.ROUTER_LLM_API_KEY.get_secret_value() if settings.ROUTER_LLM_API_KEY else "dummy"
        base_url = settings.ROUTER_LLM_BASE_URL
        _model = settings.ROUTER_LLM_MODEL_NAME or "gpt-3.5-turbo" # Default fallback if provider is set but model isn't
        _reasoning_enabled = reasoning_enabled if reasoning_enabled is not None else False
        _reasoning_effort = reasoning_effort
        _reasoning_max_tokens = reasoning_max_tokens
        _reasoning_exclude = reasoning_exclude if reasoning_exclude is not None else False
    else:
        # Default to main settings
        provider = settings.LLM_PROVIDER
        api_key = settings.LLM_API_KEY.get_secret_value() if settings.LLM_API_KEY else "dummy"
        base_url = settings.LLM_BASE_URL
        _model = settings.LLM_MODEL_NAME
        # Use main LLM reasoning settings if not overridden
        _reasoning_enabled = reasoning_enabled if reasoning_enabled is not None else settings.LLM_REASONING_ENABLED
        _reasoning_effort = reasoning_effort or settings.LLM_REASONING_EFFORT
        _reasoning_max_tokens = reasoning_max_tokens or settings.LLM_REASONING_MAX_TOKENS
        _reasoning_exclude = reasoning_exclude if reasoning_exclude is not None else settings.LLM_REASONING_EXCLUDE
    
    # Override model if provided
    if model_name:
        _model = model_name
    
    # Use provided temperature, or settings default for main mode, or 0.7 fallback
    if temperature is not None:
        temp = temperature
    elif mode == "main":
        temp = settings.LLM_TEMPERATURE
    else:
        temp = 0.7
    
    # Build reasoning config for extra_body
    reasoning_config = _build_reasoning_config(
        enabled=_reasoning_enabled,
        effort=_reasoning_effort,
        max_tokens=_reasoning_max_tokens,
        exclude=_reasoning_exclude
    )

    logger.info(f"Initializing LLM ({mode}): {provider} ({_model}) Temp: {temp}" + 
                (f" Reasoning: {reasoning_config}" if reasoning_config else ""))

    # Determine timeout: local models get longer timeout (they're slower)
    is_local = provider in ["lmstudio", "ollama"]
    timeout = request_timeout or (180 if is_local else 60)

    if provider == "openai":
        kwargs: dict[str, Any] = {
            "api_key": api_key,
            "model": _model,
            "temperature": temp,
            "request_timeout": timeout
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        if reasoning_config:
            kwargs["model_kwargs"] = reasoning_config
        return ChatOpenAI(**kwargs)
    
    elif provider == "openrouter":
        # OpenRouter is OpenAI-compatible
        headers = {
            "X-Title": "WhisperEngine",
            "HTTP-Referer": "https://github.com/whisperengine-ai/whisperengine-v2"
        }
        
        kwargs = {
            "api_key": api_key,
            "base_url": base_url or "https://openrouter.ai/api/v1",
            "model": _model,
            "temperature": temp,
            "default_headers": headers,
            "request_timeout": timeout
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        if reasoning_config:
            kwargs["model_kwargs"] = reasoning_config
        return ChatOpenAI(**kwargs)
        
    elif provider == "lmstudio":
        # LM Studio is OpenAI-compatible with native tool support
        # Best models: Qwen2.5-Instruct, Llama 3.1/3.2-Instruct, Ministral-Instruct
        kwargs = {
            "api_key": "lm-studio",  # Required but ignored
            "base_url": base_url or "http://localhost:1234/v1",
            "model": _model,
            "temperature": temp,
            "request_timeout": timeout
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        # Note: Local models typically don't support reasoning mode
        return ChatOpenAI(**kwargs)
    
    elif provider == "ollama":
        # Ollama via OpenAI-compatible endpoint with native tool support
        # Uses /v1/chat/completions which supports the tools parameter
        # Best models: qwen2.5, llama3.1, llama3.2, llama3.3, mistral, mistral-nemo
        # See: https://ollama.com/blog/tool-support
        ollama_base = base_url or "http://localhost:11434"
        kwargs = {
            "api_key": "ollama",  # Required but ignored by Ollama
            "base_url": f"{ollama_base}/v1",
            "model": _model,
            "temperature": temp,
            "request_timeout": timeout
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        return ChatOpenAI(**kwargs)
    
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}. Supported: openai, openrouter, ollama, lmstudio")
