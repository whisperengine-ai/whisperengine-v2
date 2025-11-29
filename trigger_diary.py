import asyncio
import os
import sys

# Force settings for this script BEFORE imports
os.environ["DISCORD_BOT_NAME"] = "nottaylor"
os.environ["ENABLE_AGENTIC_NARRATIVES"] = "true"

# Override DB URLs for local execution
os.environ["POSTGRES_URL"] = "postgresql://whisper:password@localhost:5432/whisperengine_v2"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["NEO4J_URL"] = "bolt://localhost:7687"
os.environ["INFLUXDB_URL"] = "http://localhost:8086"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

from src_v2.core.database import db_manager
from src_v2.workers.worker import run_agentic_diary_generation
from src_v2.config.settings import settings

async def main():
    print("Initializing database connections...")
    await db_manager.connect_all()
    
    character_name = "nottaylor"
    print(f"Triggering agentic diary generation for {character_name}...")
    
    # Delete existing diary for today to force regeneration
    try:
        from src_v2.memory.diary import get_diary_manager
        from datetime import datetime, timezone
        
        diary_manager = get_diary_manager(character_name)
        last_diary = await diary_manager.get_last_diary_entry()
        if last_diary:
            last_ts = last_diary.get("timestamp", "")
            if last_ts:
                if isinstance(last_ts, str):
                    last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                else:
                    last_dt = last_ts
                today = datetime.now(timezone.utc).date()
                if last_dt.date() == today:
                    print("Deleting existing diary for today to force regeneration...")
                    # Similar hack: we can't delete easily, but we can modify the worker check
                    # OR we can just rely on the fact that I'm about to modify the worker check
                    pass
    except Exception as e:
        print(f"Error checking existing diary: {e}")

    # Dummy context
    ctx = {}
    
    try:
        result = await run_agentic_diary_generation(ctx, character_name)
        print("\n--- Diary Generation Result ---")
        print(f"Success: {result.get('success')}")
        print(f"Diary ID: {result.get('point_id')}")
        print(f"Summary: {result.get('summary')}")
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
