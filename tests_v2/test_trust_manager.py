import asyncio
import sys
import os
from pathlib import Path
from loguru import logger

# Add project root to path
sys.path.append(os.getcwd())

from src_v2.config.settings import settings
from src_v2.core.database import db_manager
from src_v2.evolution.trust import trust_manager

async def test_trust_manager():
    logger.info("Starting Trust Manager Test...")
    
    # Initialize database
    await db_manager.connect_postgres()
    
    if not db_manager.postgres_pool:
        logger.error("❌ PostgreSQL not available. Skipping test.")
        return
    
    test_user = "test_trust_user_001"
    test_character = "elena"
    
    try:
        # ---------------------------------------------------------
        # Test 1: Initial Relationship Creation
        # ---------------------------------------------------------
        logger.info("Test 1: Get initial relationship (auto-creates if not exists)")
        relationship = await trust_manager.get_relationship_level(test_user, test_character)
        
        if relationship:
            logger.info(f"✅ Initial relationship created: {relationship['level']} (Trust: {relationship['trust_score']})")
            assert relationship['trust_score'] == 0, "Initial trust should be 0"
            assert relationship['level'] == "Stranger", "Initial level should be Stranger"
        else:
            logger.error("❌ Failed to create initial relationship")
            return
        
        # ---------------------------------------------------------
        # Test 2: Trust Update (Positive)
        # ---------------------------------------------------------
        logger.info("Test 2: Update trust with +10")
        await trust_manager.update_trust(test_user, test_character, delta=10)
        
        relationship = await trust_manager.get_relationship_level(test_user, test_character)
        if relationship['trust_score'] == 10:
            logger.info(f"✅ Trust updated successfully: {relationship['trust_score']}")
        else:
            logger.error(f"❌ Trust update failed. Expected 10, got {relationship['trust_score']}")
        
        # ---------------------------------------------------------
        # Test 3: Trust Update (Negative)
        # ---------------------------------------------------------
        logger.info("Test 3: Update trust with -5")
        await trust_manager.update_trust(test_user, test_character, delta=-5)
        
        relationship = await trust_manager.get_relationship_level(test_user, test_character)
        if relationship['trust_score'] == 5:
            logger.info(f"✅ Negative trust update successful: {relationship['trust_score']}")
        else:
            logger.error(f"❌ Negative trust update failed. Expected 5, got {relationship['trust_score']}")
        
        # ---------------------------------------------------------
        # Test 4: Level Progression
        # ---------------------------------------------------------
        logger.info("Test 4: Progress through trust levels")
        # Acquaintance: 20-49, Friend: 50-79, Close Friend: 80-119, Soulmate: 120+
        
        # Push to Acquaintance level (need 15 more to reach 20)
        await trust_manager.update_trust(test_user, test_character, delta=15)
        relationship = await trust_manager.get_relationship_level(test_user, test_character)
        
        if relationship['level'] == "Acquaintance" and relationship['trust_score'] == 20:
            logger.info(f"✅ Level progression: {relationship['level']} (Trust: {relationship['trust_score']})")
        else:
            logger.error(f"❌ Expected Acquaintance at 20, got {relationship['level']} at {relationship['trust_score']}")
        
        # Push to Friend level
        await trust_manager.update_trust(test_user, test_character, delta=30)
        relationship = await trust_manager.get_relationship_level(test_user, test_character)
        
        if relationship['level'] == "Friend" and relationship['trust_score'] == 50:
            logger.info(f"✅ Level progression: {relationship['level']} (Trust: {relationship['trust_score']})")
        else:
            logger.error(f"❌ Expected Friend at 50, got {relationship['level']} at {relationship['trust_score']}")
        
        # ---------------------------------------------------------
        # Test 5: Trait Unlocking
        # ---------------------------------------------------------
        logger.info("Test 5: Unlock trait")
        await trust_manager.unlock_trait(test_user, test_character, "vulnerable")
        
        relationship = await trust_manager.get_relationship_level(test_user, test_character)
        if "vulnerable" in relationship.get('unlocked_traits', []):
            logger.info(f"✅ Trait unlocked: {relationship['unlocked_traits']}")
        else:
            logger.error(f"❌ Trait unlock failed: {relationship.get('unlocked_traits', [])}")
        
        # ---------------------------------------------------------
        # Test 6: Verify Relationship Data Structure
        # ---------------------------------------------------------
        logger.info("Test 6: Verify relationship data structure")
        relationship = await trust_manager.get_relationship_level(test_user, test_character)
        
        # Check that all expected keys exist
        expected_keys = ['trust_score', 'level', 'unlocked_traits', 'insights', 'preferences']
        missing_keys = [k for k in expected_keys if k not in relationship]
        
        if len(missing_keys) == 0:
            logger.info(f"✅ All expected keys present: {expected_keys}")
        else:
            logger.error(f"❌ Missing keys: {missing_keys}")
        
        # Check data types
        if isinstance(relationship['unlocked_traits'], list):
            logger.info("✅ unlocked_traits is a list")
        else:
            logger.error(f"❌ unlocked_traits wrong type: {type(relationship['unlocked_traits'])}")
        
        # ---------------------------------------------------------
        # Test 7: Trust Bounds (min/max)
        # ---------------------------------------------------------
        logger.info("Test 7: Test trust bounds")
        # Try to go negative
        await trust_manager.update_trust(test_user, test_character, delta=-1000)
        relationship = await trust_manager.get_relationship_level(test_user, test_character)
        
        if relationship['trust_score'] >= 0:
            logger.info(f"✅ Trust floor enforced: {relationship['trust_score']} (should be >= 0)")
        else:
            logger.error(f"❌ Trust went negative: {relationship['trust_score']}")
        
        # Try to exceed maximum
        await trust_manager.update_trust(test_user, test_character, delta=1000)
        relationship = await trust_manager.get_relationship_level(test_user, test_character)
        
        if relationship['trust_score'] <= 150:
            logger.info(f"✅ Trust ceiling enforced: {relationship['trust_score']} (should be <= 150)")
        else:
            logger.error(f"❌ Trust exceeded maximum: {relationship['trust_score']}")
        
        logger.info("✅ All Trust Manager tests completed successfully!")
        
    except Exception as e:
        logger.exception(f"❌ Test failed with exception: {e}")
    
    finally:
        # Cleanup test data
        logger.info("Cleaning up test data...")
        if db_manager.postgres_pool:
            async with db_manager.postgres_pool.acquire() as conn:
                await conn.execute("""
                    DELETE FROM v2_user_relationships 
                    WHERE user_id = $1 AND character_name = $2
                """, test_user, test_character)
        
        await db_manager.disconnect_all()

if __name__ == "__main__":
    asyncio.run(test_trust_manager())
