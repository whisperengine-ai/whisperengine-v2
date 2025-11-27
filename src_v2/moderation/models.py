"""Data models for the moderation system."""

from dataclasses import dataclass
from typing import Literal


@dataclass
class UserTimeoutStatus:
    """Status of a user's manipulation timeout."""
    
    status: Literal["active", "warning", "timeout"]
    remaining_seconds: int
    violation_count: int
    escalation_level: int = 0
    warning_score: float = 0.0  # Current decay-weighted score
    
    def is_restricted(self) -> bool:
        """Returns True if user is currently in timeout (not warning)."""
        return self.status == "timeout"
    
    def is_warned(self) -> bool:
        """Returns True if user has violations but not yet timed out."""
        return self.status == "warning"
    
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
    
    def format_score(self) -> str:
        """Format warning score as a simple indicator."""
        if self.warning_score <= 0:
            return "clean"
        if self.warning_score < 1.0:
            return f"low ({self.warning_score:.1f})"
        if self.warning_score < 2.0:
            return f"moderate ({self.warning_score:.1f})"
        if self.warning_score < 3.0:
            return f"high ({self.warning_score:.1f})"
        return f"critical ({self.warning_score:.1f})"
