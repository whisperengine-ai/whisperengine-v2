from typing import List, Dict, Any, Optional
import uuid
import datetime
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from loguru import logger
from qdrant_client.models import VectorParams, Distance, PointStruct, Filter, FieldCondition, MatchValue, Range
from src_v2.core.database import db_manager, retry_db_operation, require_db
from src_v2.config.settings import settings
from src_v2.memory.embeddings import EmbeddingService
from src_v2.utils.time_utils import get_relative_time
from src_v2.memory.models import MemorySourceType
from src_v2.memory import scoring
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

            # --- Initialize Shared Artifacts Collection (Phase E13) ---
            if settings.ENABLE_STIGMERGIC_DISCOVERY:
                from src_v2.memory.shared_artifacts import SharedArtifactManager
                shared_collection = SharedArtifactManager.COLLECTION_NAME
                shared_exists = any(c.name == shared_collection for c in collections)
                
                if not shared_exists:
                    logger.info(f"Creating Shared Artifacts collection: {shared_collection}")
                    vectors_config = VectorParams(size=384, distance=Distance.COSINE)
                    await db_manager.qdrant_client.create_collection(
                        collection_name=shared_collection,
                        vectors_config=vectors_config
                    )
                    logger.info("Shared Artifacts collection initialized.")
                
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant: {e}")

    @require_db("postgres")
    @retry_db_operation(max_retries=3)
    async def add_message(self, user_id: str, character_name: str, role: str, content: str, user_name: Optional[str] = None, channel_id: str = None, message_id: str = None, metadata: Dict[str, Any] = None, importance_score: int = 3, source_type: Optional[MemorySourceType] = None):
        """
        Adds a message to the history.
        role: 'human' or 'ai'
        importance_score: 1-10 scale of how important this message is (default 3 for raw chat)
        """
        try:
            async with db_manager.postgres_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO v2_chat_history (user_id, character_name, role, content, user_name, channel_id, message_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (message_id) DO NOTHING
                """, str(user_id), character_name, role, content, user_name or "User", str(channel_id) if channel_id else None, str(message_id) if message_id else None)
            
            # Also save to vector memory
            # Derive collection name from character_name to support cross-bot operations (e.g., gossip injection)
            target_collection = f"whisperengine_memory_{character_name}" if character_name else self.collection_name
            await self._save_vector_memory(
                user_id=user_id, 
                role=role, 
                content=content, 
                metadata=metadata,
                channel_id=channel_id, 
                message_id=message_id,
                collection_name=target_collection,
                importance_score=importance_score,
                source_type=source_type
            )
            
        except Exception as e:
            logger.error(f"Failed to save message: {e}")

    async def save_typed_memory(
        self,
        user_id: str,
        memory_type: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        collection_name: Optional[str] = None,
        importance_score: int = 3,
        source_type: Optional[MemorySourceType] = None
    ) -> None:
        """
        Public method to save typed memories (epiphanies, reasoning traces, patterns, etc.).
        
        This is the preferred method for storing special memory types from tools.
        Use this instead of calling _save_vector_memory directly.
        
        Args:
            user_id: The user ID associated with this memory
            memory_type: Type of memory (epiphany, reasoning_trace, response_pattern, etc.)
            content: The memory content
            metadata: Additional metadata to store
            collection_name: Optional override for collection name
            importance_score: Importance score (1-5, default 3)
            source_type: Source of the memory (human, inference, dream, gossip)
        """
        full_metadata = metadata or {}
        full_metadata["type"] = memory_type
        
        await self._save_vector_memory(
            user_id=user_id,
            role=memory_type,
            content=content,
            metadata=full_metadata,
            collection_name=collection_name,
            importance_score=importance_score,
            source_type=source_type
        )

    @require_db("qdrant")
    @retry_db_operation(max_retries=3)
    async def _save_vector_memory(self, user_id: str, role: str, content: str, metadata: Optional[Dict[str, Any]] = None, channel_id: Optional[str] = None, message_id: Optional[str] = None, collection_name: Optional[str] = None, importance_score: int = 3, source_type: Optional[MemorySourceType] = None):
        """
        Embeds and saves a memory to Qdrant.
        """
        start_time = time.time()
        
        try:
            # Determine source type if not provided
            if source_type is None:
                if role == "human" or role == "user":
                    source_type = MemorySourceType.HUMAN_DIRECT
                elif role == "ai" or role == "assistant":
                    source_type = MemorySourceType.INFERENCE
                else:
                    source_type = MemorySourceType.INFERENCE  # Default for other types
            
            # Generate embedding
            embedding = await self.embedding_service.embed_query_async(content)
            
            # Prepare payload
            payload = {
                "type": "conversation",  # Default type for chat messages
                "user_id": str(user_id),
                "role": role,
                "content": content,
                "timestamp": datetime.datetime.now().isoformat(),
                "channel_id": str(channel_id) if channel_id else None,
                "message_id": str(message_id) if message_id else None,
                "importance_score": importance_score,
                "source_type": source_type.value
            }
            
            # Metadata can override type (e.g., for save_typed_memory)
            # But preserve source_type - it should not be overwritten by metadata
            if metadata:
                preserved_source_type = payload["source_type"]
                payload.update(metadata)
                payload["source_type"] = preserved_source_type  # Restore after update
            
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
                        .tag("source_type", source_type.value) \
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

    async def save_summary_vector(self, session_id: str, user_id: str, content: str, meaningfulness_score: int, emotions: List[str], topics: Optional[List[str]] = None, user_name: Optional[str] = None, collection_name: Optional[str] = None) -> Optional[str]:
        """
        Embeds and saves a summary to Qdrant.
        
        Args:
            user_name: User's display name (for diary provenance)
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
                    "source_type": MemorySourceType.SUMMARY.value,
                    "session_id": str(session_id),
                    "user_id": str(user_id),
                    "user_name": user_name or "someone",  # For diary provenance display
                    "content": content,
                    "meaningfulness_score": meaningfulness_score,
                    "emotions": emotions,
                    "topics": topics or [],
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
            
            # === WEIGHTED SCORING FOR EPISODES ===
            results = []
            
            for hit in search_result.points:
                semantic_score = hit.score
                payload = hit.payload or {}
                
                # 1. Temporal Weight (Decay)
                # Use centralized scoring logic for consistent decay rates
                temporal_weight = scoring.calculate_temporal_weight(payload)
                
                # 2. Source Weight (Trust)
                # Prefer direct human interaction over gossip/dreams
                source_type = payload.get("source_type")
                # Fallback to role if source_type missing (legacy data)
                if not source_type:
                    role = payload.get("role")
                    if role == "human": source_type = "human_direct"
                    elif role == "ai": source_type = "inference"
                
                source_weight = scoring.SOURCE_WEIGHTS.get(source_type, scoring.DEFAULT_SOURCE_WEIGHT)
                
                # 3. Importance Weight
                # 1-10 → 0.5-1.0 (default 3 -> 0.65)
                raw_importance = payload.get("importance_score", 3)
                importance_multiplier = 0.5 + (raw_importance / 20.0)

                # Final Score Calculation
                # Semantic * Temporal * Source * Importance
                weighted_score = semantic_score * temporal_weight * source_weight * importance_multiplier
                
                results.append({
                    "id": hit.id,
                    "content": payload.get("content"),
                    "role": payload.get("role"),
                    "source_type": source_type,
                    "score": weighted_score,
                    "semantic_score": semantic_score,
                    "temporal_weight": round(temporal_weight, 3),
                    "source_weight": round(source_weight, 3),
                    "importance_multiplier": round(importance_multiplier, 3),
                    "timestamp": payload.get("timestamp"),
                    "relative_time": get_relative_time(payload.get("timestamp")) if payload.get("timestamp") else "unknown time"
                })
            
            # Re-rank by weighted score
            results.sort(key=lambda x: x["score"], reverse=True)
            
            # Log metrics
            if db_manager.influxdb_write_api:
                try:
                    duration_ms = (time.time() - start_time) * 1000
                    point = Point("memory_latency") \
                        .tag("user_id", user_id) \
                        .tag("operation", "read") \
                        .field("duration_ms", duration_ms) \
                        .field("result_count", len(results)) \
                        .time(datetime.datetime.utcnow())
                    
                    db_manager.influxdb_write_api.write(
                        bucket=settings.INFLUXDB_BUCKET,
                        org=settings.INFLUXDB_ORG,
                        record=point
                    )
                except Exception as e:
                    logger.error(f"Failed to log memory search metrics: {e}")

            return results[:limit]
            
        except Exception as e:
            logger.error(f"Failed to search memories: {e}")
            return []

    async def search_memories_advanced(
        self,
        query: str,
        user_id: Optional[str] = None,
        limit: int = 5,
        min_timestamp: Optional[float] = None,
        max_timestamp: Optional[float] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
        collection_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Advanced search with time range and metadata filtering.
        Useful for 'dreaming' (finding old memories) or specific emotional queries.
        """
        if not db_manager.qdrant_client:
            return []

        target_collection = collection_name or self.collection_name
        
        try:
            embedding = await self.embedding_service.embed_query_async(query)
            
            must_conditions = []
            
            # User Filter
            if user_id:
                must_conditions.append(
                    FieldCondition(key="user_id", match=MatchValue(value=str(user_id)))
                )
                
            # Time Range Filter
            if min_timestamp is not None or max_timestamp is not None:
                range_filter = Range()
                if min_timestamp is not None:
                    range_filter.gte = min_timestamp
                if max_timestamp is not None:
                    range_filter.lte = max_timestamp
                
                must_conditions.append(
                    FieldCondition(key="timestamp", range=range_filter)
                )
                
            # Metadata Filter (e.g., {"emotions": "joy"})
            # Note: This assumes simple key-value matching for now
            if metadata_filter:
                for key, value in metadata_filter.items():
                    must_conditions.append(
                        FieldCondition(key=key, match=MatchValue(value=value))
                    )

            results = await db_manager.qdrant_client.query_points(
                collection_name=target_collection,
                query=embedding,
                query_filter=Filter(must=must_conditions) if must_conditions else None,
                limit=limit
            )
            
            return [point.payload for point in results.points if point.payload]
            
        except Exception as e:
            logger.error(f"Advanced memory search failed: {e}")
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
                payload = hit.payload or {}
                ts_str = payload.get("timestamp")
                
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
                raw_meaningfulness = payload.get("meaningfulness_score", 5)
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
                    "content": payload.get("content"),
                    "score": weighted_score,
                    "semantic_score": semantic_score,
                    "meaningfulness": raw_meaningfulness,
                    "recency_multiplier": round(recency_multiplier, 3),
                    "topics": payload.get("topics", []),
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
                        SELECT role, content, user_id, user_name, timestamp 
                        FROM v2_chat_history 
                        WHERE channel_id = $1 AND character_name = $2
                        ORDER BY timestamp DESC
                        LIMIT $3
                    """, str(channel_id), character_name, limit)
                else:
                    # Fetch by user_id (DM Context)
                    rows = await conn.fetch("""
                        SELECT role, content, user_id, user_name, timestamp 
                        FROM v2_chat_history 
                        WHERE user_id = $1 AND character_name = $2
                        ORDER BY timestamp DESC
                        LIMIT $3
                    """, str(user_id), character_name, limit)
                
                # Reverse to get chronological order
                for row in reversed(rows):
                    # Calculate relative time for context
                    timestamp = row['timestamp']
                    rel_time = get_relative_time(timestamp)
                    
                    if row['role'] == 'human':
                        content = row['content']
                        
                        # In group contexts (channel_id present), distinguish other users
                        if channel_id and row['user_id'] != str(user_id):
                            display_name = row['user_name'] or f"User {row['user_id']}"
                            content = f"[{display_name}]: {content}"
                        
                        # Add timestamp context (suffix to avoid LLM echoing)
                        content = f"{content} ({rel_time})"
                            
                        messages.append(HumanMessage(content=content))
                    elif row['role'] == 'ai':
                        # Add timestamp context to AI messages as well (suffix)
                        content = f"{row['content']} ({rel_time})"
                        messages.append(AIMessage(content=content))
                        
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

    async def search_reasoning_traces(self, query: str, user_id: str, limit: int = 3, collection_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Searches for reasoning traces relevant to the query.
        """
        if not db_manager.qdrant_client:
            return []

        collection = collection_name or self.collection_name
        
        try:
            # Generate embedding for the query
            # Use async wrapper to avoid blocking the event loop
            query_vector = await self.embedding_service.embed_query_async(query)
            
            # Filter for reasoning traces for this user
            search_filter = Filter(
                must=[
                    FieldCondition(key="type", match=MatchValue(value="reasoning_trace")),
                    FieldCondition(key="user_id", match=MatchValue(value=user_id))
                ]
            )
            
            results = await db_manager.qdrant_client.query_points(
                collection_name=collection,
                query=query_vector,
                query_filter=search_filter,
                limit=limit
            )
            
            return [
                {
                    "content": hit.payload.get("content", ""),
                    "metadata": hit.payload.get("metadata", {}),
                    "score": hit.score
                }
                for hit in results.points
            ]
            
        except Exception as e:
            logger.error(f"Failed to search reasoning traces: {e}")
            return []

    async def get_summaries_since(self, hours: int = 24, limit: int = 50, collection_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all summaries from the last N hours (for diary generation).
        
        Unlike search_summaries, this doesn't filter by user - it gets all summaries
        for this character/bot to synthesize into a daily diary.
        
        Args:
            hours: How many hours back to look (default 24)
            limit: Maximum number of summaries to return
            collection_name: Override collection name
            
        Returns:
            List of summary payloads with user_id, content, emotions, topics, etc.
        """
        if not db_manager.qdrant_client:
            return []
        
        collection = collection_name or self.collection_name
        
        try:
            # Calculate threshold timestamp
            threshold = datetime.datetime.now() - datetime.timedelta(hours=hours)
            threshold_iso = threshold.isoformat()
            
            # Scroll through all summaries (no embedding query, just filter)
            results = await db_manager.qdrant_client.scroll(
                collection_name=collection,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="type", match=MatchValue(value="summary"))
                    ]
                ),
                limit=limit * 2,  # Fetch extra for date filtering
                with_payload=True,
                with_vectors=False
            )
            
            # Filter by timestamp (Qdrant doesn't support date range in scroll easily)
            summaries = []
            for point in results[0]:
                payload = point.payload
                if payload:
                    ts = payload.get("timestamp", "")
                    if ts >= threshold_iso:
                        summaries.append({
                            "user_id": payload.get("user_id"),
                            "content": payload.get("content", ""),
                            "emotions": payload.get("emotions", []),
                            "topics": payload.get("topics", []),
                            "meaningfulness_score": payload.get("meaningfulness_score", 3),
                            "timestamp": ts
                        })
            
            # Sort by timestamp descending
            summaries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
            logger.debug(f"Found {len(summaries)} summaries in last {hours} hours")
            return summaries[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get recent summaries: {e}")
            return []

    async def get_high_meaningfulness_memories(
        self,
        hours: int = 24,
        limit: int = 10,
        min_meaningfulness: float = 0.6,
        collection_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get high-meaningfulness memories from the last N hours (for dream generation).
        
        Retrieves individual memories (not summaries) that have high meaningfulness
        scores, suitable for synthesizing into surreal dreams.
        
        Args:
            hours: How many hours back to look (default 24)
            limit: Maximum number of memories to return
            min_meaningfulness: Minimum meaningfulness score (0.0-1.0)
            collection_name: Override collection name
            
        Returns:
            List of memory payloads with content, emotions, topics, etc.
        """
        if not db_manager.qdrant_client:
            return []
        
        collection = collection_name or self.collection_name
        
        try:
            # Calculate threshold timestamp (datetime is imported at top of file)
            threshold = datetime.datetime.now() - datetime.timedelta(hours=hours)
            threshold_iso = threshold.isoformat()
            
            # Get summaries (which have meaningfulness_score)
            # Note: timestamp is stored as ISO string, so we filter by type first
            # then manually filter by timestamp (Range only works with numeric fields)
            results = await db_manager.qdrant_client.scroll(
                collection_name=collection,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="type", match=MatchValue(value="summary")),
                    ]
                ),
                limit=limit * 10,  # Fetch extra for time-based filtering
                with_payload=True,
                with_vectors=False
            )
            
            memories = []
            for point in results[0]:
                payload = point.payload
                if not payload:
                    continue
                
                ts = payload.get("timestamp", "")
                if ts < threshold_iso:
                    continue
                
                # Check meaningfulness score
                meaningfulness = payload.get("meaningfulness_score", 0.5)
                if isinstance(meaningfulness, (int, float)) and meaningfulness >= min_meaningfulness:
                    memories.append({
                        "content": payload.get("content", ""),
                        "summary": payload.get("summary", payload.get("content", "")),
                        "emotions": payload.get("emotions", []),
                        "topics": payload.get("topics", []),
                        "meaningfulness_score": meaningfulness,
                        "user_id": payload.get("user_id"),
                        "timestamp": ts
                    })
            
            # Also check summaries if we don't have enough memories
            if len(memories) < limit:
                summary_results = await db_manager.qdrant_client.scroll(
                    collection_name=collection,
                    scroll_filter=Filter(
                        must=[
                            FieldCondition(key="type", match=MatchValue(value="summary")),
                        ]
                    ),
                    limit=limit * 5,  # Fetch extra for time-based filtering
                    with_payload=True,
                    with_vectors=False
                )
                
                for point in summary_results[0]:
                    payload = point.payload
                    if not payload:
                        continue
                    
                    ts = payload.get("timestamp", "")
                    if ts < threshold_iso:
                        continue
                    
                    # Normalize meaningfulness score (summaries use 1-5 scale)
                    raw_score = payload.get("meaningfulness_score", 3)
                    if isinstance(raw_score, (int, float)):
                        if raw_score > 1:  # Probably 1-5 scale
                            meaningfulness = raw_score / 5.0
                        else:
                            meaningfulness = raw_score
                        
                        if meaningfulness >= min_meaningfulness:
                            memories.append({
                                "content": payload.get("content", ""),
                                "summary": payload.get("content", ""),
                                "emotions": payload.get("emotions", []),
                                "topics": payload.get("topics", []),
                                "meaningfulness_score": meaningfulness,
                                "user_id": payload.get("user_id"),
                                "timestamp": ts
                            })
            
            # Sort by meaningfulness (descending) and then timestamp
            memories.sort(key=lambda x: (x.get("meaningfulness_score", 0), x.get("timestamp", "")), reverse=True)
            
            logger.debug(f"Found {len(memories)} high-meaningfulness memories in last {hours} hours")
            return memories[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get high meaningfulness memories: {e}")
            return []

    async def search_by_type(
        self,
        memory_type: str,
        collection_name: Optional[str] = None,
        limit: int = 10,
        hours: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for memories by type (observation, gossip, diary, dream, epiphany, etc).
        
        Used by narrative agents (Diary/Dream) to gather different types of material.
        
        Args:
            memory_type: The type of memory to search for
            collection_name: Override collection name
            limit: Maximum number of results
            hours: Optional - only get memories from last N hours
            
        Returns:
            List of memory payloads matching the type
        """
        if not db_manager.qdrant_client:
            return []
        
        collection = collection_name or self.collection_name
        
        try:
            # Build filter conditions
            must_conditions = [
                FieldCondition(key="type", match=MatchValue(value=memory_type))
            ]
            
            # Calculate threshold if hours specified
            threshold_iso = None
            if hours:
                threshold = datetime.datetime.now() - datetime.timedelta(hours=hours)
                threshold_iso = threshold.isoformat()
            
            results = await db_manager.qdrant_client.scroll(
                collection_name=collection,
                scroll_filter=Filter(must=must_conditions),
                limit=limit * 3 if hours else limit,  # Fetch extra if filtering by time
                with_payload=True,
                with_vectors=False
            )
            
            memories = []
            for point in results[0]:
                payload = point.payload
                if not payload:
                    continue
                
                # Filter by time if specified
                if threshold_iso:
                    ts = payload.get("timestamp", payload.get("created_at", ""))
                    if ts and ts < threshold_iso:
                        continue
                
                memories.append({
                    "content": payload.get("content", ""),
                    "metadata": payload,
                    "user_id": payload.get("user_id"),
                    "created_at": payload.get("timestamp", payload.get("created_at", "")),
                    "type": memory_type
                })
                
                if len(memories) >= limit:
                    break
            
            logger.debug(f"Found {len(memories)} memories of type '{memory_type}'")
            return memories
            
        except Exception as e:
            logger.error(f"Failed to search memories by type: {e}")
            return []

    async def search_by_type_semantic(
        self,
        memory_type: str,
        query: str,
        collection_name: Optional[str] = None,
        limit: int = 5,
        user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for memories by type using semantic search.
        
        Args:
            memory_type: The type of memory to search for
            query: The semantic query string
            collection_name: Override collection name
            limit: Maximum number of results
            user_id: Optional user ID to filter by
            
        Returns:
            List of memory payloads matching the type and query
        """
        if not db_manager.qdrant_client:
            return []
        
        collection = collection_name or self.collection_name
        
        try:
            embedding = await self.embedding_service.embed_query_async(query)
            
            must_conditions = [
                FieldCondition(key="type", match=MatchValue(value=memory_type))
            ]
            
            if user_id:
                must_conditions.append(
                    FieldCondition(key="user_id", match=MatchValue(value=str(user_id)))
                )
            
            results = await db_manager.qdrant_client.query_points(
                collection_name=collection,
                query=embedding,
                query_filter=Filter(must=must_conditions),
                limit=limit,
                with_payload=True
            )
            
            memories = []
            for hit in results.points:
                payload = hit.payload
                if not payload:
                    continue
                    
                memories.append({
                    "content": payload.get("content", ""),
                    "metadata": payload,
                    "user_id": payload.get("user_id"),
                    "created_at": payload.get("timestamp", payload.get("created_at", "")),
                    "type": memory_type,
                    "score": hit.score
                })
                
            logger.debug(f"Found {len(memories)} semantic matches for type '{memory_type}' query '{query}'")
            return memories
            
        except Exception as e:
            logger.error(f"Failed to search memories by type semantic: {e}")
            return []

    async def search_all_summaries(
        self,
        query: str,
        collection_name: Optional[str] = None,
        limit: int = 10,
        hours: Optional[int] = 24
    ) -> List[Dict[str, Any]]:
        """
        Search summaries across ALL users (for diary/dream generation).
        
        Unlike search_summaries which requires a user_id, this searches
        globally across the bot's collection.
        
        Args:
            query: Semantic query string
            collection_name: Override collection name
            limit: Maximum results to return
            hours: Only get summaries from last N hours
            
        Returns:
            List of summary payloads
        """
        if not db_manager.qdrant_client:
            return []
        
        collection = collection_name or self.collection_name
        
        try:
            embedding = await self.embedding_service.embed_query_async(query)
            
            # Build filter - type must be summary
            must_conditions = [
                FieldCondition(key="type", match=MatchValue(value="summary"))
            ]
            
            search_result = await db_manager.qdrant_client.query_points(
                collection_name=collection,
                query=embedding,
                query_filter=Filter(must=must_conditions),
                limit=limit * 2  # Fetch extra for filtering
            )
            
            # Calculate threshold if hours specified
            threshold_iso = None
            if hours:
                threshold = datetime.datetime.now() - datetime.timedelta(hours=hours)
                threshold_iso = threshold.isoformat()
            
            summaries = []
            for point in search_result.points:
                payload = point.payload
                if not payload:
                    continue
                
                # Filter by time if specified
                if threshold_iso:
                    ts = payload.get("timestamp", payload.get("created_at", ""))
                    if ts and ts < threshold_iso:
                        continue
                
                summaries.append({
                    "content": payload.get("content", ""),
                    "user_id": payload.get("user_id"),
                    "timestamp": payload.get("timestamp", ""),
                    "topics": payload.get("topics", []),
                    "emotions": payload.get("emotions", [])
                })
                
                if len(summaries) >= limit:
                    break
            
            logger.debug(f"Found {len(summaries)} summaries across all users")
            return summaries
            
        except Exception as e:
            logger.error(f"Failed to search all summaries: {e}")
            return []

# Global instance
memory_manager = MemoryManager()
