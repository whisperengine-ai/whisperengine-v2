from typing import List, Optional
from src_v2.core.character import Character
from src_v2.config.settings import settings

class VoiceTriggerDetector:
    """Detects if a user message triggers a voice response."""
    
    @staticmethod
    def should_trigger_voice(message: str, character: Character) -> bool:
        """
        Check if the message contains any voice trigger keywords for the character.
        """
        keywords = ["speak", "say", "voice", "audio"] # Defaults
        
        if character.voice_config:
            keywords = character.voice_config.trigger_keywords
        elif not settings.ELEVENLABS_VOICE_ID:
            # No character config AND no global voice ID -> No voice
            return False
            
        message_lower = message.lower()
        for keyword in keywords:
            if keyword.lower() in message_lower:
                return True
                
        return False
