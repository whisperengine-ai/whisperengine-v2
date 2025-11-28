"""
Universe Event Bus (Phase 3.4)

Cross-bot coordination via events. When a significant event happens with one
character (e.g., user shares major life news), other characters in the universe
can be notified if privacy rules allow.

Event Flow:
1. Character detects significant event during conversation
2. Publishes event to bus via task_queue.enqueue_gossip()
3. Worker processes event, checks privacy, and injects "gossip" memories
4. Other characters can now reference the information naturally

Privacy Rules (from PRIVACY_AND_DATA_SEGMENTATION.md):
- Only share with bots the user has FRIEND+ trust with
- Never share sensitive topics (health, finances, relationships, legal)
- Respect user opt-out preferences
- Events have propagation_depth to prevent infinite loops
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from loguru import logger
import json

from src_v2.config.settings import settings
from src_v2.core.database import db_manager
from src_v2.evolution.trust import trust_manager
from src_v2.universe.privacy import privacy_manager


class EventType(str, Enum):
    """Types of events that can be shared across the universe."""
    USER_UPDATE = "user_update"          # Major life event (new job, moved, etc.)
    EMOTIONAL_SPIKE = "emotional_spike"  # User is notably happy/sad
    TOPIC_DISCOVERY = "topic_discovery"  # User revealed new interest/hobby
    GOAL_ACHIEVED = "goal_achieved"      # User completed something meaningful


# Topics that should NEVER be shared across bots
SENSITIVE_TOPICS = frozenset([
    "health", "medical", "doctor", "therapy", "medication", "diagnosis",
    "finance", "money", "debt", "salary", "income", "bankrupt",
    "relationship", "dating", "partner", "divorce", "breakup",
    "legal", "lawsuit", "arrest", "crime", "court",
    "secret", "private", "confidential", "don't tell",
])

# Minimum trust level required for target bot to receive events
MIN_TRUST_FOR_GOSSIP = 20  # FRIEND level


@dataclass
class UniverseEvent:
    """
    An event to be shared across the universe.
    
    Attributes:
        event_type: Category of event
        user_id: Discord user ID this event concerns
        source_bot: Character name that detected the event
        summary: Brief, privacy-safe summary of the event
        topic: Main topic (for filtering sensitive content)
        propagation_depth: 0 = from user interaction, 1 = from another event
                          Events with depth > 1 are ignored to prevent loops
        timestamp: When the event occurred
        metadata: Additional context (optional)
    """
    event_type: EventType
    user_id: str
    source_bot: str
    summary: str
    topic: str
    propagation_depth: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for Redis/arq."""
        data = asdict(self)
        data["event_type"] = self.event_type.value
        data["timestamp"] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UniverseEvent":
        """Deserialize from Redis/arq."""
        data["event_type"] = EventType(data["event_type"])
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)
    
    def is_sensitive(self) -> bool:
        """Check if event contains sensitive topics."""
        topic_lower = self.topic.lower()
        summary_lower = self.summary.lower()
        
        for keyword in SENSITIVE_TOPICS:
            if keyword in topic_lower or keyword in summary_lower:
                return True
        return False


class UniverseEventBus:
    """
    Dispatcher for cross-bot events.
    
    Publishes events to the task queue, which are then processed by
    the insight worker to inject "gossip" memories into other bots.
    """
    
    async def publish(self, event: UniverseEvent) -> bool:
        """
        Publish an event to the universe.
        
        Args:
            event: The event to publish
            
        Returns:
            True if event was published, False if blocked by privacy rules
        """
        if not settings.ENABLE_UNIVERSE_EVENTS:
            logger.debug("Universe events disabled, skipping publish")
            return False
        
        # Block events with high propagation depth (prevent loops)
        if event.propagation_depth > 1:
            logger.warning(f"Blocking event with propagation_depth={event.propagation_depth}")
            self._log_blocked_metric("propagation_depth")
            return False
        
        # Block sensitive topics
        if event.is_sensitive():
            logger.info(f"Blocking sensitive event topic: {event.topic}")
            self._log_blocked_metric("sensitive_topic")
            return False
        
        # Check user privacy preferences
        privacy = await privacy_manager.get_settings(event.user_id)
        if not privacy.get("share_with_other_bots", True):
            logger.info(f"User {event.user_id} has opted out of cross-bot sharing")
            self._log_blocked_metric("user_opt_out")
            return False
        
        # Enqueue for processing
        from src_v2.workers.task_queue import task_queue
        job_id = await task_queue.enqueue_gossip(event)
        
        if job_id:
            logger.info(f"Published {event.event_type.value} event for user {event.user_id}")
            self._log_published_metric(event)
            return True
        
        return False
    
    async def get_eligible_recipients(self, event: UniverseEvent) -> List[str]:
        """
        Get list of bot names that should receive this event.
        
        A bot is eligible if:
        1. It's not the source bot
        2. User has FRIEND+ trust with the bot
        3. User hasn't opted out of sharing with that bot
        """
        if not db_manager.postgres_pool:
            return []
        
        async with db_manager.postgres_pool.acquire() as conn:
            # Get all bots with relationships to this user
            rows = await conn.fetch("""
                SELECT character_name, trust_score
                FROM v2_user_relationships
                WHERE user_id = $1 AND character_name != $2
            """, event.user_id, event.source_bot)
        
        eligible = []
        for row in rows:
            bot_name = row["character_name"]
            trust_score = row["trust_score"]
            
            # Check trust threshold
            if trust_score < MIN_TRUST_FOR_GOSSIP:
                logger.debug(f"Skipping {bot_name}: trust {trust_score} < {MIN_TRUST_FOR_GOSSIP}")
                continue
            
            eligible.append(bot_name)
        
        logger.debug(f"Eligible recipients for event: {eligible}")
        return eligible
    
    def _log_published_metric(self, event: UniverseEvent) -> None:
        """Log event publication to InfluxDB."""
        if not db_manager.influxdb_write_api:
            return
        
        try:
            from influxdb_client.client.write.point import Point
            
            point = Point("universe_event_published") \
                .tag("bot_name", event.source_bot) \
                .tag("event_type", event.event_type.value) \
                .tag("topic", event.topic[:50]) \
                .field("propagation_depth", event.propagation_depth) \
                .field("count", 1)
            
            db_manager.influxdb_write_api.write(
                bucket=settings.INFLUXDB_BUCKET,
                org=settings.INFLUXDB_ORG,
                record=point
            )
        except Exception as e:
            logger.warning(f"Failed to log universe event metric: {e}")
    
    def _log_blocked_metric(self, reason: str) -> None:
        """Log blocked event to InfluxDB."""
        if not db_manager.influxdb_write_api:
            return
        
        try:
            from influxdb_client.client.write.point import Point
            
            point = Point("universe_event_blocked") \
                .tag("reason", reason) \
                .field("count", 1)
            
            db_manager.influxdb_write_api.write(
                bucket=settings.INFLUXDB_BUCKET,
                org=settings.INFLUXDB_ORG,
                record=point
            )
        except Exception as e:
            logger.warning(f"Failed to log blocked event metric: {e}")


# Global instance
event_bus = UniverseEventBus()
