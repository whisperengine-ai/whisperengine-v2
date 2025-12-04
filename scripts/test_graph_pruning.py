import asyncio
import sys
import os
import argparse
from pathlib import Path

# Add root to path
sys.path.append(os.getcwd())

async def main():
    parser = argparse.ArgumentParser(description="Test Knowledge Graph Pruning")
    parser.add_argument("bot_name", help="Name of the bot (e.g., elena)")
    parser.add_argument("--force", action="store_true", help="Actually delete items (default is dry-run)")
    args = parser.parse_args()

    # Set bot name in env for settings to pick up
    os.environ["DISCORD_BOT_NAME"] = args.bot_name
    
    # Override Neo4j URL for local execution
    if "NEO4J_URL" not in os.environ:
        os.environ["NEO4J_URL"] = "bolt://localhost:7687"
    
    from src_v2.core.database import db_manager
    from src_v2.knowledge.pruning import KnowledgeGraphPruner
    from src_v2.config.settings import settings

    print(f"🔍 Testing Graph Pruning for Bot: {args.bot_name}")
    print(f"   Mode: {'REAL DELETION' if args.force else 'DRY RUN'}")
    
    # Connect to DBs
    try:
        await db_manager.connect_neo4j()
    except Exception as e:
        print(f"❌ Failed to connect to Neo4j: {e}")
        return

    pruner = KnowledgeGraphPruner(bot_name=args.bot_name)
    
    print("\n--- Configuration ---")
    print(f"Orphan Grace Days: {pruner.orphan_grace_days}")
    print(f"Stale Fact Days: {pruner.stale_fact_days}")
    print(f"Min Access Count: {pruner.min_access_count}")
    print(f"Min Confidence: {pruner.min_confidence}")
    
    print("\n--- Running Pruning ---")
    # Force dry_run unless --force is specified
    is_dry_run = not args.force
    
    stats = await pruner.run_full_prune(dry_run=is_dry_run)
    
    print("\n--- Results ---")
    print(f"Orphans Removed: {stats.orphans_removed}")
    print(f"Stale Facts Removed: {stats.stale_facts_removed}")
    print(f"Duplicates Merged: {stats.duplicates_merged}")
    print(f"Low Confidence Removed: {stats.low_confidence_removed}")
    print(f"Total Nodes: {stats.total_nodes_before} -> {stats.total_nodes_after}")
    print(f"Total Edges: {stats.total_edges_before} -> {stats.total_edges_after}")
    print(f"Duration: {stats.duration_seconds:.2f}s")
    
    if stats.errors:
        print("\n❌ Errors:")
        for error in stats.errors:
            print(f"  - {error}")

    if is_dry_run and (stats.orphans_removed > 0 or stats.stale_facts_removed > 0):
        print("\n💡 To actually prune these items, run with --force")

if __name__ == "__main__":
    asyncio.run(main())
