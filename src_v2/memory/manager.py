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
    async def add_message(self, user_id: str, character_name: str, role: str, content: str, user_name: Optional[str] = None, channel_id: str = None, message_id: str = None, metadata: Dict[str, Any] = None, importance_score: int = 3):
        """
        Adds a message to the history.
        role: 'human' or 'ai'
        importance_score: 1-10 scale of how important this message is (default 3 for raw chat)
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
                message_id=message_id,
                importance_score=importance_score
            )
            
        except Exception as e:
            logger.error(f"Failed to save message: {e}")

    @retry_db_operation(max_retries=3)
    async def _save_vector_memory(self, user_id: str, role: str, content: str, metadata: Optional[Dict[str, Any]] = None, channel_id: Optional[str] = None, message_id: Optional[str] = None, collection_name: Optional[str] = None, importance_score: int = 3):
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
                "message_id": str(message_id) if message_id else None,
                "importance_score": importance_score
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
        Searches for relevant episode memories in Qdrant with recency weighting.
        
        Weighted Score = Semantic × Recency
        - Semantic: Raw cosine similarity (0-1)  
        - Recency: Exponential decay (1.0 for today → 0.5 for 7 days ago for episodes)
        
        Episodes decay faster than summaries since they're raw conversation fragments.
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
            
            # Fetch more for re-ranking
            fetch_limit = max(limit * 3, 15)
            
            search_result = await db_manager.qdrant_client.query_points(
                collection_name=target_collection,
                query=embedding,
                query_filter=Filter(must=must_conditions),
                limit=fetch_limit
            )
            
            logger.debug(f"Found {len(search_result.points)} memory results for re-ranking")
            
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

            # === WEIGHTED SCORING FOR EPISODES ===
            now = datetime.datetime.now()
            results = []
            
            for hit in search_result.points:
                semantic_score = hit.score
                ts_str = hit.payload.get("timestamp") if hit.payload else None
                
                # Recency: Episodes decay faster (7-day half-life vs 30-day for summaries)
                recency_multiplier = 1.0
                if ts_str:
                    try:
                        dt = datetime.datetime.fromisoformat(str(ts_str))
                        age_days = (now - dt).total_seconds() / 86400
                        # Floor at 0.2 for episodes (they fade more than summaries)
                        recency_multiplier = max(0.2, 0.5 ** (age_days / 7.0))
                    except Exception:
                        pass
                
                # Importance: 1-10 → 0.5-1.0 (default 3 -> 0.65)
                payload = hit.payload or {}
                raw_importance = payload.get("importance_score", 3)
                importance_multiplier = 0.5 + (raw_importance / 20.0)

                weighted_score = semantic_score * recency_multiplier * importance_multiplier
                
                results.append({
                    "id": hit.id,
                    "content": payload.get("content"),
                    "role": payload.get("role"),
                    "score": weighted_score,
                    "semantic_score": semantic_score,
                    "recency_multiplier": round(recency_multiplier, 3),
                    "importance_multiplier": round(importance_multiplier, 3),
                    "timestamp": ts_str,
                    "relative_time": get_relative_time(ts_str) if ts_str else "unknown time"
                })
            
            # Re-rank by weighted score
            results.sort(key=lambda x: x["score"], reverse=True)
            
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Failed to search memories: {e}")
            return []

    async def search_summaries(self, query: str, user_id: str, limit: int = 3, start_timestamp: Optional[float] = None, collection_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Searches for relevant summaries in Qdrant with weighted scoring.
        
        Weighted Score = Semantic × Meaningfulness × Recency
        - Semantic: Raw cosine similarity (0-1)
        - Meaningfulness: Normalized from 1-10 scale → 0.5-1.0 (important memories never fully suppressed)
        - Recency: Exponential decay based on age (1.0 for today → 0.5 for 30 days ago)
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
            
            # Fetch more results to allow for re-ranking
            fetch_limit = max(limit * 3, 10)

            search_result = await db_manager.qdrant_client.query_points(
                collection_name=target_collection,
                query=embedding,
                query_filter=Filter(must=must_conditions),
                limit=fetch_limit
            )
            
            logger.debug(f"Found {len(search_result.points)} summary results for re-ranking")
            
            now = datetime.datetime.now()
            results = []
            
            for hit in search_result.points:
                # Parse timestamp from payload
                ts_str = hit.payload.get("timestamp")
                
                # Post-retrieval filtering for safety
                if start_timestamp and ts_str:
                    try:
                        dt = datetime.datetime.fromisoformat(str(ts_str))
                        if dt.timestamp() < start_timestamp:
                            continue
                    except Exception:
                        pass
                
                # === WEIGHTED SCORING ===
                semantic_score = hit.score  # 0-1 (cosine similarity)
                
                # Meaningfulness: 1-10 → 0.5-1.0 (floor of 0.5 so important memories never vanish)
                raw_meaningfulness = hit.payload.get("meaningfulness_score", 5)
                meaningfulness_multiplier = 0.5 + (raw_meaningfulness / 20.0)  # 1→0.55, 5→0.75, 10→1.0
                
                # Recency: Exponential decay with 30-day half-life
                recency_multiplier = 1.0
                if ts_str:
                    try:
                        dt = datetime.datetime.fromisoformat(str(ts_str))
                        age_days = (now - dt).total_seconds() / 86400
                        # Decay: 1.0 at day 0, ~0.5 at day 30, ~0.25 at day 60
                        # Floor at 0.3 so old memories can still surface if highly relevant
                        recency_multiplier = max(0.3, 0.5 ** (age_days / 30.0))
                    except Exception:
                        pass
                
                # Combined weighted score
                weighted_score = semantic_score * meaningfulness_multiplier * recency_multiplier

                results.append({
                    "content": hit.payload.get("content"),
                    "score": weighted_score,
                    "semantic_score": semantic_score,
                    "meaningfulness": raw_meaningfulness,
                    "recency_multiplier": round(recency_multiplier, 3),
                    "timestamp": ts_str,
                    "relative_time": get_relative_time(ts_str) if ts_str else "unknown time"
                })
            
            # Re-rank by weighted score
            results.sort(key=lambda x: x["score"], reverse=True)
            
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
