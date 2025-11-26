import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src_v2.agents.composite_tools import AnalyzeTopicTool

@pytest.mark.asyncio
async def test_analyze_topic_tool():
    user_id = "test_user"
    bot_name = "test_bot"
    topic = "quantum physics"

    # Mock the sub-tools
    with patch("src_v2.agents.composite_tools.SearchSummariesTool") as MockSummaries, \
         patch("src_v2.agents.composite_tools.SearchEpisodesTool") as MockEpisodes, \
         patch("src_v2.agents.composite_tools.LookupFactsTool") as MockFacts:
        
        # Setup mock instances
        mock_summaries_instance = AsyncMock()
        mock_summaries_instance.ainvoke.return_value = "Summary about quantum physics"
        MockSummaries.return_value = mock_summaries_instance

        mock_episodes_instance = AsyncMock()
        mock_episodes_instance.ainvoke.return_value = "Episode about quantum physics"
        MockEpisodes.return_value = mock_episodes_instance

        mock_facts_instance = AsyncMock()
        mock_facts_instance.ainvoke.return_value = "Fact about quantum physics"
        MockFacts.return_value = mock_facts_instance

        # Instantiate the composite tool
        tool = AnalyzeTopicTool(user_id=user_id, bot_name=bot_name)
        
        # Run the tool
        result = await tool._arun(topic)
        
        # Verify sub-tools were called correctly
        mock_summaries_instance.ainvoke.assert_called_once_with({"query": topic})
        mock_episodes_instance.ainvoke.assert_called_once_with({"query": topic})
        mock_facts_instance.ainvoke.assert_called_once_with({"query": topic})
        
        # Verify result format
        assert "[ANALYSIS FOR: quantum physics]" in result
        assert "--- SUMMARIES ---" in result
        assert "Summary about quantum physics" in result
        assert "--- EPISODES ---" in result
        assert "Episode about quantum physics" in result
        assert "--- FACTS ---" in result
        assert "Fact about quantum physics" in result
