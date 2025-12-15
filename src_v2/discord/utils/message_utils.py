import discord
import re
import os
from typing import List, Tuple, Optional
from loguru import logger
from src_v2.image_gen.service import pending_images

# Regex pattern for BFL image URLs (to strip them out if LLM includes them)
BFL_IMAGE_URL_PATTERN = re.compile(
    r'https://bfldelivery\S+\.blob\.core\.windows\.net/results/\S+\.(jpeg|jpg|png)'
)

from src_v2.artifacts.discord_utils import extract_pending_artifacts

async def extract_pending_images(text: str, user_id: str) -> Tuple[str, List[discord.File]]:
    """
    Extracts pending images (and other artifacts) for a user and returns cleaned text + files.
    
    NOTE: This function name is kept for backward compatibility, but it now retrieves
    ALL pending artifacts (images, audio, documents) from the unified registry.
    """
    # Get all pending artifacts (images, audio, etc.)
    files = await extract_pending_artifacts(user_id)
    
    # Return original text (no cleaning needed as we don't embed markers anymore) and files
    return text, files

def chunk_message(text: str, max_length: int = 2000) -> List[str]:
    """
    Splits a long message into chunks that fit Discord's character limit.
    Tries to split on sentence boundaries when possible.
    
    Args:
        text: The text to split into chunks
        max_length: Maximum length per chunk (Discord limit is 2000)
        
    Returns:
        List of text chunks (never empty - returns placeholder if input is empty)
    """
    # Guard against empty text to prevent Discord API errors
    if not text or not text.strip():
        return ["..."]
    
    if len(text) <= max_length:
        return [text]
    
    chunks: List[str] = []
    current_chunk: str = ""
    
    # Split by sentences (basic approach)
    sentences = text.replace("\n\n", "\n\n<BREAK>").replace(". ", ".<BREAK>").split("<BREAK>")
    
    for sentence in sentences:
        # If adding this sentence would exceed the limit
        if len(current_chunk) + len(sentence) > max_length:
            # If current chunk has content, save it
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
            
            # If the sentence itself is too long, force split by words
            if len(sentence) > max_length:
                words = sentence.split()
                for word in words:
                    if len(current_chunk) + len(word) + 1 > max_length:
                        chunks.append(current_chunk.strip())
                        current_chunk = word + " "
                    else:
                        current_chunk += word + " "
            else:
                current_chunk = sentence
        else:
            current_chunk += sentence
    
    # Add the last chunk
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

def is_image(attachment: discord.Attachment) -> bool:
    """
    Determines if an attachment is an image based on content_type or filename extension.
    
    Args:
        attachment: Discord attachment object
        
    Returns:
        True if the attachment is an image, False otherwise
    """
    # 1. Check Content-Type (Reliable if present)
    if attachment.content_type and attachment.content_type.startswith("image/"):
        return True
        
    # 2. Fallback: Check Extension
    valid_extensions: set[str] = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.tiff'}
    _, ext = os.path.splitext(attachment.filename)
    if ext.lower() in valid_extensions:
        return True
        
    return False

async def send_chunked_message(
    channel: discord.abc.Messageable,
    content: str,
    reference: Optional[discord.MessageReference] = None,
    mention_author: bool = False,
    files: Optional[List[discord.File]] = None
) -> List[discord.Message]:
    """
    Sends a message to a channel, chunking it if necessary.
    Handles replies and file attachments (attached to first chunk).
    
    Args:
        channel: The channel to send to
        content: The message content
        reference: Optional message reference for reply
        mention_author: Whether to mention the author in reply
        files: Optional list of files to attach
        
    Returns:
        List of sent discord.Message objects
    """
    chunks = chunk_message(content)
    sent_messages = []
    
    for i, chunk in enumerate(chunks):
        kwargs = {"content": chunk}
        
        # Only attach files to the first chunk
        if i == 0 and files:
            kwargs["files"] = files
            
        # Only reply/mention on the first chunk
        if i == 0 and reference:
            kwargs["reference"] = reference
            kwargs["mention_author"] = mention_author
            
        sent_msg = await channel.send(**kwargs)
        sent_messages.append(sent_msg)
        
    return sent_messages
