
import asyncio
import sys
from pathlib import Path
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src_v2.core.database import db_manager
from src_v2.memory.manager import MemoryManager
from src_v2.config.settings import settings

async def verify():
    # Connect to DBs
    await db_manager.connect_qdrant()
    
    # Initialize manager for Elena
    manager = MemoryManager(bot_name="elena")
    
    query = "high-trust bot pairs"
    logger.info(f"Searching for: '{query}'")
    
    # We need a user_id to use the manager's search_memories, 
    # but we might not know the exact user_id used in the chat.
    # Let's try to search using the raw client to find ANY match in the collection.
    
    embedding = await manager.embedding_service.embed_query_async(query)
    
    results = await db_manager.qdrant_client.query_points(
        collection_name="whisperengine_memory_elena",
        query=embedding,
        limit=5,
        with_payload=True
    )
    
    print(f"\nFound {len(results.points)} results:\n")
    
    for hit in results.points:
        payload = hit.payload
        content = payload.get("content", "")[:100] + "..."
        score = hit.score
        is_chunk = payload.get("is_chunk", False)
        chunk_idx = payload.get("chunk_index")
        total = payload.get("chunk_total")
        user_id = payload.get("user_id")
        parent_id = payload.get("parent_message_id")
        msg_id = payload.get("message_id")
        
        print(f"Score: {score:.4f}")
        print(f"User ID: {user_id}")
        print(f"Parent ID: {parent_id} | Message ID: {msg_id}")
        print(f"Type: {'CHUNK' if is_chunk else 'FULL MESSAGE'} ({chunk_idx}/{total} if chunk)")
        print(f"Content: {content}")
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(verify())
