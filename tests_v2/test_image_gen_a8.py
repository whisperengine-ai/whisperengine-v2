import pytest
import asyncio
from unittest.mock import MagicMock, patch
from src_v2.image_gen.session import ImageSessionManager
from src_v2.tools.image_tools import GenerateImageTool

@pytest.mark.asyncio
async def test_image_session_manager():
    # Mock Redis
    mock_redis = MagicMock()
    
    # Create a future for get()
    f_get = asyncio.Future()
    f_get.set_result(b'{"prompt": "test", "seed": 123}')
    mock_redis.get = MagicMock(return_value=f_get)
    
    # Create a future for setex()
    f_set = asyncio.Future()
    f_set.set_result(True)
    mock_redis.setex = MagicMock(return_value=f_set)
    
    # Create a future for delete()
    f_del = asyncio.Future()
    f_del.set_result(True)
    mock_redis.delete = MagicMock(return_value=f_del)
    
    with patch("redis.asyncio.from_url", return_value=mock_redis):
        manager = ImageSessionManager()
        # Inject mock redis directly to avoid async init issues in test
        manager._redis = mock_redis
        
        # Test get
        session = await manager.get_session("user1")
        assert session is not None
        assert session["prompt"] == "test"
        assert session["seed"] == 123
        
        # Test save
        await manager.save_session("user1", "new prompt", 456, {"width": 1024})
        mock_redis.setex.assert_called()

@pytest.mark.asyncio
async def test_generate_image_tool_logic():
    # Verify the tool can be instantiated and has correct name
    tool = GenerateImageTool()
    assert tool.name == "generate_image"
    assert "refine" in tool.description.lower()
