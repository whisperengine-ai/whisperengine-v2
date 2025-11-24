import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock, patch
from loguru import logger

# Add project root to path
sys.path.append(os.getcwd())

# Mock settings before importing modules that use it
with patch.dict(os.environ, {
    "DISCORD_TOKEN": "mock_token",
    "DISCORD_BOT_NAME": "testbot",
    "LLM_API_KEY": "mock_key",
    "NEO4J_PASSWORD": "mock_pass",
    "INFLUXDB_TOKEN": "mock_token"
}):
    from src_v2.agents.router import CognitiveRouter
    from langchain_core.messages import HumanMessage

async def test_cognitive_router():
    logger.info("Starting Cognitive Router Test...")
    
    # Mock create_llm to return a mock LLM
    with patch("src_v2.agents.router.create_llm") as mock_create_llm:
        mock_llm = MagicMock()
        mock_create_llm.return_value = mock_llm
        
        # Mock bind_tools
        mock_llm_with_tools = AsyncMock()
        mock_llm.bind_tools.return_value = mock_llm_with_tools
        
        router = CognitiveRouter()
        user_id = "test_user"
        
        # ---------------------------------------------------------
        # 1. Test Route with Tools (Memory Needed)
        # ---------------------------------------------------------
        logger.info("Test 1: Route with Tools")
        
        # Mock LLM response with tool calls
        mock_response = MagicMock()
        mock_response.tool_calls = [
            {"name": "search_archived_summaries", "args": {"query": "last week"}}
        ]
        mock_llm_with_tools.ainvoke.return_value = mock_response
        
        # Mock the tool execution itself
        # We need to patch the SearchSummariesTool class inside router.py or mock the instance list
        # Since router instantiates tools inside the method, we patch the class
        with patch("src_v2.agents.router.SearchSummariesTool") as MockTool:
            mock_tool_instance = AsyncMock()
            mock_tool_instance.name = "search_archived_summaries"
            mock_tool_instance.ainvoke.return_value = "Found summary: We talked about movies."
            MockTool.return_value = mock_tool_instance
            
            # We also need to patch other tools to avoid instantiation errors if they have deps
            with patch("src_v2.agents.router.SearchEpisodesTool"), \
                 patch("src_v2.agents.router.LookupFactsTool"), \
                 patch("src_v2.agents.router.UpdateFactsTool"), \
                 patch("src_v2.agents.router.UpdatePreferencesTool"):
                
                result = await router.route_and_retrieve(user_id, "What did we talk about last week?")
                
                if "Found summary" in result["context"]:
                    logger.info("✅ Tool execution and context retrieval passed.")
                else:
                    logger.error(f"❌ Tool execution failed. Got: {result}")
                
                if "search_archived_summaries" in result["tool_calls"]:
                    logger.info("✅ Tool call tracking passed.")
                else:
                    logger.error("❌ Tool call tracking failed.")

        # ---------------------------------------------------------
        # 2. Test Route without Tools (Small Talk)
        # ---------------------------------------------------------
        logger.info("Test 2: Route without Tools")
        
        mock_response.tool_calls = []
        mock_llm_with_tools.ainvoke.return_value = mock_response
        
        result = await router.route_and_retrieve(user_id, "Hi there!")
        
        if result["context"] == "" and not result["tool_calls"]:
            logger.info("✅ No-tool routing passed.")
        else:
            logger.error(f"❌ No-tool routing failed. Got: {result}")

    logger.info("Cognitive Router Test Complete.")

if __name__ == "__main__":
    asyncio.run(test_cognitive_router())
