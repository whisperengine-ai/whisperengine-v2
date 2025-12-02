import asyncio
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct

async def main():
    client = AsyncQdrantClient(location=":memory:")
    
    try:
        await client.recreate_collection(
            collection_name="test_collection",
            vectors_config={"size": 4, "distance": "Cosine"}
        )
        await client.upsert(
            collection_name="test_collection",
            points=[
                PointStruct(id=1, vector=[0.1, 0.1, 0.1, 0.1], payload={"test": "data"})
            ]
        )
        result = await client.query_points(
            collection_name="test_collection",
            query=[0.1, 0.1, 0.1, 0.1],
            limit=1
        )
        print("\n--- query_points Result Type ---")
        print(type(result))
        print(result)
        print("\n--- Result Attributes ---")
        print(dir(result))
        if hasattr(result, 'points'):
            print(f"Points type: {type(result.points)}")
            if len(result.points) > 0:
                print(f"First point type: {type(result.points[0])}")
                print(f"First point attrs: {dir(result.points[0])}")
    except Exception as e:
        print(f"Error testing query_points: {e}")

if __name__ == "__main__":
    asyncio.run(main())