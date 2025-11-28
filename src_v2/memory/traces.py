"""
Reasoning Trace Quality Scoring and Retrieval

Phase 3.2: Memory of Reasoning (Learning)

This module provides quality scoring for reasoning traces and retrieval
of high-quality traces for few-shot injection in the ReflectiveAgent.

Quality scoring formula:
- Base: 10 points for successful outcome
- Efficiency bonus: +5 if fewer steps than average
- Retry penalty: -5 if trace had tool failures/retries
- User feedback: +/- based on InfluxDB reactions
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from loguru import logger
from influxdb_client.client.write.point import Point

from src_v2.config.settings import settings
from src_v2.core.database import db_manager
from src_v2.memory.manager import memory_manager
from src_v2.evolution.feedback import FeedbackAnalyzer


@dataclass
class ScoredTrace:
    """A reasoning trace with quality score metadata."""
    content: str
    query_pattern: str
    successful_approach: str
    tools_used: List[str]
    complexity: str
    quality_score: float
    similarity_score: float
    
    def to_few_shot_example(self) -> str:
        """Format trace as a few-shot example for the LLM."""
        return (
            f"[EXAMPLE: Similar problem solved successfully]\n"
            f"Problem Type: {self.query_pattern}\n"
            f"Approach: {self.successful_approach}\n"
            f"Tools Used: {', '.join(self.tools_used)}\n"
            f"---"
        )


class TraceQualityScorer:
    """
    Scores reasoning traces for quality before using as few-shot examples.
    
    Quality criteria:
    1. Outcome: Was the trace from a successful interaction?
    2. Efficiency: Did it solve the problem in fewer steps than average?
    3. Stability: Did it require retries or have tool failures?
    4. User Feedback: What was the user's reaction (via InfluxDB)?
    """
    
    # Scoring weights (from spec)
    SUCCESS_BONUS = 10
    EFFICIENCY_BONUS = 5
    RETRY_PENALTY = -5
    MAX_FEEDBACK_BONUS = 5  # Scale user feedback -5 to +5
    
    # Thresholds
    AVERAGE_TOOLS_USED = 3  # Baseline for efficiency comparison
    MIN_QUALITY_THRESHOLD = 5.0  # Minimum score to use as few-shot
    
    def __init__(self):
        self.feedback_analyzer = FeedbackAnalyzer()
    
    async def score_trace(
        self,
        trace: Dict[str, Any],
        message_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> float:
        """
        Calculate quality score for a reasoning trace.
        
        Args:
            trace: Trace dict from Qdrant with content and metadata
            message_id: Optional Discord message ID for feedback lookup
            user_id: Optional user ID for feedback lookup
            
        Returns:
            Quality score (higher = better, typically 0-20 range)
        """
        score = 0.0
        metadata = trace.get("metadata", {})
        
        # 1. Base success score (all stored traces are assumed successful)
        score += self.SUCCESS_BONUS
        
        # 2. Efficiency bonus: fewer tools than average
        tools_used = metadata.get("tools_used", [])
        if isinstance(tools_used, str):
            tools_used = tools_used.split(",")
        num_tools = len(tools_used)
        
        if num_tools < self.AVERAGE_TOOLS_USED:
            score += self.EFFICIENCY_BONUS
            logger.debug(f"Trace efficiency bonus: used {num_tools} tools (< {self.AVERAGE_TOOLS_USED})")
        
        # 3. Retry penalty: check if trace mentions retries
        content = trace.get("content", "")
        if "retry" in content.lower() or "failed" in content.lower():
            score += self.RETRY_PENALTY
            logger.debug("Trace retry penalty applied")
        
        # 4. User feedback bonus (from InfluxDB reactions)
        if message_id and user_id:
            try:
                feedback = await self.feedback_analyzer.get_feedback_score(message_id, user_id)
                if feedback:
                    # Scale feedback score (-1 to +1) to (-5 to +5)
                    feedback_bonus = feedback["score"] * self.MAX_FEEDBACK_BONUS
                    score += feedback_bonus
                    logger.debug(f"Trace feedback bonus: {feedback_bonus:.2f}")
            except Exception as e:
                logger.warning(f"Failed to get feedback score for trace: {e}")
        
        return score
    
    def parse_trace_content(self, trace: Dict[str, Any]) -> Optional[ScoredTrace]:
        """
        Parse a raw trace dict into a structured ScoredTrace object.
        
        Args:
            trace: Raw trace dict from Qdrant
            
        Returns:
            ScoredTrace if parsing succeeds, None otherwise
        """
        try:
            metadata = trace.get("metadata", {})
            content = trace.get("content", "")
            
            # Extract fields from metadata (stored by StoreReasoningTraceTool)
            query_pattern = metadata.get("query_pattern", "unknown")
            complexity = metadata.get("complexity", "COMPLEX_MID")
            
            # Parse tools_used (could be list or comma-separated string)
            tools_used = metadata.get("tools_used", [])
            if isinstance(tools_used, str):
                tools_used = [t.strip() for t in tools_used.split(",")]
            
            # Extract approach from content (format: "Approach: <approach>")
            successful_approach = ""
            for line in content.split("\n"):
                if line.startswith("Approach:"):
                    successful_approach = line.replace("Approach:", "").strip()
                    break
            
            return ScoredTrace(
                content=content,
                query_pattern=query_pattern,
                successful_approach=successful_approach,
                tools_used=tools_used,
                complexity=complexity,
                quality_score=0.0,  # Set later by score_trace
                similarity_score=trace.get("score", 0.0)
            )
        except Exception as e:
            logger.warning(f"Failed to parse trace: {e}")
            return None


class TraceRetriever:
    """
    Retrieves high-quality reasoning traces for few-shot injection.
    
    Used by ReflectiveAgent to inject successful past approaches
    as examples before starting the reasoning loop.
    """
    
    # Configuration
    SIMILARITY_THRESHOLD = 0.75  # Minimum similarity to consider trace relevant
    MAX_TRACES_TO_SCORE = 5  # How many traces to retrieve and score
    MAX_TRACES_TO_INJECT = 2  # How many to actually inject as few-shot
    
    def __init__(self):
        self.scorer = TraceQualityScorer()
    
    async def get_relevant_traces(
        self,
        query: str,
        user_id: str,
        collection_name: Optional[str] = None,
        include_negative: bool = False
    ) -> List[ScoredTrace]:
        """
        Find and score relevant reasoning traces for a query.
        
        Args:
            query: The user's current query
            user_id: User ID for filtering traces
            collection_name: Qdrant collection name
            include_negative: Whether to include negative examples (failure traces)
            
        Returns:
            List of ScoredTrace objects sorted by quality score (best first)
        """
        if not settings.ENABLE_TRACE_LEARNING:
            return []
        
        try:
            # 1. Search for similar traces
            raw_traces = await memory_manager.search_reasoning_traces(
                query=query,
                user_id=user_id,
                limit=self.MAX_TRACES_TO_SCORE,
                collection_name=collection_name
            )
            
            if not raw_traces:
                logger.debug("No reasoning traces found for query")
                return []
            
            # 2. Filter by similarity threshold
            similar_traces = [
                t for t in raw_traces
                if t.get("score", 0) >= self.SIMILARITY_THRESHOLD
            ]
            
            if not similar_traces:
                logger.debug(f"No traces above similarity threshold ({self.SIMILARITY_THRESHOLD})")
                return []
            
            # 3. Parse and score each trace
            scored_traces: List[ScoredTrace] = []
            for trace in similar_traces:
                parsed = self.scorer.parse_trace_content(trace)
                if parsed:
                    # Calculate quality score
                    quality = await self.scorer.score_trace(trace, user_id=user_id)
                    parsed.quality_score = quality
                    
                    # Only include traces above minimum quality
                    if quality >= TraceQualityScorer.MIN_QUALITY_THRESHOLD:
                        scored_traces.append(parsed)
                    else:
                        logger.debug(f"Trace below quality threshold: {quality:.2f}")
            
            # 4. Sort by quality score (best first)
            scored_traces.sort(key=lambda t: t.quality_score, reverse=True)
            
            # 5. Limit to max injection count
            result = scored_traces[:self.MAX_TRACES_TO_INJECT]
            
            if result:
                logger.info(f"Found {len(result)} high-quality traces for few-shot injection")
                for t in result:
                    logger.debug(f"  - {t.query_pattern} (quality={t.quality_score:.2f}, similarity={t.similarity_score:.2f})")
                
                # Log metric to InfluxDB
                self._log_trace_reuse_metric(result, user_id)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to retrieve reasoning traces: {e}")
            return []
    
    def _log_trace_reuse_metric(self, traces: List[ScoredTrace], user_id: str) -> None:
        """Log trace reuse event to InfluxDB for metrics tracking."""
        if not db_manager.influxdb_write_api:
            return
        
        try:
            bot_name = settings.DISCORD_BOT_NAME or "default"
            for trace in traces:
                point = Point("trace_reused") \
                    .tag("bot_name", bot_name) \
                    .tag("user_id", user_id) \
                    .tag("problem_type", trace.query_pattern[:50]) \
                    .tag("complexity", trace.complexity) \
                    .field("quality_score", trace.quality_score) \
                    .field("similarity_score", trace.similarity_score)
                
                db_manager.influxdb_write_api.write(
                    bucket=settings.INFLUXDB_BUCKET,
                    org=settings.INFLUXDB_ORG,
                    record=point
                )
        except Exception as e:
            logger.warning(f"Failed to log trace reuse metric: {e}")
    
    def format_few_shot_section(self, traces: List[ScoredTrace]) -> str:
        """
        Format traces as a few-shot section for the system prompt.
        
        Args:
            traces: List of scored traces to format
            
        Returns:
            Formatted string to inject into system prompt
        """
        if not traces:
            return ""
        
        sections = ["SIMILAR PROBLEMS YOU'VE SOLVED BEFORE:"]
        for trace in traces:
            sections.append(trace.to_few_shot_example())
        sections.append("")  # Trailing newline
        
        return "\n".join(sections)


# Global instances
trace_scorer = TraceQualityScorer()
trace_retriever = TraceRetriever()
