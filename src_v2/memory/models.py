from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class MemorySourceType(str, Enum):
    """
    Origin of a memory, used for trust scoring and feedback loop control.
    """
    HUMAN_DIRECT = "human_direct"       # Direct observation of user input (Highest trust)
    INFERENCE = "inference"             # AI thought/reasoning trace (Medium trust)
    DREAM = "dream"                     # Generated during dream cycle (Lower trust)
    GOSSIP = "gossip"                   # Heard from another bot (Low trust)
    OBSERVATION = "observation"         # Stigmergic observation of environment
    DIARY = "diary"                     # Self-reflection in diary
    SUMMARY = "summary"                 # Compressed history

class Memory(BaseModel):
    """
    Schema for a memory stored in Vector DB.
    
    NOTE: This model is defined for future structured operations but is not
    currently used in the hot path. Qdrant payloads are built as dicts directly
    for performance. This schema serves as documentation and for potential
    future migration to strict validation.
    """
    id: str
    user_id: str
    content: str
    type: str = "conversation"  # conversation, summary, epiphany, etc.
    source_type: MemorySourceType = MemorySourceType.HUMAN_DIRECT
    created_at: datetime = Field(default_factory=datetime.now)
    importance_score: int = 3
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Context
    channel_id: Optional[str] = None
    message_id: Optional[str] = None
    session_id: Optional[str] = None
