#!/usr/bin/env python3
"""
Graph Enrichment Cleanup Script

Cleans up excessive edges created by aggressive graph enrichment.
Run this to remove the LINKED_TO and RELATED_TO edge explosion.

Usage:
    python scripts/cleanup_graph_enrichment.py --dry-run   # Preview what will be deleted
    python scripts/cleanup_graph_enrichment.py             # Actually delete

The script:
1. Removes all LINKED_TO edges (entity-entity, the main culprit)
2. Removes RELATED_TO edges with low strength (topic-topic noise)
3. Optionally removes orphaned Entity/Topic nodes with no edges
"""

import asyncio
import argparse
from loguru import logger


async def cleanup_graph(dry_run: bool = True, remove_orphans: bool = True):
    """Clean up excessive graph enrichment edges."""
    
    # Import here to avoid circular imports and ensure settings are loaded
    import sys
    sys.path.insert(0, '/Users/markcastillo/git/whisperengine-v2')
    
    from src_v2.core.database import db_manager
    from src_v2.config.settings import settings
    
    logger.info(f"Connecting to Neo4j at {settings.NEO4J_URL}...")
    
    # Initialize database connections
    await db_manager.connect_all()
    
    if not db_manager.neo4j_driver:
        logger.error("Failed to connect to Neo4j")
        return
    
    async with db_manager.neo4j_driver.session() as session:
        
        # 1. Count LINKED_TO edges (the main problem)
        result = await session.run(
            "MATCH ()-[r:LINKED_TO]->() RETURN count(r) as count"
        )
        record = await result.single()
        linked_to_count = record['count'] if record else 0
        logger.info(f"Found {linked_to_count:,} LINKED_TO edges")
        
        # 2. Count low-strength RELATED_TO edges
        result = await session.run(
            "MATCH ()-[r:RELATED_TO]->() WHERE r.strength < 5 RETURN count(r) as count"
        )
        record = await result.single()
        weak_related_count = record['count'] if record else 0
        logger.info(f"Found {weak_related_count:,} weak RELATED_TO edges (strength < 5)")
        
        # 3. Count orphaned Entity nodes
        result = await session.run(
            """
            MATCH (e:Entity)
            WHERE NOT (e)--()
            RETURN count(e) as count
            """
        )
        record = await result.single()
        orphan_entity_count = record['count'] if record else 0
        logger.info(f"Found {orphan_entity_count:,} orphaned Entity nodes")
        
        # 4. Count orphaned Topic nodes
        result = await session.run(
            """
            MATCH (t:Topic)
            WHERE NOT (t)--()
            RETURN count(t) as count
            """
        )
        record = await result.single()
        orphan_topic_count = record['count'] if record else 0
        logger.info(f"Found {orphan_topic_count:,} orphaned Topic nodes")
        
        if dry_run:
            logger.info("\n--- DRY RUN - No changes made ---")
            logger.info(f"Would delete {linked_to_count:,} LINKED_TO edges")
            logger.info(f"Would delete {weak_related_count:,} weak RELATED_TO edges")
            if remove_orphans:
                logger.info(f"Would delete {orphan_entity_count:,} orphaned Entity nodes")
                logger.info(f"Would delete {orphan_topic_count:,} orphaned Topic nodes")
            logger.info("\nRun without --dry-run to actually delete.")
            return
        
        # Actually delete
        logger.info("\n--- DELETING ---")
        
        # Delete LINKED_TO edges in batches
        if linked_to_count > 0:
            logger.info("Deleting LINKED_TO edges (in batches of 10000)...")
            deleted = 0
            while True:
                result = await session.run(
                    """
                    MATCH ()-[r:LINKED_TO]->()
                    WITH r LIMIT 10000
                    DELETE r
                    RETURN count(r) as deleted
                    """
                )
                record = await result.single()
                batch_deleted = record['deleted'] if record else 0
                if batch_deleted == 0:
                    break
                deleted += batch_deleted
                logger.info(f"  Deleted {deleted:,} / {linked_to_count:,} LINKED_TO edges...")
            logger.info(f"✓ Deleted {deleted:,} LINKED_TO edges")
        
        # Delete weak RELATED_TO edges
        if weak_related_count > 0:
            logger.info("Deleting weak RELATED_TO edges (strength < 5)...")
            result = await session.run(
                """
                MATCH ()-[r:RELATED_TO]->()
                WHERE r.strength < 5
                DELETE r
                RETURN count(r) as deleted
                """
            )
            record = await result.single()
            deleted = record['deleted'] if record else 0
            logger.info(f"✓ Deleted {deleted:,} weak RELATED_TO edges")
        
        if remove_orphans:
            # Delete orphaned Entity nodes
            if orphan_entity_count > 0:
                logger.info("Deleting orphaned Entity nodes...")
                result = await session.run(
                    """
                    MATCH (e:Entity)
                    WHERE NOT (e)--()
                    DELETE e
                    RETURN count(e) as deleted
                    """
                )
                record = await result.single()
                deleted = record['deleted'] if record else 0
                logger.info(f"✓ Deleted {deleted:,} orphaned Entity nodes")
            
            # Delete orphaned Topic nodes
            if orphan_topic_count > 0:
                logger.info("Deleting orphaned Topic nodes...")
                result = await session.run(
                    """
                    MATCH (t:Topic)
                    WHERE NOT (t)--()
                    DELETE t
                    RETURN count(t) as deleted
                    """
                )
                record = await result.single()
                deleted = record['deleted'] if record else 0
                logger.info(f"✓ Deleted {deleted:,} orphaned Topic nodes")
        
        # Final stats
        result = await session.run(
            "MATCH ()-[r]->() RETURN type(r) as type, count(r) as count ORDER BY count DESC LIMIT 10"
        )
        records = [r async for r in result]
        logger.info("\n--- Final Graph Stats ---")
        for record in records:
            logger.info(f"  {record['type']}: {record['count']:,}")
    
    await db_manager.disconnect_all()
    logger.info("\n✓ Cleanup complete!")


def main():
    parser = argparse.ArgumentParser(
        description="Clean up excessive graph enrichment edges",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Preview what will be deleted
    python scripts/cleanup_graph_enrichment.py --dry-run
    
    # Actually delete (CAUTION!)
    python scripts/cleanup_graph_enrichment.py
    
    # Delete edges but keep orphaned nodes
    python scripts/cleanup_graph_enrichment.py --keep-orphans
        """
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview what will be deleted without making changes'
    )
    parser.add_argument(
        '--keep-orphans',
        action='store_true',
        help='Keep orphaned Entity/Topic nodes (only delete edges)'
    )
    
    args = parser.parse_args()
    
    asyncio.run(cleanup_graph(
        dry_run=args.dry_run,
        remove_orphans=not args.keep_orphans
    ))


if __name__ == "__main__":
    main()
