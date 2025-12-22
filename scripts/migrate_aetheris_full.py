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

async def migrate():
    # Initialize connections
    logger.info("Initializing connections...")
    await db_manager.connect_postgres()
    
    qdrant = AsyncQdrantClient(url=settings.QDRANT_URL)
    embedding_service = EmbeddingService()
    
    # Ensure v2 collection exists
    exists = await qdrant.collection_exists(V2_COLLECTION)
    if not exists:
        logger.info(f"Creating v2 collection {V2_COLLECTION}")
        await qdrant.create_collection(
            collection_name=V2_COLLECTION,
            vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE)
        )
    
    # Scroll v1 collection
    offset = None
    total_migrated = 0
    
    logger.info(f"Starting migration from {V1_COLLECTION} to {V2_COLLECTION}...")
    
    while True:
        points, next_offset = await qdrant.scroll(
            collection_name=V1_COLLECTION,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False
        )
        
        if not points:
            break
            
        for point in points:
            payload = point.payload
            
            # Extract fields
            user_id = payload.get("user_id")
            content = payload.get("content")
            if not content or not isinstance(content, str) or not content.strip():
                continue
            
            timestamp_str = payload.get("timestamp")
            timestamp = datetime.datetime.now()
            if timestamp_str and isinstance(timestamp_str, str):
                try:
                    timestamp = datetime.datetime.fromisoformat(timestamp_str)
                except ValueError:
                    logger.warning(f"Could not parse timestamp {timestamp_str}, using now()")
            v1_role = payload.get("role")
            channel_id = payload.get("channel_id")
            
            # Map role
            role = "ai" if v1_role in ["assistant", "ai"] else "human"
            if v1_role == "system": role = "system"
            
            # Generate deterministic IDs to prevent duplicates on re-runs
            # Use content + timestamp + user_id as seed
            seed = f"{user_id}_{timestamp.isoformat()}_{content}"
            message_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, seed))
            
            # Author info
            author_is_bot = (role == "ai")
            author_id = CHARACTER_NAME if author_is_bot else user_id
            
            # 1. Save to Postgres
            try:
                async with db_manager.postgres_pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO v2_chat_history 
                        (user_id, character_name, role, content, user_name, channel_id, message_id, author_id, author_is_bot, metadata, timestamp)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::timestamp)
                        ON CONFLICT (message_id) DO NOTHING
                    """, 
                        str(user_id), 
                        CHARACTER_NAME, 
                        role, 
                        content, 
                        "User", # Default
                        str(channel_id) if channel_id else None, 
                        message_id,
                        str(author_id),
                        author_is_bot,
                        json.dumps(payload), # Store original payload as metadata
                        timestamp
                    )
            except Exception as e:
                logger.error(f"Postgres error for msg {message_id}: {e}")
                continue

            # 2. Save to Qdrant (with chunking and timestamp preservation)
            
            # Clean content for embedding if human
            embed_content = content
            if role == "human":
                embed_content = strip_context_markers(content)
            
            # Chunking
            chunks = []
            if len(embed_content) > CHUNK_THRESHOLD:
                chunks = chunk_text(embed_content)
            else:
                chunks = [(embed_content, 0)]
                
            points_to_upsert = []
            
            for chunk_content, chunk_idx in chunks:
                embedding = await embedding_service.embed_query_async(chunk_content)
                # Deterministic vector ID based on message_id and chunk index
                vector_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{message_id}_{chunk_idx}"))
                
                chunk_payload = {
                    "type": "conversation",
                    "user_id": str(user_id),
                    "role": role,
                    "content": chunk_content,
                    "timestamp": timestamp, # Preserved timestamp
                    "channel_id": str(channel_id) if channel_id else None,
                    "message_id": message_id,
                    "importance_score": 3, # Default
                    "source_type": "migration",
                    "author_id": str(author_id),
                    "author_is_bot": author_is_bot,
                    "chunk_index": chunk_idx,
                    "total_chunks": len(chunks),
                    "original_payload": payload
                }
                
                points_to_upsert.append(models.PointStruct(
                    id=vector_id,
                    vector=embedding,
                    payload=chunk_payload
                ))
            
            if points_to_upsert:
                await qdrant.upsert(
                    collection_name=V2_COLLECTION,
                    points=points_to_upsert
                )
            
            total_migrated += 1
            if total_migrated % 10 == 0:
                print(f"Migrated {total_migrated} messages...", end='\r')
        
        offset = next_offset
        if offset is None:
            break
            
    logger.info(f"\nMigration complete! Total messages: {total_migrated}")

if __name__ == "__main__":
    asyncio.run(migrate())
