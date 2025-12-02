from typing import Dict, Any
from datetime import datetime, timedelta
from loguru import logger
from src_v2.config.settings import settings
from src_v2.core.database import db_manager
from src_v2.core.behavior import get_character_timezone
# Note: Tasks are enqueued by name string, so we don't need to import the functions directly
# from src_v2.workers.tasks.diary_tasks import run_diary_generation, run_agentic_diary_generation
# from src_v2.workers.tasks.dream_tasks import run_dream_generation, run_agentic_dream_generation

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo  # Python < 3.9


def is_processing_window(target_hour: int, target_minute: int, timezone_str: str, window_hours: int = 4) -> bool:
    """
    Check if the current time is within the processing window (target time + window).
    This allows catching up on missed jobs if the worker was down.
    """
    try:
        tz = ZoneInfo(timezone_str)
        local_now = datetime.now(tz)
        
        # Check window for TODAY
        target_today = local_now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        end_today = target_today + timedelta(hours=window_hours)
        if target_today <= local_now < end_today:
            return True
            
        # Check window for YESTERDAY (in case we are in the early morning spillover)
        target_yesterday = target_today - timedelta(days=1)
        end_yesterday = target_yesterday + timedelta(hours=window_hours)
        if target_yesterday <= local_now < end_yesterday:
            return True
            
        return False
    except Exception as e:
        logger.warning(f"Invalid timezone '{timezone_str}': {e}, using UTC")
        utc_now = datetime.utcnow()
        return utc_now.hour == target_hour and utc_now.minute == target_minute


async def run_nightly_diary_generation(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Cron job that generates diary entries for characters where it's currently
    the target hour (default: 10 PM) in their local timezone.
    
    Each character can have a timezone in their core.yaml. The cron runs hourly
    and only generates diaries for characters where it's currently 10 PM local.
    
    If ENABLE_AGENTIC_NARRATIVES is True, uses the DreamWeaver agent for
    richer, multi-step narrative generation with proper story arcs.
    """
    if not settings.ENABLE_CHARACTER_DIARY:
        logger.info("Character diary feature disabled, skipping nightly generation")
        return {"success": False, "reason": "disabled"}
    
    mode = "agentic" if settings.ENABLE_AGENTIC_NARRATIVES else "simple"
    target_hour = settings.DIARY_GENERATION_LOCAL_HOUR
    target_minute = settings.DIARY_GENERATION_LOCAL_MINUTE
    logger.info(f"Checking for characters with local time {target_hour}:{target_minute:02d} for diary generation (mode: {mode})")
    
    try:
        from pathlib import Path
        
        # Scan characters directory for available characters
        characters_dir = Path("characters")
        if not characters_dir.exists():
            logger.warning("Characters directory not found")
            return {"success": False, "error": "no_characters_dir"}
        
        # Get all character names (subdirectories with character.md)
        all_characters = []
        for char_dir in characters_dir.iterdir():
            if char_dir.is_dir() and (char_dir / "character.md").exists():
                all_characters.append(char_dir.name)
        
        if not all_characters:
            logger.info("No characters found for diary generation")
            return {"success": True, "processed": 0}
        
        # Filter to only characters where it's the target hour in their timezone
        character_names = []
        for char_name in all_characters:
            char_tz = get_character_timezone(char_name)
            if is_processing_window(target_hour, target_minute, char_tz):
                character_names.append(char_name)
                logger.debug(f"Character {char_name} ({char_tz}): in diary window {target_hour}:{target_minute:02d}, will generate if needed")
            else:
                logger.debug(f"Character {char_name} ({char_tz}): not in diary window {target_hour}:{target_minute:02d}, skipping")
        
        if not character_names:
            logger.info(f"No characters in diary window {target_hour}:{target_minute:02d} right now")
            return {"success": True, "processed": 0, "reason": "no_matching_timezone"}
        
        logger.info(f"Found {len(character_names)} characters for diary generation: {character_names}")
        
        # Choose generation function based on settings
        job_name = "run_agentic_diary_generation" if settings.ENABLE_AGENTIC_NARRATIVES else "run_diary_generation"
        
        # Run diary generation for each character
        processed_count = 0
        for char_name in character_names:
            # Check if character is active (has memory collection)
            collection_name = f"whisperengine_memory_{char_name}"
            try:
                if db_manager.qdrant_client and not await db_manager.qdrant_client.collection_exists(collection_name):
                    logger.info(f"Skipping diary for {char_name}: Memory collection {collection_name} not found (inactive?)")
                    continue
            except Exception as e:
                logger.warning(f"Failed to check collection existence for {char_name}: {e}")
                # Continue anyway
            
            try:
                # Enqueue job instead of running directly
                # This decouples scheduling from execution
                await ctx['redis'].enqueue_job(job_name, character_name=char_name, _queue_name="arq:cognition")
                processed_count += 1
                logger.debug(f"Enqueued diary generation for {char_name} (job: {job_name}) to arq:cognition")
            except Exception as e:
                logger.error(f"Failed to enqueue diary for {char_name}: {e}")
        
        logger.info(f"Nightly diary generation check complete: {processed_count} processed (mode: {mode})")
        
        return {
            "success": True,
            "processed": processed_count,
            "mode": mode
        }
        
    except Exception as e:
        logger.error(f"Nightly diary generation failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def run_nightly_dream_generation(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Cron job that generates dreams for characters where it's currently
    the target hour (default: 7 AM) in their local timezone.
    
    Each character can have a timezone in their core.yaml. The cron runs hourly
    and only generates dreams for characters where it's currently 7 AM local.
    
    If ENABLE_AGENTIC_NARRATIVES is True, uses the DreamWeaver agent for
    richer, multi-step narrative generation with proper story arcs.
    """
    if not settings.ENABLE_DREAM_SEQUENCES:
        logger.info("Dream sequences feature disabled, skipping nightly generation")
        return {"success": False, "reason": "disabled"}
    
    mode = "agentic" if settings.ENABLE_AGENTIC_NARRATIVES else "simple"
    target_hour = settings.DREAM_GENERATION_LOCAL_HOUR
    target_minute = settings.DREAM_GENERATION_LOCAL_MINUTE
    logger.info(f"Checking for characters with local time {target_hour}:{target_minute:02d} for dream generation (mode: {mode})")
    
    try:
        from pathlib import Path
        
        # Scan characters directory for available characters
        characters_dir = Path("characters")
        if not characters_dir.exists():
            logger.warning("Characters directory not found")
            return {"success": False, "error": "no_characters_dir"}
        
        # Get all character names (subdirectories with character.md)
        all_characters = []
        for char_dir in characters_dir.iterdir():
            if char_dir.is_dir() and (char_dir / "character.md").exists():
                all_characters.append(char_dir.name)
        
        if not all_characters:
            logger.info("No characters found for dream generation")
            return {"success": True, "processed": 0}
        
        # Filter to only characters where it's the target hour in their timezone
        character_names = []
        for char_name in all_characters:
            char_tz = get_character_timezone(char_name)
            if is_processing_window(target_hour, target_minute, char_tz):
                character_names.append(char_name)
                logger.debug(f"Character {char_name} ({char_tz}): in dream window {target_hour}:{target_minute:02d}, will generate if needed")
            else:
                logger.debug(f"Character {char_name} ({char_tz}): not in dream window {target_hour}:{target_minute:02d}, skipping")
        
        if not character_names:
            logger.info(f"No characters in dream window {target_hour}:{target_minute:02d} right now")
            return {"success": True, "processed": 0, "reason": "no_matching_timezone"}
        
        logger.info(f"Found {len(character_names)} characters for dream generation: {character_names}")
        
        # Choose generation function based on settings
        job_name = "run_agentic_dream_generation" if settings.ENABLE_AGENTIC_NARRATIVES else "run_dream_generation"
        
        # Run dream generation for each character
        processed_count = 0
        for char_name in character_names:
            try:
                # Enqueue job instead of running directly
                await ctx['redis'].enqueue_job(job_name, character_name=char_name, _queue_name="arq:cognition")
                processed_count += 1
                logger.debug(f"Enqueued dream generation for {char_name} (job: {job_name}) to arq:cognition")
            except Exception as e:
                logger.error(f"Failed to enqueue dream for {char_name}: {e}")
        
        logger.info(f"Nightly dream generation check complete: {processed_count} processed (mode: {mode})")
        
        return {
            "success": True,
            "processed": processed_count,
            "mode": mode
        }
        
    except Exception as e:
        logger.error(f"Nightly dream generation failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def run_weekly_drift_observation(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Weekly cron job that observes personality drift for all active characters.
    
    Runs once per week (Sunday at midnight UTC) and compares recent responses
    to a baseline embedding to detect personality drift over time.
    
    Phase E16: Feedback Loop Stability - Observability layer for emergence.
    """
    if not settings.ENABLE_DRIFT_OBSERVATION:
        logger.info("Drift observation feature disabled, skipping weekly run")
        return {"success": False, "reason": "disabled"}
    
    logger.info("Starting weekly drift observation for all characters")
    
    try:
        from pathlib import Path
        from src_v2.workers.tasks.drift_observation import run_drift_observation
        
        # Scan characters directory for available characters
        characters_dir = Path("characters")
        if not characters_dir.exists():
            logger.warning("Characters directory not found")
            return {"success": False, "error": "no_characters_dir"}
        
        # Get all character names (subdirectories with character.md)
        all_characters = []
        for char_dir in characters_dir.iterdir():
            if char_dir.is_dir() and (char_dir / "character.md").exists():
                all_characters.append(char_dir.name)
        
        if not all_characters:
            logger.info("No characters found for drift observation")
            return {"success": True, "processed": 0}
        
        logger.info(f"Running drift observation for {len(all_characters)} characters")
        
        # Run drift observation for each character
        processed_count = 0
        drift_results = {}
        for char_name in all_characters:
            # Check if character is active (has memory collection)
            collection_name = f"whisperengine_memory_{char_name}"
            try:
                if db_manager.qdrant_client and not await db_manager.qdrant_client.collection_exists(collection_name):
                    logger.debug(f"Skipping drift observation for {char_name}: not active")
                    continue
            except Exception as e:
                logger.warning(f"Failed to check collection existence for {char_name}: {e}")
                continue
            
            try:
                result = await run_drift_observation(ctx, char_name)
                if result.get("success"):
                    processed_count += 1
                    drift_results[char_name] = result.get("drift_score", 0.0)
                    logger.info(f"Drift observation for {char_name}: distance={result.get('drift_score', 0.0):.4f}")
            except Exception as e:
                logger.error(f"Failed drift observation for {char_name}: {e}")
        
        logger.info(f"Weekly drift observation complete: {processed_count} characters processed")
        
        return {
            "success": True,
            "processed": processed_count,
            "drift_results": drift_results
        }
        
    except Exception as e:
        logger.error(f"Weekly drift observation failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def run_nightly_goal_strategist(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Cron job that runs goal strategist for characters where it's currently
    the target hour (default: 11 PM) in their local timezone.
    
    Each character can have a timezone in their core.yaml. The cron runs hourly
    and only runs the strategist for characters where it's currently 11 PM local.
    
    This is part of Autonomous Agents Phase 3.1.
    """
    if not settings.ENABLE_GOAL_STRATEGIST:
        logger.info("Goal strategist feature disabled, skipping nightly run")
        return {"success": False, "reason": "disabled"}
    
    target_hour = settings.GOAL_STRATEGIST_LOCAL_HOUR
    target_minute = 0  # Default to on the hour
    logger.info(f"Checking for characters with local time {target_hour}:{target_minute:02d} for goal strategist")
    
    try:
        from pathlib import Path
        
        # Scan characters directory for available characters
        characters_dir = Path("characters")
        if not characters_dir.exists():
            logger.warning("Characters directory not found")
            return {"success": False, "error": "no_characters_dir"}
        
        # Get all character names (subdirectories with character.md)
        all_characters = []
        for char_dir in characters_dir.iterdir():
            if char_dir.is_dir() and (char_dir / "character.md").exists():
                all_characters.append(char_dir.name)
        
        if not all_characters:
            logger.info("No characters found for goal strategist")
            return {"success": True, "processed": 0}
        
        # Filter to only characters where it's the target hour in their timezone
        character_names = []
        for char_name in all_characters:
            char_tz = get_character_timezone(char_name)
            if is_processing_window(target_hour, target_minute, char_tz):
                character_names.append(char_name)
                logger.debug(f"Character {char_name} ({char_tz}): in goal strategist window {target_hour}:{target_minute:02d}, will run if needed")
            else:
                logger.debug(f"Character {char_name} ({char_tz}): not in goal strategist window {target_hour}:{target_minute:02d}, skipping")
        
        if not character_names:
            logger.info(f"No characters in goal strategist window {target_hour}:{target_minute:02d} right now")
            return {"success": True, "processed": 0, "reason": "no_matching_timezone"}
        
        logger.info(f"Found {len(character_names)} characters for goal strategist: {character_names}")
        
        # Enqueue goal strategist for each character
        queued_count = 0
        for char_name in character_names:
            # Check if character is active (has memory collection)
            collection_name = f"whisperengine_memory_{char_name}"
            try:
                if db_manager.qdrant_client and not await db_manager.qdrant_client.collection_exists(collection_name):
                    logger.info(f"Skipping goal strategist for {char_name}: Memory collection {collection_name} not found (inactive?)")
                    continue
            except Exception as e:
                logger.warning(f"Failed to check collection existence for {char_name}: {e}")
                # Continue anyway
            
            try:
                # Enqueue the job to run in parallel
                await ctx["redis"].enqueue_job("run_goal_strategist", bot_name=char_name, _queue_name="arq:cognition")
                queued_count += 1
                logger.debug(f"Queued goal strategist for {char_name} to arq:cognition")
            except Exception as e:
                logger.error(f"Failed to enqueue goal strategist for {char_name}: {e}")
        
        logger.info(f"Nightly goal strategist check complete: {queued_count} jobs queued")
        
        return {
            "success": True,
            "processed": len(character_names),
            "queued": queued_count
        }
        
    except Exception as e:
        logger.error(f"Nightly goal strategist failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }
