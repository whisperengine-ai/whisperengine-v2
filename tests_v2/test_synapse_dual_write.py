import asyncio
import sys
import os
import uuid
from loguru import logger

# Add project root to path
sys.path.append(os.getcwd())

from src_v2.core.database import db_manager
from src_v2.memory.manager import memory_manager
from src_v2.knowledge.manager import knowledge_manager

async def test_synapse_dual_write():
    """
    Verifies Phase 2.5.1: Synapse (Graph Unification)
    Ensures that saving a memory to Qdrant also creates a (:Memory) node in Neo4j.
    """
    logger.info("🧠 Starting Synapse Dual-Write Test...")
    
    # 1. Initialize
    await db_manager.connect_postgres()
    await db_manager.connect_qdrant()
    await db_manager.connect_neo4j()
    await memory_manager.initialize()
    await knowledge_manager.initialize()

    if not db_manager.qdrant_client or not db_manager.neo4j_driver:
        logger.error("❌ Databases not available. Skipping test.")
        return

    # Test Data
    test_run_id = str(uuid.uuid4())[:8]
    user_id = f"test_synapse_user_{test_run_id}"
    content = f"I am testing the Synapse dual-write system with run ID {test_run_id}."
    
    try:
        # 2. Add Memory (Should trigger dual-write)
        logger.info(f"📝 Adding memory for user {user_id}...")
        await memory_manager.add_message(
            user_id=user_id,
            character_name="elena",
            role="user",
            content=content
        )
        
        # Give async operations a moment to settle (though they should be awaited)
        await asyncio.sleep(1)

        # 3. Retrieve from Qdrant to get the Vector ID
        logger.info("🔍 Searching Qdrant for the memory ID...")
        memories = await memory_manager.search_memories(
            query=content,
            user_id=user_id,
            limit=1,
            collection_name="whisperengine_memory_elena"
        )
        
        if not memories:
            logger.error("❌ Failed to find memory in Qdrant!")
            return
            
        vector_id = memories[0]['id']
        logger.info(f"✅ Found memory in Qdrant. Vector ID: {vector_id}")

        # 4. Verify Graph Node (Neo4j)
        logger.info("🕸️ Verifying (:Memory) node in Neo4j...")
        query = """
        MATCH (m:Memory {id: $vector_id})
        RETURN m.content as content, m.source_type as source_type
        """
        async with db_manager.neo4j_driver.session() as session:
            result = await session.run(query, vector_ids=[vector_id], vector_id=vector_id)
            record = await result.single()
            
            if record:
                logger.info(f"✅ Found (:Memory) node in Neo4j!")
                logger.info(f"   Content: {record['content']}")
                if record['content'] == content:
                    logger.info("   Content matches exactly.")
                else:
                    logger.warning(f"   Content mismatch! Expected '{content}', got '{record['content']}'")
            else:
                logger.error("❌ Failed to find (:Memory) node in Neo4j!")

        # 5. Verify Neighborhood Retrieval
        logger.info("🏘️ Testing get_memory_neighborhood()...")
        neighborhood = await knowledge_manager.get_memory_neighborhood([vector_id])
        
        # Note: Neighborhood might be empty if user has no facts, but the call should succeed
        logger.info(f"✅ Neighborhood call successful. Items found: {len(neighborhood)}")
        
        logger.info("🎉 Synapse Test Complete!")

    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(test_synapse_dual_write())
