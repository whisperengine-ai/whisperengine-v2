import asyncio
import os
import sys
from datetime import datetime, timezone

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src_v2.config.settings import settings
from src_v2.core.database import db_manager
from src_v2.broadcast.cross_bot import cross_bot_manager
from src_v2.intelligence.activity import server_monitor

async def check_status():
    print("🔍 Checking Activity Orchestrator Status...\n")
    
    # 1. Check Settings
    print("1. Configuration:")
    print(f"   - ENABLE_AUTONOMOUS_ACTIVITY: {settings.ENABLE_AUTONOMOUS_ACTIVITY}")
    print(f"   - ENABLE_BOT_CONVERSATIONS: {settings.ENABLE_BOT_CONVERSATIONS}")
    print(f"   - BOT_CONVERSATION_CHANNEL_ID: {settings.BOT_CONVERSATION_CHANNEL_ID}")
    print(f"   - ACTIVITY_CHECK_INTERVAL_MINUTES: {settings.ACTIVITY_CHECK_INTERVAL_MINUTES}")
    
    if not settings.ENABLE_AUTONOMOUS_ACTIVITY:
        print("   ❌ Master switch ENABLE_AUTONOMOUS_ACTIVITY is OFF. No autonomous actions will occur.")
    elif not settings.ENABLE_BOT_CONVERSATIONS:
        print("   ❌ ENABLE_BOT_CONVERSATIONS is OFF. Bot-to-bot chats are disabled.")
    elif not settings.BOT_CONVERSATION_CHANNEL_ID:
        print("   ❌ BOT_CONVERSATION_CHANNEL_ID is not set. Bots don't know where to chat.")
    else:
        print("   ✅ Configuration looks correct for bot conversations.")

    # 2. Connect to DBs
    print("\n2. Connecting to Databases...")
    await db_manager.connect_redis()
    
    if not db_manager.redis_client:
        print("   ❌ Failed to connect to Redis. Cannot check runtime state.")
        return

    # 3. Check Known Bots
    print("\n3. Known Bots (Redis Registry):")
    await cross_bot_manager.load_known_bots()
    bots = cross_bot_manager.known_bots
    if bots:
        for name, bid in bots.items():
            print(f"   - {name}: {bid}")
        if len(bots) < 2:
            print("   ⚠️ Less than 2 bots detected. Conversations require at least 2 bots.")
    else:
        print("   ❌ No bots detected in registry.")

    # 4. Check Activity Levels (if guild ID provided or iterate all keys)
    print("\n4. Activity Levels:")
    # Scan for activity keys: whisper:activity:guild:*:messages
    cursor = 0
    pattern = "whisper:activity:guild:*:messages"
    found_activity = False
    
    while True:
        cursor, keys = await db_manager.redis_client.scan(cursor, match=pattern, count=100)
        for key in keys:
            found_activity = True
            if isinstance(key, bytes):
                key = key.decode()
            # Extract guild ID
            parts = key.split(":")
            guild_id = parts[3]
            
            count = await db_manager.redis_client.zcard(key)
            rate = count / 30.0  # Assuming 30 min window
            
            is_dead_quiet = rate < 0.1
            status = "DEAD QUIET (Ready for chat)" if is_dead_quiet else "ACTIVE (Too busy)"
            
            print(f"   - Guild {guild_id}: {rate:.3f} msgs/min -> {status}")
            
        if cursor == 0:
            break
            
    if not found_activity:
        print("   ℹ️ No activity data found (no messages recently?). Assuming DEAD QUIET.")

    # 5. Check Cooldowns
    print("\n5. Cooldowns & Locks:")
    # Check conversation lock
    # We can't easily list all locks without scanning, but we can check if we knew the guild ID
    # Let's just scan for conversation locks
    cursor = 0
    pattern = "whisper:autonomous:guild:*:conversation_lock"
    while True:
        cursor, keys = await db_manager.redis_client.scan(cursor, match=pattern, count=100)
        for key in keys:
            if isinstance(key, bytes):
                key = key.decode()
            val = await db_manager.redis_client.get(key)
            print(f"   - Conversation Lock Active: {key} -> {val}")
        if cursor == 0:
            break

    print("\nDone.")

if __name__ == "__main__":
    asyncio.run(check_status())
