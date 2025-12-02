"""Constants for WhisperEngine v2."""

from typing import Dict, Literal

# Type aliases for better clarity
ImageFormat = Literal["url", "base64"]
TraitName = Literal["Vulnerable", "Sarcastic", "Affectionate", "Professional", "Curious", "Playful", "Philosophical", "Direct"]

# Define Trait Behaviors
TRAIT_BEHAVIORS: Dict[str, str] = {
    "Vulnerable": "You are willing to share your own fears, insecurities, and past failures. Be open about your limitations.",
    "Sarcastic": "Use dry humor, irony, and wit. Don't be afraid to playfully tease the user.",
    "Affectionate": "Express warmth and care. Use terms of endearment if appropriate. Show you value the relationship.",
    "Professional": "Maintain a polite, objective, and efficient tone. Focus on the task at hand.",
    "Curious": "Ask follow-up questions. Show genuine interest in the user's life and opinions.",
    "Playful": "Be lighthearted, make jokes, and use emojis. Don't take things too seriously.",
    "Philosophical": "Discuss abstract concepts, meaning of life, and ethics. Use metaphors.",
    "Direct": "Be blunt and to the point. Avoid sugarcoating."
}

# Image Handling Configuration by Provider
# Determines whether a provider accepts direct URLs or requires base64 encoding
IMAGE_HANDLING_BY_PROVIDER: Dict[str, ImageFormat] = {
    "openai": "url",        # OpenAI (GPT-4o, GPT-4 Vision) supports direct URLs
    "anthropic": "base64",  # Anthropic via API often has issues with Discord CDN links (403), safer to use base64
    "openrouter": "url",    # OpenRouter supports URLs, but we force base64 for Discord CDN via url_requires_base64 check
    "google": "url",        # Google (Gemini) supports direct URLs
    "ollama": "base64",     # Ollama requires base64 encoding
    "lmstudio": "base64",   # LM Studio requires base64 encoding
}

# URLs that always require base64 encoding because they have auth tokens
# that external LLM providers cannot access
URLS_REQUIRING_BASE64 = [
    "cdn.discordapp.com",
    "media.discordapp.net",
]

def url_requires_base64(url: str) -> bool:
    """
    Check if a URL requires base64 encoding regardless of provider.
    Discord CDN URLs have auth tokens that external services can't access.
    
    Args:
        url: The image URL to check
        
    Returns:
        True if the URL should always be base64 encoded
    """
    return any(domain in url for domain in URLS_REQUIRING_BASE64)

def get_image_format_for_provider(provider: str) -> ImageFormat:
    """
    Returns the required image format for the given provider.
    
    Args:
        provider: LLM provider name (e.g., "openai", "ollama")
        
    Returns:
        "url" or "base64" depending on provider requirements
    """
    return IMAGE_HANDLING_BY_PROVIDER.get(provider.lower(), "url")  # Default to URL

def should_use_base64(url: str, provider: str) -> bool:
    """
    Determine if base64 encoding should be used for an image URL.
    
    Returns True if:
    1. The URL is from a source that requires base64 (e.g., Discord CDN), OR
    2. The provider requires base64 encoding
    
    Args:
        url: The image URL
        provider: The LLM provider name
        
    Returns:
        True if base64 encoding should be used
    """
    return url_requires_base64(url) or get_image_format_for_provider(provider) == "base64"
