#!/usr/bin/env python3
"""
Check FULL diary entries for any bot in Qdrant.
Usage: python check_diary_full.py <bot_name>
"""
import asyncio
import sys
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

# Available bots for validation
AVAILABLE_BOTS = [
    "elena", "ryan", "dotty", "aria", "dream", 
    "jake", "sophia", "marcus", "nottaylor"
]

async def main():
    if len(sys.argv) < 2:
        print("Usage: python check_diary_full.py <bot_name>")
        return

    bot_name = sys.argv[1].lower()

    # Connect to Qdrant
    client = AsyncQdrantClient(url="http://localhost:6333")
    collection_name = f"whisperengine_memory_{bot_name}"
    
    print(f"Checking collection: {collection_name}")
    
    try:
        # Fetch recent diaries
        search_result = await client.scroll(
            collection_name=collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="type",
                        match=MatchValue(value="diary")
                    )
                ]
            ),
            limit=3, # Just get top 3
            with_payload=True,
            with_vectors=False
        )
        
        print("\n--- Recent Diary Entries (FULL) ---")
        for point in search_result[0]:
            payload = point.payload
            if payload:
                print(f"\n=== Date: {payload.get('timestamp')} ===")
                print(payload.get('content', ''))
                print("="*50)

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
