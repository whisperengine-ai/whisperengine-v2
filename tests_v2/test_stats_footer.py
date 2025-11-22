#!/usr/bin/env python3
"""
Test script for the stats footer functionality.
Demonstrates how to use the stats footer system.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src_v2.config.settings import settings
from src_v2.core.database import db_manager
from src_v2.utils.stats_footer import stats_footer


async def test_footer():
    """Test the stats footer generation."""
    
    # Initialize database
    await db_manager.connect_all()
    
    # Test user ID (use your own Discord ID for testing)
    test_user_id = "123456789012345678"
    character_name = settings.DISCORD_BOT_NAME or "elena"
    
    print("=" * 60)
    print("Stats Footer Test")
    print("=" * 60)
    
    # 1. Test enabling footer
    print("\n1. Enabling stats footer for test user...")
    await stats_footer.toggle_for_user(test_user_id, character_name, True)
    is_enabled = await stats_footer.is_enabled_for_user(test_user_id, character_name)
    print(f"   Footer enabled: {is_enabled}")
    
    # 2. Generate full footer
    print("\n2. Generating full stats footer...")
    footer = await stats_footer.generate_footer(
        user_id=test_user_id,
        character_name=character_name,
        memory_count=15,
        processing_time_ms=2543,
        llm_time_ms=1284,
        response_length=450
    )
    print("\n" + footer)
    
    # 3. Generate compact footer
    print("\n3. Generating compact footer...")
    compact = await stats_footer.generate_compact_footer(
        user_id=test_user_id,
        character_name=character_name,
        memory_count=15,
        processing_time_ms=2543
    )
    print(f"\n{compact}")
    
    # 4. Test disabling footer
    print("\n4. Disabling stats footer...")
    await stats_footer.toggle_for_user(test_user_id, character_name, False)
    is_enabled = await stats_footer.is_enabled_for_user(test_user_id, character_name)
    print(f"   Footer enabled: {is_enabled}")
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)
    
    # Cleanup
    await db_manager.disconnect_all()


if __name__ == "__main__":
    asyncio.run(test_footer())
