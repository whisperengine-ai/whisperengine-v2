"""
Task Queue Manager using arq (Async Redis Queue)
Provides a lightweight persistent job queue for background tasks.
"""
import os
from typing import Any, Dict, List, Optional, Callable, Awaitable
from loguru import logger
from arq import create_pool
from arq.connections import RedisSettings, ArqRedis

from src_v2.config.settings import settings


class TaskQueue:
    """
    Manages enqueueing tasks to Redis for background workers.
    
    Usage:
        # Enqueue a task
        await task_queue.enqueue("analyze_conversation", user_id="123", session_id="abc")
        
        # Enqueue with delay
        await task_queue.enqueue("summarize_session", _defer_by=60, user_id="123")
    """
    
    _instance: Optional["TaskQueue"] = None
    _pool: Optional[ArqRedis] = None
    
    def __new__(cls) -> "TaskQueue":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def get_redis_settings(cls) -> RedisSettings:
        """Parse REDIS_URL into RedisSettings for arq."""
        redis_url = settings.REDIS_URL
        
        # Parse redis://host:port/db format
        if redis_url.startswith("redis://"):
            url = redis_url[8:]  # Remove redis://
        else:
            url = redis_url
            
        # Split host:port/db
        if "/" in url:
            host_port, db = url.rsplit("/", 1)
            database = int(db) if db else 0
        else:
            host_port = url
            database = 0
            
        if ":" in host_port:
            host, port = host_port.split(":")
            port = int(port)
        else:
            host = host_port
            port = 6379
            
        return RedisSettings(
            host=host,
            port=port,
            database=database,
            conn_timeout=10,
            conn_retries=5,
        )
    
    async def connect(self) -> None:
        """Initialize connection to Redis."""
        if self._pool is None:
            try:
                # Connect to Redis and set default queue to match worker's queue
                self._pool = await create_pool(
                    self.get_redis_settings(),
                    default_queue_name="arq:cognition"
                )
                logger.info("TaskQueue connected to Redis (queue: arq:cognition)")
            except Exception as e:
                logger.error(f"Failed to connect TaskQueue to Redis: {e}")
                raise
    
    async def close(self) -> None:
        """Close Redis connection."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("TaskQueue disconnected from Redis")
    
    async def enqueue(
        self, 
        task_name: str, 
        _defer_by: Optional[int] = None,
        _job_id: Optional[str] = None,
        _queue_name: str = "arq:cognition",
        **kwargs: Any
    ) -> Optional[str]:
        """
        Enqueue a task for background processing.
        
        Args:
            task_name: Name of the task function to execute
            _defer_by: Delay in seconds before execution
            _job_id: Optional unique job ID (for deduplication)
            _queue_name: The queue to enqueue the job in (default: arq:cognition)
            **kwargs: Arguments to pass to the task
            
        Returns:
            Job ID if successfully enqueued, None otherwise
        """
        if self._pool is None:
            await self.connect()
            
        if self._pool is None:
            logger.warning(f"Cannot enqueue task {task_name}: Redis not connected")
            return None
            
        try:
            logger.debug(f"Calling enqueue_job: task={task_name}, defer_by={_defer_by}, queue={_queue_name}")
            job = await self._pool.enqueue_job(
                task_name,
                _defer_by=_defer_by,
                _job_id=_job_id,
                _queue_name=_queue_name,
                **kwargs
            )
            
            if job:
                logger.debug(f"Enqueued task {task_name} (job_id: {job.job_id}) to {_queue_name}")
                return job.job_id
            else:
                logger.debug(f"Task {task_name} already queued (duplicate job_id)")
                return None
                
        except Exception as e:
            logger.error(f"Failed to enqueue task {task_name}: {e}")
            return None
    
    async def enqueue_insight_analysis(
        self,
        user_id: str,
        character_name: str,
        trigger: str = "volume",
        priority: int = 5,
        recent_context: Optional[str] = None
    ) -> Optional[str]:
        """
        Convenience method to enqueue an insight analysis task.
        
        Args:
            user_id: Discord user ID
            character_name: Bot character name
            trigger: What triggered this analysis (time, volume, session_end, feedback)
            priority: 1-10, lower = higher priority
            recent_context: Optional recent conversation text
        """
        job_id = f"insight_{user_id}_{character_name}"
        
        return await self.enqueue(
            "run_insight_analysis",
            _job_id=job_id,  # Prevents duplicate jobs for same user/character
            user_id=user_id,
            character_name=character_name,
            trigger=trigger,
            priority=priority,
            recent_context=recent_context
        )
    
    async def enqueue_goal_analysis(
        self,
        user_id: str,
        character_name: str,
        interaction_text: str
    ) -> Optional[str]:
        """Enqueue a goal analysis task."""
        return await self.enqueue(
            "run_goal_analysis",
            user_id=user_id,
            character_name=character_name,
            interaction_text=interaction_text
        )

    async def enqueue_preference_extraction(
        self,
        user_id: str,
        character_name: str,
        message_content: str
    ) -> Optional[str]:
        """Enqueue a preference extraction task."""
        return await self.enqueue(
            "run_preference_extraction",
            user_id=user_id,
            character_name=character_name,
            message_content=message_content
        )

    async def enqueue_vision_analysis(
        self,
        image_url: str,
        user_id: str,
        channel_id: str
    ) -> Optional[str]:
        """Enqueue a vision analysis task."""
        return await self.enqueue(
            "run_vision_analysis",
            image_url=image_url,
            user_id=user_id,
            channel_id=channel_id
        )

    async def enqueue_summarization(
        self,
        user_id: str,
        character_name: str,
        session_id: str,
        messages: list,
        user_name: Optional[str] = None
    ) -> Optional[str]:
        """
        Enqueue a session summarization task.
        
        Args:
            user_id: Discord user ID
            character_name: Bot character name
            session_id: Conversation session ID
            messages: List of message dicts with 'role' and 'content' keys
            user_name: User's display name (for diary provenance)
        """
        job_id = f"summarize_{session_id}"
        
        return await self.enqueue(
            "run_summarization",
            _job_id=job_id,
            user_id=user_id,
            character_name=character_name,
            session_id=session_id,
            messages=messages,
            user_name=user_name
        )
    
    async def enqueue_reflection(
        self,
        user_id: str,
        character_name: str
    ) -> Optional[str]:
        """
        Enqueue a user reflection/pattern analysis task.
        
        Args:
            user_id: Discord user ID
            character_name: Bot character name
        """
        job_id = f"reflection_{user_id}_{character_name}"
        
        return await self.enqueue(
            "run_reflection",
            _job_id=job_id,
            user_id=user_id,
            character_name=character_name
        )
    
    async def enqueue_knowledge_extraction(self, user_id: str, message: str, character_name: str) -> Optional[str]:
        """
        Queue a job to extract facts from a user message.
        
        Args:
            user_id: Discord user ID
            message: The message content
            character_name: The name of the bot (for privacy segmentation)
            
        Returns:
            Job ID if queued, None if queue unavailable
        """
        # No job_id deduplication - each message should be processed
        return await self.enqueue(
            "run_knowledge_extraction",
            user_id=user_id,
            message=message,
            character_name=character_name
        )

    async def enqueue_relationship_update(
        self,
        character_name: str,
        user_id: str,
        guild_id: Optional[str] = None,
        interaction_quality: int = 1,
        extracted_traits: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Queue a job to update the relationship between a character and user.
        
        Called after each meaningful conversation to build familiarity
        and record learned traits.
        
        Args:
            character_name: Bot character name (e.g., "elena")
            user_id: Discord user ID
            guild_id: Optional guild where interaction happened
            interaction_quality: Quality multiplier (1=normal, 2=high engagement)
            extracted_traits: Optional list of traits to add to user profile
            
        Returns:
            Job ID if queued, None if queue unavailable
        """
        return await self.enqueue(
            "run_relationship_update",
            character_name=character_name,
            user_id=user_id,
            guild_id=guild_id,
            interaction_quality=interaction_quality,
            extracted_traits=extracted_traits
        )

    async def enqueue_gossip(self, event: Any) -> Optional[str]:
        """
        Queue a gossip event for cross-bot sharing (Phase 3.4).
        
        Args:
            event: UniverseEvent instance to process
            
        Returns:
            Job ID if queued, None if queue unavailable
        """
        # Import here to avoid circular dependency
        from src_v2.universe.bus import UniverseEvent
        
        if not isinstance(event, UniverseEvent):
            logger.error(f"Invalid event type: {type(event)}")
            return None
        
        # Use event details for job_id to prevent duplicates
        job_id = f"gossip_{event.user_id}_{event.source_bot}_{event.event_type.value}"
        
        return await self.enqueue(
            "run_gossip_dispatch",
            _job_id=job_id,
            event_data=event.to_dict()
        )


# Global instance
task_queue = TaskQueue()
