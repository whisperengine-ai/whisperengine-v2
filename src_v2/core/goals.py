from typing import List, Optional, Dict
import os
import yaml
from pydantic import BaseModel, Field
from loguru import logger

class Goal(BaseModel):
    """
    Represents a character's goal.
    """
    slug: str
    description: str
    success_criteria: str
    priority: int = 5
    category: str = "general"  # expertise, relationship, mission, personal_knowledge, personality

class GoalManager:
    """
    Manages loading and accessing character goals.
    """
    def __init__(self, characters_dir: str = "characters"):
        self.characters_dir = characters_dir
        self._cache: Dict[str, List[Goal]] = {}

    def load_goals(self, character_name: str) -> List[Goal]:
        """
        Load goals for a specific character from goals.yaml.
        """
        if character_name in self._cache:
            return self._cache[character_name]

        goals_path = os.path.join(self.characters_dir, character_name, "goals.yaml")
        
        if not os.path.exists(goals_path):
            logger.warning(f"No goals.yaml found for {character_name}")
            return []

        try:
            with open(goals_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                
            if not data or "goals" not in data:
                return []
                
            goals = [Goal(**g) for g in data["goals"]]
            # Sort by priority (descending)
            goals.sort(key=lambda x: x.priority, reverse=True)
            
            self._cache[character_name] = goals
            return goals
            
        except Exception as e:
            logger.error(f"Failed to load goals for {character_name}: {e}")
            return []

    def get_goals_by_category(self, character_name: str, category: str) -> List[Goal]:
        """
        Get goals filtered by category.
        """
        goals = self.load_goals(character_name)
        return [g for g in goals if g.category == category]

# Global instance
goal_manager = GoalManager()
