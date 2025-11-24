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
    from src_v2.agents.engine import AgentEngine
    from src_v2.core.character import Character

async def test_agent_engine():
    logger.info("Starting Agent Engine Test...")
    
    # Mock dependencies
    mock_trust = MagicMock()
    mock_feedback = MagicMock()
    mock_goal = MagicMock()
    mock_llm = AsyncMock()
    
    # Setup Engine with mocks
    engine = AgentEngine(
        trust_manager_dep=mock_trust,
        feedback_analyzer_dep=mock_feedback,
        goal_manager_dep=mock_goal,
        llm_client_dep=mock_llm
    )
    
    # Mock internal components that are instantiated in __init__
    engine.router = AsyncMock()
    engine.classifier = AsyncMock()
    engine.reflective_agent = AsyncMock()
    
    # Test Data
    character = Character(
        name="TestBot",
        system_prompt="You are a test bot."
    )
    user_id = "test_user"
    message = "Hello world"
    
    # ---------------------------------------------------------
    # 1. Test Fast Mode (Standard Flow)
    # ---------------------------------------------------------
    logger.info("Test 1: Fast Mode Generation")
    
    # Mocks for flow
    engine.classifier.classify.return_value = "SIMPLE"
    
    # Mock async methods correctly
    mock_trust.get_relationship_level = AsyncMock(return_value={"level": 1, "trust_score": 10})
    mock_feedback.get_current_mood = AsyncMock(return_value="Neutral")
    mock_feedback.analyze_user_feedback_patterns = AsyncMock(return_value={})
    mock_goal.get_active_goals = AsyncMock(return_value=[])
    
    # Mock Router response
    engine.router.route_and_retrieve = AsyncMock(return_value={"context": "Memory", "reasoning": "Reason"})
    
    # Mock LLM response
    mock_response = MagicMock()
    mock_response.content = "Hello human!"
    # ainvoke returns the message object, not just content
    mock_llm.ainvoke.return_value = mock_response
    
    # Mock Knowledge Manager (it's a global import in engine.py, so we patch it)
    with patch("src_v2.agents.engine.knowledge_manager") as mock_km:
        mock_km.find_common_ground = AsyncMock(return_value="")
        mock_km.search_bot_background = AsyncMock(return_value="")
        
        response = await engine.generate_response(character, message, user_id=user_id)
        
        # The engine returns str(response.content)
        if response == "Hello human!":
            logger.info("✅ Fast mode response passed.")
        else:
            logger.error(f"❌ Fast mode response failed. Got: {response}")
            
        # Verify Router was called
        engine.router.route_and_retrieve.assert_called()
        logger.info("✅ Router invocation passed.")

    # ---------------------------------------------------------
    # 2. Test Reflective Mode
    # ---------------------------------------------------------
    logger.info("Test 2: Reflective Mode Trigger")
    
    # Force complex classification
    engine.classifier.classify.return_value = "COMPLEX"
    
    # Mock Reflective Agent
    engine.reflective_agent.run.return_value = ("Reflective Answer", [])
    
    # Enable reflective mode in settings
    with patch("src_v2.agents.engine.settings") as mock_settings:
        mock_settings.ENABLE_REFLECTIVE_MODE = True
        mock_settings.ENABLE_PROMPT_LOGGING = False
        mock_settings.LLM_SUPPORTS_VISION = False
        mock_settings.LLM_PROVIDER = "openai"
        
        response = await engine.generate_response(character, "Complex question", user_id=user_id)
        
        if response == "Reflective Answer":
            logger.info("✅ Reflective mode response passed.")
        else:
            logger.error(f"❌ Reflective mode response failed. Got: {response}")
            
        engine.reflective_agent.run.assert_called()

    logger.info("Agent Engine Test Complete.")

if __name__ == "__main__":
    asyncio.run(test_agent_engine())
