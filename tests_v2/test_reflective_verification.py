import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock, patch
from loguru import logger
from langchain_core.messages import AIMessage, SystemMessage

# Add project root to path
sys.path.append(os.getcwd())

# Mock settings
with patch.dict(os.environ, {
    "DISCORD_TOKEN": "mock_token",
    "DISCORD_BOT_NAME": "testbot",
    "LLM_API_KEY": "mock_key",
    "NEO4J_PASSWORD": "mock_pass",
    "INFLUXDB_TOKEN": "mock_token"
}):
    from src_v2.agents.reflective import ReflectiveAgent

async def test_verification_logic():
    logger.info("Starting Reflective Verification Test...")
    
    # Mock LLM
    mock_llm = AsyncMock()
    
    # bind_tools should be a standard MagicMock, not AsyncMock, because it's not awaited
    mock_llm.bind_tools = MagicMock(return_value=mock_llm)
    
    # Sequence of responses:
    # 1. Proposed Answer
    # 2. "VERIFIED" (after critic prompt)
    
    response1 = AIMessage(content="The answer is 42.")
    response1.tool_calls = []
    
    response2 = AIMessage(content="VERIFIED")
    response2.tool_calls = []
    
    mock_llm.ainvoke.side_effect = [response1, response2]
    
    # Initialize Agent
    agent = ReflectiveAgent()
    agent.llm = mock_llm # Inject mock
    
    # Run with verification enabled
    final_response, history = await agent.run(
        user_input="What is the meaning of life?",
        user_id="test_user",
        system_prompt="You are a bot.",
        enable_verification=True
    )
    
    # Checks
    logger.info(f"Final Response: {final_response}")
    
    # 1. Check if final response is the original answer (not "VERIFIED")
    if final_response == "The answer is 42.":
        logger.info("✅ Correctly returned the verified answer.")
    else:
        logger.error(f"❌ Failed. Expected 'The answer is 42.', got '{final_response}'")
        
    # 2. Check history for Critic Prompt
    critic_found = False
    for msg in history:
        if isinstance(msg, SystemMessage) and "CRITIC STEP" in str(msg.content):
            critic_found = True
            break
            
    if critic_found:
        logger.info("✅ Critic prompt found in history.")
    else:
        logger.error("❌ Critic prompt NOT found in history.")

if __name__ == "__main__":
    asyncio.run(test_verification_logic())
