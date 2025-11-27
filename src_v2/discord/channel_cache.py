"""
Channel Context Cache - Redis-backed rolling buffer with semantic search.

Caches non-mentioned messages in channels/threads for context awareness.
Uses local embeddings (all-MiniLM-L6-v2, 384-dim) - zero API cost.

Thread messages are stored separately from main channel messages.
"""

import json
import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from loguru import logger
import redis.asyncio as redis

from src_v2.config.settings import settings
from src_v2.memory.embeddings import EmbeddingService


class ChannelContextCache:
    """
    Redis-backed rolling buffer with semantic search for channel messages.
    
    Storage Keys:
    - channel_msg:{channel_id}:{message_id} - Individual message JSON
    - channel_msgs:{channel_id} - Sorted set of message IDs by timestamp
    
    Thread Separation:
    - Threads have their own channel_id, so they're automatically separated
    - Parent channel context is NOT mixed with thread context
    """
    
    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._embeddings = EmbeddingService()
        self._ttl = settings.CHANNEL_CONTEXT_TTL_SECONDS
        self._max_messages = settings.CHANNEL_CONTEXT_MAX_MESSAGES
        self._initialized = False
        
    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis connection."""
        if not self._redis:
            self._redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._redis
    
    async def initialize(self) -> None:
        """Initialize the cache. Called on bot startup."""
        if self._initialized:
            return
            
        try:
            r = await self._get_redis()
            # Ping to verify connection
            await r.ping()
            self._initialized = True
            logger.info("ChannelContextCache initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ChannelContextCache: {e}")
            raise
    
    async def add_message(
        self,
        channel_id: str,
        message_id: str,
        author: str,
        author_id: str,
        content: str,
        timestamp: datetime,
        is_thread: bool = False,
        parent_channel_id: Optional[str] = None
    ) -> None:
        """
        Add a message to the channel cache.
        
        Args:
            channel_id: The channel/thread ID (threads have their own ID)
            message_id: Discord message ID
            author: Display name of the author
            author_id: Discord user ID of the author
            content: Message content (truncated to 500 chars)
            timestamp: When the message was sent
            is_thread: Whether this is in a thread
            parent_channel_id: Parent channel ID if in a thread
        """
        if not content or not content.strip():
            return
            
        try:
            r = await self._get_redis()
            
            # Smart truncation: keep beginning and end for long messages
            if len(content) > 400:
                content = content[:180] + " ... " + content[-180:]
            
            # Generate embedding locally (~5ms, free)
            loop = asyncio.get_running_loop()
            embedding = await loop.run_in_executor(
                None, 
                self._embeddings.embed_query, 
                content
            )
            
            # Prepare message data
            ts_unix = timestamp.timestamp() if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc).timestamp()
            
            msg_data = {
                "channel_id": channel_id,
                "message_id": message_id,
                "author": author,
                "author_id": author_id,
                "content": content,
                "timestamp": ts_unix,
                "is_thread": is_thread,
                "parent_channel_id": parent_channel_id,
                "embedding": embedding
            }
            
            msg_key = f"channel_msg:{channel_id}:{message_id}"
            index_key = f"channel_msgs:{channel_id}"
            
            # Store message with TTL
            await r.setex(msg_key, self._ttl, json.dumps(msg_data))
            
            # Add to sorted set (score = timestamp for ordering)
            await r.zadd(index_key, {message_id: ts_unix})
            await r.expire(index_key, self._ttl)
            
            # Prune old messages if over limit
            await self._prune_channel(r, channel_id)
            
            logger.debug(f"Cached message {message_id} in channel {channel_id} (thread={is_thread})")
            
        except Exception as e:
            logger.error(f"Failed to cache channel message: {e}")
    
    async def _prune_channel(self, r: redis.Redis, channel_id: str) -> None:
        """Keep only the most recent N messages per channel."""
        index_key = f"channel_msgs:{channel_id}"
        
        # Get count
        count = await r.zcard(index_key)
        if count <= self._max_messages:
            return
            
        # Remove oldest messages (lowest scores)
        to_remove = count - self._max_messages
        oldest = await r.zrange(index_key, 0, to_remove - 1)
        
        if oldest:
            # Delete message data
            for msg_id in oldest:
                await r.delete(f"channel_msg:{channel_id}:{msg_id}")
            # Remove from index
            await r.zrem(index_key, *oldest)
            
            logger.debug(f"Pruned {len(oldest)} old messages from channel {channel_id}")
    
    async def search_semantic(
        self,
        channel_id: str,
        query: str,
        limit: int = 10,
        min_similarity: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Semantic search for messages in a channel.
        
        Uses cosine similarity between query embedding and stored embeddings.
        
        Args:
            channel_id: Channel/thread to search
            query: Search query
            limit: Max results to return
            min_similarity: Minimum cosine similarity threshold (0-1)
            
        Returns:
            List of matching messages with similarity scores, sorted by relevance
        """
        try:
            r = await self._get_redis()
            
            # Get all message IDs in this channel
            index_key = f"channel_msgs:{channel_id}"
            msg_ids = await r.zrange(index_key, 0, -1)
            
            if not msg_ids:
                return []
            
            # Embed query
            loop = asyncio.get_running_loop()
            query_vec = await loop.run_in_executor(
                None,
                self._embeddings.embed_query,
                query
            )
            
            # Fetch all messages and compute similarity
            results = []
            for msg_id in msg_ids:
                msg_key = f"channel_msg:{channel_id}:{msg_id}"
                data = await r.get(msg_key)
                if not data:
                    continue
                    
                msg = json.loads(data)
                msg_vec = msg.get("embedding", [])
                
                if not msg_vec:
                    continue
                
                # Compute cosine similarity
                similarity = self._cosine_similarity(query_vec, msg_vec)
                
                if similarity >= min_similarity:
                    results.append({
                        "message_id": msg["message_id"],
                        "author": msg["author"],
                        "author_id": msg["author_id"],
                        "content": msg["content"],
                        "timestamp": msg["timestamp"],
                        "similarity": similarity,
                        "is_thread": msg.get("is_thread", False)
                    })
            
            # Sort by similarity (descending) and limit
            results.sort(key=lambda x: x["similarity"], reverse=True)
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []
    
    async def get_recent(
        self,
        channel_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get most recent messages from a channel (no semantic filtering).
        
        Args:
            channel_id: Channel/thread to get messages from
            limit: Max messages to return
            
        Returns:
            List of messages sorted by timestamp (oldest first for context)
        """
        try:
            r = await self._get_redis()
            
            # Get message IDs sorted by timestamp (most recent last)
            index_key = f"channel_msgs:{channel_id}"
            msg_ids = await r.zrange(index_key, -limit, -1)
            
            if not msg_ids:
                return []
            
            # Fetch message data
            results = []
            for msg_id in msg_ids:
                msg_key = f"channel_msg:{channel_id}:{msg_id}"
                data = await r.get(msg_key)
                if data:
                    msg = json.loads(data)
                    results.append({
                        "message_id": msg["message_id"],
                        "author": msg["author"],
                        "author_id": msg["author_id"],
                        "content": msg["content"],
                        "timestamp": msg["timestamp"],
                        "is_thread": msg.get("is_thread", False)
                    })
            
            # Sort chronologically (oldest first) for context
            results.sort(key=lambda x: x["timestamp"])
            return results
            
        except Exception as e:
            logger.error(f"Failed to get recent messages: {e}")
            return []
    
    async def clear_channel(self, channel_id: str) -> None:
        """Clear all cached messages for a channel."""
        try:
            r = await self._get_redis()
            
            index_key = f"channel_msgs:{channel_id}"
            msg_ids = await r.zrange(index_key, 0, -1)
            
            # Delete all message data
            for msg_id in msg_ids:
                await r.delete(f"channel_msg:{channel_id}:{msg_id}")
            
            # Delete index
            await r.delete(index_key)
            
            logger.info(f"Cleared channel cache for {channel_id}")
            
        except Exception as e:
            logger.error(f"Failed to clear channel cache: {e}")
    
    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
            
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
            
        return dot_product / (norm1 * norm2)


# Global instance
channel_cache = ChannelContextCache()
