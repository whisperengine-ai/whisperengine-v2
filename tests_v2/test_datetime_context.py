"""Test datetime context and relative timestamps."""
import asyncio
import datetime
from src_v2.utils.time_utils import get_relative_time


def test_relative_time_calculations():
    """Test that relative time calculations work correctly."""
    now = datetime.datetime.now(datetime.timezone.utc)
    
    # Test "just now"
    result = get_relative_time(now)
    assert result == "just now"
    
    # Test "2 hours ago"
    two_hours_ago = now - datetime.timedelta(hours=2)
    result = get_relative_time(two_hours_ago)
    assert result == "2 hours ago"
    
    # Test "3 days ago"
    three_days_ago = now - datetime.timedelta(days=3)
    result = get_relative_time(three_days_ago)
    assert result == "3 days ago"
    
    # Test "2 weeks ago"
    two_weeks_ago = now - datetime.timedelta(weeks=2)
    result = get_relative_time(two_weeks_ago)
    assert result == "2 weeks ago"
    
    # Test ISO string parsing
    iso_time = (now - datetime.timedelta(minutes=30)).isoformat()
    result = get_relative_time(iso_time)
    assert result == "30 minutes ago"
    
    print("✅ All relative time tests passed!")


async def test_memory_includes_relative_time():
    """Test that memory search results include relative_time field."""
    from src_v2.memory.manager import memory_manager
    from src_v2.core.database import db_manager
    
    # Initialize connections
    await db_manager.connect_all()
    await memory_manager.initialize()
    
    # Add a test memory
    test_user = "test_user_datetime"
    test_content = "I love whale watching at Monterey Bay"
    
    await memory_manager.add_message(
        user_id=test_user,
        character_name="elena",
        role="human",
        content=test_content
    )
    
    # Wait for indexing
    await asyncio.sleep(2)
    
    # Search for the memory
    results = await memory_manager.search_memories("whale watching", test_user)
    
    assert len(results) > 0, "Should find at least one memory"
    
    # Check that relative_time field is present
    memory = results[0]
    assert "relative_time" in memory, "Memory should include relative_time field"
    assert memory["relative_time"] in ["just now", "1 minute ago"], f"Expected recent time, got: {memory['relative_time']}"
    
    print(f"✅ Memory includes relative_time: {memory['relative_time']}")
    
    # Cleanup
    await memory_manager.clear_memory(test_user, "elena")


def test_datetime_format():
    """Test that datetime format is readable."""
    now = datetime.datetime.now()
    formatted = now.strftime("%A, %B %d, %Y at %H:%M")
    
    # Should include day name, month name, day, year, and time
    assert len(formatted) > 20, "Formatted datetime should be descriptive"
    
    # Should contain "at" separator
    assert " at " in formatted, "Should have 'at' separator between date and time"
    
    print(f"✅ Datetime format example: {formatted}")


if __name__ == "__main__":
    print("Testing datetime and relative time functionality...\n")
    
    # Run synchronous tests
    test_relative_time_calculations()
    test_datetime_format()
    
    # Run async test
    print("\nTesting memory with relative timestamps...")
    asyncio.run(test_memory_includes_relative_time())
    
    print("\n✅ All tests passed!")
