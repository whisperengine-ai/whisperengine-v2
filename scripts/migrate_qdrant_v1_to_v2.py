import argparse
import asyncio
import sys
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
import uuid

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Configure logger
from loguru import logger
logger.remove()
logger.add(sys.stderr, level="INFO")

try:
    from qdrant_client import AsyncQdrantClient, models
except ImportError:
    logger.error("qdrant-client is not installed. Please run: pip install qdrant-client")
    sys.exit(1)

try:
    from src_v2.memory.embeddings import EmbeddingService
except ImportError:
    logger.warning("Could not import EmbeddingService. Re-embedding capability will be limited.")
    EmbeddingService = None

async def migrate_collection(
    v1_url: str,
    v1_api_key: Optional[str],
    v1_collection: str,
    v2_url: str,
    v2_api_key: Optional[str],
    v2_collection: str,
    batch_size: int = 100,
    re_embed: bool = False,
    dry_run: bool = False
):
    logger.info(f"Connecting to v1 Qdrant: {v1_url}")
    client_v1 = AsyncQdrantClient(url=v1_url, api_key=v1_api_key)
    
    logger.info(f"Connecting to v2 Qdrant: {v2_url}")
    client_v2 = AsyncQdrantClient(url=v2_url, api_key=v2_api_key)

    # Check v1 collection
    try:
        v1_info = await client_v1.get_collection(v1_collection)
        logger.info(f"Found v1 collection '{v1_collection}': {v1_info.points_count} points")
    except Exception as e:
        logger.error(f"Failed to get v1 collection '{v1_collection}': {e}")
        return

    # Check/Create v2 collection
    try:
        v2_exists = await client_v2.collection_exists(v2_collection)
        if not v2_exists:
            if dry_run:
                logger.info(f"[Dry Run] Would create v2 collection '{v2_collection}'")
            else:
                logger.info(f"Creating v2 collection '{v2_collection}' with size 384 (Cosine)")
                await client_v2.create_collection(
                    collection_name=v2_collection,
                    vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE)
                )
        else:
            logger.info(f"Found v2 collection '{v2_collection}'")
    except Exception as e:
        logger.error(f"Failed to check/create v2 collection '{v2_collection}': {e}")
        return

    # Initialize embedding service if needed
    embedding_service = None
    if re_embed:
        if EmbeddingService:
            logger.info("Initializing EmbeddingService for re-embedding...")
            embedding_service = EmbeddingService()
        else:
            logger.error("Cannot re-embed: EmbeddingService not available.")
            return

    # Migrate points
    offset = None
    total_migrated = 0
    
    logger.info("Starting migration...")
    
    while True:
        # Scroll v1
        points, next_offset = await client_v1.scroll(
            collection_name=v1_collection,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=True
        )
        
        if not points:
            break
            
        points_to_upsert = []
        
        for point in points:
            # Prepare new point
            new_id = point.id
            old_payload = point.payload or {}
            
            # --- Schema Mapping ---
            # v1 fields: user_id, content, role (bot/user), timestamp, channel_id, original_message_id, ...
            # v2 fields: user_id, content, role (ai/human), timestamp, channel_id, message_id, ...
            
            new_payload = old_payload.copy()
            
            # Map 'role'
            old_role = old_payload.get("role")
            if old_role == "bot":
                new_payload["role"] = "ai"
            elif old_role == "user":
                new_payload["role"] = "human"
            # else keep as is (e.g. 'system' or already correct)
            
            # Map 'original_message_id' to 'message_id'
            if "original_message_id" in old_payload and "message_id" not in old_payload:
                new_payload["message_id"] = old_payload["original_message_id"]
                
            # Map 'overall_significance' to 'importance_score' (v2 uses 1-10 int)
            if "importance_score" not in new_payload:
                if "overall_significance" in old_payload:
                    try:
                        sig = float(old_payload["overall_significance"])
                        # Map 0.0-1.0 to 1-10
                        new_payload["importance_score"] = max(1, min(10, int(sig * 10)))
                    except (ValueError, TypeError):
                        new_payload["importance_score"] = 3
                else:
                    new_payload["importance_score"] = 3

            # Ensure required fields exist (fill with defaults if missing)
            if "timestamp" not in new_payload:
                import datetime
                new_payload["timestamp"] = datetime.datetime.now().isoformat()
                
            # ----------------------

            new_vector = point.vector
            
            # Re-embed if requested
            if re_embed and embedding_service:
                content = new_payload.get("content")
                if content:
                    # Generate new embedding
                    # embed_query returns a list of floats
                    new_vector = embedding_service.embed_query(content)
                else:
                    logger.warning(f"Point {point.id} has no 'content' in payload, skipping re-embedding.")
            
            # Validate vector size for v2 (384)
            # Note: point.vector can be a list or a dict (if named vectors)
            # We assume single vector for now as per v2 spec
            if isinstance(new_vector, dict):
                # Handle named vectors from v1
                # Prefer 'content' or 'semantic' vector
                if "content" in new_vector:
                    new_vector = new_vector["content"]
                elif "semantic" in new_vector:
                    new_vector = new_vector["semantic"]
                else:
                    # Fallback to first available vector
                    first_key = next(iter(new_vector))
                    new_vector = new_vector[first_key]
                    logger.warning(f"Point {point.id} has named vectors but no 'content' or 'semantic'. Using '{first_key}'.")
            
            if new_vector is None:
                logger.warning(f"Point {point.id} has no vector. Skipping.")
                continue
                
            if len(new_vector) != 384 and not re_embed:
                logger.warning(f"Point {point.id} vector size {len(new_vector)} != 384. Use --re-embed to fix. Skipping.")
                continue
                
            points_to_upsert.append(models.PointStruct(
                id=new_id,
                vector=new_vector,
                payload=new_payload
            ))
            
        if points_to_upsert:
            if dry_run:
                logger.info(f"[Dry Run] Would upsert {len(points_to_upsert)} points")
            else:
                await client_v2.upsert(
                    collection_name=v2_collection,
                    points=points_to_upsert
                )
                
        total_migrated += len(points_to_upsert)
        logger.info(f"Migrated {total_migrated} points...")
        
        offset = next_offset
        if offset is None:
            break
            
    logger.info(f"Migration complete. Total points migrated: {total_migrated}")

def main():
    parser = argparse.ArgumentParser(description="Migrate Qdrant collection from v1 to v2")
    parser.add_argument("--v1-url", default="http://localhost:6333", help="v1 Qdrant URL")
    parser.add_argument("--v1-key", default=None, help="v1 Qdrant API Key")
    parser.add_argument("--v1-collection", required=True, help="Source collection name")
    
    parser.add_argument("--v2-url", default="http://localhost:6333", help="v2 Qdrant URL")
    parser.add_argument("--v2-key", default=None, help="v2 Qdrant API Key")
    parser.add_argument("--v2-collection", required=True, help="Destination collection name")
    
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size")
    parser.add_argument("--re-embed", action="store_true", help="Force re-embedding of content")
    parser.add_argument("--dry-run", action="store_true", help="Simulate migration without writing")
    
    args = parser.parse_args()
    
    asyncio.run(migrate_collection(
        v1_url=args.v1_url,
        v1_api_key=args.v1_key,
        v1_collection=args.v1_collection,
        v2_url=args.v2_url,
        v2_api_key=args.v2_key,
        v2_collection=args.v2_collection,
        batch_size=args.batch_size,
        re_embed=args.re_embed,
        dry_run=args.dry_run
    ))

if __name__ == "__main__":
    main()
