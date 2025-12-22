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
    await db_manager.connect_postgres()
    
    mem_mgr = MemoryManager(bot_name="aetheris")
    
    user_id = "brand_new_user_final_test"
    
    print(f"Checking history for user: {user_id}")
    
    # Test 1: With channel_id (the OLD buggy way)
    print("\n--- With channel_id='api_chat' (OLD WAY) ---")
    history_with_channel = await mem_mgr.get_recent_history(
        user_id=user_id,
        character_name="aetheris",
        channel_id="api_chat",
        limit=10
    )
    print(f"Found {len(history_with_channel)} messages:")
    for i, msg in enumerate(history_with_channel):
        print(f"{i+1}. {msg.content[:100]}...")
    
    # Test 2: Without channel_id (the FIXED way)
    print("\n--- Without channel_id (NEW WAY) ---")
    history_without_channel = await mem_mgr.get_recent_history(
        user_id=user_id,
        character_name="aetheris",
        channel_id=None,
        limit=10
    )
    print(f"Found {len(history_without_channel)} messages:")
    for i, msg in enumerate(history_without_channel):
        print(f"{i+1}. {msg.content[:100]}...")
    
    # Test 3: Check what's actually in the database
    print("\n--- Raw database query ---")
    async with db_manager.postgres_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT role, content, user_id, channel_id, timestamp
            FROM v2_chat_history 
            WHERE user_id = $1 AND character_name = $2
            ORDER BY timestamp DESC
            LIMIT 10
        """, user_id, "aetheris")
        
        print(f"Found {len(rows)} rows in database:")
        for i, row in enumerate(rows):
            print(f"{i+1}. [{row['role']}] user_id={row['user_id']}, channel_id={row['channel_id']}")
            print(f"   Content: {row['content'][:80]}...")

if __name__ == "__main__":
    asyncio.run(main())
