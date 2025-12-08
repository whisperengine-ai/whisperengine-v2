from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from loguru import logger

from src_v2.config.settings import settings


def create_llm(
    temperature: Optional[float] = None, 
    mode: str = "main", 
    model_name: Optional[str] = None,
    request_timeout: Optional[float] = None
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
    
    Args:
        temperature: The temperature to use for the model.
        mode: "main" for the character model, "router" for the cognitive router, 
              "reflective" for reflective mode, "utility" for structured tasks.
        model_name: Specific model name to use (overrides settings).
        request_timeout: Request timeout in seconds. Defaults to 180s for local models, 60s for cloud APIs.
    """
    # Determine which settings to use
    if mode == "reflective" and settings.REFLECTIVE_LLM_PROVIDER:
        # Use configured reflective LLM (if set)
        provider = settings.REFLECTIVE_LLM_PROVIDER
        api_key = settings.REFLECTIVE_LLM_API_KEY.get_secret_value() if settings.REFLECTIVE_LLM_API_KEY else "dummy"
        base_url = settings.REFLECTIVE_LLM_BASE_URL
        _model = settings.REFLECTIVE_LLM_MODEL_NAME or "anthropic/claude-3.5-sonnet"
    elif mode in ["router", "utility"] and settings.ROUTER_LLM_PROVIDER:
        # Use router LLM for routing AND utility tasks (summarization, classification, etc.)
        provider = settings.ROUTER_LLM_PROVIDER
        api_key = settings.ROUTER_LLM_API_KEY.get_secret_value() if settings.ROUTER_LLM_API_KEY else "dummy"
        base_url = settings.ROUTER_LLM_BASE_URL
        _model = settings.ROUTER_LLM_MODEL_NAME or "gpt-3.5-turbo" # Default fallback if provider is set but model isn't
    else:
        # Default to main settings
        provider = settings.LLM_PROVIDER
        api_key = settings.LLM_API_KEY.get_secret_value() if settings.LLM_API_KEY else "dummy"
        base_url = settings.LLM_BASE_URL
        _model = settings.LLM_MODEL_NAME
    
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

    logger.info(f"Initializing LLM ({mode}): {provider} ({_model}) Temp: {temp}")

    # Determine timeout: local models get longer timeout (they're slower)
    is_local = provider in ["lmstudio", "ollama"]
    timeout = request_timeout or (180 if is_local else 60)

    if provider == "openai":
        return ChatOpenAI(
            api_key=api_key,
            model=_model,
            temperature=temp,
            request_timeout=timeout
        )
    
    elif provider == "openrouter":
        # OpenRouter is OpenAI-compatible
        headers = {
            "X-Title": "WhisperEngine",
            "HTTP-Referer": "https://github.com/whisperengine-ai/whisperengine-v2"
        }
        
        return ChatOpenAI(
            api_key=api_key,
            base_url=base_url or "https://openrouter.ai/api/v1",
            model=_model,
            temperature=temp,
            default_headers=headers,
            request_timeout=timeout
        )
        
    elif provider == "lmstudio":
        # LM Studio is OpenAI-compatible with native tool support
        # Best models: Qwen2.5-Instruct, Llama 3.1/3.2-Instruct, Ministral-Instruct
        return ChatOpenAI(
            api_key="lm-studio",  # Required but ignored
            base_url=base_url or "http://localhost:1234/v1",
            model=_model,
            temperature=temp,
            request_timeout=timeout
        )
    
    elif provider == "ollama":
        # Ollama via OpenAI-compatible endpoint with native tool support
        # Uses /v1/chat/completions which supports the tools parameter
        # Best models: qwen2.5, llama3.1, llama3.2, llama3.3, mistral, mistral-nemo
        # See: https://ollama.com/blog/tool-support
        ollama_base = base_url or "http://localhost:11434"
        return ChatOpenAI(
            api_key="ollama",  # Required but ignored by Ollama
            base_url=f"{ollama_base}/v1",
            model=_model,
            temperature=temp,
            request_timeout=timeout
        )
    
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}. Supported: openai, openrouter, ollama, lmstudio")
