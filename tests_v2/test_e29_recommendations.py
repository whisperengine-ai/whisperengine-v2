"""
Tests for E29: Graph-Based Recommendations

Tests the RecommendationEngine and GraphWalker integration.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass
from typing import List, Dict, Any

from src_v2.knowledge.recommendations import RecommendationEngine, SimilarUser


@pytest.mark.asyncio
class TestRecommendationEngine:
    """Test the RecommendationEngine."""
    
    @patch("src_v2.knowledge.recommendations.db_manager")
    @patch("src_v2.knowledge.recommendations.settings")
    async def test_find_similar_users_success(self, mock_settings, mock_db):
        """Test finding similar users with shared topics."""
        # Setup mocks
        mock_settings.RECOMMENDATION_MIN_SHARED_TOPICS = 2
        mock_settings.RECOMMENDATION_SERENDIPITY = 0.0
        mock_db.neo4j_driver = MagicMock()
        
        # Mock Neo4j session and result
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        
        # Mock data returned from Cypher query
        mock_records = [
            {
                "user_id": "user_456",
                "shared_count": 5,
                "topic_names": ["ocean", "fish", "coral", "diving", "blue"]
            },
            {
                "user_id": "user_789",
                "shared_count": 3,
                "topic_names": ["ocean", "fish", "sharks"]
            }
        ]
        
        mock_result.data.return_value = mock_records
        mock_session.run.return_value = mock_result
        mock_db.neo4j_driver.session.return_value.__aenter__.return_value = mock_session
        
        # Initialize engine
        engine = RecommendationEngine()
        
        # Run test
        recommendations = await engine.find_similar_users(
            user_id="user_123",
            server_id="guild_abc",
            limit=5
        )
        
        # Verify
        assert len(recommendations) == 2
        assert recommendations[0].user_id == "user_456"
        assert recommendations[0].shared_topics == 5
        assert recommendations[0].score == 5.0
        assert recommendations[0].reason == "shared_interests"
        
        assert recommendations[1].user_id == "user_789"
        assert recommendations[1].shared_topics == 3
        
        # Verify query parameters
        args, kwargs = mock_session.run.call_args
        query = args[0]
        params = args[1]
        
        assert params["user_id"] == "user_123"
        assert params["server_id"] == "guild_abc"
        assert "DISCUSSED" in query  # Should filter by server via DISCUSSED edge
    
    @patch("src_v2.knowledge.recommendations.db_manager")
    async def test_find_similar_users_no_neo4j(self, mock_db):
        """Test graceful failure when Neo4j is missing."""
        mock_db.neo4j_driver = None
        
        engine = RecommendationEngine()
        recommendations = await engine.find_similar_users("user_123")
        
        assert recommendations == []
    
    @patch("src_v2.knowledge.recommendations.db_manager")
    @patch("src_v2.knowledge.recommendations.settings")
    async def test_serendipity(self, mock_settings, mock_db):
        """Test serendipitous recommendations."""
        mock_settings.RECOMMENDATION_SERENDIPITY = 1.0  # Force serendipity
        mock_db.neo4j_driver = MagicMock()
        
        mock_session = AsyncMock()
        
        # First query (shared topics) returns empty
        mock_result1 = AsyncMock()
        mock_result1.data.return_value = []
        
        # Second query (random user) returns a user
        mock_result2 = AsyncMock()
        mock_result2.single.return_value = {"user_id": "random_user_999"}
        
        # Configure side effects for session.run
        mock_session.run.side_effect = [mock_result1, mock_result2]
        mock_db.neo4j_driver.session.return_value.__aenter__.return_value = mock_session
        
        engine = RecommendationEngine()
        
        recommendations = await engine.find_similar_users(
            user_id="user_123",
            server_id="guild_abc"
        )
        
        assert len(recommendations) == 1
        assert recommendations[0].user_id == "random_user_999"
        assert recommendations[0].reason == "serendipity"
        assert recommendations[0].shared_topics == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
