#!/usr/bin/env python3
"""
Trigger autonomous posting for any bot.
Usage: python trigger_posting_any.py <bot_name>
"""
import asyncio
import os
import sys

# Add current directory to path so we can import src_v2
sys.path.append(os.getcwd())

from src_v2.workers.task_queue import TaskQueue

async def main():
    if len(sys.argv) < 2:
        print("Usage: python trigger_posting_any.py <bot_name>")
        return
    
    bot_name = sys.argv[1].lower()
    
    # Setup local Redis
    os.environ["REDIS_URL"] = "redis://localhost:6379/0"
    
    queue = TaskQueue()
    await queue.connect()
    
    print(f"Triggering posting agent for {bot_name}...")
    await queue.enqueue(
        "run_posting_agent",
        bot_name=bot_name,
        _queue_name=TaskQueue.QUEUE_ACTION
    )
    print(f"Done! Task enqueued to {TaskQueue.QUEUE_ACTION}. Check worker logs.")
    await queue.close()

if __name__ == "__main__":
    asyncio.run(main())
