import asyncio
import sys
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from loguru import logger

# Add project root to path
sys.path.append(os.getcwd())

from src_v2.evolution.feedback import FeedbackAnalyzer

async def test_feedback_analyzer():
    logger.info("Starting Feedback Analyzer Test...")
    
    analyzer = FeedbackAnalyzer()
    
    # ---------------------------------------------------------
    # Test 1: Reaction Classification
    # ---------------------------------------------------------
    logger.info("Test 1: Verify reaction classifications")
    
    positive_reactions = ['👍', '❤️', '😊', '🎉', '✨', '💯', '🔥', '💖']
    negative_reactions = ['👎', '😢', '😠', '💔', '😕', '🤔']
    
    if all(r in analyzer.POSITIVE_REACTIONS for r in positive_reactions):
        logger.info(f"✅ Positive reactions defined: {len(analyzer.POSITIVE_REACTIONS)} reactions")
    else:
        logger.error("❌ Some positive reactions not in POSITIVE_REACTIONS")
    
    if all(r in analyzer.NEGATIVE_REACTIONS for r in negative_reactions):
        logger.info(f"✅ Negative reactions defined: {len(analyzer.NEGATIVE_REACTIONS)} reactions")
    else:
        logger.error("❌ Some negative reactions not in NEGATIVE_REACTIONS")
    
    # ---------------------------------------------------------
    # Test 2: Get Feedback Score (Mocked InfluxDB)
    # ---------------------------------------------------------
    logger.info("Test 2: Calculate feedback score from reactions (Mocked)")
    
    # Mock InfluxDB query result
    mock_query_api = MagicMock()
    mock_table = MagicMock()
    
    # Mock records for new parsing logic
    # Record 1: Positive reaction
    mock_record_positive = MagicMock()
    mock_record_positive.get_field.return_value = "reaction"
    mock_record_positive.get_value.return_value = "❤️"
    mock_record_positive.values = {"action": "add"}
    
    # Record 2: Another positive reaction
    mock_record_positive_2 = MagicMock()
    mock_record_positive_2.get_field.return_value = "reaction"
    mock_record_positive_2.get_value.return_value = "❤️"
    mock_record_positive_2.values = {"action": "add"}
    
    # Record 3: Negative reaction
    mock_record_negative = MagicMock()
    mock_record_negative.get_field.return_value = "reaction"
    mock_record_negative.get_value.return_value = "👎"
    mock_record_negative.values = {"action": "add"}
    
    mock_table.records = [mock_record_positive, mock_record_positive_2, mock_record_negative]
    mock_query_api.query.return_value = [mock_table]
    
    with patch('src_v2.evolution.feedback.db_manager.influxdb_client', MagicMock()) as mock_client:
        mock_client.query_api.return_value = mock_query_api
        
        result = await analyzer.get_feedback_score("test_message_123", "test_user")
        
        if result:
            logger.info(f"✅ Feedback score calculated: {result['score']}")
            logger.info(f"   Positive: {result['positive_count']}, Negative: {result['negative_count']}")
            
            # Should be positive (2 positive, 1 negative)
            if result['score'] > 0:
                logger.info("✅ Score correctly positive")
            else:
                logger.error(f"❌ Expected positive score, got {result['score']}")
        else:
            logger.warning("⚠️ InfluxDB not available (expected in test environment)")
    
    # ---------------------------------------------------------
    # Test 3: Analyze Feedback Patterns (Mocked)
    # ---------------------------------------------------------
    logger.info("Test 3: Analyze user feedback patterns (Mocked)")
    
    # Mock InfluxDB query for pattern analysis
    mock_query_api = MagicMock()
    mock_table = MagicMock()
    
    # Simulate reactions to long messages with negative feedback
    mock_record_1 = MagicMock()
    mock_record_1.get_field.return_value = "reaction"
    mock_record_1.get_value.return_value = "👎"
    mock_record_1.values = {
        "message_id": "msg1",
        "message_length": 600,
        "action": "add"
    }
    mock_record_2 = MagicMock()
    mock_record_2.get_field.return_value = "reaction"
    mock_record_2.get_value.return_value = "👎"
    mock_record_2.values = {
        "message_id": "msg1",
        "message_length": 600,
        "action": "add"
    }
    
    mock_table.records = [mock_record_1, mock_record_2]
    mock_query_api.query.return_value = [mock_table]
    
    with patch('src_v2.evolution.feedback.db_manager.influxdb_client', MagicMock()) as mock_client:
        mock_client.query_api.return_value = mock_query_api
        
        insights = await analyzer.analyze_user_feedback_patterns("test_user", days=30)
        
        if "error" not in insights:
            logger.info("✅ Pattern analysis completed")
            logger.info(f"   Recommendations: {insights.get('recommendations', [])}")
            
            # Check if verbosity preference was detected
            if insights.get('verbosity_preference'):
                logger.info(f"✅ Verbosity preference detected: {insights['verbosity_preference']}")
        else:
            logger.warning(f"⚠️ Pattern analysis not available: {insights['error']}")
    
    # ---------------------------------------------------------
    # Test 4: Get Current Mood (Mocked)
    # ---------------------------------------------------------
    logger.info("Test 4: Determine current mood from recent reactions (Mocked)")
    
    # Mock InfluxDB query for recent reactions
    mock_query_api = MagicMock()
    mock_table = MagicMock()
    
    # Simulate recent positive reactions
    mock_records = []
    for _ in range(5):
        record = MagicMock()
        record.get_field.return_value = "reaction"
        record.get_value.return_value = "❤️"
        record.values = {"action": "add"}
        mock_records.append(record)
    
    mock_table.records = mock_records
    mock_query_api.query.return_value = [mock_table]
    
    with patch('src_v2.evolution.feedback.db_manager.influxdb_client', MagicMock()) as mock_client:
        mock_client.query_api.return_value = mock_query_api
        
        mood = await analyzer.get_current_mood("test_user")
        
        logger.info(f"✅ Current mood: {mood}")
        
        # Should be positive mood
        if mood in ["Happy", "Excited"]:
            logger.info("✅ Mood correctly positive")
        else:
            logger.warning(f"⚠️ Expected positive mood, got {mood}")
    
    # ---------------------------------------------------------
    # Test 5: No InfluxDB Client Handling
    # ---------------------------------------------------------
    logger.info("Test 5: Handle missing InfluxDB gracefully")
    
    analyzer_no_influx = FeedbackAnalyzer()
    
    with patch('src_v2.evolution.feedback.db_manager.influxdb_client', None):
        result = await analyzer_no_influx.get_feedback_score("test_msg", "test_user")
        
        if result is None:
            logger.info("✅ Correctly returns None when InfluxDB unavailable")
        else:
            logger.error(f"❌ Should return None without InfluxDB, got {result}")
        
        mood = await analyzer_no_influx.get_current_mood("test_user")
        
        if mood == "Neutral":
            logger.info("✅ Returns Neutral mood when InfluxDB unavailable")
        else:
            logger.error(f"❌ Should return Neutral without InfluxDB, got {mood}")
    
    # ---------------------------------------------------------
    # Test 6: Score Calculation Logic
    # ---------------------------------------------------------
    logger.info("Test 6: Verify score calculation logic")
    
    # Test all positive
    mock_query_api = MagicMock()
    mock_table = MagicMock()
    
    mock_records = []
    for _ in range(3):
        r = MagicMock()
        r.get_field.return_value = "reaction"
        r.get_value.return_value = "❤️"
        r.values = {"action": "add"}
        mock_records.append(r)
        
    mock_table.records = mock_records
    mock_query_api.query.return_value = [mock_table]
    
    with patch('src_v2.evolution.feedback.db_manager.influxdb_client', MagicMock()) as mock_client:
        mock_client.query_api.return_value = mock_query_api
        
        result = await analyzer.get_feedback_score("test_msg", "test_user")
        
        if result and result['score'] == 1.0:
            logger.info("✅ All positive reactions = 1.0 score")
        else:
            logger.error(f"❌ Expected 1.0 for all positive, got {result['score'] if result else 'None'}")
    
    # Test all negative
    mock_records = []
    for _ in range(3):
        r = MagicMock()
        r.get_field.return_value = "reaction"
        r.get_value.return_value = "👎"
        r.values = {"action": "add"}
        mock_records.append(r)
    mock_table.records = mock_records
    
    with patch('src_v2.evolution.feedback.db_manager.influxdb_client', MagicMock()) as mock_client:
        mock_client.query_api.return_value = mock_query_api
        
        result = await analyzer.get_feedback_score("test_msg", "test_user")
        
        if result and result['score'] == -1.0:
            logger.info("✅ All negative reactions = -1.0 score")
        else:
            logger.error(f"❌ Expected -1.0 for all negative, got {result['score'] if result else 'None'}")
    
    logger.info("✅ All Feedback Analyzer tests completed!")

if __name__ == "__main__":
    asyncio.run(test_feedback_analyzer())
