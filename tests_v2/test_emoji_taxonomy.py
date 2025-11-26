import pytest
from src_v2.evolution.emoji_taxonomy import emoji_taxonomy, Sentiment, Category

def test_emoji_taxonomy_stats():
    stats = emoji_taxonomy.get_stats()
    assert stats['total'] > 0
    assert stats['positive'] > 0
    assert stats['negative'] > 0
    assert stats['neutral'] > 0

def test_positive_emojis():
    assert emoji_taxonomy.is_positive("👍")
    assert emoji_taxonomy.is_positive("❤️")
    assert emoji_taxonomy.is_positive("😂")
    assert emoji_taxonomy.is_positive("🔥")
    assert emoji_taxonomy.get_score("❤️") > 1.0  # Weighted score check

def test_negative_emojis():
    assert emoji_taxonomy.is_negative("👎")
    assert emoji_taxonomy.is_negative("😠")
    assert emoji_taxonomy.is_negative("💔")
    assert emoji_taxonomy.get_score("🖕") < -1.0  # Weighted score check

def test_neutral_emojis():
    assert emoji_taxonomy.is_neutral("🤔")
    assert emoji_taxonomy.is_neutral("🤷")
    assert emoji_taxonomy.is_neutral("unknown_emoji")  # Unknown should be neutral

def test_categories():
    assert emoji_taxonomy.get_category("😂") == Category.LAUGHTER
    assert emoji_taxonomy.get_category("❤️") == Category.LOVE
    assert emoji_taxonomy.get_category("👎") == Category.DISAPPROVAL

def test_backward_compatibility():
    # Check that lists are populated
    assert "👍" in emoji_taxonomy.list_positive()
    assert "👎" in emoji_taxonomy.list_negative()
    
    # Check simple scores
    assert emoji_taxonomy.get_simple_score("👍") == 1
    assert emoji_taxonomy.get_simple_score("👎") == -1
    assert emoji_taxonomy.get_simple_score("🤔") == 0
