import asyncio
from typing import Optional
from qdrant_client import AsyncQdrantClient
from neo4j import AsyncGraphDatabase, AsyncDriver
import asyncpg
import redis.asyncio as redis
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import WriteOptions
from loguru import logger
from functools import wraps

from src_v2.config.settings import settings

def retry_db_operation(max_retries: int = 3, delay: int = 1):
    """
    Decorator to retry async database operations.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"Operation {func.__name__} failed after {max_retries} attempts: {e}")
                        raise
                    logger.warning(f"Operation {func.__name__} failed (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {delay * (attempt + 1)}s...")
                    await asyncio.sleep(delay * (attempt + 1))
        return wrapper
    return decorator

class DatabaseManager:
    def __init__(self):
        self.postgres_pool: Optional[asyncpg.Pool] = None
        self.qdrant_client: Optional[AsyncQdrantClient] = None
        self.neo4j_driver: Optional[AsyncDriver] = None
        self.influxdb_client: Optional[InfluxDBClient] = None
        self.influxdb_write_api = None
        self.redis_client: Optional[redis.Redis] = None

    async def _connect_with_retry(self, name: str, connect_func, max_retries: int = 5, delay: int = 2):
        """Helper to connect to a database with retry logic."""
        for attempt in range(max_retries):
            try:
                await connect_func()
                return
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to connect to {name} after {max_retries} attempts: {e}")
                    raise
                logger.warning(f"Failed to connect to {name} (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {delay}s...")
                await asyncio.sleep(delay)

    async def connect_postgres(self):
        async def _connect():
            logger.info(f"Connecting to PostgreSQL at {settings.POSTGRES_URL}...")
            self.postgres_pool = await asyncpg.create_pool(settings.POSTGRES_URL)
            logger.info("Connected to PostgreSQL.")
        
        await self._connect_with_retry("PostgreSQL", _connect)

    async def connect_redis(self):
        async def _connect():
            logger.info(f"Connecting to Redis at {settings.REDIS_URL}...")
            self.redis_client = redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
            await self.redis_client.ping()
            logger.info("Connected to Redis.")

        await self._connect_with_retry("Redis", _connect)

    async def connect_qdrant(self):
        async def _connect():
            logger.info(f"Connecting to Qdrant at {settings.QDRANT_URL}...")
            # Use AsyncQdrantClient for non-blocking operations
            self.qdrant_client = AsyncQdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY.get_secret_value() if settings.QDRANT_API_KEY else None
            )
            # Verify connection
            await self.qdrant_client.get_collections()
            logger.info("Connected to Qdrant.")

        await self._connect_with_retry("Qdrant", _connect)

    async def connect_neo4j(self):
        async def _connect():
            logger.info(f"Connecting to Neo4j at {settings.NEO4J_URL}...")
            auth = (settings.NEO4J_USER, settings.NEO4J_PASSWORD.get_secret_value())
            self.neo4j_driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URL, 
                auth=auth,
                notifications_disabled_categories=['UNRECOGNIZED']
            )
            # Verify connection
            await self.neo4j_driver.verify_connectivity()
            logger.info("Connected to Neo4j.")

        await self._connect_with_retry("Neo4j", _connect)

    async def connect_influxdb(self):
        try:
            logger.info(f"Connecting to InfluxDB at {settings.INFLUXDB_URL}...")
            self.influxdb_client = InfluxDBClient(
                url=settings.INFLUXDB_URL,
                token=settings.INFLUXDB_TOKEN.get_secret_value() if settings.INFLUXDB_TOKEN else None,
                org=settings.INFLUXDB_ORG
            )
            # Create write API (synchronous but fast enough for batching, or we can use async client if needed)
            # For now, using synchronous write_api with batching
            self.influxdb_write_api = self.influxdb_client.write_api(write_options=WriteOptions(batch_size=1))
            
            # Verify connection (run ping in thread pool to avoid blocking)
            loop = asyncio.get_event_loop()
            is_healthy = await loop.run_in_executor(None, self.influxdb_client.ping)
            if not is_healthy:
                logger.warning("InfluxDB ping failed. Metrics will not be recorded.")
                self.influxdb_client = None
                self.influxdb_write_api = None
            else:
                logger.info("Connected to InfluxDB.")
        except Exception as e:
            logger.warning(f"Failed to connect to InfluxDB: {e}. Metrics will not be recorded.")
            self.influxdb_client = None
            self.influxdb_write_api = None

    async def connect_all(self):
        await asyncio.gather(
            self.connect_postgres(),
            self.connect_redis(),
            self.connect_qdrant(),
            self.connect_neo4j(),
            self.connect_influxdb()
        )

    async def disconnect_all(self):
        logger.info("Disconnecting from databases...")
        if self.postgres_pool:
            await self.postgres_pool.close()
        if self.neo4j_driver:
            await self.neo4j_driver.close()
        if self.qdrant_client:
            await self.qdrant_client.close()
        if self.redis_client:
            await self.redis_client.close()
        if self.influxdb_client:
            self.influxdb_client.close()
        logger.info("Disconnected from databases.")

# Global database manager instance
db_manager = DatabaseManager()
