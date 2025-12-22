"""
Fix missing user_id fields in aetheris Qdrant collection after v1 migration.

The migration from v1 to v2 failed to preserve user_id in point payloads,
causing cross-user data leaks. This script:
1. Scrolls through all points in whisperengine_memory_aetheris
2. For each point missing user_id, attempts to recover it from content/metadata
3. Updates the point payload with the correct user_id

CRITICAL: This fixes the privacy leak where test users were seeing Cynthia's memories.
"""

import asyncio
import os
import sys
from typing import Optional, Dict, Any

# Force localhost for local debugging
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["NEO4J_URL"] = "bolt://localhost:7687"
os.environ["INFLUXDB_URL"] = "http://localhost:8086"

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from src_v2.core.database import db_manager
from qdrant_client.models import PointStruct

# Cynthia's Discord ID (the primary user of aetheris)
CYNTHIA_USER_ID = "1008886439108411472"
COLLECTION_NAME = "whisperengine_memory_aetheris"

async def infer_user_id_from_payload(payload: Dict[str, Any]) -> Optional[str]:
    """
    Attempt to infer user_id from other payload fields.
    For aetheris, most memories should belong to Cynthia.
    """
    # Check if user_id already exists
    if payload.get("user_id"):
        return payload["user_id"]
    
    # Check for author_id (ADR-014 field)
    author_id = payload.get("author_id")
    if author_id and not payload.get("author_is_bot", False):
        # If author is not a bot, use author_id as user_id
        return author_id
    
    # Check for legacy user_name field (might contain user ID or name)
    user_name = payload.get("user_name")
    
    # Default: Since this is aetheris (Cynthia's personal bot), default to Cynthia
    # Unless it's clearly a broadcast message
    if payload.get("type") == "broadcast":
        return "__broadcast__"
    
    # For aetheris, assume Cynthia unless proven otherwise
    return CYNTHIA_USER_ID

async def main():
    logger.info("Starting aetheris user_id backfill...")
    
    # Connect to Qdrant
    await db_manager.connect_qdrant()
    
    if not db_manager.qdrant_client:
        logger.error("Qdrant not available")
        return
    
    # Scroll through all points in the collection
    offset = None
    total_processed = 0
    total_fixed = 0
    total_already_ok = 0
    batch_size = 100
    
    points_to_update = []
    
    while True:
        logger.info(f"Fetching batch (offset={offset})...")
        
        scroll_result = await db_manager.qdrant_client.scroll(
            collection_name=COLLECTION_NAME,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False  # Don't need vectors for this
        )
        
        points = scroll_result[0]
        next_offset = scroll_result[1]
        
        if not points:
            logger.info("No more points to process")
            break
        
        for point in points:
            total_processed += 1
            payload = point.payload or {}
            
            # Check if user_id is missing or None
            current_user_id = payload.get("user_id")
            
            if current_user_id:
                total_already_ok += 1
                continue
            
            # Infer user_id
            inferred_user_id = await infer_user_id_from_payload(payload)
            
            if not inferred_user_id:
                logger.warning(f"Could not infer user_id for point {point.id}, skipping")
                continue
            
            # Update payload
            payload["user_id"] = inferred_user_id
            
            points_to_update.append(
                PointStruct(
                    id=point.id,
                    payload=payload,
                    vector=point.vector  # Keep existing vector
                )
            )
            
            total_fixed += 1
            
            # Batch update every 50 points
            if len(points_to_update) >= 50:
                logger.info(f"Updating batch of {len(points_to_update)} points...")
                await db_manager.qdrant_client.upsert(
                    collection_name=COLLECTION_NAME,
                    points=points_to_update
                )
                points_to_update = []
        
        # Check if we're done
        if next_offset is None:
            break
        
        offset = next_offset
    
    # Update remaining points
    if points_to_update:
        logger.info(f"Updating final batch of {len(points_to_update)} points...")
        await db_manager.qdrant_client.upsert(
            collection_name=COLLECTION_NAME,
            points=points_to_update
        )
    
    logger.info("=" * 60)
    logger.info(f"Backfill complete!")
    logger.info(f"Total points processed: {total_processed}")
    logger.info(f"Points already OK: {total_already_ok}")
    logger.info(f"Points fixed: {total_fixed}")
    logger.info("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
