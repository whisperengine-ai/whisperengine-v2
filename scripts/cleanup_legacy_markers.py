"""
One-time cleanup script to remove messages containing legacy [WHISPER_IMAGE:...] markers from Qdrant.
"""
import asyncio
import re
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchText

QDRANT_URL = "http://localhost:6333"
MARKER_PATTERN = re.compile(r'\[WHISPER_IMAGE:[a-f0-9]+\]')

async def cleanup_legacy_markers():
    client = QdrantClient(url=QDRANT_URL)
    
    # Get all collections
    collections = client.get_collections().collections
    print(f"Found {len(collections)} collections")
    
    total_deleted = 0
    
    for collection in collections:
        name = collection.name
        if not name.startswith("whisperengine_memory_"):
            continue
            
        print(f"\nProcessing collection: {name}")
        
        # Scroll through all points
        offset = None
        points_to_delete = []
        
        while True:
            results = client.scroll(
                collection_name=name,
                offset=offset,
                limit=100,
                with_payload=True,
                with_vectors=False
            )
            
            points, next_offset = results
            
            for point in points:
                payload = point.payload or {}
                content = payload.get("content", "")
                
                if MARKER_PATTERN.search(content):
                    points_to_delete.append(point.id)
                    print(f"  Found marker in point {point.id}: {content[:80]}...")
            
            if next_offset is None:
                break
            offset = next_offset
        
        if points_to_delete:
            print(f"  Deleting {len(points_to_delete)} points with legacy markers...")
            client.delete(
                collection_name=name,
                points_selector=points_to_delete
            )
            total_deleted += len(points_to_delete)
        else:
            print(f"  No legacy markers found")
    
    print(f"\n✅ Cleanup complete. Deleted {total_deleted} points total.")

if __name__ == "__main__":
    asyncio.run(cleanup_legacy_markers())
