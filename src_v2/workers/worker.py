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
import os
from typing import Any, Dict
from loguru import logger
import arq
from arq import cron

from src_v2.workers.task_queue import TaskQueue
from src_v2.core.database import db_manager
from src_v2.config.settings import settings
from src_v2.workers.strategist import run_goal_strategist

# Import tasks from modular files
from src_v2.workers.tasks.insight_tasks import run_insight_analysis, run_reflection
from src_v2.workers.tasks.summary_tasks import run_summarization
from src_v2.workers.tasks.knowledge_tasks import run_knowledge_extraction
from src_v2.workers.tasks.batch_knowledge_tasks import run_batch_knowledge_extraction
from src_v2.workers.tasks.diary_tasks import run_diary_generation
from src_v2.workers.tasks.dream_tasks import run_dream_generation, run_active_dream_cycle
from src_v2.workers.tasks.drift_observation import run_drift_observation
from src_v2.workers.tasks.social_tasks import (
    run_universe_observation,
    run_relationship_update,
    run_gossip_dispatch,
)
from src_v2.workers.tasks.analysis_tasks import (
    run_goal_analysis,
    run_preference_extraction
)
from src_v2.workers.tasks.batch_preference_tasks import run_batch_preference_extraction
from src_v2.workers.tasks.batch_goal_tasks import run_batch_goal_analysis
from src_v2.workers.tasks.vision_tasks import run_vision_analysis
from src_v2.workers.tasks.posting_tasks import run_posting_agent
from src_v2.workers.tasks.daily_life_tasks import process_daily_life
from src_v2.workers.tasks.enrichment_tasks import (
    run_graph_enrichment,
    run_batch_enrichment,
    run_nightly_enrichment
)
from src_v2.workers.tasks.action_tasks import run_proactive_message
from src_v2.workers.tasks.cron_tasks import (
    run_nightly_diary_generation,
    run_nightly_dream_generation,
    run_nightly_goal_strategist,
    run_weekly_drift_observation,
    run_weekly_graph_pruning,
    run_session_timeout_processing
)


async def startup(ctx: Dict[str, Any]) -> None:
    """Called when worker starts up."""
    logger.info("Worker starting up...")
    
    # Initialize LangSmith tracing if enabled
    if settings.LANGCHAIN_TRACING_V2:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
        os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
        logger.info(f"LangSmith tracing enabled (project: {settings.LANGCHAIN_PROJECT})")
    
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
    # Note: LangGraph tasks (diary, dream, strategist) have longer timeouts set via func() wrapper
    functions = [
        run_insight_analysis,
        run_summarization,
        run_reflection,
        run_knowledge_extraction,
        run_batch_knowledge_extraction,
        run_universe_observation,
        run_relationship_update,
        # LangGraph agents get 10 min timeout (local LLMs + multi-step reasoning)
        arq.func(run_goal_strategist, timeout=600),
        run_goal_analysis,           # DEPRECATED: per-message goal analysis
        run_preference_extraction,   # DEPRECATED: per-message preference extraction
        run_batch_preference_extraction,  # Session-level preference extraction
        run_batch_goal_analysis,          # Session-level goal analysis
        run_vision_analysis,
        run_gossip_dispatch,
        arq.func(run_diary_generation, timeout=600),  # Phase E2/E10: Character Diary (agentic)
        arq.func(run_dream_generation, timeout=600),  # Phase E3/E10: Nightly Dreams (agentic)
        run_drift_observation,  # Phase E16: Personality drift observation
        run_posting_agent,      # Phase E15: Autonomous Posting
        run_graph_enrichment,   # Phase E25: Graph Enrichment
        run_batch_enrichment,   # Phase E25: Batch Graph Enrichment
        run_proactive_message,  # Phase E24: Proactive Message (Action Queue)
        arq.func(process_daily_life, timeout=300), # Phase E31: Daily Life Graph
    ]
    
    # Cron jobs (scheduled tasks)
    # These run periodically and check each character's timezone to determine if
    # it's the right local time for that character's scheduled task.
    cron_jobs = [
        # Check every 30 minutes for characters where it's diary time (default: 8:30 PM local)
        cron(
            run_nightly_diary_generation,
            hour=None,  # Run every hour
            minute={0, 30},  # Check on the hour and half-hour
            run_at_startup=False  # Don't run immediately on worker start
        ),
        # Check every 30 minutes for characters where it's dream time (default: 6:30 AM local)
        cron(
            run_nightly_dream_generation,
            hour=None,  # Run every hour
            minute={0, 30},  # Check on the hour and half-hour
            run_at_startup=False
        ),
        # Check every 30 minutes for characters where it's goal strategist time (default: 11:00 PM local)
        cron(
            run_nightly_goal_strategist,
            hour=None,  # Run every hour
            minute={0, 30},  # Check on the hour and half-hour
            run_at_startup=False
        ),
        # Weekly drift observation - runs Sunday at midnight UTC (Phase E16)
        cron(
            run_weekly_drift_observation,
            weekday=6,  # Sunday (0=Monday, 6=Sunday)
            hour=0,     # Midnight UTC
            minute=0,
            run_at_startup=False
        ),
        # Weekly graph pruning - runs Sunday at 2 AM UTC (Phase E24)
        cron(
            run_weekly_graph_pruning,
            weekday=6,  # Sunday (0=Monday, 6=Sunday)
            hour=2,     # 2 AM UTC (after drift observation)
            minute=0,
            run_at_startup=False
        ),
        # Nightly graph enrichment - runs at 3 AM UTC (Phase E25)
        cron(
            run_nightly_enrichment,
            hour=3,     # 3 AM UTC (quiet time)
            minute=0,
            run_at_startup=False
        ),
        # Session timeout processing - runs every 5 minutes (Phase S6)
        cron(
            run_session_timeout_processing,
            minute=set(range(0, 60, 5)),
            run_at_startup=True
        ),
    ]
    
    # Primary queue name - arq only listens to a single queue per worker instance
    # Set to arq:cognition for deep reasoning tasks (diaries, dreams, reflection, strategy)
    # To listen to multiple queues, use separate worker instances or routing logic
    queue_name = os.getenv("ARQ_QUEUE_NAME", "arq:cognition")
    
    # Startup/shutdown hooks
    on_startup = startup
    on_shutdown = shutdown
    
    # Worker behavior
    # Auto-detect max_jobs based on LLM provider:
    # - Local LLMs (lmstudio, ollama): 1 job at a time (single GPU, avoid OOM)
    # - Cloud LLMs: 5 concurrent jobs (APIs handle parallelism)
    @staticmethod
    def _get_max_jobs() -> int:
        if settings.WORKER_MAX_JOBS is not None:
            return settings.WORKER_MAX_JOBS
        # Auto-detect based on router/main LLM provider
        provider = settings.ROUTER_LLM_PROVIDER or settings.LLM_PROVIDER
        if provider in ["lmstudio", "ollama"]:
            logger.info("Local LLM detected - limiting worker to 1 concurrent job")
            return 1
        return 5
    
    max_jobs = _get_max_jobs()
    job_timeout = 300  # 5 minutes max per job (local LLMs need more time)
    keep_result = 3600  # Keep results for 1 hour
    
    # Health check
    health_check_interval = 30


if __name__ == "__main__":
    # Allow running directly for testing via: python -m src_v2.workers.worker
    # Or use arq CLI: arq src_v2.workers.worker.WorkerSettings
    from arq.worker import run_worker
    
    logger.info(f"Starting Worker with queue: {WorkerSettings.queue_name}")
    run_worker(WorkerSettings)  # type: ignore[arg-type]
