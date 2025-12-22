import asyncio
import os

# Force localhost for local debugging
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["NEO4J_URL"] = "bolt://localhost:7687"
os.environ["INFLUXDB_URL"] = "http://localhost:8086"

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src_v2.memory.manager import MemoryManager
from src_v2.core.database import db_manager

async def main():
    # Connect to Qdrant
    await db_manager.connect_qdrant()
    
    # Create memory manager for aetheris
    mem_mgr = MemoryManager(bot_name="aetheris")
    
    print("Searching for broadcast memories in aetheris collection...")
    broadcast_mems = await mem_mgr.search_memories(
        query="second life discord",
        user_id="__broadcast__",
        limit=10
    )
    
    print(f"\nFound {len(broadcast_mems)} broadcast memories:")
    for i, mem in enumerate(broadcast_mems):
        print(f"\n--- Memory {i+1} ---")
        print(f"User ID: {mem.get('user_id')}")
        print(f"Content: {mem.get('content')[:200]}...")
        print(f"Timestamp: {mem.get('timestamp')}")
        print(f"Channel: {mem.get('channel_id')}")
    
    print("\n\nSearching for test user memories...")
    test_mems = await mem_mgr.search_memories(
        query="I am sending you an image",
        user_id="test_user_api_v2",
        limit=10
    )
    
    print(f"\nFound {len(test_mems)} test user memories:")
    for i, mem in enumerate(test_mems):
        print(f"\n--- Memory {i+1} ---")
        print(f"User ID: {mem.get('user_id')}")
        print(f"Content: {mem.get('content')[:200]}...")

    print("\n\nSearching for Cynthia's 'second life' memories...")
    cynthia_mems = await mem_mgr.search_memories(
        query="second life",
        user_id="1008886439108411472",
        limit=5
    )
    
    print(f"\nFound {len(cynthia_mems)} Cynthia memories about second life:")
    for i, mem in enumerate(cynthia_mems):
        print(f"\n--- Memory {i+1} ---")
        print(f"User ID: {mem.get('user_id')}")
        print(f"Content: {mem.get('content')[:300]}...")

    print("\n\nSearching for NEW test user memories...")
    new_test_mems = await mem_mgr.search_memories(
        query="Hello who am I",
        user_id="test_user_api_v2_clean",
        limit=10
    )
    
    print(f"\nFound {len(new_test_mems)} NEW test user memories:")
    for i, mem in enumerate(new_test_mems):
        print(f"\n--- Memory {i+1} ---")
        print(f"Content: {mem.get('content')[:200]}...")
        print(f"Timestamp: {mem.get('timestamp')}")

if __name__ == "__main__":
    asyncio.run(main())
