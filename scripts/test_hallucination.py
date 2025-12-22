import asyncio
import os

# Force localhost for local debugging
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["NEO4J_URL"] = "bolt://localhost:7687"
os.environ["INFLUXDB_URL"] = "http://localhost:8086"

import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src_v2.core.character import CharacterManager
from src_v2.agents.context_builder import ContextBuilder
from src_v2.core.database import db_manager

async def main():
    # Connect to DBs (needed for context builder)
    await db_manager.connect_all()
    
    # Load character
    char_manager = CharacterManager()
    character = char_manager.load_character("aetheris")
    
    # Initialize ContextBuilder
    builder = ContextBuilder()
    
    # Build context for test user
    user_id = "test_user_api_v2"
    user_message = "Hello"
    context_variables = {
        "user_name": "Traveler",
        "guild_id": "api_guild",
        "channel_name": "api_chat"
    }
    
    print(f"Building context for user: {user_id}")
    
    # Build system prompt
    system_prompt = await builder.build_system_context(
        character=character,
        user_message=user_message,
        user_id=user_id,
        context_variables=context_variables,
        prefetched_context={} # Simulate empty context
    )
    
    print("\n" + "="*50)
    print("SYSTEM PROMPT START")
    print("="*50)
    print(system_prompt)
    print("="*50)
    print("SYSTEM PROMPT END")
    print("="*50)
    
    # Check for "Second Life"
    if "Second Life" in system_prompt:
        print("\n[FOUND] 'Second Life' IS in the system prompt!")
    else:
        print("\n[NOT FOUND] 'Second Life' is NOT in the system prompt.")

    # Check for "RavenOfMercy"
    if "RavenOfMercy" in system_prompt:
        print("[FOUND] 'RavenOfMercy' IS in the system prompt.")

if __name__ == "__main__":
    asyncio.run(main())
