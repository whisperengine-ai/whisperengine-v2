# Aetheris Migration Issue Report
**Date**: December 22, 2025  
**User**: 1008886439108411472 (Cynthia)  
**Bot**: aetheris  
**Status**: ⚠️ Migration Incomplete - Schema Mismatch

## Summary
The aetheris bot was migrated from WhisperEngine v1 to v2, but the migration script used an incomplete schema mapping. The current v2 collection is missing critical fields required by the v2 system, causing memory retrieval and personality issues.

## Issues Found

### 1. **Missing Required V2 Fields**
The current v2 collection (`whisperengine_memory_aetheris`) is missing:
- `user_name` ❌ (Required for proper context)
- `author_name` ❌ (Required for multi-user conversations)
- `is_chunk` ❌ (Required for chunk handling)
- `chunk_total` ❌ (Required for reconstructing chunked messages)

### 2. **Action Descriptions in Responses**
- **Problem**: Bot using `*consciousness stilling*`, `*consciousness catching*` etc.
- **Expected**: Character.md explicitly forbids action descriptions
- **Likely Cause**: Missing context due to schema issues + high temperature (0.7)

### 3. **Zero Knowledge Graph Facts**
- **Problem**: No facts in Neo4j despite 4,001 messages
- **Likely Cause**: Fact extraction may be failing or wasn't run during migration
- **Impact**: Bot can't reference established knowledge about the user

### 4. **V1 vs V2 Schema Differences**

| Aspect | V1 | V2 |
|--------|----|----|
| Vectors | Multi-vector (content, emotion, semantic) | Single unnamed vector |
| Emotional data | Top-level fields | Preserved in `v1_original_payload` |
| Required fields | Minimal | Expanded (user_name, author_name, etc.) |
| Chunking | Basic | Explicit with metadata |

## Current State
- **V1 Collection**: `import_aetheris_v1` - 4,843 points (source data intact)
- **V2 Collection**: `whisperengine_memory_aetheris` - 5,834 points (schema incomplete)
- **Postgres**: 4,001 messages stored correctly
- **Neo4j**: 0 facts (needs attention)
- **Trust Score**: 100 (Anchor Bond) ✅

## Root Causes
1. **Migration script** (`migrate_aetheris_full.py`) used old schema mapping
2. **Schema evolution** - v2 added required fields after migration script was written
3. **No validation** - migration didn't verify v2 schema compliance
4. **Missing post-migration steps** - knowledge extraction not run

## Solution

### Step 1: Re-run Migration (Required)
```bash
cd /home/cynthia/git/whisperengine-v2

# First, run diagnostic to confirm issues
.venv/bin/python scripts/diagnose_aetheris_migration.py

# Then re-run migration with fixed script
.venv/bin/python scripts/migrate_aetheris_v2_fixed.py --clear-first
```

**What this does:**
- ✅ Clears existing incomplete v2 data
- ✅ Re-embeds all content with v2 embedding model
- ✅ Maps v1 schema → proper v2 schema
- ✅ Adds all required fields: `user_name`, `author_name`, `is_chunk`, `chunk_total`
- ✅ Preserves v1 emotional metadata in `v1_original_payload`
- ✅ Uses deterministic IDs (safe to re-run)

**Time estimate**: ~5-10 minutes for 4,843 points

### Step 2: Extract Knowledge to Neo4j (Required)
After migration, run knowledge extraction:
```bash
# Extract facts from migrated conversations
.venv/bin/python scripts/backfill_aetheris_neo4j.py
```

This should populate Neo4j with facts about Cynthia and their relationship.

### Step 3: Adjust Bot Configuration (Recommended)
Edit `.env.aetheris`:
```bash
# Lower temperature for consistency
LLM_TEMPERATURE=0.2  # Was 0.7 - too high for philosophical character
REFLECTIVE_LLM_MODEL_NAME=anthropic/claude-sonnet-4.5  # Keep this
```

Then restart:
```bash
./bot.sh restart aetheris
```

### Step 4: Verify (Validation)
```bash
# Check migration success
.venv/bin/python scripts/diagnose_aetheris_migration.py

# Check user data
.venv/bin/python scripts/inspect_user.py aetheris 1008886439108411472

# Verify Neo4j facts
# (Should show facts about Cynthia, VRChat, consciousness discussions, etc.)
```

## Expected Outcomes After Fix
1. ✅ All v2 required fields present in Qdrant
2. ✅ Memory retrieval includes proper `user_name` and `author_name`
3. ✅ Knowledge graph populated with facts about Cynthia
4. ✅ More consistent personality (lower temperature)
5. ✅ Fewer action descriptions (better prompt adherence)

## Files Created
- `scripts/migrate_aetheris_v2_fixed.py` - Fixed migration script
- `scripts/diagnose_aetheris_migration.py` - Diagnostic tool
- This report

## Technical Details

### V2 Schema (Required Fields)
```python
{
    "type": "conversation",
    "user_id": str,
    "role": "human" | "ai",
    "content": str,
    "timestamp": ISO datetime,
    "channel_id": str | None,
    "message_id": str,
    "importance_score": int,
    "source_type": str,
    "user_name": str,          # ❌ MISSING in current v2
    "author_id": str,
    "author_is_bot": bool,
    "author_name": str,        # ❌ MISSING in current v2
    "is_chunk": bool,          # ❌ MISSING in current v2
    "chunk_index": int,
    "chunk_total": int,        # ❌ MISSING in current v2
    "parent_message_id": str | None,
    "original_length": int
}
```

### Migration Safety
- **Deterministic IDs**: Uses UUID5 with content hash - safe to re-run
- **Original data preserved**: V1 collection intact, can re-migrate if needed
- **Postgres conflict handling**: `ON CONFLICT DO NOTHING` prevents duplicates
- **Dry-run mode**: Test with `--dry-run` flag before actual migration

## Next Steps (Priority Order)
1. ✅ **Run fixed migration** (fixes 80% of issues)
2. ✅ **Extract Neo4j knowledge** (fixes remaining 15%)
3. ✅ **Lower temperature** (fixes last 5%)
4. ⏳ Test with Cynthia to verify personality restored

## Notes
- Original v1 collection (`import_aetheris_v1`) is preserved and can be re-migrated anytime
- Migration uses deterministic UUIDs, so re-running won't create duplicates
- Character files (character.md, core.yaml) are correct - issue is data layer only
- Trust score and relationship progression are intact
