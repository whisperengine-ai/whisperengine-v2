# Embedding Dimension Upgrade: 384D → 768D

**Document Version:** 1.2  
**Created:** November 25, 2025  
**Status:** Ready to Implement  
**Priority:** 🔴 CRITICAL (Do Before More Production Data)  
**Complexity:** 🟢 Low  
**Estimated Time:** 30-60 minutes (depends on data volume)

---

## Multi-Modal Context: Memory Resolution

Embeddings are the **resolution** of the Memory modality (🧠). Just as human memory clarity varies from fuzzy to crystal clear, embedding dimensions determine how finely characters can distinguish between similar memories.

| Dimension | Resolution Quality |
|-----------|-------------------|
| 384D | "Blurry" - similar memories blend together |
| 768D | "Clear" - nuanced distinctions preserved |

Think of it like upgrading from standard definition to high definition memory. Characters will remember with greater fidelity.

For full philosophy: See [`../architecture/MULTI_MODAL_PERCEPTION.md`](../architecture/MULTI_MODAL_PERCEPTION.md)

---

## Executive Summary

Upgrade the embedding model from `all-MiniLM-L6-v2` (384 dimensions) to `BAAI/bge-base-en-v1.5` (768 dimensions) across the entire system. This is a one-time migration that should be done **now while in development** before any production data exists.

**Why Now?**
- Easy now: Delete collections, restart, done
- Hard later: Would require re-embedding all stored memories (expensive, slow)
- No production data to migrate yet

---

## Current State

| Component | Model | Dimensions | Context Limit |
|-----------|-------|------------|---------------|
| Memory (Qdrant) | all-MiniLM-L6-v2 | 384 | 256 tokens |
| Future: Reasoning Traces | all-MiniLM-L6-v2 | 384 | 256 tokens |
| Future: Response Patterns | all-MiniLM-L6-v2 | 384 | 256 tokens |

---

## Proposed State

| Component | Model | Dimensions | Context Limit |
|-----------|-------|------------|---------------|
| Memory (Qdrant) | BAAI/bge-base-en-v1.5 | 768 | 512 tokens |
| Future: Reasoning Traces | BAAI/bge-base-en-v1.5 | 768 | 512 tokens |
| Future: Response Patterns | BAAI/bge-base-en-v1.5 | 768 | 512 tokens |

---

## Why Upgrade?

### Semantic Resolution Improvement

384D embeddings can miss nuanced differences:
- "Talked about coral reef conservation" vs "Mentioned going to the beach"
- These might have high similarity in 384D but are quite different topics

768D provides ~2x the "resolution" for distinguishing semantic meaning.

### Benchmark Comparison

| Model | Dims | MTEB Score | Retrieval Score |
|-------|------|------------|-----------------|
| all-MiniLM-L6-v2 | 384 | 56.3 | 41.9 |
| BAAI/bge-base-en-v1.5 | 768 | 63.5 | 53.3 |

**~10-15% improvement in retrieval quality**

### Context Window

| Model | Max Tokens | Implication |
|-------|------------|-------------|
| all-MiniLM-L6-v2 | 256 | Long messages get truncated |
| BAAI/bge-base-en-v1.5 | 512 | Can embed longer context |

### Impact on Features

| Feature | Improvement |
|---------|-------------|
| Memory Retrieval | Better at finding relevant past conversations |
| Lurk Detection | More accurate topic matching |
| Reasoning Traces | Better at finding similar past reasoning |
| Response Patterns | More precise style matching |

---

## Why NOT 1024D?

| Consideration | 768D | 1024D |
|---------------|------|-------|
| Storage | 2x of 384 | 2.7x of 384 |
| Speed | ~15-20ms | ~25-35ms |
| Model Size | 210MB | 1.2GB |
| Quality Gain | +10-15% vs 384 | +2-3% vs 768 |

**Verdict:** 1024D has diminishing returns for chat-length text. 768D is the sweet spot.

---

## Model Selection: BAAI/bge-base-en-v1.5

**Why this model?**

| Criterion | Value |
|-----------|-------|
| Dimensions | 768 |
| Model Size | 210MB |
| Context Window | 512 tokens |
| License | MIT (commercial OK) |
| FastEmbed Support | ✅ Native |
| Benchmark Ranking | Top-tier for size |
| Speed | ~15-20ms per embed |

**Alternatives Considered:**

| Model | Why Not |
|-------|---------|
| nomic-embed-text-v1.5 | 520MB, larger than needed |
| snowflake-arctic-embed-m | Similar quality, less battle-tested |
| bge-large-en-v1.5 | 1024D, overkill |

---

## Storage Impact

| Memories | 384D Storage | 768D Storage | Delta |
|----------|--------------|--------------|-------|
| 1,000 | 1.5 MB | 3 MB | +1.5 MB |
| 10,000 | 15 MB | 30 MB | +15 MB |
| 100,000 | 150 MB | 300 MB | +150 MB |
| 1,000,000 | 1.5 GB | 3 GB | +1.5 GB |

**Verdict:** Storage increase is trivial for expected data volumes.

---

## Implementation Plan

### Files to Modify

1. **`src_v2/config/settings.py`** - Add embedding config
2. **`src_v2/memory/embeddings.py`** - Use settings for model
3. **`src_v2/memory/manager.py`** - Use settings for vector size
4. **`scripts/migrate_qdrant_384_to_768.py`** - NEW: Migration script for existing data

### Code Changes

#### 1. Settings (settings.py)

```python
# --- Embedding Configuration ---
EMBEDDING_MODEL: str = "BAAI/bge-base-en-v1.5"
EMBEDDING_DIMENSIONS: int = 768
```

#### 2. Embedding Service (embeddings.py)

```python
from src_v2.config.settings import settings

class EmbeddingService:
    """
    Service for generating vector embeddings using FastEmbed.
    Model and dimensions configured via settings.
    """
    
    def __init__(self, model_name: str = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL
```

#### 3. Memory Manager (manager.py)

```python
from src_v2.config.settings import settings

# In initialize():
vectors_config = VectorParams(
    size=settings.EMBEDDING_DIMENSIONS, 
    distance=Distance.COSINE
)
```

### Migration Script for Existing User Data

Since you have existing users with conversation history, we need to **re-embed all existing vectors** with the new model. This preserves all memories but upgrades them to 768D.

#### Migration Script: `scripts/migrate_qdrant_384_to_768.py`

```python
#!/usr/bin/env python3
"""
Migrate Qdrant collections from 384D (all-MiniLM-L6-v2) to 768D (bge-base-en-v1.5).

This script:
1. Reads all points from the 384D collection
2. Re-embeds the content using the new 768D model
3. Creates a new 768D collection with the migrated data
4. Optionally deletes the old collection after verification

Usage:
    python scripts/migrate_qdrant_384_to_768.py --collection whisperengine_memory_elena
    python scripts/migrate_qdrant_384_to_768.py --collection whisperengine_memory_elena --dry-run
    python scripts/migrate_qdrant_384_to_768.py --all-collections
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional, List
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from loguru import logger
logger.remove()
logger.add(sys.stderr, level="INFO")

from qdrant_client import AsyncQdrantClient, models
from src_v2.memory.embeddings import EmbeddingService
from src_v2.config.settings import settings

# Old model for reference
OLD_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
OLD_DIMS = 384

# New model (from settings, but can override)
NEW_MODEL = "BAAI/bge-base-en-v1.5"
NEW_DIMS = 768


async def migrate_collection(
    client: AsyncQdrantClient,
    old_collection: str,
    new_collection: str,
    embedding_service: EmbeddingService,
    batch_size: int = 100,
    dry_run: bool = False
) -> dict:
    """Migrate a single collection from 384D to 768D."""
    
    stats = {
        "total_points": 0,
        "migrated": 0,
        "failed": 0,
        "skipped": 0
    }
    
    # Get collection info
    try:
        info = await client.get_collection(old_collection)
        stats["total_points"] = info.points_count
        logger.info(f"Found {info.points_count} points in '{old_collection}'")
    except Exception as e:
        logger.error(f"Collection '{old_collection}' not found: {e}")
        return stats
    
    if stats["total_points"] == 0:
        logger.info("No points to migrate.")
        return stats
    
    # Create new collection if it doesn't exist
    new_exists = await client.collection_exists(new_collection)
    if not new_exists:
        if dry_run:
            logger.info(f"[DRY RUN] Would create collection '{new_collection}' with {NEW_DIMS}D vectors")
        else:
            logger.info(f"Creating new collection '{new_collection}' with {NEW_DIMS}D vectors")
            await client.create_collection(
                collection_name=new_collection,
                vectors_config=models.VectorParams(size=NEW_DIMS, distance=models.Distance.COSINE)
            )
    else:
        logger.warning(f"Collection '{new_collection}' already exists. Will append/update points.")
    
    # Scroll through all points
    offset = None
    batch_num = 0
    
    while True:
        # Fetch batch of points
        results = await client.scroll(
            collection_name=old_collection,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False  # Don't need old vectors, we're re-embedding
        )
        
        points, next_offset = results
        if not points:
            break
            
        batch_num += 1
        logger.info(f"Processing batch {batch_num}: {len(points)} points")
        
        # Extract content and re-embed
        new_points = []
        for point in points:
            content = point.payload.get("content", "")
            if not content:
                stats["skipped"] += 1
                continue
            
            try:
                # Re-embed with new model
                if not dry_run:
                    new_vector = embedding_service.embed_query(content)
                    
                    new_points.append(models.PointStruct(
                        id=point.id,
                        vector=new_vector,
                        payload=point.payload
                    ))
                stats["migrated"] += 1
                
            except Exception as e:
                logger.error(f"Failed to embed point {point.id}: {e}")
                stats["failed"] += 1
        
        # Upsert batch to new collection
        if new_points and not dry_run:
            await client.upsert(
                collection_name=new_collection,
                points=new_points
            )
            logger.info(f"  Upserted {len(new_points)} points to '{new_collection}'")
        
        # Check for more
        offset = next_offset
        if offset is None:
            break
    
    return stats


async def main():
    parser = argparse.ArgumentParser(description="Migrate Qdrant 384D → 768D")
    parser.add_argument("--collection", help="Single collection to migrate")
    parser.add_argument("--all-collections", action="store_true", help="Migrate all whisperengine_memory_* collections")
    parser.add_argument("--url", default="http://localhost:6333", help="Qdrant URL")
    parser.add_argument("--batch-size", type=int, default=100, help="Points per batch")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually migrate, just show what would happen")
    parser.add_argument("--delete-old", action="store_true", help="Delete old collection after successful migration")
    args = parser.parse_args()
    
    if not args.collection and not args.all_collections:
        parser.error("Must specify --collection or --all-collections")
    
    # Connect to Qdrant
    client = AsyncQdrantClient(url=args.url)
    
    # Initialize new embedding service
    logger.info(f"Loading embedding model: {NEW_MODEL}")
    embedding_service = EmbeddingService(model_name=NEW_MODEL)
    # Warm up the model
    _ = embedding_service.embed_query("warmup")
    logger.info("Embedding model loaded.")
    
    # Get collections to migrate
    collections_to_migrate = []
    if args.collection:
        collections_to_migrate = [args.collection]
    else:
        # Find all whisperengine_memory_* collections
        all_collections = await client.get_collections()
        collections_to_migrate = [
            c.name for c in all_collections.collections 
            if c.name.startswith("whisperengine_memory_")
        ]
        logger.info(f"Found {len(collections_to_migrate)} collections to migrate: {collections_to_migrate}")
    
    # Migrate each collection
    total_stats = {"total_points": 0, "migrated": 0, "failed": 0, "skipped": 0}
    
    for old_name in collections_to_migrate:
        # New collection name: append _768d suffix during migration, then rename
        new_name = f"{old_name}_768d"
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Migrating: {old_name} → {new_name}")
        logger.info(f"{'='*60}")
        
        stats = await migrate_collection(
            client=client,
            old_collection=old_name,
            new_collection=new_name,
            embedding_service=embedding_service,
            batch_size=args.batch_size,
            dry_run=args.dry_run
        )
        
        for key in total_stats:
            total_stats[key] += stats[key]
        
        logger.info(f"Collection '{old_name}' migration complete: {stats}")
        
        # Delete old and rename new (if requested and not dry run)
        if args.delete_old and not args.dry_run and stats["failed"] == 0:
            logger.info(f"Deleting old collection '{old_name}'...")
            await client.delete_collection(old_name)
            
            # Rename new collection to old name
            # Note: Qdrant doesn't have native rename, so we'd need to copy again
            # For simplicity, just keep the _768d suffix or manually rename
            logger.info(f"Old collection deleted. New collection is '{new_name}'")
            logger.info(f"To use: update your code to use '{new_name}' OR manually rename")
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("MIGRATION SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Total points:  {total_stats['total_points']}")
    logger.info(f"Migrated:      {total_stats['migrated']}")
    logger.info(f"Failed:        {total_stats['failed']}")
    logger.info(f"Skipped:       {total_stats['skipped']}")
    
    if args.dry_run:
        logger.info("\n[DRY RUN] No changes were made. Run without --dry-run to execute.")


if __name__ == "__main__":
    asyncio.run(main())
```

### Migration Steps (With Existing Users)

```bash
# 1. Stop the bot
./bot.sh down elena

# 2. Apply code changes (settings.py, embeddings.py, manager.py)
# ... make the code changes ...

# 3. Run migration (dry run first to verify)
python scripts/migrate_qdrant_384_to_768.py --all-collections --dry-run

# 4. Run actual migration
python scripts/migrate_qdrant_384_to_768.py --all-collections

# 5. Verify new collections exist
curl "http://localhost:6333/collections" | jq '.result.collections[].name'
# Should see: whisperengine_memory_elena_768d

# 6. Update collection name in settings (or rename collection)
# Option A: Add to settings.py:
#   QDRANT_COLLECTION_SUFFIX: str = "_768d"
# Option B: Rename collection in Qdrant (requires copy)

# 7. Delete old 384D collections (after verification!)
python scripts/migrate_qdrant_384_to_768.py --all-collections --delete-old

# 8. Restart bot
./bot.sh up elena
```

### Migration Time Estimate

| Memories | Embedding Time | Total Time |
|----------|----------------|------------|
| 100 | ~2 sec | ~1 min |
| 1,000 | ~20 sec | ~2 min |
| 10,000 | ~3 min | ~5 min |
| 100,000 | ~30 min | ~35 min |

### Verification After Migration

```bash
# 1. Check new collection exists and has correct dimensions
curl "http://localhost:6333/collections/whisperengine_memory_elena_768d" | jq '.result.config.params.vectors.size'
# Should return: 768

# 2. Check point count matches original
curl "http://localhost:6333/collections/whisperengine_memory_elena_768d" | jq '.result.points_count'
# Should match original collection

# 3. Test search works
curl -X POST "http://localhost:6333/collections/whisperengine_memory_elena_768d/points/search" \
  -H "Content-Type: application/json" \
  -d '{"vector": [0.1, 0.2, ...], "limit": 5}'  # Use a real 768D vector

# 4. Restart bot and test memory retrieval
./bot.sh up elena
# Send a message and verify memories are retrieved correctly
```

---

## Update Documentation

After migration, update these references to 768:

- [ ] `docs/architecture/DATA_MODELS.md`
- [ ] `docs/architecture/MESSAGE_FLOW.md`
- [ ] `docs/architecture/SUMMARIZATION_SYSTEM.md`
- [ ] `docs/architecture/VISION_PIPELINE.md`
- [ ] `docs/IMPLEMENTATION_ROADMAP_OVERVIEW.md` (reasoning traces table)
- [ ] `docs/roadmaps/RESPONSE_PATTERN_LEARNING.md`
- [ ] `docs/roadmaps/CHANNEL_LURKING.md` (if mentions dimensions)
- [ ] `.github/copilot-instructions.md` (if mentions 384D)

---

## Rollback Plan

If issues arise:

1. Revert code changes
2. Delete 768D collections
3. Restart (will recreate with 384D)

**Risk:** Low - this is a clean swap with no data dependencies.

---

## Future Considerations

### Hybrid Search (Optional Enhancement)

Once on 768D, could add sparse embeddings for hybrid search:
- Dense: BAAI/bge-base-en-v1.5 (semantic)
- Sparse: BM25 or SPLADE (keyword)

This gives best-of-both-worlds retrieval. Not required now, but 768D is a prerequisite.

### Multi-Vector (Future)

Some advanced use cases benefit from multiple vector types per document:
- Content vector
- Emotion vector  
- Topic vector

768D makes this more practical (better base quality).

---

## Success Metrics

| Metric | Before (384D) | After (768D) | Target |
|--------|---------------|--------------|--------|
| Memory retrieval relevance | Baseline | +10-15% | Measurable improvement |
| Lurk detection accuracy | N/A | Higher | Fewer false positives |
| Embedding latency | ~10ms | ~20ms | <50ms acceptable |

---

## Timeline

| Task | Time | Status |
|------|------|--------|
| Update settings.py | 5 min | 📋 Ready |
| Update embeddings.py | 5 min | 📋 Ready |
| Update manager.py | 5 min | 📋 Ready |
| Create migration script | 10 min | 📋 Ready |
| Run migration (dry run) | 5 min | 📋 Ready |
| Run migration (actual) | 5-30 min* | 📋 Ready |
| Verify new collections | 5 min | 📋 Ready |
| Delete old collections | 2 min | 📋 Ready |
| Update docs | 15 min | 📋 Ready |
| **Total** | **~45-75 min** | |

*Migration time depends on data volume. See estimates above.

---

## Related Documents

- `src_v2/memory/embeddings.py` - Current embedding service
- `src_v2/memory/manager.py` - Qdrant collection creation
- `docs/architecture/DATA_MODELS.md` - Data model documentation

---

**Version History:**
- v1.0 (Nov 25, 2025) - Initial document
