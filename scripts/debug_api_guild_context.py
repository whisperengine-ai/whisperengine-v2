import os
# Force localhost for local debugging
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["NEO4J_URL"] = "bolt://localhost:7687"
os.environ["INFLUXDB_URL"] = "http://localhost:8086"

import asyncio
import sys
from loguru import logger

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src_v2.core.database import db_manager
from src_v2.config.settings import settings

async def main():
    print("Connecting to Neo4j only...")
    # Manually connect only to Neo4j to avoid Qdrant/Postgres connection issues if running outside docker network
    # But wait, db_manager.connect_all() uses settings.
    # If I am running this from the terminal, I might need to use localhost ports if exposed.
    
    # Let's try to connect just Neo4j
    await db_manager.connect_neo4j()
    
    if not db_manager.neo4j_driver:
        print("Neo4j not available.")
        return

    guild_id = "api_guild"
    print(f"Checking context for guild_id: {guild_id}")

    async with db_manager.neo4j_driver.session() as session:
        # 1. Check if planet exists
        result = await session.run("MATCH (p:Planet {id: $id}) RETURN p", id=guild_id)
        record = await result.single()
        if record:
            print(f"Planet '{guild_id}' exists: {record['p']}")
        else:
            print(f"Planet '{guild_id}' does NOT exist.")

        # 2. Check topics
        query = """
        MATCH (p:Planet {id: $guild_id})-[r:HAS_TOPIC]->(t:Topic)
        RETURN t.name as name, r.count as count
        ORDER BY r.count DESC
        LIMIT 10
        """
        result = await session.run(query, guild_id=guild_id)
        topics = await result.data()
        print(f"\nTopics for '{guild_id}':")
        for t in topics:
            print(f"- {t['name']} (count: {t['count']})")

        # 3. Check inhabitants
        query = """
        MATCH (u:User)-[:ON_PLANET]->(p:Planet {id: $guild_id})
        RETURN count(u) as count
        """
        result = await session.run(query, guild_id=guild_id)
        count = await result.single()
        print(f"\nInhabitant count: {count['count']}")

    await db_manager.close_all()

if __name__ == "__main__":
    asyncio.run(main())
