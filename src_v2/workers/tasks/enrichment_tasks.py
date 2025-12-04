"""
Graph Enrichment Tasks (Phase E25)

Background tasks for proactive graph enrichment.
Runs after conversations end or as nightly batch job.

See: docs/spec/SPEC-E25-GRAPH_WALKER_EXTENSIONS.md
"""

from typing import Dict, Any
from datetime import datetime, timezone
from loguru import logger


async def run_graph_enrichment(
    ctx: Dict[str, Any],
    channel_id: str,
    server_id: str,
    messages: list,
    bot_name: str = "unknown"
) -> Dict[str, Any]:
    """
    Enrich the graph from a completed conversation.
    
    Called after conversation ends (5 min inactivity) to discover
    implicit connections between users, topics, and entities.
    
    Args:
        ctx: arq context
        channel_id: Discord channel ID
        server_id: Discord server ID
        messages: List of message dicts with 'user_id', 'content', 'timestamp'
        bot_name: Bot that observed the conversation
        
    Returns:
        Dict with success status and edge counts
    """
    from src_v2.config.settings import settings
    
    if not getattr(settings, 'ENABLE_GRAPH_ENRICHMENT', False):
        return {"success": True, "skipped": True, "reason": "disabled"}
    
    if not messages or len(messages) < 3:
        return {
            "success": True,
            "skipped": True,
            "reason": "insufficient_messages",
            "message_count": len(messages) if messages else 0
        }
    
    logger.info(f"Running graph enrichment for channel {channel_id} ({len(messages)} messages)")
    
    try:
        from src_v2.knowledge.enrichment import enrichment_agent
        
        result = await enrichment_agent.enrich_from_conversation(
            messages=messages,
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
    from src_v2.config.settings import settings
    
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
            from src_v2.config.settings import settings as app_settings
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
                    bucket=app_settings.INFLUXDB_BUCKET,
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
    from src_v2.config.settings import settings
    
    if not getattr(settings, 'ENABLE_GRAPH_ENRICHMENT', False):
        logger.debug("Graph enrichment disabled, skipping nightly run")
        return {"success": True, "skipped": True, "reason": "disabled"}
    
    bot_name = settings.DISCORD_BOT_NAME or "unknown"
    
    logger.info(f"Running nightly graph enrichment for {bot_name}")
    
    return await run_batch_enrichment(ctx, hours=24, bot_name=bot_name)
