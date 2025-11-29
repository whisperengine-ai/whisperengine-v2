from typing import Dict, Any
from datetime import datetime
from loguru import logger
from src_v2.config.settings import settings
from src_v2.core.database import db_manager
from src_v2.core.behavior import get_character_timezone
from src_v2.workers.tasks.diary_tasks import run_diary_generation, run_agentic_diary_generation
from src_v2.workers.tasks.dream_tasks import run_dream_generation, run_agentic_dream_generation

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo  # Python < 3.9


def is_target_hour_in_timezone(target_hour: int, timezone_str: str) -> bool:
    """
    Check if the current hour in the given timezone matches the target hour.
    This allows cron jobs to run hourly but only process characters when it's
    the right local time for them.
    """
    try:
        tz = ZoneInfo(timezone_str)
        local_now = datetime.now(tz)
        return local_now.hour == target_hour
    except Exception as e:
        logger.warning(f"Invalid timezone '{timezone_str}': {e}, using UTC")
        return datetime.utcnow().hour == target_hour


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
    logger.info(f"Checking for characters with local time {target_hour}:00 for diary generation (mode: {mode})")
    
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
            if is_target_hour_in_timezone(target_hour, char_tz):
                character_names.append(char_name)
                logger.debug(f"Character {char_name} ({char_tz}): it's {target_hour}:00 local, will generate diary")
            else:
                logger.debug(f"Character {char_name} ({char_tz}): not {target_hour}:00 local, skipping")
        
        if not character_names:
            logger.info(f"No characters have local time {target_hour}:00 right now")
            return {"success": True, "processed": 0, "reason": "no_matching_timezone"}
        
        logger.info(f"Found {len(character_names)} characters for diary generation: {character_names}")
        
        # Choose generation function based on settings
        gen_func = run_agentic_diary_generation if settings.ENABLE_AGENTIC_NARRATIVES else run_diary_generation
        
        # Generate diary for each character
        results = []
        for char_name in character_names:
            # Check if character is active (has memory collection)
            # This prevents errors for characters that exist on disk but aren't running/initialized
            collection_name = f"whisperengine_memory_{char_name}"
            try:
                if db_manager.qdrant_client and not await db_manager.qdrant_client.collection_exists(collection_name):
                    logger.info(f"Skipping diary for {char_name}: Memory collection {collection_name} not found (inactive?)")
                    results.append({
                        "character": char_name,
                        "success": True,
                        "skipped": True,
                        "reason": "inactive_no_memory"
                    })
                    continue
            except Exception as e:
                logger.warning(f"Failed to check collection existence for {char_name}: {e}")
                # Continue anyway, let the generation function handle it or fail
            
            try:
                result = await gen_func(ctx, character_name=char_name)
                results.append({
                    "character": char_name,
                    "success": result.get("success", False),
                    "skipped": result.get("skipped", False),
                    "reason": result.get("reason"),
                    "mode": result.get("mode", mode)
                })
            except Exception as e:
                logger.error(f"Diary generation failed for {char_name}: {e}")
                results.append({
                    "character": char_name,
                    "success": False,
                    "error": str(e)
                })
        
        successful = sum(1 for r in results if r.get("success") and not r.get("skipped"))
        skipped = sum(1 for r in results if r.get("skipped"))
        failed = sum(1 for r in results if not r.get("success"))
        
        logger.info(f"Nightly diary generation complete: {successful} generated, {skipped} skipped, {failed} failed (mode: {mode})")
        
        return {
            "success": True,
            "processed": len(character_names),
            "generated": successful,
            "skipped": skipped,
            "failed": failed,
            "mode": mode,
            "results": results
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
    logger.info(f"Checking for characters with local time {target_hour}:00 for dream generation (mode: {mode})")
    
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
            if is_target_hour_in_timezone(target_hour, char_tz):
                character_names.append(char_name)
                logger.debug(f"Character {char_name} ({char_tz}): it's {target_hour}:00 local, will generate dream")
            else:
                logger.debug(f"Character {char_name} ({char_tz}): not {target_hour}:00 local, skipping")
        
        if not character_names:
            logger.info(f"No characters have local time {target_hour}:00 right now")
            return {"success": True, "processed": 0, "reason": "no_matching_timezone"}
        
        logger.info(f"Found {len(character_names)} characters for dream generation: {character_names}")
        
        # Choose generation function based on settings
        gen_func = run_agentic_dream_generation if settings.ENABLE_AGENTIC_NARRATIVES else run_dream_generation
        
        # Generate dream for each character
        results = []
        for char_name in character_names:
            try:
                result = await gen_func(ctx, character_name=char_name)
                results.append({
                    "character": char_name,
                    "success": result.get("success", False),
                    "skipped": result.get("skipped", False),
                    "reason": result.get("reason"),
                    "mode": result.get("mode", mode)
                })
            except Exception as e:
                logger.error(f"Dream generation failed for {char_name}: {e}")
                results.append({
                    "character": char_name,
                    "success": False,
                    "error": str(e)
                })
        
        successful = sum(1 for r in results if r.get("success") and not r.get("skipped"))
        skipped = sum(1 for r in results if r.get("skipped"))
        failed = sum(1 for r in results if not r.get("success"))
        
        logger.info(f"Nightly dream generation complete: {successful} generated, {skipped} skipped, {failed} failed (mode: {mode})")
        
        return {
            "success": True,
            "processed": len(character_names),
            "generated": successful,
            "skipped": skipped,
            "failed": failed,
            "mode": mode,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Nightly dream generation failed: {e}")
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
    logger.info(f"Checking for characters with local time {target_hour}:00 for goal strategist")
    
    try:
        from pathlib import Path
        from src_v2.workers.strategist import goal_strategist
        
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
            if is_target_hour_in_timezone(target_hour, char_tz):
                character_names.append(char_name)
                logger.debug(f"Character {char_name} ({char_tz}): it's {target_hour}:00 local, will run strategist")
            else:
                logger.debug(f"Character {char_name} ({char_tz}): not {target_hour}:00 local, skipping")
        
        if not character_names:
            logger.info(f"No characters have local time {target_hour}:00 right now")
            return {"success": True, "processed": 0, "reason": "no_matching_timezone"}
        
        logger.info(f"Found {len(character_names)} characters for goal strategist: {character_names}")
        
        # Run goal strategist for each character
        results = []
        for char_name in character_names:
            # Check if character is active (has memory collection)
            collection_name = f"whisperengine_memory_{char_name}"
            try:
                if db_manager.qdrant_client and not await db_manager.qdrant_client.collection_exists(collection_name):
                    logger.info(f"Skipping goal strategist for {char_name}: Memory collection {collection_name} not found (inactive?)")
                    results.append({
                        "character": char_name,
                        "success": True,
                        "skipped": True,
                        "reason": "inactive_no_memory"
                    })
                    continue
            except Exception as e:
                logger.warning(f"Failed to check collection existence for {char_name}: {e}")
                # Continue anyway
            
            try:
                await goal_strategist.run_nightly_analysis(char_name)
                results.append({
                    "character": char_name,
                    "success": True,
                    "skipped": False
                })
            except Exception as e:
                logger.error(f"Goal strategist failed for {char_name}: {e}")
                results.append({
                    "character": char_name,
                    "success": False,
                    "error": str(e)
                })
        
        successful = sum(1 for r in results if r.get("success") and not r.get("skipped"))
        skipped = sum(1 for r in results if r.get("skipped"))
        failed = sum(1 for r in results if not r.get("success"))
        
        logger.info(f"Nightly goal strategist complete: {successful} processed, {skipped} skipped, {failed} failed")
        
        return {
            "success": True,
            "processed": len(character_names),
            "successful": successful,
            "skipped": skipped,
            "failed": failed,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Nightly goal strategist failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }
