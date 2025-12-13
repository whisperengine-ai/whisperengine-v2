from typing import Dict, Any
from datetime import datetime
from loguru import logger
from src_v2.config.settings import settings
from src_v2.memory.manager import memory_manager
from src_v2.memory.models import MemorySourceType
from src_v2.core.cache import CacheManager

# Redis key prefix for dream generation locks
DREAM_LOCK_PREFIX = "dream:generation:lock:"
DREAM_LOCK_TTL = 86400  # 24 hours - prevent multiple dreams per day

cache = CacheManager()


async def _acquire_dream_lock(character_name: str) -> bool:
    """
    Acquire a distributed lock for dream generation.
    
    Uses Redis SET NX (set if not exists) with TTL to prevent
    multiple dream generations for the same character on the same day.
    
    Returns:
        True if lock acquired, False if another job is already running
    """
    try:
        # Use today's date (UTC) in the lock key so it resets daily
        today = datetime.utcnow().strftime("%Y-%m-%d")
        lock_key = f"{DREAM_LOCK_PREFIX}{character_name}:{today}"
        
        # SET NX with TTL - atomic operation
        # CacheManager handles prefixing
        result = await cache.set_nx(
            lock_key,
            datetime.utcnow().isoformat(),
            ttl=DREAM_LOCK_TTL
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
    try:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        lock_key = f"{DREAM_LOCK_PREFIX}{character_name}:{today}"
        await cache.delete(lock_key)
        logger.debug(f"Released dream lock for {character_name}")
    except Exception as e:
        logger.debug(f"Failed to release dream lock: {e}")


async def run_dream_generation(
    ctx: Dict[str, Any],
    character_name: str,
    override: bool = False
) -> Dict[str, Any]:
    """
    DREAM JOURNAL - Generate a first-person dream narrative for broadcast.
    
    Uses DreamJournalAgent (generator-critic loop) to create surreal,
    first-person dream narratives that get broadcast to users.
    
    Key features:
    - First-person perspective enforced ("I am...", "I see...")
    - Critic rejects third-person or literal content
    - Anti-repetition checks against previous dreams
    
    NOT TO BE CONFUSED WITH:
    - Reverie (run_reverie_cycle): Background memory consolidation.
      Reverie is invisible - it just links memories.
      Dream Journal is visible - users see the broadcast.
    
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
        # Dream Journal Agent - generates first-person dream narratives (NOT Reverie)
        from src_v2.agents.dream_journal_graph import dream_journal_agent
        from src_v2.memory.dreams import get_dream_manager, DreamContent
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
        
        # Gather material first
        material = await dream_manager.gather_dream_material(hours=24)
        
        if not material.is_sufficient():
            logger.info(f"Not enough dream material for {character_name}")
            
            # Phase E22: Absence Tracking
            # Record the failure to dream as a memory
            try:
                target_collection = f"whisperengine_memory_{character_name}"
                
                # 1. Find previous absence to calculate streak
                # We search for recent "absence" type memories
                recent_absences = await memory_manager.search_memories(
                    user_id=character_name,
                    query="absence of dream material",
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
                    collection_name=target_collection,
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

        # Get previous dreams to avoid repetition
        previous_dreams = []
        try:
            recent_dreams = await dream_manager.get_recent_dreams(limit=3)
            previous_dreams = [d.get("dream", d.get("content", "")) for d in recent_dreams if d]
        except Exception as e:
            logger.debug(f"Could not fetch previous dreams: {e}")
            
        # Run DreamJournalAgent with generator-critic loop (first-person enforcement)
        logger.info(f"Using DreamJournalAgent for {character_name}")
        dream = await dream_journal_agent.run(
            material=material,
            character_context=character_description,
            previous_dreams=previous_dreams,
            max_steps=3
        )
        
        if not dream:
            logger.warning(f"Dream generation failed: no dream produced")
            return {
                "success": False,
                "error": "no_dream_produced",
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
            
        # Save the dream (DreamJournalAgent only generates, doesn't save)
        point_id = await dream_manager.save_dream(
            user_id=character_name,  # Self-dream
            dream=dream,
            provenance=provenance_data
        )
        
        if not point_id:
            logger.warning(f"Failed to save dream for {character_name}")
            return {
                "success": False,
                "error": "save_failed",
                "character_name": character_name
            }
        
        # Phase E22: Check for absence resolution (dream succeeded after previous failures)
        try:
            target_collection = f"whisperengine_memory_{character_name}"
            
            recent_absences = await memory_manager.search_memories(
                user_id=character_name,
                query="absence of dream material",
                limit=1,
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
                    collection_name=target_collection,
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


async def run_reverie_cycle(
    ctx: Dict[str, Any],
    character_name: str
) -> Dict[str, Any]:
    """
    REVERIE - Active Idle Memory Consolidation (Phase E34).
    
    This is a BACKGROUND process that runs when the bot is idle.
    It links memories together and creates structural connections.
    
    NOT TO BE CONFUSED WITH:
    - Dream Journal (run_dream_generation): Generates first-person narrative
      that gets broadcast to users. Uses DreamJournalAgent.
    
    Reverie is invisible to users - it just improves memory retrieval.
    Dream Journal is visible - users see the dream broadcast.
    """
    if not settings.ENABLE_REVERIE:
        return {"success": False, "reason": "disabled"}

    logger.info(f"Entering Reverie State for {character_name} (memory consolidation, not dream journal)")
    
    try:
        from src_v2.agents.reverie.graph import get_reverie_graph
        
        graph = get_reverie_graph()
        
        # Initial state
        initial_state = {
            "bot_name": character_name,
            "seeds": [],
            "context": [],
            "reverie_result": None,
            "consolidation_status": "pending",
            "process_type": "reverie"
        }
        
        # Run the graph
        final_state = await graph.build_graph().ainvoke(initial_state)
        
        status = final_state.get("consolidation_status")
        logger.info(f"Reverie Cycle finished for {character_name}: {status}")
        
        return {
            "success": status == "success",
            "status": status,
            "character_name": character_name
        }
        
    except Exception as e:
        logger.error(f"Reverie Cycle failed for {character_name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "character_name": character_name
        }
