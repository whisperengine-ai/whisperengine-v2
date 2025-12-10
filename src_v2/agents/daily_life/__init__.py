"""
Daily Life Graph - Stigmergic Agent Loop for autonomous bot behavior.

This module implements the unified "daily life" system that replaces:
- ActivityOrchestrator (timer-based triggering)
- CrossBotManager (Redis locks for turn-taking)
- ReactionAgent (probability-based reactions)
- LurkDetector (background channel monitoring)
- Scattered cron jobs (diary, dream, goal)

Key principle: The environment IS the state. The bot queries Discord and its
own artifacts to discover what needs doing. Stigmergic, not scheduled.

Usage:
    from src_v2.agents.daily_life import DailyLifeGraph
    
    graph = DailyLifeGraph(bot=discord_bot, character=character)
    result = await graph.run()
"""

from src_v2.agents.daily_life.graph import DailyLifeGraph
from src_v2.agents.daily_life.state import (
    DailyLifeState,
    InternalLifeState,
    RelationshipState,
    ChannelState,
    ScoredMessage,
    PlannedAction,
    ActionResult,
)

__all__ = [
    "DailyLifeGraph",
    "DailyLifeState",
    "InternalLifeState",
    "RelationshipState",
    "ChannelState",
    "ScoredMessage",
    "PlannedAction",
    "ActionResult",
]
