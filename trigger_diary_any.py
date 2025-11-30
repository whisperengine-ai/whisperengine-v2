#!/usr/bin/env python3
"""
Trigger diary generation for any bot.
Usage: python trigger_diary_any.py <bot_name>

Examples:
  python trigger_diary_any.py elena
  python trigger_diary_any.py dotty
  python trigger_diary_any.py nottaylor
"""
import asyncio
import os
import sys

# Bot API ports
BOT_PORTS = {
    "elena": 8000,
    "ryan": 8001,
    "dotty": 8002,
    "aria": 8003,
    "dream": 8004,
    "jake": 8005,
    "sophia": 8006,
    "marcus": 8007,
    "nottaylor": 8008,
    "gabriel": 8009,
    "aethys": 8010,
    "aetheris": 8011,
}

def setup_env(bot_name: str):
    """Set up environment variables for the bot."""
    os.environ["DISCORD_BOT_NAME"] = bot_name
    os.environ["ENABLE_AGENTIC_NARRATIVES"] = "true"
    
    # Override DB URLs for local execution
    os.environ["POSTGRES_URL"] = "postgresql://whisper:password@localhost:5432/whisperengine_v2"
    os.environ["QDRANT_URL"] = "http://localhost:6333"
    os.environ["NEO4J_URL"] = "bolt://localhost:7687"
    os.environ["INFLUXDB_URL"] = "http://localhost:8086"
    os.environ["REDIS_URL"] = "redis://localhost:6379/0"

async def main():
    if len(sys.argv) < 2:
        print("Usage: python trigger_diary_any.py <bot_name>")
        print(f"Available bots: {', '.join(BOT_PORTS.keys())}")
        return
    
    bot_name = sys.argv[1].lower()
    
    if bot_name not in BOT_PORTS:
        print(f"Unknown bot: {bot_name}")
        print(f"Available bots: {', '.join(BOT_PORTS.keys())}")
        return
    
    # Set up environment BEFORE importing modules
    setup_env(bot_name)
    
    # Now import after env is set
    from src_v2.core.database import db_manager
    from src_v2.workers.worker import run_agentic_diary_generation
    
    print(f"Initializing database connections for {bot_name}...")
    await db_manager.connect_all()
    
    print(f"Triggering agentic diary generation for {bot_name}...")

    # Dummy context
    ctx = {}
    
    try:
        result = await run_agentic_diary_generation(ctx, bot_name)
        print("\n--- Diary Generation Result ---")
        print(f"Success: {result.get('success')}")
        print(f"Diary ID: {result.get('point_id')}")
        print(f"Mood: {result.get('mood')}")
        print(f"Themes: {result.get('themes')}")
        print(f"Broadcast queued: {result.get('broadcast_queued')}")
        
        if result.get('success'):
            print(f"\n✅ Diary generated for {bot_name}!")
            print(f"   The bot will broadcast it to Discord within ~60 seconds (fallback queue)")
            print(f"   Or immediately if HTTP callback succeeds.")
        else:
            print(f"\n❌ Diary generation failed: {result.get('error')}")
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        if db_manager.postgres_pool:
            await db_manager.postgres_pool.close()
        if db_manager.qdrant_client:
            await db_manager.qdrant_client.close()

if __name__ == "__main__":
    asyncio.run(main())
