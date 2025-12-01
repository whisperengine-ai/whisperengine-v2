import asyncio
from redis.asyncio import Redis

async def check_queue():
    redis = Redis()
    queue_name = "arq:cognition"
    
    # Check ZSET size
    count = await redis.zcard(queue_name)
    print(f"Jobs in {queue_name}: {count}")
    
    if count > 0:
        items = await redis.zrange(queue_name, 0, -1, withscores=True)
        print(f"Items: {items}")
        
    await redis.aclose()

if __name__ == "__main__":
    asyncio.run(check_queue())
