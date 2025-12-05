#!/usr/bin/env python3
"""
Re-chunk existing long memories in Qdrant for better semantic search.

This script finds memories > CHUNK_THRESHOLD chars and re-embeds them as
multiple smaller chunks. Each chunk gets its own vector for more precise
semantic matching.

Usage:
    python scripts/rechunk_memories.py elena          # Process elena's memories
    python scripts/rechunk_memories.py elena --dry-run  # Preview without changes
    python scripts/rechunk_memories.py all            # Process all bots

The script is idempotent - already-chunked memories are skipped.
"""

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue

from src_v2.config.settings import settings
from src_v2.memory.embeddings import EmbeddingService
from src_v2.memory.manager import chunk_text, CHUNK_THRESHOLD

# All known bot names
ALL_BOTS = [
    "elena", "nottaylor", "dotty", "aria", "dream", 
    "jake", "marcus", "ryan", "sophia", "gabriel", "aetheris"
]


async def rechunk_collection(
    bot_name: str,
    dry_run: bool = False,
    qdrant_host: str = "localhost",
    qdrant_port: int = 6333
) -> dict:
    """
    Re-chunk long memories in a bot's Qdrant collection.
    
    Returns:
        dict with stats: processed, chunked, chunks_created, skipped, errors
    """
    collection_name = f"whisperengine_memory_{bot_name}"
    
    logger.info(f"Processing collection: {collection_name}")
    
    # Connect to Qdrant
    client = QdrantClient(host=qdrant_host, port=qdrant_port)
    
    # Check if collection exists
    try:
        info = client.get_collection(collection_name)
        logger.info(f"Collection has {info.points_count} points")
    except Exception as e:
        logger.error(f"Collection {collection_name} not found: {e}")
        return {"error": str(e)}
    
    # Initialize embedding service
    embedding_service = EmbeddingService()
    
    stats = {
        "processed": 0,
        "already_chunked": 0,
        "needs_chunking": 0,
        "chunks_created": 0,
        "deleted": 0,
        "errors": 0
    }
    
    # Scroll through all points
    offset = None
    batch_size = 100
    
    while True:
        results = client.scroll(
            collection_name=collection_name,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False
        )
        
        points, next_offset = results
        
        if not points:
            break
        
        for point in points:
            stats["processed"] += 1
            payload = point.payload or {}
            content = payload.get("content", "")
            
            # Skip if already a chunk
            if payload.get("is_chunk"):
                stats["already_chunked"] += 1
                continue
            
            # Skip if short enough
            if len(content) <= CHUNK_THRESHOLD:
                continue
            
            stats["needs_chunking"] += 1
            
            # Get metadata to preserve
            user_id = payload.get("user_id")
            role = payload.get("role")
            channel_id = payload.get("channel_id")
            message_id = payload.get("message_id")
            timestamp = payload.get("timestamp")
            source_type = payload.get("source_type")
            importance_score = payload.get("importance_score", 3)
            user_name = payload.get("user_name")
            memory_type = payload.get("type", "conversation")
            
            if dry_run:
                chunks = chunk_text(content)
                logger.info(
                    f"  Would chunk point {point.id}: {len(content)} chars -> {len(chunks)} chunks"
                )
                stats["chunks_created"] += len(chunks)
                continue
            
            try:
                # Generate chunks
                chunks = chunk_text(content)
                
                # Ensure we have a parent ID for grouping chunks
                chunk_group_id = str(message_id) if message_id else str(uuid.uuid4())
                
                # Create new points for each chunk
                new_points = []
                for chunk_content, chunk_idx in chunks:
                    # Generate embedding
                    embedding = await embedding_service.embed_query_async(chunk_content)
                    
                    new_payload = {
                        "type": memory_type,
                        "user_id": user_id,
                        "role": role,
                        "content": chunk_content,
                        "timestamp": timestamp,
                        "channel_id": channel_id,
                        "message_id": message_id,
                        "importance_score": importance_score,
                        "source_type": source_type,
                        "user_name": user_name,
                        # Chunk metadata
                        "is_chunk": True,
                        "chunk_index": chunk_idx,
                        "chunk_total": len(chunks),
                        "parent_message_id": chunk_group_id,
                        "original_length": len(content)
                    }
                    
                    new_points.append(
                        PointStruct(
                            id=str(uuid.uuid4()),
                            vector=embedding,
                            payload=new_payload
                        )
                    )
                
                # Delete original point
                client.delete(
                    collection_name=collection_name,
                    points_selector=[point.id]
                )
                stats["deleted"] += 1
                
                # Insert new chunks
                client.upsert(
                    collection_name=collection_name,
                    points=new_points
                )
                stats["chunks_created"] += len(new_points)
                
                logger.info(
                    f"  Chunked point {point.id}: {len(content)} chars -> {len(chunks)} chunks"
                )
                
            except Exception as e:
                logger.error(f"  Error processing point {point.id}: {e}")
                stats["errors"] += 1
        
        # Progress update
        if stats["processed"] % 500 == 0:
            logger.info(f"  Progress: {stats['processed']} points processed...")
        
        offset = next_offset
        if offset is None:
            break
    
    return stats


async def main():
    parser = argparse.ArgumentParser(
        description="Re-chunk long memories in Qdrant for better semantic search"
    )
    parser.add_argument(
        "bot",
        help="Bot name to process (e.g., 'elena') or 'all' for all bots"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying data"
    )
    parser.add_argument(
        "--qdrant-host",
        default="localhost",
        help="Qdrant host (default: localhost)"
    )
    parser.add_argument(
        "--qdrant-port",
        type=int,
        default=6333,
        help="Qdrant port (default: 6333)"
    )
    
    args = parser.parse_args()
    
    # Determine which bots to process
    if args.bot.lower() == "all":
        bots = ALL_BOTS
    else:
        bots = [args.bot.lower()]
    
    if args.dry_run:
        logger.info("=== DRY RUN MODE - No changes will be made ===")
    
    logger.info(f"Chunk threshold: {CHUNK_THRESHOLD} chars")
    logger.info(f"Processing {len(bots)} bot(s): {', '.join(bots)}")
    print()
    
    all_stats = {}
    
    for bot in bots:
        logger.info(f"{'='*50}")
        logger.info(f"Bot: {bot}")
        logger.info(f"{'='*50}")
        
        stats = await rechunk_collection(
            bot_name=bot,
            dry_run=args.dry_run,
            qdrant_host=args.qdrant_host,
            qdrant_port=args.qdrant_port
        )
        
        all_stats[bot] = stats
        
        if "error" in stats:
            logger.error(f"  Failed: {stats['error']}")
        else:
            logger.info(f"  Processed: {stats['processed']}")
            logger.info(f"  Already chunked (skipped): {stats['already_chunked']}")
            logger.info(f"  Needed chunking: {stats['needs_chunking']}")
            logger.info(f"  Chunks created: {stats['chunks_created']}")
            if not args.dry_run:
                logger.info(f"  Original points deleted: {stats['deleted']}")
            logger.info(f"  Errors: {stats['errors']}")
        
        print()
    
    # Summary
    logger.info("="*50)
    logger.info("SUMMARY")
    logger.info("="*50)
    
    total_processed = sum(s.get("processed", 0) for s in all_stats.values())
    total_chunked = sum(s.get("needs_chunking", 0) for s in all_stats.values())
    total_chunks = sum(s.get("chunks_created", 0) for s in all_stats.values())
    total_errors = sum(s.get("errors", 0) for s in all_stats.values())
    
    logger.info(f"Total points processed: {total_processed}")
    logger.info(f"Total messages re-chunked: {total_chunked}")
    logger.info(f"Total new chunks created: {total_chunks}")
    logger.info(f"Total errors: {total_errors}")
    
    if args.dry_run:
        logger.info("\n[DRY RUN] No changes were made. Run without --dry-run to apply.")


if __name__ == "__main__":
    asyncio.run(main())
