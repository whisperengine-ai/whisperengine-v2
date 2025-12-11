"""Utility functions for time and date formatting."""
import datetime
from typing import Union
from zoneinfo import ZoneInfo
from loguru import logger
from src_v2.config.settings import settings


def get_configured_timezone() -> ZoneInfo:
    """
    Get the configured timezone object.
    Falls back to UTC if the configured timezone is invalid.
    """
    try:
        return ZoneInfo(settings.TIMEZONE)
    except Exception:
        logger.warning(f"Invalid timezone '{settings.TIMEZONE}', falling back to UTC")
        return ZoneInfo("UTC")


def get_formatted_timestamp(dt: datetime.datetime = None, format_str: str = "%I:%M %p %Z") -> str:
    """
    Get a formatted timestamp string in the configured timezone.
    
    Args:
        dt: Datetime object (defaults to now)
        format_str: Format string (defaults to "HH:MM AM/PM PST")
    """
    if dt is None:
        dt = datetime.datetime.now(datetime.timezone.utc)
    
    # Ensure timezone awareness
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
        
    # Convert to configured timezone
    tz = get_configured_timezone()
    local_dt = dt.astimezone(tz)
    
    return local_dt.strftime(format_str)


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
