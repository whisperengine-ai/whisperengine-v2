"""
Channel Lurking - Passive Engagement Detector

Detects when a conversation in a channel is relevant to the bot's expertise
and determines if the bot should organically join the conversation.

Key Principles:
- NO LLM calls for detection (all local processing)
- Keyword matching + embedding similarity for relevance scoring
- Strict rate limiting to prevent spam
- Conservative thresholds (start high, tune down)
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
import yaml
import asyncio
from loguru import logger

from src_v2.memory.embeddings import EmbeddingService
from src_v2.config.settings import settings
from src_v2.core.database import db_manager


@dataclass
class LurkTriggers:
    """Configuration for character-specific lurk triggers."""
    high_relevance: List[str] = field(default_factory=list)
    medium_relevance: List[str] = field(default_factory=list)
    low_relevance: List[str] = field(default_factory=list)
    question_patterns: List[str] = field(default_factory=list)
    topic_sentences: List[str] = field(default_factory=list)
    emotional_keywords: Dict[str, List[str]] = field(default_factory=dict)
    spam_warnings: List[str] = field(default_factory=list)


@dataclass
class LurkResult:
    """Result of lurk detection analysis."""
    should_respond: bool
    confidence: float
    detected_topics: List[str]
    trigger_reason: str
    keyword_score: float
    embedding_score: float
    context_boost: float


class LurkCooldownManager:
    """
    Manages rate limiting for lurk responses.
    Prevents the bot from responding too frequently in channels or to users.
    Uses Redis for persistence if available, falls back to in-memory.
    """
    
    def __init__(self):
        self.channel_cooldown_minutes = getattr(settings, 'LURK_CHANNEL_COOLDOWN_MINUTES', 30)
        self.user_cooldown_minutes = getattr(settings, 'LURK_USER_COOLDOWN_MINUTES', 60)
        self.max_daily_responses = getattr(settings, 'LURK_DAILY_MAX_RESPONSES', 20)
        
        # In-memory fallback
        self._channel_last_response: Dict[str, datetime] = {}
        self._user_last_response: Dict[str, datetime] = {}
        self._daily_count = 0
        self._daily_reset: Optional[datetime] = None
    
    def _check_daily_reset_memory(self) -> None:
        """Reset in-memory daily counter if it's a new day."""
        now = datetime.now()
        if self._daily_reset is None or now.date() > self._daily_reset.date():
            self._daily_count = 0
            self._daily_reset = now
    
    async def can_respond(self, channel_id: str, user_id: str) -> Tuple[bool, str]:
        """
        Check if a lurk response is allowed.
        
        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        # Redis Path
        if db_manager.redis_client:
            try:
                today = datetime.now().strftime("%Y-%m-%d")
                daily_key = f"lurk:daily:{today}"
                channel_key = f"lurk:cooldown:channel:{channel_id}"
                user_key = f"lurk:cooldown:user:{user_id}"
                
                # Check daily limit
                daily_count = await db_manager.redis_client.get(daily_key)
                if daily_count and int(daily_count) >= self.max_daily_responses:
                    return False, "daily_limit"
                
                # Check channel cooldown
                if await db_manager.redis_client.exists(channel_key):
                    return False, "channel_cooldown"
                
                # Check user cooldown
                if await db_manager.redis_client.exists(user_key):
                    return False, "user_cooldown"
                    
                return True, "allowed"
            except Exception as e:
                logger.error(f"Redis error in can_respond: {e}. Falling back to memory.")

        # In-Memory Fallback
        self._check_daily_reset_memory()
        now = datetime.now()
        
        # Check global daily limit
        if self._daily_count >= self.max_daily_responses:
            return False, "daily_limit"
        
        # Check channel cooldown
        if channel_id in self._channel_last_response:
            elapsed = now - self._channel_last_response[channel_id]
            if elapsed < timedelta(minutes=self.channel_cooldown_minutes):
                return False, "channel_cooldown"
        
        # Check user cooldown
        if user_id in self._user_last_response:
            elapsed = now - self._user_last_response[user_id]
            if elapsed < timedelta(minutes=self.user_cooldown_minutes):
                return False, "user_cooldown"
        
        return True, "allowed"
    
    async def record_response(self, channel_id: str, user_id: str) -> None:
        """Record that a lurk response was sent."""
        # Redis Path
        if db_manager.redis_client:
            try:
                today = datetime.now().strftime("%Y-%m-%d")
                daily_key = f"lurk:daily:{today}"
                channel_key = f"lurk:cooldown:channel:{channel_id}"
                user_key = f"lurk:cooldown:user:{user_id}"
                
                async with db_manager.redis_client.pipeline() as pipe:
                    # Increment daily count (expire in 48h to be safe)
                    await pipe.incr(daily_key)
                    await pipe.expire(daily_key, 172800)
                    
                    # Set channel cooldown
                    await pipe.setex(channel_key, self.channel_cooldown_minutes * 60, "1")
                    
                    # Set user cooldown
                    await pipe.setex(user_key, self.user_cooldown_minutes * 60, "1")
                    
                    await pipe.execute()
                logger.debug(f"Recorded lurk response in Redis.")
                return
            except Exception as e:
                logger.error(f"Redis error in record_response: {e}. Falling back to memory.")

        # In-Memory Fallback
        now = datetime.now()
        self._channel_last_response[channel_id] = now
        self._user_last_response[user_id] = now
        self._daily_count += 1
        logger.debug(f"Recorded lurk response in memory. Daily count: {self._daily_count}")
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get current cooldown statistics."""
        if db_manager.redis_client:
            try:
                today = datetime.now().strftime("%Y-%m-%d")
                daily_key = f"lurk:daily:{today}"
                daily_count = await db_manager.redis_client.get(daily_key)
                return {
                    "daily_count": int(daily_count) if daily_count else 0,
                    "max_daily": self.max_daily_responses,
                    "storage": "redis"
                }
            except Exception:
                pass

        self._check_daily_reset_memory()
        return {
            "daily_count": self._daily_count,
            "max_daily": self.max_daily_responses,
            "channels_on_cooldown": len(self._channel_last_response),
            "users_on_cooldown": len(self._user_last_response),
            "storage": "memory"
        }


class LurkDetector:
    """
    Detects when a message is relevant enough to the bot's expertise
    to warrant an organic response (without being @mentioned).
    
    Detection is local-only (no LLM calls) using:
    1. Keywords from lurk_triggers.yaml (character-specific)
    2. Keywords from Neo4j background facts (character knowledge graph)
    3. Embedding similarity to topic sentences
    """
    
    # Messages to always ignore
    IGNORE_PREFIXES = ('!', '/', '.', '?', '-', '$', '%')
    MIN_MESSAGE_LENGTH = 15
    
    def __init__(self, character_name: str):
        self.character_name = character_name
        self.embedding_service = EmbeddingService()
        self.cooldown_manager = LurkCooldownManager()
        
        # Load triggers from YAML
        self.triggers = self._load_triggers()
        
        # Pre-compute topic embeddings (lazy loaded)
        self._topic_embeddings: Optional[List[List[float]]] = None
        
        # Neo4j-derived keywords (loaded async on first use)
        self._neo4j_keywords: Optional[List[str]] = None
        self._neo4j_loaded: bool = False
        
        # Threshold from settings
        self.threshold = getattr(settings, 'LURK_CONFIDENCE_THRESHOLD', 0.7)
        
        # Channel management (in-memory for now, TODO: persist to DB)
        # We use a blocklist approach: lurking is enabled by default on all channels
        # unless explicitly disabled.
        self._disabled_channels: set = set()
        self._channel_thresholds: Dict[str, float] = {}
        
        logger.info(f"LurkDetector initialized for {character_name}")
    
    def _load_triggers(self) -> LurkTriggers:
        """Load lurk triggers from YAML file."""
        yaml_path = Path(f"characters/{self.character_name}/lurk_triggers.yaml")
        
        if not yaml_path.exists():
            logger.warning(f"No lurk_triggers.yaml found for {self.character_name}. Using empty triggers.")
            return LurkTriggers()
        
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            
            keywords = data.get("keywords", {})
            
            # Helper to ensure all items are strings (handles numbers like 1989 in YAML)
            def to_str_list(items: Any) -> List[str]:
                if not items or not isinstance(items, list):
                    return []
                return [str(item) for item in items if item is not None]

            return LurkTriggers(
                high_relevance=to_str_list(keywords.get("high_relevance", [])),
                medium_relevance=to_str_list(keywords.get("medium_relevance", [])),
                low_relevance=to_str_list(keywords.get("low_relevance", [])),
                question_patterns=to_str_list(data.get("question_patterns", [])),
                topic_sentences=to_str_list(data.get("topic_sentences", [])),
                emotional_keywords={k: to_str_list(v) for k, v in data.get("emotional_keywords", {}).items()},
                spam_warnings=to_str_list(data.get("spam_warnings", []))
            )
        except Exception as e:
            logger.error(f"Failed to load lurk triggers: {e}")
            return LurkTriggers()
    
    async def _load_neo4j_keywords(self) -> List[str]:
        """
        Load additional keywords from the character's Neo4j knowledge graph.
        
        Extracts entity names from HAS_INTEREST, HAS_EXPERTISE, HAS_SKILL,
        and similar predicates to enrich lurk detection.
        
        This runs once on first analyze() call, not per-message.
        """
        if self._neo4j_loaded:
            return self._neo4j_keywords or []
            
        self._neo4j_loaded = True
        self._neo4j_keywords = []
        
        try:
            if not db_manager.neo4j_driver:
                logger.debug("Neo4j not connected, skipping keyword enrichment")
                return []
            
            # Query for character's interests, expertise, and skills
            query = """
            MATCH (c:Character {name: $bot_name})-[r:FACT]->(e:Entity)
            WHERE r.predicate IN [
                'HAS_INTEREST', 'HAS_EXPERTISE', 'HAS_SKILL', 
                'SPECIALIZES_IN', 'TEACHES', 'OCCUPATION',
                'HAS_VALUE', 'HAS_GOAL'
            ]
            RETURN DISTINCT e.name as keyword
            """
            
            async with db_manager.neo4j_driver.session() as session:
                result = await session.run(query, bot_name=self.character_name)
                records = await result.data()
                
                # Extract meaningful words from each entity
                for record in records:
                    entity_name = record.get("keyword", "")
                    if entity_name:
                        # Split into words and filter short ones
                        words = [w.lower() for w in entity_name.split() if len(w) > 3]
                        self._neo4j_keywords.extend(words)
                
                # Deduplicate
                self._neo4j_keywords = list(set(self._neo4j_keywords))
                logger.info(f"Loaded {len(self._neo4j_keywords)} keywords from Neo4j for {self.character_name}")
                
        except Exception as e:
            logger.warning(f"Failed to load Neo4j keywords for lurk detection: {e}")
            
        return self._neo4j_keywords or []
    
    async def _get_topic_embeddings(self) -> List[List[float]]:
        """Lazy load and cache topic sentence embeddings."""
        if self._topic_embeddings is None:
            if not self.triggers.topic_sentences:
                self._topic_embeddings = []
            else:
                # Compute embeddings for topic sentences
                loop = asyncio.get_running_loop()
                self._topic_embeddings = await loop.run_in_executor(
                    None,
                    self.embedding_service.embed_documents,
                    self.triggers.topic_sentences
                )
                logger.debug(f"Computed {len(self._topic_embeddings or [])} topic embeddings for {self.character_name}")
        
        return self._topic_embeddings or []
    
    def _should_ignore_message(self, content: str, author_is_bot: bool, has_mentions: bool = False, is_broadcast_channel: bool = False) -> Tuple[bool, str]:
        """Check if message should be ignored entirely."""
        # Ignore bot messages UNLESS they're from broadcast channel
        # This enables cross-bot discovery (Dream pouncing on Elena's dreams, etc.)
        if author_is_bot and not is_broadcast_channel:
            return True, "bot_message"
            
        # Ignore messages mentioning others (politeness)
        if has_mentions:
            return True, "mentions_others"
        
        # Ignore too short
        if len(content.strip()) < self.MIN_MESSAGE_LENGTH:
            return True, "too_short"
        
        # Ignore command-like messages
        if content.strip().startswith(self.IGNORE_PREFIXES):
            return True, "command"
        
        # Ignore messages that are mostly links
        if content.count("http") >= 2 or (content.count("http") == 1 and len(content) < 100):
            return True, "link_heavy"
        
        return False, ""
    
    async def _keyword_score(self, message: str) -> Tuple[float, List[str]]:
        """
        Calculate keyword-based relevance score.
        
        Uses keywords from:
        1. lurk_triggers.yaml (high/medium/low relevance)
        2. Neo4j knowledge graph (character interests, expertise, skills)
        
        Returns:
            Tuple of (score, matched_keywords)
        """
        message_lower = message.lower()
        score = 0.0
        matched = []
        
        # High relevance keywords (+0.4 each, cap at 0.8)
        for kw in self.triggers.high_relevance:
            if kw.lower() in message_lower:
                score += 0.4
                matched.append(kw)
        
        # Medium relevance keywords (+0.2 each)
        for kw in self.triggers.medium_relevance:
            if kw.lower() in message_lower:
                score += 0.2
                matched.append(kw)
        
        # Low relevance keywords (+0.1 each)
        for kw in self.triggers.low_relevance:
            if kw.lower() in message_lower:
                score += 0.1
                matched.append(kw)
        
        # Neo4j-derived keywords (+0.15 each, up to 0.45 max)
        neo4j_keywords = await self._load_neo4j_keywords()
        neo4j_bonus = 0.0
        for kw in neo4j_keywords:
            if kw in message_lower and kw not in matched:
                neo4j_bonus += 0.15
                matched.append(f"[neo4j:{kw}]")
                if neo4j_bonus >= 0.45:
                    break
        score += neo4j_bonus
        
        # Question patterns bonus (+0.15)
        for pattern in self.triggers.question_patterns:
            if pattern.lower() in message_lower:
                score += 0.15
                break  # Only count once
        
        return min(score, 1.0), matched
    
    async def _embedding_score(self, message: str) -> float:
        """
        Calculate embedding-based semantic similarity score.
        
        Returns:
            Best similarity score (0.0 to 1.0)
        """
        topic_embeddings = await self._get_topic_embeddings()
        
        if not topic_embeddings:
            return 0.0
        
        # Embed the message
        msg_embedding = await self.embedding_service.embed_query_async(message)
        
        # Calculate cosine similarity with each topic
        def cosine_similarity(a: List[float], b: List[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = sum(x * x for x in a) ** 0.5
            norm_b = sum(x * x for x in b) ** 0.5
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot / (norm_a * norm_b)
        
        similarities = [cosine_similarity(msg_embedding, te) for te in topic_embeddings]
        return max(similarities) if similarities else 0.0
    
    def _context_boost(self, message: str, user_trust_score: Optional[int] = None) -> float:
        """
        Calculate context-based score boost.
        
        Args:
            message: The message content
            user_trust_score: Optional trust score for the user (0-100)
        
        Returns:
            Boost value (0.0 to 0.3)
        """
        boost = 0.0
        
        # Question bonus
        if message.strip().endswith('?'):
            boost += 0.15
        
        # Trust bonus (close friends get priority)
        if user_trust_score is not None and user_trust_score >= 50:
            boost += 0.1
        
        # Emotional keywords bonus
        message_lower = message.lower()
        positive_emotions = self.triggers.emotional_keywords.get("positive", [])
        
        # Ensure positive_emotions is a list of strings
        if positive_emotions and isinstance(positive_emotions, list):
            for emotion in positive_emotions:
                if isinstance(emotion, str) and emotion.lower() in message_lower:
                    boost += 0.05
                    break
        
        return min(boost, 0.3)
    
    async def analyze(
        self,
        message: str,
        channel_id: str,
        user_id: str,
        author_is_bot: bool = False,
        has_mentions: bool = False,
        user_trust_score: Optional[int] = None,
        channel_lurk_enabled: bool = True,
        custom_threshold: Optional[float] = None,
        is_broadcast_channel: bool = False
    ) -> LurkResult:
        """
        Analyze a message to determine if the bot should respond.
        
        Args:
            message: Message content
            channel_id: Discord channel ID
            user_id: Discord user ID
            author_is_bot: Whether the author is a bot
            has_mentions: Whether the message mentions other users
            user_trust_score: Optional trust score for personalization
            channel_lurk_enabled: Whether lurking is enabled for this channel
            custom_threshold: Override default threshold
            is_broadcast_channel: If True, allows bot messages (for cross-bot discovery)
        
        Returns:
            LurkResult with decision and scores
        """
        # Check if lurking is enabled for this channel
        if not channel_lurk_enabled:
            return LurkResult(
                should_respond=False,
                confidence=0.0,
                detected_topics=[],
                trigger_reason="channel_disabled",
                keyword_score=0.0,
                embedding_score=0.0,
                context_boost=0.0
            )
        
        # Check if message should be ignored
        should_ignore, ignore_reason = self._should_ignore_message(message, author_is_bot, has_mentions, is_broadcast_channel)
        if should_ignore:
            return LurkResult(
                should_respond=False,
                confidence=0.0,
                detected_topics=[],
                trigger_reason=ignore_reason,
                keyword_score=0.0,
                embedding_score=0.0,
                context_boost=0.0
            )
        
        # Check cooldowns
        can_respond, cooldown_reason = await self.cooldown_manager.can_respond(channel_id, user_id)
        if not can_respond:
            return LurkResult(
                should_respond=False,
                confidence=0.0,
                detected_topics=[],
                trigger_reason=cooldown_reason,
                keyword_score=0.0,
                embedding_score=0.0,
                context_boost=0.0
            )
        
        # Layer 1: Keyword matching (fast, includes Neo4j enrichment)
        kw_score, matched_keywords = await self._keyword_score(message)
        
        # Early exit if no keywords match at all
        if kw_score == 0:
            return LurkResult(
                should_respond=False,
                confidence=0.0,
                detected_topics=[],
                trigger_reason="no_keyword_match",
                keyword_score=0.0,
                embedding_score=0.0,
                context_boost=0.0
            )
        
        # Layer 2: Embedding similarity (accurate)
        emb_score = await self._embedding_score(message)
        
        # Layer 3: Context boost
        ctx_boost = self._context_boost(message, user_trust_score)
        
        # Weighted combination
        # Keywords: 30%, Embeddings: 50%, Context: 20%
        final_score = (kw_score * 0.3) + (emb_score * 0.5) + ctx_boost
        
        # Apply threshold
        threshold = custom_threshold if custom_threshold is not None else self.threshold
        should_respond = final_score >= threshold
        
        trigger_reason = "threshold_met" if should_respond else "below_threshold"
        
        return LurkResult(
            should_respond=should_respond,
            confidence=final_score,
            detected_topics=matched_keywords,
            trigger_reason=trigger_reason,
            keyword_score=kw_score,
            embedding_score=emb_score,
            context_boost=ctx_boost
        )
    
    # =====================
    # Channel Management
    # =====================
    
    async def is_channel_enabled(self, channel_id: str) -> bool:
        """Check if lurking is enabled for a channel."""
        # Lurking is enabled by default unless the channel is in the disabled list
        # For now, use in-memory storage. In production, this should query v2_channel_settings
        return channel_id not in self._disabled_channels
    
    async def enable_channel(self, channel_id: str) -> None:
        """Enable lurking for a channel."""
        self._disabled_channels.discard(channel_id)
        logger.info(f"Lurking enabled for channel {channel_id}")
        # TODO: Persist to v2_channel_settings table
    
    async def disable_channel(self, channel_id: str) -> None:
        """Disable lurking for a channel."""
        self._disabled_channels.add(channel_id)
        logger.info(f"Lurking disabled for channel {channel_id}")
        # TODO: Persist to v2_channel_settings table
    
    async def get_channel_threshold(self, channel_id: str) -> float:
        """Get the confidence threshold for a channel."""
        return self._channel_thresholds.get(channel_id, self.threshold)
    
    async def set_channel_threshold(self, channel_id: str, threshold: float) -> None:
        """Set a custom threshold for a channel."""
        self._channel_thresholds[channel_id] = threshold
        logger.info(f"Set threshold {threshold} for channel {channel_id}")
        # TODO: Persist to v2_channel_settings table
    
    async def get_channel_stats(self, channel_id: str) -> Dict[str, Any]:
        """Get lurking statistics for a channel."""
        # For now, use cooldown manager stats (no per-channel tracking yet)
        cooldown_stats = await self.cooldown_manager.get_stats()
        return {
            "today": cooldown_stats.get("daily_count", 0),
            "total": cooldown_stats.get("daily_count", 0),  # TODO: Query v2_lurk_responses for historical data
            "threshold": await self.get_channel_threshold(channel_id),
            "enabled": await self.is_channel_enabled(channel_id)
        }
    
    async def get_guild_stats(self, guild_id: str) -> Dict[str, Any]:
        """Get lurking statistics for the guild."""
        # Since lurking is enabled by default, we return disabled channels
        # and channels with custom thresholds.
        
        return {
            "guild_id": guild_id,
            "disabled_channels": list(self._disabled_channels),
            "custom_thresholds": self._channel_thresholds,
            "global_stats": await self.cooldown_manager.get_stats()
        }
    
    async def record_response(
        self, 
        channel_id: str, 
        user_id: str,
        message_id: str = "",
        confidence: float = 0.0,
        trigger_type: str = ""
    ) -> None:
        """Record that a lurk response was sent."""
        await self.cooldown_manager.record_response(channel_id, user_id)
        logger.info(f"Recorded lurk response: channel={channel_id}, user={user_id}, confidence={confidence:.2f}")
        # TODO: Insert into v2_lurk_responses table
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get detector statistics."""
        return {
            "character": self.character_name,
            "threshold": self.threshold,
            "triggers_loaded": {
                "high_relevance": len(self.triggers.high_relevance),
                "medium_relevance": len(self.triggers.medium_relevance),
                "low_relevance": len(self.triggers.low_relevance),
                "topic_sentences": len(self.triggers.topic_sentences)
            },
            "cooldown": await self.cooldown_manager.get_stats()
        }


# Singleton per character (lazy loaded)
_lurk_detectors: Dict[str, LurkDetector] = {}


def get_lurk_detector(character_name: str) -> LurkDetector:
    """Get or create a LurkDetector for a character."""
    if character_name not in _lurk_detectors:
        _lurk_detectors[character_name] = LurkDetector(character_name)
    return _lurk_detectors[character_name]
