"""
State definitions for the Daily Life Graph.

These dataclasses represent the bot's understanding of its world at check time.
No new database tables - everything is derived from querying existing systems.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import List, Optional, TypedDict, Annotated, Literal
import operator
from langchain_core.messages import BaseMessage

from src_v2.config.settings import settings


# ──────────────────────────────────────────────────────────────────────────────
# CORE GRAPH STATE
# ──────────────────────────────────────────────────────────────────────────────

class DailyLifeState(TypedDict):
    """State for the Daily Life graph - both social and internal."""
    
    # ── Bot & Character Context ──
    bot_name: str
    character_name: str
    character_summary: str  # Brief description for LLM context
    
    # ── Time Context ──
    current_time: datetime
    time_of_day: Literal["morning", "midday", "evening", "night"]
    day_of_week: str
    hours_since_last_check: float
    
    # ── Internal Life State (from querying artifacts) ──
    diary_overdue: bool
    last_diary_date: Optional[str]
    dreams_could_generate: bool  # True if night + hasn't dreamed today
    goals_stale: bool
    last_goal_review: Optional[str]
    
    # ── Relationship State (from Neo4j) ──
    concerning_absences: List["ConcerningAbsence"]
    active_relationship_count: int
    
    # ── Discord State ──
    mentions: List["ScoredMessage"]
    channel_states: List["ChannelState"]
    my_recent_activity: dict  # channel_id -> last_post_time
    
    # ── Derived Flags ──
    has_relevant_content: bool  # Did embedding filter find anything?
    has_pending_internal_tasks: bool  # Any internal life tasks due?
    wants_to_socialize: bool  # Spontaneity trigger
    should_skip: bool  # Skip LLM entirely?
    
    # ── Planning & Execution ──
    messages: Annotated[List[BaseMessage], operator.add]  # LLM conversation
    planned_actions: List["PlannedAction"]
    executed_actions: List["ActionResult"]
    current_action_index: int
    
    # ── Output ──
    summary: str


# ──────────────────────────────────────────────────────────────────────────────
# INTERNAL LIFE STATE (derived from existing artifacts)
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class InternalLifeState:
    """Derived from querying existing artifacts - no new storage."""
    
    # Diary state
    last_diary_date: Optional[datetime] = None
    diary_overdue: bool = False  # last_diary > 24 hours
    
    # Dream state
    last_dream_date: Optional[datetime] = None
    dreams_could_generate: bool = False  # night + no dream today
    
    # Goals state
    last_goal_review: Optional[datetime] = None
    goals_stale: bool = False  # last_goal_review > 7 days


@dataclass
class PendingTasks:
    """Internal life tasks that may need attention."""
    diary_due: bool = False
    dream_due: bool = False
    goal_review_due: bool = False
    drift_check_due: bool = False  # Weekly personality drift analysis


# ──────────────────────────────────────────────────────────────────────────────
# RELATIONSHIP STATE (from Neo4j queries)
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class RelationshipState:
    """Queried from Neo4j - no new storage."""
    
    concerning_absences: List["ConcerningAbsence"] = field(default_factory=list)
    active_relationship_count: int = 0


@dataclass
class ConcerningAbsence:
    """A user the character is concerned about."""
    
    user_id: str
    user_name: str
    days_absent: int
    relationship_strength: float  # 0.0 - 1.0 from trust score
    last_topic: Optional[str] = None  # What were we talking about?


# ──────────────────────────────────────────────────────────────────────────────
# DISCORD STATE (from Discord API queries)
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ChannelState:
    """State of a watched channel."""
    
    channel_id: str
    channel_name: str
    message_count: int  # Messages in fetch window
    last_human_message_age_minutes: float
    consecutive_bot_messages: int  # How many bot messages in a row?
    scored_messages: List["ScoredMessage"] = field(default_factory=list)
    max_relevance_score: float = 0.0  # Highest relevance in this channel


@dataclass
class ScoredMessage:
    """A message with its relevance score."""
    
    message_id: str
    channel_id: str
    channel_name: str
    author_id: str
    author_name: str
    author_is_bot: bool
    content: str
    created_at: datetime
    relevance_score: float  # 0.0 - 1.0, from embedding similarity
    is_mention: bool = False  # Does this mention our bot?
    is_reply_to_me: bool = False  # Is this a reply to our message?
    reference_message_id: Optional[str] = None  # Parent message if reply


# ──────────────────────────────────────────────────────────────────────────────
# ACTIONS
# ──────────────────────────────────────────────────────────────────────────────

ActionType = Literal[
    # Social actions
    "reply",       # Reply to a Discord message
    "react",       # Add emoji reaction to a message
    "post",        # Start a new conversation in a channel
    "reach_out",   # DM a user we're concerned about
    
    # Internal life actions
    "write_diary",     # Generate diary entry
    "generate_dream",  # Process today's experiences as a dream
    "review_goals",    # Review and update goals
    
    # Meta
    "skip",        # Do nothing this check
]


@dataclass
class PlannedAction:
    """An action the graph decided to take.
    
    The Plan node decides WHAT to do, not WHAT TO SAY.
    Content is generated by specialized agents during execution:
    - reply/post → AgentEngine for content
    - write_diary → DiaryGraph
    - generate_dream → DreamGraph
    """
    
    action_type: ActionType
    
    # For Discord actions
    channel_id: Optional[str] = None
    target_message_id: Optional[str] = None  # For reply/react
    target_user_id: Optional[str] = None  # For reach_out
    target_bot_name: Optional[str] = None  # For post (mentioning another bot)
    emoji: Optional[str] = None  # For react
    
    # For internal actions - no extra fields needed, just the type
    
    # Metadata
    reason: str = ""  # Brief explanation for research logging
    priority: int = 10  # Lower = higher priority


@dataclass
class ActionResult:
    """Result of executing an action."""
    
    action: PlannedAction
    success: bool
    error: Optional[str] = None
    
    # For Discord actions
    message_id: Optional[str] = None  # ID of message we created
    
    # For internal actions
    artifact_id: Optional[str] = None  # ID of diary/dream/goal we created


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def get_local_time() -> datetime:
    """Get current time in the bot's configured timezone."""
    try:
        tz = ZoneInfo(settings.TZ)
    except Exception:
        # Fallback to UTC if TZ is invalid
        tz = timezone.utc
        
    return datetime.now(timezone.utc).astimezone(tz)


def get_time_of_day(hour: int) -> Literal["morning", "midday", "evening", "night"]:
    """Classify hour into time-of-day bucket."""
    if 6 <= hour < 12:
        return "morning"
    elif 12 <= hour < 18:
        return "midday"
    elif 18 <= hour < 22:
        return "evening"
    else:
        return "night"


def format_time_ago(minutes: float) -> str:
    """Format minutes as human-readable time ago."""
    if minutes < 1:
        return "just now"
    elif minutes < 60:
        return f"{int(minutes)} min ago"
    elif minutes < 1440:  # 24 hours
        hours = int(minutes / 60)
        return f"{hours}h ago"
    else:
        days = int(minutes / 1440)
        return f"{days}d ago"
