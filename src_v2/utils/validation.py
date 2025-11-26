"""
Input validation utilities for WhisperEngine v2.

These validators can be used across different entry points (Discord, API, etc.)
to ensure consistent validation behavior.
"""

from typing import Optional, Tuple, List
from loguru import logger


class ValidationError(Exception):
    """Custom exception for validation failures with user-friendly messages."""
    def __init__(self, message: str, user_message: str):
        self.message = message  # Technical message for logs
        self.user_message = user_message  # User-friendly message
        super().__init__(message)


class InputValidator:
    """Validates user inputs before processing."""
    
    # Discord limits
    DISCORD_INPUT_MAX_LENGTH = 2000
    DISCORD_OUTPUT_MAX_LENGTH = 2000  # Per message chunk
    
    # Engine limits (for non-Discord entry points)
    ENGINE_INPUT_MAX_LENGTH = 200000  # ~50k tokens
    ENGINE_INPUT_MAX_TOKENS = 50000  # Approximate
    
    @staticmethod
    def validate_message_content(
        message: str, 
        max_length: int = DISCORD_INPUT_MAX_LENGTH,
        context: str = "Discord"
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates message content for emptiness and length.
        
        Args:
            message: The message to validate
            max_length: Maximum allowed length
            context: Context string for error messages (e.g., "Discord", "API")
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check for empty/whitespace-only
        if not message or not message.strip():
            return False, "I didn't catch that. Could you say that again?"
        
        # Check length
        if len(message) > max_length:
            if context == "Discord":
                return False, f"That message is too long! Discord limits messages to {max_length} characters. Please break it into smaller parts."
            else:
                return False, "That's quite a lot to process at once. Could you break that down into smaller parts?"
        
        return True, None
    
    @staticmethod
    def validate_image_urls(urls: List[str]) -> Tuple[List[str], List[str]]:
        """
        Validates and filters image URLs.
        
        Args:
            urls: List of URLs to validate
            
        Returns:
            Tuple of (valid_urls, invalid_urls)
        """
        valid_urls = []
        invalid_urls = []
        
        for url in urls:
            if url.startswith(('http://', 'https://')):
                valid_urls.append(url)
            else:
                invalid_urls.append(url)
                logger.warning(f"Invalid image URL format: {url}")
        
        return valid_urls, invalid_urls
    
    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        Rough estimation of token count.
        Actual tokenization depends on the model, but this gives a ballpark.
        
        Args:
            text: Text to estimate tokens for
            
        Returns:
            Estimated token count
        """
        # Rough heuristic: ~4 characters per token on average
        return len(text) // 4
    
    @staticmethod
    def validate_for_discord(message: str, image_urls: Optional[List[str]] = None) -> None:
        """
        Validates input specifically for Discord entry point.
        Raises ValidationError if validation fails.
        
        Args:
            message: Message content
            image_urls: Optional list of image URLs
            
        Raises:
            ValidationError: If validation fails
        """
        # Validate message content
        is_valid, error_msg = InputValidator.validate_message_content(
            message, 
            InputValidator.DISCORD_INPUT_MAX_LENGTH,
            context="Discord"
        )
        if not is_valid:
            raise ValidationError(f"Discord message validation failed: {error_msg}", error_msg or "Invalid message")
        
        # Validate image URLs if present
        if image_urls:
            valid_urls, invalid_urls = InputValidator.validate_image_urls(image_urls)
            if invalid_urls and not valid_urls:
                raise ValidationError(
                    f"All image URLs invalid: {invalid_urls}",
                    "The image URLs you provided are not valid. Please use direct image links (starting with http:// or https://)."
                )
    
    @staticmethod
    def validate_for_engine(message: str, image_urls: Optional[List[str]] = None) -> None:
        """
        Validates input for the engine (defensive validation).
        Raises ValidationError if validation fails.
        
        Args:
            message: Message content
            image_urls: Optional list of image URLs
            
        Raises:
            ValidationError: If validation fails
        """
        # Validate message content (more lenient than Discord)
        is_valid, error_msg = InputValidator.validate_message_content(
            message, 
            InputValidator.ENGINE_INPUT_MAX_LENGTH,
            context="Engine"
        )
        if not is_valid:
            raise ValidationError(f"Engine message validation failed: {error_msg}", error_msg or "Invalid message")
        
        # Check token estimate
        estimated_tokens = InputValidator.estimate_tokens(message)
        if estimated_tokens > InputValidator.ENGINE_INPUT_MAX_TOKENS:
            error_msg = "That's quite a lot to process at once. Could you break that down into smaller parts?"
            raise ValidationError(
                f"Message too long: ~{estimated_tokens} tokens (max: {InputValidator.ENGINE_INPUT_MAX_TOKENS})",
                error_msg
            )
        
        # Validate image URLs if present
        if image_urls:
            valid_urls, invalid_urls = InputValidator.validate_image_urls(image_urls)
            if not valid_urls and invalid_urls:
                logger.warning(f"All image URLs invalid, proceeding without images: {invalid_urls}")


# Convenience instance
validator = InputValidator()
