"""
Goal Strategist Worker

Runs nightly to analyze goal progress and generate strategies.
Part of Autonomous Agents Phase 3.1.

Note: The legacy GoalStrategist class was removed in Dec 2024.
All strategy generation now uses the LangGraph-based strategist_graph_agent.
"""
from typing import Dict, Any
from datetime import datetime
from loguru import logger
from src_v2.config.settings import settings
from src_v2.core.database import db_manager

# Redis key prefix for goal strategist locks
STRATEGIST_LOCK_PREFIX = "strategist:generation:lock:"
STRATEGIST_LOCK_TTL = 600  # 10 minutes - enough for strategist run


async def _acquire_strategist_lock(bot_name: str) -> bool:
    """
    Acquire a distributed lock for goal strategist.
    
    Uses Redis SET NX (set if not exists) with TTL to prevent
    multiple strategist runs for the same character on the same day.
    
    Returns:
        True if lock acquired, False if another job is already running
    """
    if not db_manager.redis_client:
        logger.warning("Redis not available, skipping lock")
        return True  # Allow to proceed without lock
    
    try:
        # Use today's date (UTC) in the lock key so it resets daily
        today = datetime.utcnow().strftime("%Y-%m-%d")
        lock_key = f"{STRATEGIST_LOCK_PREFIX}{bot_name}:{today}"
        
        # SET NX with TTL - atomic operation
        result = await db_manager.redis_client.set(
            lock_key,
            datetime.utcnow().isoformat(),
            nx=True,  # Only set if not exists
            ex=STRATEGIST_LOCK_TTL  # Expire after 10 minutes
        )
        
        if result:
            logger.debug(f"Acquired strategist lock for {bot_name} on {today}")
            return True
        else:
            logger.info(f"Strategist lock already held for {bot_name} on {today}, skipping")
            return False
            
    except Exception as e:
        logger.warning(f"Failed to acquire strategist lock: {e}")
        return True  # Allow to proceed on error


async def run_goal_strategist(_ctx: Dict[str, Any], bot_name: str) -> Dict[str, Any]:
    """
    Worker task entry point for goal strategist.
    
    Called by arq worker on schedule or manually.
    
    Args:
        _ctx: arq context (unused but required by arq signature)
        bot_name: The character/bot name to run strategist for
        
    Returns:
        Dict with success status and results
    """
    if not settings.ENABLE_GOAL_STRATEGIST:
        logger.debug("Goal strategist is disabled, skipping")
        return {"success": False, "reason": "disabled"}
    
    # Acquire distributed lock to prevent duplicate runs
    if not await _acquire_strategist_lock(bot_name):
        return {
            "success": True,
            "skipped": True,
            "reason": "lock_held",
            "character_name": bot_name
        }
    
    # Use the LangGraph-based strategist agent
    logger.info(f"Running LangGraph Strategist Agent for {bot_name}")
    from src_v2.agents.strategist_graph import strategist_graph_agent, save_strategist_output
    
    try:
        output = await strategist_graph_agent.run(bot_name)
        
        if output:
            results = await save_strategist_output(bot_name, output)
            logger.info(
                f"Strategist complete for {bot_name}: "
                f"{results['strategies_applied']} strategies, "
                f"{results['goals_created']} new goals"
            )
            return {
                "success": True,
                "strategies_applied": results["strategies_applied"],
                "goals_created": results["goals_created"],
                "summary": output.summary,
                "character_name": bot_name
            }
        else:
            return {
                "success": True,
                "skipped": True,
                "reason": "no_output",
                "character_name": bot_name
            }
    except Exception as e:
        logger.error(f"LangGraph strategist failed for {bot_name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "character_name": bot_name
        }
