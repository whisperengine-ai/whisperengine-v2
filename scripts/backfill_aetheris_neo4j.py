import asyncio
import sys
from pathlib import Path
from loguru import logger
import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from qdrant_client import AsyncQdrantClient
from neo4j import AsyncGraphDatabase
from src_v2.config.settings import settings

V2_COLLECTION = "whisperengine_memory_aetheris"
BOT_NAME = "aetheris"

async def backfill():
    logger.info("Starting Neo4j backfill for Aetheris...")
    
    # Connect Qdrant
    qdrant = AsyncQdrantClient(url=settings.QDRANT_URL)
    
    # Connect Neo4j
    driver = AsyncGraphDatabase.driver(
        settings.NEO4J_URL, 
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD.get_secret_value())
    )
    
    # Verify connection
    try:
        await driver.verify_connectivity()
        logger.info("Connected to Neo4j.")
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {e}")
        return

    offset = None
    count = 0
    
    query = """
    MERGE (u:User {id: $user_id})
    ON CREATE SET u.is_bot = false
    MERGE (m:Memory {id: $vector_id})
    ON CREATE SET 
        m.name = $name,
        m.content = $content,
        m.timestamp = $timestamp,
        m.source_type = $source_type,
        m.bot_name = $bot_name,
        m.author_id = $author_id,
        m.author_is_bot = $author_is_bot
    MERGE (u)-[:HAS_MEMORY]->(m)
    
    WITH m
    WHERE $author_id IS NOT NULL AND $author_id <> $user_id
    MERGE (a:User {id: $author_id})
    ON CREATE SET a.is_bot = $author_is_bot
    MERGE (a)-[:AUTHORED]->(m)
    """
    
    async with driver.session() as session:
        while True:
            points, next_offset = await qdrant.scroll(
                collection_name=V2_COLLECTION,
                limit=100,
                offset=offset,
                with_payload=True
            )
            
            if not points:
                break
                
            for point in points:
                payload = point.payload
                vector_id = point.id
                
                user_id = payload.get("user_id")
                content = payload.get("content", "")
                timestamp_str = payload.get("timestamp")
                source_type = payload.get("source_type", "migration")
                author_id = payload.get("author_id", user_id)
                author_is_bot = payload.get("author_is_bot", False)
                
                # Create human-readable name
                memory_name = content[:50].strip() if content else "memory"
                if len(content) > 50:
                    memory_name += "..."
                
                # Ensure timestamp is string for Neo4j (or datetime if driver supports it, but string is safer for ISO)
                if isinstance(timestamp_str, datetime.datetime):
                    timestamp_str = timestamp_str.isoformat()
                
                try:
                    await session.run(
                        query,
                        user_id=str(user_id),
                        vector_id=str(vector_id),
                        name=memory_name,
                        content=content,
                        timestamp=timestamp_str,
                        source_type=source_type,
                        bot_name=BOT_NAME,
                        author_id=str(author_id),
                        author_is_bot=author_is_bot
                    )
                    count += 1
                    if count % 100 == 0:
                        print(f"Backfilled {count} memories...", end='\r')
                except Exception as e:
                    logger.error(f"Error processing point {vector_id}: {e}")
            
            offset = next_offset
            if offset is None:
                break
    
    logger.info(f"\nBackfill complete! Processed {count} memories.")
    await driver.close()

if __name__ == "__main__":
    asyncio.run(backfill())
