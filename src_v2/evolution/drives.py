"""
Drive System for Autonomous Agents (Phase 3.3)

Manages internal drives (Social Battery, Curiosity, Concern) that motivate
proactive behavior. Drives decay or increase over time and trigger
actions when they cross a threshold.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from loguru import logger
import random
import json

from src_v2.core.database import db_manager
from src_v2.config.settings import settings
from src_v2.evolution.trust import trust_manager


@dataclass
class Drive:
    name: str
    value: float  # 0.0 to 1.0 (1.0 = maximum intensity)
    threshold: float  # Value above which this drive triggers action
    description: str

    def is_active(self) -> bool:
        return self.value >= self.threshold


class DriveManager:
    """
    Manages the state and evaluation of character drives.
    
    Drives:
    1. Social Battery (Global): Drains when alone, recharges when chatting.
       - High: Wants to chat.
       - Low: Wants to be alone (lurk).
    2. Concern (Per-User): Increases when high-trust users are silent.
    3. Curiosity (Per-User): Increases when goals are stagnant or random.
    """
    
    # Configuration
    SOCIAL_BATTERY_DECAY_PER_HOUR = 0.05
    CONCERN_GROWTH_PER_HOUR = 0.02
    CURIOSITY_BASE_CHANCE = 0.1
    
    def __init__(self):
        pass

    async def get_social_battery(self, character_name: str) -> float:
        """
        Get global social battery level (0.0 to 1.0).
        Stored in Redis. Default 1.0 (Full).
        """
        if not db_manager.redis_client:
            return 1.0
            
        key = f"drives:{character_name}:social_battery"
        val = await db_manager.redis_client.get(key)
        return float(val) if val else 1.0

    async def update_social_battery(self, character_name: str, delta: float):
        """
        Update social battery level.
        """
        if not db_manager.redis_client:
            return
            
        current = await self.get_social_battery(character_name)
        new_val = max(0.0, min(1.0, current + delta))
        
        key = f"drives:{character_name}:social_battery"
        await db_manager.redis_client.set(key, str(new_val), ex=86400*7) # 7 day expiry
        logger.debug(f"Updated social battery for {character_name}: {current:.2f} -> {new_val:.2f}")

    async def evaluate_drives(
        self, 
        user_id: str, 
        character_name: str, 
        trust_score: int, 
        last_interaction: Optional[datetime]
    ) -> List[Drive]:
        """
        Evaluate all drives for a specific user context.
        Returns a list of active drives (above threshold).
        """
        active_drives = []
        
        # 1. Social Battery (Global)
        # If battery is high, we are "Socially Eager"
        # If battery is low, we are "Socially Drained" (might prevent proactive)
        social_battery = await self.get_social_battery(character_name)
        
        # Simulate decay based on time (simplified: just use current value)
        # In a real loop, we'd decay it periodically. Here we assume it's updated by events.
        
        if social_battery > 0.7:
            active_drives.append(Drive(
                name="social_eagerness",
                value=social_battery,
                threshold=0.7,
                description="I'm feeling energetic and want to chat."
            ))
        elif social_battery < 0.3:
            # Low battery might suppress other drives
            logger.debug(f"Social battery low ({social_battery:.2f}), suppressing proactive drives.")
            return []

        # 2. Concern (Per-User)
        # Only for friends (trust > 10)
        if trust_score > 10 and last_interaction:
            # Ensure UTC
            if last_interaction.tzinfo is None:
                last_interaction = last_interaction.replace(tzinfo=timezone.utc)
            
            now = datetime.now(timezone.utc)
            hours_since = (now - last_interaction).total_seconds() / 3600
            
            # Concern grows with time, scaled by trust
            # Trust 10: 0.02 per hour
            # Trust 50: 0.05 per hour
            growth_rate = self.CONCERN_GROWTH_PER_HOUR * (1 + (trust_score / 50))
            concern_value = min(1.0, hours_since * growth_rate)
            
            # Threshold drops as trust increases (we worry faster about close friends)
            # Trust 10: Threshold 0.8 (40 hours)
            # Trust 50: Threshold 0.5 (10 hours)
            concern_threshold = max(0.3, 0.9 - (trust_score / 100))
            
            if concern_value > concern_threshold:
                active_drives.append(Drive(
                    name="concern",
                    value=concern_value,
                    threshold=concern_threshold,
                    description=f"I haven't heard from them in {int(hours_since)} hours and I'm worried."
                ))

        # 3. Curiosity (Per-User)
        # Random chance + boost if we have unfinished goals
        # We don't query goals here to avoid circular deps or perf hit, 
        # just use a base chance + trust boost
        curiosity_value = random.random()
        curiosity_threshold = 0.95 - (trust_score / 200) # Easier to be curious about friends
        
        if curiosity_value > curiosity_threshold:
            active_drives.append(Drive(
                name="curiosity",
                value=curiosity_value,
                threshold=curiosity_threshold,
                description="I'm thinking about them and wondering what they're up to."
            ))

        return active_drives

    async def should_initiate(self, user_id: str, character_name: str, drive: Drive) -> bool:
        """
        Trust-gating logic.
        Decides if a drive is strong enough to overcome social anxiety/norms based on trust.
        """
        trust = await trust_manager.get_relationship_level(user_id, character_name)
        trust_score = trust.get("score", 0)
        
        # Never initiate with Strangers (Trust < 0) or very low trust
        if trust_score < 0:
            return False
            
        # Base threshold to initiate
        # Stranger (0-10): High threshold (0.9)
        # Friend (20-50): Medium threshold (0.6)
        # Partner (80+): Low threshold (0.3)
        required_intensity = max(0.2, 0.9 - (trust_score / 100))
        
        should_act = drive.value >= required_intensity
        
        if should_act:
            logger.info(f"Drive '{drive.name}' ({drive.value:.2f}) triggered initiation for {user_id} (Trust: {trust_score}, Req: {required_intensity:.2f})")
        else:
            logger.debug(f"Drive '{drive.name}' ({drive.value:.2f}) too weak for trust level {trust_score} (Req: {required_intensity:.2f})")
            
        return should_act

# Global instance
drive_manager = DriveManager()
