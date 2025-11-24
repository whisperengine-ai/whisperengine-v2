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
    from src_v2.evolution.goals import GoalManager

async def test_goal_manager():
    logger.info("Starting Goal Manager Test...")
    
    with patch("src_v2.evolution.goals.db_manager") as mock_db:
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_db.postgres_pool = mock_pool
        
        manager = GoalManager()
        user_id = "test_user"
        char_name = "test_char"

        # ---------------------------------------------------------
        # 1. Test ensure_goals_exist
        # ---------------------------------------------------------
        logger.info("Test 1: Ensure Goals Exist")
        # Mock fetchval returning None (goal doesn't exist)
        mock_conn.fetchval.return_value = None
        
        # Mock file loading to return default goals
        with patch.object(manager, '_load_character_goals_from_file', return_value=manager.default_goals):
            await manager.ensure_goals_exist(char_name)
            
            # Should insert default goals
            mock_conn.execute.assert_called()
            logger.info("✅ Goal creation query passed.")

        # ---------------------------------------------------------
        # 2. Test get_active_goals
        # ---------------------------------------------------------
        logger.info("Test 2: Get Active Goals")
        # Mock fetch returning rows
        mock_conn.fetch.return_value = [
            {
                "id": 1, "slug": "learn_name", "description": "Learn name", 
                "success_criteria": "...", "priority": 10, 
                "status": "not_started", "progress": 0.0
            }
        ]
        
        goals = await manager.get_active_goals(user_id, char_name)
        
        if len(goals) == 1 and goals[0]["slug"] == "learn_name":
            logger.info("✅ Active goals retrieval passed.")
        else:
            logger.error(f"❌ Active goals retrieval failed. Got: {goals}")

        # ---------------------------------------------------------
        # 3. Test update_goal_progress
        # ---------------------------------------------------------
        logger.info("Test 3: Update Goal Progress")
        # Mock fetchval returning goal_id
        mock_conn.fetchval.return_value = 123
        
        await manager.update_goal_progress(user_id, "learn_name", char_name, "in_progress", 0.5)
        
        args = mock_conn.execute.call_args[0]
        if "INSERT INTO v2_user_goal_progress" in args[0]:
            logger.info("✅ Update progress query passed.")
        else:
            logger.error("❌ Update progress query failed.")

    logger.info("Goal Manager Test Complete.")

if __name__ == "__main__":
    asyncio.run(test_goal_manager())
