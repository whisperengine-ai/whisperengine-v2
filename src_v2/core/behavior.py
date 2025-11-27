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

def load_behavior_profile(character_dir: str) -> Optional[BehaviorProfile]:
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
        logger.error(f"Failed to load behavior profile from {core_path}: {e}")
        return None
