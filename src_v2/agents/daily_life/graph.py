"""
Daily Life Graph - Main graph construction and entry point.

Stigmergic Agent Loop: Sense → Decide → Act → Trace
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional, TYPE_CHECKING

from loguru import logger
from langgraph.graph import StateGraph, END

import discord
from discord.ext import commands

from src_v2.agents.daily_life.state import (
    DailyLifeState,
    PlannedAction,
    ActionResult,
)
from src_v2.agents.daily_life.gather import gather_context
from src_v2.agents.daily_life.plan import plan_actions
from src_v2.agents.daily_life.execute import execute_action
from src_v2.config.settings import settings

if TYPE_CHECKING:
    from src_v2.core.character import Character


# ──────────────────────────────────────────────────────────────────────────────
# SUMMARIZE NODE
# ──────────────────────────────────────────────────────────────────────────────

async def summarize_session(state: DailyLifeState) -> Dict[str, Any]:
    """
    Trace phase: Log a summary of the session.
    
    This creates observability for:
    - Research (decision patterns)
    - Metrics (action counts, skip rates)
    - Debugging (what happened and why)
    """
    
    executed = state.get("executed_actions", [])
    planned = state.get("planned_actions", [])
    
    # Count outcomes
    social_count = sum(1 for a in executed if a.action.action_type in ("reply", "react", "post", "reach_out") and a.success)
    internal_count = sum(1 for a in executed if a.action.action_type in ("write_diary", "generate_dream", "review_goals") and a.success)
    skipped = any(a.action.action_type == "skip" for a in executed)
    failed = [a for a in executed if not a.success and a.action.action_type != "skip"]
    
    # Build summary
    if skipped and len(executed) == 1:
        summary = f"Session complete: Skipped (nothing needed)"
    else:
        parts = []
        if social_count:
            parts.append(f"Social={social_count}")
        if internal_count:
            parts.append(f"Internal={internal_count}")
        if failed:
            parts.append(f"Failed={len(failed)}")
        summary = f"Session complete: {', '.join(parts) if parts else 'No actions'}"
    
    logger.info(f"[DailyLife] {state.get('character_name', 'unknown')} {summary}")
    
    # Log to metrics (if InfluxDB available)
    try:
        from src_v2.core.database import db_manager
        
        if db_manager.influxdb_client:
            from influxdb_client import Point
            
            point = (
                Point("daily_life_session")
                .tag("bot_name", state.get("bot_name", "unknown"))
                .tag("time_of_day", state.get("time_of_day", "unknown"))
                .field("social_actions", social_count)
                .field("internal_actions", internal_count)
                .field("skipped", 1 if skipped else 0)
                .field("failed", len(failed))
                .field("llm_invoked", 0 if state.get("should_skip") else 1)
                .field("mentions_count", len(state.get("mentions", [])))
                .field("channels_count", len(state.get("channel_states", [])))
            )
            
            write_api = db_manager.influxdb_client.write_api()
            write_api.write(bucket=settings.INFLUXDB_BUCKET, record=point)
    except Exception as e:
        logger.debug(f"[DailyLife] Metrics write failed (non-critical): {e}")
    
    return {"summary": summary}


# ──────────────────────────────────────────────────────────────────────────────
# ROUTING LOGIC
# ──────────────────────────────────────────────────────────────────────────────

def should_skip_planning(state: DailyLifeState) -> str:
    """Route after gather: skip to summarize or continue to plan."""
    should_skip = state.get("should_skip", False)
    time_of_day = state.get("time_of_day", "unknown")
    
    logger.info(f"[DailyLife] Routing: should_skip={should_skip}, time_of_day={time_of_day}")
    
    # Safety check: if gather failed (time_of_day is unknown), skip planning
    if time_of_day == "unknown":
        logger.warning("[DailyLife] Gather seemingly failed (time_of_day unknown) - skipping planning")
        return "summarize"
        
    if should_skip:
        return "summarize"
    return "plan"


def should_continue_executing(state: DailyLifeState) -> str:
    """Route after execute: continue executing or go to summarize."""
    planned = state.get("planned_actions", [])
    current_idx = state.get("current_action_index", 0)
    
    if current_idx >= len(planned):
        return "summarize"
    return "execute"


# ──────────────────────────────────────────────────────────────────────────────
# GRAPH CLASS
# ──────────────────────────────────────────────────────────────────────────────

class DailyLifeGraph:
    """
    The bot's autonomous rhythm - social engagement and internal life.
    
    Runs periodically via worker cron. Each run:
    1. Gathers context (Discord, internal state, relationships)
    2. Plans actions (LLM decides what to do)
    3. Executes actions (delegates to specialized agents)
    4. Summarizes (logs for observability)
    
    Key principle: The environment IS the state. Stateless execution.
    """
    
    def __init__(self, bot: commands.Bot, character: "Character"):
        self.bot = bot
        self.character = character
        
        # Build the graph
        self.graph = self._build_graph()
    
    def _build_graph(self):
        """Build the LangGraph workflow."""
        
        workflow = StateGraph(DailyLifeState)
        
        # Add nodes with closures to pass bot/character
        async def _gather(state: DailyLifeState) -> Dict[str, Any]:
            try:
                result = await gather_context(state, self.bot, self.character)
                # Log key decision factors for debugging
                logger.info(
                    f"[DailyLife] Gather complete: "
                    f"should_skip={result.get('should_skip')}, "
                    f"relevant={result.get('has_relevant_content')}, "
                    f"pending={result.get('has_pending_internal_tasks')}"
                )
                return result
            except Exception as e:
                logger.error(f"[DailyLife] Gather failed with exception: {e}")
                # Return minimal state to prevent graph crash, but ensure we skip planning
                return {
                    "should_skip": True, 
                    "error": str(e),
                    "time_of_day": "unknown" # Explicitly mark as unknown
                }
        
        async def _plan(state: DailyLifeState) -> Dict[str, Any]:
            return await plan_actions(state, self.character)
        
        async def _execute(state: DailyLifeState) -> Dict[str, Any]:
            return await execute_action(state, self.bot, self.character)
        
        async def _summarize(state: DailyLifeState) -> Dict[str, Any]:
            return await summarize_session(state)
        
        workflow.add_node("gather", _gather)
        workflow.add_node("plan", _plan)
        workflow.add_node("execute", _execute)
        workflow.add_node("summarize", _summarize)
        
        # Entry point
        workflow.set_entry_point("gather")
        
        # Edges
        workflow.add_conditional_edges(
            "gather",
            should_skip_planning,
            {
                "summarize": "summarize",
                "plan": "plan",
            }
        )
        
        workflow.add_edge("plan", "execute")
        
        workflow.add_conditional_edges(
            "execute",
            should_continue_executing,
            {
                "execute": "execute",
                "summarize": "summarize",
            }
        )
        
        workflow.add_edge("summarize", END)
        
        return workflow.compile()
    
    async def run(self) -> Dict[str, Any]:
        """
        Run the daily life check.
        
        Returns a summary dict with actions taken.
        """
        
        # Build initial state
        # Get character purpose from behavior profile if available
        character_purpose = "A thoughtful AI assistant"
        if self.character.behavior and hasattr(self.character.behavior, "purpose"):
            character_purpose = self.character.behavior.purpose
        
        initial_state: DailyLifeState = {
            # Bot & Character
            "bot_name": settings.DISCORD_BOT_NAME or "unknown",
            "character_name": self.character.name,
            "character_summary": character_purpose,
            
            # Time (will be updated by gather)
            "current_time": datetime.now(timezone.utc),
            "time_of_day": "unknown",
            "day_of_week": "",
            "hours_since_last_check": 0.0,
            
            # Internal state (will be updated by gather)
            "diary_overdue": False,
            "last_diary_date": None,
            "dreams_could_generate": False,
            "goals_stale": False,
            "last_goal_review": None,
            
            # Relationship state
            "concerning_absences": [],
            "active_relationship_count": 0,
            
            # Discord state
            "mentions": [],
            "channel_states": [],
            "my_recent_activity": {},
            
            # Derived flags
            "has_relevant_content": False,
            "has_pending_internal_tasks": False,
            "should_skip": False,  # Revert to False (logic should handle it)
            
            # Planning & Execution
            "messages": [],
            "planned_actions": [],
            "executed_actions": [],
            "current_action_index": 0,
            
            # Output
            "summary": "",
        }
        
        try:
            # Run the graph
            result = await self.graph.ainvoke(initial_state)
            
            return {
                "success": True,
                "summary": result.get("summary", ""),
                "actions_taken": len([a for a in result.get("executed_actions", []) if a.success and a.action.action_type != "skip"]),
                "skipped": result.get("should_skip", False),
            }
            
        except Exception as e:
            logger.error(f"[DailyLife] Graph execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }


# ──────────────────────────────────────────────────────────────────────────────
# CONVENIENCE RUNNER
# ──────────────────────────────────────────────────────────────────────────────

async def run_daily_life_check(
    bot: commands.Bot,
    character: "Character",
) -> Dict[str, Any]:
    """
    Convenience function to run a daily life check.
    
    Can be called directly from bot code or worker.
    """
    
    graph = DailyLifeGraph(bot, character)
    return await graph.run()
