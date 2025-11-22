import asyncio
import yaml
import sys
from pathlib import Path
from loguru import logger

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src_v2.core.database import db_manager
from src_v2.config.settings import settings

async def ingest_facts(character_name: str, yaml_path: str):
    # 1. Connect to Neo4j
    await db_manager.connect_neo4j()
    
    if not db_manager.neo4j_driver:
        logger.error("Failed to connect to Neo4j")
        return

    # 2. Read YAML
    try:
        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to read YAML file: {e}")
        return

    facts = data.get("facts", [])
    logger.info(f"Found {len(facts)} facts for {character_name}")

    # 3. Ingest into Neo4j
    async with db_manager.neo4j_driver.session() as session:
        # Create Character Node
        await session.run(
            "MERGE (c:Character {name: $name})",
            name=character_name
        )
        
        for fact in facts:
            predicate = fact["predicate"]
            obj = fact["object"]
            
            # Create Entity and Relationship
            # We use MERGE to avoid duplicates
            query = """
            MATCH (c:Character {name: $name})
            MERGE (e:Entity {name: $obj})
            MERGE (c)-[r:FACT {predicate: $predicate}]->(e)
            """
            await session.run(query, name=character_name, obj=obj, predicate=predicate)
            logger.info(f"Ingested: ({character_name}) -[{predicate}]-> ({obj})")

    logger.info("Ingestion complete.")
    await db_manager.neo4j_driver.close()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python ingest_character_facts.py <character_name> <path_to_yaml>")
        sys.exit(1)
    
    char_name = sys.argv[1]
    yaml_file = sys.argv[2]
    
    asyncio.run(ingest_facts(char_name, yaml_file))
