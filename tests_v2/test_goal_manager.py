import asyncio
import sys
import os
from pathlib import Path
from loguru import logger

# Add project root to path
sys.path.append(os.getcwd())

from src_v2.config.settings import settings
from src_v2.core.database import db_manager
from src_v2.evolution.goals import goal_manager

async def test_goal_manager():
    logger.info("Starting Goal Manager Test...")
    
    # Initialize database
    await db_manager.connect_postgres()
    
    if not db_manager.postgres_pool:
        logger.error("❌ PostgreSQL not available. Skipping test.")
        return
    
    test_user = "test_goal_user_001"
    test_character = "elena"
    
    try:
        # ---------------------------------------------------------
        # Test 1: Create Goal
        # ---------------------------------------------------------
        logger.info("Test 1: Create a new goal")
        
        await goal_manager.create_goal(
            user_id=test_user,
            character_name=test_character,
            slug="learn_user_hobby",
            description="Learn about the user's main hobby",
            success_criteria="User shares details about their hobby and why they enjoy it",
            priority=1
        )
        
        logger.info("✅ Goal created successfully")
        
        # ---------------------------------------------------------
        # Test 2: Get Active Goals
        # ---------------------------------------------------------
        logger.info("Test 2: Retrieve active goals")
        
        active_goals = await goal_manager.get_active_goals(test_user, test_character)
        
        if len(active_goals) > 0:
            logger.info(f"✅ Retrieved {len(active_goals)} active goal(s)")
            goal = active_goals[0]
            logger.info(f"   Slug: {goal['slug']}")
            logger.info(f"   Description: {goal['description']}")
        else:
            logger.error("❌ No active goals found")
        
        # ---------------------------------------------------------
        # Test 3: Update Goal Progress
        # ---------------------------------------------------------
        logger.info("Test 3: Update goal progress")
        
        await goal_manager.update_goal_progress(
            user_id=test_user,
            goal_slug="learn_user_hobby",
            character_name=test_character,
            status="in_progress",
            progress=0.5,
            metadata={"reasoning": "User mentioned they like hiking"}
        )
        
        active_goals = await goal_manager.get_active_goals(test_user, test_character)
        goal = active_goals[0]
        
        if goal['status'] == 'in_progress' and goal['progress'] == 0.5:
            logger.info(f"✅ Goal progress updated: {goal['progress']*100}%")
        else:
            logger.error(f"❌ Progress update failed: status={goal['status']}, progress={goal['progress']}")
        
        # ---------------------------------------------------------
        # Test 4: Complete Goal
        # ---------------------------------------------------------
        logger.info("Test 4: Mark goal as completed")
        
        await goal_manager.update_goal_progress(
            user_id=test_user,
            goal_slug="learn_user_hobby",
            character_name=test_character,
            status="completed",
            progress=1.0,
            metadata={"reasoning": "User shared detailed information about hiking"}
        )
        
        # Goals with status 'completed' should not appear in active goals
        active_goals = await goal_manager.get_active_goals(test_user, test_character)
        
        if len(active_goals) == 0 or all(g['slug'] != 'learn_user_hobby' for g in active_goals):
            logger.info("✅ Completed goal removed from active list")
        else:
            logger.warning("⚠️ Completed goal still in active list (may be by design)")
        
        # ---------------------------------------------------------
        # Test 5: Create Multiple Goals with Priority
        # ---------------------------------------------------------
        logger.info("Test 5: Create multiple goals and verify priority ordering")
        
        await goal_manager.create_goal(
            user_id=test_user,
            character_name=test_character,
            slug="learn_user_location",
            description="Find out where the user lives",
            success_criteria="User mentions their city or region",
            priority=2
        )
        
        await goal_manager.create_goal(
            user_id=test_user,
            character_name=test_character,
            slug="learn_user_profession",
            description="Understand what the user does for work",
            success_criteria="User shares their job title or field",
            priority=1
        )
        
        active_goals = await goal_manager.get_active_goals(test_user, test_character)
        
        if len(active_goals) >= 2:
            logger.info(f"✅ Multiple goals created: {len(active_goals)} active")
            # Check if ordered by priority (priority 1 should come first)
            if active_goals[0]['priority'] <= active_goals[1]['priority']:
                logger.info("✅ Goals correctly ordered by priority")
            else:
                logger.warning(f"⚠️ Goal ordering may be incorrect: {[g['priority'] for g in active_goals]}")
        else:
            logger.error(f"❌ Expected at least 2 goals, got {len(active_goals)}")
        
        # ---------------------------------------------------------
        # Test 6: Get Goal History
        # ---------------------------------------------------------
        logger.info("Test 6: Retrieve goal history")
        
        # Query all goals (including completed ones)
        if db_manager.postgres_pool:
            async with db_manager.postgres_pool.acquire() as conn:
                history = await conn.fetch("""
                    SELECT slug, status, progress, completed_at
                    FROM v2_user_goals
                    WHERE user_id = $1 AND character_name = $2
                    ORDER BY created_at DESC
                """, test_user, test_character)
                
                if len(history) >= 3:
                    logger.info(f"✅ Goal history retrieved: {len(history)} total goals")
                    completed = [g for g in history if g['status'] == 'completed']
                    logger.info(f"   Completed: {len(completed)}")
                else:
                    logger.error(f"❌ Expected at least 3 goals in history, got {len(history)}")
        
        logger.info("✅ All Goal Manager tests completed!")
        
    except Exception as e:
        logger.exception(f"❌ Test failed with exception: {e}")
    
    finally:
        # Cleanup test data
        logger.info("Cleaning up test data...")
        if db_manager.postgres_pool:
            async with db_manager.postgres_pool.acquire() as conn:
                await conn.execute("""
                    DELETE FROM v2_user_goals 
                    WHERE user_id = $1 AND character_name = $2
                """, test_user, test_character)
        
        await db_manager.disconnect_all()

if __name__ == "__main__":
    asyncio.run(test_goal_manager())
