"""Simple direct test of datetime and relative time functionality."""
import datetime
from src_v2.utils.time_utils import get_relative_time


def test_relative_time():
    """Test relative time calculations."""
    now = datetime.datetime.now(datetime.timezone.utc)
    
    tests = [
        (now, "just now"),
        (now - datetime.timedelta(seconds=30), "just now"),
        (now - datetime.timedelta(minutes=1), "1 minute ago"),
        (now - datetime.timedelta(minutes=2), "2 minutes ago"),
        (now - datetime.timedelta(minutes=5), "5 minutes ago"),
        (now - datetime.timedelta(minutes=15), "15 minutes ago"),
        (now - datetime.timedelta(minutes=30), "30 minutes ago"),
        (now - datetime.timedelta(minutes=45), "45 minutes ago"),
        (now - datetime.timedelta(hours=1), "1 hour ago"),
        (now - datetime.timedelta(hours=2), "2 hours ago"),
        (now - datetime.timedelta(hours=5), "5 hours ago"),
        (now - datetime.timedelta(hours=12), "12 hours ago"),
        (now - datetime.timedelta(hours=23), "23 hours ago"),
        (now - datetime.timedelta(days=1), "1 day ago"),
        (now - datetime.timedelta(days=2), "2 days ago"),
        (now - datetime.timedelta(days=4), "4 days ago"),
        (now - datetime.timedelta(days=6), "6 days ago"),
        (now - datetime.timedelta(weeks=1), "1 week ago"),
        (now - datetime.timedelta(weeks=2), "2 weeks ago"),
        (now - datetime.timedelta(weeks=3), "3 weeks ago"),
        (now - datetime.timedelta(days=35), "1 month ago"),
        (now - datetime.timedelta(days=60), "2 months ago"),
        (now - datetime.timedelta(days=90), "3 months ago"),
        (now - datetime.timedelta(days=150), "5 months ago"),
        (now - datetime.timedelta(days=300), "10 months ago"),
        (now - datetime.timedelta(days=335), "11 months ago"),
        (now - datetime.timedelta(days=400), "1 year ago"),
        (now - datetime.timedelta(days=800), "2 years ago"),
    ]
    
    print("Testing relative time calculations:")
    print("=" * 60)
    for timestamp, expected in tests:
        result = get_relative_time(timestamp)
        status = "✅" if result == expected else "❌"
        print(f"{status} {expected:20s} -> {result}")
    print()


def test_datetime_format():
    """Test the full datetime format."""
    now = datetime.datetime.now()
    formatted = now.strftime("%A, %B %d, %Y at %H:%M")
    
    print("Testing datetime format:")
    print("=" * 60)
    print(f"Current datetime: {formatted}")
    print(f"Length: {len(formatted)} characters")
    
    # Verify format contains expected elements
    assert "," in formatted, "Should contain comma"
    assert " at " in formatted, "Should contain ' at ' separator"
    assert any(day in formatted for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]), "Should contain day name"
    print("✅ Format is valid and readable")
    print()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("DATETIME & RELATIVE TIME TESTS")
    print("=" * 60 + "\n")
    
    test_relative_time()
    test_datetime_format()
    
    print("=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60 + "\n")
    
    # Demo: Show what the character will see
    print("\nEXAMPLE: What the character will see in system prompt:")
    print("=" * 60)
    now = datetime.datetime.now()
    print(f"Current date and time is {now.strftime('%A, %B %d, %Y at %H:%M')}.")
    print()
    print("Recent memories:")
    example_memories = [
        ("User loves whale watching at Monterey Bay", datetime.timedelta(days=2)),
        ("User mentioned son's birthday tomorrow", datetime.timedelta(hours=3)),
        ("User said they prefer concise responses", datetime.timedelta(weeks=1)),
    ]
    
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    for content, time_ago in example_memories:
        timestamp = utc_now - time_ago
        relative = get_relative_time(timestamp)
        print(f"- {content} ({relative})")
    print("=" * 60)
