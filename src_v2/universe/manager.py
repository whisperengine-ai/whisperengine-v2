from typing import Optional, List
from datetime import datetime
from loguru import logger
from src_v2.core.database import db_manager, retry_db_operation


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
        
    @property
    def embedding_service(self):
        """Lazy load embedding service to avoid circular imports."""
        if self._embedding_service is None:
            from src_v2.memory.embeddings import EmbeddingService
            self._embedding_service = EmbeddingService()
        return self._embedding_service

    async def initialize(self):
        """Initialize constraints for the Universe graph."""
        if not db_manager.neo4j_driver:
            logger.warning("Neo4j driver not available. Universe features disabled.")
            return

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
    async def register_planet(self, guild_id: str, name: str):
        """Register or update a Discord server as a Planet."""
        if not db_manager.neo4j_driver: return

        query = """
        MERGE (p:Planet {id: $guild_id})
        SET p.name = $name, p.last_seen = datetime(), p.active = true
        RETURN p
        """
        async with db_manager.neo4j_driver.session() as session:
            await session.run(query, guild_id=str(guild_id), name=name)

    @retry_db_operation()
    async def register_channel(self, guild_id: str, channel_id: str, name: str, channel_type: str):
        """Register a channel on a planet."""
        if not db_manager.neo4j_driver: return

        query = """
        MATCH (p:Planet {id: $guild_id})
        MERGE (c:Channel {id: $channel_id})
        SET c.name = $name, c.type = $channel_type, c.last_seen = datetime()
        MERGE (p)-[:HAS_CHANNEL]->(c)
        """
        async with db_manager.neo4j_driver.session() as session:
            await session.run(query, guild_id=str(guild_id), channel_id=str(channel_id), name=name, channel_type=channel_type)

    @retry_db_operation()
    async def record_presence(self, user_id: str, guild_id: str):
        """Record that a user is on a planet."""
        if not db_manager.neo4j_driver: return

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
    async def mark_planet_inactive(self, guild_id: str):
        """Mark a planet as inactive (bot removed)."""
        if not db_manager.neo4j_driver: return

        query = """
        MATCH (p:Planet {id: $guild_id})
        SET p.active = false, p.left_at = datetime()
        """
        async with db_manager.neo4j_driver.session() as session:
            await session.run(query, guild_id=str(guild_id))

    @retry_db_operation()
    async def remove_inhabitant(self, user_id: str, guild_id: str):
        """Remove a user's presence from a planet."""
        if not db_manager.neo4j_driver: return

        query = """
        MATCH (u:User {id: $user_id})-[r:ON_PLANET]->(p:Planet {id: $guild_id})
        DELETE r
        """
        async with db_manager.neo4j_driver.session() as session:
            await session.run(query, user_id=str(user_id), guild_id=str(guild_id))

    # ============ Phase 2: Learning to Listen ============
    
    async def observe_message(
        self, 
        guild_id: str, 
        channel_id: str, 
        user_id: str,
        message_content: str,
        mentioned_user_ids: List[str],
        reply_to_user_id: Optional[str] = None
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
        """
        if not db_manager.neo4j_driver:
            return
            
        # Skip very short messages (greetings, reactions, etc.)
        if len(message_content.strip()) < 10:
            return
            
        try:
            # Run observations in parallel (non-blocking)
            import asyncio
            await asyncio.gather(
                self._update_user_activity(user_id, guild_id, channel_id),
                self._extract_and_link_topics(guild_id, message_content),
                self._record_user_interactions(user_id, mentioned_user_ids, reply_to_user_id, guild_id),
                self._track_activity_hour(guild_id),
                return_exceptions=True  # Don't fail on individual errors
            )
        except Exception as e:
            # Log but don't raise - observation is non-critical
            logger.debug(f"Universe observation error (non-fatal): {e}")

    @retry_db_operation()
    async def _update_user_activity(self, user_id: str, guild_id: str, channel_id: str) -> None:
        """Update user's last seen timestamp and activity on planet/channel."""
        if not db_manager.neo4j_driver: return
        
        query = """
        MERGE (u:User {id: $user_id})
        SET u.last_seen_at = datetime()
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
            await session.run(query, user_id=str(user_id), guild_id=str(guild_id), channel_id=str(channel_id))

    async def _extract_and_link_topics(self, guild_id: str, message_content: str) -> None:
        """Extract topics from message and link them to the planet."""
        if not db_manager.neo4j_driver: return
        
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
    async def _link_topics_to_planet(self, guild_id: str, topics: List[str]) -> None:
        """Create or update Topic nodes and link them to the planet."""
        if not db_manager.neo4j_driver or not topics: return
        
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
    async def _record_user_interactions(
        self, 
        author_id: str, 
        mentioned_user_ids: List[str], 
        reply_to_user_id: Optional[str],
        guild_id: str
    ) -> None:
        """Record user-to-user interactions (mentions and replies)."""
        if not db_manager.neo4j_driver: return
        
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
    async def _track_activity_hour(self, guild_id: str) -> None:
        """Track the current hour for peak activity learning."""
        if not db_manager.redis_client: return
        
        # Use Redis to track hourly activity counts
        current_hour = datetime.now().hour
        key = f"universe:planet:{guild_id}:activity_hours"
        
        try:
            # Increment the count for this hour
            await db_manager.redis_client.hincrby(key, str(current_hour), 1)
            # Set expiry to 30 days (recalculate monthly)
            await db_manager.redis_client.expire(key, 60 * 60 * 24 * 30)
        except Exception as e:
            logger.debug(f"Failed to track activity hour: {e}")

    async def get_planet_peak_hours(self, guild_id: str) -> List[int]:
        """Get the top 3 peak activity hours for a planet."""
        if not db_manager.redis_client: return []
        
        try:
            key = f"universe:planet:{guild_id}:activity_hours"
            hour_counts = await db_manager.redis_client.hgetall(key)
            
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


universe_manager = UniverseManager()
