"""
Diagnostic: Compare V1 vs V2 Schema for Aetheris
================================================

This script analyzes the current aetheris Qdrant collection and compares it
against the expected v2 schema to identify issues.

Usage:
    python scripts/diagnose_aetheris_migration.py
"""
import asyncio
import sys
from pathlib import Path
from typing import Dict, Any, Set, List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from qdrant_client import AsyncQdrantClient
from src_v2.config.settings import settings
from loguru import logger

V1_COLLECTION = "import_aetheris_v1"
V2_COLLECTION = "whisperengine_memory_aetheris"

# Expected v2 schema fields (from src_v2/memory/manager.py)
V2_REQUIRED_FIELDS = {
    "type", "user_id", "role", "content", "timestamp", "channel_id",
    "message_id", "importance_score", "source_type", "user_name",
    "author_id", "author_is_bot", "author_name", "is_chunk",
    "chunk_index", "chunk_total"
}

V2_OPTIONAL_FIELDS = {
    "reply_to_msg_id", "session_id", "parent_message_id", "original_length",
    "v1_emotional_context", "v1_emotional_intensity", "v1_significance",
    "v1_memory_tier", "v1_original_payload", "original_payload"
}

async def diagnose():
    """Analyze current aetheris collection schema."""
    qdrant = AsyncQdrantClient(url=settings.QDRANT_URL)
    
    # Check collections exist
    v1_exists = await qdrant.collection_exists(V1_COLLECTION)
    v2_exists = await qdrant.collection_exists(V2_COLLECTION)
    
    print("=" * 80)
    print("AETHERIS MIGRATION DIAGNOSTIC")
    print("=" * 80)
    print()
    
    # V1 Collection
    if v1_exists:
        v1_info = await qdrant.get_collection(V1_COLLECTION)
        print(f"✅ V1 Collection: {V1_COLLECTION}")
        print(f"   Points: {v1_info.points_count}")
        print(f"   Vectors: {list(v1_info.config.params.vectors.keys())}")
        
        # Sample v1 point
        v1_points, _ = await qdrant.scroll(
            collection_name=V1_COLLECTION,
            limit=1,
            with_payload=True,
            with_vectors=False
        )
        if v1_points:
            v1_sample = v1_points[0].payload
            print(f"   Sample fields: {sorted(v1_sample.keys())[:15]}...")
    else:
        print(f"❌ V1 Collection: {V1_COLLECTION} NOT FOUND")
    
    print()
    
    # V2 Collection
    if v2_exists:
        v2_info = await qdrant.get_collection(V2_COLLECTION)
        print(f"✅ V2 Collection: {V2_COLLECTION}")
        print(f"   Points: {v2_info.points_count}")
        print(f"   Vector config: Single unnamed vector (expected for v2)")
        
        # Sample v2 points to analyze schema
        v2_points, _ = await qdrant.scroll(
            collection_name=V2_COLLECTION,
            limit=10,
            with_payload=True,
            with_vectors=False
        )
        
        if v2_points:
            # Analyze field coverage
            all_fields: Set[str] = set()
            field_counts: Dict[str, int] = {}
            
            for point in v2_points:
                for field in point.payload.keys():
                    all_fields.add(field)
                    field_counts[field] = field_counts.get(field, 0) + 1
            
            print()
            print("   Field Analysis:")
            print("   " + "-" * 76)
            
            # Check required fields
            missing_required = V2_REQUIRED_FIELDS - all_fields
            if missing_required:
                print(f"   ❌ MISSING REQUIRED FIELDS: {missing_required}")
            else:
                print(f"   ✅ All required fields present")
            
            # Check field consistency
            print()
            print("   Field Presence (out of 10 sampled points):")
            for field in sorted(all_fields):
                count = field_counts[field]
                status = "✅" if count == 10 else "⚠️ "
                required = "REQUIRED" if field in V2_REQUIRED_FIELDS else "optional"
                print(f"   {status} {field:30s} {count}/10  [{required}]")
            
            # Sample payload
            print()
            print("   Sample V2 Payload:")
            print("   " + "-" * 76)
            sample = v2_points[0].payload
            for key in sorted(sample.keys()):
                value = sample[key]
                if isinstance(value, str) and len(value) > 60:
                    value = value[:57] + "..."
                elif isinstance(value, dict) or isinstance(value, list):
                    value = f"<{type(value).__name__}>"
                print(f"   {key:30s} = {value}")
            
            # Check for v1 artifacts
            print()
            has_v1_payload = any("original_payload" in p.payload for p in v2_points)
            has_proper_schema = all(
                "user_name" in p.payload and "author_name" in p.payload 
                for p in v2_points
            )
            
            if has_v1_payload and not has_proper_schema:
                print("   ⚠️  ISSUE DETECTED:")
                print("      Collection has v1 data in 'original_payload' but")
                print("      missing proper v2 schema fields (user_name, author_name)")
                print()
                print("   📋 RECOMMENDATION:")
                print("      Run: python scripts/migrate_aetheris_v2_fixed.py --clear-first")
            elif has_proper_schema:
                print("   ✅ Schema looks good!")
            else:
                print("   ⚠️  Schema incomplete, migration recommended")
                
    else:
        print(f"❌ V2 Collection: {V2_COLLECTION} NOT FOUND")
        print("   Need to run migration script first")
    
    print()
    print("=" * 80)
    
    # Summary and recommendations
    print()
    print("RECOMMENDATIONS:")
    print("=" * 80)
    
    if not v1_exists:
        print("❌ No v1 data found. Cannot migrate.")
    elif not v2_exists:
        print("1. Run migration:")
        print("   python scripts/migrate_aetheris_v2_fixed.py")
    elif v2_exists and v1_exists:
        v2_count = (await qdrant.get_collection(V2_COLLECTION)).points_count
        v1_count = (await qdrant.get_collection(V1_COLLECTION)).points_count
        
        if v2_count < v1_count * 0.9:  # Less than 90% migrated
            print(f"⚠️  V2 has {v2_count} points but V1 has {v1_count}")
            print("   Migration may be incomplete. Consider re-running:")
            print("   python scripts/migrate_aetheris_v2_fixed.py --clear-first")
        
        # Check schema
        v2_points, _ = await qdrant.scroll(
            collection_name=V2_COLLECTION,
            limit=5,
            with_payload=True,
            with_vectors=False
        )
        
        if v2_points:
            has_proper_schema = all(
                "user_name" in p.payload and 
                "author_name" in p.payload and
                "is_chunk" in p.payload
                for p in v2_points
            )
            
            if not has_proper_schema:
                print()
                print("⚠️  Schema issues detected. Re-run migration with fixed script:")
                print("   python scripts/migrate_aetheris_v2_fixed.py --clear-first")
            else:
                print()
                print("✅ Migration looks complete!")
                print("   V2 collection has proper schema and data count")
    
    print()

if __name__ == "__main__":
    asyncio.run(diagnose())
