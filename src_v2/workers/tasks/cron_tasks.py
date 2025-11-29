from typing import Dict, Any
from loguru import logger
from src_v2.config.settings import settings
from src_v2.core.database import db_manager
from src_v2.workers.tasks.diary_tasks import run_diary_generation, run_agentic_diary_generation
from src_v2.workers.tasks.dream_tasks import run_dream_generation, run_agentic_dream_generation

async def run_nightly_diary_generation(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Cron job that generates diary entries for all active characters.
    
    Runs at end of day (default 10 PM UTC) to reflect on the day's events.
    Scans the characters/ directory for available characters and
    triggers diary generation for each one.
    
    If ENABLE_AGENTIC_NARRATIVES is True, uses the DreamWeaver agent for
    richer, multi-step narrative generation with proper story arcs.
    """
    if not settings.ENABLE_CHARACTER_DIARY:
        logger.info("Character diary feature disabled, skipping nightly generation")
        return {"success": False, "reason": "disabled"}
    
    mode = "agentic" if settings.ENABLE_AGENTIC_NARRATIVES else "simple"
    logger.info(f"Starting nightly diary generation for all characters (mode: {mode})")
    
    try:
        from pathlib import Path
        
        # Scan characters directory for available characters
        characters_dir = Path("characters")
        if not characters_dir.exists():
            logger.warning("Characters directory not found")
            return {"success": False, "error": "no_characters_dir"}
        
        # Get all character names (subdirectories with character.md)
        character_names = []
        for char_dir in characters_dir.iterdir():
            if char_dir.is_dir() and (char_dir / "character.md").exists():
                character_names.append(char_dir.name)
        
        if not character_names:
            logger.info("No characters found for diary generation")
            return {"success": True, "processed": 0}
        
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
    Cron job that generates dreams for all active characters.
    
    Runs in the morning (default 7 AM UTC) to share dreams upon waking.
    Scans the characters/ directory for available characters and
    triggers dream generation for each one.
    
    If ENABLE_AGENTIC_NARRATIVES is True, uses the DreamWeaver agent for
    richer, multi-step narrative generation with proper story arcs.
    """
    if not settings.ENABLE_DREAM_SEQUENCES:
        logger.info("Dream sequences feature disabled, skipping nightly generation")
        return {"success": False, "reason": "disabled"}
    
    mode = "agentic" if settings.ENABLE_AGENTIC_NARRATIVES else "simple"
    logger.info(f"Starting nightly dream generation for all characters (mode: {mode})")
    
    try:
        from pathlib import Path
        
        # Scan characters directory for available characters
        characters_dir = Path("characters")
        if not characters_dir.exists():
            logger.warning("Characters directory not found")
            return {"success": False, "error": "no_characters_dir"}
        
        # Get all character names (subdirectories with character.md)
        character_names = []
        for char_dir in characters_dir.iterdir():
            if char_dir.is_dir() and (char_dir / "character.md").exists():
                character_names.append(char_dir.name)
        
        if not character_names:
            logger.info("No characters found for dream generation")
            return {"success": True, "processed": 0}
        
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
