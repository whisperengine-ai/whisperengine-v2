import asyncio
from qdrant_client import AsyncQdrantClient
import json

async def inspect():
    client = AsyncQdrantClient(url="http://localhost:6333")
    points, _ = await client.scroll(
        collection_name="import_aetheris_v1",
        limit=1,
        with_payload=True,
        with_vectors=False
    )
    if points:
        print(json.dumps(points[0].payload, indent=2))
    else:
        print("No points found")

if __name__ == "__main__":
    asyncio.run(inspect())
