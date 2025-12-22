import asyncio
import sys
from pathlib import Path
from loguru import logger

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from qdrant_client import AsyncQdrantClient
from src_v2.core.database import db_manager
from src_v2.config.settings import settings

async def verify():
    await db_manager.connect_postgres()
    qdrant = AsyncQdrantClient(url=settings.QDRANT_URL)
    
    # Check Postgres
    async with db_manager.postgres_pool.acquire() as conn:
        pg_count = await conn.fetchval("SELECT COUNT(*) FROM v2_chat_history WHERE character_name = 'aetheris'")
        logger.info(f"Postgres count for aetheris: {pg_count}")
        
        # Sample a message
        sample = await conn.fetchrow("SELECT * FROM v2_chat_history WHERE character_name = 'aetheris' LIMIT 1")
        logger.info(f"Sample Postgres message: {dict(sample) if sample else 'None'}")

    # Check Qdrant
    qdrant_count = (await qdrant.count(collection_name="whisperengine_memory_aetheris")).count
    logger.info(f"Qdrant count for whisperengine_memory_aetheris: {qdrant_count}")
    
    # Sample a point
    points, _ = await qdrant.scroll(
        collection_name="whisperengine_memory_aetheris",
        limit=1,
        with_payload=True
    )
    if points:
        logger.info(f"Sample Qdrant payload: {points[0].payload}")

if __name__ == "__main__":
    asyncio.run(verify())
