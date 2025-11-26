"""
Emoji Taxonomy System for WhisperEngine v2

A comprehensive classification system for emojis used in Discord reactions.
This module provides:
- Sentiment classification (positive, negative, neutral)
- Weighted scoring based on intensity
- Categorical groupings for analytics
- Easy extensibility for new emojis

Usage:
    from src_v2.evolution.emoji_taxonomy import EmojiTaxonomy
    
    taxonomy = EmojiTaxonomy()
    score = taxonomy.get_score("🔥")  # Returns 1.2 (high positive)
    sentiment = taxonomy.get_sentiment("👎")  # Returns "negative"
    category = taxonomy.get_category("😂")  # Returns "laughter"
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Sentiment(Enum):
    """Emoji sentiment classification."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class Category(Enum):
    """Emoji category for analytics and grouping."""
    # Positive categories
    LOVE = "love"
    LAUGHTER = "laughter"
    CELEBRATION = "celebration"
    APPROVAL = "approval"
    AMAZEMENT = "amazement"
    SUPPORT = "support"
    GRATITUDE = "gratitude"
    COOL = "cool"
    
    # Negative categories
    DISAPPROVAL = "disapproval"
    SADNESS = "sadness"
    ANGER = "anger"
    DISGUST = "disgust"
    DISAPPOINTMENT = "disappointment"
    
    # Neutral categories
    THINKING = "thinking"
    SURPRISE = "surprise"
    INFORMATIONAL = "informational"
    MISC = "misc"


@dataclass
class EmojiDefinition:
    """
    Complete definition of an emoji's meaning and scoring.
    
    Attributes:
        emoji: The emoji character
        sentiment: Positive, negative, or neutral
        category: Semantic category for analytics
        score: Weighted score (-2.0 to +2.0)
            - +2.0: Extremely positive (rare)
            - +1.5: Very positive
            - +1.0: Standard positive
            - +0.5: Mildly positive
            - 0.0: Neutral
            - -0.5: Mildly negative
            - -1.0: Standard negative
            - -1.5: Very negative
            - -2.0: Extremely negative (rare)
        name: Human-readable name
        aliases: Alternative representations (optional)
    """
    emoji: str
    sentiment: Sentiment
    category: Category
    score: float
    name: str
    aliases: Optional[list[str]] = None


# =============================================================================
# EMOJI DEFINITIONS
# Organized by sentiment, then by category within each sentiment
# =============================================================================

EMOJI_DEFINITIONS: list[EmojiDefinition] = [
    # =========================================================================
    # POSITIVE EMOJIS
    # =========================================================================
    
    # --- Love & Affection (score: 1.0 - 1.5) ---
    EmojiDefinition("❤️", Sentiment.POSITIVE, Category.LOVE, 1.2, "red heart"),
    EmojiDefinition("💖", Sentiment.POSITIVE, Category.LOVE, 1.2, "sparkling heart"),
    EmojiDefinition("💕", Sentiment.POSITIVE, Category.LOVE, 1.0, "two hearts"),
    EmojiDefinition("💗", Sentiment.POSITIVE, Category.LOVE, 1.0, "growing heart"),
    EmojiDefinition("💝", Sentiment.POSITIVE, Category.LOVE, 1.0, "heart with ribbon"),
    EmojiDefinition("💜", Sentiment.POSITIVE, Category.LOVE, 1.0, "purple heart"),
    EmojiDefinition("💙", Sentiment.POSITIVE, Category.LOVE, 1.0, "blue heart"),
    EmojiDefinition("💚", Sentiment.POSITIVE, Category.LOVE, 1.0, "green heart"),
    EmojiDefinition("🧡", Sentiment.POSITIVE, Category.LOVE, 1.0, "orange heart"),
    EmojiDefinition("💛", Sentiment.POSITIVE, Category.LOVE, 1.0, "yellow heart"),
    EmojiDefinition("🤍", Sentiment.POSITIVE, Category.LOVE, 1.0, "white heart"),
    EmojiDefinition("🖤", Sentiment.POSITIVE, Category.LOVE, 0.8, "black heart"),  # Often used positively in alt communities
    EmojiDefinition("❤️‍🔥", Sentiment.POSITIVE, Category.LOVE, 1.5, "heart on fire"),
    EmojiDefinition("😍", Sentiment.POSITIVE, Category.LOVE, 1.2, "heart eyes"),
    EmojiDefinition("🥰", Sentiment.POSITIVE, Category.LOVE, 1.2, "smiling with hearts"),
    EmojiDefinition("😘", Sentiment.POSITIVE, Category.LOVE, 1.0, "kiss face"),
    EmojiDefinition("💏", Sentiment.POSITIVE, Category.LOVE, 1.0, "kiss"),
    EmojiDefinition("🫶", Sentiment.POSITIVE, Category.LOVE, 1.2, "heart hands"),
    
    # --- Laughter & Joy (score: 1.0 - 1.5) ---
    EmojiDefinition("😂", Sentiment.POSITIVE, Category.LAUGHTER, 1.2, "face with tears of joy"),
    EmojiDefinition("🤣", Sentiment.POSITIVE, Category.LAUGHTER, 1.3, "rolling on floor laughing"),
    EmojiDefinition("😆", Sentiment.POSITIVE, Category.LAUGHTER, 1.0, "grinning squinting face"),
    EmojiDefinition("😁", Sentiment.POSITIVE, Category.LAUGHTER, 1.0, "beaming face"),
    EmojiDefinition("😄", Sentiment.POSITIVE, Category.LAUGHTER, 1.0, "grinning face with smiling eyes"),
    EmojiDefinition("😊", Sentiment.POSITIVE, Category.LAUGHTER, 0.8, "smiling face with smiling eyes"),
    EmojiDefinition("😸", Sentiment.POSITIVE, Category.LAUGHTER, 1.0, "grinning cat"),
    EmojiDefinition("😹", Sentiment.POSITIVE, Category.LAUGHTER, 1.2, "cat with tears of joy"),
    EmojiDefinition("🙃", Sentiment.POSITIVE, Category.LAUGHTER, 0.5, "upside-down face"),  # Playful
    EmojiDefinition("😏", Sentiment.POSITIVE, Category.LAUGHTER, 0.5, "smirking face"),
    EmojiDefinition("💀", Sentiment.POSITIVE, Category.LAUGHTER, 1.3, "skull"),  # "I'm dead" = hilarious
    EmojiDefinition("☠️", Sentiment.POSITIVE, Category.LAUGHTER, 1.2, "skull and crossbones"),  # Same usage
    
    # --- Celebration & Excitement (score: 1.0 - 1.5) ---
    EmojiDefinition("🎉", Sentiment.POSITIVE, Category.CELEBRATION, 1.2, "party popper"),
    EmojiDefinition("🎊", Sentiment.POSITIVE, Category.CELEBRATION, 1.2, "confetti ball"),
    EmojiDefinition("🥳", Sentiment.POSITIVE, Category.CELEBRATION, 1.2, "partying face"),
    EmojiDefinition("✨", Sentiment.POSITIVE, Category.CELEBRATION, 1.0, "sparkles"),
    EmojiDefinition("🌟", Sentiment.POSITIVE, Category.CELEBRATION, 1.0, "glowing star"),
    EmojiDefinition("⭐", Sentiment.POSITIVE, Category.CELEBRATION, 0.8, "star"),
    EmojiDefinition("🏆", Sentiment.POSITIVE, Category.CELEBRATION, 1.3, "trophy"),
    EmojiDefinition("👑", Sentiment.POSITIVE, Category.CELEBRATION, 1.3, "crown"),
    EmojiDefinition("💎", Sentiment.POSITIVE, Category.CELEBRATION, 1.2, "gem stone"),
    EmojiDefinition("🥇", Sentiment.POSITIVE, Category.CELEBRATION, 1.3, "first place medal"),
    EmojiDefinition("🥈", Sentiment.POSITIVE, Category.CELEBRATION, 1.0, "second place medal"),
    EmojiDefinition("🥉", Sentiment.POSITIVE, Category.CELEBRATION, 0.8, "third place medal"),
    EmojiDefinition("🎯", Sentiment.POSITIVE, Category.CELEBRATION, 1.0, "bullseye"),
    EmojiDefinition("🚀", Sentiment.POSITIVE, Category.CELEBRATION, 1.2, "rocket"),
    
    # --- Approval & Agreement (score: 0.8 - 1.2) ---
    EmojiDefinition("👍", Sentiment.POSITIVE, Category.APPROVAL, 1.0, "thumbs up"),
    EmojiDefinition("👍🏻", Sentiment.POSITIVE, Category.APPROVAL, 1.0, "thumbs up light skin"),
    EmojiDefinition("👍🏼", Sentiment.POSITIVE, Category.APPROVAL, 1.0, "thumbs up medium-light skin"),
    EmojiDefinition("👍🏽", Sentiment.POSITIVE, Category.APPROVAL, 1.0, "thumbs up medium skin"),
    EmojiDefinition("👍🏾", Sentiment.POSITIVE, Category.APPROVAL, 1.0, "thumbs up medium-dark skin"),
    EmojiDefinition("👍🏿", Sentiment.POSITIVE, Category.APPROVAL, 1.0, "thumbs up dark skin"),
    EmojiDefinition("👏", Sentiment.POSITIVE, Category.APPROVAL, 1.0, "clapping hands"),
    EmojiDefinition("🙌", Sentiment.POSITIVE, Category.APPROVAL, 1.2, "raising hands"),
    EmojiDefinition("💯", Sentiment.POSITIVE, Category.APPROVAL, 1.2, "hundred points"),
    EmojiDefinition("✅", Sentiment.POSITIVE, Category.APPROVAL, 0.8, "check mark"),
    EmojiDefinition("☑️", Sentiment.POSITIVE, Category.APPROVAL, 0.8, "ballot box with check"),
    EmojiDefinition("✔️", Sentiment.POSITIVE, Category.APPROVAL, 0.8, "check mark"),
    EmojiDefinition("👌", Sentiment.POSITIVE, Category.APPROVAL, 0.8, "OK hand"),
    EmojiDefinition("🤝", Sentiment.POSITIVE, Category.APPROVAL, 1.0, "handshake"),
    EmojiDefinition("🫡", Sentiment.POSITIVE, Category.APPROVAL, 1.0, "saluting face"),
    EmojiDefinition("🫶", Sentiment.POSITIVE, Category.APPROVAL, 1.0, "heart hands"),
    
    # --- Amazement & Mind Blown (score: 1.0 - 1.5) ---
    EmojiDefinition("🤯", Sentiment.POSITIVE, Category.AMAZEMENT, 1.3, "exploding head"),
    EmojiDefinition("🤩", Sentiment.POSITIVE, Category.AMAZEMENT, 1.2, "star-struck"),
    EmojiDefinition("😲", Sentiment.POSITIVE, Category.AMAZEMENT, 0.8, "astonished face"),
    EmojiDefinition("😱", Sentiment.POSITIVE, Category.AMAZEMENT, 0.8, "face screaming"),  # Often positive surprise
    EmojiDefinition("🔥", Sentiment.POSITIVE, Category.AMAZEMENT, 1.2, "fire"),
    EmojiDefinition("⚡", Sentiment.POSITIVE, Category.AMAZEMENT, 1.0, "high voltage"),
    EmojiDefinition("💥", Sentiment.POSITIVE, Category.AMAZEMENT, 1.0, "collision"),
    EmojiDefinition("🤌", Sentiment.POSITIVE, Category.AMAZEMENT, 1.0, "pinched fingers"),  # Chef's kiss
    EmojiDefinition("👀", Sentiment.POSITIVE, Category.AMAZEMENT, 0.5, "eyes"),  # Interest/attention
    
    # --- Support & Encouragement (score: 0.8 - 1.2) ---
    EmojiDefinition("💪", Sentiment.POSITIVE, Category.SUPPORT, 1.0, "flexed biceps"),
    EmojiDefinition("🙏", Sentiment.POSITIVE, Category.GRATITUDE, 1.0, "folded hands"),
    EmojiDefinition("🤗", Sentiment.POSITIVE, Category.SUPPORT, 1.0, "hugging face"),
    EmojiDefinition("🫂", Sentiment.POSITIVE, Category.SUPPORT, 1.0, "people hugging"),
    EmojiDefinition("❣️", Sentiment.POSITIVE, Category.SUPPORT, 1.0, "heart exclamation"),
    EmojiDefinition("💐", Sentiment.POSITIVE, Category.SUPPORT, 0.8, "bouquet"),
    EmojiDefinition("🌹", Sentiment.POSITIVE, Category.SUPPORT, 0.8, "rose"),
    EmojiDefinition("🌺", Sentiment.POSITIVE, Category.SUPPORT, 0.8, "hibiscus"),
    
    # --- Cool & Swagger (score: 0.8 - 1.2) ---
    EmojiDefinition("😎", Sentiment.POSITIVE, Category.COOL, 1.0, "smiling with sunglasses"),
    EmojiDefinition("🤙", Sentiment.POSITIVE, Category.COOL, 0.8, "call me hand"),
    EmojiDefinition("✌️", Sentiment.POSITIVE, Category.COOL, 0.8, "victory hand"),
    EmojiDefinition("🤟", Sentiment.POSITIVE, Category.COOL, 0.8, "love-you gesture"),
    EmojiDefinition("🤘", Sentiment.POSITIVE, Category.COOL, 0.8, "sign of the horns"),
    EmojiDefinition("😈", Sentiment.POSITIVE, Category.COOL, 0.8, "smiling imp"),  # Playful mischief
    EmojiDefinition("👻", Sentiment.POSITIVE, Category.COOL, 0.5, "ghost"),  # Playful
    EmojiDefinition("🦾", Sentiment.POSITIVE, Category.COOL, 1.0, "mechanical arm"),
    EmojiDefinition("🧠", Sentiment.POSITIVE, Category.COOL, 1.0, "brain"),  # "Big brain"
    
    # =========================================================================
    # NEGATIVE EMOJIS
    # =========================================================================
    
    # --- Disapproval (score: -0.8 to -1.5) ---
    EmojiDefinition("👎", Sentiment.NEGATIVE, Category.DISAPPROVAL, -1.0, "thumbs down"),
    EmojiDefinition("👎🏻", Sentiment.NEGATIVE, Category.DISAPPROVAL, -1.0, "thumbs down light skin"),
    EmojiDefinition("👎🏼", Sentiment.NEGATIVE, Category.DISAPPROVAL, -1.0, "thumbs down medium-light skin"),
    EmojiDefinition("👎🏽", Sentiment.NEGATIVE, Category.DISAPPROVAL, -1.0, "thumbs down medium skin"),
    EmojiDefinition("👎🏾", Sentiment.NEGATIVE, Category.DISAPPROVAL, -1.0, "thumbs down medium-dark skin"),
    EmojiDefinition("👎🏿", Sentiment.NEGATIVE, Category.DISAPPROVAL, -1.0, "thumbs down dark skin"),
    EmojiDefinition("🙄", Sentiment.NEGATIVE, Category.DISAPPROVAL, -0.8, "eye roll"),
    EmojiDefinition("😒", Sentiment.NEGATIVE, Category.DISAPPROVAL, -0.8, "unamused face"),
    EmojiDefinition("😑", Sentiment.NEGATIVE, Category.DISAPPROVAL, -0.6, "expressionless face"),
    EmojiDefinition("🚫", Sentiment.NEGATIVE, Category.DISAPPROVAL, -1.0, "prohibited"),
    EmojiDefinition("❌", Sentiment.NEGATIVE, Category.DISAPPROVAL, -1.0, "cross mark"),
    EmojiDefinition("⛔", Sentiment.NEGATIVE, Category.DISAPPROVAL, -1.0, "no entry"),
    
    # --- Sadness (score: -0.5 to -1.2) ---
    EmojiDefinition("😢", Sentiment.NEGATIVE, Category.SADNESS, -0.8, "crying face"),
    EmojiDefinition("😭", Sentiment.NEGATIVE, Category.SADNESS, -1.0, "loudly crying face"),
    EmojiDefinition("💔", Sentiment.NEGATIVE, Category.SADNESS, -1.0, "broken heart"),
    EmojiDefinition("😿", Sentiment.NEGATIVE, Category.SADNESS, -0.8, "crying cat"),
    EmojiDefinition("🥺", Sentiment.NEGATIVE, Category.SADNESS, -0.5, "pleading face"),
    EmojiDefinition("😞", Sentiment.NEGATIVE, Category.SADNESS, -0.8, "disappointed face"),
    EmojiDefinition("😔", Sentiment.NEGATIVE, Category.SADNESS, -0.6, "pensive face"),
    
    # --- Anger (score: -1.0 to -1.5) ---
    EmojiDefinition("😠", Sentiment.NEGATIVE, Category.ANGER, -1.2, "angry face"),
    EmojiDefinition("😡", Sentiment.NEGATIVE, Category.ANGER, -1.3, "pouting face"),
    EmojiDefinition("🤬", Sentiment.NEGATIVE, Category.ANGER, -1.5, "face with symbols on mouth"),
    EmojiDefinition("💢", Sentiment.NEGATIVE, Category.ANGER, -1.0, "anger symbol"),
    EmojiDefinition("👊", Sentiment.NEGATIVE, Category.ANGER, -0.8, "oncoming fist"),  # Can be aggressive
    
    # --- Disgust (score: -1.0 to -1.5) ---
    EmojiDefinition("🤮", Sentiment.NEGATIVE, Category.DISGUST, -1.3, "face vomiting"),
    EmojiDefinition("🤢", Sentiment.NEGATIVE, Category.DISGUST, -1.0, "nauseated face"),
    EmojiDefinition("💩", Sentiment.NEGATIVE, Category.DISGUST, -1.0, "pile of poo"),
    EmojiDefinition("🤡", Sentiment.NEGATIVE, Category.DISGUST, -1.2, "clown face"),  # Often mocking
    EmojiDefinition("🖕", Sentiment.NEGATIVE, Category.DISGUST, -2.0, "middle finger"),
    
    # --- Disappointment (score: -0.5 to -1.0) ---
    EmojiDefinition("😕", Sentiment.NEGATIVE, Category.DISAPPOINTMENT, -0.5, "confused face"),
    EmojiDefinition("🙁", Sentiment.NEGATIVE, Category.DISAPPOINTMENT, -0.6, "slightly frowning face"),
    EmojiDefinition("☹️", Sentiment.NEGATIVE, Category.DISAPPOINTMENT, -0.8, "frowning face"),
    EmojiDefinition("😟", Sentiment.NEGATIVE, Category.DISAPPOINTMENT, -0.6, "worried face"),
    EmojiDefinition("🫤", Sentiment.NEGATIVE, Category.DISAPPOINTMENT, -0.5, "face with diagonal mouth"),
    
    # =========================================================================
    # NEUTRAL EMOJIS
    # =========================================================================
    
    # --- Thinking & Contemplation (score: 0.0) ---
    EmojiDefinition("🤔", Sentiment.NEUTRAL, Category.THINKING, 0.0, "thinking face"),
    EmojiDefinition("🧐", Sentiment.NEUTRAL, Category.THINKING, 0.0, "face with monocle"),
    EmojiDefinition("🫠", Sentiment.NEUTRAL, Category.THINKING, 0.0, "melting face"),
    EmojiDefinition("🤷", Sentiment.NEUTRAL, Category.THINKING, 0.0, "shrug"),
    EmojiDefinition("😐", Sentiment.NEUTRAL, Category.THINKING, 0.0, "neutral face"),
    EmojiDefinition("😶", Sentiment.NEUTRAL, Category.THINKING, 0.0, "face without mouth"),
    EmojiDefinition("🫥", Sentiment.NEUTRAL, Category.THINKING, 0.0, "dotted line face"),
    
    # --- Surprise (score: 0.0, context-dependent) ---
    EmojiDefinition("😮", Sentiment.NEUTRAL, Category.SURPRISE, 0.0, "face with open mouth"),
    EmojiDefinition("😯", Sentiment.NEUTRAL, Category.SURPRISE, 0.0, "hushed face"),
    EmojiDefinition("😳", Sentiment.NEUTRAL, Category.SURPRISE, 0.0, "flushed face"),
    EmojiDefinition("🫢", Sentiment.NEUTRAL, Category.SURPRISE, 0.0, "face with open eyes and hand over mouth"),
    EmojiDefinition("😬", Sentiment.NEUTRAL, Category.SURPRISE, 0.0, "grimacing face"),
    EmojiDefinition("🙈", Sentiment.NEUTRAL, Category.SURPRISE, 0.0, "see-no-evil monkey"),
    EmojiDefinition("🙊", Sentiment.NEUTRAL, Category.SURPRISE, 0.0, "speak-no-evil monkey"),
    EmojiDefinition("🙉", Sentiment.NEUTRAL, Category.SURPRISE, 0.0, "hear-no-evil monkey"),
    
    # --- Informational (score: 0.0) ---
    EmojiDefinition("ℹ️", Sentiment.NEUTRAL, Category.INFORMATIONAL, 0.0, "information"),
    EmojiDefinition("❓", Sentiment.NEUTRAL, Category.INFORMATIONAL, 0.0, "question mark"),
    EmojiDefinition("❔", Sentiment.NEUTRAL, Category.INFORMATIONAL, 0.0, "white question mark"),
    EmojiDefinition("❗", Sentiment.NEUTRAL, Category.INFORMATIONAL, 0.0, "exclamation mark"),
    EmojiDefinition("❕", Sentiment.NEUTRAL, Category.INFORMATIONAL, 0.0, "white exclamation mark"),
    EmojiDefinition("💭", Sentiment.NEUTRAL, Category.INFORMATIONAL, 0.0, "thought balloon"),
    EmojiDefinition("💬", Sentiment.NEUTRAL, Category.INFORMATIONAL, 0.0, "speech balloon"),
    EmojiDefinition("🔄", Sentiment.NEUTRAL, Category.INFORMATIONAL, 0.0, "counterclockwise arrows"),
    EmojiDefinition("⏳", Sentiment.NEUTRAL, Category.INFORMATIONAL, 0.0, "hourglass not done"),
    EmojiDefinition("⌛", Sentiment.NEUTRAL, Category.INFORMATIONAL, 0.0, "hourglass done"),
    
    # --- Misc (score: 0.0) ---
    EmojiDefinition("👋", Sentiment.NEUTRAL, Category.MISC, 0.0, "waving hand"),
    EmojiDefinition("👁️", Sentiment.NEUTRAL, Category.MISC, 0.0, "eye"),
    EmojiDefinition("🫣", Sentiment.NEUTRAL, Category.MISC, 0.0, "face with peeking eye"),
    EmojiDefinition("😴", Sentiment.NEUTRAL, Category.MISC, 0.0, "sleeping face"),
    EmojiDefinition("🥱", Sentiment.NEUTRAL, Category.MISC, 0.0, "yawning face"),
    EmojiDefinition("😪", Sentiment.NEUTRAL, Category.MISC, 0.0, "sleepy face"),
]


class EmojiTaxonomy:
    """
    Main interface for emoji classification and scoring.
    
    Provides O(1) lookup for emoji properties and supports both
    the new weighted scoring system and backward-compatible
    simple +1/0/-1 scoring.
    """
    
    def __init__(self):
        """Initialize taxonomy with indexed lookups."""
        self._by_emoji: dict[str, EmojiDefinition] = {}
        self._by_sentiment: dict[Sentiment, list[EmojiDefinition]] = {
            Sentiment.POSITIVE: [],
            Sentiment.NEGATIVE: [],
            Sentiment.NEUTRAL: [],
        }
        self._by_category: dict[Category, list[EmojiDefinition]] = {cat: [] for cat in Category}
        
        # Build indexes
        for defn in EMOJI_DEFINITIONS:
            self._by_emoji[defn.emoji] = defn
            self._by_sentiment[defn.sentiment].append(defn)
            self._by_category[defn.category].append(defn)
    
    def get(self, emoji: str) -> Optional[EmojiDefinition]:
        """Get full definition for an emoji, or None if unknown."""
        return self._by_emoji.get(emoji)
    
    def get_score(self, emoji: str) -> float:
        """
        Get weighted score for an emoji.
        
        Returns:
            Weighted score from -2.0 to +2.0, or 0.0 for unknown emojis
        """
        defn = self._by_emoji.get(emoji)
        return defn.score if defn else 0.0
    
    def get_simple_score(self, emoji: str) -> int:
        """
        Get simple +1/0/-1 score for backward compatibility.
        
        This maintains compatibility with the existing FeedbackAnalyzer logic.
        """
        defn = self._by_emoji.get(emoji)
        if not defn:
            return 0
        if defn.sentiment == Sentiment.POSITIVE:
            return 1
        elif defn.sentiment == Sentiment.NEGATIVE:
            return -1
        return 0
    
    def get_sentiment(self, emoji: str) -> Optional[Sentiment]:
        """Get sentiment classification for an emoji."""
        defn = self._by_emoji.get(emoji)
        return defn.sentiment if defn else None
    
    def get_category(self, emoji: str) -> Optional[Category]:
        """Get category for an emoji."""
        defn = self._by_emoji.get(emoji)
        return defn.category if defn else None
    
    def is_positive(self, emoji: str) -> bool:
        """Check if emoji is positive."""
        defn = self._by_emoji.get(emoji)
        return defn.sentiment == Sentiment.POSITIVE if defn else False
    
    def is_negative(self, emoji: str) -> bool:
        """Check if emoji is negative."""
        defn = self._by_emoji.get(emoji)
        return defn.sentiment == Sentiment.NEGATIVE if defn else False
    
    def is_neutral(self, emoji: str) -> bool:
        """Check if emoji is neutral (or unknown)."""
        defn = self._by_emoji.get(emoji)
        return defn.sentiment == Sentiment.NEUTRAL if defn else True
    
    def list_positive(self) -> list[str]:
        """Get all positive emojis (for backward compatibility)."""
        return [d.emoji for d in self._by_sentiment[Sentiment.POSITIVE]]
    
    def list_negative(self) -> list[str]:
        """Get all negative emojis (for backward compatibility)."""
        return [d.emoji for d in self._by_sentiment[Sentiment.NEGATIVE]]
    
    def list_neutral(self) -> list[str]:
        """Get all neutral emojis."""
        return [d.emoji for d in self._by_sentiment[Sentiment.NEUTRAL]]
    
    def list_by_category(self, category: Category) -> list[str]:
        """Get all emojis in a specific category."""
        return [d.emoji for d in self._by_category[category]]
    
    def get_stats(self) -> dict:
        """Get statistics about the taxonomy."""
        return {
            "total": len(EMOJI_DEFINITIONS),
            "positive": len(self._by_sentiment[Sentiment.POSITIVE]),
            "negative": len(self._by_sentiment[Sentiment.NEGATIVE]),
            "neutral": len(self._by_sentiment[Sentiment.NEUTRAL]),
            "categories": {cat.value: len(self._by_category[cat]) for cat in Category},
        }


# Global singleton instance
emoji_taxonomy = EmojiTaxonomy()


# =============================================================================
# BACKWARD COMPATIBILITY
# These lists are provided for modules still using the old pattern.
# Prefer using emoji_taxonomy.is_positive()/is_negative() for new code.
# =============================================================================

POSITIVE_REACTIONS = emoji_taxonomy.list_positive()
NEGATIVE_REACTIONS = emoji_taxonomy.list_negative()
NEUTRAL_REACTIONS = emoji_taxonomy.list_neutral()
