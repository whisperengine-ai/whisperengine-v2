from typing import Dict, Any
from loguru import logger
from src_v2.config.settings import settings

async def run_diary_generation(
    ctx: Dict[str, Any],
    character_name: str
) -> Dict[str, Any]:
    """
    Generate a daily diary entry for a character (Phase E2).
    
    This task synthesizes the day's session summaries into a private diary entry
    that gives the character a sense of inner life and temporal continuity.
    
    Args:
        ctx: arq context
        character_name: Bot character name (e.g., "elena")
        
    Returns:
        Dict with success status and diary summary
    """
    if not settings.ENABLE_CHARACTER_DIARY:
        return {"success": False, "reason": "disabled"}
    
    logger.info(f"Generating diary entry for {character_name}")
    
    try:
        from src_v2.memory.diary import get_diary_manager
        from src_v2.memory.manager import MemoryManager
        from src_v2.core.behavior import load_behavior_profile
        
        diary_manager = get_diary_manager(character_name)
        memory_manager = MemoryManager(bot_name=character_name)
        
        # Check if diary already exists for today
        if await diary_manager.has_diary_for_today():
            logger.info(f"Diary already exists for {character_name} today, skipping")
            return {
                "success": True,
                "skipped": True,
                "reason": "already_exists",
                "character_name": character_name
            }
        
        # Get today's summaries
        summaries = await memory_manager.get_summaries_since(hours=24, limit=30)
        
        if len(summaries) < settings.DIARY_MIN_SESSIONS:
            logger.info(f"Not enough sessions for {character_name} diary (have {len(summaries)}, need {settings.DIARY_MIN_SESSIONS})")
            return {
                "success": True,
                "skipped": True,
                "reason": "insufficient_sessions",
                "session_count": len(summaries),
                "character_name": character_name
            }
        
        # Get character context for diary writing
        # Load from core.yaml (behavior system) - provides purpose, drives, constitution
        character_context = ""
        try:
            character_dir = f"characters/{character_name}"
            behavior = load_behavior_profile(character_dir)
            if behavior:
                character_context = behavior.to_prompt_section()
        except Exception:
            pass
        
        if not character_context:
            character_context = f"You are {character_name.title()}."
        
        # Count unique users from summaries (we don't have display names here)
        unique_user_ids = set(s.get("user_id", "unknown") for s in summaries)
        user_count = len(unique_user_ids)
        # Use descriptive text instead of IDs (which are just numbers)
        user_names = [f"{user_count} different {'people' if user_count > 1 else 'person'}"]
        
        # Generate diary entry
        entry, provenance = await diary_manager.generate_diary_entry(
            summaries=summaries,
            character_context=character_context,
            user_names=user_names
        )
        
        if not entry:
            logger.warning(f"Failed to generate diary entry for {character_name}")
            return {
                "success": False,
                "error": "generation_failed",
                "character_name": character_name
            }
        
        # Save to Qdrant
        point_id = await diary_manager.save_diary_entry(entry, provenance=provenance)
        
        # Queue public version for broadcast channel (Phase E8)
        # Worker doesn't have Discord access, so we queue for the bot to post
        broadcast_queued = False
        if settings.ENABLE_BOT_BROADCAST and settings.BOT_BROADCAST_DIARIES:
            try:
                from src_v2.broadcast.manager import broadcast_manager
                
                public_version = await diary_manager.create_public_version(entry)
                if public_version:
                    broadcast_queued = await broadcast_manager.queue_diary(
                        public_version,
                        character_name,
                        provenance
                    )
                    if broadcast_queued:
                        logger.info(f"Diary broadcast queued for {character_name}")
            except Exception as e:
                logger.warning(f"Failed to queue diary broadcast: {e}")
        
        if point_id:
            logger.info(f"Diary entry saved for {character_name}: mood={entry.mood}, themes={entry.themes}")
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


async def run_agentic_diary_generation(
    ctx: Dict[str, Any],
    character_name: str
) -> Dict[str, Any]:
    """
    Generate a diary entry using the DreamWeaver agent (Phase E10).
    
    This uses a multi-step agentic approach:
    1. Plan the narrative arc (story structure, emotional journey)
    2. Use tools to gather data from multiple sources (memories, facts, gossip, etc.)
    3. Weave the final diary entry with proper story arc and emotional depth
    
    Much richer output than the simple diary generator, but uses more tokens.
    
    Args:
        ctx: arq context
        character_name: Bot character name (e.g., "elena")
        
    Returns:
        Dict with success status and diary details
    """
    if not settings.ENABLE_CHARACTER_DIARY:
        return {"success": False, "reason": "disabled"}
    
    if not settings.ENABLE_AGENTIC_NARRATIVES:
        # Fall back to simple generation
        return await run_diary_generation(ctx, character_name)
    
    logger.info(f"Generating AGENTIC diary entry for {character_name}")
    
    try:
        from src_v2.agents.dreamweaver import get_dreamweaver_agent
        from src_v2.memory.diary import get_diary_manager, DiaryEntry
        from src_v2.core.behavior import load_behavior_profile
        from src_v2.core.provenance import ProvenanceCollector, SourceType
        
        diary_manager = get_diary_manager(character_name)
        
        # Check if diary already exists for today
        # FORCE REGENERATION FOR TESTING: Commented out check
        # if await diary_manager.has_diary_for_today():
        #     logger.info(f"Diary already exists for {character_name} today, skipping")
        #     return {
        #         "success": True,
        #         "skipped": True,
        #         "reason": "already_exists",
        #         "character_name": character_name,
        #         "mode": "agentic"
        #     }
        
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
        
        # Run the DreamWeaver agent
        agent = get_dreamweaver_agent()
        success, result = await agent.generate_diary(
            character_name=character_name,
            character_description=character_description
        )
        
        if not success or not result:
            logger.warning(f"Agentic diary generation failed for {character_name}, falling back to simple")
            return await run_diary_generation(ctx, character_name)
        
        # Extract the diary content from the agent's output
        diary_entry_text = result.get("content", "")
        if "---" in diary_entry_text:
            # Extract just the diary entry from the formatted output
            parts = diary_entry_text.split("---")
            if len(parts) >= 2:
                diary_entry_text = parts[1].strip()
        
        # Build provenance
        provenance = ProvenanceCollector(artifact_type="diary", character_name=character_name)
        # Note: material_sources from agent is a list of strings, not structured objects
        # We'll add them as generic conversation/memory items for now
        for source in result.get("material_sources", []):
            # Source string format is usually "Type: Description"
            if ":" in source:
                sType, sDesc = source.split(":", 1)
                sDesc = sDesc.strip()
                if "memory" in sType.lower():
                    provenance.add_memory(who="User", topic=sDesc, when="recently")
                elif "fact" in sType.lower():
                    provenance.add_knowledge(who="User", fact=sDesc)
                else:
                    provenance.add_conversation(who="User", topic=sDesc, where="chat", when="recently")
            else:
                provenance.add_conversation(who="User", topic=source, where="chat", when="recently")
        
        # Create DiaryEntry from agent output
        entry = DiaryEntry(
            entry=diary_entry_text,
            mood=result.get("mood", "reflective"),
            notable_users=result.get("notable_users", []),
            themes=result.get("themes", []),
            emotional_highlights=[]
        )
        
        # Save to Qdrant
        point_id = await diary_manager.save_diary_entry(entry, provenance=provenance.get_provenance_data())
        
        # Queue for broadcast
        broadcast_queued = False
        if settings.ENABLE_BOT_BROADCAST and settings.BOT_BROADCAST_DIARIES:
            try:
                from src_v2.broadcast.manager import broadcast_manager
                
                public_version = await diary_manager.create_public_version(entry)
                if public_version:
                    broadcast_queued = await broadcast_manager.queue_diary(
                        public_version,
                        character_name,
                        provenance.get_provenance_data()
                    )
            except Exception as e:
                logger.warning(f"Failed to queue diary broadcast: {e}")
        
        if point_id:
            logger.info(f"Agentic diary saved for {character_name}: mood={entry.mood}, themes={entry.themes}")
            return {
                "success": True,
                "character_name": character_name,
                "mood": entry.mood,
                "themes": entry.themes,
                "notable_users": entry.notable_users,
                "point_id": point_id,
                "broadcast_queued": broadcast_queued,
                "mode": "agentic",
                "plan": result.get("plan")
            }
        else:
            return {
                "success": False,
                "error": "save_failed",
                "character_name": character_name,
                "mode": "agentic"
            }
        
    except Exception as e:
        logger.error(f"Agentic diary generation failed for {character_name}: {e}")
        # Fall back to simple generation
        logger.info(f"Falling back to simple diary generation for {character_name}")
        return await run_diary_generation(ctx, character_name)
