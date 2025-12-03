"""
Autonomous Reaction Agent (Phase E12)

Decides when and what emoji reactions to add to messages in channels.
This creates organic bot presence without requiring direct interaction.

Key Principles:
- No LLM calls for reaction decisions (keep it fast and cheap)
- Character-specific reaction styles (from ux.yaml)
- Strict rate limiting to prevent spam
- Activity-aware (react less when humans are active)
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import random
from loguru import logger

from src_v2.config.settings import settings
from src_v2.core.database import db_manager
from src_v2.core.character import character_manager


@dataclass
class ReactionStyle:
    """Configuration for a character's reaction behavior."""
    enabled: bool = True
    base_rate: float = 0.3  # Base probability of reacting
    topic_boost: float = 0.5  # Additional probability for relevant topics
    
    # Emoji sets by context
    positive_emojis: List[str] = field(default_factory=lambda: ["❤️", "✨", "🔥", "💯"])
    thinking_emojis: List[str] = field(default_factory=lambda: ["🤔", "💭", "👀"])
    agreement_emojis: List[str] = field(default_factory=lambda: ["👍", "💯", "✅"])
    excitement_emojis: List[str] = field(default_factory=lambda: ["🎉", "🙌", "⭐"])
    supportive_emojis: List[str] = field(default_factory=lambda: ["💜", "🫂", "💪"])
    
    # Character-specific signature emoji
    signature_emojis: List[str] = field(default_factory=list)
    
    # Timing
    reaction_delay_min: int = 2  # Minimum seconds to wait
    reaction_delay_max: int = 15  # Maximum seconds to wait


@dataclass
class ReactionDecision:
    """Result of a reaction decision."""
    should_react: bool
    emojis: List[str]
    delay_seconds: float
    reason: str


class ReactionCooldownManager:
    """
    Manages rate limiting for autonomous reactions.
    Uses Redis for persistence, falls back to in-memory.
    """
    
    def __init__(self):
        self.max_reactions_per_channel_per_hour = getattr(
            settings, 'REACTION_CHANNEL_HOURLY_MAX', 10
        )
        self.min_seconds_same_user = getattr(
            settings, 'REACTION_SAME_USER_COOLDOWN_SECONDS', 300
        )
        self.max_daily_global = getattr(
            settings, 'REACTION_DAILY_MAX', 100
        )
        
        # In-memory fallback
        self._channel_counts: Dict[str, int] = {}
        self._channel_reset: Dict[str, datetime] = {}
        self._user_last: Dict[str, datetime] = {}
        self._daily_count = 0
        self._daily_reset: Optional[datetime] = None
    
    def _check_daily_reset(self) -> None:
        """Reset daily counter if new day."""
        now = datetime.now()
        if self._daily_reset is None or now.date() > self._daily_reset.date():
            self._daily_count = 0
            self._daily_reset = now
            self._channel_counts.clear()
            self._channel_reset.clear()
    
    async def can_react(self, channel_id: str, user_id: str, bot_name: str) -> Tuple[bool, str]:
        """
        Check if a reaction is allowed.
        
        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        # Redis path
        if db_manager.redis_client:
            try:
                now = datetime.now()
                today = now.strftime("%Y-%m-%d")
                hour = now.strftime("%Y-%m-%d-%H")
                
                daily_key = f"reaction:{bot_name}:daily:{today}"
                channel_key = f"reaction:{bot_name}:channel:{channel_id}:{hour}"
                user_key = f"reaction:{bot_name}:user:{user_id}"
                
                # Check daily limit
                daily_count = await db_manager.redis_client.get(daily_key)
                if daily_count and int(daily_count) >= self.max_daily_global:
                    return False, "daily_limit"
                
                # Check channel hourly limit
                channel_count = await db_manager.redis_client.get(channel_key)
                if channel_count and int(channel_count) >= self.max_reactions_per_channel_per_hour:
                    return False, "channel_limit"
                
                # Check user cooldown
                user_last = await db_manager.redis_client.get(user_key)
                if user_last:
                    last_time = datetime.fromisoformat(user_last)
                    if (now - last_time).total_seconds() < self.min_seconds_same_user:
                        return False, "user_cooldown"
                
                return True, "allowed"
            except Exception as e:
                logger.error(f"Redis error in can_react: {e}. Falling back to memory.")
        
        # In-memory fallback
        self._check_daily_reset()
        now = datetime.now()
        
        if self._daily_count >= self.max_daily_global:
            return False, "daily_limit"
        
        # Check channel hourly
        hour_key = f"{channel_id}:{now.strftime('%H')}"
        if hour_key in self._channel_reset:
            if now - self._channel_reset[hour_key] > timedelta(hours=1):
                self._channel_counts[hour_key] = 0
                self._channel_reset[hour_key] = now
        else:
            self._channel_counts[hour_key] = 0
            self._channel_reset[hour_key] = now
        
        if self._channel_counts.get(hour_key, 0) >= self.max_reactions_per_channel_per_hour:
            return False, "channel_limit"
        
        # Check user cooldown
        if user_id in self._user_last:
            if (now - self._user_last[user_id]).total_seconds() < self.min_seconds_same_user:
                return False, "user_cooldown"
        
        return True, "allowed"
    
    async def record_reaction(self, channel_id: str, user_id: str, bot_name: str) -> None:
        """Record that a reaction was sent."""
        if db_manager.redis_client:
            try:
                now = datetime.now()
                today = now.strftime("%Y-%m-%d")
                hour = now.strftime("%Y-%m-%d-%H")
                
                daily_key = f"reaction:{bot_name}:daily:{today}"
                channel_key = f"reaction:{bot_name}:channel:{channel_id}:{hour}"
                user_key = f"reaction:{bot_name}:user:{user_id}"
                
                async with db_manager.redis_client.pipeline() as pipe:
                    await pipe.incr(daily_key)
                    await pipe.expire(daily_key, 172800)  # 48h
                    
                    await pipe.incr(channel_key)
                    await pipe.expire(channel_key, 7200)  # 2h
                    
                    await pipe.set(user_key, now.isoformat())
                    await pipe.expire(user_key, self.min_seconds_same_user)
                    
                    await pipe.execute()
                return
            except Exception as e:
                logger.error(f"Redis error in record_reaction: {e}")
        
        # In-memory fallback
        now = datetime.now()
        hour_key = f"{channel_id}:{now.strftime('%H')}"
        self._channel_counts[hour_key] = self._channel_counts.get(hour_key, 0) + 1
        self._user_last[user_id] = now
        self._daily_count += 1


class MessageAnalysis:
    """Simple content analysis for reaction decisions."""
    
    # Sentiment indicators
    POSITIVE_WORDS = frozenset([
        "amazing", "awesome", "beautiful", "brilliant", "cool", "excellent",
        "fantastic", "good", "great", "happy", "incredible", "love", "nice",
        "perfect", "super", "thanks", "thank you", "wonderful", "wow", "yay",
        "excited", "proud", "congrats", "congratulations", "celebrate"
    ])
    
    NEGATIVE_WORDS = frozenset([
        "bad", "hate", "terrible", "awful", "horrible", "sad", "angry",
        "frustrated", "annoyed", "disappointed", "worried", "scared"
    ])
    
    QUESTION_STARTERS = frozenset([
        "what", "how", "why", "when", "where", "who", "which", "can", "could",
        "would", "should", "is", "are", "do", "does", "did", "has", "have"
    ])
    
    SUPPORTIVE_TRIGGERS = frozenset([
        "struggling", "hard day", "rough", "difficult", "stressed", "overwhelmed",
        "tired", "exhausted", "anxious", "nervous", "scared", "afraid", "alone"
    ])
    
    @classmethod
    def analyze(cls, content: str) -> dict:
        """Analyze message content for reaction-relevant signals."""
        content_lower = content.lower()
        words = set(content_lower.split())
        
        # Sentiment
        positive_count = len(words & cls.POSITIVE_WORDS)
        negative_count = len(words & cls.NEGATIVE_WORDS)
        
        sentiment = "neutral"
        if positive_count > negative_count and positive_count >= 1:
            sentiment = "positive"
        elif negative_count > positive_count and negative_count >= 1:
            sentiment = "negative"
        
        # Question detection
        first_word = content_lower.split()[0] if content_lower.split() else ""
        is_question = "?" in content or first_word in cls.QUESTION_STARTERS
        
        # Support needed
        needs_support = bool(words & cls.SUPPORTIVE_TRIGGERS)
        
        # Excitement (caps, exclamation)
        is_excited = content.isupper() or content.count("!") >= 2
        
        # Length (short messages less interesting)
        word_count = len(content.split())
        
        return {
            "sentiment": sentiment,
            "is_question": is_question,
            "needs_support": needs_support,
            "is_excited": is_excited,
            "word_count": word_count,
            "positive_count": positive_count,
            "negative_count": negative_count,
        }


class ReactionAgent:
    """
    Decides when and what emoji reactions to add to messages.
    
    This agent observes channel messages and occasionally adds
    contextually appropriate reactions to create organic engagement.
    """
    
    def __init__(self, character_name: str):
        self.character_name = character_name
        self.cooldown_manager = ReactionCooldownManager()
        self._style: Optional[ReactionStyle] = None
        self._loaded = False
    
    def _load_style(self) -> ReactionStyle:
        """Load reaction style from character config."""
        if self._loaded and self._style:
            return self._style
        
        character = character_manager.get_character(self.character_name)
        if not character:
            logger.warning(f"Character {self.character_name} not found, using defaults")
            self._style = ReactionStyle()
            self._loaded = True
            return self._style
        
        # Load reactions config directly from ux.yaml
        import os
        import yaml
        
        reactions_config = {}
        ux_yaml_path = os.path.join("characters", self.character_name, "ux.yaml")
        if os.path.exists(ux_yaml_path):
            try:
                with open(ux_yaml_path, "r", encoding="utf-8") as f:
                    ux_config = yaml.safe_load(f)
                    if ux_config and "reactions" in ux_config:
                        reactions_config = ux_config["reactions"]
            except Exception as e:
                logger.warning(f"Failed to load reactions config from {ux_yaml_path}: {e}")
        
        # Use emoji_sets from Character if no reactions config
        emoji_sets = character.emoji_sets or {}
        
        self._style = ReactionStyle(
            enabled=reactions_config.get('enabled', True),
            base_rate=reactions_config.get('base_rate', 0.3),
            topic_boost=reactions_config.get('topic_boost', 0.5),
            positive_emojis=reactions_config.get('positive_emojis', emoji_sets.get('positive', ["❤️", "✨", "🔥", "💯"])),
            thinking_emojis=reactions_config.get('thinking_emojis', emoji_sets.get('thinking', ["🤔", "💭", "👀"])),
            agreement_emojis=reactions_config.get('agreement_emojis', ["👍", "💯", "✅"]),
            excitement_emojis=reactions_config.get('excitement_emojis', emoji_sets.get('celebration', ["🎉", "🙌", "⭐"])),
            supportive_emojis=reactions_config.get('supportive_emojis', emoji_sets.get('affection', ["💜", "🫂", "💪"])),
            signature_emojis=reactions_config.get('signature_emojis', []),
            reaction_delay_min=reactions_config.get('reaction_delay_seconds', [2, 15])[0] if isinstance(reactions_config.get('reaction_delay_seconds'), list) else 2,
            reaction_delay_max=reactions_config.get('reaction_delay_seconds', [2, 15])[1] if isinstance(reactions_config.get('reaction_delay_seconds'), list) else 15,
        )
        self._loaded = True
        return self._style
    
    async def decide_reaction(
        self,
        message_content: str,
        message_author_id: str,
        message_author_is_bot: bool,
        channel_id: str,
        is_command: bool = False,
    ) -> ReactionDecision:
        """
        Decide whether to react to a message and what emoji to use.
        
        Args:
            message_content: The text content of the message
            message_author_id: Discord user ID of the message author
            message_author_is_bot: Whether the author is a bot
            channel_id: Discord channel ID
            is_command: Whether this appears to be a command
            
        Returns:
            ReactionDecision with should_react, emojis, delay, and reason
        """
        style = self._load_style()
        
        # Quick rejections
        if not style.enabled:
            return ReactionDecision(False, [], 0, "reactions_disabled")
        
        if message_author_is_bot:
            return ReactionDecision(False, [], 0, "author_is_bot")
        
        if is_command or message_content.startswith(("/", "!", ".")):
            return ReactionDecision(False, [], 0, "is_command")
        
        if len(message_content) < 5:
            return ReactionDecision(False, [], 0, "too_short")
        
        # Rate limit check
        can_react, cooldown_reason = await self.cooldown_manager.can_react(
            channel_id, message_author_id, self.character_name
        )
        if not can_react:
            return ReactionDecision(False, [], 0, f"cooldown:{cooldown_reason}")
        
        # Analyze message
        analysis = MessageAnalysis.analyze(message_content)
        
        # Calculate reaction probability
        base_prob = style.base_rate
        
        # Boost for positive/excited content
        if analysis["sentiment"] == "positive":
            base_prob += 0.2
        if analysis["is_excited"]:
            base_prob += 0.15
        
        # Reduce for very short messages
        if analysis["word_count"] < 10:
            base_prob *= 0.7
        
        # Roll the dice
        roll = random.random()
        if roll > base_prob:
            return ReactionDecision(False, [], 0, f"random_skip:{roll:.2f}>{base_prob:.2f}")
        
        # Pick appropriate emoji(s)
        emojis, category = self._select_emojis(analysis, style)
        
        if not emojis:
            return ReactionDecision(False, [], 0, "no_emoji_match")
        
        # Calculate delay
        delay = random.uniform(style.reaction_delay_min, style.reaction_delay_max)
        
        return ReactionDecision(
            should_react=True,
            emojis=emojis,
            delay_seconds=delay,
            reason=f"category:{category}"
        )
    
    def _select_emojis(self, analysis: dict, style: ReactionStyle) -> tuple[List[str], str]:
        """
        Select appropriate emojis based on message analysis.
        
        Returns:
            Tuple of (emoji_list, category_reason)
        """
        candidates: List[str] = []
        category = "neutral"
        
        if analysis["needs_support"]:
            candidates.extend(style.supportive_emojis)
            category = "support"
        elif analysis["is_excited"] or analysis["sentiment"] == "positive":
            # 70% chance positive, 30% chance excitement
            if random.random() < 0.7:
                candidates.extend(style.positive_emojis)
                category = "positive"
            else:
                candidates.extend(style.excitement_emojis)
                category = "excitement"
        elif analysis["is_question"]:
            candidates.extend(style.thinking_emojis)
            category = "thinking"
        else:
            # Neutral - maybe a light positive
            if random.random() < 0.5:
                candidates.extend(style.positive_emojis[:2])  # Just hearts/sparkles
                category = "light_positive"
        
        # Maybe add signature emoji
        if style.signature_emojis and random.random() < 0.2:
            candidates.extend(style.signature_emojis)
            if category == "neutral":
                category = "signature"
        
        if not candidates:
            return [], "no_match"
        
        # Pick 1-2 emojis
        num_emojis = 1 if random.random() < 0.8 else 2
        return random.sample(candidates, min(num_emojis, len(candidates))), category
    
    async def record_reaction(self, channel_id: str, user_id: str) -> None:
        """Record that we sent a reaction for rate limiting."""
        await self.cooldown_manager.record_reaction(channel_id, user_id, self.character_name)


# Singleton instances per character
_reaction_agents: Dict[str, ReactionAgent] = {}


def get_reaction_agent(character_name: str) -> ReactionAgent:
    """Get or create a ReactionAgent for a character."""
    if character_name not in _reaction_agents:
        _reaction_agents[character_name] = ReactionAgent(character_name)
    return _reaction_agents[character_name]
