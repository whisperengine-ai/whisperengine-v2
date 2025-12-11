from typing import Dict, List, Optional
import os
import yaml
from pydantic import BaseModel, Field
from loguru import logger

class BehaviorProfile(BaseModel):
    """
    Defines the core behavioral seed for a character.
    This replaces rigid scripting with emergent constraints.
    """
    purpose: str = Field(..., description="The character's core reason for existing (1 sentence).")
    drives: Dict[str, float] = Field(default_factory=dict, description="Intrinsic motivations (0.0-1.0).")
    constitution: List[str] = Field(default_factory=list, description="Hard constraints and ethical rules.")
    timezone: str = Field(default="America/Los_Angeles", description="Character's local timezone (IANA format).")
    anchors: List[str] = Field(default_factory=list, description="Thematic anchors for knowledge graph exploration.")
    social_battery_limit: int = Field(default=5, description="Max messages per 15m in a channel before fatigue sets in.")

    def to_prompt_section(self) -> str:
        """
        Converts the behavior profile into a system prompt section.
        """
        drives_str = "\n".join([f"- {k}: {v}" for k, v in self.drives.items()])
        const_str = "\n".join([f"- {c}" for c in self.constitution])
        
        return f"""
## CORE IDENTITY
**Purpose:** {self.purpose}

**Drives:**
{drives_str}

**Constitution (Hard Limits):**
{const_str}
"""

def load_behavior_profile(character_dir: str, raise_on_error: bool = False) -> Optional[BehaviorProfile]:
    """
    Loads core.yaml from the character directory.
    """
    core_path = os.path.join(character_dir, "core.yaml")
    
    if not os.path.exists(core_path):
        return None
        
    try:
        with open(core_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            
        return BehaviorProfile(**data)
    except Exception as e:
        if raise_on_error:
            raise
        logger.error(f"Failed to load behavior profile from {core_path}: {e}")
        return None


def get_character_timezone(character_name: str, characters_dir: str = "characters") -> str:
    """
    Get a character's timezone from their core.yaml.
    Returns 'America/Los_Angeles' (Pacific) as default.
    """
    profile = load_behavior_profile(os.path.join(characters_dir, character_name))
    if profile:
        return profile.timezone
    return "America/Los_Angeles"
