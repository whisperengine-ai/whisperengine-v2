"""
Tests for E26: Temporal Graph Scoring

Tests the temporal scoring heuristics added to GraphWalker:
- Velocity boost (active relationships score higher)
- Recency decay (old edges score lower)
- Trust trajectory (rising trust boosts score)
- Edge count trends (growing relationships score higher)
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src_v2.knowledge.walker import (
    GraphWalker,
    WalkedNode,
    WalkedEdge,
)


class TestTemporalScoring:
    """Tests for _score_temporal() method."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.walker = GraphWalker()
    
    def test_base_score_without_temporal_data(self):
        """No temporal data should return score of 1.0."""
        node = WalkedNode(id="test", label="Entity", name="test")
        score = self.walker._score_temporal(node)
        assert score == 1.0
    
    def test_velocity_boost_active_relationship(self):
        """High activity rate should boost score."""
        node = WalkedNode(id="test", label="Entity", name="test")
        
        # Edge with 30 interactions over 10 days = 3/day velocity
        edge = WalkedEdge(
            source_id="source",
            target_id="test",
            edge_type="DISCUSSED",
            count=30,
            created_at=datetime.now(timezone.utc) - timedelta(days=10)
        )
        
        score = self.walker._score_temporal(node, edge=edge)
        assert score > 1.0, "Active relationships should get velocity boost"
    
    def test_velocity_capped_at_2x(self):
        """Velocity boost should not exceed 2.0x."""
        node = WalkedNode(id="test", label="Entity", name="test")
        
        # Edge with 1000 interactions over 1 day = very high velocity
        edge = WalkedEdge(
            source_id="source",
            target_id="test",
            edge_type="DISCUSSED",
            count=1000,
            created_at=datetime.now(timezone.utc) - timedelta(days=1)
        )
        
        score = self.walker._score_temporal(node, edge=edge)
        assert score <= 2.0, "Velocity boost should be capped at 2.0"
    
    def test_recency_decay_old_edge(self):
        """Old edges should score lower due to recency decay."""
        node = WalkedNode(id="test", label="Entity", name="test")
        
        # Edge last updated 60 days ago
        edge_old = WalkedEdge(
            source_id="source",
            target_id="test",
            edge_type="DISCUSSED",
            updated_at=datetime.now(timezone.utc) - timedelta(days=60)
        )
        
        # Edge last updated today
        edge_new = WalkedEdge(
            source_id="source",
            target_id="test",
            edge_type="DISCUSSED",
            updated_at=datetime.now(timezone.utc)
        )
        
        score_old = self.walker._score_temporal(node, edge=edge_old)
        score_new = self.walker._score_temporal(node, edge=edge_new)
        
        assert score_old < score_new, "Old edges should score lower than new ones"
    
    def test_recency_decay_minimum(self):
        """Recency decay should not go below 0.3x."""
        node = WalkedNode(id="test", label="Entity", name="test")
        
        # Edge last updated 120 days ago (way past 60-day decay window)
        edge = WalkedEdge(
            source_id="source",
            target_id="test",
            edge_type="DISCUSSED",
            updated_at=datetime.now(timezone.utc) - timedelta(days=120)
        )
        
        score = self.walker._score_temporal(node, edge=edge)
        assert score >= 0.3, "Recency decay should not go below 0.3"
    
    def test_trust_trajectory_rising(self):
        """Rising trust should boost score."""
        node = WalkedNode(id="user123", label="User", name="test_user")
        
        # Trust trajectory with older low values and recent high values
        # Need > 5 elements so there's an "older" set to compare against
        trajectory = [10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0, 55.0]
        
        score = self.walker._score_temporal(node, trust_trajectory=trajectory)
        assert score > 1.0, f"Rising trust should boost score, got {score}"
    
    def test_trust_trajectory_falling(self):
        """Falling trust should reduce score."""
        node = WalkedNode(id="user123", label="User", name="test_user")
        
        # Trust trajectory with older high values and recent low values
        trajectory = [55.0, 50.0, 45.0, 40.0, 35.0, 30.0, 25.0, 20.0, 15.0, 10.0]
        
        score = self.walker._score_temporal(node, trust_trajectory=trajectory)
        assert score < 1.0, f"Falling trust should reduce score, got {score}"
    
    def test_trust_trajectory_stable(self):
        """Stable trust should not change score much."""
        node = WalkedNode(id="user123", label="User", name="test_user")
        
        # Trust trajectory: all same value (stable)
        trajectory = [30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0]
        
        score = self.walker._score_temporal(node, trust_trajectory=trajectory)
        assert 0.95 <= score <= 1.05, f"Stable trust should keep score near 1.0, got {score}"
    
    def test_trust_trajectory_too_short(self):
        """Short trust trajectory should not affect score."""
        node = WalkedNode(id="user123", label="User", name="test_user")
        
        # Only 3 data points (need 5 minimum to activate)
        trajectory = [10.0, 20.0, 30.0]
        
        score = self.walker._score_temporal(node, trust_trajectory=trajectory)
        assert score == 1.0, "Short trajectory should not affect score"
    
    def test_edge_count_trend_growing(self):
        """Growing edge activity should boost score."""
        node = WalkedNode(id="test", label="Topic", name="test_topic")
        
        # 20 interactions in last 30d, 10 in 30-60d period (growing)
        edge = WalkedEdge(
            source_id="source",
            target_id="test",
            edge_type="DISCUSSED",
            properties={
                "count_30d": 20,
                "count_60d": 30  # Total 60d = 30, so older period = 10
            }
        )
        
        score = self.walker._score_temporal(node, edge=edge)
        assert score > 1.0, "Growing activity should boost score"
    
    def test_edge_count_trend_declining(self):
        """Declining edge activity should reduce score."""
        node = WalkedNode(id="test", label="Topic", name="test_topic")
        
        # 5 interactions in last 30d, 20 in 30-60d period (declining)
        edge = WalkedEdge(
            source_id="source",
            target_id="test",
            edge_type="DISCUSSED",
            properties={
                "count_30d": 5,
                "count_60d": 25  # Total 60d = 25, so older period = 20
            }
        )
        
        score = self.walker._score_temporal(node, edge=edge)
        assert score < 1.0, "Declining activity should reduce score"
    
    def test_combined_temporal_factors(self):
        """Multiple temporal factors should combine properly."""
        node = WalkedNode(id="test", label="Entity", name="test")
        
        # Active, recent edge
        edge = WalkedEdge(
            source_id="source",
            target_id="test",
            edge_type="DISCUSSED",
            count=20,
            created_at=datetime.now(timezone.utc) - timedelta(days=5),
            updated_at=datetime.now(timezone.utc)
        )
        
        score = self.walker._score_temporal(node, edge=edge)
        
        # Should get both velocity boost and no recency penalty
        assert score > 1.0, "Active recent edge should score well"


class TestDatetimeParsing:
    """Tests for _parse_datetime() helper."""
    
    def setup_method(self):
        self.walker = GraphWalker()
    
    def test_parse_none(self):
        """None should return None."""
        assert self.walker._parse_datetime(None) is None
    
    def test_parse_datetime_object(self):
        """Datetime objects should pass through."""
        dt = datetime(2025, 1, 1, 12, 0, 0)
        result = self.walker._parse_datetime(dt)
        assert result == dt
    
    def test_parse_iso_string(self):
        """ISO format strings should parse correctly."""
        result = self.walker._parse_datetime("2025-01-01T12:00:00")
        assert result is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 1
    
    def test_parse_iso_string_with_z(self):
        """ISO format strings with Z suffix should parse."""
        result = self.walker._parse_datetime("2025-01-01T12:00:00Z")
        assert result is not None
        assert result.year == 2025
    
    def test_parse_invalid_string(self):
        """Invalid strings should return None."""
        assert self.walker._parse_datetime("not-a-date") is None
    
    def test_parse_neo4j_datetime(self):
        """Neo4j datetime objects with to_native() should work."""
        mock_neo4j_dt = MagicMock()
        mock_neo4j_dt.to_native.return_value = datetime(2025, 1, 1)
        
        result = self.walker._parse_datetime(mock_neo4j_dt)
        assert result == datetime(2025, 1, 1)


class TestTrustTrajectoryQuery:
    """Tests for get_trust_trajectory() method."""
    
    def setup_method(self):
        self.walker = GraphWalker()
    
    @pytest.mark.asyncio
    async def test_returns_empty_without_influxdb(self):
        """Should return empty list when InfluxDB is unavailable."""
        with patch('src_v2.knowledge.walker.db_manager') as mock_db:
            mock_db.influxdb_client = None
            
            result = await self.walker.get_trust_trajectory("user123", "elena")
            assert result == []
    
    @pytest.mark.asyncio
    async def test_returns_cached_value(self):
        """Should return cached value if available."""
        with patch('src_v2.knowledge.walker.db_manager') as mock_db, \
             patch('src_v2.knowledge.walker.cache_manager') as mock_cache:
            # InfluxDB is available
            mock_db.influxdb_client = MagicMock()
            # Cache returns the value
            mock_cache.get = AsyncMock(return_value=[10.0, 20.0, 30.0])
            
            result = await self.walker.get_trust_trajectory("user123", "elena")
            assert result == [10.0, 20.0, 30.0]
    
    @pytest.mark.asyncio
    async def test_queries_influxdb(self):
        """Should query InfluxDB for trust history."""
        with patch('src_v2.knowledge.walker.db_manager') as mock_db, \
             patch('src_v2.knowledge.walker.cache_manager') as mock_cache:
            
            # Set up mocks
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()
            
            # Mock InfluxDB client
            mock_client = MagicMock()
            mock_query_api = MagicMock()
            mock_client.query_api.return_value = mock_query_api
            
            # Mock query result
            mock_record = MagicMock()
            mock_record.get_value.return_value = 42.0
            mock_table = MagicMock()
            mock_table.records = [mock_record]
            mock_query_api.query.return_value = [mock_table]
            
            mock_db.influxdb_client = mock_client
            
            result = await self.walker.get_trust_trajectory("user123", "elena")
            
            # Should have queried InfluxDB
            mock_query_api.query.assert_called_once()
            
            # Should return the score
            assert result == [42.0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
