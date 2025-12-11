from loguru import logger
from src_v2.agents.daily_life.models import SensorySnapshot
from src_v2.agents.daily_life.graph import DailyLifeGraph
from src_v2.core.database import db_manager
from src_v2.config.settings import settings
import json

async def process_daily_life(ctx, snapshot_data: dict):
    """
    Worker task to process a sensory snapshot and generate actions.
    """
    try:
        # 1. Parse Snapshot
        snapshot = SensorySnapshot(**snapshot_data)
        bot_name = snapshot.bot_name
        logger.info(f"Processing daily life for {bot_name} (Channels: {len(snapshot.channels)})")
        
        # 2. Run Graph
        graph = DailyLifeGraph()
        commands = await graph.run(snapshot)
        
        if not commands:
            logger.info(f"No actions generated for {bot_name}")
            return
            
        # 3. Push to Redis
        # Key: pending_actions:{bot_name}
        # We need to ensure we use the raw redis client
        redis = db_manager.redis_client
        if not redis:
            logger.error("Redis client not available")
            return
            
        key = f"{settings.REDIS_KEY_PREFIX}pending_actions:{bot_name}"
        
        # Fetch existing pending actions to prevent duplicates
        pending_items = await redis.lrange(key, 0, -1)
        pending_target_ids = set()
        for item in pending_items:
            try:
                if isinstance(item, bytes):
                    item = item.decode('utf-8')
                existing_cmd = json.loads(item)
                if "target_message_id" in existing_cmd and existing_cmd["target_message_id"]:
                    pending_target_ids.add(existing_cmd["target_message_id"])
            except Exception:
                pass
        
        for cmd in commands:
            # Skip if we already have a pending action for this message
            if cmd.target_message_id and cmd.target_message_id in pending_target_ids:
                logger.info(f"Skipping duplicate action for message {cmd.target_message_id}")
                continue
                
            # Serialize command
            cmd_json = cmd.model_dump_json()
            await redis.rpush(key, cmd_json)
            
        logger.info(f"Queued {len(commands)} actions for {bot_name}")
        
    except Exception as e:
        logger.error(f"Failed to process daily life: {e}")
        raise
