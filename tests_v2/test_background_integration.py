import asyncio
import sys
import os
from pathlib import Path
from loguru import logger

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src_v2.core.database import db_manager
from src_v2.knowledge.manager import knowledge_manager
from src_v2.agents.reflective import ReflectiveAgent
from src_v2.config.settings import settings

# Mock user ID
USER_ID = "test_user_background_v2"
BOT_NAME = "ryan"

async def test_common_ground():
    logger.info("--- Testing Common Ground Detection ---")
    
    # 1. Setup: Ensure DB connected
    await db_manager.connect_neo4j()
    
    if not db_manager.neo4j_driver:
        logger.error("Neo4j not connected. Skipping.")
        return

    # 2. Setup: Create a fact for the user that matches Ryan
    # Ryan LISTENS_TO "Lo-fi hip hop while coding"
    # We'll create an exact match for the test
    async with db_manager.neo4j_driver.session() as session:
        # Clean up previous test data
        await session.run("MATCH (u:User {id: $uid}) DETACH DELETE u", uid=USER_ID)
        
        # Create User and Fact
        await session.run("""
            MERGE (u:User {id: $uid})
            MERGE (e:Entity {name: "Lo-fi hip hop while coding"})
            MERGE (u)-[:FACT {predicate: "LISTENS_TO"}]->(e)
        """, uid=USER_ID)
        logger.info(f"Created test fact for user {USER_ID}: LISTENS_TO 'Lo-fi hip hop while coding'")

    # 3. Test find_common_ground
    result = await knowledge_manager.find_common_ground(USER_ID, BOT_NAME)
    logger.info(f"Common Ground Result:\n{result}")
    
    if "Lo-fi hip hop" in result:
        logger.success("✅ Common ground detected successfully!")
    else:
        logger.error("❌ Common ground NOT detected.")

async def test_background_relevance():
    logger.info("\n--- Testing Background Relevance ---")
    
    # Ryan has "HAS_PHYSICAL_TRAIT" -> "Callus on right pinky from resting on keyboard"
    # We'll use a message that contains "callus" and "pinky"
    user_message = "I noticed you have a callus on your pinky finger."
    
    result = await knowledge_manager.search_bot_background(BOT_NAME, user_message)
    logger.info(f"Background Search Result:\n{result}")
    
    if "Callus" in result:
        logger.success("✅ Background relevance detected successfully!")
    else:
        logger.error("❌ Background relevance NOT detected.")

async def test_reflective_lookup():
    logger.info("\n--- Testing Reflective Agent Lookup ---")
    logger.info("(This will make a real LLM call)")
    
    agent = ReflectiveAgent()
    
    # Question that requires lookup
    question = "Why do you have a callus on your pinky?"
    system_prompt = "You are Ryan Chen, a game developer."
    
    try:
        response = await agent.run(question, USER_ID, system_prompt)
        logger.info(f"Agent Response: {response}")
        logger.success("✅ Reflective Agent run completed.")
    except Exception as e:
        logger.error(f"Reflective Agent failed: {e}")

async def main():
    # Ensure we are using the right bot name for the test
    os.environ["DISCORD_BOT_NAME"] = BOT_NAME
    
    await test_common_ground()
    await test_background_relevance()
    await test_reflective_lookup()

if __name__ == "__main__":
    asyncio.run(main())
