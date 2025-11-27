import os
from typing import Optional, Dict, List
from pydantic import BaseModel
from loguru import logger
from src_v2.core.database import db_manager
from src_v2.core.behavior import BehaviorProfile, load_behavior_profile

class ThinkingIndicators(BaseModel):
    """Character-specific thinking status indicators."""
    reflective_mode: Dict[str, str] = {"icon": "🧠", "text": "Reflective Mode Activated"}
    tool_use: Dict[str, str] = {"icon": "✨", "text": "Using my abilities..."}

class Character(BaseModel):
    name: str
    system_prompt: str
    visual_description: str = "A generic AI assistant."
    behavior: Optional[BehaviorProfile] = None
    thinking_indicators: Optional[ThinkingIndicators] = None
    cold_responses: List[str] = ["Noted.", "Okay.", "Got it.", "Sure.", "Alright."]
    error_messages: List[str] = ["I'm having a bit of trouble processing that right now. Please try again later."]
    manipulation_responses: List[str] = ["I appreciate the poetic framing, but I'm just here to chat as myself. What's actually on your mind?"]
    emoji_sets: Dict[str, List[str]] = {}

class CharacterManager:
    def __init__(self, characters_dir: str = "characters"):
        self.characters_dir = characters_dir
        self.characters: Dict[str, Character] = {}

    def load_character(self, name: str, raise_on_error: bool = False) -> Optional[Character]:
        """
        Loads a character from the characters directory.
        Expected structure: 
        - characters/{name}/character.md (System Prompt)
        - characters/{name}/visual.md (Visual Description - Optional)
        - characters/{name}/core.yaml (Behavior Profile - Optional)
        - characters/{name}/ux.yaml (UX/Presentation Config - Optional)
        """
        char_dir = os.path.join(self.characters_dir, name)
        char_path = os.path.join(char_dir, "character.md")
        visual_path = os.path.join(char_dir, "visual.md")
        
        if not os.path.exists(char_path):
            msg = f"Character file not found: {char_path}"
            if raise_on_error:
                raise FileNotFoundError(msg)
            logger.warning(msg)
            return None

        try:
            with open(char_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            visual_desc = "A generic AI assistant."
            if os.path.exists(visual_path):
                with open(visual_path, "r", encoding="utf-8") as f:
                    visual_desc = f.read().strip()
            
            # Load behavior profile (Phase B9)
            behavior = load_behavior_profile(char_dir, raise_on_error=raise_on_error)

            # Load thinking indicators from ux.yaml
            thinking_indicators = None
            cold_responses = ["Noted.", "Okay.", "Got it.", "Sure.", "Alright."]
            error_messages = ["I'm having a bit of trouble processing that right now. Please try again later."]
            manipulation_responses = ["I appreciate the poetic framing, but I'm just here to chat as myself. What's actually on your mind?"]
            emoji_sets = {}
            ux_yaml_path = os.path.join(char_dir, "ux.yaml")
            if os.path.exists(ux_yaml_path):
                try:
                    import yaml
                    with open(ux_yaml_path, "r", encoding="utf-8") as f:
                        ux_config = yaml.safe_load(f)
                        if ux_config:
                            if "thinking_indicators" in ux_config:
                                thinking_indicators = ThinkingIndicators(**ux_config["thinking_indicators"])
                            if "cold_responses" in ux_config:
                                cold_responses = ux_config["cold_responses"]
                            if "error_messages" in ux_config:
                                error_messages = ux_config["error_messages"]
                            if "manipulation_responses" in ux_config:
                                manipulation_responses = ux_config["manipulation_responses"]
                            if "emoji_sets" in ux_config:
                                emoji_sets = ux_config["emoji_sets"]
                except Exception as e:
                    if raise_on_error:
                        raise
                    logger.warning(f"Failed to load ux.yaml from {ux_yaml_path}: {e}")

            # Inject behavior into system prompt if present
            if behavior:
                content += behavior.to_prompt_section()

            # Inject emoji sets into system prompt if present
            if emoji_sets:
                emoji_section = "\n\n## Signature Emojis\n"
                emoji_section += "You have a set of signature emojis that reflect your personality. Use them naturally in your responses to convey emotion, but do not overuse them.\n"
                for category, emojis in emoji_sets.items():
                    emoji_section += f"- **{category.title()}**: {' '.join(emojis)}\n"
                content += emoji_section

            # Simple parsing: The whole file is the system prompt for now.
            # In the future, we can parse frontmatter (YAML) for metadata.
            character = Character(
                name=name,
                system_prompt=content,
                visual_description=visual_desc,
                behavior=behavior,
                thinking_indicators=thinking_indicators,
                cold_responses=cold_responses,
                error_messages=error_messages,
                manipulation_responses=manipulation_responses,
                emoji_sets=emoji_sets
            )
            self.characters[name] = character
            logger.info(f"Loaded character: {name}")
            return character
        except Exception as e:
            if raise_on_error:
                raise
            logger.error(f"Failed to load character {name}: {e}")
            return None

    def get_character(self, name: str) -> Optional[Character]:
        if name not in self.characters:
            return self.load_character(name)
        return self.characters[name]

    async def get_visual_description(self, name: str) -> str:
        """
        Gets visual description from DB, falling back to file/memory.
        """
        # 1. Try DB
        if db_manager.postgres_pool:
            try:
                row = await db_manager.postgres_pool.fetchrow(
                    "SELECT visual_description FROM character_profiles WHERE character_name = $1",
                    name
                )
                if row and row['visual_description']:
                    return row['visual_description']
            except Exception as e:
                logger.error(f"Failed to fetch visual description from DB: {e}")

        # 2. Fallback to loaded character (file-based)
        char = self.get_character(name)
        if char:
            return char.visual_description
        
        return "A generic AI assistant."

    async def update_visual_description(self, name: str, description: str):
        """
        Updates visual description in DB.
        """
        if not db_manager.postgres_pool:
            logger.warning("Postgres not connected, cannot save visual description.")
            return

        try:
            await db_manager.postgres_pool.execute(
                """
                INSERT INTO character_profiles (character_name, visual_description, updated_at)
                VALUES ($1, $2, CURRENT_TIMESTAMP)
                ON CONFLICT (character_name) 
                DO UPDATE SET visual_description = $2, updated_at = CURRENT_TIMESTAMP
                """,
                name, description
            )
            logger.info(f"Updated visual description for {name} in DB.")
            
            # Update in-memory cache if exists
            if name in self.characters:
                self.characters[name].visual_description = description
                
        except Exception as e:
            logger.error(f"Failed to update visual description in DB: {e}")

# Global character manager
character_manager = CharacterManager()
