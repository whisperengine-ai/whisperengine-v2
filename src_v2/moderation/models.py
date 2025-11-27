"""Data models for the moderation system."""

from dataclasses import dataclass
from typing import Literal


@dataclass
class UserTimeoutStatus:
    """Status of a user's manipulation timeout."""
    
    status: Literal["active", "timeout"]
    remaining_seconds: int
    violation_count: int
    escalation_level: int = 0
    
    def is_restricted(self) -> bool:
        """Returns True if user is currently in timeout."""
        return self.status == "timeout"
    
    def format_remaining(self) -> str:
        """Format remaining timeout as human-readable string."""
        if self.remaining_seconds <= 0:
            return "none"
        if self.remaining_seconds < 60:
            return f"{self.remaining_seconds}s"
        if self.remaining_seconds < 3600:
            return f"{self.remaining_seconds // 60}m"
        hours = self.remaining_seconds // 3600
        mins = (self.remaining_seconds % 3600) // 60
        return f"{hours}h {mins}m"
