import asyncio
import os
import sys
from loguru import logger

# Add src to path
sys.path.append(os.getcwd())

# Setup environment like run_v2.py
if len(sys.argv) > 1:
    bot_name = sys.argv[1]
    os.environ["DISCORD_BOT_NAME"] = bot_name
    print(f"🤖 Setting DISCORD_BOT_NAME to '{bot_name}'")

from src_v2.config.settings import settings
from src_v2.discord.bot import bot
from src_v2.core.database import db_manager
from src_v2.memory.manager import memory_manager
from src_v2.knowledge.manager import knowledge_manager

async def main():
    # Setup
    logger.info(f"Testing Daily Life Graph for {settings.DISCORD_BOT_NAME}...")
    
    # Connect DBs (needed for gather phase)
    logger.info("Initializing databases...")
    await db_manager.connect_all()
    await memory_manager.initialize()
    await knowledge_manager.initialize()
    
    # Start bot in background to establish Discord connection
    logger.info("Connecting to Discord...")
    
    async def run_check_when_ready():
        logger.info("Waiting for bot to be ready...")
        await bot.wait_until_ready()
        logger.info("Bot is ready! Running manual check...")
        
        # Run the check
        try:
            # We access the scheduler directly
            result = await bot.daily_life_scheduler.trigger_manual_check()
            
            print("\n" + "="*60)
            print(f"DAILY LIFE CHECK RESULT: {settings.DISCORD_BOT_NAME}")
            print("="*60)
            
            if result.get("success"):
                print(f"✅ SUCCESS")
                print(f"Summary: {result.get('summary')}")
                print(f"Actions Taken: {result.get('actions_taken')}")
                print(f"Skipped: {result.get('skipped')}")
            else:
                print(f"❌ FAILED")
                print(f"Error: {result.get('error')}")
                
            print("="*60 + "\n")
            
        except Exception as e:
            logger.error(f"Check failed with exception: {e}")
            import traceback
            traceback.print_exc()
        finally:
            logger.info("Closing bot...")
            await bot.close()

    # Run bot and check concurrently
    try:
        token = settings.DISCORD_TOKEN.get_secret_value() if settings.DISCORD_TOKEN else None
        if not token:
            logger.error("DISCORD_TOKEN not found in settings!")
            return

        await asyncio.gather(
            bot.start(token),
            run_check_when_ready()
        )
    except Exception as e:
        # Ignore the close exception
        pass
    finally:
        # Cleanup
        await db_manager.disconnect_all()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
