"""
Personality Drift Observation (Phase E16: Feedback Loop Stability)

Weekly job that compares recent response embeddings to baseline.
This is OBSERVATION ONLY - we don't auto-correct, just track.

Philosophy: Observe first, constrain only what's proven problematic.

Thresholds:
- Green: drift < 0.2 (normal variation)
- Yellow: 0.2-0.4 (watch for sustained drift)
- Red: > 0.4 (review needed if sustained 2+ weeks)
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from loguru import logger
import numpy as np

from src_v2.core.database import db_manager
from src_v2.config.settings import settings
from src_v2.memory.embeddings import EmbeddingService


# Cache for baseline embeddings (computed once per bot)
_baseline_cache: Dict[str, np.ndarray] = {}


async def get_or_create_baseline(
    bot_name: str,
    embedding_service: EmbeddingService
) -> Optional[np.ndarray]:
    """
    Get or create the baseline embedding for a bot.
    
    Baseline is the average embedding of the first 100 responses,
    representing the character's "natural voice".
    
    Args:
        bot_name: Character name
        embedding_service: Service to generate embeddings
        
    Returns:
        Baseline embedding vector or None if insufficient data
    """
    # Check cache first
    if bot_name in _baseline_cache:
        return _baseline_cache[bot_name]
    
    if not db_manager.postgres_pool:
        return None
    
    try:
        async with db_manager.postgres_pool.acquire() as conn:
            # Get the first 100 assistant responses (baseline period)
            rows = await conn.fetch("""
                SELECT content 
                FROM v2_chat_history 
                WHERE character_name = $1 AND role = 'assistant'
                ORDER BY timestamp ASC 
                LIMIT 100
            """, bot_name)
            
            if len(rows) < 50:
                logger.debug(f"Not enough baseline data for {bot_name} ({len(rows)} responses)")
                return None
            
            # Embed all responses
            embeddings = []
            for row in rows:
                content = row["content"]
                if content and len(content) > 10:
                    emb = await embedding_service.embed_query_async(content[:1000])
                    embeddings.append(emb)
            
            if len(embeddings) < 50:
                return None
            
            # Average to create baseline
            baseline = np.mean(embeddings, axis=0)
            _baseline_cache[bot_name] = baseline
            
            logger.info(f"Created baseline embedding for {bot_name} from {len(embeddings)} responses")
            return baseline
            
    except Exception as e:
        logger.error(f"Failed to create baseline for {bot_name}: {e}")
        return None


async def get_recent_responses(
    bot_name: str,
    days: int = 7
) -> List[Dict[str, Any]]:
    """
    Get recent assistant responses for drift analysis.
    
    Args:
        bot_name: Character name
        days: How far back to look
        
    Returns:
        List of response dicts with 'content' field
    """
    if not db_manager.postgres_pool:
        return []
    
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        async with db_manager.postgres_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT content, timestamp 
                FROM v2_chat_history 
                WHERE character_name = $1 AND role = 'assistant'
                AND timestamp > $2
                ORDER BY timestamp DESC 
                LIMIT 100
            """, bot_name, cutoff)
            
            return [{"content": row["content"], "created_at": row["timestamp"]} for row in rows]
            
    except Exception as e:
        logger.error(f"Failed to get recent responses for {bot_name}: {e}")
        return []


async def calculate_personality_drift(
    bot_name: str,
    days: int = 7
) -> Optional[float]:
    """
    Calculate personality drift from baseline.
    
    Compares the average embedding of recent responses to the
    baseline embedding using cosine distance.
    
    Args:
        bot_name: Character name
        days: How far back to analyze
        
    Returns:
        Drift score (0.0 = identical, 1.0 = completely different)
        or None if insufficient data
    """
    embedding_service = EmbeddingService()
    
    # Get baseline
    baseline = await get_or_create_baseline(bot_name, embedding_service)
    if baseline is None:
        return None
    
    # Get recent responses
    recent = await get_recent_responses(bot_name, days)
    if len(recent) < 10:
        logger.debug(f"Not enough recent data for {bot_name} drift analysis ({len(recent)} responses)")
        return None
    
    # Embed recent responses
    embeddings = []
    for r in recent:
        content = r["content"]
        if content and len(content) > 10:
            try:
                emb = await embedding_service.embed_query_async(content[:1000])
                embeddings.append(emb)
            except Exception:
                pass
    
    if len(embeddings) < 10:
        return None
    
    # Average recent embeddings
    recent_avg = np.mean(embeddings, axis=0)
    
    # Calculate cosine distance (1 - cosine similarity)
    # Cosine similarity = dot(a, b) / (norm(a) * norm(b))
    dot_product = np.dot(baseline, recent_avg)
    norm_product = np.linalg.norm(baseline) * np.linalg.norm(recent_avg)
    
    if norm_product == 0:
        return None
    
    cosine_similarity = dot_product / norm_product
    drift = 1 - cosine_similarity
    
    return float(max(0.0, min(1.0, drift)))


async def run_drift_observation(
    ctx: Dict[str, Any],
    bot_name: str
) -> Dict[str, Any]:
    """
    Worker task: Observe personality drift for a bot.
    
    This is a weekly task that:
    1. Calculates drift from baseline
    2. Logs to InfluxDB for Grafana dashboards
    3. Warns if significant drift detected (but does NOT auto-correct)
    
    Args:
        ctx: arq context
        bot_name: Character name
        
    Returns:
        Dict with drift analysis results
    """
    logger.info(f"Running personality drift observation for {bot_name}")
    
    try:
        drift = await calculate_personality_drift(bot_name, days=7)
        
        if drift is None:
            return {
                "success": True,
                "skipped": True,
                "reason": "insufficient_data",
                "bot_name": bot_name
            }
        
        # Log to InfluxDB
        try:
            from influxdb_client.client.write.point import Point
            
            if db_manager.influxdb_write_api:
                # Determine status for alerting
                if drift < 0.2:
                    status = "green"
                elif drift < 0.4:
                    status = "yellow"
                else:
                    status = "red"
                
                point = Point("personality_drift") \
                    .tag("bot_name", bot_name) \
                    .tag("status", status) \
                    .field("drift_score", drift)
                
                db_manager.influxdb_write_api.write(
                    bucket=settings.INFLUXDB_BUCKET,
                    org=settings.INFLUXDB_ORG,
                    record=point
                )
        except Exception as e:
            logger.debug(f"Failed to log drift metrics: {e}")
        
        # Warn if significant (but don't auto-correct - philosophy is observe first)
        if drift > 0.3:
            logger.warning(
                f"Personality drift detected for {bot_name}: {drift:.3f} "
                f"(threshold: 0.3). Review recent responses if sustained."
            )
        else:
            logger.info(f"Personality drift for {bot_name}: {drift:.3f} (normal)")
        
        return {
            "success": True,
            "bot_name": bot_name,
            "drift_score": drift,
            "status": "green" if drift < 0.2 else ("yellow" if drift < 0.4 else "red")
        }
        
    except Exception as e:
        logger.error(f"Drift observation failed for {bot_name}: {e}")
        return {
            "success": False,
            "error": str(e),
            "bot_name": bot_name
        }


async def run_all_drift_observations(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Worker task: Run drift observation for all active bots.
    
    Designed to be scheduled weekly via arq cron.
    """
    from pathlib import Path
    
    logger.info("Running weekly personality drift observations for all bots")
    
    results = {}
    
    # Find all character directories
    characters_dir = Path("characters")
    if not characters_dir.exists():
        return {"success": False, "error": "no_characters_dir"}
    
    for char_dir in characters_dir.iterdir():
        if char_dir.is_dir() and (char_dir / "character.md").exists():
            bot_name = char_dir.name
            result = await run_drift_observation(ctx, bot_name)
            results[bot_name] = result
    
    return {
        "success": True,
        "observations": results,
        "count": len(results)
    }
