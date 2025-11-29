#!/usr/bin/env python3
"""
Trigger agentic dream generation for any bot.

Usage:
    python trigger_dream_any.py <bot_name>
    
Examples:
    python trigger_dream_any.py elena
    python trigger_dream_any.py dotty
    python trigger_dream_any.py nottaylor
"""

import asyncio
import sys
import os

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
}

def setup_env(bot_name: str):
    """Set up environment variables for the bot."""
    os.environ["DISCORD_BOT_NAME"] = bot_name
    os.environ["ENABLE_AGENTIC_NARRATIVES"] = "true"
    
    # Override DB URLs for local execution (since .env files use Docker hostnames)
    os.environ["POSTGRES_URL"] = "postgresql://whisper:password@localhost:5432/whisperengine_v2"
    os.environ["QDRANT_URL"] = "http://localhost:6333"
    os.environ["NEO4J_URL"] = "bolt://localhost:7687"
    os.environ["INFLUXDB_URL"] = "http://localhost:8086"
    os.environ["REDIS_URL"] = "redis://localhost:6379/0"

def main():
    if len(sys.argv) < 2:
        print("Usage: python trigger_dream_any.py <bot_name>")
        print(f"Available bots: {', '.join(BOT_PORTS.keys())}")
        sys.exit(1)
    
    bot_name = sys.argv[1].lower()
    
    if bot_name not in BOT_PORTS:
        print(f"Unknown bot: {bot_name}")
        print(f"Available bots: {', '.join(BOT_PORTS.keys())}")
        sys.exit(1)
    
    # Set up environment BEFORE any imports
    setup_env(bot_name)
    
    # Now load the bot's env file for other settings (like API keys)
    from dotenv import load_dotenv
    load_dotenv(f'.env.{bot_name}', override=False)  # Don't override our localhost URLs
    
    asyncio.run(run_dream(bot_name))

async def run_dream(bot_name: str):
    from src_v2.core.database import db_manager
    from src_v2.workers.tasks.dream_tasks import run_agentic_dream_generation
    
    print(f'Initializing database connections for {bot_name}...')
    await db_manager.connect_all()
    
    # Dummy context (worker functions accept dict or WorkerContext)
    ctx = {}
    
    print(f'Triggering agentic dream generation for {bot_name}...')
    
    try:
        result = await run_agentic_dream_generation(ctx, bot_name)
        
        print()
        print('--- Dream Generation Result ---')
        print(f'Success: {result.get("success", False)}')
        print(f'Dream ID: {result.get("dream_id", "N/A")}')
        print(f'Mood: {result.get("mood", "N/A")}')
        print(f'Themes: {result.get("themes", [])}')
        print(f'Broadcast queued: {result.get("broadcast_queued", False)}')
        
        if result.get('success'):
            print(f'\n✅ Dream generated for {bot_name}!')
            print('   The bot will broadcast it to Discord within ~60 seconds (fallback queue)')
            print('   Or immediately if HTTP callback succeeds.')
        else:
            print(f'\n❌ Dream generation failed: {result.get("error", "Unknown error")}')
    finally:
        # Cleanup connections
        if db_manager.postgres_pool:
            await db_manager.postgres_pool.close()
        if db_manager.qdrant_client:
            await db_manager.qdrant_client.close()
        if db_manager.neo4j_driver:
            await db_manager.neo4j_driver.close()

if __name__ == "__main__":
    main()
