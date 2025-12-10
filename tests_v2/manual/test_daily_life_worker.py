import asyncio
import os
from dotenv import load_dotenv

# Load worker env first to get real keys
load_dotenv(".env.worker")

from datetime import datetime
from loguru import logger
from src_v2.agents.daily_life.models import SensorySnapshot, ChannelSnapshot, MessageSnapshot
from src_v2.agents.daily_life.graph import DailyLifeGraph
from src_v2.config.settings import settings

# Mock data
def create_mock_snapshot():
    return SensorySnapshot(
        bot_name="elena",
        timestamp=datetime.now(),
        channels=[
            ChannelSnapshot(
                channel_id="123",
                channel_name="general",
                messages=[
                    MessageSnapshot(
                        id="msg1",
                        content="Hey Elena, what do you think about consciousness?",
                        author_id="user1",
                        author_name="Mark",
                        is_bot=False,
                        created_at=datetime.now(),
                        mentions_bot=True
                    ),
                    MessageSnapshot(
                        id="msg2",
                        content="I love coding in Python.",
                        author_id="user2",
                        author_name="Dev",
                        is_bot=False,
                        created_at=datetime.now(),
                        mentions_bot=False
                    )
                ]
            )
        ],
        mentions=[]
    )

async def test_graph():
    logger.info("Testing DailyLifeGraph...")
    
    # Ensure we have a character to load interests for
    # Assuming 'elena' exists
    
    snapshot = create_mock_snapshot()
    graph = DailyLifeGraph()
    
    logger.info("Running graph...")
    commands = await graph.run(snapshot)
    
    logger.info(f"Result commands: {len(commands)}")
    for cmd in commands:
        logger.info(f"Command: {cmd}")

if __name__ == "__main__":
    asyncio.run(test_graph())
