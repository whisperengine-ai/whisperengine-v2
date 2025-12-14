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
        
        # --- Locking (Phase E36) ---
        redis = db_manager.redis_client
        if not redis:
            logger.error("Redis client not available")
            return

        lock_key = f"{settings.REDIS_KEY_PREFIX}lock:daily_life:{bot_name}"
        # Try to acquire lock (non-blocking)
        # Set NX=True (Only set if not exists), EX=60 (Expire in 60s)
        is_locked = await redis.set(lock_key, "1", nx=True, ex=60)
        
        if not is_locked:
            logger.info(f"Daily Life for {bot_name} is locked/running. Skipping.")
            return
            
        try:
            logger.info(f"Processing daily life for {bot_name} (Channels: {len(snapshot.channels)})")
            
            # 2. Run Graph
            graph = DailyLifeGraph()
            commands = await graph.run(snapshot)
            
            if not commands:
                logger.info(f"No actions generated for {bot_name}")
                return
                
            # 3. Push to Redis
            # Key: pending_actions:{bot_name}
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
                    continue
                    
                await redis.rpush(key, cmd.model_dump_json())
                logger.info(f"Enqueued action for {bot_name}: {cmd.action_type}")
            
            # Update Last Autonomous Action Timestamp (for Debouncing)
            if commands:
                import time
                last_action_key = f"{settings.REDIS_KEY_PREFIX}bot:{bot_name}:last_autonomous_action"
                await redis.set(last_action_key, str(time.time()))
        
        finally:
            # Release Lock
            await redis.delete(lock_key)
            
    except Exception as e:
        logger.error(f"Error in process_daily_life: {e}")
