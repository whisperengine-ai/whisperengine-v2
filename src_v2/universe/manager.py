from typing import Optional, List
from datetime import datetime
from loguru import logger
from src_v2.core.database import db_manager, retry_db_operation, require_db
from src_v2.core.cache import CacheManager


class UniverseManager:
    """
    Manages the Emergent Universe - planets, inhabitants, topics, and relationships.
    
    The universe grows organically from real interactions:
    - Planets (Discord servers) are discovered when bots land
    - Topics emerge from message content
    - User relationships form from interactions (mentions, replies)
    - Peak hours are learned from activity patterns
    """
    
    def __init__(self):
        self._embedding_service = None
        self._cache = CacheManager()
        
    @property
    def embedding_service(self):
        """Lazy load embedding service to avoid circular imports."""
        if self._embedding_service is None:
            from src_v2.memory.embeddings import EmbeddingService
            self._embedding_service = EmbeddingService()
        return self._embedding_service

    @require_db("neo4j")
    async def initialize(self):
        """Initialize constraints for the Universe graph."""
        queries = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Planet) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Channel) REQUIRE c.id IS UNIQUE",
            # User constraint is likely already created by KnowledgeManager, but good to ensure
            "CREATE CONSTRAINT IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
            # Topic constraint for emergent topics
            "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE",
        ]
        
        # Create indexes for faster lookups
        indexes = [
            "CREATE INDEX IF NOT EXISTS FOR (p:Planet) ON (p.active)",
            "CREATE INDEX IF NOT EXISTS FOR (t:Topic) ON (t.mention_count)",
        ]
        
        try:
            async with db_manager.neo4j_driver.session() as session:
                for query in queries:
                    await session.run(query)
                for index in indexes:
                    await session.run(index)
            logger.info("Universe graph constraints and indexes initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize Universe constraints: {e}")

    @retry_db_operation()
    @require_db("neo4j")
    async def register_planet(self, guild_id: str, name: str):
        """Register or update a Discord server as a Planet."""
        query = """
        MERGE (p:Planet {id: $guild_id})
        SET p.name = $name, p.last_seen = datetime(), p.active = true
        RETURN p
        """
        async with db_manager.neo4j_driver.session() as session:
            await session.run(query, guild_id=str(guild_id), name=name)

    @retry_db_operation()
    @require_db("neo4j")
    async def register_channel(self, guild_id: str, channel_id: str, name: str, channel_type: str):
        """Register a channel on a planet."""
        query = """
        MATCH (p:Planet {id: $guild_id})
        MERGE (c:Channel {id: $channel_id})
        SET c.name = $name, c.type = $channel_type, c.last_seen = datetime()
        MERGE (p)-[:HAS_CHANNEL]->(c)
        """
        async with db_manager.neo4j_driver.session() as session:
            await session.run(query, guild_id=str(guild_id), channel_id=str(channel_id), name=name, channel_type=channel_type)

    @retry_db_operation()
    @require_db("neo4j")
    async def record_presence(self, user_id: str, guild_id: str):
        """Record that a user is on a planet."""
        query = """
        MATCH (u:User {id: $user_id})
        MATCH (p:Planet {id: $guild_id})
        MERGE (u)-[r:ON_PLANET]->(p)
        SET r.last_seen = datetime()
        """
        async with db_manager.neo4j_driver.session() as session:
            await session.run(query, user_id=str(user_id), guild_id=str(guild_id))

    @retry_db_operation()
    async def get_planet_context(self, guild_id: str) -> Optional[dict]:
        """Get context about the current planet (server)."""
        if not db_manager.neo4j_driver: return None

        query = """
        MATCH (p:Planet {id: $guild_id})
        OPTIONAL MATCH (p)-[:HAS_CHANNEL]->(c:Channel)
        OPTIONAL MATCH (u:User)-[:ON_PLANET]->(p)
        RETURN p.name as name, 
               count(DISTINCT c) as channel_count, 
               collect(DISTINCT c.name) as channels,
               count(DISTINCT u) as inhabitant_count
        """
        async with db_manager.neo4j_driver.session() as session:
            result = await session.run(query, guild_id=str(guild_id))
            record = await result.single()
            if record and record["name"]:
                return {
                    "name": record["name"],
                    "channel_count": record["channel_count"],
                    "channels": record["channels"][:20], # Limit to 20 for context window
                    "inhabitant_count": record["inhabitant_count"]
                }
            return None

    @retry_db_operation()
    @require_db("neo4j")
    async def mark_planet_inactive(self, guild_id: str):
        """Mark a planet as inactive (bot removed)."""
        query = """
        MATCH (p:Planet {id: $guild_id})
        SET p.active = false, p.left_at = datetime()
        """
        async with db_manager.neo4j_driver.session() as session:
            await session.run(query, guild_id=str(guild_id))

    @retry_db_operation()
    @require_db("neo4j")
    async def remove_inhabitant(self, user_id: str, guild_id: str):
        """Remove a user's presence from a planet."""
        query = """
        MATCH (u:User {id: $user_id})-[r:ON_PLANET]->(p:Planet {id: $guild_id})
        DELETE r
        """
        async with db_manager.neo4j_driver.session() as session:
            await session.run(query, user_id=str(user_id), guild_id=str(guild_id))

    # ============ Phase 2: Learning to Listen ============
    
    @require_db("neo4j")
    async def observe_message(
        self, 
        guild_id: str, 
        channel_id: str, 
        user_id: str,
        message_content: str,
        mentioned_user_ids: List[str],
        reply_to_user_id: Optional[str] = None,
        user_display_name: Optional[str] = None
    ) -> None:
        """
        Observe a message and learn from it. Called for ALL guild messages.
        
        This is the core "learning" function that makes the universe emergent:
        - Extracts topics from message content
        - Records user-to-user interactions (mentions, replies)
        - Updates user last_seen timestamps
        - Tracks message hour for peak activity learning
        
        Args:
            guild_id: Discord server ID
            channel_id: Channel ID where message was sent
            user_id: Author of the message
            message_content: Text content of the message
            mentioned_user_ids: List of user IDs mentioned in the message
            reply_to_user_id: User ID being replied to, if this is a reply
            user_display_name: Display name of the user
        """
        # Skip very short messages (greetings, reactions, etc.)
        if len(message_content.strip()) < 10:
            return
            
        try:
            # Run observations in parallel (non-blocking)
            import asyncio
            await asyncio.gather(
                self._update_user_activity(user_id, guild_id, channel_id, user_display_name),
                self._extract_and_link_topics(guild_id, message_content),
                self._record_user_interactions(user_id, mentioned_user_ids, reply_to_user_id, guild_id),
                self._track_activity_hour(guild_id),
                return_exceptions=True  # Don't fail on individual errors
            )
        except Exception as e:
            # Log but don't raise - observation is non-critical
            logger.debug(f"Universe observation error (non-fatal): {e}")

    @retry_db_operation()
    @require_db("neo4j")
    async def _update_user_activity(
        self, 
        user_id: str, 
        guild_id: str, 
        channel_id: str,
        display_name: Optional[str] = None
    ) -> None:
        """Update user's last seen timestamp and activity on planet/channel."""
        query = """
        MERGE (u:User {id: $user_id})
        SET u.last_seen_at = datetime()
        """
        
        if display_name:
            query += "SET u.display_name = $display_name "
            
        query += """
        WITH u
        MATCH (p:Planet {id: $guild_id})
        MERGE (u)-[r:ON_PLANET]->(p)
        SET r.last_seen = datetime(), r.message_count = COALESCE(r.message_count, 0) + 1
        WITH u, p
        MATCH (c:Channel {id: $channel_id})
        MERGE (u)-[a:ACTIVE_IN]->(c)
        SET a.last_seen = datetime(), a.message_count = COALESCE(a.message_count, 0) + 1
        """
        async with db_manager.neo4j_driver.session() as session:
            await session.run(
                query, 
                user_id=str(user_id), 
                guild_id=str(guild_id), 
                channel_id=str(channel_id),
                display_name=display_name
            )

    async def _extract_and_link_topics(self, guild_id: str, message_content: str) -> None:
        """Extract topics from message and link them to the planet."""
        # Extract meaningful topics (simple keyword extraction)
        topics = self._extract_topics(message_content)
        if not topics:
            return
            
        # Link topics to planet
        await self._link_topics_to_planet(guild_id, topics)

    def _extract_topics(self, message_content: str) -> List[str]:
        """
        Extract meaningful topics from message content.
        
        Uses simple keyword extraction (no LLM) to identify topics:
        - Filters out common stop words
        - Looks for nouns and key phrases
        - Returns lowercase, deduplicated topics
        """
        # Common stop words to filter out
        stop_words = {
            'i', 'me', 'my', 'myself', 'we', 'our', 'you', 'your', 'he', 'she', 'it',
            'they', 'them', 'what', 'which', 'who', 'this', 'that', 'these', 'those',
            'am', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has',
            'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may',
            'might', 'must', 'shall', 'can', 'a', 'an', 'the', 'and', 'but', 'if',
            'or', 'because', 'as', 'until', 'while', 'of', 'at', 'by', 'for', 'with',
            'about', 'against', 'between', 'into', 'through', 'during', 'before',
            'after', 'above', 'below', 'to', 'from', 'up', 'down', 'in', 'out', 'on',
            'off', 'over', 'under', 'again', 'further', 'then', 'once', 'here', 'there',
            'when', 'where', 'why', 'how', 'all', 'each', 'few', 'more', 'most', 'other',
            'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than',
            'too', 'very', 'just', 'also', 'now', 'even', 'well', 'way', 'like', 'really',
            'thing', 'things', 'know', 'think', 'want', 'get', 'got', 'go', 'going',
            'yeah', 'yes', 'ok', 'okay', 'lol', 'lmao', 'haha', 'hehe', 'omg',
            'im', 'ive', 'dont', 'doesnt', 'didnt', 'cant', 'wont', 'its', 'thats',
        }
        
        # Clean and tokenize
        import re
        # Remove URLs, mentions, emojis
        cleaned = re.sub(r'https?://\S+', '', message_content)
        cleaned = re.sub(r'<@!?\d+>', '', cleaned)
        cleaned = re.sub(r'<:\w+:\d+>', '', cleaned)
        
        # Extract words (alphanumeric, min 3 chars)
        words = re.findall(r'\b[a-zA-Z]{3,}\b', cleaned.lower())
        
        # Filter stop words and keep meaningful words
        topics = []
        for word in words:
            if word not in stop_words and len(word) >= 3:
                topics.append(word)
        
        # Deduplicate while preserving order, limit to top 5
        seen = set()
        unique_topics = []
        for topic in topics:
            if topic not in seen:
                seen.add(topic)
                unique_topics.append(topic)
                if len(unique_topics) >= 5:
                    break
                    
        return unique_topics

    @retry_db_operation()
    @require_db("neo4j")
    async def _link_topics_to_planet(self, guild_id: str, topics: List[str]) -> None:
        """Create or update Topic nodes and link them to the planet."""
        if not topics: return
        
        query = """
        MATCH (p:Planet {id: $guild_id})
        UNWIND $topics as topic_name
        MERGE (t:Topic {name: topic_name})
        ON CREATE SET t.mention_count = 1, t.first_seen = datetime()
        ON MATCH SET t.mention_count = t.mention_count + 1
        MERGE (p)-[r:HAS_TOPIC]->(t)
        ON CREATE SET r.count = 1, r.first_seen = datetime()
        ON MATCH SET r.count = r.count + 1
        SET r.last_seen = datetime()
        """
        async with db_manager.neo4j_driver.session() as session:
            await session.run(query, guild_id=str(guild_id), topics=topics)

    @retry_db_operation()
    @require_db("neo4j")
    async def _record_user_interactions(
        self, 
        author_id: str, 
        mentioned_user_ids: List[str], 
        reply_to_user_id: Optional[str],
        guild_id: str
    ) -> None:
        """Record user-to-user interactions (mentions and replies)."""
        # Combine mentions and reply target
        interacted_with = set(mentioned_user_ids)
        if reply_to_user_id:
            interacted_with.add(reply_to_user_id)
        
        # Remove self-interactions
        interacted_with.discard(author_id)
        
        if not interacted_with:
            return
            
        query = """
        MATCH (author:User {id: $author_id})
        MATCH (p:Planet {id: $guild_id})
        UNWIND $target_ids as target_id
        MATCH (target:User {id: target_id})
        MERGE (author)-[r:INTERACTS_WITH]->(target)
        ON CREATE SET r.count = 1, r.first_seen = datetime(), r.planets = [$guild_id]
        ON MATCH SET r.count = r.count + 1, r.last_seen = datetime(),
                     r.planets = CASE WHEN $guild_id IN r.planets THEN r.planets ELSE r.planets + $guild_id END
        """
        async with db_manager.neo4j_driver.session() as session:
            await session.run(
                query, 
                author_id=str(author_id), 
                target_ids=[str(uid) for uid in interacted_with],
                guild_id=str(guild_id)
            )

    @retry_db_operation()
    @require_db("redis")
    async def _track_activity_hour(self, guild_id: str) -> None:
        """Track the current hour for peak activity learning."""
        # Use Redis to track hourly activity counts
        current_hour = datetime.now().hour
        key = f"universe:planet:{guild_id}:activity_hours"
        
        try:
            # Increment the count for this hour
            await self._cache.hincrby(key, str(current_hour), 1)
            # Set expiry to 30 days (recalculate monthly)
            await self._cache.expire(key, 60 * 60 * 24 * 30)
        except Exception as e:
            logger.debug(f"Failed to track activity hour: {e}")

    @require_db("redis", default_return=[])
    async def get_planet_peak_hours(self, guild_id: str) -> List[int]:
        """Get the top 3 peak activity hours for a planet."""
        try:
            key = f"universe:planet:{guild_id}:activity_hours"
            hour_counts = await self._cache.hgetall(key)
            
            if not hour_counts:
                return []
                
            # Sort by count descending, return top 3 hours
            sorted_hours = sorted(
                [(int(h), int(c)) for h, c in hour_counts.items()],
                key=lambda x: x[1],
                reverse=True
            )
            return [h for h, _ in sorted_hours[:3]]
        except Exception as e:
            logger.debug(f"Failed to get peak hours: {e}")
            return []

    @retry_db_operation()
    async def get_planet_topics(self, guild_id: str, limit: int = 10) -> List[dict]:
        """Get the most discussed topics on a planet."""
        if not db_manager.neo4j_driver: return []
        
        query = """
        MATCH (p:Planet {id: $guild_id})-[r:HAS_TOPIC]->(t:Topic)
        RETURN t.name as name, r.count as count
        ORDER BY r.count DESC
        LIMIT $limit
        """
        async with db_manager.neo4j_driver.session() as session:
            result = await session.run(query, guild_id=str(guild_id), limit=limit)
            return [{"name": r["name"], "count": r["count"]} for r in await result.data()]

    @retry_db_operation()
    async def get_user_interactions(self, user_id: str, guild_id: Optional[str] = None, limit: int = 5) -> List[dict]:
        """Get users that a user frequently interacts with."""
        if not db_manager.neo4j_driver: return []
        
        if guild_id:
            query = """
            MATCH (u:User {id: $user_id})-[r:INTERACTS_WITH]->(other:User)
            WHERE $guild_id IN r.planets
            RETURN other.id as user_id, r.count as interaction_count
            ORDER BY r.count DESC
            LIMIT $limit
            """
            params = {"user_id": str(user_id), "guild_id": str(guild_id), "limit": limit}
        else:
            query = """
            MATCH (u:User {id: $user_id})-[r:INTERACTS_WITH]->(other:User)
            RETURN other.id as user_id, r.count as interaction_count
            ORDER BY r.count DESC
            LIMIT $limit
            """
            params = {"user_id": str(user_id), "limit": limit}
            
        async with db_manager.neo4j_driver.session() as session:
            result = await session.run(query, **params)
            return [{"user_id": r["user_id"], "count": r["interaction_count"]} for r in await result.data()]

    # ============ Phase 3: Building Relationships ============
    
    @retry_db_operation()
    async def increment_familiarity(
        self, 
        character_name: str, 
        user_id: str, 
        guild_id: Optional[str] = None,
        interaction_quality: int = 1
    ) -> None:
        """
        Increment the familiarity between a character (bot) and user.
        
        Called after each meaningful conversation. Familiarity grows organically
        through repeated interactions across planets.
        
        Args:
            character_name: Bot character name (e.g., "elena")
            user_id: Discord user ID
            guild_id: Optional guild where interaction happened
            interaction_quality: Quality multiplier (1=normal, 2=high engagement)
        """
        if not db_manager.neo4j_driver: return
        
        query = """
        MERGE (c:Character {name: $character_name})
        MERGE (u:User {id: $user_id})
        MERGE (c)-[r:KNOWS_USER]->(u)
        ON CREATE SET 
            r.familiarity = $quality,
            r.interaction_count = 1,
            r.first_met = datetime(),
            r.planets_shared = CASE WHEN $guild_id IS NOT NULL THEN [$guild_id] ELSE [] END
        ON MATCH SET 
            r.familiarity = r.familiarity + $quality,
            r.interaction_count = r.interaction_count + 1,
            r.last_interaction = datetime(),
            r.planets_shared = CASE 
                WHEN $guild_id IS NOT NULL AND NOT $guild_id IN r.planets_shared 
                THEN r.planets_shared + $guild_id 
                ELSE r.planets_shared 
            END
        """
        async with db_manager.neo4j_driver.session() as session:
            await session.run(
                query, 
                character_name=character_name.lower(),
                user_id=str(user_id),
                guild_id=str(guild_id) if guild_id else None,
                quality=interaction_quality
            )

    @retry_db_operation()
    async def add_user_trait(
        self, 
        user_id: str, 
        trait: str, 
        category: str = "interest",
        learned_by: Optional[str] = None,
        confidence: float = 0.7
    ) -> None:
        """
        Add a trait to a user's profile in the universe.
        
        Traits are shareable characteristics that can be seen by other bots
        (respecting privacy settings). They're aggregated from fact extraction.
        
        Args:
            user_id: Discord user ID
            trait: The trait name (e.g., "astronomy", "dog lover")
            category: Type of trait - "interest", "personality", "fact"
            learned_by: Character that learned this (for attribution)
            confidence: How confident we are in this trait (0-1)
        """
        if not db_manager.neo4j_driver: return
        
        # Normalize trait name
        trait = trait.lower().strip()
        if len(trait) < 2 or len(trait) > 50:
            return
        
        query = """
        MERGE (u:User {id: $user_id})
        MERGE (t:Trait {name: $trait})
        ON CREATE SET t.category = $category, t.created_at = datetime()
        MERGE (u)-[r:HAS_TRAIT]->(t)
        ON CREATE SET 
            r.confidence = $confidence,
            r.learned_by = $learned_by,
            r.first_seen = datetime(),
            r.mention_count = 1
        ON MATCH SET 
            r.confidence = CASE WHEN $confidence > r.confidence THEN $confidence ELSE r.confidence END,
            r.last_seen = datetime(),
            r.mention_count = r.mention_count + 1
        """
        async with db_manager.neo4j_driver.session() as session:
            await session.run(
                query,
                user_id=str(user_id),
                trait=trait,
                category=category,
                learned_by=learned_by,
                confidence=confidence
            )

    @retry_db_operation()
    async def get_user_traits(self, user_id: str, limit: int = 10) -> List[dict]:
        """Get traits associated with a user."""
        if not db_manager.neo4j_driver: return []
        
        query = """
        MATCH (u:User {id: $user_id})-[r:HAS_TRAIT]->(t:Trait)
        RETURN t.name as trait, t.category as category, r.confidence as confidence, r.mention_count as mentions
        ORDER BY r.confidence DESC, r.mention_count DESC
        LIMIT $limit
        """
        async with db_manager.neo4j_driver.session() as session:
            result = await session.run(query, user_id=str(user_id), limit=limit)
            return [dict(r) for r in await result.data()]

    @retry_db_operation()
    async def get_character_knowledge_of_user(self, character_name: str, user_id: str) -> Optional[dict]:
        """
        Get what a specific character knows about a user.
        
        Returns familiarity level, shared planets, and interaction history.
        """
        if not db_manager.neo4j_driver: return None
        
        query = """
        MATCH (c:Character {name: $character_name})-[r:KNOWS_USER]->(u:User {id: $user_id})
        OPTIONAL MATCH (u)-[t:HAS_TRAIT]->(trait:Trait)
        RETURN r.familiarity as familiarity, 
               r.interaction_count as interactions,
               r.planets_shared as planets,
               r.first_met as first_met,
               collect(DISTINCT {name: trait.name, category: trait.category, confidence: t.confidence})[0..5] as top_traits
        """
        async with db_manager.neo4j_driver.session() as session:
            result = await session.run(
                query, 
                character_name=character_name.lower(), 
                user_id=str(user_id)
            )
            record = await result.single()
            if record:
                return dict(record)
            return None

    @retry_db_operation()
    async def get_cross_bot_knowledge(self, user_id: str, exclude_character: Optional[str] = None) -> List[dict]:
        """
        Get what OTHER bots know about this user (for cross-bot sharing).
        
        This enables "Elena mentioned you're into astronomy" type interactions.
        Respects privacy settings (checked by caller).
        """
        if not db_manager.neo4j_driver: return []
        
        query = """
        MATCH (c:Character)-[r:KNOWS_USER]->(u:User {id: $user_id})
        WHERE c.name <> $exclude_character OR $exclude_character IS NULL
        RETURN c.name as character, 
               r.familiarity as familiarity,
               r.interaction_count as interactions,
               r.planets_shared as planets
        ORDER BY r.familiarity DESC
        LIMIT 5
        """
        async with db_manager.neo4j_driver.session() as session:
            result = await session.run(
                query, 
                user_id=str(user_id),
                exclude_character=exclude_character.lower() if exclude_character else None
            )
            return [dict(r) for r in await result.data()]

    async def build_relationship_context(
        self, 
        character_name: str, 
        user_id: str,
        include_cross_bot: bool = True
    ) -> str:
        """
        Build a natural language context about the relationship for the LLM.
        
        This is called by the context builder to inject relationship awareness
        into the system prompt.
        """
        lines = []
        
        # 1. What this character knows about the user
        knowledge = await self.get_character_knowledge_of_user(character_name, user_id)
        if knowledge and knowledge.get("familiarity"):
            familiarity = knowledge["familiarity"]
            interactions = knowledge.get("interactions", 0)
            
            # Convert familiarity to human-readable level
            if familiarity >= 50:
                level = "very well (close friend)"
            elif familiarity >= 20:
                level = "fairly well (regular)"
            elif familiarity >= 5:
                level = "somewhat (occasional chats)"
            else:
                level = "a little (recent acquaintance)"
            
            lines.append(f"You know this user {level}. You've had {interactions} conversations.")
            
            # Add traits
            if knowledge.get("top_traits"):
                traits = [t["name"] for t in knowledge["top_traits"] if t.get("name")]
                if traits:
                    lines.append(f"You know they're interested in: {', '.join(traits)}")
        
        # 2. What other bots know (cross-bot knowledge)
        if include_cross_bot:
            other_knowledge = await self.get_cross_bot_knowledge(user_id, exclude_character=character_name)
            if other_knowledge:
                other_bots = [k["character"] for k in other_knowledge if k.get("familiarity", 0) >= 5]
                if other_bots:
                    lines.append(f"Other travelers who know this user: {', '.join(other_bots)}")
        
        return "\n".join(lines) if lines else ""

    @retry_db_operation()
    async def get_universe_overview(self) -> dict:
        """
        Get a comprehensive overview of the entire universe.
        
        Returns aggregated data about ALL active planets, channels, topics, 
        and inhabitants. Useful for cross-universe awareness queries like
        "what's happening across all planets?" or "tell elena what you see everywhere".
        
        Returns:
            dict with keys:
                - planet_count: Total number of active planets
                - planets: List of planet summaries (name, channels, inhabitant_count, top_topics)
                - total_inhabitants: Unique user count across universe
                - top_universal_topics: Most discussed topics across all planets
        """
        if not db_manager.neo4j_driver:
            return {
                "error": "Universe tracking unavailable (Neo4j not connected)",
                "planet_count": 0,
                "planets": [],
                "total_inhabitants": 0,
                "top_universal_topics": []
            }
        
        try:
            # Query 1: Get all active planets with basic stats
            planet_query = """
            MATCH (p:Planet {active: true})
            OPTIONAL MATCH (p)-[:HAS_CHANNEL]->(c:Channel)
            OPTIONAL MATCH (u:User)-[:ON_PLANET]->(p)
            WITH p, 
                 count(DISTINCT c) as channel_count,
                 collect(DISTINCT c.name)[0..10] as channels,
                 count(DISTINCT u) as inhabitant_count
            RETURN p.id as id, 
                   p.name as name, 
                   channel_count, 
                   channels,
                   inhabitant_count
            ORDER BY inhabitant_count DESC
            """
            
            # Query 2: Get top topics for each planet (run separately to avoid cartesian explosion)
            topic_query = """
            MATCH (p:Planet {active: true})-[r:HAS_TOPIC]->(t:Topic)
            WITH p.id as planet_id, t.name as topic, r.count as count
            ORDER BY count DESC
            WITH planet_id, collect({topic: topic, count: count})[0..5] as topics
            RETURN planet_id, topics
            """
            
            # Query 3: Get universal topics across all planets
            universal_topics_query = """
            MATCH (p:Planet {active: true})-[r:HAS_TOPIC]->(t:Topic)
            WITH t.name as topic, sum(r.count) as total_mentions
            RETURN topic, total_mentions
            ORDER BY total_mentions DESC
            LIMIT 10
            """
            
            # Query 4: Get unique inhabitant count
            inhabitant_query = """
            MATCH (u:User)-[:ON_PLANET]->(p:Planet {active: true})
            RETURN count(DISTINCT u) as total_inhabitants
            """
            
            async with db_manager.neo4j_driver.session() as session:
                # Execute all queries in parallel
                planet_result = await session.run(planet_query)
                planet_records = await planet_result.data()
                
                topic_result = await session.run(topic_query)
                topic_records = await topic_result.data()
                
                universal_result = await session.run(universal_topics_query)
                universal_records = await universal_result.data()
                
                inhabitant_result = await session.run(inhabitant_query)
                inhabitant_record = await inhabitant_result.single()
            
            # Build topic lookup map
            topics_by_planet = {r["planet_id"]: r["topics"] for r in topic_records}
            
            # Build planet summaries
            planets = []
            for p in planet_records:
                planet_id = p["id"]
                planet_topics = topics_by_planet.get(planet_id, [])
                
                planets.append({
                    "id": planet_id,
                    "name": p["name"],
                    "channel_count": p["channel_count"],
                    "channels": p["channels"],
                    "inhabitant_count": p["inhabitant_count"],
                    "top_topics": [t["topic"] for t in planet_topics]
                })
            
            return {
                "planet_count": len(planets),
                "planets": planets,
                "total_inhabitants": inhabitant_record["total_inhabitants"] if inhabitant_record else 0,
                "top_universal_topics": [r["topic"] for r in universal_records]
            }
            
        except Exception as e:
            logger.error(f"Failed to get universe overview: {e}")
            return {
                "error": f"Failed to query universe: {str(e)}",
                "planet_count": 0,
                "planets": [],
                "total_inhabitants": 0,
                "top_universal_topics": []
            }


universe_manager = UniverseManager()
