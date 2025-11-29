#!/usr/bin/env python3
"""
Check dream entries for any bot in Qdrant.
Usage: python check_dreams.py <bot_name>
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
        print("Usage: python check_dreams.py <bot_name>")
        print(f"Available bots: {', '.join(AVAILABLE_BOTS)}")
        return

    bot_name = sys.argv[1].lower()
    if bot_name not in AVAILABLE_BOTS:
        print(f"Warning: '{bot_name}' is not in the standard list, but proceeding anyway.")

    # Connect to Qdrant (assuming localhost:6333 based on standard setup)
    client = AsyncQdrantClient(url="http://localhost:6333")
    collection_name = f"whisperengine_memory_{bot_name}"
    
    print(f"Checking collection: {collection_name}")
    
    try:
        # Check if collection exists
        collections = await client.get_collections()
        exists = any(c.name == collection_name for c in collections.collections)
        if not exists:
            print(f"Collection {collection_name} does not exist.")
            return

        # Count dreams
        count_result = await client.count(
            collection_name=collection_name,
            count_filter=Filter(
                must=[
                    FieldCondition(
                        key="type",
                        match=MatchValue(value="dream")
                    )
                ]
            )
        )
        print(f"Total dreams found: {count_result.count}")
        
        if count_result.count > 0:
            # Fetch a few dreams
            scroll_result = await client.scroll(
                collection_name=collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="type",
                            match=MatchValue(value="dream")
                        )
                    ]
                ),
                limit=3,
                with_payload=True
            )
            
            print("\n--- Recent Dreams ---")
            for point in scroll_result[0]:
                payload = point.payload
                if payload:
                    print(f"\nDate: {payload.get('timestamp', 'Unknown')}")
                    content = payload.get('content', '')
                    if content:
                        print(f"Content: {content[:200]}...")
                    else:
                        print("Content: [Empty]")
                
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
