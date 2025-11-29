"""
Background Worker - Handles all background processing tasks for WhisperEngine.

This worker runs in a shared container and processes jobs from the Redis queue.
It's designed to be fault-isolated from the main Discord bot and serves ALL bots.
Jobs include bot_name in the payload for character context routing.

Supported tasks:
- Insight Analysis: Pattern detection and epiphany generation
- Summarization: Session summary generation (post-session)
- Reflection: User pattern analysis across sessions
- Knowledge Extraction: Fact extraction to Neo4j (offloaded from response pipeline)
- Diary Generation: Nightly character diary entries (Phase E2)

Usage:
    python -m src_v2.workers.worker
    
Or via arq CLI:
    arq src_v2.workers.worker.WorkerSettings
"""
import asyncio
from typing import Any, Dict
from loguru import logger
from arq import cron

from src_v2.workers.task_queue import TaskQueue
from src_v2.core.database import db_manager
from src_v2.config.settings import settings
from src_v2.workers.strategist import run_goal_strategist

# Import tasks from modular files
from src_v2.workers.tasks.insight_tasks import run_insight_analysis, run_reflection
from src_v2.workers.tasks.summary_tasks import run_summarization
from src_v2.workers.tasks.knowledge_tasks import run_knowledge_extraction
from src_v2.workers.tasks.diary_tasks import run_diary_generation, run_agentic_diary_generation
from src_v2.workers.tasks.dream_tasks import run_dream_generation, run_agentic_dream_generation
from src_v2.workers.tasks.social_tasks import (
    run_store_observation,
    run_universe_observation,
    run_relationship_update,
    run_gossip_dispatch,
)
from src_v2.workers.tasks.analysis_tasks import (
    run_goal_analysis,
    run_preference_extraction
)
from src_v2.workers.tasks.vision_tasks import run_vision_analysis
from src_v2.workers.tasks.cron_tasks import (
    run_nightly_diary_generation,
    run_nightly_dream_generation,
    run_nightly_goal_strategist
)


async def startup(ctx: Dict[str, Any]) -> None:
    """Called when worker starts up."""
    logger.info("Worker starting up...")
    
    # Initialize database connections
    await db_manager.connect_all()
    
    ctx["db_connected"] = True
    logger.info("Worker ready to process jobs")


async def shutdown(ctx: Dict[str, Any]) -> None:
    """Called when worker shuts down."""
    logger.info("Worker shutting down...")
    
    # Close database connections (use individual close methods)
    if db_manager.postgres_pool:
        await db_manager.postgres_pool.close()
    if db_manager.qdrant_client:
        await db_manager.qdrant_client.close()
    if db_manager.neo4j_driver:
        await db_manager.neo4j_driver.close()
    
    logger.info("Worker shutdown complete")


# Worker configuration for arq
class WorkerSettings:
    """arq worker settings."""
    
    # Redis connection
    redis_settings = TaskQueue.get_redis_settings()
    
    # Functions the worker can execute
    functions = [
        run_insight_analysis,
        run_summarization,
        run_reflection,
        run_knowledge_extraction,
        run_store_observation,
        run_universe_observation,
        run_relationship_update,
        run_goal_strategist,
        run_goal_analysis,
        run_preference_extraction,
        run_vision_analysis,
        run_gossip_dispatch,
        run_diary_generation,  # Phase E2: Character Diary
        run_agentic_diary_generation,
        run_dream_generation,  # Phase E3: Nightly Dreams
        run_agentic_dream_generation,
    ]
    
    # Cron jobs (scheduled tasks)
    # These run hourly and check each character's timezone to determine if
    # it's the right local time for that character's scheduled task.
    cron_jobs = [
        # Check hourly for characters where it's diary time (default: 10 PM local)
        cron(
            run_nightly_diary_generation,
            hour=None,  # Run every hour
            minute={0},
            run_at_startup=False  # Don't run immediately on worker start
        ),
        # Check hourly for characters where it's dream time (default: 7 AM local)
        cron(
            run_nightly_dream_generation,
            hour=None,  # Run every hour
            minute={0},
            run_at_startup=False
        ),
        # Check hourly for characters where it's goal strategist time (default: 11 PM local)
        cron(
            run_nightly_goal_strategist,
            hour=None,  # Run every hour
            minute={0},
            run_at_startup=False
        ),
    ]
    
    # Startup/shutdown hooks
    on_startup = startup
    on_shutdown = shutdown
    
    # Worker behavior
    max_jobs = 5  # Max concurrent jobs
    job_timeout = 120  # 2 minutes max per job
    keep_result = 3600  # Keep results for 1 hour
    
    # Health check
    health_check_interval = 30


if __name__ == "__main__":
    # Allow running directly for testing via: python -m src_v2.workers.worker
    # Or use arq CLI: arq src_v2.workers.worker.WorkerSettings
    from arq.worker import run_worker
    
    logger.info("Starting Worker...")
    run_worker(WorkerSettings)  # type: ignore[arg-type]
