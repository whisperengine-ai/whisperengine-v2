"""
Image Processing Utilities

Handles image preprocessing for LLM vision APIs, including:
- Animated GIF frame extraction
- Format conversion
- Base64 encoding
"""
import base64
import io
from typing import Tuple, Optional
from loguru import logger

try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    logger.warning("Pillow not available - animated GIF processing disabled")


def is_animated_gif(image_bytes: bytes) -> bool:
    """
    Check if image bytes represent an animated GIF.
    
    Args:
        image_bytes: Raw image data
        
    Returns:
        True if this is an animated GIF with multiple frames
    """
    if not PILLOW_AVAILABLE:
        return False
    
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            # Check if it's a GIF and has multiple frames
            if img.format == 'GIF':
                try:
                    img.seek(1)  # Try to seek to second frame
                    return True
                except EOFError:
                    # Only one frame - not animated
                    return False
    except Exception as e:
        logger.debug(f"Could not check if GIF is animated: {e}")
    
    return False


def extract_gif_frame(image_bytes: bytes, output_format: str = "PNG", frame_position: str = "middle") -> Tuple[bytes, str]:
    """
    Extract a representative frame from an animated GIF and convert to a static format.
    
    Args:
        image_bytes: Raw GIF image data
        output_format: Target format (PNG recommended for quality)
        frame_position: Which frame to extract - "first", "middle", or "quarter" (25% in)
        
    Returns:
        Tuple of (processed_bytes, mime_type)
        
    Raises:
        ValueError: If Pillow is not available or processing fails
    """
    if not PILLOW_AVAILABLE:
        raise ValueError("Pillow is required for GIF processing")
    
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            # Count total frames
            frame_count = 0
            try:
                while True:
                    frame_count += 1
                    img.seek(frame_count)
            except EOFError:
                pass  # Reached end of frames
            
            # Determine which frame to extract
            if frame_position == "first" or frame_count <= 2:
                target_frame = 0
            elif frame_position == "quarter":
                # 25% into the animation - good for fade-ins
                target_frame = max(1, frame_count // 4)
            else:  # "middle"
                target_frame = frame_count // 2
            
            # Seek to target frame
            img.seek(target_frame)
            logger.debug(f"Extracting frame {target_frame + 1}/{frame_count} from animated GIF")
            
            # Convert to RGB if needed (GIFs can have transparency/palette issues)
            frame = img.copy()  # Copy the frame to avoid issues with seek
            if frame.mode in ('RGBA', 'LA', 'P'):
                # Create white background for transparent images
                background = Image.new('RGB', frame.size, (255, 255, 255))
                if frame.mode == 'P':
                    frame = frame.convert('RGBA')
                background.paste(frame, mask=frame.split()[-1] if frame.mode == 'RGBA' else None)
                frame = background
            elif frame.mode != 'RGB':
                frame = frame.convert('RGB')
            
            # Save to bytes
            output_buffer = io.BytesIO()
            frame.save(output_buffer, format=output_format, quality=95)
            output_buffer.seek(0)
            
            mime_type = f"image/{output_format.lower()}"
            logger.info(f"Extracted frame {target_frame + 1}/{frame_count} from animated GIF -> {output_format}")
            
            return output_buffer.getvalue(), mime_type
            
    except Exception as e:
        logger.error(f"Failed to extract GIF frame: {e}")
        raise ValueError(f"GIF processing failed: {e}") from e


def process_image_for_llm(image_bytes: bytes, content_type: Optional[str] = None) -> Tuple[str, str]:
    """
    Process image bytes for LLM vision API consumption.
    
    Handles:
    - Animated GIFs: Extracts a middle frame as PNG (avoids fade-in/title frames)
    - Other formats: Returns as-is with proper encoding
    
    Args:
        image_bytes: Raw image data
        content_type: Original content-type header (e.g., "image/gif")
        
    Returns:
        Tuple of (base64_encoded_data, mime_type)
    """
    # Check if this is an animated GIF that needs processing
    is_gif = (content_type and "gif" in content_type.lower()) or image_bytes[:6] in (b'GIF87a', b'GIF89a')
    
    if is_gif and PILLOW_AVAILABLE and is_animated_gif(image_bytes):
        # Extract middle frame and convert to PNG (avoids fade-in frames)
        try:
            processed_bytes, mime_type = extract_gif_frame(image_bytes, "PNG", frame_position="middle")
            return base64.b64encode(processed_bytes).decode('utf-8'), mime_type
        except ValueError as e:
            logger.warning(f"GIF processing failed, using original: {e}")
            # Fall through to return original
    
    # Return original image as-is
    mime_type = content_type or "image/png"
    return base64.b64encode(image_bytes).decode('utf-8'), mime_type
