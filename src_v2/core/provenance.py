"""
Artifact Provenance System (Phase E9)

Tracks the source data (memories, conversations, facts) that contributed to
generated artifacts like dreams and diaries. This allows us to show users
that the bot's "inner life" is grounded in real interactions, not just hallucination.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum

class SourceType(str, Enum):
    CONVERSATION = "conversation"   # Chat with user
    MEMORY = "memory"               # Retrieved memory
    KNOWLEDGE = "knowledge"         # Graph fact
    CHANNEL = "channel"             # Channel context
    OTHER_BOT = "other_bot"         # Another bot's post/knowledge
    COMMUNITY = "community"         # General community observation

@dataclass
class GroundingSource:
    """
    A source that contributed to artifact generation.
    
    Public channel context means we can be specific:
    - User names: "Alex", "Sam" (display names)
    - Topics: "astronomy", "job search stress"
    - Channels: "#general", "#science"
    - Timing: "last Tuesday", "earlier this week"
    """
    source_type: SourceType
    
    # Human-readable description (displayed in artifacts)
    narrative: str  # "Alex's excitement about astronomy in #science"
    
    # Optional specifics (all public channel data)
    who: Optional[str] = None       # "Alex", "Sam" - display names
    topic: Optional[str] = None     # "astronomy", "cooking"
    where: Optional[str] = None     # "#general", "#science"
    when: Optional[str] = None      # "last week", "yesterday"
    
    # Technical details (for dev debugging, not displayed)
    technical: Optional[Dict[str, Any]] = None
    
    def to_narrative(self) -> str:
        """Generate display string for artifact."""
        return self.narrative
    
    def to_dict(self, include_technical: bool = False) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        result = {
            "type": self.source_type.value,
            "description": self.narrative,
            "who": self.who,
            "topic": self.topic,
            "where": self.where,
            "when": self.when
        }
        if include_technical and self.technical:
            result["_debug"] = self.technical
        return {k: v for k, v in result.items() if v is not None}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GroundingSource':
        """Reconstruct from dictionary."""
        return cls(
            source_type=SourceType(data.get("type", "conversation")),
            narrative=data.get("description", ""),
            who=data.get("who"),
            topic=data.get("topic"),
            where=data.get("where"),
            when=data.get("when"),
            technical=data.get("_debug")
        )

class ProvenanceCollector:
    """
    Collects grounding sources for an artifact during generation.
    """
    
    def __init__(self, artifact_type: str, character_name: str):
        self.artifact_type = artifact_type
        self.character_name = character_name
        self.sources: List[GroundingSource] = []
    
    def add_conversation(
        self,
        who: str,           # "Alex" - display name
        topic: str,         # "astronomy"
        where: str,         # "#science"
        when: str,          # "yesterday", "last week"
        technical: Optional[Dict] = None
    ):
        """Add a conversation as grounding source."""
        self.sources.append(GroundingSource(
            source_type=SourceType.CONVERSATION,
            narrative=f"{who}'s thoughts on {topic} in {where}",
            who=who, topic=topic, where=where, when=when,
            technical=technical
        ))
    
    def add_memory(
        self,
        who: str,
        topic: str,
        when: str,
        memory_id: Optional[str] = None,
        score: Optional[float] = None
    ):
        """Add a retrieved memory."""
        self.sources.append(GroundingSource(
            source_type=SourceType.MEMORY,
            narrative=f"Remembering {topic} with {who}",
            who=who, topic=topic, when=when,
            technical={"id": memory_id, "score": score} if memory_id else None
        ))
    
    def add_knowledge(
        self,
        who: str,
        fact: str,  # "loves astronomy", "works in healthcare"
        technical: Optional[Dict] = None
    ):
        """Add a knowledge graph fact."""
        self.sources.append(GroundingSource(
            source_type=SourceType.KNOWLEDGE,
            narrative=f"Knowing {who} {fact}",
            who=who, topic=fact,
            technical=technical
        ))

    def add_source(self, source: GroundingSource):
        """Add a pre-constructed source."""
        self.sources.append(source)

    def get_provenance_data(self) -> List[Dict[str, Any]]:
        """Get list of dicts for storage."""
        return [s.to_dict(include_technical=True) for s in self.sources]
