from typing import Optional, List
from loguru import logger
from src_v2.core.database import db_manager, retry_db_operation
from src_v2.config.settings import settings

class UniverseManager:
    def __init__(self):
        pass

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
        ]
        
        try:
            async with db_manager.neo4j_driver.session() as session:
                for query in queries:
                    await session.run(query)
            logger.info("Universe graph constraints initialized.")
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

universe_manager = UniverseManager()
