#!/usr/bin/env python3
"""
Queue today's already-generated diaries for broadcast.
One-time fix for diaries that were generated when ENABLE_BOT_BROADCAST was off.

Usage: python scripts/queue_todays_diaries.py [bot_name]
  - No args: queue all bots' diaries from today
  - With arg: queue only that bot's diary
"""
import asyncio
import os
import sys
from datetime import datetime, timezone

# Set up environment for local execution
os.environ["POSTGRES_URL"] = "postgresql://whisper:password@localhost:5432/whisperengine_v2"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["NEO4J_URL"] = "bolt://localhost:7687"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

from dotenv import load_dotenv
load_dotenv('.env.worker', override=False)

BOT_NAMES = ["elena", "dotty", "nottaylor", "aria", "dream", "jake", "sophia", "marcus", "ryan", "gabriel", "aetheris"]


async def queue_diary_for_bot(bot_name: str) -> bool:
    """Fetch today's diary for a bot and queue it for broadcast."""
    from qdrant_client import QdrantClient
    from qdrant_client.models import Filter, FieldCondition, MatchValue, Range
    import redis.asyncio as redis
    import json
    import uuid
    
    qdrant = QdrantClient(url="http://localhost:6333")
    redis_client = redis.from_url("redis://localhost:6379/0")
    
    collection_name = f"whisperengine_memory_{bot_name}"
    
    # Get today's date range
    today = datetime.now(timezone.utc).date()
    today_start = datetime.combine(today, datetime.min.time()).isoformat()
    
    try:
        # Check if collection exists
        collections = qdrant.get_collections().collections
        if not any(c.name == collection_name for c in collections):
            print(f"  ⚠️  Collection {collection_name} doesn't exist")
            return False
        
        # Find today's diary
        results = qdrant.scroll(
            collection_name=collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="type", match=MatchValue(value="diary")),
                    FieldCondition(key="bot_name", match=MatchValue(value=bot_name)),
                ]
            ),
            limit=5,
            with_payload=True,
            with_vectors=False
        )
        
        # Filter to today's entries
        today_diaries = []
        for point in results[0]:
            if point.payload:
                timestamp = point.payload.get("timestamp", "")
                if timestamp.startswith(str(today)):
                    today_diaries.append(point.payload)
        
        if not today_diaries:
            print(f"  ℹ️  No diary found for {bot_name} today")
            return False
        
        # Use the most recent one
        diary = sorted(today_diaries, key=lambda x: x.get("timestamp", ""), reverse=True)[0]
        
        # Get the content (public_version if available, otherwise content)
        content = diary.get("public_version") or diary.get("content", "")
        if not content:
            print(f"  ⚠️  Diary for {bot_name} has no content")
            return False
        
        # Queue to Redis
        queue_item = {
            "id": str(uuid.uuid4()),
            "content": content,
            "post_type": "diary",
            "character_name": bot_name,
            "provenance": [{"type": "diary", "source": "manual_queue"}],
            "queued_at": datetime.now(timezone.utc).isoformat(),
        }
        
        queue_key = f"whisper:broadcast:queue:{bot_name}"
        await redis_client.rpush(queue_key, json.dumps(queue_item))
        
        print(f"  ✅ Queued diary for {bot_name} (mood: {diary.get('mood', 'unknown')})")
        await redis_client.aclose()
        return True
        
    except Exception as e:
        print(f"  ❌ Error for {bot_name}: {e}")
        return False


async def main():
    target_bot = sys.argv[1].lower() if len(sys.argv) > 1 else None
    
    if target_bot:
        if target_bot not in BOT_NAMES:
            print(f"Unknown bot: {target_bot}")
            print(f"Available: {', '.join(BOT_NAMES)}")
            return
        bots = [target_bot]
    else:
        bots = BOT_NAMES
    
    print(f"Queuing today's diaries for broadcast...")
    print(f"Date: {datetime.now(timezone.utc).date()}")
    print()
    
    queued = 0
    for bot in bots:
        print(f"[{bot}]")
        if await queue_diary_for_bot(bot):
            queued += 1
    
    print()
    print(f"Done! Queued {queued} diaries.")
    print("The bots will pick them up from the broadcast queue automatically.")


if __name__ == "__main__":
    asyncio.run(main())
