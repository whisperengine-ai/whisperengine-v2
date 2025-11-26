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

Usage:
    python -m src_v2.workers.worker
    
Or via arq CLI:
    arq src_v2.workers.worker.WorkerSettings
"""
import asyncio
from typing import Any, Dict, List, Optional
from loguru import logger
from arq import cron
from arq.connections import RedisSettings

from src_v2.workers.task_queue import TaskQueue
from src_v2.agents.insight_agent import insight_agent
from src_v2.core.database import db_manager
from src_v2.config.settings import settings


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


async def run_insight_analysis(
    ctx: Dict[str, Any],
    user_id: str,
    character_name: str,
    trigger: str = "volume",
    priority: int = 5,
    recent_context: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main task function for running insight analysis.
    
    Args:
        ctx: arq context (contains worker state)
        user_id: Discord user ID to analyze
        character_name: Bot character name
        trigger: What triggered this analysis
        priority: Task priority (unused currently)
        recent_context: Optional recent conversation text
        
    Returns:
        Dict with success status and summary
    """
    logger.info(f"Processing insight analysis for user {user_id} (character: {character_name}, trigger: {trigger})")
    
    try:
        success, summary = await insight_agent.analyze(
            user_id=user_id,
            character_name=character_name,
            trigger=trigger,
            recent_context=recent_context
        )
        
        return {
            "success": success,
            "summary": summary,
            "user_id": user_id,
            "character_name": character_name
        }
        
    except Exception as e:
        logger.error(f"Insight analysis failed for user {user_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "user_id": user_id,
            "character_name": character_name
        }


async def run_summarization(
    ctx: Dict[str, Any],
    user_id: str,
    character_name: str,
    session_id: str,
    messages: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Generate a session summary and save to database.
    
    Args:
        ctx: arq context
        user_id: Discord user ID
        character_name: Bot character name
        session_id: Conversation session ID
        messages: List of message dicts with 'role' and 'content' keys
        
    Returns:
        Dict with success status and summary content
    """
    logger.info(f"Processing summarization for session {session_id} (user: {user_id}, character: {character_name})")
    
    try:
        # Lazy import to avoid circular dependencies
        from src_v2.memory.summarizer import SummaryManager
        
        # Pass character_name to ensure we use the correct memory collection
        summarizer = SummaryManager(bot_name=character_name)
        result = await summarizer.generate_summary(messages)
        
        if result and result.meaningfulness_score >= 3:
            await summarizer.save_summary(session_id, user_id, result)
            logger.info(f"Summary saved for session {session_id} (score: {result.meaningfulness_score})")
            return {
                "success": True,
                "summary": result.summary,
                "meaningfulness_score": result.meaningfulness_score,
                "emotions": result.emotions,
                "session_id": session_id
            }
        else:
            logger.info(f"Session {session_id} not meaningful enough to summarize (score: {result.meaningfulness_score if result else 0})")
            return {
                "success": True,
                "skipped": True,
                "reason": "low_meaningfulness",
                "session_id": session_id
            }
            
    except Exception as e:
        logger.error(f"Summarization failed for session {session_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "session_id": session_id
        }


async def run_reflection(
    ctx: Dict[str, Any],
    user_id: str,
    character_name: str
) -> Dict[str, Any]:
    """
    Analyze user patterns across recent summaries and update insights.
    
    Args:
        ctx: arq context
        user_id: Discord user ID
        character_name: Bot character name
        
    Returns:
        Dict with success status and extracted insights
    """
    logger.info(f"Processing reflection for user {user_id} (character: {character_name})")
    
    try:
        from src_v2.intelligence.reflection import ReflectionEngine
        
        reflection_engine = ReflectionEngine()
        result = await reflection_engine.analyze_user_patterns(user_id, character_name)
        
        if result:
            logger.info(f"Reflection complete for user {user_id}: {len(result.insights)} insights, {len(result.updated_traits)} traits")
            return {
                "success": True,
                "insights": result.insights,
                "traits": result.updated_traits,
                "user_id": user_id,
                "character_name": character_name
            }
        else:
            return {
                "success": True,
                "skipped": True,
                "reason": "no_summaries",
                "user_id": user_id
            }
            
    except Exception as e:
        logger.error(f"Reflection failed for user {user_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "user_id": user_id
        }


async def run_knowledge_extraction(
    ctx: Dict[str, Any],
    user_id: str,
    message: str
) -> Dict[str, Any]:
    """
    Extract facts from a message and store in Neo4j knowledge graph.
    
    This is the most critical background task - it was previously blocking
    the response pipeline. Now runs asynchronously after response is sent.
    
    Args:
        ctx: arq context
        user_id: Discord user ID
        message: User message text to extract facts from
        
    Returns:
        Dict with success status and extracted fact count
    """
    logger.info(f"Processing knowledge extraction for user {user_id}")
    
    try:
        from src_v2.knowledge.manager import knowledge_manager
        
        # This internally checks ENABLE_RUNTIME_FACT_EXTRACTION
        await knowledge_manager.process_user_message(user_id, message)
        
        return {
            "success": True,
            "user_id": user_id,
            "message_length": len(message)
        }
        
    except Exception as e:
        logger.error(f"Knowledge extraction failed for user {user_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "user_id": user_id
        }


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
