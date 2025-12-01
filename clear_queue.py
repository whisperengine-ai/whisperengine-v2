import asyncio
from redis.asyncio import Redis
from src_v2.config.settings import settings

async def clear_queue():
    redis = Redis.from_url(settings.REDIS_URL)
    
    queues = ["arq:cognition", "arq:queue"]
    for q in queues:
        print(f"Deleting key '{q}'...")
        await redis.delete(q)
    print("Deleted.")
    
    await redis.close()

if __name__ == "__main__":
    asyncio.run(clear_queue())
