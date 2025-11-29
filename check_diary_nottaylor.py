import asyncio
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

async def main():
    # Connect to Qdrant (assuming localhost:6333 based on standard setup)
    client = AsyncQdrantClient(url="http://localhost:6333")
    collection_name = "whisperengine_memory_nottaylor"
    
    print(f"Checking collection: {collection_name}")
    
    try:
        # Check if collection exists
        collections = await client.get_collections()
        exists = any(c.name == collection_name for c in collections.collections)
        if not exists:
            print(f"Collection {collection_name} does not exist.")
            return

        # Count diaries
        count_result = await client.count(
            collection_name=collection_name,
            count_filter=Filter(
                must=[
                    FieldCondition(
                        key="type",
                        match=MatchValue(value="diary")
                    )
                ]
            )
        )
        
        print(f"Total diary entries found: {count_result.count}")
        
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
            limit=5,
            with_payload=True,
            with_vectors=False
        )
        
        print("\n--- Recent Diary Entries ---")
        for point in search_result[0]:
            payload = point.payload
            print(f"\nDate: {payload.get('timestamp')}")
            print(f"Content: {payload.get('content')[:150]}...")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
