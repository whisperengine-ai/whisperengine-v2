"""Utility functions for time and date formatting."""
import datetime
from typing import Union


def get_relative_time(timestamp: Union[str, datetime.datetime]) -> str:
    """
    Converts an absolute timestamp into a human-readable relative time string.
    
    Args:
        timestamp: ISO format string or datetime object
        
    Returns:
        Human-readable relative time (e.g., "2 hours ago", "3 days ago", "2 weeks ago")
    """
    # Parse timestamp if it's a string
    if isinstance(timestamp, str):
        try:
            dt = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return "unknown time"
    else:
        dt = timestamp
    
    # Ensure both datetimes are timezone-aware or both are naive
    now = datetime.datetime.now(datetime.timezone.utc)
    if dt.tzinfo is None:
        # Assume UTC if naive
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    
    # Calculate time difference
    diff = now - dt
    seconds = diff.total_seconds()
    
    if seconds < 0:
        return "just now"
    
    # Calculate various time units
    minutes = seconds / 60
    hours = minutes / 60
    days = hours / 24
    weeks = days / 7
    months = days / 30.44  # Average month length
    years = days / 365.25  # Average year length including leap years
    
    # Return appropriate description
    if seconds < 60:
        return "just now"
    elif minutes < 2:
        return "1 minute ago"
    elif minutes < 60:
        return f"{int(minutes)} minutes ago"
    elif hours < 2:
        return "1 hour ago"
    elif hours < 24:
        return f"{int(hours)} hours ago"
    elif days < 2:
        return "1 day ago"
    elif days < 7:
        return f"{int(days)} days ago"
    elif weeks < 2:
        return "1 week ago"
    elif weeks < 5:  # ~1 month = 4.3 weeks, so use 5 as threshold
        return f"{int(weeks)} weeks ago"
    elif months < 1.5:
        return "1 month ago"
    elif months < 12:
        return f"{int(round(months))} months ago"
    elif years < 2:
        return "1 year ago"
    else:
        return f"{int(years)} years ago"
