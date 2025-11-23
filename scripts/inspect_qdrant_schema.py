import asyncio
import sys
from qdrant_client import AsyncQdrantClient

async def inspect_schema(url, collection_name):
    client = AsyncQdrantClient(url=url)
    try:
        points, _ = await client.scroll(
            collection_name=collection_name,
            limit=1,
            with_payload=True,
            with_vectors=False
        )
        
        if points:
            print(f"--- Sample Point from {collection_name} ---")
            print(f"ID: {points[0].id}")
            print("Payload:")
            for k, v in points[0].payload.items():
                print(f"  {k}: {v}")
        else:
            print(f"Collection {collection_name} is empty.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python inspect_qdrant_schema.py <url> <collection>")
        sys.exit(1)
        
    asyncio.run(inspect_schema(sys.argv[1], sys.argv[2]))
