"""
Tests for E28: User-Facing Graph

Tests the /api/user-graph endpoint and Discord command.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass, field
from typing import List, Dict, Any

# Import the models
from src_v2.api.models import (
    UserGraphRequest, UserGraphResponse, 
    GraphNode, GraphEdge, GraphCluster
)


# Mock classes matching walker.py dataclasses
@dataclass
class MockWalkedNode:
    id: str
    label: str
    name: str
    properties: Dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    depth: int = 0
    is_serendipitous: bool = False


@dataclass
class MockWalkedEdge:
    source_id: str
    target_id: str
    edge_type: str
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MockThematicCluster:
    theme: str
    nodes: List[MockWalkedNode]
    central_node: MockWalkedNode = None  # type: ignore
    cohesion_score: float = 0.0


@dataclass
class MockGraphWalkResult:
    nodes: List[MockWalkedNode]
    edges: List[MockWalkedEdge]
    clusters: List[MockThematicCluster]
    interpretation: str = ""
    walk_stats: Dict[str, Any] = field(default_factory=dict)


class TestUserGraphModels:
    """Test the Pydantic models for user graph."""
    
    def test_user_graph_request_defaults(self):
        """Test default values for UserGraphRequest."""
        request = UserGraphRequest(user_id="test_user")
        assert request.user_id == "test_user"
        assert request.depth == 2
        assert request.include_other_users is False
        assert request.max_nodes == 50
    
    def test_user_graph_request_validation(self):
        """Test validation constraints."""
        # Depth too low
        with pytest.raises(ValueError):
            UserGraphRequest(user_id="test", depth=0)
        
        # Depth too high
        with pytest.raises(ValueError):
            UserGraphRequest(user_id="test", depth=5)
        
        # max_nodes too low
        with pytest.raises(ValueError):
            UserGraphRequest(user_id="test", max_nodes=5)
        
        # max_nodes too high
        with pytest.raises(ValueError):
            UserGraphRequest(user_id="test", max_nodes=200)
    
    def test_graph_node_model(self):
        """Test GraphNode model."""
        node = GraphNode(
            id="entity_ocean",
            label="Entity",
            name="ocean",
            score=0.85,
            properties={"type": "topic"}
        )
        assert node.id == "entity_ocean"
        assert node.label == "Entity"
        assert node.score == 0.85
    
    def test_graph_edge_model(self):
        """Test GraphEdge model."""
        edge = GraphEdge(
            source="user_123",
            target="entity_ocean",
            edge_type="FACT",
            properties={"predicate": "loves"}
        )
        assert edge.source == "user_123"
        assert edge.edge_type == "FACT"
    
    def test_user_graph_response(self):
        """Test full response model."""
        response = UserGraphResponse(
            success=True,
            user_id="test_user",
            bot_name="elena",
            nodes=[
                GraphNode(id="user_123", label="User", name="TestUser", score=1.0),
                GraphNode(id="entity_ocean", label="Entity", name="ocean", score=0.8)
            ],
            edges=[
                GraphEdge(source="user_123", target="entity_ocean", edge_type="FACT")
            ],
            clusters=[],
            stats={"node_count": 2, "edge_count": 1}
        )
        assert response.success is True
        assert len(response.nodes) == 2
        assert len(response.edges) == 1


@pytest.mark.asyncio
class TestUserGraphEndpoint:
    """Test the /api/user-graph endpoint."""
    
    @patch("src_v2.api.routes.db_manager")
    @patch("src_v2.api.routes.GraphWalker")
    @patch("src_v2.api.routes.settings")
    async def test_user_graph_success(self, mock_settings, mock_walker_class, mock_db):
        """Test successful graph retrieval."""
        from src_v2.api.routes import get_user_graph
        
        # Setup mocks
        mock_settings.DISCORD_BOT_NAME = "elena"
        mock_db.neo4j_driver = MagicMock()  # Neo4j available
        
        # Create mock walk result
        mock_nodes = [
            MockWalkedNode(id="user_123", label="User", name="TestUser", score=1.0),
            MockWalkedNode(id="entity_ocean", label="Entity", name="ocean", score=0.85),
            MockWalkedNode(id="entity_fish", label="Entity", name="fish", score=0.7),
        ]
        mock_edges = [
            MockWalkedEdge(source_id="user_123", target_id="entity_ocean", edge_type="FACT"),
            MockWalkedEdge(source_id="entity_ocean", target_id="entity_fish", edge_type="RELATED"),
        ]
        mock_clusters = [
            MockThematicCluster(theme="marine life", nodes=mock_nodes[1:], cohesion_score=0.8)
        ]
        
        mock_result = MockGraphWalkResult(
            nodes=mock_nodes,
            edges=mock_edges,
            clusters=mock_clusters,
            walk_stats={"depth": 2, "visited": 3}
        )
        
        # Setup walker mock
        mock_walker = AsyncMock()
        mock_walker.explore.return_value = mock_result
        mock_walker_class.return_value = mock_walker
        
        # Make request
        request = UserGraphRequest(user_id="user_123", depth=2)
        response = await get_user_graph(request)
        
        # Verify
        assert response.success is True
        assert response.user_id == "user_123"
        assert response.bot_name == "elena"
        assert len(response.nodes) == 3
        assert len(response.edges) == 2
        assert len(response.clusters) == 1
        assert response.stats["node_count"] == 3
    
    @patch("src_v2.api.routes.db_manager")
    @patch("src_v2.api.routes.settings")
    async def test_user_graph_no_neo4j(self, mock_settings, mock_db):
        """Test error when Neo4j unavailable."""
        from src_v2.api.routes import get_user_graph
        from fastapi import HTTPException
        
        mock_settings.DISCORD_BOT_NAME = "elena"
        mock_db.neo4j_driver = None  # Neo4j not available
        
        request = UserGraphRequest(user_id="user_123")
        
        with pytest.raises(HTTPException) as exc_info:
            await get_user_graph(request)
        
        assert exc_info.value.status_code == 503
        assert "Neo4j" in str(exc_info.value.detail)
    
    @patch("src_v2.api.routes.db_manager")
    @patch("src_v2.api.routes.GraphWalker")
    @patch("src_v2.api.routes.settings")
    async def test_user_graph_filters_other_users(self, mock_settings, mock_walker_class, mock_db):
        """Test that other users are filtered out by default."""
        from src_v2.api.routes import get_user_graph
        
        mock_settings.DISCORD_BOT_NAME = "elena"
        mock_db.neo4j_driver = MagicMock()
        
        # Include another user in results
        mock_nodes = [
            MockWalkedNode(id="user_123", label="User", name="TestUser", score=1.0),
            MockWalkedNode(id="user_456", label="User", name="OtherUser", score=0.5),  # Should be filtered
            MockWalkedNode(id="entity_ocean", label="Entity", name="ocean", score=0.85),
        ]
        mock_edges = [
            MockWalkedEdge(source_id="user_123", target_id="entity_ocean", edge_type="FACT"),
            MockWalkedEdge(source_id="user_456", target_id="entity_ocean", edge_type="FACT"),
        ]
        
        mock_result = MockGraphWalkResult(
            nodes=mock_nodes,
            edges=mock_edges,
            clusters=[],
            walk_stats={}
        )
        
        mock_walker = AsyncMock()
        mock_walker.explore.return_value = mock_result
        mock_walker_class.return_value = mock_walker
        
        # Request without include_other_users
        request = UserGraphRequest(user_id="user_123", include_other_users=False)
        response = await get_user_graph(request)
        
        # Should only have 2 nodes (user_123 and entity_ocean), not user_456
        assert len(response.nodes) == 2
        node_ids = {n.id for n in response.nodes}
        assert "user_123" in node_ids
        assert "entity_ocean" in node_ids
        assert "user_456" not in node_ids
        
        # Edge to user_456 should also be filtered
        assert len(response.edges) == 1
    
    @patch("src_v2.api.routes.db_manager")
    @patch("src_v2.api.routes.GraphWalker")
    @patch("src_v2.api.routes.settings")
    async def test_user_graph_includes_other_users(self, mock_settings, mock_walker_class, mock_db):
        """Test that other users are included when requested."""
        from src_v2.api.routes import get_user_graph
        
        mock_settings.DISCORD_BOT_NAME = "elena"
        mock_db.neo4j_driver = MagicMock()
        
        mock_nodes = [
            MockWalkedNode(id="user_123", label="User", name="TestUser", score=1.0),
            MockWalkedNode(id="user_456", label="User", name="OtherUser", score=0.5),
            MockWalkedNode(id="entity_ocean", label="Entity", name="ocean", score=0.85),
        ]
        mock_edges = [
            MockWalkedEdge(source_id="user_123", target_id="entity_ocean", edge_type="FACT"),
            MockWalkedEdge(source_id="user_456", target_id="entity_ocean", edge_type="FACT"),
        ]
        
        mock_result = MockGraphWalkResult(
            nodes=mock_nodes,
            edges=mock_edges,
            clusters=[],
            walk_stats={}
        )
        
        mock_walker = AsyncMock()
        mock_walker.explore.return_value = mock_result
        mock_walker_class.return_value = mock_walker
        
        # Request WITH include_other_users
        request = UserGraphRequest(user_id="user_123", include_other_users=True)
        response = await get_user_graph(request)
        
        # Should have all 3 nodes
        assert len(response.nodes) == 3
        assert len(response.edges) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
