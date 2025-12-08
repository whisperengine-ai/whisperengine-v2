"""
Universe Event Detector (Phase 3.4)

Analyzes conversations to detect significant events worth sharing
across the universe. This runs after each response is generated.

Detection is lightweight and rule-based (no LLM calls) to avoid
adding latency. The goal is to catch obvious signals:
- Emotional spikes (explicit statements of feeling)
- Major life updates (job, move, graduation, etc.)
- Topic discoveries (new hobbies, interests mentioned for first time)
"""

from typing import Optional, Dict, Any
from loguru import logger
import re

from src_v2.config.settings import settings
from src_v2.universe.bus import UniverseEvent, EventType, event_bus
from src_v2.safety.sensitivity import sensitivity_checker


# Patterns for detecting emotional spikes
POSITIVE_EMOTION_PATTERNS = [
    r"\b(so happy|really excited|amazing news|great news|best day)\b",
    r"\b(i got|just got|we got)\b.{0,30}\b(promoted|job|offer|accepted)\b",
    r"\b(engaged|getting married|had a baby|expecting)\b",
    r"\b(finally|at last)\b.{0,20}\b(did it|made it|finished|completed)\b",
]

NEGATIVE_EMOTION_PATTERNS = [
    r"\b(so sad|really upset|terrible news|awful|devastated)\b",
    r"\b(i lost|just lost|we lost)\b.{0,30}\b(job|pet|someone|mom|dad|friend)\b",
    r"\b(broke up|got fired|laid off|diagnosed)\b",
    r"\b(don't know what to do|feel hopeless|at my lowest)\b",
]

# Patterns for major life updates
LIFE_UPDATE_PATTERNS = [
    (r"\b(got a new job|started new job|got promoted|got hired)\b", "career"),
    (r"\b(moving to|moved to|relocating to|just moved)\b", "relocation"),
    (r"\b(graduating|graduated|finished school|got my degree)\b", "education"),
    (r"\b(engaged|getting married|got married|wedding)\b", "relationship"),
    (r"\b(having a baby|pregnant|expecting|new baby)\b", "family"),
    (r"\b(bought a house|new home|closing on|first house)\b", "home"),
]

# Compile patterns for efficiency
_positive_patterns = [re.compile(p, re.IGNORECASE) for p in POSITIVE_EMOTION_PATTERNS]
_negative_patterns = [re.compile(p, re.IGNORECASE) for p in NEGATIVE_EMOTION_PATTERNS]
_life_patterns = [(re.compile(p, re.IGNORECASE), topic) for p, topic in LIFE_UPDATE_PATTERNS]


class EventDetector:
    """
    Detects significant events from user messages.
    
    This is called after each response. If a significant event is detected,
    it's published to the universe event bus for cross-bot sharing.
    
    Detection can use either:
    1. LLM-detected intents (preferred) - passed from the classifier
    2. Regex patterns (fallback) - for when intents aren't available
    """
    
    async def analyze_and_publish(
        self,
        user_id: str,
        user_message: str,
        character_name: str,
        detected_intents: Optional[Dict[str, Any]] = None,
        user_name: Optional[str] = None
    ) -> Optional[UniverseEvent]:
        """
        Analyze a user message for significant events and publish if found.
        
        Args:
            user_id: Discord user ID
            user_message: The user's message text
            character_name: The bot that received this message
            detected_intents: Optional list of intents from LLM classifier
            user_name: Display name of the user (for readable summaries)
            
        Returns:
            The published event if one was detected, None otherwise
        """
        if not settings.ENABLE_UNIVERSE_EVENTS:
            return None
        
        # Use a privacy-safe fallback if no name provided
        display_name = user_name or "someone"
        
        event: Optional[UniverseEvent] = None
        
        # Prefer LLM-detected intents if available
        if detected_intents:
            event = self._detect_from_intents(user_id, user_message, character_name, detected_intents, display_name)
        
        # Fallback to regex if no intent-based detection
        if not event:
            event = self._detect_emotional_spike(user_id, user_message, character_name, display_name)
        
        if not event:
            event = self._detect_life_update(user_id, user_message, character_name, display_name)
        
        if event:
            # S3: LLM-based sensitivity check before publishing
            # This catches context-dependent sensitivity that keywords miss
            if settings.ENABLE_SENSITIVITY_CHECK:
                is_sensitive, reason = await sensitivity_checker.is_sensitive(
                    content=user_message,
                    topic=event.topic,
                    event_summary=event.summary
                )
                
                if is_sensitive:
                    logger.info(f"Event blocked by sensitivity check: {reason}")
                    return None
            
            await event_bus.publish(event)
            return event
        
        return None
    
    def _detect_from_intents(
        self,
        user_id: str,
        _message: str,
        character_name: str,
        detected_intents: Dict[str, Any],
        display_name: str
    ) -> Optional[UniverseEvent]:
        """Detect events from LLM-classified intents."""
        intents = detected_intents.get("intents", [])
        
        if "event_positive" in intents:
            logger.debug(f"LLM detected positive emotion event for user {user_id}")
            return UniverseEvent(
                event_type=EventType.EMOTIONAL_SPIKE,
                user_id=user_id,
                source_bot=character_name,
                summary=f"{display_name} is feeling very happy",
                topic="positive_emotion",
                metadata={"sentiment": "positive", "source": "llm_intent"}
            )
        
        if "event_negative" in intents:
            logger.debug(f"LLM detected negative emotion event for user {user_id}")
            return UniverseEvent(
                event_type=EventType.EMOTIONAL_SPIKE,
                user_id=user_id,
                source_bot=character_name,
                summary=f"{display_name} seems to be going through a tough time",
                topic="negative_emotion",
                metadata={"sentiment": "negative", "source": "llm_intent"}
            )
        
        if "event_life_update" in intents:
            logger.debug(f"LLM detected life update event for user {user_id}")
            return UniverseEvent(
                event_type=EventType.USER_UPDATE,
                user_id=user_id,
                source_bot=character_name,
                summary=f"{display_name} shared some personal news",
                topic="life_update",
                metadata={"source": "llm_intent"}
            )
        
        return None
    
    def _detect_emotional_spike(
        self,
        user_id: str,
        message: str,
        character_name: str,
        display_name: str
    ) -> Optional[UniverseEvent]:
        """Detect strong emotional expressions."""
        
        # Check positive emotions
        for pattern in _positive_patterns:
            match = pattern.search(message)
            if match:
                return UniverseEvent(
                    event_type=EventType.EMOTIONAL_SPIKE,
                    user_id=user_id,
                    source_bot=character_name,
                    summary=f"{display_name} is feeling very happy",
                    topic="positive_emotion",
                    metadata={"sentiment": "positive", "match": match.group(0)}
                )
        
        # Check negative emotions
        for pattern in _negative_patterns:
            match = pattern.search(message)
            if match:
                return UniverseEvent(
                    event_type=EventType.EMOTIONAL_SPIKE,
                    user_id=user_id,
                    source_bot=character_name,
                    summary=f"{display_name} seems to be going through a tough time",
                    topic="negative_emotion",
                    metadata={"sentiment": "negative", "match": match.group(0)}
                )
        
        return None
    
    def _detect_life_update(
        self,
        user_id: str,
        message: str,
        character_name: str,
        display_name: str
    ) -> Optional[UniverseEvent]:
        """Detect major life updates."""
        
        for pattern, topic in _life_patterns:
            match = pattern.search(message)
            if match:
                # Create a privacy-safe summary
                summary_map = {
                    "career": "has news about their career",
                    "relocation": "is moving or has moved",
                    "education": "has education news",
                    "relationship": "has relationship news",
                    "family": "has family news",
                    "home": "has news about their home",
                }
                
                summary_text = summary_map.get(topic, "shared some personal news")
                return UniverseEvent(
                    event_type=EventType.USER_UPDATE,
                    user_id=user_id,
                    source_bot=character_name,
                    summary=f"{display_name} {summary_text}",
                    topic=topic,
                    metadata={"match": match.group(0)}
                )
        
        return None


# Global instance
event_detector = EventDetector()
