import asyncio
import uuid
import datetime
import time
from loguru import logger
from qdrant_client.models import PointStruct

from src_v2.memory.manager import memory_manager
from src_v2.memory.context_builder import context_builder
from src_v2.core.database import db_manager
from src_v2.config.settings import settings
from src_v2.memory.embeddings import EmbeddingService

# Override settings for local testing (running from host, not container)
settings.POSTGRES_URL = "postgresql://whisper:password@localhost:5432/whisperengine_v2"
settings.QDRANT_URL = "http://localhost:6333"
settings.NEO4J_URL = "bolt://localhost:7687"
settings.REDIS_URL = "redis://localhost:6379/0"
settings.INFLUXDB_URL = "http://localhost:8086"

# Setup logger
logger.add("tests_v2/test_advanced_memory.log", rotation="1 MB")

async def test_weighted_retrieval():
    print("\n=== Testing Weighted Retrieval (Episodes) ===")
    user_id = f"test_user_{uuid.uuid4().hex[:8]}"
    embedding_service = EmbeddingService()
    
    # We need to manually insert points to control timestamps for decay testing
    collection_name = memory_manager.collection_name
    
    # 1. Create Test Data
    # A: Recent (Today), Low Importance (1) -> Should be low score
    # B: Recent (Today), High Importance (10) -> Should be highest score
    # C: Old (30 days ago), High Importance (10) -> Should be decayed but still present
    
    now = datetime.datetime.now()
    old_date = now - datetime.timedelta(days=30)
    
    scenarios = [
        ("I ate a sandwich today.", 1, now),
        ("I am moving to Mars.", 10, now),
        ("I won the lottery last month.", 10, old_date)
    ]
    
    points = []
    for content, importance, ts in scenarios:
        vector = await embedding_service.embed_query_async(content)
        points.append(PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={
                "user_id": user_id,
                "content": content,
                "role": "human",
                "timestamp": ts.isoformat(),
                "importance_score": importance
            }
        ))
        
    await db_manager.qdrant_client.upsert(
        collection_name=collection_name,
        points=points
    )
    
    print("Waiting for Qdrant indexing...")
    await asyncio.sleep(2) 
    
    # 2. Search
    query = "important events"
    results = await memory_manager.search_memories(query, user_id, limit=10)
    
    print(f"\nQuery: '{query}'")
    print(f"{'Content':<30} | {'Score':<8} | {'Sem':<6} | {'Recency':<6} | {'Imp':<6}")
    print("-" * 70)
    
    for r in results:
        content = r['content'][:27] + "..." if len(r['content']) > 27 else r['content']
        print(f"{content:<30} | {r['score']:.4f}   | {r['semantic_score']:.4f} | {r['recency_multiplier']:.4f}   | {r.get('importance_multiplier', 0):.4f}")

    # Assertions
    # "Moving to Mars" (Recent + High Imp) should be #1
    if results and "Mars" in results[0]['content']:
        print("✅ SUCCESS: Recent High Importance memory ranked #1")
    else:
        print("❌ FAILURE: Recent High Importance memory NOT ranked #1")

async def test_context_builder():
    print("\n=== Testing Context Builder ===")
    user_id = f"test_user_{uuid.uuid4().hex[:8]}"
    
    # Insert a dummy memory so we get something back
    await memory_manager.add_message(user_id, "bot", "human", "Context builder test message", importance_score=5)
    await asyncio.sleep(1)
    
    context = await context_builder.build_context(user_id, "bot", "test")
    
    keys = ["history", "memories", "summaries", "knowledge", "trust"]
    missing = [k for k in keys if k not in context]
    
    if not missing:
        print("✅ SUCCESS: Context Builder returned all keys.")
        print(f"Keys found: {list(context.keys())}")
        print(f"Memories found: {len(context['memories'])}")
    else:
        print(f"❌ FAILURE: Missing keys: {missing}")

async def test_summary_topics():
    print("\n=== Testing Summary Topics Storage ===")
    user_id = f"test_user_{uuid.uuid4().hex[:8]}"
    session_id = str(uuid.uuid4())
    
    # Manually save a summary with topics
    topics = ["coding", "testing", "ai"]
    await memory_manager.save_summary_vector(
        session_id=session_id,
        user_id=user_id,
        content="We tested the AI memory system.",
        meaningfulness_score=5,
        emotions=["excited"],
        topics=topics
    )
    
    await asyncio.sleep(1)
    
    # Search and verify topics come back
    results = await memory_manager.search_summaries("testing", user_id)
    
    if results:
        retrieved_topics = results[0].get("topics", [])
        print(f"Retrieved Topics: {retrieved_topics}")
        if set(topics) == set(retrieved_topics):
            print("✅ SUCCESS: Topics retrieved correctly.")
        else:
            print("❌ FAILURE: Topics mismatch.")
    else:
        print("❌ FAILURE: No summary found.")

async def main():
    print("Initializing DB connections...")
    await db_manager.connect_all()
    await memory_manager.initialize()
    
    try:
        await test_weighted_retrieval()
        await test_context_builder()
        await test_summary_topics()
    except Exception as e:
        logger.exception("Test failed")
        print(f"❌ Test failed with error: {e}")
    finally:
        # Cleanup
        if db_manager.postgres_pool:
            await db_manager.postgres_pool.close()
        if db_manager.qdrant_client:
            await db_manager.qdrant_client.close()
        if db_manager.neo4j_driver:
            await db_manager.neo4j_driver.close()

if __name__ == "__main__":
    asyncio.run(main())
