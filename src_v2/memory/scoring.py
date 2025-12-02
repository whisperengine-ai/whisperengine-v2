"""
Memory Scoring Module (Phase E16: Feedback Loop Stability)

Provides temporal decay and source-type weighting for memories.
This ensures recent, direct observations have more influence than
old gossip-derived content, while preserving cross-bot mythology.

Philosophy: Observe first, constrain only what's proven problematic.
"""
from datetime import datetime, timezone
from typing import Dict, Any, Optional


# ============================================================================
# Temporal Decay Rates
# ============================================================================

# How quickly different memory types decay over time (per day)
# Higher = slower decay (more persistent)
DECAY_RATES = {
    "conversation": 0.98,      # Direct user observations decay slowest
    "episode": 0.98,           # Raw message exchanges
    "session_summary": 0.97,   # Session summaries
    "summary": 0.97,           # Alias for session_summary
    "diary": 0.95,             # Daily diary entries
    "observation": 0.94,       # Stigmergic observations
    "gossip": 0.93,            # Cross-bot gossip
    "dream": 0.90,             # Abstract dream content decays fastest
}

# Default decay rate for unknown types
DEFAULT_DECAY_RATE = 0.95


# ============================================================================
# Source Type Weights
# ============================================================================

# Base influence weight by source type
# Higher = more trusted/influential
SOURCE_WEIGHTS = {
    # New Enum Values
    "human_direct": 1.0,         # Direct observation of user input (Highest trust)
    "inference": 0.8,            # AI thought/reasoning trace (Medium trust)
    "dream": 0.5,                # Generated during dream cycle (Lower trust)
    "gossip": 0.4,               # Heard from another bot (Low trust)
    "observation": 0.6,          # Stigmergic observation of environment
    "diary": 0.7,                # Self-reflection in diary
    "summary": 0.9,              # Compressed history

    # Legacy/Compat Values
    "direct_conversation": 1.0,  # User said this directly
    "episode": 1.0,              # Raw message
    "conversation": 1.0,         # Conversation memory
    "session_summary": 0.9,      # Summarized conversation
    "own_diary": 0.7,            # Character's own diary
    "own_dream": 0.5,            # Character's own dream
    "other_diary": 0.3,          # Another bot's diary
    "other_dream": 0.2,          # Another bot's dream
}

# Default source weight for unknown types
DEFAULT_SOURCE_WEIGHT = 0.5


# ============================================================================
# Scoring Functions
# ============================================================================

def calculate_temporal_weight(
    memory: Dict[str, Any],
    reference_time: Optional[datetime] = None
) -> float:
    """
    Calculate time-based weight for a memory.
    
    Older memories have less influence, with decay rate based on memory type.
    High-meaningfulness memories decay slower (protected).
    
    Args:
        memory: Memory dict with 'created_at', 'type', 'meaningfulness'
        reference_time: Time to calculate age from (default: now)
        
    Returns:
        Weight between 0.0 and 1.0
    """
    # Get creation time
    created_at_raw = memory.get("created_at") or memory.get("timestamp")
    if not created_at_raw:
        return 1.0  # No timestamp, assume recent
    
    # Parse timestamp
    if isinstance(created_at_raw, str):
        try:
            created_at = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
        except ValueError:
            return 1.0
    elif isinstance(created_at_raw, datetime):
        created_at = created_at_raw
    else:
        return 1.0
    
    # Ensure timezone aware
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    
    # Calculate age in days
    ref_time = reference_time or datetime.now(timezone.utc)
    age_days = (ref_time - created_at).total_seconds() / 86400
    
    if age_days <= 0:
        return 1.0
    
    # Get base decay rate for memory type
    memory_type = memory.get("type", "conversation")
    decay_rate = DECAY_RATES.get(memory_type, DEFAULT_DECAY_RATE)
    
    # Meaningfulness protection: high-meaning memories decay slower
    # Score 1-5, centered at 3
    meaningfulness = memory.get("meaningfulness") or memory.get("meaningfulness_score") or 3
    if isinstance(meaningfulness, str):
        try:
            meaningfulness = int(meaningfulness)
        except ValueError:
            meaningfulness = 3
    
    # Adjust decay rate: +0.01 per meaningfulness point above 3
    adjusted_decay = decay_rate + (0.01 * (meaningfulness - 3))
    adjusted_decay = min(0.99, max(0.85, adjusted_decay))
    
    # Calculate weight with exponential decay
    weight = adjusted_decay ** age_days
    
    return max(0.0, min(1.0, weight))


def calculate_source_weight(memory: Dict[str, Any]) -> float:
    """
    Calculate weight based on source type.
    
    Direct observations are weighted higher than derived/gossip content.
    
    Args:
        memory: Memory dict with 'type' or 'source' field
        
    Returns:
        Weight between 0.0 and 1.0
    """
    # Check multiple possible field names
    source_type = (
        memory.get("source_type") or 
        memory.get("source") or 
        memory.get("type") or 
        "conversation"
    )
    
    return SOURCE_WEIGHTS.get(source_type, DEFAULT_SOURCE_WEIGHT)


def calculate_composite_score(
    memory: Dict[str, Any],
    semantic_similarity: float,
    weights: Optional[Dict[str, float]] = None
) -> float:
    """
    Combine temporal, semantic, and source type scores into a composite score.
    
    Default weights:
    - Semantic similarity: 50%
    - Temporal freshness: 30%
    - Source type trust: 20%
    
    Args:
        memory: Memory dict with scoring metadata
        semantic_similarity: Semantic match score (0.0-1.0)
        weights: Optional custom weights dict
        
    Returns:
        Composite score between 0.0 and 1.0
    """
    # Default weights
    w = weights or {
        "semantic": 0.5,
        "temporal": 0.3,
        "source": 0.2,
    }
    
    # Calculate component scores
    temporal = calculate_temporal_weight(memory)
    source = calculate_source_weight(memory)
    
    # Combine
    composite = (
        semantic_similarity * w.get("semantic", 0.5) +
        temporal * w.get("temporal", 0.3) +
        source * w.get("source", 0.2)
    )
    
    return max(0.0, min(1.0, composite))


def rerank_memories(
    memories: list,
    score_field: str = "score",
    weights: Optional[Dict[str, float]] = None
) -> list:
    """
    Re-rank a list of memories using composite scoring.
    
    Args:
        memories: List of memory dicts with semantic scores
        score_field: Field name containing semantic similarity score
        weights: Optional custom weights
        
    Returns:
        Memories sorted by composite score (descending)
    """
    scored = []
    for mem in memories:
        semantic = mem.get(score_field, 0.5)
        composite = calculate_composite_score(mem, semantic, weights)
        scored.append({
            **mem,
            "composite_score": composite,
            "temporal_weight": calculate_temporal_weight(mem),
            "source_weight": calculate_source_weight(mem),
        })
    
    # Sort by composite score descending
    scored.sort(key=lambda x: x["composite_score"], reverse=True)
    
    return scored


# ============================================================================
# Metrics Helpers
# ============================================================================

def calculate_source_distribution(memories: list) -> Dict[str, float]:
    """
    Calculate the distribution of source types in a memory set.
    
    Useful for observing what's feeding into narratives.
    
    Args:
        memories: List of memory dicts
        
    Returns:
        Dict mapping source type to percentage (0.0-1.0)
    """
    if not memories:
        return {}
    
    type_counts: Dict[str, int] = {}
    for mem in memories:
        source_type = mem.get("type") or mem.get("source_type") or "unknown"
        type_counts[source_type] = type_counts.get(source_type, 0) + 1
    
    total = len(memories)
    return {k: v / total for k, v in type_counts.items()}


def calculate_gossip_ratio(memories: list) -> float:
    """
    Calculate what percentage of memories are gossip-derived.
    
    Used for observing feedback loop health.
    Green: <40%, Yellow: 40-60%, Red: >60%
    
    Args:
        memories: List of memory dicts
        
    Returns:
        Ratio of gossip-derived memories (0.0-1.0)
    """
    if not memories:
        return 0.0
    
    gossip_types = {"gossip", "other_diary", "other_dream"}
    gossip_count = sum(
        1 for mem in memories 
        if (mem.get("type") or mem.get("source_type", "")) in gossip_types
    )
    
    return gossip_count / len(memories)
