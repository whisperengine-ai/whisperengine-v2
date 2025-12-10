"""
Goal Strategist Worker

Runs nightly to analyze goal progress and generate strategies.
Part of Autonomous Agents Phase 3.1.

Note: The legacy GoalStrategist class was removed in Dec 2024.
All strategy generation now uses the LangGraph-based strategist_graph_agent.
"""
from typing import Dict, Any
from loguru import logger
from src_v2.config.settings import settings


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
    
    # Use the LangGraph-based strategist agent
    logger.info(f"Running LangGraph Strategist Agent for {bot_name}")
    from src_v2.agents.strategist_graph import strategist_graph_agent, save_strategist_output
    from src_v2.workers.tasks.diary_tasks import record_artifact
    
    try:
        output = await strategist_graph_agent.run(bot_name)
        
        if output:
            results = await save_strategist_output(bot_name, output)
            
            # Record artifact for Daily Life Graph staleness detection (E31)
            await record_artifact(
                character_name=bot_name,
                artifact_type="goal_review",
                metadata={
                    "strategies_applied": results["strategies_applied"],
                    "goals_created": results["goals_created"],
                }
            )
            
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
