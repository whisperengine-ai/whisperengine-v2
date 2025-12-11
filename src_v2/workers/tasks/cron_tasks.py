from typing import Dict, Any, Optional
import random
from datetime import datetime, timedelta
from loguru import logger
from src_v2.config.settings import settings
from src_v2.core.database import db_manager
from src_v2.core.behavior import get_character_timezone
from src_v2.memory.session import session_manager
# Note: Tasks are enqueued by name string, so we don't need to import the functions directly
# from src_v2.workers.tasks.diary_tasks import run_diary_generation, run_agentic_diary_generation
# from src_v2.workers.tasks.dream_tasks import run_dream_generation, run_agentic_dream_generation

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo  # Python < 3.9


def is_processing_window(
    target_hour: int, 
    target_minute: int, 
    timezone_str: str, 
    window_hours: int = 4,
    jitter_minutes: int = 0,
    seed_key: Optional[str] = None
) -> bool:
    """
    Check if the current time is within the processing window (target time + window).
    This allows catching up on missed jobs if the worker was down.
    
    Args:
        target_hour: The hour to start the window
        target_minute: The minute to start the window
        timezone_str: The timezone of the character
        window_hours: How long the window stays open
        jitter_minutes: Max random offset in minutes (±jitter)
        seed_key: Unique key for deterministic jitter (e.g., character name)
    """
    try:
        tz = ZoneInfo(timezone_str)
        local_now = datetime.now(tz)
        
        # Calculate deterministic jitter if enabled
        jitter_offset = 0
        if jitter_minutes > 0 and seed_key:
            # Use date + seed_key to ensure consistent jitter for the day
            # We use local_now.date() so the jitter is fixed for "today"
            seed_str = f"{local_now.date().isoformat()}_{seed_key}"
            # Use a separate Random instance to avoid affecting global state
            rng = random.Random(seed_str)
            jitter_offset = rng.randint(-jitter_minutes, jitter_minutes)
            
        # Check window for TODAY
        target_today = local_now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        
        # Apply jitter
        target_today = target_today + timedelta(minutes=jitter_offset)
        
        end_today = target_today + timedelta(hours=window_hours)
        if target_today <= local_now < end_today:
            return True
            
        # Check window for YESTERDAY (in case we are in the early morning spillover)
        # Re-calculate jitter for yesterday
        jitter_offset_yesterday = 0
        if jitter_minutes > 0 and seed_key:
            yesterday_date = (local_now - timedelta(days=1)).date()
            seed_str = f"{yesterday_date.isoformat()}_{seed_key}"
            rng = random.Random(seed_str)
            jitter_offset_yesterday = rng.randint(-jitter_minutes, jitter_minutes)

        target_yesterday = (local_now - timedelta(days=1)).replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        target_yesterday = target_yesterday + timedelta(minutes=jitter_offset_yesterday)
        
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
    
    Uses the LangGraph Diary Agent for narrative generation.
    """
    if not settings.ENABLE_CHARACTER_DIARY:
        logger.info("Character diary feature disabled, skipping nightly generation")
        return {"success": False, "reason": "disabled"}
    
    target_hour = settings.DIARY_GENERATION_LOCAL_HOUR
    target_minute = settings.DIARY_GENERATION_LOCAL_MINUTE
    jitter_minutes = settings.DIARY_GENERATION_JITTER_MINUTES
    logger.info(f"Checking for characters with local time {target_hour}:{target_minute:02d} (±{jitter_minutes}m) for diary generation")
    
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
            if is_processing_window(target_hour, target_minute, char_tz, jitter_minutes=jitter_minutes, seed_key=char_name):
                character_names.append(char_name)
                logger.debug(f"Character {char_name} ({char_tz}): in diary window {target_hour}:{target_minute:02d}, will generate if needed")
            else:
                logger.debug(f"Character {char_name} ({char_tz}): not in diary window {target_hour}:{target_minute:02d}, skipping")
        
        if not character_names:
            logger.info(f"No characters in diary window {target_hour}:{target_minute:02d} right now")
            return {"success": True, "processed": 0, "reason": "no_matching_timezone"}
        
        logger.info(f"Found {len(character_names)} characters for diary generation: {character_names}")
        
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
                # Enqueue diary generation job
                await ctx['redis'].enqueue_job("run_diary_generation", character_name=char_name, _queue_name="arq:cognition")
                processed_count += 1
                logger.debug(f"Enqueued diary generation for {char_name} to arq:cognition")
            except Exception as e:
                logger.error(f"Failed to enqueue diary for {char_name}: {e}")
        
        logger.info(f"Nightly diary generation check complete: {processed_count} processed")
        
        return {
            "success": True,
            "processed": processed_count
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
    
    Uses the LangGraph Dream Agent for narrative generation.
    """
    if not settings.ENABLE_DREAM_SEQUENCES:
        logger.info("Dream sequences feature disabled, skipping nightly generation")
        return {"success": False, "reason": "disabled"}
    
    target_hour = settings.DREAM_GENERATION_LOCAL_HOUR
    target_minute = settings.DREAM_GENERATION_LOCAL_MINUTE
    jitter_minutes = settings.DREAM_GENERATION_JITTER_MINUTES
    logger.info(f"Checking for characters with local time {target_hour}:{target_minute:02d} (±{jitter_minutes}m) for dream generation")
    
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
            if is_processing_window(target_hour, target_minute, char_tz, jitter_minutes=jitter_minutes, seed_key=char_name):
                character_names.append(char_name)
                logger.debug(f"Character {char_name} ({char_tz}): in dream window {target_hour}:{target_minute:02d}, will generate if needed")
            else:
                logger.debug(f"Character {char_name} ({char_tz}): not in dream window {target_hour}:{target_minute:02d}, skipping")
        
        if not character_names:
            logger.info(f"No characters in dream window {target_hour}:{target_minute:02d} right now")
            return {"success": True, "processed": 0, "reason": "no_matching_timezone"}
        
        logger.info(f"Found {len(character_names)} characters for dream generation: {character_names}")
        
        # Run dream generation for each character
        processed_count = 0
        for char_name in character_names:
            try:
                # Enqueue dream generation job
                await ctx['redis'].enqueue_job("run_dream_generation", character_name=char_name, _queue_name="arq:cognition")
                processed_count += 1
                logger.debug(f"Enqueued dream generation for {char_name} to arq:cognition")
            except Exception as e:
                logger.error(f"Failed to enqueue dream for {char_name}: {e}")
        
        logger.info(f"Nightly dream generation check complete: {processed_count} processed")
        
        return {
            "success": True,
            "processed": processed_count
        }
        
    except Exception as e:
        logger.error(f"Nightly dream generation failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def run_weekly_graph_pruning(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Weekly cron job to run knowledge graph pruning.
    
    Runs once per week to clean up:
    - Orphaned nodes
    - Stale facts
    - Duplicate entities
    - Low-confidence facts
    """
    if not settings.ENABLE_GRAPH_PRUNING:
        logger.info("Graph pruning disabled, skipping")
        return {"success": False, "reason": "disabled"}
    
    try:
        from src_v2.knowledge.pruning import run_scheduled_prune
        
        logger.info("Starting weekly knowledge graph pruning...")
        stats = await run_scheduled_prune()
        
        total = (
            stats.orphans_removed + 
            stats.stale_facts_removed + 
            stats.duplicates_merged + 
            stats.low_confidence_removed
        )
        logger.info(
            f"Graph pruning complete: {total} items cleaned "
            f"(orphans={stats.orphans_removed}, stale={stats.stale_facts_removed}, "
            f"duplicates={stats.duplicates_merged}, low_conf={stats.low_confidence_removed})"
        )
        
        return {
            "success": True,
            "stats": {
                "orphans": stats.orphans_removed,
                "stale": stats.stale_facts_removed,
                "duplicates": stats.duplicates_merged,
                "low_confidence": stats.low_confidence_removed
            }
        }
    except Exception as e:
        logger.error(f"Graph pruning failed: {e}")
        return {"success": False, "error": str(e)}


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


async def run_session_timeout_processing(ctx: Dict[str, Any]) -> Dict[str, Any]:  # noqa: ARG001
    """
    Cron job that runs every 5 minutes to find stale sessions, close them,
    and trigger post-session processing (summarization, goal analysis, etc.).
    
    Args:
        ctx: arq context (required by arq cron interface, unused here)
    """
    # Import here to avoid circular imports at module level
    from src_v2.discord.handlers.message_handler import enqueue_post_conversation_tasks
    
    logger.info("Running session timeout processing...")
    
    # 1. Find stale sessions (inactive > 30 mins)
    stale_sessions = await session_manager.get_stale_sessions(timeout_minutes=30)
    
    if not stale_sessions:
        logger.info("No stale sessions found.")
        return {"success": True, "processed_count": 0}
    
    logger.info(f"Found {len(stale_sessions)} stale sessions to process.")
    processed_count = 0
    
    for session in stale_sessions:
        session_id = str(session['id'])
        user_id = session['user_id']
        character_name = session['character_name']
        
        try:
            # 2. Get messages for the session BEFORE closing it (to get correct time range)
            messages = await session_manager.get_session_messages(session_id)
            
            # 3. Close the session
            await session_manager.close_session(session_id)
            
            if not messages:
                logger.debug(f"Session {session_id} has no messages, skipping processing.")
                continue
                
            # 4. Trigger post-session processing using the canonical pipeline
            user_name = messages[-1].get('user_name', 'User') if messages else 'User'
            
            await enqueue_post_conversation_tasks(
                user_id=user_id,
                character_name=character_name,
                session_id=session_id,
                messages=messages,
                user_name=user_name,
                trigger="session_timeout"
            )
            
            processed_count += 1
            logger.info(f"Processed timeout for session {session_id} (User: {user_id}, Bot: {character_name})")
            
        except Exception as e:
            logger.error(f"Failed to process timeout for session {session_id}: {e}")
            
    return {"success": True, "processed_count": processed_count}
