from datetime import datetime
from typing import List, Optional, Literal
from pydantic import BaseModel

class MessageSnapshot(BaseModel):
    id: str
    content: str
    author_id: str
    author_name: str
    is_bot: bool
    created_at: datetime
    mentions_bot: bool
    reference_id: Optional[str] = None
    channel_id: Optional[str] = None

class ChannelSnapshot(BaseModel):
    channel_id: str
    channel_name: str
    messages: List[MessageSnapshot]  # Last 50 messages

class SensorySnapshot(BaseModel):
    """Raw text data from Discord environment."""
    bot_name: str
    timestamp: datetime
    channels: List[ChannelSnapshot]
    mentions: List[MessageSnapshot]

class ActionCommand(BaseModel):
    """Command for the bot to execute."""
    action_type: Literal["reply", "react", "post", "reach_out"]
    channel_id: str
    target_message_id: Optional[str] = None
    content: Optional[str] = None  # The text to send
    emoji: Optional[str] = None
