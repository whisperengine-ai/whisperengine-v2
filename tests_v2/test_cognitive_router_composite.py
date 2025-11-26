import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src_v2.agents.router import CognitiveRouter
from langchain_core.messages import AIMessage

@pytest.mark.asyncio
async def test_router_uses_analyze_topic():
    with patch("src_v2.agents.router.create_llm") as mock_create_llm:
        # Setup mock LLM
        mock_llm = MagicMock() # Use MagicMock for the base object to handle sync methods like bind_tools
        mock_llm.ainvoke = AsyncMock() # Explicitly make ainvoke async
        
        mock_response = MagicMock()
        
        # Simulate LLM choosing analyze_topic
        mock_response.tool_calls = [{
            "name": "analyze_topic",
            "args": {"topic": "quantum physics"},
            "id": "call_123"
        }]
        mock_response.content = ""
        
        # Mock the bind_tools method to return the mock_llm (chaining)
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke.return_value = mock_response
        
        mock_create_llm.return_value = mock_llm

        # Mock the AnalyzeTopicTool execution
        with patch("src_v2.agents.router.AnalyzeTopicTool") as MockAnalyzeTool:
            mock_tool_instance = AsyncMock()
            mock_tool_instance.name = "analyze_topic"
            mock_tool_instance.ainvoke.return_value = "Composite Analysis Result"
            MockAnalyzeTool.return_value = mock_tool_instance
            
            router = CognitiveRouter()
            result = await router.route_and_retrieve("user123", "Tell me everything about quantum physics")
            
            # Verify context contains the result
            assert "Composite Analysis Result" in result["context"]
            assert "analyze_topic" in result["tool_calls"]
