import os
import tempfile
from typing import Optional, Tuple
from loguru import logger
from src_v2.core.character import Character
from src_v2.voice.tts import tts_manager
from src_v2.config.settings import settings
from src_v2.core.quota import quota_manager, QuotaExceededError
from src_v2.artifacts.registry import artifact_registry

from src_v2.workers.task_queue import task_queue

class VoiceResponseManager:
    """Orchestrates voice response generation and file handling."""
    
    async def generate_voice_response(self, text: str, character: Character, user_id: Optional[str] = None) -> bool:
        """
        Queues a voice response generation task.
        Returns True if queued successfully, False otherwise.
        Raises QuotaExceededError if quota is exceeded.
        """
        if not settings.ENABLE_VOICE_RESPONSES:
            return False
            
        # Check Quota
        if user_id:
            has_quota = await quota_manager.check_quota(user_id, 'audio')
            if not has_quota:
                usage = await quota_manager.get_usage(user_id, 'audio')
                limit = settings.DAILY_AUDIO_QUOTA
                logger.info(f"Voice response blocked for user {user_id}: Daily quota exceeded")
                raise QuotaExceededError('audio', limit, usage)

        # Resolve Voice ID
        voice_id = None
        if character.voice_config and character.voice_config.voice_id:
            voice_id = character.voice_config.voice_id
        
        # Fallback to global setting if not set in character config
        if not voice_id and settings.ELEVENLABS_VOICE_ID:
            voice_id = settings.ELEVENLABS_VOICE_ID
            
        if not voice_id:
            logger.warning(f"Voice response requested for {character.name} but no voice_id found (checked character config and global settings).")
            return False
            
        # Truncate text if too long
        if len(text) > settings.VOICE_RESPONSE_MAX_LENGTH:
            logger.info(f"Truncating voice response text from {len(text)} to {settings.VOICE_RESPONSE_MAX_LENGTH}")
            text = text[:settings.VOICE_RESPONSE_MAX_LENGTH]
        
        try:
            # Queue Task
            await task_queue.enqueue(
                "run_voice_generation",
                user_id=user_id,
                text=text,
                voice_id=voice_id,
                character_name=character.name
            )
            
            logger.info(f"Queued voice generation task for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error queuing voice response: {e}")
            return False

# Global instance
voice_response_manager = VoiceResponseManager()
