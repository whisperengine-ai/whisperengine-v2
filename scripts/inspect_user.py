import asyncio
import sys
import os
import argparse
from pathlib import Path

# Add root to path
sys.path.append(os.getcwd())

# Mock settings if needed or rely on env vars
# We need to load settings AFTER setting env var
# Imports moved to main block

async def inspect(user_id: str, bot_name: str, fix: bool, reset_trust: bool = False):
    # Import here to ensure env vars are set
    from src_v2.core.database import db_manager
    from src_v2.knowledge.manager import knowledge_manager
    from src_v2.evolution.trust import trust_manager
    
    print(f"🔍 Inspecting data for User ID: {user_id} (Bot: {bot_name})")
    
    # Connect to DBs
    try:
        await db_manager.connect_postgres()
        await db_manager.connect_neo4j()
    except Exception as e:
        print(f"❌ Failed to connect to databases: {e}")
        return

    # 1. Check Trust/Identity
    print("\n--- 💙 Relationship (Postgres) ---")
    try:
        if reset_trust:
            print("   -> RESETTING trust and preferences...")
            await trust_manager.clear_user_preferences(user_id, bot_name)
            print("   -> Reset complete.")

        rel = await trust_manager.get_relationship_level(user_id, bot_name)
        print(f"Trust Score: {rel.get('trust_score')}")
        print(f"Level: {rel.get('level_label')}")
        print(f"Preferences: {rel.get('preferences')}")
        
        # Check Chat History Count
        if db_manager.postgres_pool:
            async with db_manager.postgres_pool.acquire() as conn:
                count = await conn.fetchval("SELECT COUNT(*) FROM v2_chat_history WHERE user_id = $1 AND character_name = $2", user_id, bot_name)
                print(f"Chat History Rows: {count}")
                
                if count > 0:
                    print("Latest 3 messages:")
                    rows = await conn.fetch("SELECT role, content, timestamp FROM v2_chat_history WHERE user_id = $1 AND character_name = $2 ORDER BY timestamp DESC LIMIT 3", user_id, bot_name)
                    for r in rows:
                        print(f"[{r['timestamp']}] {r['role']}: {r['content'][:50]}...")

    except Exception as e:
        print(f"Error fetching relationship/history: {e}")

    # 2. Check Knowledge (Neo4j)
    print("\n--- 🧠 Knowledge Graph (Neo4j) ---")
    try:
        if db_manager.neo4j_driver:
            # We need to access the driver directly for raw queries to see predicates
            async with db_manager.neo4j_driver.session() as session:
                query = """
                MATCH (u:User {id: $user_id})-[r:FACT]->(o:Entity)
                RETURN r.predicate, o.name
                """
                result = await session.run(query, user_id=user_id)
                records = await result.data()
                
                for r in records:
                    pred = r['r.predicate']
                    val = r['o.name']
                    print(f"- {pred}: {val}")
                    
                    if pred == "HAS_NAME" or pred == "IS_NAMED":
                        if fix:
                            print(f"   -> DELETING name fact: {val}")
                            del_query = "MATCH (u:User {id: $user_id})-[r:FACT]->(o:Entity {name: $name}) WHERE r.predicate = $pred DELETE r"
                            await session.run(del_query, user_id=user_id, name=val, pred=pred)
                            print("   -> Deleted.")

                if not records:
                    print("No facts found.")
        else:
            print("Neo4j driver not available.")
                
    except Exception as e:
        print(f"Error fetching knowledge: {e}")

    # Close connections
    if db_manager.postgres_pool:
        await db_manager.postgres_pool.close()
    if db_manager.neo4j_driver:
        await db_manager.neo4j_driver.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspect user data")
    parser.add_argument("bot_name", help="Name of the bot (e.g. nottaylor)")
    parser.add_argument("user_id", help="Discord User ID")
    parser.add_argument("--fix", action="store_true", help="Delete ALL 'HAS_NAME' facts for this user (to reset identity)")
    parser.add_argument("--reset-trust", action="store_true", help="Reset trust score and preferences to 0")
    
    args = parser.parse_args()
    
    # Set bot name for config BEFORE importing settings
    os.environ["DISCORD_BOT_NAME"] = args.bot_name
    
    asyncio.run(inspect(args.user_id, args.bot_name, args.fix, args.reset_trust))
