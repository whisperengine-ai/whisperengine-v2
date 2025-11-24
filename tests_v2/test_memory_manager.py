import asyncio
import sys
import os
from pathlib import Path
from loguru import logger

# Add project root to path
sys.path.append(os.getcwd())

from src_v2.config.settings import settings
from src_v2.core.database import db_manager
from src_v2.memory.manager import memory_manager

async def test_memory_manager():
    logger.info("Starting Memory Manager Test...")
    
    # Initialize databases
    await db_manager.connect_postgres()
    await db_manager.connect_qdrant()
    
    if not db_manager.postgres_pool:
        logger.error("❌ PostgreSQL not available. Skipping test.")
        return
    
    if not db_manager.qdrant_client:
        logger.error("❌ Qdrant not available. Skipping test.")
        return
    
    test_user = "test_memory_user_001"
    test_character = "elena"
    test_channel = "test_channel_001"
    
    try:
        # ---------------------------------------------------------
        # Test 1: Add Message to Memory
        # ---------------------------------------------------------
        logger.info("Test 1: Add user message to memory")
        await memory_manager.add_message(
            user_id=test_user,
            character_name=test_character,
            role="user",
            content="I love hiking in the mountains on weekends.",
            channel_id=test_channel
        )
        
        logger.info("✅ User message added")
        
        # Add bot response
        await memory_manager.add_message(
            user_id=test_user,
            character_name=test_character,
            role="assistant",
            content="That sounds amazing! Mountain hiking is so peaceful.",
            channel_id=test_channel
        )
        
        logger.info("✅ Assistant message added")
        
        # ---------------------------------------------------------
        # Test 2: Retrieve Recent History
        # ---------------------------------------------------------
        logger.info("Test 2: Retrieve recent history")
        history = await memory_manager.get_recent_history(test_user, test_character, limit=5)
        
        if len(history) >= 2:
            logger.info(f"✅ Retrieved {len(history)} messages from history")
            # Check if messages contain expected content
            contents = [str(msg.content) for msg in history]
            if any("hiking" in c.lower() for c in contents):
                logger.info("✅ History contains expected content")
            else:
                logger.error("❌ History missing expected content")
        else:
            logger.error(f"❌ Expected at least 2 messages, got {len(history)}")
        
        # ---------------------------------------------------------
        # Test 3: Vector Search (Semantic Memory)
        # ---------------------------------------------------------
        logger.info("Test 3: Semantic search in vector memory")
        await asyncio.sleep(1)  # Give Qdrant time to index
        
        results = await memory_manager.search_memories(
            user_id=test_user,
            query="outdoor activities",
            limit=5
        )
        
        if results:
            logger.info(f"✅ Vector search returned {len(results)} results")
            # Check if results contain relevant content
            if any("hiking" in r['content'].lower() or "mountain" in r['content'].lower() for r in results):
                logger.info("✅ Semantic search found relevant content")
            else:
                logger.warning("⚠️ Semantic search didn't find exact match (may be okay depending on embeddings)")
        else:
            logger.warning("⚠️ No vector search results (Qdrant may need more time to index)")
        
        # ---------------------------------------------------------
        # Test 4: Message Count Verification
        # ---------------------------------------------------------
        logger.info("Test 4: Verify message count")
        # Check that we have at least the 2 messages we added
        history = await memory_manager.get_recent_history(test_user, test_character, limit=10)
        
        if len(history) >= 2:
            logger.info(f"✅ Message count verified: {len(history)} messages")
        else:
            logger.error(f"❌ Insufficient messages: {len(history)}")
        
        # ---------------------------------------------------------
        # Test 5: Add Multiple Messages and Check Ordering
        # ---------------------------------------------------------
        logger.info("Test 5: Add multiple messages and verify ordering")
        for i in range(3):
            await memory_manager.add_message(
                user_id=test_user,
                character_name=test_character,
                role="user",
                content=f"Test message {i+1}",
                channel_id=test_channel
            )
            await asyncio.sleep(0.1)  # Small delay to ensure ordering
        
        history = await memory_manager.get_recent_history(test_user, test_character, limit=10)
        
        if len(history) >= 5:  # 2 original + 3 new
            logger.info(f"✅ Retrieved {len(history)} messages")
            # Verify chronological order (most recent last)
            recent_contents = [str(msg.content) for msg in history[-3:]]
            if "Test message 3" in recent_contents[-1]:
                logger.info("✅ Messages are in correct chronological order")
            else:
                logger.warning("⚠️ Message ordering may be incorrect")
        else:
            logger.error(f"❌ Expected at least 5 messages, got {len(history)}")
        
        # ---------------------------------------------------------
        # Test 6: Clear User Memory
        # ---------------------------------------------------------
        logger.info("Test 6: Clear user memory")
        await memory_manager.clear_memory(test_user, test_character)
        
        history = await memory_manager.get_recent_history(test_user, test_character, limit=5)
        
        if len(history) == 0:
            logger.info("✅ User memory cleared successfully")
        else:
            logger.error(f"❌ Memory not fully cleared, {len(history)} messages remain")
        
        logger.info("✅ All Memory Manager tests completed!")
        
    except Exception as e:
        logger.exception(f"❌ Test failed with exception: {e}")
    
    finally:
        # Cleanup
        logger.info("Cleaning up test data...")
        if db_manager.postgres_pool:
            async with db_manager.postgres_pool.acquire() as conn:
                await conn.execute("""
                    DELETE FROM v2_chat_history 
                    WHERE user_id = $1 AND character_name = $2
                """, test_user, test_character)
                await conn.execute("""
                    DELETE FROM v2_chat_sessions 
                    WHERE user_id = $1 AND character_name = $2
                """, test_user, test_character)
        
        # Clear Qdrant collection
        if db_manager.qdrant_client:
            try:
                collection_name = f"whisperengine_memory_{test_character}"
                # Delete points by filter
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                await db_manager.qdrant_client.delete(
                    collection_name=collection_name,
                    points_selector=Filter(
                        must=[
                            FieldCondition(
                                key="user_id",
                                match=MatchValue(value=test_user)
                            )
                        ]
                    )
                )
                logger.info("✅ Qdrant test data cleaned")
            except Exception as e:
                logger.warning(f"⚠️ Qdrant cleanup failed: {e}")
        
        await db_manager.disconnect_all()

if __name__ == "__main__":
    asyncio.run(test_memory_manager())
