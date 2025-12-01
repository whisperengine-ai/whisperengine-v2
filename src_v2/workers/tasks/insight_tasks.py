from typing import Dict, Any, Optional
from loguru import logger
from src_v2.agents.insight_agent import insight_agent
from src_v2.agents.insight_graph import insight_graph_agent
from src_v2.config.settings import settings

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
        if settings.ENABLE_LANGGRAPH_INSIGHT_AGENT:
            logger.info("Using LangGraph Insight Agent")
            success, summary = await insight_graph_agent.analyze(
                user_id=user_id,
                character_name=character_name,
                trigger=trigger,
                recent_context=recent_context
            )
        else:
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


async def run_reflection(
    ctx: Dict[str, Any],
    user_id: str,
    character_name: str
) -> Dict[str, Any]:
    """
    Analyze user patterns across recent summaries and update insights.
    Also infers user-specific goals from conversation patterns.
    
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
            inferred_goal_slugs = [g.slug for g in result.inferred_goals] if result.inferred_goals else []
            logger.info(f"Reflection complete for user {user_id}: {len(result.insights)} insights, {len(result.updated_traits)} traits, {len(inferred_goal_slugs)} inferred goals")
            return {
                "success": True,
                "insights": result.insights,
                "traits": result.updated_traits,
                "inferred_goals": inferred_goal_slugs,
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
