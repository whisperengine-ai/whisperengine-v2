#!/usr/bin/env python3
"""
Backfill 'name' property on existing Memory nodes in Neo4j.

Background:
Memory nodes created before 2025-12-15 don't have a 'name' property,
which causes GraphWalker to fall back to using the UUID (vector_id) as
the name. This leaks UUIDs into dream/diary interpretations.

This script:
1. Finds all Memory nodes without a 'name' property
2. Creates a human-readable name from the content (first 50 chars)
3. Updates the node in place

Usage:
    python scripts/backfill_memory_names.py --dry-run  # Preview changes
    python scripts/backfill_memory_names.py            # Apply changes
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from src_v2.core.database import db_manager
from src_v2.config.settings import settings

logger.remove()
logger.add(sys.stderr, level="INFO")


async def backfill_memory_names(dry_run: bool = False) -> dict:
    """
    Backfill 'name' property on Memory nodes without one.
    
    Returns:
        dict with stats: found, updated, errors
    """
    stats = {
        "found": 0,
        "updated": 0,
        "errors": 0
    }
    
    # Connect to Neo4j
    await db_manager.connect_neo4j()
    
    if not db_manager.neo4j_driver:
        logger.error("Failed to connect to Neo4j")
        return stats
    
    try:
        async with db_manager.neo4j_driver.session() as session:
            # Find all Memory nodes without a 'name' property
            query = """
            MATCH (m:Memory)
            WHERE m.name IS NULL
            RETURN m.id as id, m.content as content
            """
            
            result = await session.run(query)
            records = await result.data()
            
            stats["found"] = len(records)
            logger.info(f"Found {stats['found']} Memory nodes without 'name' property")
            
            if dry_run:
                logger.info("[Dry Run] Would update the following nodes:")
                for record in records[:10]:  # Show first 10
                    memory_id = record["id"]
                    content = record["content"] or ""
                    name = content[:50].strip() if content else "memory"
                    if len(content) > 50:
                        name += "..."
                    logger.info(f"  {memory_id} -> \"{name}\"")
                if stats["found"] > 10:
                    logger.info(f"  ... and {stats['found'] - 10} more")
                return stats
            
            # Update each Memory node with a name
            update_query = """
            MATCH (m:Memory {id: $id})
            SET m.name = $name
            """
            
            for record in records:
                try:
                    memory_id = record["id"]
                    content = record["content"] or ""
                    
                    # Create human-readable name from content
                    name = content[:50].strip() if content else "memory"
                    if len(content) > 50:
                        name += "..."
                    
                    await session.run(update_query, id=memory_id, name=name)
                    stats["updated"] += 1
                    
                    if stats["updated"] % 100 == 0:
                        logger.info(f"Updated {stats['updated']}/{stats['found']} nodes...")
                        
                except Exception as e:
                    logger.error(f"Failed to update {memory_id}: {e}")
                    stats["errors"] += 1
            
            logger.info(f"Backfill complete: {stats['updated']} updated, {stats['errors']} errors")
    
    except Exception as e:
        logger.error(f"Backfill failed: {e}")
        stats["errors"] += 1
    
    finally:
        await db_manager.neo4j_driver.close()
    
    return stats


async def main():
    parser = argparse.ArgumentParser(description="Backfill Memory node names in Neo4j")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    args = parser.parse_args()
    
    logger.info("Starting Memory node name backfill...")
    if args.dry_run:
        logger.info("[DRY RUN MODE - No changes will be made]")
    
    stats = await backfill_memory_names(dry_run=args.dry_run)
    
    logger.info(f"\nBackfill Summary:")
    logger.info(f"  Found: {stats['found']}")
    logger.info(f"  Updated: {stats['updated']}")
    logger.info(f"  Errors: {stats['errors']}")
    
    if args.dry_run:
        logger.info("\nTo apply changes, run without --dry-run flag")


if __name__ == "__main__":
    asyncio.run(main())
