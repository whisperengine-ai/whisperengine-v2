"""
Aetheris V1 → V2 Migration Script (Fixed)
==========================================

This script migrates aetheris data from v1 to v2 schema with proper field mapping.

Key Changes from v1 to v2:
1. Vector schema: Multi-vector (content/emotion/semantic) → Single unnamed vector
2. Payload: v1 emotional metadata → v2 simplified schema
3. Required fields: user_name, author_name, is_chunk, chunk metadata
4. Re-embed all content with v2 embedding model

Usage:
    python scripts/migrate_aetheris_v2_fixed.py [--dry-run] [--clear-first]
"""
import asyncio
import sys
import os
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import uuid
import datetime
import json
from loguru import logger

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from qdrant_client import AsyncQdrantClient, models
from src_v2.memory.embeddings import EmbeddingService
from src_v2.core.database import db_manager
from src_v2.config.settings import settings
from src_v2.utils.content_cleaning import strip_context_markers

# Constants
CHUNK_THRESHOLD = 1000
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
V1_COLLECTION = "import_aetheris_v1"
V2_COLLECTION = "whisperengine_memory_aetheris"
CHARACTER_NAME = "aetheris"

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[Tuple[str, int]]:
    """Split long text into overlapping chunks."""
    if not text or not text.strip():
        return []
    if len(text) <= chunk_size:
        return [(text, 0)]
    
    chunks = []
    start = 0
    chunk_idx = 0
    
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            search_start = max(end - 100, start)
            best_break = end
            for i in range(end, search_start, -1):
                if i < len(text) and text[i-1] in '.!?\n':
                    best_break = i
                    break
            end = best_break
        else:
            end = len(text)
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append((chunk, chunk_idx))
            chunk_idx += 1
        
        start = end - overlap if end < len(text) else len(text)
    
    return chunks

async def migrate(dry_run: bool = False, clear_first: bool = False):
    """
    Migrate aetheris from v1 to v2 schema.
    
    Args:
        dry_run: If True, only shows what would be migrated without writing
        clear_first: If True, clears v2 collection before migration
    """
    # Initialize connections
    logger.info("Initializing connections...")
    await db_manager.connect_postgres()
    
    qdrant = AsyncQdrantClient(url=settings.QDRANT_URL)
    embedding_service = EmbeddingService()
    
    # Check v1 collection exists
    v1_exists = await qdrant.collection_exists(V1_COLLECTION)
    if not v1_exists:
        logger.error(f"V1 collection {V1_COLLECTION} does not exist!")
        return
    
    v1_info = await qdrant.get_collection(V1_COLLECTION)
    v1_count = v1_info.points_count
    logger.info(f"V1 collection has {v1_count} points")
    
    # Handle v2 collection
    v2_exists = await qdrant.collection_exists(V2_COLLECTION)
    
    if clear_first and v2_exists:
        logger.warning(f"⚠️  Clearing existing v2 collection {V2_COLLECTION}")
        if not dry_run:
            await qdrant.delete_collection(V2_COLLECTION)
            v2_exists = False
    
    if not v2_exists:
        logger.info(f"Creating v2 collection {V2_COLLECTION}")
        if not dry_run:
            await qdrant.create_collection(
                collection_name=V2_COLLECTION,
                vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE)
            )
    else:
        v2_info = await qdrant.get_collection(V2_COLLECTION)
        logger.info(f"V2 collection exists with {v2_info.points_count} points")
    
    # Scroll v1 collection
    # NOTE: V1 had multiple named vectors (content, emotion, semantic) but they all
    # represent the same message. We only need payload data - we'll re-embed with v2 model.
    offset = None
    total_migrated = 0
    total_skipped = 0
    batch_size = 50
    seen_messages = set()  # Track unique messages to avoid duplicates
    
    logger.info(f"Starting migration from {V1_COLLECTION} to {V2_COLLECTION}...")
    logger.info(f"Note: V1 had multi-vector per message, v2 uses single vector")
    logger.info(f"Dry run: {dry_run}, Clear first: {clear_first}")
    
    while True:
        points, next_offset = await qdrant.scroll(
            collection_name=V1_COLLECTION,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False  # We'll re-embed with v2 model, don't need v1 vectors
        )
        
        if not points:
            break
        
        logger.info(f"Processing batch of {len(points)} points...")
        
        for point in points:
            payload = point.payload
            
            # Extract v1 fields
            user_id = payload.get("user_id")
            content = payload.get("content")
            
            if not content or not isinstance(content, str) or not content.strip():
                total_skipped += 1
                continue
            
            # Parse timestamp
            timestamp_str = payload.get("timestamp")
            timestamp = datetime.datetime.now()
            if timestamp_str and isinstance(timestamp_str, str):
                try:
                    timestamp = datetime.datetime.fromisoformat(timestamp_str)
                except ValueError:
                    logger.warning(f"Could not parse timestamp {timestamp_str}, using now()")
            
            # Determine role from v1 source
            v1_source = payload.get("source", "user_message")
            if v1_source in ["bot_response", "bot_message"]:
                role = "ai"
                author_is_bot = True
                author_id = CHARACTER_NAME
                author_name = "Aetheris"
            else:
                role = "human"
                author_is_bot = False
                author_id = user_id
                author_name = "User"  # Default, could be enhanced
            
            channel_id = payload.get("channel_id")
            
            # Generate deterministic message_id to prevent duplicates
            # NOTE: Since v1 had the same message in multiple vectors, we need to dedupe
            seed = f"{user_id}_{timestamp.isoformat()}_{content[:100]}"
            message_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, seed))
            
            # Skip if we've already processed this message (v1 multi-vector deduplication)
            if message_id in seen_messages:
                total_skipped += 1
                continue
            seen_messages.add(message_id)
            
            # 1. Save to Postgres
            if not dry_run:
                try:
                    async with db_manager.postgres_pool.acquire() as conn:
                        await conn.execute("""
                            INSERT INTO v2_chat_history 
                            (user_id, character_name, role, content, user_name, channel_id, message_id, 
                             author_id, author_is_bot, metadata, timestamp)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::timestamp)
                            ON CONFLICT (message_id) DO NOTHING
                        """, 
                            str(user_id), 
                            CHARACTER_NAME, 
                            role, 
                            content, 
                            "User",  # Default user_name
                            str(channel_id) if channel_id else None, 
                            message_id,
                            str(author_id),
                            author_is_bot,
                            json.dumps(payload),  # Preserve v1 data
                            timestamp
                        )
                except Exception as e:
                    logger.error(f"Postgres error for msg {message_id}: {e}")
                    total_skipped += 1
                    continue
            
            # 2. Save to Qdrant with v2 schema
            
            # Clean content for embedding
            embed_content = content
            if role == "human":
                embed_content = strip_context_markers(content)
            
            # Chunking (if needed)
            chunks = []
            if len(embed_content) > CHUNK_THRESHOLD:
                chunks = chunk_text(embed_content)
            else:
                chunks = [(embed_content, 0)]
            
            points_to_upsert = []
            
            for chunk_content, chunk_idx in chunks:
                # Re-embed with v2 model
                embedding = await embedding_service.embed_query_async(chunk_content)
                
                # Deterministic vector ID
                vector_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{message_id}_{chunk_idx}"))
                
                # Build v2 payload
                v2_payload = {
                    # Core fields (v2 schema)
                    "type": "conversation",
                    "user_id": str(user_id),
                    "role": role,
                    "content": chunk_content,
                    "timestamp": timestamp.isoformat(),
                    "channel_id": str(channel_id) if channel_id else None,
                    "message_id": message_id,
                    "importance_score": 3,  # Default
                    "source_type": "migration",
                    "user_name": "User",  # Default
                    
                    # Author tracking (ADR-014)
                    "author_id": str(author_id),
                    "author_is_bot": author_is_bot,
                    "author_name": author_name,
                    
                    # Chunk metadata
                    "is_chunk": len(chunks) > 1,
                    "chunk_index": chunk_idx,
                    "chunk_total": len(chunks),
                    "parent_message_id": message_id if len(chunks) > 1 else None,
                    "original_length": len(content),
                    
                    # Preserve v1 emotional analysis (for reference)
                    "v1_emotional_context": payload.get("emotional_context"),
                    "v1_emotional_intensity": payload.get("emotional_intensity"),
                    "v1_significance": payload.get("overall_significance"),
                    "v1_memory_tier": payload.get("memory_tier"),
                    
                    # Full v1 payload preserved
                    "v1_original_payload": payload
                }
                
                points_to_upsert.append(models.PointStruct(
                    id=vector_id,
                    vector=embedding,
                    payload=v2_payload
                ))
            
            if points_to_upsert and not dry_run:
                try:
                    await qdrant.upsert(
                        collection_name=V2_COLLECTION,
                        points=points_to_upsert
                    )
                except Exception as e:
                    logger.error(f"Qdrant error for msg {message_id}: {e}")
                    total_skipped += 1
                    continue
            
            total_migrated += 1
            if total_migrated % 10 == 0:
                print(f"Migrated {total_migrated}/{v1_count} messages... ({total_skipped} skipped)", end='\r')
        
        offset = next_offset
        if offset is None:
            break
    
    print()  # Newline after progress
    logger.info(f"✅ Migration complete!")
    logger.info(f"   Total migrated: {total_migrated}")
    logger.info(f"   Total skipped: {total_skipped}")
    logger.info(f"   Dry run: {dry_run}")
    
    if not dry_run:
        # Verify v2 collection
        v2_info = await qdrant.get_collection(V2_COLLECTION)
        logger.info(f"   V2 collection now has: {v2_info.points_count} points")
    
    await db_manager.close_all()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate aetheris from v1 to v2 schema")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be migrated without writing")
    parser.add_argument("--clear-first", action="store_true", help="Clear v2 collection before migration")
    
    args = parser.parse_args()
    
    if args.clear_first:
        confirm = input("⚠️  This will DELETE all existing v2 data. Type 'yes' to continue: ")
        if confirm.lower() != "yes":
            print("Aborted.")
            sys.exit(0)
    
    asyncio.run(migrate(dry_run=args.dry_run, clear_first=args.clear_first))
