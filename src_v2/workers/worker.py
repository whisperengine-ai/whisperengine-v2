"""
Background Worker - Handles all background processing tasks for WhisperEngine.

This worker runs in a shared container and processes jobs from the Redis queue.
It's designed to be fault-isolated from the main Discord bot and serves ALL bots.
Jobs include bot_name in the payload for character context routing.

Supported tasks:
- Insight Analysis: Pattern detection and epiphany generation
- Summarization: Session summary generation (post-session)
- Reflection: User pattern analysis across sessions
- Knowledge Extraction: Fact extraction to Neo4j (offloaded from response pipeline)
- Diary Generation: Nightly character diary entries (Phase E2)

Usage:
    python -m src_v2.workers.worker
    
Or via arq CLI:
    arq src_v2.workers.worker.WorkerSettings
"""
import asyncio
from typing import Any, Dict, List, Optional
from loguru import logger
from arq import cron
from arq.connections import RedisSettings

from src_v2.workers.task_queue import TaskQueue
from src_v2.agents.insight_agent import insight_agent
from src_v2.core.database import db_manager
from src_v2.config.settings import settings
from src_v2.workers.strategist import run_goal_strategist


async def startup(ctx: Dict[str, Any]) -> None:
    """Called when worker starts up."""
    logger.info("Worker starting up...")
    
    # Initialize database connections
    await db_manager.connect_all()
    
    ctx["db_connected"] = True
    logger.info("Worker ready to process jobs")


async def shutdown(ctx: Dict[str, Any]) -> None:
    """Called when worker shuts down."""
    logger.info("Worker shutting down...")
    
    # Close database connections (use individual close methods)
    if db_manager.postgres_pool:
        await db_manager.postgres_pool.close()
    if db_manager.qdrant_client:
        await db_manager.qdrant_client.close()
    if db_manager.neo4j_driver:
        await db_manager.neo4j_driver.close()
    
    logger.info("Worker shutdown complete")


async def run_insight_analysis(
    ctx: Dict[str, Any],
    user_id: str,
    character_name: str,
    trigger: str = "volume",
    priority: int = 5,
    recent_context: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main task function for running insight analysis.
    
    Args:
        ctx: arq context (contains worker state)
        user_id: Discord user ID to analyze
        character_name: Bot character name
        trigger: What triggered this analysis
        priority: Task priority (unused currently)
        recent_context: Optional recent conversation text
        
    Returns:
        Dict with success status and summary
    """
    logger.info(f"Processing insight analysis for user {user_id} (character: {character_name}, trigger: {trigger})")
    
    try:
        success, summary = await insight_agent.analyze(
            user_id=user_id,
            character_name=character_name,
            trigger=trigger,
            recent_context=recent_context
        )
        
        return {
            "success": success,
            "summary": summary,
            "user_id": user_id,
            "character_name": character_name
        }
        
    except Exception as e:
        logger.error(f"Insight analysis failed for user {user_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "user_id": user_id,
            "character_name": character_name
        }


async def run_summarization(
    ctx: Dict[str, Any],
    user_id: str,
    character_name: str,
    session_id: str,
    messages: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Generate a session summary and save to database.
    
    Args:
        ctx: arq context
        user_id: Discord user ID
        character_name: Bot character name
        session_id: Conversation session ID
        messages: List of message dicts with 'role' and 'content' keys
        
    Returns:
        Dict with success status and summary content
    """
    logger.info(f"Processing summarization for session {session_id} (user: {user_id}, character: {character_name})")
    
    try:
        # Lazy import to avoid circular dependencies
        from src_v2.memory.summarizer import SummaryManager
        
        # Pass character_name to ensure we use the correct memory collection
        summarizer = SummaryManager(bot_name=character_name)
        result = await summarizer.generate_summary(messages)
        
        if result and result.meaningfulness_score >= 3:
            await summarizer.save_summary(session_id, user_id, result)
            logger.info(f"Summary saved for session {session_id} (score: {result.meaningfulness_score})")
            return {
                "success": True,
                "summary": result.summary,
                "meaningfulness_score": result.meaningfulness_score,
                "emotions": result.emotions,
                "session_id": session_id
            }
        else:
            logger.info(f"Session {session_id} not meaningful enough to summarize (score: {result.meaningfulness_score if result else 0})")
            return {
                "success": True,
                "skipped": True,
                "reason": "low_meaningfulness",
                "session_id": session_id
            }
            
    except Exception as e:
        logger.error(f"Summarization failed for session {session_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "session_id": session_id
        }


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
        from src_v2.core.provenance import ProvenanceCollector
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
        
        # Build provenance
        provenance = ProvenanceCollector(artifact_type="dream", character_name=character_name)
        # Note: material_sources from agent is a list of strings
        for source in result.get("material_sources", []):
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
            provenance=provenance.get_provenance_data()
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
                            provenance=provenance.get_provenance_data()
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
        logger.error(f"Dream generation failed for {character_name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "character_name": character_name
        }


async def run_reflection(
    ctx: Dict[str, Any],
    user_id: str,
    character_name: str
) -> Dict[str, Any]:
    """
    Analyze user patterns across recent summaries and update insights.
    Also infers user-specific goals from conversation patterns.
    
    Args:
        ctx: arq context
        user_id: Discord user ID
        character_name: Bot character name
        
    Returns:
        Dict with success status and extracted insights
    """
    logger.info(f"Processing reflection for user {user_id} (character: {character_name})")
    
    try:
        from src_v2.intelligence.reflection import ReflectionEngine
        
        reflection_engine = ReflectionEngine()
        result = await reflection_engine.analyze_user_patterns(user_id, character_name)
        
        if result:
            inferred_goal_slugs = [g.slug for g in result.inferred_goals] if result.inferred_goals else []
            logger.info(f"Reflection complete for user {user_id}: {len(result.insights)} insights, {len(result.updated_traits)} traits, {len(inferred_goal_slugs)} inferred goals")
            return {
                "success": True,
                "insights": result.insights,
                "traits": result.updated_traits,
                "inferred_goals": inferred_goal_slugs,
                "user_id": user_id,
                "character_name": character_name
            }
        else:
            return {
                "success": True,
                "skipped": True,
                "reason": "no_summaries",
                "user_id": user_id
            }
            
    except Exception as e:
        logger.error(f"Reflection failed for user {user_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "user_id": user_id
        }


async def run_knowledge_extraction(
    ctx: Dict[str, Any],
    user_id: str,
    message: str,
    character_name: str = "unknown"
) -> Dict[str, Any]:
    """
    Extract facts from a message and store in Neo4j knowledge graph.
    
    This is the most critical background task - it was previously blocking
    the response pipeline. Now runs asynchronously after response is sent.
    
    Args:
        ctx: arq context
        user_id: Discord user ID
        message: User message text to extract facts from
        character_name: Name of the bot that received the message
        
    Returns:
        Dict with success status and extracted fact count
    """
    logger.info(f"Processing knowledge extraction for user {user_id} (source: {character_name})")
    
    try:
        from src_v2.knowledge.manager import knowledge_manager
        
        # This internally checks ENABLE_RUNTIME_FACT_EXTRACTION
        await knowledge_manager.process_user_message(user_id, message, character_name)
        
        return {
            "success": True,
            "user_id": user_id,
            "message_length": len(message)
        }
        
    except Exception as e:
        logger.error(f"Knowledge extraction failed for user {user_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "user_id": user_id
        }


async def run_store_observation(
    ctx: Dict[str, Any],
    observer_bot: str,
    observation_type: str,
    subject: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Store a stigmergic observation in the knowledge graph.
    
    This is part of Phase B9 (Emergent Behavior Architecture).
    Characters don't communicate directly - they leave traces in the
    environment that other characters can discover.
    
    Args:
        ctx: arq context
        observer_bot: Character making the observation
        observation_type: Category (user_mood, topic_trend, relationship, etc.)
        subject: Who/what the observation is about
        content: The observation content
        metadata: Optional additional data
        
    Returns:
        Dict with success status
    """
    logger.info(f"Storing observation: {observer_bot} observed {observation_type} about {subject}")
    
    try:
        from src_v2.knowledge.manager import knowledge_manager
        
        success = await knowledge_manager.store_observation(
            observer_bot=observer_bot,
            observation_type=observation_type,
            subject=subject,
            content=content,
            metadata=metadata
        )
        
        return {
            "success": success,
            "observer_bot": observer_bot,
            "observation_type": observation_type,
            "subject": subject
        }
        
    except Exception as e:
        logger.error(f"Store observation failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "observer_bot": observer_bot
        }


async def run_universe_observation(
    ctx: Dict[str, Any],
    guild_id: str,
    channel_id: str,
    user_id: str,
    message_content: str,
    mentioned_user_ids: List[str],
    reply_to_user_id: Optional[str] = None,
    user_display_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Observe a message and learn from it for the Emergent Universe.
    
    This is Phase B8 - the universe learning from conversations:
    - Extracts topics from message content
    - Records user-to-user interactions (mentions, replies)
    - Updates user last_seen timestamps
    - Tracks message hour for peak activity learning
    
    Args:
        ctx: arq context
        guild_id: Discord server ID (Planet)
        channel_id: Channel ID where message was sent
        user_id: Author of the message
        message_content: Text content of the message
        mentioned_user_ids: List of user IDs mentioned in the message
        reply_to_user_id: User ID being replied to, if this is a reply
        user_display_name: Display name of the user
        
    Returns:
        Dict with success status and observation summary
    """
    # Skip very short messages
    if len(message_content.strip()) < 10:
        return {"success": True, "skipped": True, "reason": "message_too_short"}
    
    try:
        from src_v2.universe.manager import universe_manager
        
        await universe_manager.observe_message(
            guild_id=guild_id,
            channel_id=channel_id,
            user_id=user_id,
            message_content=message_content,
            mentioned_user_ids=mentioned_user_ids,
            reply_to_user_id=reply_to_user_id,
            user_display_name=user_display_name
        )
        
        return {
            "success": True,
            "guild_id": guild_id,
            "user_id": user_id,
            "message_length": len(message_content)
        }
        
    except Exception as e:
        logger.debug(f"Universe observation failed (non-fatal): {e}")
        return {
            "success": False,
            "error": str(e),
            "guild_id": guild_id,
            "user_id": user_id
        }


async def run_relationship_update(
    ctx: Dict[str, Any],
    character_name: str,
    user_id: str,
    guild_id: Optional[str] = None,
    interaction_quality: int = 1,
    extracted_traits: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Update the relationship between a character and user after a conversation.
    
    This is Phase B8 Phase 3 - Building Relationships:
    - Increments bot-user familiarity based on interaction
    - Adds any extracted traits to the user profile
    - Tracks which planets they've interacted on
    
    Args:
        ctx: arq context
        character_name: Bot character name (e.g., "elena")
        user_id: Discord user ID
        guild_id: Optional guild where interaction happened
        interaction_quality: Quality multiplier (1=normal, 2=high engagement)
        extracted_traits: Optional list of traits extracted from the conversation
        
    Returns:
        Dict with success status
    """
    try:
        from src_v2.universe.manager import universe_manager
        
        # 1. Increment familiarity
        await universe_manager.increment_familiarity(
            character_name=character_name,
            user_id=user_id,
            guild_id=guild_id,
            interaction_quality=interaction_quality
        )
        
        # 2. Add extracted traits
        traits_added = 0
        if extracted_traits:
            for trait in extracted_traits[:5]:  # Limit to 5 traits per call
                await universe_manager.add_user_trait(
                    user_id=user_id,
                    trait=trait,
                    category="interest",
                    learned_by=character_name,
                    confidence=0.7
                )
                traits_added += 1
        
        # 3. Infer timezone from activity patterns (S4: Proactive Timezone Awareness)
        # Only run inference occasionally (when we don't have high confidence)
        from src_v2.intelligence.timezone import timezone_manager
        current_settings = await timezone_manager.get_user_time_settings(user_id, character_name)
        
        if current_settings.timezone_confidence < 0.7:
            inferred_tz, confidence = await timezone_manager.infer_timezone_from_activity(user_id, character_name)
            if inferred_tz and confidence > current_settings.timezone_confidence:
                await timezone_manager.save_inferred_timezone(user_id, character_name, inferred_tz, confidence)
                logger.debug(f"Inferred timezone {inferred_tz} for user {user_id} (confidence: {confidence:.2f})")
        
        logger.debug(f"Updated relationship: {character_name} -> user {user_id} (traits: {traits_added})")
        
        return {
            "success": True,
            "character_name": character_name,
            "user_id": user_id,
            "traits_added": traits_added
        }
        
    except Exception as e:
        logger.error(f"Relationship update failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "character_name": character_name,
            "user_id": user_id
        }


async def run_gossip_dispatch(
    ctx: Dict[str, Any],
    event_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Process a gossip event and inject memories into eligible bots (Phase 3.4).
    
    Args:
        ctx: arq context
        event_data: Serialized UniverseEvent dict
        
    Returns:
        Dict with success status and recipients
    """
    if not settings.ENABLE_UNIVERSE_EVENTS:
        return {"success": False, "reason": "disabled"}
    
    try:
        from src_v2.universe.bus import UniverseEvent, event_bus
        from src_v2.memory.manager import memory_manager
        
        # Deserialize event
        event = UniverseEvent.from_dict(event_data)
        
        logger.info(f"Processing gossip: {event.event_type.value} from {event.source_bot} about user {event.user_id}")
        
        # Get eligible recipients
        recipients = await event_bus.get_eligible_recipients(event)
        
        if not recipients:
            logger.debug(f"No eligible recipients for event from {event.source_bot}")
            return {
                "success": True,
                "recipients": [],
                "reason": "no_eligible_recipients"
            }
        
        # Inject gossip memory into each recipient
        injected = []
        for bot_name in recipients:
            try:
                # Format as a natural "I heard" memory
                gossip_content = (
                    f"[Gossip from {event.source_bot}] "
                    f"I heard that {event.summary}"
                )
                
                # Store as a special "gossip" memory type
                await memory_manager.add_message(
                    user_id=event.user_id,
                    character_name=bot_name,
                    role="system",  # System role for gossip memories
                    content=gossip_content,
                    metadata={
                        "type": "gossip",
                        "source_bot": event.source_bot,
                        "event_type": event.event_type.value,
                        "topic": event.topic,
                        "propagation_depth": event.propagation_depth + 1
                    }
                )
                
                injected.append(bot_name)
                logger.info(f"Injected gossip memory into {bot_name} about user {event.user_id}")
                
            except Exception as e:
                logger.warning(f"Failed to inject gossip into {bot_name}: {e}")
        
        return {
            "success": True,
            "source_bot": event.source_bot,
            "recipients": injected,
            "event_type": event.event_type.value
        }
        
    except Exception as e:
        logger.error(f"Gossip dispatch failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


async def run_nightly_diary_generation(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Cron job that generates diary entries for all active characters.
    
    Runs nightly at the configured hour (default 4 AM UTC).
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
                if not await db_manager.qdrant_client.collection_exists(collection_name):
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
    
    Runs nightly at the configured hour (default 5 AM UTC, 1 hour after diaries).
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


# Worker configuration for arq
class WorkerSettings:
    """arq worker settings."""
    
    # Redis connection
    redis_settings = TaskQueue.get_redis_settings()
    
    # Functions the worker can execute
    functions = [
        run_insight_analysis,
        run_summarization,
        run_reflection,
        run_knowledge_extraction,
        run_store_observation,
        run_universe_observation,
        run_relationship_update,
        run_goal_strategist,
        run_gossip_dispatch,
        run_diary_generation,  # Phase E2: Character Diary
        run_dream_generation,  # Phase E3: Nightly Dreams
    ]
    
    # Cron jobs (scheduled tasks)
    cron_jobs = [
        # Generate diaries for all active characters nightly at 4 AM UTC
        cron(
            run_nightly_diary_generation,
            hour={settings.DIARY_GENERATION_HOUR_UTC},
            minute={0},
            run_at_startup=False  # Don't run immediately on worker start
        ),
        # Generate dreams for all active characters nightly at 5 AM UTC (after diaries)
        cron(
            run_nightly_dream_generation,
            hour={settings.DREAM_GENERATION_HOUR_UTC},
            minute={0},
            run_at_startup=False
        ),
    ]
    
    # Startup/shutdown hooks
    on_startup = startup
    on_shutdown = shutdown
    
    # Worker behavior
    max_jobs = 5  # Max concurrent jobs
    job_timeout = 120  # 2 minutes max per job
    keep_result = 3600  # Keep results for 1 hour
    
    # Health check
    health_check_interval = 30


if __name__ == "__main__":
    # Allow running directly for testing via: python -m src_v2.workers.worker
    # Or use arq CLI: arq src_v2.workers.worker.WorkerSettings
    from arq.worker import run_worker
    
    logger.info("Starting Worker...")
    run_worker(WorkerSettings)  # type: ignore[arg-type]
