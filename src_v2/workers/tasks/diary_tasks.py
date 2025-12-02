from typing import Dict, Any
from loguru import logger
from src_v2.config.settings import settings
from src_v2.core.database import db_manager


async def run_diary_generation(
    ctx: Dict[str, Any],
    character_name: str,
    override: bool = False
) -> Dict[str, Any]:
    """
    Generate a daily diary entry for a character (Phase E2).
    
    This task synthesizes the day's session summaries into a private diary entry
    that gives the character a sense of inner life and temporal continuity.
    
    Args:
        ctx: arq context
        character_name: Bot character name (e.g., "elena")
        override: If True, ignore "already exists" check
        
    Returns:
        Dict with success status and diary summary
    """
    if not settings.ENABLE_CHARACTER_DIARY:
        return {"success": False, "reason": "disabled"}
    
    logger.info(f"Generating diary entry for {character_name} (override={override})")
    
    try:
        from src_v2.memory.diary import get_diary_manager
        from src_v2.memory.manager import MemoryManager
        from src_v2.core.behavior import load_behavior_profile
        
        diary_manager = get_diary_manager(character_name)
        memory_manager = MemoryManager(bot_name=character_name)
        
        # Check if diary already exists for today
        if not override and await diary_manager.has_diary_for_today():
            logger.info(f"Diary already exists for {character_name} today, skipping")
            return {
                "success": True,
                "skipped": True,
                "reason": "already_exists",
                "character_name": character_name
            }
        
        # Get today's summaries
        summaries = await memory_manager.get_summaries_since(hours=24, limit=30)
        
        # Log narrative source metrics (Phase E16: Feedback Loop Stability)
        # Diary sources are simpler - just session summaries
        try:
            from influxdb_client.client.write.point import Point
            if db_manager.influxdb_write_api:
                point = Point("narrative_sources") \
                    .tag("bot_name", character_name) \
                    .tag("narrative_type", "diary") \
                    .field("from_conversations", len(summaries)) \
                    .field("from_gossip", 0) \
                    .field("from_dreams", 0) \
                    .field("from_past_diaries", 0) \
                    .field("total_sources", len(summaries)) \
                    .field("gossip_ratio", 0.0)
                
                db_manager.influxdb_write_api.write(
                    bucket=settings.INFLUXDB_BUCKET,
                    org=settings.INFLUXDB_ORG,
                    record=point
                )
        except Exception as e:
            logger.debug(f"Failed to log narrative source metrics: {e}")
        
        if len(summaries) < settings.DIARY_MIN_SESSIONS:
            if not settings.DIARY_ALWAYS_GENERATE:
                logger.info(f"Not enough sessions for {character_name} diary (have {len(summaries)}, need {settings.DIARY_MIN_SESSIONS})")
                return {
                    "success": True,
                    "skipped": True,
                    "reason": "insufficient_sessions",
                    "session_count": len(summaries),
                    "character_name": character_name
                }
            else:
                logger.info(f"Generating diary for {character_name} despite low sessions ({len(summaries)}) - DIARY_ALWAYS_GENERATE is enabled")
        
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
            user_names=user_names,
            override=override
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
    character_name: str,
    override: bool = False
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
        override: If True, ignore "already exists" check
        
    Returns:
        Dict with success status and diary details
    """
    if not settings.ENABLE_CHARACTER_DIARY:
        return {"success": False, "reason": "disabled"}
    
    if not settings.ENABLE_AGENTIC_NARRATIVES:
        # Fall back to simple generation
        return await run_diary_generation(ctx, character_name, override=override)
    
    logger.info(f"Generating AGENTIC diary entry for {character_name} (override={override})")
    
    try:
        from src_v2.agents.dreamweaver import get_dreamweaver_agent
        from src_v2.agents.diary_graph import DiaryGraphAgent
        from src_v2.memory.diary import get_diary_manager, DiaryEntry, DiaryMaterial
        from src_v2.core.behavior import load_behavior_profile
        
        diary_manager = get_diary_manager(character_name)
        
        # Check if diary already exists for today
        if not override and await diary_manager.has_diary_for_today():
            logger.info(f"Diary already exists for {character_name} today, skipping")
            return {
                "success": True,
                "skipped": True,
                "reason": "already_exists",
                "character_name": character_name,
                "mode": "agentic"
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
        
        # --- LANGGRAPH PATH ---
        if settings.ENABLE_LANGGRAPH_DIARY_AGENT:
            logger.info(f"Using LangGraph Diary Agent for {character_name}")
            graph_agent = DiaryGraphAgent()
            
            # Gather material first (Graph expects material object)
            # We reuse the logic from DreamWeaver agent which gathers it internally,
            # but here we need to pass it in.
            # For now, let's use the diary manager to get summaries which is the main source
            summaries = await diary_manager.get_summaries_since(hours=24, limit=30)
            
            # Convert summaries to DiaryMaterial
            # Note: DiaryMaterial expects structured data. 
            # We'll create a simple adapter here.
            material = DiaryMaterial(
                summaries=summaries,
                facts=[], # Could fetch from KG
                gossip=[], # Could fetch from shared artifacts
                observations=[]
            )
            
            # Count users
            unique_user_ids = set(s.get("user_id", "unknown") for s in summaries)
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
                return await run_diary_generation(ctx, character_name)
                
            # Save
            # Provenance is simplified for now as Graph doesn't return detailed source map yet
            provenance_data = [{"type": "summary", "count": len(summaries)}]
            point_id = await diary_manager.save_diary_entry(entry, provenance=provenance_data)
            
            # Queue Broadcast (Same as below)
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
                return {
                    "success": True,
                    "character_name": character_name,
                    "mood": entry.mood,
                    "themes": entry.themes,
                    "notable_users": entry.notable_users,
                    "point_id": point_id,
                    "broadcast_queued": broadcast_queued,
                    "mode": "langgraph"
                }
        # ----------------------

        # Run the DreamWeaver agent (Legacy)
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
        
        # Get provenance directly from agent (now returns rich dicts)
        # material_sources is now List[Dict] with type, description, who, when, etc.
        provenance_data = result.get("material_sources", [])
        
        # Create DiaryEntry from agent output
        entry = DiaryEntry(
            entry=diary_entry_text,
            mood=result.get("mood", "reflective"),
            notable_users=result.get("notable_users", []),
            themes=result.get("themes", []),
            emotional_highlights=[]
        )
        
        # Save to Qdrant
        point_id = await diary_manager.save_diary_entry(entry, provenance=provenance_data)
        
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
                        provenance_data
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
