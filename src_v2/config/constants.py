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
    "openrouter": "base64", # OpenRouter: Discord CDN links often 403 when fetched by remote servers. Use base64.
    "google": "url",        # Google (Gemini) supports direct URLs
    "ollama": "base64",     # Ollama requires base64 encoding
    "lmstudio": "base64",   # LM Studio requires base64 encoding
}

def get_image_format_for_provider(provider: str) -> ImageFormat:
    """
    Returns the required image format for the given provider.
    
    Args:
        provider: LLM provider name (e.g., "openai", "ollama")
        
    Returns:
        "url" or "base64" depending on provider requirements
    """
    return IMAGE_HANDLING_BY_PROVIDER.get(provider.lower(), "url")  # Default to URL
