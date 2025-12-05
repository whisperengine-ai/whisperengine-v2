import asyncio
import os
import sys
from loguru import logger

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src_v2.core.database import db_manager
from src_v2.memory.manager import memory_manager
from src_v2.tools.memory_tools import SearchEpisodesTool, ReadFullMemoryTool

async def main():
    # Initialize DBs
    await db_manager.connect_all()
    
    user_id = "672814231002939413"
    message_id = "1446594687401197569"
    
    print("\n=== TESTING SEARCH EPISODES TOOL ===")
    search_tool = SearchEpisodesTool(user_id=user_id)
    search_result = await search_tool._arun("high-trust bot pairs")
    print(search_result)
    
    print("\n=== TESTING READ FULL MEMORY TOOL ===")
    read_tool = ReadFullMemoryTool()
    read_result = await read_tool._arun(message_id)
    print(read_result)

if __name__ == "__main__":
    asyncio.run(main())
