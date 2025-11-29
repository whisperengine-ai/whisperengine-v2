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

async def extract_pending_images(text: str, user_id: str) -> Tuple[str, List[discord.File]]:
    """
    Retrieve any pending images for the user from Redis.
    Also strips out any BFL URLs that the LLM might have included.
    
    Args:
        text: The response text
        user_id: The user ID to check for pending images
        
    Returns:
        Tuple of (cleaned_text, list_of_discord_files)
    """
    files: List[discord.File] = []
    
    # Retrieve all pending images for this user from Redis
    results = await pending_images.pop_all(user_id)
    
    for result in results:
        files.append(result.to_discord_file())
        logger.info(f"Retrieved pending image for user {user_id} for Discord upload")
    
    # Strip out any BFL URLs that the LLM might have included
    cleaned_text = BFL_IMAGE_URL_PATTERN.sub("", text)
    
    # Clean up any double spaces or newlines left behind
    cleaned_text = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned_text)
    
    return cleaned_text.strip(), files

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
