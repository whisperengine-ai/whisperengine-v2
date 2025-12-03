import asyncio
from unittest.mock import AsyncMock
from datetime import datetime, timedelta

async def test_absence_tracking_logic():
    """
    Test the logic for tracking absence streaks.
    This simulates the logic added to dream_tasks.py.
    """
    print("Testing Absence Tracking Logic...")
    
    # Mock memory manager
    mock_memory_manager = AsyncMock()
    
    # Scenario 1: No prior absence (First failure)
    mock_memory_manager.search_memories_advanced.return_value = []
    
    # Logic from dream_tasks.py
    recent_absences = await mock_memory_manager.search_memories_advanced(
        query="absence of dream material",
        metadata_filter={"type": "absence"},
        limit=1
    )
    
    streak = 1
    prior_id = None
    
    if recent_absences:
        last_absence = recent_absences[0]
        last_streak = last_absence.get("absence_streak", 1)
        streak = last_streak + 1
        prior_id = last_absence.get("id")
    
    assert streak == 1
    assert prior_id is None
    print("✅ Scenario 1 (First Absence) Passed")
    
    # Scenario 2: Prior absence exists (Streak continues)
    mock_memory_manager.search_memories_advanced.return_value = [{
        "id": "prev_id",
        "absence_streak": 5,
        "timestamp": (datetime.now() - timedelta(hours=24)).isoformat()
    }]
    
    recent_absences = await mock_memory_manager.search_memories_advanced(
        query="absence of dream material",
        metadata_filter={"type": "absence"},
        limit=1
    )
    
    streak = 1
    prior_id = None
    
    if recent_absences:
        last_absence = recent_absences[0]
        last_streak = last_absence.get("absence_streak", 1)
        streak = last_streak + 1
        prior_id = last_absence.get("id")
        
    assert streak == 6
    assert prior_id == "prev_id"
    print("✅ Scenario 2 (Streak Continuation) Passed")

if __name__ == "__main__":
    asyncio.run(test_absence_tracking_logic())
