from typing import Dict, Any
from loguru import logger
from src_v2.config.settings import settings

async def run_dream_generation(
    ctx: Dict[str, Any],
    character_name: str
) -> Dict[str, Any]:
    """
    Generate a nightly dream for a character (Phase E3 - enhanced).
    
    This task synthesizes high-meaningfulness memories from recent interactions
    into a surreal dream that can be broadcast, giving the character a sense
    of continuous inner life.
    
    Args:
        ctx: arq context
        character_name: Bot character name (e.g., "elena")
        
    Returns:
        Dict with success status and dream summary
    """
    if not settings.ENABLE_DREAM_SEQUENCES:
        return {"success": False, "reason": "disabled"}
    
    logger.info(f"Generating nightly dream for {character_name}")
    
    try:
        from src_v2.memory.dreams import get_dream_manager
        from src_v2.core.behavior import load_behavior_profile
        from src_v2.safety.content_review import content_safety_checker
        from datetime import datetime, timezone
        
        dream_manager = get_dream_manager(character_name)
        
        # Check if dream already exists for today (character-level)
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
        
        # Gather dream material from ALL sources (enhanced E3)
        # - Memories from conversations
        # - Facts from knowledge graph
        # - Observations the bot has made
        # - Gossip from other bots
        # - Recent diary themes
        # - Character goals
        material = await dream_manager.gather_dream_material(hours=24)
        
        if not material.is_sufficient():
            logger.info(f"Not enough dream material for {character_name}")
            return {
                "success": True,
                "skipped": True,
                "reason": "insufficient_material",
                "material_count": (
                    len(material.memories) + len(material.facts) + 
                    len(material.observations) + len(material.gossip)
                ),
                "character_name": character_name
            }
        
        # Get character context for dream generation
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
        
        # Generate dream from blended material
        dream, provenance = await dream_manager.generate_dream_from_material(
            material=material,
            character_context=character_context
        )
        
        if not dream:
            logger.warning(f"Failed to generate dream for {character_name}")
            return {
                "success": False,
                "error": "generation_failed",
                "character_name": character_name
            }
        
        # Save to Qdrant as character-level dream
        point_id = await dream_manager.save_dream(
            dream=dream,
            user_id="__character__",
            provenance=provenance
        )
        
        # Create public version and queue for broadcast
        broadcast_queued = False
        if settings.ENABLE_BOT_BROADCAST and settings.BOT_BROADCAST_DREAMS:
            try:
                from src_v2.broadcast.manager import broadcast_manager, PostType
                
                # Create a public-friendly dream message
                public_dream = await dream_manager.create_public_dream_version(dream)
                
                if public_dream:
                    # Content safety check
                    is_safe = await content_safety_checker.is_safe(
                        public_dream,
                        content_type="dream"
                    )
                    
                    if is_safe:
                        broadcast_queued = await broadcast_manager.queue_broadcast(
                            content=public_dream,
                            post_type=PostType.DREAM,
                            character_name=character_name,
                            provenance=provenance
                        )
                        if broadcast_queued:
                            logger.info(f"Dream broadcast queued for {character_name}")
                    else:
                        logger.warning(f"Dream failed content safety check for {character_name}")
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


async def run_agentic_dream_generation(
    ctx: Dict[str, Any],
    character_name: str
) -> Dict[str, Any]:
    """
    Generate a dream using the DreamWeaver agent (Phase E10).
    
    This uses a multi-step agentic approach:
    1. Plan the narrative arc (dream structure, emotional journey)
    2. Use tools to gather data from multiple sources (memories, facts, gossip, etc.)
    3. Weave the final dream with proper story arc and symbolic imagery
    
    Much richer output than the simple dream generator, but uses more tokens.
    
    Args:
        ctx: arq context
        character_name: Bot character name (e.g., "elena")
        
    Returns:
        Dict with success status and dream details
    """
    if not settings.ENABLE_DREAM_SEQUENCES:
        return {"success": False, "reason": "disabled"}
    
    if not settings.ENABLE_AGENTIC_NARRATIVES:
        # Fall back to simple generation
        return await run_dream_generation(ctx, character_name)
    
    logger.info(f"Generating AGENTIC dream for {character_name}")
    
    try:
        from src_v2.agents.dreamweaver import get_dreamweaver_agent
        from src_v2.memory.dreams import get_dream_manager, DreamContent
        from src_v2.core.behavior import load_behavior_profile
        from src_v2.safety.content_review import content_safety_checker
        from datetime import datetime, timezone
        
        dream_manager = get_dream_manager(character_name)
        
        # Check if dream already exists for today
        # FORCE REGENERATION FOR TESTING: Commented out check
        # last_dream = await dream_manager.get_last_character_dream()
        # if last_dream:
        #     last_ts = last_dream.get("timestamp", "")
        #     if last_ts:
        #         try:
        #             if isinstance(last_ts, str):
        #                 last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
        #             else:
        #                 last_dt = last_ts
        #             today = datetime.now(timezone.utc).date()
        #             if last_dt.date() == today:
        #                 logger.info(f"Dream already exists for {character_name} today, skipping")
        #                 return {
        #                     "success": True,
        #                     "skipped": True,
        #                     "reason": "already_exists",
        #                     "character_name": character_name,
        #                     "mode": "agentic"
        #                 }
        #         except Exception:
        #             pass
        
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
        success, result = await agent.generate_dream(
            character_name=character_name,
            character_description=character_description
        )
        
        if not success or not result:
            logger.warning(f"Agentic dream generation failed for {character_name}, falling back to simple")
            return await run_dream_generation(ctx, character_name)
        
        # Extract the dream content from the agent's output
        dream_narrative = result.get("content", "")
        if "---" in dream_narrative:
            # Extract just the dream from the formatted output
            parts = dream_narrative.split("---")
            if len(parts) >= 2:
                dream_narrative = parts[1].strip()
        
        # Get provenance directly from agent (now returns rich dicts)
        # material_sources is now List[Dict] with type, description, who, when, etc.
        provenance_data = result.get("material_sources", [])
        
        # Create DreamContent from agent output
        dream = DreamContent(
            dream=dream_narrative,
            mood=result.get("mood", "dreamlike"),
            symbols=result.get("symbols", []),
            memory_echoes=result.get("memory_echoes", [])
        )
        
        # Save to Qdrant
        point_id = await dream_manager.save_dream(
            dream=dream,
            user_id="__character__",
            provenance=provenance_data
        )
        
        # Queue for broadcast
        broadcast_queued = False
        if settings.ENABLE_BOT_BROADCAST and settings.BOT_BROADCAST_DREAMS:
            try:
                from src_v2.broadcast.manager import broadcast_manager, PostType
                
                public_dream = await dream_manager.create_public_dream_version(dream)
                
                if public_dream:
                    is_safe = await content_safety_checker.is_safe(
                        public_dream,
                        content_type="dream"
                    )
                    
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
            logger.info(f"Agentic dream saved for {character_name}: mood={dream.mood}, symbols={dream.symbols}")
            return {
                "success": True,
                "character_name": character_name,
                "mood": dream.mood,
                "symbols": dream.symbols,
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
        logger.error(f"Agentic dream generation failed for {character_name}: {e}")
        # Fall back to simple generation
        logger.info(f"Falling back to simple dream generation for {character_name}")
        return await run_dream_generation(ctx, character_name)
