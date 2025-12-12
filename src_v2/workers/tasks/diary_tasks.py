from typing import Dict, Any
from datetime import datetime, timedelta
from loguru import logger
from src_v2.config.settings import settings
from src_v2.memory.manager import memory_manager
from src_v2.memory.models import MemorySourceType
from src_v2.core.database import db_manager

# Redis key prefix for diary generation locks
DIARY_LOCK_PREFIX = "diary:generation:lock:"
DIARY_LOCK_TTL = 600  # 10 minutes - enough for diary generation


async def _acquire_diary_lock(character_name: str) -> bool:
    """
    Acquire a distributed lock for diary generation.
    
    Uses Redis SET NX (set if not exists) with TTL to prevent
    multiple diary generations for the same character on the same day.
    
    Returns:
        True if lock acquired, False if another job is already running
    """
    if not db_manager.redis_client:
        logger.warning("Redis not available, skipping lock")
        return True  # Allow to proceed without lock
    
    try:
        # Use today's date (UTC) in the lock key so it resets daily
        today = datetime.utcnow().strftime("%Y-%m-%d")
        lock_key = f"{DIARY_LOCK_PREFIX}{character_name}:{today}"
        
        # SET NX with TTL - atomic operation
        result = await db_manager.redis_client.set(
            lock_key,
            datetime.utcnow().isoformat(),
            nx=True,  # Only set if not exists
            ex=DIARY_LOCK_TTL  # Expire after 10 minutes
        )
        
        if result:
            logger.debug(f"Acquired diary lock for {character_name} on {today}")
            return True
        else:
            logger.info(f"Diary lock already held for {character_name} on {today}, skipping")
            return False
            
    except Exception as e:
        logger.warning(f"Failed to acquire diary lock: {e}")
        return True  # Allow to proceed on error


async def _release_diary_lock(character_name: str) -> None:
    """Release the diary generation lock (optional - TTL handles cleanup)."""
    if not db_manager.redis_client:
        return
    
    try:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        lock_key = f"{DIARY_LOCK_PREFIX}{character_name}:{today}"
        await db_manager.redis_client.delete(lock_key)
        logger.debug(f"Released diary lock for {character_name}")
    except Exception as e:
        logger.debug(f"Failed to release diary lock: {e}")


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
    
    # Acquire distributed lock to prevent duplicate diaries
    if not override:
        if not await _acquire_diary_lock(character_name):
            return {
                "success": True,
                "skipped": True,
                "reason": "lock_held",
                "character_name": character_name
            }
    
    logger.info(f"Generating diary entry for {character_name} (override={override})")
    
    try:
        from src_v2.agents.diary_graph import DiaryGraphAgent
        from src_v2.memory.diary import get_diary_manager
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
            from src_v2.core.goals import goal_manager
            
            char_manager = CharacterManager()
            character = char_manager.load_character(character_name)
            if character:
                character_description = character.system_prompt
                
            # Inject goals (Phase E2)
            goals = goal_manager.load_goals(character_name)
            if goals:
                character_description += "\n\n## CURRENT GOALS\n" + "\n".join([f"- {g.description}" for g in goals])
                
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
        
        # Phase E22: Check material sufficiency and track absences
        if not material.is_sufficient() or not material.is_rich_enough():
            reason = "insufficient_material" if not material.is_sufficient() else "low_richness"
            richness = material.richness_score()
            
            logger.info(f"Insufficient diary material for {character_name}: {reason} (richness={richness})")
            
            # Track absence with streak linking
            try:
                target_collection = f"whisperengine_memory_{character_name}"
                
                # Find previous absence to calculate streak
                recent_absences = await memory_manager.search_memories(
                    user_id=character_name,
                    query="absence of diary material",
                    limit=1,
                    collection_name=target_collection
                )
                
                streak = 1
                prior_id = None
                
                if recent_absences:
                    last_absence = recent_absences[0]
                    last_streak = last_absence.get("absence_streak", 1)
                    streak = last_streak + 1
                    prior_id = last_absence.get("id")
                    logger.info(f"Found prior diary absence (streak: {last_streak} -> {streak})")
                
                # Store absence memory
                content = f"I wanted to write in my diary tonight, but the day felt sparse. Not enough to reflect on. (Streak: {streak})"
                
                await memory_manager.save_typed_memory(
                    user_id=character_name,  # Self-memory
                    memory_type="absence",
                    content=content,
                    metadata={
                        "what_was_sought": "diary_material",
                        "reason": reason,
                        "material_richness": richness,
                        "threshold": settings.DIARY_MIN_RICHNESS,
                        "prior_absence_id": prior_id,
                        "absence_streak": streak,
                        "summaries_count": len(material.summaries),
                        "observations_count": len(material.observations)
                    },
                    collection_name=target_collection,
                    source_type=MemorySourceType.ABSENCE,
                    importance_score=2
                )
                logger.info(f"Recorded diary absence for {character_name} (streak: {streak})")
                
            except Exception as e:
                logger.error(f"Failed to record diary absence: {e}")
            
            return {
                "success": True,
                "skipped": True,
                "reason": reason,
                "character_name": character_name,
                "absence_recorded": True
            }
        
        # Extract actual user names from summaries for searchability
        # This allows the diary to mention people by name, making it searchable
        user_names_set = set()
        for s in material.summaries:
            # Prefer display_name > user_name > user_id
            name = s.get("display_name") or s.get("user_name") or s.get("user_id")
            if name and name != "unknown":
                user_names_set.add(name)
        
        # Fall back to count if no names available
        if user_names_set:
            user_names = list(user_names_set)
        else:
            unique_user_ids = set(s.get("user_id", "unknown") for s in material.summaries)
            user_count = len(unique_user_ids)
            user_names = [f"{user_count} different {'people' if user_count > 1 else 'person'}"] if user_count > 0 else []
        
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
            
        # Build provenance data - vague/poetic for display, content has explicit names for search
        provenance_data = []
        
        # Conversations - vague
        if material.summaries:
            provenance_data.append({
                "type": "conversation",
                "description": "echoes of today's conversations"
            })
        
        # Observations - vague
        if material.observations:
            provenance_data.append({
                "type": "observation",
                "description": "fragments overheard"
            })
        
        # Gossip - vague
        if material.gossip:
            provenance_data.append({
                "type": "other_bot",
                "description": "whispers between friends"
            })
        
        # Epiphanies - vague
        if material.epiphanies:
            provenance_data.append({
                "type": "memory",
                "description": "quiet realizations"
            })
        
        # Save
        point_id = await diary_manager.save_diary_entry(entry, provenance=provenance_data)
        
        # Phase E22: Check for absence resolution (diary succeeded after previous failures)
        try:
            target_collection = f"whisperengine_memory_{character_name}"
            
            recent_absences = await memory_manager.search_memories(
                user_id=character_name,
                query="absence of diary material",
                limit=1,
                collection_name=target_collection
            )
            
            if recent_absences:
                last_absence = recent_absences[0]
                absence_streak = last_absence.get("absence_streak", 1)
                absence_id = last_absence.get("id")
                
                # Store resolution memory
                resolution_content = f"Today I finally had enough to write about. After {absence_streak} {'days' if absence_streak > 1 else 'day'} of wanting to reflect but finding nothing, the words finally came."
                
                await memory_manager.save_typed_memory(
                    user_id=character_name,
                    memory_type="absence_resolution",
                    content=resolution_content,
                    metadata={
                        "what_was_resolved": "diary_material",
                        "resolved_absence_id": absence_id,
                        "absence_streak_was": absence_streak,
                        "resolution_context": "diary"
                    },
                    collection_name=target_collection,
                    source_type=MemorySourceType.INFERENCE,
                    importance_score=3
                )
                logger.info(f"Recorded diary absence resolution for {character_name} (streak was: {absence_streak})")
        except Exception as e:
            logger.debug(f"Failed to check/record absence resolution: {e}")
        
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
