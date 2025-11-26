"""
Tests for the Insight Agent and related components.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_task_queue_enqueue():
    """Test that task queue can enqueue insight analysis jobs."""
    with patch("src_v2.workers.task_queue.create_pool") as mock_create_pool:
        # Setup mock pool
        mock_pool = AsyncMock()
        mock_job = MagicMock()
        mock_job.job_id = "test_job_123"
        mock_pool.enqueue_job.return_value = mock_job
        mock_create_pool.return_value = mock_pool
        
        from src_v2.workers.task_queue import TaskQueue
        
        queue = TaskQueue()
        queue._pool = mock_pool
        
        job_id = await queue.enqueue_insight_analysis(
            user_id="user123",
            character_name="elena",
            trigger="feedback",
            priority=3
        )
        
        assert job_id == "test_job_123"
        mock_pool.enqueue_job.assert_called_once()


@pytest.mark.asyncio
async def test_insight_tools_creation():
    """Test that insight tools can be created."""
    from src_v2.tools.insight_tools import get_insight_tools
    
    tools = get_insight_tools(user_id="user123", character_name="elena")
    
    assert len(tools) == 5
    tool_names = [t.name for t in tools]
    assert "analyze_conversation_patterns" in tool_names
    assert "detect_recurring_themes" in tool_names
    assert "generate_epiphany" in tool_names
    assert "store_reasoning_trace" in tool_names
    assert "learn_response_pattern" in tool_names


@pytest.mark.asyncio
async def test_insight_agent_prompt_construction():
    """Test that insight agent constructs proper prompts."""
    from src_v2.agents.insight_agent import InsightAgent
    
    agent = InsightAgent()
    
    prompt = agent._construct_prompt("elena", "feedback")
    
    assert "elena" in prompt
    assert "feedback" in prompt
    assert "epiphany" in prompt.lower() or "epiphanies" in prompt.lower()
    assert "pattern" in prompt.lower()
