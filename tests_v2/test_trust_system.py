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
    from src_v2.evolution.trust import TrustManager

async def test_trust_manager():
    logger.info("Starting Trust Manager Test...")
    
    # Mock the database manager
    with patch("src_v2.evolution.trust.db_manager") as mock_db:
        # Setup mock connection pool
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_db.postgres_pool = mock_pool
        
        manager = TrustManager()
        user_id = "test_user"
        char_name = "test_char"

        # ---------------------------------------------------------
        # 1. Test get_relationship_level (New User)
        # ---------------------------------------------------------
        logger.info("Test 1: Get Relationship (New User)")
        # Mock fetchrow returning None (no relationship yet)
        mock_conn.fetchrow.return_value = None
        
        result = await manager.get_relationship_level(user_id, char_name)
        
        if result["level_label"] == "Stranger" and result["trust_score"] == 0:
            logger.info("✅ New relationship creation passed.")
        else:
            logger.error(f"❌ New relationship creation failed. Got: {result}")
            
        # Verify INSERT was called
        mock_conn.execute.assert_called()

        # ---------------------------------------------------------
        # 2. Test get_relationship_level (Existing User)
        # ---------------------------------------------------------
        logger.info("Test 2: Get Relationship (Existing User)")
        # Mock fetchrow returning data
        mock_conn.fetchrow.return_value = {
            "trust_score": 55,
            "unlocked_traits": '["loyal"]',
            "insights": '["likes cats"]',
            "preferences": '{"verbosity": "short"}'
        }
        
        result = await manager.get_relationship_level(user_id, char_name)
        
        if result["level_label"] == "Friend" and result["trust_score"] == 55:
            logger.info("✅ Existing relationship retrieval passed.")
        else:
            logger.error(f"❌ Existing relationship retrieval failed. Got: {result}")
            
        if "loyal" in result["unlocked_traits"]:
             logger.info("✅ JSON parsing passed.")
        else:
             logger.error("❌ JSON parsing failed.")

        # ---------------------------------------------------------
        # 3. Test update_trust
        # ---------------------------------------------------------
        logger.info("Test 3: Update Trust")
        await manager.update_trust(user_id, char_name, 10)
        
        # Verify UPDATE called
        # We check if the SQL contains "UPDATE v2_user_relationships"
        args = mock_conn.execute.call_args[0]
        if "UPDATE v2_user_relationships" in args[0] and "trust_score" in args[0]:
            logger.info("✅ Update trust query passed.")
        else:
            logger.error("❌ Update trust query failed.")

        # ---------------------------------------------------------
        # 4. Test unlock_trait
        # ---------------------------------------------------------
        logger.info("Test 4: Unlock Trait")
        await manager.unlock_trait(user_id, char_name, "brave")
        
        args = mock_conn.execute.call_args[0]
        if "unlocked_traits" in args[0]:
            logger.info("✅ Unlock trait query passed.")
        else:
            logger.error("❌ Unlock trait query failed.")

    logger.info("Trust Manager Test Complete.")

if __name__ == "__main__":
    asyncio.run(test_trust_manager())
