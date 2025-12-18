"""
Content Cleaning Utilities

Functions for cleaning message content before embedding/extraction.
Removes context markers that would pollute semantic search or fact extraction.
"""
import re
from loguru import logger


def strip_context_markers(content: str) -> str:
    """
    Strip reply/forward context markers from message content.
    
    Messages are stored with context like:
    - [CONTEXT: User is replying to YOUR previous message...]
    - [Your original message was: "..."]
    - [Replying to SomeBot: "..."]
    - [Forwarded Message: "..."]
    - [User shared a link to an earlier message...]
    
    We need to strip these BEFORE embedding/fact extraction to avoid:
    1. Semantic pollution (searching "marine biologist" finds user who quoted Elena)
    2. Fact attribution errors (user IS_A marine biologist because they quoted bot)
    
    Returns only the user's actual words.
    """
    if not content:
        return content
    
    original_len = len(content)
    
    # Pattern 1: [CONTEXT: ...] blocks (bot reply context)
    # Remove everything from [CONTEXT: to the [User's response]: marker
    content = re.sub(
        r'\[CONTEXT:[^\]]*\]\s*\[Your original message was[^\]]*:\s*"[^"]*"\]\s*\[[^\]]*\'s response\]:\s*',
        '',
        content,
        flags=re.IGNORECASE | re.DOTALL
    )
    
    # Pattern 1b: Simpler CONTEXT block without the response marker
    content = re.sub(
        r'\[CONTEXT:[^\]]*\]\s*\[Your original message was[^\]]*:\s*"[^"]*"\]\s*',
        '',
        content,
        flags=re.IGNORECASE | re.DOTALL
    )
    
    # Pattern 2: [Replying to Author: "..."] - reply to other users/bots
    content = re.sub(
        r'\[Replying to [^\]]+:\s*"[^"]*"\]\s*',
        '',
        content,
        flags=re.IGNORECASE
    )
    
    # Pattern 3: [Replying to Author's image...] - reply to images
    content = re.sub(
        r'\[Replying to [^\]]+\'s image[^\]]*\]\s*',
        '',
        content,
        flags=re.IGNORECASE
    )
    
    # Pattern 4: [Forwarded Message: "..."] - forwarded content
    content = re.sub(
        r'\[Forwarded Message:\s*"[^"]*"\]\s*',
        '',
        content,
        flags=re.IGNORECASE
    )
    
    # Pattern 5: [Forwarded Sticker(s): ...] - forwarded stickers
    content = re.sub(
        r'\[Forwarded Sticker\(s\):[^\]]*\]\s*',
        '',
        content,
        flags=re.IGNORECASE
    )
    
    # Pattern 6: [Sent Sticker(s): ...] - sticker references
    content = re.sub(
        r'\[Sent Sticker\(s\):[^\]]*\]\s*',
        '',
        content,
        flags=re.IGNORECASE
    )
    
    # Pattern 7: [User shared a link to an earlier message from Author: "..."]
    content = re.sub(
        r'\[User shared a link to an earlier message from [^\]]+:\s*"[^"]*"\]\s*',
        '',
        content,
        flags=re.IGNORECASE
    )
    
    # Pattern 8: [User shared a link to a message from #channel by Author: "..."]
    content = re.sub(
        r'\[User shared a link to a message from #[^\]]+:\s*"[^"]*"\]\s*',
        '',
        content,
        flags=re.IGNORECASE
    )
    
    # Pattern 9: [Attached File Content]: ... (document attachments)
    # Keep the user's message but remove the attached file content for embedding
    content = re.sub(
        r'\n\n\[Attached File Content\]:.*$',
        '',
        content,
        flags=re.IGNORECASE | re.DOTALL
    )
    
    # Clean up any leftover whitespace
    content = content.strip()
    
    if len(content) < original_len:
        logger.debug(f"Stripped context markers: {original_len} -> {len(content)} chars")
    
    return content
