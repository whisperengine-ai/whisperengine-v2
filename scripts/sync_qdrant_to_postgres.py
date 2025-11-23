import asyncio
import sys
import os
from pathlib import Path
import asyncpg
from qdrant_client import AsyncQdrantClient
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src_v2.config.settings import settings
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="INFO")

async def sync_to_postgres(collection_name: str, bot_name: str, dry_run: bool = False):
    # 1. Connect to Postgres
    logger.info(f"Connecting to Postgres: {settings.POSTGRES_URL}")
    try:
        conn = await asyncpg.connect(settings.POSTGRES_URL)
    except Exception as e:
        logger.error(f"Failed to connect to Postgres: {e}")
        return

    # 2. Connect to Qdrant
    logger.info(f"Connecting to Qdrant: {settings.QDRANT_URL}")
    client = AsyncQdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY.get_secret_value() if settings.QDRANT_API_KEY else None)

    # 3. Scroll Qdrant
    offset = None
    total_synced = 0
    
    logger.info(f"Starting sync for collection '{collection_name}' to bot '{bot_name}'...")
    
    while True:
        points, next_offset = await client.scroll(
            collection_name=collection_name,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False
        )
        
        if not points:
            break
            
        for point in points:
            payload = point.payload or {}
            
            user_id = payload.get("user_id")
            role = payload.get("role")
            content = payload.get("content")
            timestamp_str = payload.get("timestamp")
            channel_id = payload.get("channel_id")
            message_id = payload.get("message_id")
            
            if not user_id or not content:
                logger.warning(f"Skipping point {point.id}: Missing user_id or content")
                continue
                
            # Parse timestamp
            timestamp = None
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str)
                except ValueError:
                    logger.warning(f"Invalid timestamp for point {point.id}: {timestamp_str}")
            
            if dry_run:
                logger.info(f"[Dry Run] Would insert: {role} - {content[:30]}...")
            else:
                try:
                    # Try insert
                    # We use ON CONFLICT (message_id) DO NOTHING to avoid duplicates if message_id exists
                    if message_id:
                        await conn.execute("""
                            INSERT INTO v2_chat_history (user_id, character_name, role, content, timestamp, channel_id, message_id)
                            VALUES ($1, $2, $3, $4, $5, $6, $7)
                            ON CONFLICT (message_id) DO NOTHING
                        """, str(user_id), bot_name, role, content, timestamp, str(channel_id) if channel_id else None, str(message_id))
                    else:
                        # If no message_id, we can't easily de-dupe by ID. 
                        # We'll just insert. Be careful running this multiple times.
                        await conn.execute("""
                            INSERT INTO v2_chat_history (user_id, character_name, role, content, timestamp, channel_id, message_id)
                            VALUES ($1, $2, $3, $4, $5, $6, $7)
                        """, str(user_id), bot_name, role, content, timestamp, str(channel_id) if channel_id else None, None)
                        
                except Exception as e:
                    logger.error(f"Failed to insert point {point.id}: {e}")
        
        total_synced += len(points)
        logger.info(f"Processed {total_synced} points...")
        
        offset = next_offset
        if offset is None:
            break
            
    await conn.close()
    logger.info(f"Sync complete. Processed {total_synced} messages.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Sync Qdrant memories to Postgres chat history")
    parser.add_argument("--collection", required=True, help="Qdrant collection name")
    parser.add_argument("--bot-name", required=True, help="Bot name (character_name) for Postgres")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without writing")
    
    args = parser.parse_args()
    
    asyncio.run(sync_to_postgres(args.collection, args.bot_name, args.dry_run))
