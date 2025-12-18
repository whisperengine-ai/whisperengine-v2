#!/usr/bin/env python3
"""
Neo4j Cleanup Script

Simple utility to clean individual user data from Neo4j knowledge graph.

USAGE:
    # Show stats
    python scripts/cleanup_neo4j.py --stats
    
    # Preview what will be deleted for a user
    python scripts/cleanup_neo4j.py --user-id 629720700801777664
    
    # Clean specific user
    python scripts/cleanup_neo4j.py --user-id 629720700801777664 --execute
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def get_stats():
    """Show current Neo4j statistics."""
    from src_v2.core.database import db_manager
    
    await db_manager.connect_all()
    
    if not db_manager.neo4j_driver:
        print("ERROR: Neo4j not available")
        return
    
    print("\n" + "="*50)
    print("NEO4J STATISTICS")
    print("="*50)
    
    async with db_manager.neo4j_driver.session() as session:
        # Count nodes by label
        labels = ["User", "Character", "Entity", "Memory"]
        for label in labels:
            result = await session.run(f"MATCH (n:{label}) RETURN count(n) as count")
            data = await result.data()
            count = data[0]['count'] if data else 0
            print(f"  {label} nodes: {count}")
        
        # Count relationships
        result = await session.run("MATCH ()-[r:FACT]->() RETURN count(r) as count")
        data = await result.data()
        fact_count = data[0]['count'] if data else 0
        print(f"  FACT relationships: {fact_count}")
        
        # User facts breakdown
        result = await session.run("""
            MATCH (u:User)-[r:FACT]->()
            RETURN u.id as user_id, count(r) as facts
            ORDER BY facts DESC
            LIMIT 10
        """)
        data = await result.data()
        if data:
            print(f"\n  Top users by fact count:")
            for row in data:
                print(f"    User {row['user_id']}: {row['facts']} facts")
    
    await db_manager.disconnect_all()


async def cleanup(user_id: str, dry_run: bool = True):
    """
    Clean Neo4j data for a specific user.
    
    Args:
        user_id: specific user ID to clean
        dry_run: preview only, don't delete
    """
    from src_v2.core.database import db_manager
    
    await db_manager.connect_all()
    
    if not db_manager.neo4j_driver:
        print("ERROR: Neo4j not available")
        return
    
    print("\n" + "="*50)
    print(f"NEO4J CLEANUP - {'DRY RUN' if dry_run else 'EXECUTING'}")
    print("="*50)
    
    async with db_manager.neo4j_driver.session() as session:
        # Clean specific user
        count_query = """
            MATCH (u:User {id: $user_id})-[r:FACT]->()
            RETURN count(r) as count
        """
        result = await session.run(count_query, user_id=user_id)
        data = await result.data()
        count = data[0]['count'] if data else 0
        
        print(f"\n  User {user_id}: {count} facts")
        
        if not dry_run and count > 0:
            await session.run("""
                MATCH (u:User {id: $user_id})-[r:FACT]->()
                DELETE r
            """, user_id=user_id)
            # Delete user node with DETACH to remove any other relationships
            await session.run("""
                MATCH (u:User {id: $user_id})
                WHERE NOT (u)-[:FACT]->()
                DETACH DELETE u
            """, user_id=user_id)
            print(f"  ✅ Deleted {count} facts for user {user_id}")
        elif not dry_run and count == 0:
            print(f"  ℹ️  No facts to delete for user {user_id}")
    
    await db_manager.disconnect_all()
    
    if dry_run:
        print("\n" + "-"*50)
        print("DRY RUN - No changes made. Use --execute to apply.")
        print("-"*50)
    else:
        print("\n✅ Cleanup complete!")


async def main():
    parser = argparse.ArgumentParser(description="Neo4j User Cleanup Utility")
    parser.add_argument("--stats", action="store_true", help="Show statistics only")
    parser.add_argument("--user-id", type=str, help="Clean specific user (required for cleanup)")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Preview only (default)")
    parser.add_argument("--execute", action="store_true", help="Actually delete data")
    
    args = parser.parse_args()
    
    if args.stats:
        await get_stats()
    elif args.user_id:
        await cleanup(user_id=args.user_id, dry_run=not args.execute)
    else:
        await get_stats()
        print("\nUse --user-id <id> --execute to clean a specific user.")


if __name__ == "__main__":
    asyncio.run(main())
