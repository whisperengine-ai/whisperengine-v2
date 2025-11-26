import os
from typing import Optional, Dict
from pydantic import BaseModel
from loguru import logger

class Character(BaseModel):
    name: str
    system_prompt: str
    visual_description: str = "A generic AI assistant."
    # We can add more fields here later if needed, but for now, the prompt is key

class CharacterManager:
    def __init__(self, characters_dir: str = "characters"):
        self.characters_dir = characters_dir
        self.characters: Dict[str, Character] = {}

    def load_character(self, name: str) -> Optional[Character]:
        """
        Loads a character from the characters directory.
        Expected structure: 
        - characters/{name}/character.md (System Prompt)
        - characters/{name}/visual.md (Visual Description - Optional)
        """
        char_dir = os.path.join(self.characters_dir, name)
        char_path = os.path.join(char_dir, "character.md")
        visual_path = os.path.join(char_dir, "visual.md")
        
        if not os.path.exists(char_path):
            logger.warning(f"Character file not found: {char_path}")
            return None

        try:
            with open(char_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            visual_desc = "A generic AI assistant."
            if os.path.exists(visual_path):
                with open(visual_path, "r", encoding="utf-8") as f:
                    visual_desc = f.read().strip()
            
            # Simple parsing: The whole file is the system prompt for now.
            # In the future, we can parse frontmatter (YAML) for metadata.
            character = Character(
                name=name,
                system_prompt=content,
                visual_description=visual_desc
            )
            self.characters[name] = character
            logger.info(f"Loaded character: {name}")
            return character
        except Exception as e:
            logger.error(f"Failed to load character {name}: {e}")
            return None

    def get_character(self, name: str) -> Optional[Character]:
        if name not in self.characters:
            return self.load_character(name)
        return self.characters[name]

# Global character manager
character_manager = CharacterManager()
