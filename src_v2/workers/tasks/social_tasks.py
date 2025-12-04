from typing import Dict, Any, Optional, List
from loguru import logger
from src_v2.config.settings import settings


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
