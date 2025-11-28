from typing import Dict, List, Optional, Any
from loguru import logger
import yaml
from pathlib import Path
from src_v2.config.settings import settings

class EvolutionManager:
    """
    Manages character evolution stages, traits, and milestones based on trust levels.
    Loads configuration from characters/{bot_name}/evolution.yaml.
    """
    
    def __init__(self, character_name: str):
        self.character_name = character_name
        self.config = self._load_config()
        self._special_users_cache = self._build_special_users_cache()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load evolution.yaml for character."""
        try:
            config_path = Path(f"characters/{self.character_name}/evolution.yaml")
            if not config_path.exists():
                logger.warning(f"Evolution config not found for {self.character_name}, using defaults.")
                return self._get_default_config()
                
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load evolution config: {e}")
            return self._get_default_config()
    
    def _build_special_users_cache(self) -> Dict[str, Dict[str, Any]]:
        """Build a lookup cache for special users by discord_id."""
        cache = {}
        for user in self.config.get('special_users', []):
            discord_id = user.get('discord_id')
            if discord_id:
                cache[str(discord_id)] = user
        return cache
    
    def get_special_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Check if a user_id is a special user for this character.
        Returns the special user config if found, None otherwise.
        """
        return self._special_users_cache.get(str(user_id))
    
    def get_trust_override(self, user_id: str) -> Optional[int]:
        """
        Get trust override for a special user.
        Returns the override trust score, or None if not a special user.
        """
        special = self.get_special_user(user_id)
        if special:
            return special.get('trust_override')
        return None
            
    def _get_default_config(self) -> Dict[str, Any]:
        """Fallback configuration if file is missing."""
        return {
            "evolution_stages": [
                {"name": "Stranger", "trust_range": [-100, 100], "behavior": "Default behavior."}
            ],
            "traits": [],
            "milestones": []
        }
    
    def get_current_stage(self, trust_level: int) -> Dict[str, Any]:
        """Returns current evolution stage based on trust."""
        for stage in self.config.get('evolution_stages', []):
            min_trust, max_trust = stage['trust_range']
            if min_trust <= trust_level <= max_trust:
                return stage
        
        # Fallback: find closest stage
        # If trust is lower than lowest, return lowest. If higher than highest, return highest.
        stages = self.config.get('evolution_stages', [])
        if not stages:
            return {"name": "Unknown", "behavior": ""}
            
        if trust_level < stages[0]['trust_range'][0]:
            return stages[0]
        return stages[-1]
    
    def get_unlocked_traits(self, trust_level: int) -> List[Dict[str, Any]]:
        """Returns all traits unlocked at current trust level."""
        return [
            trait for trait in self.config.get('traits', [])
            if trust_level >= trait['unlock_at']
        ]
        
    def get_active_traits(self, trust_level: int, user_sentiment: str = "neutral") -> List[Dict[str, Any]]:
        """
        Returns traits that are unlocked AND appropriate for the current context.
        Filters out traits that are suppressed by the user's mood/sentiment.
        """
        unlocked = self.get_unlocked_traits(trust_level)
        active = []
        
        for trait in unlocked:
            suppressed_moods = trait.get('suppress_on_mood', [])
            if user_sentiment in suppressed_moods:
                continue
            active.append(trait)
            
        return active
    
    def build_evolution_context(self, trust_level: int, user_sentiment: str = "neutral") -> str:
        """Constructs prompt context about current evolution state."""
        stage = self.get_current_stage(trust_level)
        active_traits = self.get_active_traits(trust_level, user_sentiment)
        
        context = f"\n\n[RELATIONSHIP STATUS]\n"
        context += f"Trust Level: {trust_level} ({stage['name']})\n"
        context += f"{stage['behavior']}\n"
        
        if active_traits:
            context += "\n[ACTIVE TRAITS]\n"
            for trait in active_traits:
                context += f"- {trait['name']}: {trait['description']}\n"
                if 'example' in trait:
                    context += f"  Example: \"{trait['example']}\"\n"
        
        return context
    
    def check_milestone(self, old_trust: int, new_trust: int) -> Optional[str]:
        """
        Checks if a milestone was crossed and returns the message.
        Only triggers when crossing UPWARDS into a new threshold.
        """
        for milestone in self.config.get('milestones', []):
            threshold = milestone['trust_level']
            # Check if we just crossed this threshold
            if old_trust < threshold <= new_trust:
                logger.info(f"Milestone reached: {threshold} trust")
                return milestone['message']
        return None

# Global instance factory (since it depends on character name)
_managers: Dict[str, EvolutionManager] = {}

def get_evolution_manager(character_name: str) -> EvolutionManager:
    if character_name not in _managers:
        _managers[character_name] = EvolutionManager(character_name)
    return _managers[character_name]
