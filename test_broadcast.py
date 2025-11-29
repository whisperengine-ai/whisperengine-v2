#!/usr/bin/env python3
"""
Quick script to test the broadcast channel mechanism for any bot.
Usage: python test_broadcast.py elena "Test diary content here"
"""
import asyncio
import sys
import httpx

# Bot ports
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

async def send_broadcast(bot_name: str, content: str, post_type: str = "diary"):
    """Send a broadcast to the specified bot."""
    port = BOT_PORTS.get(bot_name)
    if not port:
        print(f"Unknown bot: {bot_name}")
        print(f"Available bots: {', '.join(BOT_PORTS.keys())}")
        return False
    
    url = f"http://localhost:{port}/api/internal/callback/broadcast"
    print(f"Sending {post_type} broadcast to {bot_name} at {url}...")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                url,
                json={
                    "content": content,
                    "post_type": post_type,
                    "character_name": bot_name,
                    "provenance": []
                }
            )
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Broadcast sent successfully!")
                print(f"   Message ID: {result.get('message_id')}")
                return True
            else:
                print(f"❌ Broadcast failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
    except httpx.ConnectError:
        print(f"❌ Cannot connect to {bot_name} at port {port}")
        print(f"   Is the bot running? Try: ./bot.sh up {bot_name}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

async def main():
    if len(sys.argv) < 2:
        print("Usage: python test_broadcast.py <bot_name> [content] [post_type]")
        print("  bot_name: elena, nottaylor, dotty, etc.")
        print("  content: The message to broadcast (default: test message)")
        print("  post_type: diary, dream, observation, musing (default: diary)")
        print()
        print("Examples:")
        print("  python test_broadcast.py elena")
        print("  python test_broadcast.py elena 'My test diary entry' diary")
        print("  python test_broadcast.py nottaylor 'A wild dream...' dream")
        return
    
    bot_name = sys.argv[1]
    content = sys.argv[2] if len(sys.argv) > 2 else f"📓 Test broadcast from {bot_name} at {asyncio.get_event_loop().time()}"
    post_type = sys.argv[3] if len(sys.argv) > 3 else "diary"
    
    await send_broadcast(bot_name, content, post_type)

if __name__ == "__main__":
    asyncio.run(main())
