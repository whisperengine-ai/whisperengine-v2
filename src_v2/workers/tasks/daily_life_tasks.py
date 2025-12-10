"""
Daily Life cron task - Triggers all bots to run their daily life check.

This consolidates diary, dream, goal, and social activity cron jobs into a single
unified "daily life" rhythm.
"""

import asyncio
from typing import Dict, Any, List
from loguru import logger

from src_v2.config.settings import settings


# Registry of active bot instances (populated at bot startup)
# Maps bot_name -> (discord_bot, character) tuple
_active_bots: Dict[str, tuple] = {}


def register_bot(bot_name: str, discord_bot, character) -> None:
    """Register a bot instance for daily life checks."""
    _active_bots[bot_name] = (discord_bot, character)
    logger.info(f"[DailyLife] Registered bot: {bot_name}")


def unregister_bot(bot_name: str) -> None:
    """Unregister a bot instance."""
    if bot_name in _active_bots:
        del _active_bots[bot_name]
        logger.info(f"[DailyLife] Unregistered bot: {bot_name}")


async def run_daily_life_cycle(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Trigger all registered bots to run their daily life check.
    
    Runs every 5-10 minutes via cron. Staggers bot checks to avoid rate limits.
    """
    
    if not settings.ENABLE_AUTONOMOUS_ACTIVITY:
        return {"skipped": True, "reason": "ENABLE_AUTONOMOUS_ACTIVITY is False"}
    
    if not _active_bots:
        logger.debug("[DailyLife] No active bots registered")
        return {"skipped": True, "reason": "No active bots"}
    
    # Get stagger delay from settings
    stagger_seconds = getattr(settings, "DISCORD_CHECK_STAGGER_SECONDS", 30)
    
    results: List[Dict[str, Any]] = []
    
    for bot_name, (discord_bot, character) in _active_bots.items():
        try:
            from src_v2.agents.daily_life.graph import run_daily_life_check
            
            result = await run_daily_life_check(discord_bot, character)
            results.append({
                "bot_name": bot_name,
                **result
            })
            
        except Exception as e:
            logger.error(f"[DailyLife] {bot_name} check failed: {e}")
            results.append({
                "bot_name": bot_name,
                "success": False,
                "error": str(e),
            })
        
        # Stagger between bots
        if len(_active_bots) > 1:
            await asyncio.sleep(stagger_seconds)
    
    # Summary
    successful = sum(1 for r in results if r.get("success"))
    total_actions = sum(r.get("actions_taken", 0) for r in results)
    
    logger.info(f"[DailyLife] Cycle complete: {successful}/{len(results)} bots, {total_actions} total actions")
    
    return {
        "bots_checked": len(results),
        "successful": successful,
        "total_actions": total_actions,
        "results": results,
    }


async def run_single_bot_daily_life(ctx: Dict[str, Any], bot_name: str) -> Dict[str, Any]:
    """
    Trigger a single bot's daily life check.
    
    Can be called manually or via queue for specific bot checks.
    """
    
    if not settings.ENABLE_AUTONOMOUS_ACTIVITY:
        return {"skipped": True, "reason": "ENABLE_AUTONOMOUS_ACTIVITY is False"}
    
    if bot_name not in _active_bots:
        return {"skipped": True, "reason": f"Bot {bot_name} not registered"}
    
    discord_bot, character = _active_bots[bot_name]
    
    try:
        from src_v2.agents.daily_life.graph import run_daily_life_check
        
        result = await run_daily_life_check(discord_bot, character)
        return {
            "bot_name": bot_name,
            **result
        }
        
    except Exception as e:
        logger.error(f"[DailyLife] {bot_name} check failed: {e}")
        return {
            "bot_name": bot_name,
            "success": False,
            "error": str(e),
        }
