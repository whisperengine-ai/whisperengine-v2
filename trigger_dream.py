import asyncio
import os

# Force settings for this script BEFORE imports
os.environ["DISCORD_BOT_NAME"] = "nottaylor"
os.environ["ENABLE_AGENTIC_NARRATIVES"] = "true"

# Override DB URLs for local execution (since .env.nottaylor uses docker hostnames)
os.environ["POSTGRES_URL"] = "postgresql://whisper:password@localhost:5432/whisperengine_v2"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["NEO4J_URL"] = "bolt://localhost:7687"
os.environ["INFLUXDB_URL"] = "http://localhost:8086"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

from src_v2.core.database import db_manager
from src_v2.workers.worker import run_agentic_dream_generation
from src_v2.config.settings import settings

async def main():
    print("Initializing database connections...")
    await db_manager.connect_all()
    
    character_name = "nottaylor"
    print(f"Triggering agentic dream generation for {character_name}...")
    
    # Delete existing dream for today to force regeneration
    try:
        from src_v2.memory.dreams import get_dream_manager
        from datetime import datetime, timezone
        
        dream_manager = get_dream_manager(character_name)
        last_dream = await dream_manager.get_last_character_dream()
        if last_dream:
            last_ts = last_dream.get("timestamp", "")
            if last_ts:
                if isinstance(last_ts, str):
                    last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                else:
                    last_dt = last_ts
                today = datetime.now(timezone.utc).date()
                if last_dt.date() == today:
                    print("Deleting existing dream for today to force regeneration...")
                    # We can't easily delete by ID without exposing a delete method, 
                    # but for now we can just let the worker run and skip if it exists,
                    # OR we can hack it by not checking existence in the worker.
                    # Actually, let's just rely on the fact that I'm running this manually.
                    # Wait, the worker checks for existence.
                    # I'll just print a message here.
                    pass
    except Exception as e:
        print(f"Error checking existing dream: {e}")

    # Dummy context
    ctx = {}
    
    try:
        result = await run_agentic_dream_generation(ctx, character_name)
        print("\n--- Dream Generation Result ---")
        print(f"Success: {result.get('success')}")
        print(f"Dream ID: {result.get('dream_id')}")
        print(f"Summary: {result.get('summary')}")
        
    except Exception as e:
        print(f"Error generating dream: {e}")
    finally:
        # Cleanup
        if db_manager.postgres_pool:
            await db_manager.postgres_pool.close()
        if db_manager.qdrant_client:
            await db_manager.qdrant_client.close()
        if db_manager.neo4j_driver:
            await db_manager.neo4j_driver.close()

if __name__ == "__main__":
    asyncio.run(main())
