"""
Graph Enrichment Tasks (Phase E25)

Background tasks for proactive graph enrichment.
Runs after conversations end or as nightly batch job.

See: docs/spec/SPEC-E25-GRAPH_WALKER_EXTENSIONS.md
"""

from typing import Dict, Any
from datetime import datetime, timezone
from loguru import logger

from src_v2.config.settings import settings


async def run_graph_enrichment(
    _ctx: Dict[str, Any],
    session_id: str,
    user_id: str,
    channel_id: str,
    server_id: str,
    bot_name: str = "unknown"
) -> Dict[str, Any]:
    """
    Enrich the graph from a completed conversation.
    
    Called after conversation ends (5 min inactivity) to discover
    implicit connections between users, topics, and entities.
    
    Args:
        ctx: arq context
        session_id: Session identifier for the conversation
        user_id: User ID who triggered the enrichment
        channel_id: Discord channel ID
        server_id: Discord server ID
        bot_name: Bot that observed the conversation
        
    Returns:
        Dict with success status and edge counts
    """
    if not getattr(settings, 'ENABLE_GRAPH_ENRICHMENT', False):
        return {"success": True, "skipped": True, "reason": "disabled"}
    
    # Fetch messages for the session
    from src_v2.memory.manager import memory_manager
    from src_v2.memory.session import session_manager
    
    try:
        # Get session start time
        start_time = await session_manager.get_session_start_time(session_id)
        if not start_time:
            return {"success": False, "error": "no_session_start_time"}
        
        # Count messages to determine enrichment limit
        message_count = await memory_manager.count_messages_since(user_id, bot_name, start_time)
        if message_count < settings.ENRICHMENT_MIN_MESSAGES:
            return {
                "success": True,
                "skipped": True,
                "reason": "insufficient_messages",
                "message_count": message_count
            }
        
        # Handle DM vs Channel context
        is_dm = channel_id.startswith("dm:") if channel_id else False
        fetch_channel_id = None if is_dm else channel_id
        
        # Calculate enrichment limit (similar to handler logic)
        enrichment_limit = max(message_count, settings.ENRICHMENT_MIN_MESSAGES)
        if fetch_channel_id:  # If in a real channel (not DM), allow more context
            enrichment_limit = min(enrichment_limit * 2, settings.ENRICHMENT_MAX_MESSAGES)
        
        # Fetch messages
        messages = await memory_manager.get_recent_history(
            user_id,
            bot_name,
            limit=enrichment_limit,
            channel_id=fetch_channel_id
        )
        
        # Convert to dict format
        messages_dict = [
            {
                "user_id": getattr(m, 'additional_kwargs', {}).get('user_id', 'unknown'),
                "content": m.content,
                "timestamp": getattr(m, 'additional_kwargs', {}).get('timestamp', datetime.now(timezone.utc).isoformat())
            }
            for m in messages
        ]
        
        if not messages_dict or len(messages_dict) < 3:
            return {
                "success": True,
                "skipped": True,
                "reason": "insufficient_messages_after_fetch",
                "message_count": len(messages_dict) if messages_dict else 0
            }
    
    except Exception as e:
        logger.error(f"Failed to fetch messages for enrichment: {e}")
        return {"success": False, "error": str(e)}
    
    logger.info(f"Running graph enrichment for channel {channel_id} ({len(messages_dict)} messages)")
    
    try:
        from src_v2.knowledge.enrichment import enrichment_agent
        
        result = await enrichment_agent.enrich_from_conversation(
            messages=messages_dict,
            channel_id=channel_id,
            server_id=server_id,
            bot_name=bot_name
        )
        
        return {
            "success": True,
            "channel_id": channel_id,
            "edges_created": result.edges_created,
            "edges_updated": result.edges_updated,
            "user_topic_edges": result.user_topic_edges,
            "user_user_edges": result.user_user_edges,
            "topic_topic_edges": result.topic_topic_edges,
            "entity_entity_edges": result.entity_entity_edges,
            "errors": result.errors if result.errors else None
        }
        
    except Exception as e:
        logger.error(f"Graph enrichment failed for channel {channel_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "channel_id": channel_id
        }


async def run_batch_enrichment(
    ctx: Dict[str, Any],
    hours: int = 24,
    bot_name: str = "unknown"
) -> Dict[str, Any]:
    """
    Batch enrichment from recent messages across all channels.
    
    Called by nightly cron job to catch conversations that weren't
    enriched in real-time.
    
    Args:
        ctx: arq context
        hours: Look back this many hours
        bot_name: Bot running the enrichment
        
    Returns:
        Dict with success status and aggregate edge counts
    """
    if not getattr(settings, 'ENABLE_GRAPH_ENRICHMENT', False):
        return {"success": True, "skipped": True, "reason": "disabled"}
    
    logger.info(f"Running batch graph enrichment for last {hours} hours")
    
    try:
        from src_v2.knowledge.enrichment import enrichment_agent
        
        result = await enrichment_agent.enrich_from_batch(
            hours=hours,
            bot_name=bot_name
        )
        
        # Log to InfluxDB for tracking
        try:
            from src_v2.core.database import db_manager
            from influxdb_client.client.write.point import Point
            
            if db_manager.influxdb_write_api:
                point = (
                    Point("graph_enrichment")
                    .tag("bot_name", bot_name)
                    .tag("type", "batch")
                    .field("edges_created", result.edges_created)
                    .field("user_topic_edges", result.user_topic_edges)
                    .field("user_user_edges", result.user_user_edges)
                    .field("topic_topic_edges", result.topic_topic_edges)
                    .field("entity_entity_edges", result.entity_entity_edges)
                    .field("hours_processed", hours)
                    .time(datetime.now(timezone.utc))
                )
                db_manager.influxdb_write_api.write(
                    bucket=settings.INFLUXDB_BUCKET,
                    record=point
                )
        except Exception as e:
            logger.debug(f"Failed to log enrichment metrics: {e}")
        
        return {
            "success": True,
            "bot_name": bot_name,
            "hours_processed": hours,
            "edges_created": result.edges_created,
            "edges_updated": result.edges_updated,
            "user_topic_edges": result.user_topic_edges,
            "user_user_edges": result.user_user_edges,
            "topic_topic_edges": result.topic_topic_edges,
            "entity_entity_edges": result.entity_entity_edges,
            "errors": result.errors if result.errors else None
        }
        
    except Exception as e:
        logger.error(f"Batch graph enrichment failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "bot_name": bot_name
        }


async def run_nightly_enrichment(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Nightly cron job to run batch enrichment for all bots.
    
    Similar to nightly diary/dream generation, this runs once per day
    to ensure the graph stays enriched even if real-time enrichment
    was missed.
    """
    if not getattr(settings, 'ENABLE_GRAPH_ENRICHMENT', False):
        logger.debug("Graph enrichment disabled, skipping nightly run")
        return {"success": True, "skipped": True, "reason": "disabled"}
    
    bot_name = settings.DISCORD_BOT_NAME or "unknown"
    
    logger.info(f"Running nightly graph enrichment for {bot_name}")
    
    return await run_batch_enrichment(ctx, hours=24, bot_name=bot_name)
