from typing import Dict, Any
from loguru import logger
from src_v2.config.settings import settings


async def run_diary_generation(
    ctx: Dict[str, Any],
    character_name: str,
    override: bool = False
) -> Dict[str, Any]:
    """
    Generate a diary entry using the LangGraph Diary Agent.
    
    This uses a multi-step graph approach:
    1. Gather material from session summaries
    2. Plan the narrative arc (story structure, emotional journey)
    3. Weave the final diary entry with proper story arc and emotional depth
    
    Diaries are "mask off" - they use the worker model, not the character's voice.
    
    Args:
        ctx: arq context
        character_name: Bot character name (e.g., "elena")
        override: If True, ignore "already exists" check
        
    Returns:
        Dict with success status and diary details
    """
    if not settings.ENABLE_CHARACTER_DIARY:
        return {"success": False, "reason": "disabled"}
    
    logger.info(f"Generating diary entry for {character_name} (override={override})")
    
    try:
        from src_v2.agents.diary_graph import DiaryGraphAgent
        from src_v2.memory.diary import get_diary_manager, DiaryMaterial
        from src_v2.core.behavior import load_behavior_profile
        
        diary_manager = get_diary_manager(character_name)
        
        # Check if diary already exists for today
        if not override and await diary_manager.has_diary_for_today():
            logger.info(f"Diary already exists for {character_name} today, skipping")
            return {
                "success": True,
                "skipped": True,
                "reason": "already_exists",
                "character_name": character_name
            }
        
        # Get character description for the agent
        character_description = ""
        try:
            from src_v2.core.character import CharacterManager
            char_manager = CharacterManager()
            character = char_manager.load_character(character_name)
            if character:
                character_description = character.system_prompt
        except Exception as e:
            logger.warning(f"Failed to load full character prompt for {character_name}: {e}")
            # Fallback to behavior profile only
            try:
                character_dir = f"characters/{character_name}"
                behavior = load_behavior_profile(character_dir)
                if behavior:
                    character_description = behavior.to_prompt_section()
            except Exception:
                pass
        
        if not character_description:
            character_description = f"You are {character_name.title()}, an AI companion."
        
        # Run LangGraph Diary Agent
        logger.info(f"Using LangGraph Diary Agent for {character_name}")
        graph_agent = DiaryGraphAgent()
        
        # Gather material (summaries are the main source)
        # Use the proper method to gather all material
        material = await diary_manager.gather_diary_material(hours=24)
        
        # Note: We intentionally don't skip on insufficient material.
        # The diary graph handles sparse days gracefully, and the character
        # should still reflect even on quiet days (emergence philosophy).
        
        # Count users
        unique_user_ids = set(s.get("user_id", "unknown") for s in material.summaries)
        user_count = len(unique_user_ids)
        user_names = [f"{user_count} different {'people' if user_count > 1 else 'person'}"]
        
        # Run Graph
        entry = await graph_agent.run(
            material=material,
            character_context=character_description,
            user_names=user_names
        )
        
        if not entry:
            logger.warning("LangGraph Diary Agent returned None")
            return {
                "success": False,
                "error": "graph_returned_none",
                "character_name": character_name
            }
            
        # Save
        provenance_data = [{"type": "summary", "count": len(material.summaries)}]
        point_id = await diary_manager.save_diary_entry(entry, provenance=provenance_data)
        
        # Queue Broadcast
        broadcast_queued = False
        if settings.ENABLE_BOT_BROADCAST and settings.BOT_BROADCAST_DIARIES:
            try:
                from src_v2.broadcast.manager import broadcast_manager
                public_version = await diary_manager.create_public_version(entry)
                if public_version:
                    broadcast_queued = await broadcast_manager.queue_diary(public_version, character_name, provenance_data)
            except Exception as e:
                logger.warning(f"Failed to queue diary broadcast: {e}")

        if point_id:
            logger.info(f"Diary saved for {character_name}: mood={entry.mood}, themes={entry.themes}")
            return {
                "success": True,
                "character_name": character_name,
                "mood": entry.mood,
                "themes": entry.themes,
                "notable_users": entry.notable_users,
                "point_id": point_id,
                "broadcast_queued": broadcast_queued
            }
        else:
            return {
                "success": False,
                "error": "save_failed",
                "character_name": character_name
            }
        
    except Exception as e:
        logger.error(f"Diary generation failed for {character_name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "character_name": character_name
        }


# Backward compatibility alias
run_agentic_diary_generation = run_diary_generation
