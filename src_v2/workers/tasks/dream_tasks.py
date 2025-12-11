from typing import Dict, Any
from loguru import logger
from src_v2.config.settings import settings
from src_v2.memory.manager import memory_manager
from src_v2.memory.models import MemorySourceType
from src_v2.core.database import db_manager
from datetime import datetime, timedelta

# Redis key prefix for dream generation locks
DREAM_LOCK_PREFIX = "dream:generation:lock:"
DREAM_LOCK_TTL = 600  # 10 minutes - enough for dream generation


async def _acquire_dream_lock(character_name: str) -> bool:
    """
    Acquire a distributed lock for dream generation.
    
    Uses Redis SET NX (set if not exists) with TTL to prevent
    multiple dream generations for the same character on the same day.
    
    Returns:
        True if lock acquired, False if another job is already running
    """
    if not db_manager.redis_client:
        logger.warning("Redis not available, skipping lock")
        return True  # Allow to proceed without lock
    
    try:
        # Use today's date (UTC) in the lock key so it resets daily
        today = datetime.utcnow().strftime("%Y-%m-%d")
        lock_key = f"{DREAM_LOCK_PREFIX}{character_name}:{today}"
        
        # SET NX with TTL - atomic operation
        result = await db_manager.redis_client.set(
            lock_key,
            datetime.utcnow().isoformat(),
            nx=True,  # Only set if not exists
            ex=DREAM_LOCK_TTL  # Expire after 10 minutes
        )
        
        if result:
            logger.debug(f"Acquired dream lock for {character_name} on {today}")
            return True
        else:
            logger.info(f"Dream lock already held for {character_name} on {today}, skipping")
            return False
            
    except Exception as e:
        logger.warning(f"Failed to acquire dream lock: {e}")
        return True  # Allow to proceed on error


async def _release_dream_lock(character_name: str) -> None:
    """Release the dream generation lock (optional - TTL handles cleanup)."""
    if not db_manager.redis_client:
        return
    
    try:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        lock_key = f"{DREAM_LOCK_PREFIX}{character_name}:{today}"
        await db_manager.redis_client.delete(lock_key)
        logger.debug(f"Released dream lock for {character_name}")
    except Exception as e:
        logger.debug(f"Failed to release dream lock: {e}")


async def run_dream_generation(
    ctx: Dict[str, Any],
    character_name: str,
    override: bool = False
) -> Dict[str, Any]:
    """
    Generate a dream using the LangGraph Dream Agent.
    
    This uses a multi-step graph approach:
    1. Gather material from memories, facts, gossip, observations
    2. Plan the narrative arc (dream structure, symbolic journey)
    3. Weave the final dream with surreal imagery and emotional resonance
    
    Dreams are synthesized in the character's voice using the model 
    specified in core.yaml.
    
    Args:
        ctx: arq context
        character_name: Bot character name (e.g., "elena")
        override: If True, ignore "already exists" check
        
    Returns:
        Dict with success status and dream details
    """
    if not settings.ENABLE_DREAM_SEQUENCES:
        return {"success": False, "reason": "disabled"}
    
    # Acquire distributed lock to prevent duplicate dreams
    if not override:
        if not await _acquire_dream_lock(character_name):
            return {
                "success": True,
                "skipped": True,
                "reason": "lock_held",
                "character_name": character_name
            }
    
    logger.info(f"Generating dream for {character_name} (override={override})")
    
    try:
        from src_v2.agents.dream_graph import DreamGraphAgent
        from src_v2.memory.dreams import get_dream_manager
        from src_v2.core.behavior import load_behavior_profile
        from src_v2.safety.content_review import content_safety_checker
        from datetime import timezone
        
        dream_manager = get_dream_manager(character_name)
        
        # Check if dream already exists for today
        if not override:
            last_dream = await dream_manager.get_last_character_dream()
            if last_dream:
                last_ts = last_dream.get("timestamp", "")
                if last_ts:
                    try:
                        if isinstance(last_ts, str):
                            last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                        else:
                            last_dt = last_ts
                        today = datetime.now(timezone.utc).date()
                        if last_dt.date() == today:
                            logger.info(f"Dream already exists for {character_name} today, skipping")
                            return {
                                "success": True,
                                "skipped": True,
                                "reason": "already_exists",
                                "character_name": character_name
                            }
                    except Exception:
                        pass
        
        # Get character description for the agent
        character_description = ""
        try:
            from src_v2.core.character import CharacterManager
            from src_v2.core.goals import goal_manager
            
            char_manager = CharacterManager()
            character = char_manager.load_character(character_name)
            if character:
                character_description = character.system_prompt
                
            # Inject goals (Phase E3)
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
        
        # Run LangGraph Dream Agent
        logger.info(f"Using LangGraph Dream Agent for {character_name}")
        graph_agent = DreamGraphAgent()
        
        # Gather material (Graph expects DreamMaterial object)
        material = await dream_manager.gather_dream_material(hours=24)
        
        if not material.is_sufficient():
            logger.info(f"Not enough dream material for {character_name}")
            
            # Phase E22: Absence Tracking
            # Record the failure to dream as a memory
            try:
                target_collection = f"whisperengine_memory_{character_name}"
                
                # 1. Find previous absence to calculate streak
                # We search for recent "absence" type memories
                recent_absences = await memory_manager.search_memories_advanced(
                    query="absence of dream material",
                    metadata_filter={"type": "absence", "what_was_sought": "dream_material"},
                    limit=1,
                    min_timestamp=(datetime.now() - timedelta(days=2)).timestamp(), # Look back 48h
                    collection_name=target_collection
                )
                
                streak = 1
                prior_id = None
                
                if recent_absences:
                    last_absence = recent_absences[0]
                    last_streak = last_absence.get("absence_streak", 1)
                    streak = last_streak + 1
                    prior_id = last_absence.get("id")
                    logger.info(f"Found prior absence (streak: {last_streak} -> {streak})")
                
                # 2. Store new absence memory
                content = f"I tried to dream tonight, but the day felt thin. Not enough to weave. (Streak: {streak})"
                
                await memory_manager.save_typed_memory(
                    user_id=character_name, # Self-memory
                    memory_type="absence",
                    content=content,
                    metadata={
                        "what_was_sought": "dream_material",
                        "material_richness": material.richness_score(),
                        "threshold": settings.DREAM_MIN_RICHNESS,
                        "prior_absence_id": prior_id,
                        "absence_streak": streak
                    },
                    source_type=MemorySourceType.ABSENCE,
                    importance_score=2 # Low importance, but present
                )
                logger.info(f"Recorded absence memory for {character_name} (streak: {streak})")
                
            except Exception as e:
                logger.error(f"Failed to record absence memory: {e}")

            return {
                "success": True,
                "skipped": True,
                "reason": "insufficient_material",
                "character_name": character_name,
                "absence_recorded": True
            }

        # Run Graph
        dream = await graph_agent.run(
            material=material,
            character_context=character_description
        )
        
        if not dream:
            logger.warning("LangGraph Dream Agent returned None")
            return {
                "success": False,
                "error": "graph_returned_none",
                "character_name": character_name
            }
        
        # Build provenance data - vague/poetic for display, content has explicit names for search
        provenance_data = []
        
        # Memories - vague
        if material.memories:
            provenance_data.append({
                "type": "memory",
                "description": "traces of the day"
            })
        
        # Observations - vague
        if material.observations:
            provenance_data.append({
                "type": "observation",
                "description": "things half-noticed"
            })
        
        # Gossip - vague
        if material.gossip:
            provenance_data.append({
                "type": "other_bot",
                "description": "murmurs from elsewhere"
            })
        
        # Facts - vague
        if material.facts:
            provenance_data.append({
                "type": "knowledge",
                "description": "what was known"
            })
            
        # Save
        point_id = await dream_manager.save_dream(user_id="__character__", dream=dream, provenance=provenance_data)
        
        # Phase E22: Check for absence resolution (dream succeeded after previous failures)
        try:
            target_collection = f"whisperengine_memory_{character_name}"
            
            recent_absences = await memory_manager.search_memories_advanced(
                query="absence of dream material",
                metadata_filter={"type": "absence", "what_was_sought": "dream_material"},
                limit=1,
                min_timestamp=(datetime.now() - timedelta(days=7)).timestamp(),
                collection_name=target_collection
            )
            
            if recent_absences:
                last_absence = recent_absences[0]
                absence_streak = last_absence.get("absence_streak", 1)
                absence_id = last_absence.get("id")
                
                # Store resolution memory
                resolution_content = f"Tonight I finally dreamed. After {absence_streak} {'nights' if absence_streak > 1 else 'night'} of reaching for something that wasn't there, the images finally came."
                
                await memory_manager.save_typed_memory(
                    user_id=character_name,
                    memory_type="absence_resolution",
                    content=resolution_content,
                    metadata={
                        "what_was_resolved": "dream_material",
                        "resolved_absence_id": absence_id,
                        "absence_streak_was": absence_streak,
                        "resolution_context": "dream"
                    },
                    source_type=MemorySourceType.INFERENCE,
                    importance_score=3
                )
                logger.info(f"Recorded dream absence resolution for {character_name} (streak was: {absence_streak})")
        except Exception as e:
            logger.debug(f"Failed to check/record absence resolution: {e}")
        
        # Queue Broadcast
        broadcast_queued = False
        if settings.ENABLE_BOT_BROADCAST and settings.BOT_BROADCAST_DREAMS:
            try:
                from src_v2.broadcast.manager import broadcast_manager, PostType
                public_dream = await dream_manager.create_public_dream_version(dream)
                if public_dream:
                    is_safe = await content_safety_checker.is_safe(public_dream, content_type="dream")
                    if is_safe:
                        broadcast_queued = await broadcast_manager.queue_broadcast(
                            content=public_dream,
                            post_type=PostType.DREAM,
                            character_name=character_name,
                            provenance=provenance_data
                        )
            except Exception as e:
                logger.warning(f"Failed to queue dream broadcast: {e}")

        if point_id:
            logger.info(f"Dream saved for {character_name}: mood={dream.mood}, symbols={dream.symbols}")
            return {
                "success": True,
                "character_name": character_name,
                "mood": dream.mood,
                "symbols": dream.symbols,
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
        logger.error(f"Dream generation failed for {character_name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "character_name": character_name
        }


async def run_active_dream_cycle(
    ctx: Dict[str, Any],
    character_name: str
) -> Dict[str, Any]:
    """
    Runs the Active Idle Dream cycle (Phase E34).
    This is a lightweight consolidation process that runs when the bot is idle.
    """
    if not settings.ENABLE_DREAM_SEQUENCES:
        return {"success": False, "reason": "disabled"}

    logger.info(f"Running Active Dream Cycle for {character_name}")
    
    try:
        from src_v2.agents.dream import get_dream_graph
        
        graph = get_dream_graph()
        
        # Initial state
        initial_state = {
            "bot_name": character_name,
            "seeds": [],
            "context": [],
            "dream_result": None,
            "consolidation_status": "pending"
        }
        
        # Run the graph
        final_state = await graph.build_graph().ainvoke(initial_state)
        
        status = final_state.get("consolidation_status")
        logger.info(f"Active Dream Cycle finished for {character_name}: {status}")
        
        return {
            "success": status == "success",
            "status": status,
            "character_name": character_name
        }
        
    except Exception as e:
        logger.error(f"Active Dream Cycle failed for {character_name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "character_name": character_name
        }
