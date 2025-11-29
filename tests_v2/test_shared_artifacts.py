import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from src_v2.memory.shared_artifacts import SharedArtifactManager
from src_v2.config.settings import settings

@pytest.mark.asyncio
async def test_shared_artifact_manager():
    # Mock dependencies
    db_manager_mock = MagicMock()
    db_manager_mock.qdrant_client = AsyncMock()
    
    # Patch the global db_manager in the module
    import src_v2.memory.shared_artifacts
    src_v2.memory.shared_artifacts.db_manager = db_manager_mock
    
    manager = SharedArtifactManager()
    manager.embedding_service = MagicMock()
    manager.embedding_service.embed_query_async = AsyncMock(return_value=[0.1] * 384)
    
    # Test store_artifact
    point_id = await manager.store_artifact(
        artifact_type="epiphany",
        content="Test content",
        source_bot="elena",
        user_id="user123"
    )
    
    assert point_id is not None
    assert db_manager_mock.qdrant_client.upsert.called
    
    # Test discover_artifacts
    # Mock query response
    mock_point = MagicMock()
    mock_point.id = "test_id"
    mock_point.score = 0.9
    mock_point.payload = {
        "type": "epiphany",
        "content": "Test content",
        "source_bot": "elena",
        "user_id": "user123"
    }
    
    mock_result = MagicMock()
    mock_result.points = [mock_point]
    db_manager_mock.qdrant_client.query_points.return_value = mock_result
    
    results = await manager.discover_artifacts(
        query="test",
        artifact_types=["epiphany"],
        exclude_bot="dotty"
    )
    
    assert len(results) == 1
    assert results[0]["content"] == "Test content"
    assert db_manager_mock.qdrant_client.query_points.called

if __name__ == "__main__":
    asyncio.run(test_shared_artifact_manager())
