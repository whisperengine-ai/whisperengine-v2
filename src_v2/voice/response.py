import os
import tempfile
from typing import Optional, Tuple
from loguru import logger
from src_v2.core.character import Character
from src_v2.voice.tts import tts_manager
from src_v2.config.settings import settings

class VoiceResponseManager:
    """Orchestrates voice response generation and file handling."""
    
    async def generate_voice_response(self, text: str, character: Character) -> Optional[Tuple[str, str]]:
        """
        Generates a voice response for the given text and character.
        Returns a tuple of (file_path, filename) or None if generation fails.
        """
        if not settings.ENABLE_VOICE_RESPONSES:
            return None
            
        # Resolve Voice ID
        voice_id = None
        if character.voice_config and character.voice_config.voice_id:
            voice_id = character.voice_config.voice_id
        
        # Fallback to global setting if not set in character config
        if not voice_id and settings.ELEVENLABS_VOICE_ID:
            voice_id = settings.ELEVENLABS_VOICE_ID
            
        if not voice_id:
            logger.warning(f"Voice response requested for {character.name} but no voice_id found (checked character config and global settings).")
            return None
            
        # Truncate text if too long
        if len(text) > settings.VOICE_RESPONSE_MAX_LENGTH:
            logger.info(f"Truncating voice response text from {len(text)} to {settings.VOICE_RESPONSE_MAX_LENGTH}")
            text = text[:settings.VOICE_RESPONSE_MAX_LENGTH]
        
        try:
            audio_bytes = await tts_manager.generate_speech(text, voice_id=voice_id)
            if not audio_bytes:
                return None
                
            # Create a temporary file
            temp_dir = tempfile.gettempdir()
            filename = f"{character.name.lower()}_voice_{os.urandom(4).hex()}.mp3"
            file_path = os.path.join(temp_dir, filename)
            
            with open(file_path, "wb") as f:
                f.write(audio_bytes)
                
            logger.info(f"Generated voice response file: {file_path}")
            return file_path, filename
            
        except Exception as e:
            logger.error(f"Error generating voice response: {e}")
            return None

# Global instance
voice_response_manager = VoiceResponseManager()
