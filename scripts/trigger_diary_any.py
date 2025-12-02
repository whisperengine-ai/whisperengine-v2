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
    os.environ["ENABLE_LANGGRAPH_DIARY_AGENT"] = "true"
    
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
    
    # Now load the bot's env file for other settings (like API keys, LangSmith)
    from dotenv import load_dotenv
    load_dotenv(f'.env.{bot_name}', override=False)  # Don't override our localhost URLs
    
    # Now import after env is set
    from src_v2.workers.task_queue import TaskQueue
    
    print(f"Connecting to Task Queue for {bot_name}...")
    tq = TaskQueue()
    await tq.connect()
    
    print(f"Enqueuing agentic diary generation for {bot_name}...")
    
    try:
        job_id = await tq.enqueue("run_agentic_diary_generation", character_name=bot_name, override=True, _queue_name="arq:cognition")
        # Fallback to default queue to test
        # job_id = await tq.enqueue("run_agentic_diary_generation", character_name=bot_name, override=True, _queue_name="arq:queue")
        print(f"\n✅ Job enqueued successfully! Job ID: {job_id}")
        print("   Check the worker logs for progress and results.")
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await tq.close()

if __name__ == "__main__":
    asyncio.run(main())
