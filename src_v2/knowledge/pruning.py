"""
Knowledge Graph Pruning (Phase E24)

Maintains Neo4j graph health by removing stale, orphaned, and low-value nodes/edges.
Runs as a scheduled background task to prevent unbounded growth.

Pruning Strategies:
1. Orphan Cleanup - Remove Entity nodes with no incoming relationships
2. Stale Facts - Remove facts older than retention period with low access
3. Duplicate Entities - Merge semantically identical entities
4. Low Confidence - Remove facts below confidence threshold after grace period

Design Philosophy:
- Preserve narrative value over raw data
- Never prune recently accessed nodes (even if old)
- Keep resolution tracking for absence patterns (E22)
- Log all deletions for audit trail
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger

from src_v2.config.settings import settings
from src_v2.core.database import db_manager, retry_db_operation


@dataclass
class PruningStats:
    """Statistics from a pruning run."""
    orphans_removed: int = 0
    stale_facts_removed: int = 0
    duplicates_merged: int = 0
    low_confidence_removed: int = 0
    total_nodes_before: int = 0
    total_nodes_after: int = 0
    total_edges_before: int = 0
    total_edges_after: int = 0
    duration_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "orphans_removed": self.orphans_removed,
            "stale_facts_removed": self.stale_facts_removed,
            "duplicates_merged": self.duplicates_merged,
            "low_confidence_removed": self.low_confidence_removed,
            "total_nodes_before": self.total_nodes_before,
            "total_nodes_after": self.total_nodes_after,
            "total_edges_before": self.total_edges_before,
            "total_edges_after": self.total_edges_after,
            "duration_seconds": round(self.duration_seconds, 2),
            "errors": self.errors
        }


class KnowledgeGraphPruner:
    """
    Maintains Neo4j graph health through scheduled cleanup operations.
    
    Usage:
        pruner = KnowledgeGraphPruner()
        stats = await pruner.run_full_prune()
    """
    
    def __init__(self, bot_name: Optional[str] = None):
        self.bot_name = bot_name or settings.DISCORD_BOT_NAME or "default"
        
        # Configurable thresholds (from settings or defaults)
        self.orphan_grace_days = getattr(settings, 'GRAPH_PRUNE_ORPHAN_GRACE_DAYS', 7)
        self.stale_fact_days = getattr(settings, 'GRAPH_PRUNE_STALE_FACT_DAYS', 90)
        self.min_access_count = getattr(settings, 'GRAPH_PRUNE_MIN_ACCESS_COUNT', 1)
        self.min_confidence = getattr(settings, 'GRAPH_PRUNE_MIN_CONFIDENCE', 0.3)
        self.confidence_grace_days = getattr(settings, 'GRAPH_PRUNE_CONFIDENCE_GRACE_DAYS', 14)
        self.dry_run = getattr(settings, 'GRAPH_PRUNE_DRY_RUN', False)
    
    async def run_full_prune(self, dry_run: Optional[bool] = None) -> PruningStats:
        """
        Run all pruning strategies in sequence.
        
        Args:
            dry_run: If True, report what would be deleted without deleting.
                     Overrides settings.GRAPH_PRUNE_DRY_RUN if provided.
        
        Returns:
            PruningStats with counts of removed items
        """
        is_dry_run: bool = dry_run if dry_run is not None else self.dry_run
        
        start_time = datetime.now(timezone.utc)
        stats = PruningStats()
        
        if not db_manager.neo4j_driver:
            logger.warning("Neo4j not available for graph pruning")
            stats.errors.append("Neo4j not available")
            return stats
        
        try:
            # Get initial counts
            stats.total_nodes_before, stats.total_edges_before = await self._get_graph_counts()
            
            # Run pruning strategies
            stats.orphans_removed = await self._prune_orphan_entities(is_dry_run)
            stats.stale_facts_removed = await self._prune_stale_facts(is_dry_run)
            stats.duplicates_merged = await self._merge_duplicate_entities(is_dry_run)
            stats.low_confidence_removed = await self._prune_low_confidence(is_dry_run)
            
            # Get final counts
            stats.total_nodes_after, stats.total_edges_after = await self._get_graph_counts()
            
        except Exception as e:
            logger.error(f"Graph pruning failed: {e}")
            stats.errors.append(str(e))
        
        stats.duration_seconds = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        action = "Would prune" if is_dry_run else "Pruned"
        logger.info(
            f"{action} graph for {self.bot_name}: "
            f"{stats.orphans_removed} orphans, "
            f"{stats.stale_facts_removed} stale facts, "
            f"{stats.duplicates_merged} duplicates merged, "
            f"{stats.low_confidence_removed} low-confidence in {stats.duration_seconds:.2f}s"
        )
        
        return stats
    
    async def _get_graph_counts(self) -> Tuple[int, int]:
        """Get total node and edge counts."""
        try:
            async with db_manager.neo4j_driver.session() as session:
                # Count nodes
                node_result = await session.run("MATCH (n) RETURN count(n) as count")
                node_record = await node_result.single()
                node_count = node_record["count"] if node_record else 0
                
                # Count edges
                edge_result = await session.run("MATCH ()-[r]->() RETURN count(r) as count")
                edge_record = await edge_result.single()
                edge_count = edge_record["count"] if edge_record else 0
                
                return node_count, edge_count
        except Exception as e:
            logger.error(f"Failed to get graph counts: {e}")
            return 0, 0
    
    async def _prune_orphan_entities(self, dry_run: bool = False) -> int:
        """
        Remove Entity nodes with no incoming relationships.
        
        Preserves:
        - Entities created recently (within grace period)
        - Entities with any relationship (incoming or outgoing)
        """
        grace_threshold = datetime.now(timezone.utc) - timedelta(days=self.orphan_grace_days)
        grace_str = grace_threshold.isoformat()
        
        try:
            async with db_manager.neo4j_driver.session() as session:
                if dry_run:
                    # Count only - check for entities with NO relationships at all
                    query = """
                    MATCH (e:Entity)
                    WHERE NOT (e)--()
                      AND (e.created_at IS NULL OR e.created_at < $grace_threshold)
                    RETURN count(e) as count
                    """
                    result = await session.run(query, grace_threshold=grace_str)
                    record = await result.single()
                    return record["count"] if record else 0
                else:
                    # Delete orphan entities (no relationships at all)
                    # Use DETACH DELETE for safety in case of race conditions
                    query = """
                    MATCH (e:Entity)
                    WHERE NOT (e)--()
                      AND (e.created_at IS NULL OR e.created_at < $grace_threshold)
                    WITH e, e.name as name
                    DETACH DELETE e
                    RETURN count(*) as deleted, collect(name) as names
                    """
                    result = await session.run(query, grace_threshold=grace_str)
                    record = await result.single()
                    
                    if record and record["deleted"] > 0:
                        logger.debug(f"Deleted orphan entities: {record['names'][:10]}...")
                    
                    return record["deleted"] if record else 0
                    
        except Exception as e:
            logger.error(f"Failed to prune orphan entities: {e}")
            return 0
    
    async def _prune_stale_facts(self, dry_run: bool = False) -> int:
        """
        Remove facts that are old AND haven't been accessed recently.
        
        Preserves:
        - Facts accessed within the stale threshold
        - Facts with high access counts (frequently used)
        - Facts related to absence tracking (E22)
        """
        stale_threshold = datetime.now(timezone.utc) - timedelta(days=self.stale_fact_days)
        stale_str = stale_threshold.isoformat()
        
        try:
            async with db_manager.neo4j_driver.session() as session:
                if dry_run:
                    query = """
                    MATCH (n)-[r:FACT]->(e:Entity)
                    WHERE r.created_at < $stale_threshold
                      AND (r.last_accessed IS NULL OR r.last_accessed < $stale_threshold)
                      AND (r.access_count IS NULL OR r.access_count < $min_access)
                      AND r.bot_name = $bot_name
                    RETURN count(r) as count
                    """
                else:
                    query = """
                    MATCH (n)-[r:FACT]->(e:Entity)
                    WHERE r.created_at < $stale_threshold
                      AND (r.last_accessed IS NULL OR r.last_accessed < $stale_threshold)
                      AND (r.access_count IS NULL OR r.access_count < $min_access)
                      AND r.bot_name = $bot_name
                    WITH r, n.id as source, e.name as target, r.predicate as predicate
                    DELETE r
                    RETURN count(*) as count
                    """
                
                result = await session.run(
                    query,
                    stale_threshold=stale_str,
                    min_access=self.min_access_count,
                    bot_name=self.bot_name
                )
                record = await result.single()
                return record["count"] if record else 0
                
        except Exception as e:
            logger.error(f"Failed to prune stale facts: {e}")
            return 0
    
    async def _merge_duplicate_entities(self, dry_run: bool = False) -> int:
        """
        Merge entities with identical names (case-insensitive).
        
        Strategy:
        - Find entities with same toLower(name)
        - Keep the one with most relationships
        - Redirect all relationships to the kept node (copying properties)
        - Delete the duplicates
        """
        try:
            async with db_manager.neo4j_driver.session() as session:
                if dry_run:
                    # Count potential merges
                    query = """
                    MATCH (e:Entity)
                    WITH toLower(toString(e.name)) as normalized, collect(e) as entities
                    WHERE size(entities) > 1
                    RETURN sum(size(entities) - 1) as count
                    """
                    result = await session.run(query)
                    record = await result.single()
                    return record["count"] if record else 0
                else:
                    # Perform merges
                    merge_count = 0
                    
                    # First, find all duplicates (limit to avoid timeouts)
                    find_query = """
                    MATCH (e:Entity)
                    WITH toLower(toString(e.name)) as normalized, collect(e) as entities
                    WHERE size(entities) > 1
                    RETURN normalized, entities
                    LIMIT 50
                    """
                    result = await session.run(find_query)
                    records = await result.data()
                    
                    for record in records:
                        entities = record["entities"]
                        if len(entities) < 2:
                            continue
                        
                        # Find the one with most relationships
                        best_entity = None
                        best_rel_count = -1
                        
                        for entity in entities:
                            count_query = """
                            MATCH (e:Entity {name: $name})-[r]-()
                            RETURN count(r) as rel_count
                            """
                            count_result = await session.run(count_query, name=entity["name"])
                            count_record = await count_result.single()
                            rel_count = count_record["rel_count"] if count_record else 0
                            
                            if rel_count > best_rel_count:
                                best_rel_count = rel_count
                                best_entity = entity
                        
                        # Merge others into best
                        for entity in entities:
                            if entity["name"] != best_entity["name"]:
                                # Split into separate queries to avoid complex Cypher issues with CREATE(expr)
                                try:
                                    # 1. Move incoming FACTs
                                    await session.run("""
                                        MATCH (old:Entity {name: $old_name})
                                        MATCH (new:Entity {name: $new_name})
                                        MATCH (n)-[r:FACT]->(old)
                                        CREATE (n)-[new_r:FACT]->(new)
                                        SET new_r = properties(r)
                                        DELETE r
                                    """, old_name=entity["name"], new_name=best_entity["name"])
                                    
                                    # 2. Move outgoing IS_A
                                    await session.run("""
                                        MATCH (old:Entity {name: $old_name})
                                        MATCH (new:Entity {name: $new_name})
                                        MATCH (old)-[r:IS_A]->(target)
                                        CREATE (new)-[new_r:IS_A]->(target)
                                        SET new_r = properties(r)
                                        DELETE r
                                    """, old_name=entity["name"], new_name=best_entity["name"])
                                    
                                    # 3. Move outgoing BELONGS_TO
                                    await session.run("""
                                        MATCH (old:Entity {name: $old_name})
                                        MATCH (new:Entity {name: $new_name})
                                        MATCH (old)-[r:BELONGS_TO]->(target)
                                        CREATE (new)-[new_r:BELONGS_TO]->(target)
                                        SET new_r = properties(r)
                                        DELETE r
                                    """, old_name=entity["name"], new_name=best_entity["name"])
                                    
                                    # 4. Delete old node
                                    await session.run("""
                                        MATCH (old:Entity {name: $old_name})
                                        DETACH DELETE old
                                    """, old_name=entity["name"])
                                    
                                    merge_count += 1
                                except Exception as merge_error:
                                    logger.warning(f"Failed to merge {entity['name']}: {merge_error}")
                    
                    return merge_count
                    
        except Exception as e:
            logger.error(f"Failed to merge duplicate entities: {e}")
            return 0
    
    async def _prune_low_confidence(self, dry_run: bool = False) -> int:
        """
        Remove facts with low confidence after grace period.
        
        Low confidence facts might be:
        - Uncertain extractions
        - Facts that were corrected by user
        - Inferences that weren't validated
        """
        grace_threshold = datetime.now(timezone.utc) - timedelta(days=self.confidence_grace_days)
        grace_str = grace_threshold.isoformat()
        
        try:
            async with db_manager.neo4j_driver.session() as session:
                if dry_run:
                    query = """
                    MATCH (n)-[r:FACT]->(e:Entity)
                    WHERE r.confidence IS NOT NULL 
                      AND r.confidence < $min_confidence
                      AND r.created_at < $grace_threshold
                      AND r.bot_name = $bot_name
                    RETURN count(r) as count
                    """
                else:
                    query = """
                    MATCH (n)-[r:FACT]->(e:Entity)
                    WHERE r.confidence IS NOT NULL 
                      AND r.confidence < $min_confidence
                      AND r.created_at < $grace_threshold
                      AND r.bot_name = $bot_name
                    DELETE r
                    RETURN count(*) as count
                    """
                
                result = await session.run(
                    query,
                    min_confidence=self.min_confidence,
                    grace_threshold=grace_str,
                    bot_name=self.bot_name
                )
                record = await result.single()
                return record["count"] if record else 0
                
        except Exception as e:
            logger.error(f"Failed to prune low-confidence facts: {e}")
            return 0
    
    async def get_graph_health_report(self) -> Dict[str, Any]:
        """
        Generate a health report for the knowledge graph.
        
        Returns metrics useful for monitoring graph growth and quality.
        """
        if not db_manager.neo4j_driver:
            return {"error": "Neo4j not available"}
        
        try:
            async with db_manager.neo4j_driver.session() as session:
                report = {}
                
                # Total counts
                node_count, edge_count = await self._get_graph_counts()
                report["total_nodes"] = node_count
                report["total_edges"] = edge_count
                
                # Counts by label
                label_query = """
                MATCH (n)
                WITH labels(n) as labels
                UNWIND labels as label
                RETURN label, count(*) as count
                ORDER BY count DESC
                """
                label_result = await session.run(label_query)
                label_records = await label_result.data()
                report["nodes_by_label"] = {r["label"]: r["count"] for r in label_records}
                
                # Orphan count (potential prune targets)
                orphan_query = """
                MATCH (e:Entity)
                WHERE NOT (e)<-[:FACT]-()
                  AND NOT (e)-[:FACT]->()
                RETURN count(e) as count
                """
                orphan_result = await session.run(orphan_query)
                orphan_record = await orphan_result.single()
                report["orphan_entities"] = orphan_record["count"] if orphan_record else 0
                
                # Stale facts count
                stale_threshold = datetime.now(timezone.utc) - timedelta(days=self.stale_fact_days)
                stale_query = """
                MATCH ()-[r:FACT]->()
                WHERE r.created_at < $threshold
                  AND (r.last_accessed IS NULL OR r.last_accessed < $threshold)
                RETURN count(r) as count
                """
                stale_result = await session.run(stale_query, threshold=stale_threshold.isoformat())
                stale_record = await stale_result.single()
                report["stale_facts"] = stale_record["count"] if stale_record else 0
                
                # Low confidence count
                low_conf_query = """
                MATCH ()-[r:FACT]->()
                WHERE r.confidence IS NOT NULL AND r.confidence < $threshold
                RETURN count(r) as count
                """
                low_conf_result = await session.run(low_conf_query, threshold=self.min_confidence)
                low_conf_record = await low_conf_result.single()
                report["low_confidence_facts"] = low_conf_record["count"] if low_conf_record else 0
                
                # Bot-specific counts
                bot_query = """
                MATCH ()-[r:FACT]->()
                WHERE r.bot_name = $bot_name
                RETURN count(r) as count
                """
                bot_result = await session.run(bot_query, bot_name=self.bot_name)
                bot_record = await bot_result.single()
                report["facts_for_bot"] = bot_record["count"] if bot_record else 0
                
                return report
                
        except Exception as e:
            logger.error(f"Failed to generate graph health report: {e}")
            return {"error": str(e)}


# Singleton instance
_pruner_instance: Optional[KnowledgeGraphPruner] = None


def get_pruner(bot_name: Optional[str] = None) -> KnowledgeGraphPruner:
    """Get or create the pruner singleton."""
    global _pruner_instance
    if _pruner_instance is None or (bot_name and _pruner_instance.bot_name != bot_name):
        _pruner_instance = KnowledgeGraphPruner(bot_name)
    return _pruner_instance


async def run_scheduled_prune() -> PruningStats:
    """
    Entry point for scheduled pruning task.
    Called by the scheduler on a weekly basis.
    """
    if not getattr(settings, 'ENABLE_GRAPH_PRUNING', False):
        logger.debug("Graph pruning disabled")
        return PruningStats()
    
    pruner = get_pruner()
    return await pruner.run_full_prune()
