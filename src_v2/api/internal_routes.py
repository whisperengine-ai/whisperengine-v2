"""
Internal API Routes for Worker → Bot Callbacks

These endpoints are called by the background worker to notify the bot
of completed tasks that require Discord interaction (e.g., sending messages).

These are NOT exposed externally - they're for internal Docker network use only.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field
from loguru import logger
from src_v2.config.settings import settings

router = APIRouter(prefix="/api/internal", tags=["internal"])


# ============================================================================
# Request/Response Models
# ============================================================================

class CallbackType:
    """Types of callbacks the worker can send."""
    BROADCAST = "broadcast"          # Post to broadcast channel
    SEND_MESSAGE = "send_message"    # Send a message to a specific channel
    SEND_DM = "send_dm"              # Send a DM to a specific user


class BroadcastCallbackRequest(BaseModel):
    """Request to post a broadcast (diary, dream, etc.)."""
    content: str = Field(..., description="The content to post")
    post_type: str = Field(..., description="Type: diary, dream, observation, musing")
    character_name: str = Field(..., description="Character posting this")
    provenance: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Source data for the content"
    )


class SendMessageRequest(BaseModel):
    """Request to send a message to a Discord channel."""
    channel_id: str = Field(..., description="Discord channel ID")
    content: str = Field(..., description="Message content")
    reply_to_message_id: Optional[str] = Field(
        default=None, description="Message ID to reply to"
    )
    embed: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional embed data"
    )


class SendDMRequest(BaseModel):
    """Request to send a DM to a user."""
    user_id: str = Field(..., description="Discord user ID")
    content: str = Field(..., description="Message content")


class CallbackResponse(BaseModel):
    """Response from callback endpoints."""
    success: bool
    message: str = ""
    message_id: Optional[str] = None


# Global reference to the Discord bot (set by bot.py on startup)
_discord_bot = None


def set_discord_bot(bot) -> None:
    """Called by bot.py to register the Discord bot instance."""
    global _discord_bot
    _discord_bot = bot
    logger.info("Discord bot registered with internal API")


def get_discord_bot():
    """Get the registered Discord bot instance."""
    return _discord_bot


async def register_bot_endpoint() -> None:
    """
    Register this bot's internal API endpoint in Redis for discovery.
    Called by bot.py on startup and periodically.
    """
    try:
        from src_v2.core.database import db_manager
        
        if not db_manager.redis_client:
            logger.warning("Redis not available for endpoint registration")
            return

        bot_name = settings.DISCORD_BOT_NAME.lower()
        port = settings.API_PORT
        
        # In Docker, the service name is usually the bot name
        # We assume the service name matches the bot name
        # If running locally (not docker), this might be localhost
        import os
        is_docker = os.path.exists('/.dockerenv')
        hostname = bot_name if is_docker else "localhost"
        
        # Construct internal URL
        # Note: We use the service name as hostname for Docker networking
        url = f"http://{hostname}:{port}"
        
        # Store in Redis with TTL
        key = f"{settings.REDIS_KEY_PREFIX}discovery:endpoint:{bot_name}"
        await db_manager.redis_client.set(key, url, ex=3600)  # 1 hour TTL
        
        logger.debug(f"Registered internal endpoint: {url}")
        
    except Exception as e:
        logger.warning(f"Failed to register endpoint: {e}")


# ============================================================================
# Endpoints
# ============================================================================

@router.post(
    "/callback/broadcast",
    response_model=CallbackResponse,
    summary="Post a broadcast to the broadcast channel",
    description="Called by workers to post diaries, dreams, etc. to Discord."
)
async def broadcast_callback(
    request: BroadcastCallbackRequest,
    x_internal_key: Optional[str] = Header(default=None)
) -> CallbackResponse:
    """
    Post content to the broadcast channel.
    
    This is called by the worker when a diary/dream is generated and needs
    to be posted to Discord.
    """
    # Validate this is for our bot
    my_bot_name = settings.DISCORD_BOT_NAME.lower() if settings.DISCORD_BOT_NAME else ""
    if request.character_name.lower() != my_bot_name:
        return CallbackResponse(
            success=False,
            message=f"Wrong bot: expected {my_bot_name}, got {request.character_name}"
        )
    
    bot = get_discord_bot()
    if not bot:
        logger.warning("Broadcast callback received but bot not available")
        return CallbackResponse(success=False, message="Bot not available")
    
    try:
        from src_v2.broadcast.manager import broadcast_manager, PostType
        
        # Post directly using the manager (which has the bot reference)
        results = await broadcast_manager.post_to_channel(
            content=request.content,
            post_type=PostType(request.post_type),
            character_name=request.character_name,
            provenance=request.provenance
        )
        
        if results:
            logger.info(f"Broadcast callback: posted {request.post_type} for {request.character_name} to {len(results)} channels")
            # Return all message IDs as comma-separated string
            all_message_ids = ",".join(str(m.id) for m in results)
            return CallbackResponse(
                success=True,
                message=f"Posted {request.post_type} to {len(results)} channels",
                message_id=all_message_ids
            )
        else:
            return CallbackResponse(success=False, message="Failed to post")
            
    except Exception as e:
        logger.error(f"Broadcast callback failed: {e}")
        return CallbackResponse(success=False, message=str(e))


@router.post(
    "/callback/message",
    response_model=CallbackResponse,
    summary="Send a message to a Discord channel",
    description="Called by workers to send messages (e.g., image generation complete)."
)
async def send_message_callback(
    request: SendMessageRequest,
    x_internal_key: Optional[str] = Header(default=None)
) -> CallbackResponse:
    """
    Send a message to a specific Discord channel.
    """
    bot = get_discord_bot()
    if not bot:
        return CallbackResponse(success=False, message="Bot not available")
    
    try:
        channel = bot.get_channel(int(request.channel_id))
        if not channel:
            # Try fetching if not cached
            channel = await bot.fetch_channel(int(request.channel_id))
        
        if not channel:
            return CallbackResponse(success=False, message="Channel not found")
        
        # Build message kwargs
        kwargs: Dict[str, Any] = {"content": request.content}
        
        # Handle reply
        if request.reply_to_message_id:
            try:
                reply_msg = await channel.fetch_message(int(request.reply_to_message_id))
                kwargs["reference"] = reply_msg
            except Exception:
                pass  # Reply target not found, send without reply
        
        # Handle embed
        if request.embed:
            import discord
            embed = discord.Embed.from_dict(request.embed)
            kwargs["embed"] = embed
        
        sent = await channel.send(**kwargs)
        
        logger.info(f"Message callback: sent to channel {request.channel_id}")
        return CallbackResponse(
            success=True,
            message="Message sent",
            message_id=str(sent.id)
        )
        
    except Exception as e:
        logger.error(f"Send message callback failed: {e}")
        return CallbackResponse(success=False, message=str(e))


@router.post(
    "/callback/dm",
    response_model=CallbackResponse,
    summary="Send a DM to a user",
    description="Called by workers to send direct messages to users."
)
async def send_dm_callback(
    request: SendDMRequest,
    x_internal_key: Optional[str] = Header(default=None)
) -> CallbackResponse:
    """
    Send a direct message to a user.
    """
    bot = get_discord_bot()
    if not bot:
        return CallbackResponse(success=False, message="Bot not available")
    
    try:
        user = bot.get_user(int(request.user_id))
        if not user:
            user = await bot.fetch_user(int(request.user_id))
        
        if not user:
            return CallbackResponse(success=False, message="User not found")
        
        sent = await user.send(request.content)
        
        logger.info(f"DM callback: sent to user {request.user_id}")
        return CallbackResponse(
            success=True,
            message="DM sent",
            message_id=str(sent.id)
        )
        
    except Exception as e:
        logger.error(f"Send DM callback failed: {e}")
        return CallbackResponse(success=False, message=str(e))


@router.get("/health", summary="Internal health check")
async def internal_health():
    """Check if the internal API is ready to receive callbacks."""
    bot = get_discord_bot()
    return {
        "status": "ready" if bot else "waiting",
        "bot_connected": bot is not None and not bot.is_closed() if bot else False,
        "bot_name": settings.DISCORD_BOT_NAME
    }


# ============================================================================
# Graph Pruning Endpoints (Phase E24)
# ============================================================================

class PruneRequest(BaseModel):
    """Request to run graph pruning."""
    dry_run: bool = Field(default=True, description="If True, report what would be pruned without deleting")


class PruneResponse(BaseModel):
    """Response from graph pruning."""
    success: bool
    stats: Dict[str, Any]
    message: str = ""


@router.post("/graph/prune", response_model=PruneResponse, summary="Run knowledge graph pruning")
async def run_graph_prune(request: PruneRequest):
    """
    Manually trigger knowledge graph pruning.
    
    Use dry_run=True (default) to see what would be removed without actually deleting.
    Use dry_run=False to perform the actual cleanup.
    """
    try:
        from src_v2.knowledge.pruning import get_pruner
        
        pruner = get_pruner()
        stats = await pruner.run_full_prune(dry_run=request.dry_run)
        
        action = "Would prune" if request.dry_run else "Pruned"
        total = stats.orphans_removed + stats.stale_facts_removed + stats.duplicates_merged + stats.low_confidence_removed
        
        return PruneResponse(
            success=True,
            stats=stats.to_dict(),
            message=f"{action} {total} items from knowledge graph"
        )
        
    except Exception as e:
        logger.error(f"Graph pruning API failed: {e}")
        return PruneResponse(
            success=False,
            stats={},
            message=str(e)
        )


@router.get("/graph/health", summary="Get knowledge graph health report")
async def get_graph_health():
    """
    Get a health report for the knowledge graph.
    
    Returns counts of nodes, edges, orphans, stale facts, and other metrics.
    """
    try:
        from src_v2.knowledge.pruning import get_pruner
        
        pruner = get_pruner()
        report = await pruner.get_graph_health_report()
        
        return {
            "success": True,
            "report": report
        }
        
    except Exception as e:
        logger.error(f"Graph health API failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }
