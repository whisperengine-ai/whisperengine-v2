import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src_v2.agents.classifier import ComplexityClassifier
from src_v2.tools.insight_tools import StoreReasoningTraceTool

@pytest.mark.asyncio
async def test_store_reasoning_trace_complexity():
    """Test that StoreReasoningTraceTool stores complexity in metadata."""
    tool = StoreReasoningTraceTool(user_id="test_user", character_name="test_bot")
    
    with patch("src_v2.tools.insight_tools.memory_manager") as mock_memory:
        mock_memory._save_vector_memory = AsyncMock()
        
        await tool._arun(
            query_pattern="test pattern",
            successful_approach="test approach",
            tools_used="tool1,tool2",
            complexity="COMPLEX_HIGH"
        )
        
        # Verify call arguments
        mock_memory._save_vector_memory.assert_called_once()
        call_kwargs = mock_memory._save_vector_memory.call_args.kwargs
        
        assert call_kwargs["user_id"] == "test_user"
        assert call_kwargs["role"] == "reasoning_trace"
        assert "Complexity: COMPLEX_HIGH" in call_kwargs["content"]
        assert call_kwargs["metadata"]["complexity"] == "COMPLEX_HIGH"

@pytest.mark.asyncio
async def test_adaptive_depth_override():
    """Test that ComplexityClassifier overrides based on reasoning traces."""
    
    # Mock LLM
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "SIMPLE"
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    
    with patch("src_v2.agents.classifier.create_llm", return_value=mock_llm):
        classifier = ComplexityClassifier()
        
        with patch("src_v2.agents.classifier.memory_manager") as mock_memory:
            # Case 1: No traces found -> Returns LLM result (SIMPLE)
            mock_memory.search_reasoning_traces = AsyncMock(return_value=[])
            
            result = await classifier.classify("test query", user_id="test_user", bot_name="test_bot")
            assert result == "SIMPLE"
            
            # Case 2: Trace found with high score -> Returns trace complexity (COMPLEX_HIGH)
            mock_memory.search_reasoning_traces = AsyncMock(return_value=[
                {
                    "content": "...",
                    "score": 0.9,
                    "metadata": {"complexity": "COMPLEX_HIGH"}
                }
            ])
            
            result = await classifier.classify("test query", user_id="test_user", bot_name="test_bot")
            assert result == "COMPLEX_HIGH"
            
            # Case 3: Trace found but low score -> Returns LLM result (SIMPLE)
            mock_memory.search_reasoning_traces = AsyncMock(return_value=[
                {
                    "content": "...",
                    "score": 0.5,
                    "metadata": {"complexity": "COMPLEX_HIGH"}
                }
            ])
            
            result = await classifier.classify("test query", user_id="test_user", bot_name="test_bot")
            assert result == "SIMPLE"
