from typing import List, Dict, Any, Optional
import uuid
import datetime
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from loguru import logger
from qdrant_client.models import VectorParams, Distance, PointStruct, Filter, FieldCondition, MatchValue
from src_v2.core.database import db_manager, retry_db_operation
from src_v2.config.settings import settings
from src_v2.memory.embeddings import EmbeddingService
from src_v2.utils.time_utils import get_relative_time
from influxdb_client import Point
import time

class MemoryManager:
    def __init__(self, bot_name: Optional[str] = None):
        name = bot_name or settings.DISCORD_BOT_NAME
        self.collection_name = f"whisperengine_memory_{name}" if name else "whisperengine_memory_default"
        self.embedding_service = EmbeddingService()

    async def initialize(self):
        """
        Creates the necessary tables and collections if they don't exist.
        """
        await self._initialize_postgres()
        await self._initialize_qdrant()

    async def _initialize_postgres(self):
        if not db_manager.postgres_pool:
            logger.warning("Postgres pool not available, memory persistence disabled.")
            return
            
        # We now use Alembic for schema management.
        # This method just verifies connectivity.
        try:
            async with db_manager.postgres_pool.acquire() as conn:
                await conn.execute("SELECT 1")
            logger.info("Postgres connection verified.")
        except Exception as e:
            logger.error(f"Postgres connection failed: {e}")

    async def _initialize_qdrant(self):
        if not db_manager.qdrant_client:
            logger.warning("Qdrant client not available, vector memory disabled.")
            return
            
        try:
            # Check if collection exists
            collections_response = await db_manager.qdrant_client.get_collections()
            collections = collections_response.collections
            exists = any(c.name == self.collection_name for c in collections)
            
            if not exists:
                logger.info(f"Creating Qdrant collection: {self.collection_name}")
                
                # Define single vector configuration
                # We use a single unnamed vector for content
                vectors_config = VectorParams(size=384, distance=Distance.COSINE)
                
                await db_manager.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=vectors_config
                )
                logger.info("Qdrant collection initialized with single vector.")
            else:
                logger.info(f"Qdrant collection {self.collection_name} already exists.")
                
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant: {e}")

    @retry_db_operation(max_retries=3)
    async def add_message(self, user_id: str, character_name: str, role: str, content: str, user_name: Optional[str] = None, channel_id: str = None, message_id: str = None, metadata: Dict[str, Any] = None):
        """
        Adds a message to the history.
        role: 'human' or 'ai'
        """
        if not db_manager.postgres_pool:
            return

        try:
            async with db_manager.postgres_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO v2_chat_history (user_id, character_name, role, content, user_name, channel_id, message_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, str(user_id), character_name, role, content, user_name or "User", str(channel_id) if channel_id else None, str(message_id) if message_id else None)
            
            # Also save to vector memory
            await self._save_vector_memory(
                user_id=user_id, 
                role=role, 
                content=content, 
                metadata=metadata,
                channel_id=channel_id, 
                message_id=message_id
            )
            
        except Exception as e:
            logger.error(f"Failed to save message: {e}")

    @retry_db_operation(max_retries=3)
    async def _save_vector_memory(self, user_id: str, role: str, content: str, metadata: Optional[Dict[str, Any]] = None, channel_id: Optional[str] = None, message_id: Optional[str] = None, collection_name: Optional[str] = None):
        """
        Embeds and saves a memory to Qdrant.
        """
        start_time = time.time()
        if not db_manager.qdrant_client:
            return

        try:
            # Generate embedding
            embedding = await self.embedding_service.embed_query_async(content)
            
            # Prepare payload
            payload = {
                "user_id": str(user_id),
                "role": role,
                "content": content,
                "timestamp": datetime.datetime.now().isoformat(),
                "channel_id": str(channel_id) if channel_id else None,
                "message_id": str(message_id) if message_id else None
            }
            
            if metadata:
                payload.update(metadata)
            
            # Upsert to Qdrant
            target_collection = collection_name or self.collection_name
            
            await db_manager.qdrant_client.upsert(
                collection_name=target_collection,
                points=[
                    PointStruct(
                        id=str(uuid.uuid4()),
                        vector=embedding,
                        payload=payload
                    )
                ]
            )
            
            # Log metrics
            if db_manager.influxdb_write_api:
                try:
                    duration_ms = (time.time() - start_time) * 1000
                    point = Point("memory_latency") \
                        .tag("user_id", user_id) \
                        .tag("operation", "write") \
                        .field("duration_ms", duration_ms) \
                        .time(datetime.datetime.utcnow())
                    
                    db_manager.influxdb_write_api.write(
                        bucket=settings.INFLUXDB_BUCKET,
                        org=settings.INFLUXDB_ORG,
                        record=point
                    )
                except Exception as e:
                    logger.error(f"Failed to log memory metrics: {e}")
            
        except Exception as e:
            logger.error(f"Failed to save vector memory: {e}")
            raise e

    async def save_summary_vector(self, session_id: str, user_id: str, content: str, meaningfulness_score: int, emotions: List[str], collection_name: Optional[str] = None) -> Optional[str]:
        """
        Embeds and saves a summary to Qdrant.
        """
        if not db_manager.qdrant_client:
            return None

        target_collection = collection_name or self.collection_name

        try:
            # Generate embedding
            embedding = await self.embedding_service.embed_query_async(content)
            point_id = str(uuid.uuid4())
            
            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "type": "summary",
                    "session_id": str(session_id),
                    "user_id": str(user_id),
                    "content": content,
                    "meaningfulness_score": meaningfulness_score,
                    "emotions": emotions,
                    "timestamp": datetime.datetime.now().isoformat()
                }
            )
            
            await db_manager.qdrant_client.upsert(
                collection_name=target_collection,
                points=[point]
            )
            
            return point_id
            
        except Exception as e:
            logger.error(f"Failed to save summary vector: {e}")
            return None

    async def search_memories(self, query: str, user_id: str, limit: int = 5, collection_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Searches for relevant memories in Qdrant.
        """
        start_time = time.time()
        if not db_manager.qdrant_client:
            logger.warning("Qdrant client not available for search_memories")
            return []

        target_collection = collection_name or self.collection_name

        try:
            logger.debug(f"Searching memories for user {user_id} with query: {query}")
            embedding = await self.embedding_service.embed_query_async(query)
            
            # Build Filter
            must_conditions = [
                FieldCondition(key="user_id", match=MatchValue(value=str(user_id)))
            ]
            
            search_result = await db_manager.qdrant_client.query_points(
                collection_name=target_collection,
                query=embedding,
                query_filter=Filter(must=must_conditions),
                limit=limit
            )
            
            logger.debug(f"Found {len(search_result.points)} memory results")
            
            # Log metrics
            if db_manager.influxdb_write_api:
                try:
                    duration_ms = (time.time() - start_time) * 1000
                    point = Point("memory_latency") \
                        .tag("user_id", user_id) \
                        .tag("operation", "read") \
                        .field("duration_ms", duration_ms) \
                        .field("result_count", len(search_result.points)) \
                        .time(datetime.datetime.utcnow())
                    
                    db_manager.influxdb_write_api.write(
                        bucket=settings.INFLUXDB_BUCKET,
                        org=settings.INFLUXDB_ORG,
                        record=point
                    )
                except Exception as e:
                    logger.error(f"Failed to log memory metrics: {e}")

            return [
                {
                    "id": hit.id,
                    "content": hit.payload.get("content") if hit.payload else None,
                    "role": hit.payload.get("role") if hit.payload else None,
                    "score": hit.score,
                    "timestamp": hit.payload.get("timestamp") if hit.payload else None,
                    "relative_time": get_relative_time(hit.payload.get("timestamp")) if (hit.payload and hit.payload.get("timestamp")) else "unknown time"  # type: ignore[arg-type]
                }
                for hit in search_result.points
            ]
            
        except Exception as e:
            logger.error(f"Failed to search memories: {e}")
            return []

    async def search_summaries(self, query: str, user_id: str, limit: int = 3, start_timestamp: Optional[float] = None, collection_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Searches for relevant summaries in Qdrant.
        """
        if not db_manager.qdrant_client:
            logger.warning("Qdrant client not available for search_summaries")
            return []

        target_collection = collection_name or self.collection_name

        try:
            logger.debug(f"Searching summaries for user {user_id} with query: {query}")
            embedding = await self.embedding_service.embed_query_async(query)
            
            # Build Filter
            must_conditions = [
                FieldCondition(key="user_id", match=MatchValue(value=str(user_id))),
                FieldCondition(key="type", match=MatchValue(value="summary"))
            ]
            
            # Add Time Filter if provided
            if start_timestamp:
                # Assuming 'timestamp' field in Qdrant is stored as ISO string or float.
                # Based on add_summary, it seems to be ISO string. Qdrant Range filter works on numbers.
                # If it's a string, we can't easily range filter without converting schema.
                # Let's check how it's stored. 
                # If it's stored as string, we might need to filter in Python (post-retrieval) or rely on Qdrant's datetime support (if enabled).
                # For safety/simplicity in this defensive pass, let's filter in Python if we can't be sure of Qdrant schema.
                pass 

            search_result = await db_manager.qdrant_client.query_points(
                collection_name=target_collection,
                query=embedding,
                query_filter=Filter(must=must_conditions),
                limit=limit * 2 if start_timestamp else limit # Fetch more if we plan to filter
            )
            
            logger.debug(f"Found {len(search_result.points)} summary results")
            
            results = []
            for hit in search_result.points:
                # Parse timestamp from payload
                ts_str = hit.payload.get("timestamp")
                
                # Post-retrieval filtering for safety
                if start_timestamp and ts_str:
                    try:
                        # Handle "2023-01-01T12:00:00" format
                        dt = datetime.datetime.fromisoformat(str(ts_str))
                        if dt.timestamp() < start_timestamp:
                            continue
                    except Exception:
                        pass # If parsing fails, include it to be safe

                results.append({
                    "content": hit.payload.get("content"),
                    "score": hit.score,
                    "meaningfulness": hit.payload.get("meaningfulness_score"),
                    "timestamp": ts_str,
                    "relative_time": get_relative_time(ts_str) if ts_str else "unknown time"
                })
            
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Failed to search summaries: {e}")
            return []

    async def clear_memory(self, user_id: str, character_name: str):
        """
        Clears all memory for a specific user and character from both Postgres and Qdrant.
        """
        # 1. Clear Postgres
        if db_manager.postgres_pool:
            try:
                async with db_manager.postgres_pool.acquire() as conn:
                    await conn.execute("""
                        DELETE FROM v2_chat_history 
                        WHERE user_id = $1 AND character_name = $2
                    """, str(user_id), character_name)
                logger.info(f"Cleared Postgres history for user {user_id} and character {character_name}")
            except Exception as e:
                logger.error(f"Failed to clear Postgres history: {e}")

        # 2. Clear Qdrant
        if db_manager.qdrant_client:
            try:
                await db_manager.qdrant_client.delete(
                    collection_name=self.collection_name,
                    points_selector=Filter(
                        must=[
                            FieldCondition(
                                key="user_id",
                                match=MatchValue(value=str(user_id))
                            )
                        ]
                    )
                )
                logger.info(f"Cleared Qdrant memory for user {user_id}")
            except Exception as e:
                logger.error(f"Failed to clear Qdrant memory: {e}")

    async def get_recent_history(self, user_id: str, character_name: str, limit: int = 10, channel_id: str = None) -> List[BaseMessage]:
        """
        Retrieves the recent chat history for a user and character.
        If channel_id is provided, retrieves history for that channel (group chat context).
        """
        if not db_manager.postgres_pool:
            return []

        messages = []
        try:
            async with db_manager.postgres_pool.acquire() as conn:
                if channel_id:
                    # Fetch by channel_id (Group Context)
                    rows = await conn.fetch("""
                        SELECT role, content, user_id, user_name 
                        FROM v2_chat_history 
                        WHERE channel_id = $1 AND character_name = $2
                        ORDER BY timestamp DESC
                        LIMIT $3
                    """, str(channel_id), character_name, limit)
                else:
                    # Fetch by user_id (DM Context)
                    rows = await conn.fetch("""
                        SELECT role, content, user_id, user_name 
                        FROM v2_chat_history 
                        WHERE user_id = $1 AND character_name = $2
                        ORDER BY timestamp DESC
                        LIMIT $3
                    """, str(user_id), character_name, limit)
                
                # Reverse to get chronological order
                for row in reversed(rows):
                    if row['role'] == 'human':
                        content = row['content']
                        
                        # In group contexts (channel_id present), distinguish other users
                        if channel_id and row['user_id'] != str(user_id):
                            display_name = row['user_name'] or f"User {row['user_id']}"
                            content = f"[{display_name}]: {content}"
                            
                        messages.append(HumanMessage(content=content))
                    elif row['role'] == 'ai':
                        messages.append(AIMessage(content=row['content']))
                        
        except Exception as e:
            logger.error(f"Failed to retrieve history: {e}")
            
        return messages

    async def count_messages_since(self, user_id: str, character_name: str, timestamp: datetime.datetime) -> int:
        """Counts messages since a given timestamp."""
        if not db_manager.postgres_pool:
            return 0
        
        try:
            # Ensure timestamp is offset-aware (UTC) if it's naive
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=datetime.timezone.utc)
            else:
                # Convert to UTC if it has a timezone
                timestamp = timestamp.astimezone(datetime.timezone.utc)

            # The database column is TIMESTAMP WITHOUT TIME ZONE (naive)
            # So we must pass a naive datetime (implicitly UTC)
            timestamp_naive = timestamp.replace(tzinfo=None)

            async with db_manager.postgres_pool.acquire() as conn:
                count = await conn.fetchval("""
                    SELECT COUNT(*) 
                    FROM v2_chat_history 
                    WHERE user_id = $1 AND character_name = $2 AND timestamp >= $3
                """, user_id, character_name, timestamp_naive)
                return count
        except Exception as e:
            logger.error(f"Failed to count messages: {e}")
            return 0

# Global instance
memory_manager = MemoryManager()
