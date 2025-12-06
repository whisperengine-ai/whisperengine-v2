from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime, timezone, timedelta
from loguru import logger
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue, MatchAny, Range

from src_v2.core.database import db_manager
from src_v2.memory.embeddings import EmbeddingService
from src_v2.config.settings import settings

class SharedArtifactManager:
    COLLECTION_NAME = "whisperengine_shared_artifacts"
    
    def __init__(self):
        self.embedding_service = EmbeddingService()

    async def store_artifact(
        self,
        artifact_type: str,
        content: str,
        source_bot: str,
        user_id: Optional[str] = None,
        confidence: float = 0.8,
        metadata: Dict = {}
    ) -> str:
        """Store an artifact in the shared pool."""
        if not db_manager.qdrant_client:
            logger.warning("Qdrant client not available, skipping shared artifact storage.")
            return ""

        try:
            embedding = await self.embedding_service.embed_query_async(content)
            point_id = str(uuid.uuid4())
            
            payload = {
                "type": artifact_type,
                "content": content,
                "source_bot": source_bot,
                "user_id": user_id,
                "confidence": confidence,
                "created_at": datetime.now(timezone.utc).isoformat(),
                **metadata
            }

            await db_manager.qdrant_client.upsert(
                collection_name=self.COLLECTION_NAME,
                points=[PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=payload
                )]
            )
            logger.info(f"Stored shared artifact {point_id} ({artifact_type}) from {source_bot}")
            return point_id
        except Exception as e:
            logger.error(f"Failed to store shared artifact: {e}")
            return ""
    
    async def discover_artifacts(
        self,
        query: str,
        artifact_types: Optional[List[str]] = None,
        exclude_bot: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Discover artifacts from other bots."""
        if not db_manager.qdrant_client:
            return []

        try:
            embedding = await self.embedding_service.embed_query_async(query)
            
            must_conditions = []
            must_not_conditions = []
            
            if artifact_types:
                # Match any of the specified types
                must_conditions.append(
                    FieldCondition(key="type", match=MatchAny(any=artifact_types))
                )
            
            if exclude_bot:
                must_not_conditions.append(
                    FieldCondition(key="source_bot", match=MatchValue(value=exclude_bot))
                )
            
            if user_id:
                must_conditions.append(
                    FieldCondition(key="user_id", match=MatchValue(value=user_id))
                )
            
            # Only include artifacts with high confidence
            must_conditions.append(
                FieldCondition(key="confidence", range=Range(gte=settings.STIGMERGIC_CONFIDENCE_THRESHOLD))
            )

            filter_obj = Filter(must=must_conditions, must_not=must_not_conditions)
            
            results = await db_manager.qdrant_client.query_points(
                collection_name=self.COLLECTION_NAME,
                query=embedding,
                query_filter=filter_obj if must_conditions or must_not_conditions else None,
                limit=limit,
                with_payload=True
            )
            
            return [
                {
                    "id": hit.id,
                    "score": hit.score,
                    "type": (hit.payload or {}).get("type"),
                    "content": (hit.payload or {}).get("content"),
                    "source_bot": (hit.payload or {}).get("source_bot"),
                    "user_id": (hit.payload or {}).get("user_id"),
                    "created_at": (hit.payload or {}).get("created_at"),
                    "metadata": hit.payload or {}
                }
                for hit in results.points
            ]
        except Exception as e:
            logger.error(f"Failed to discover shared artifacts: {e}")
            return []

    async def get_gossip_for_bot(self, bot_name: str, hours: int) -> List[Dict[str, Any]]:
        """
        Get gossip relevant to a specific bot from both shared and private sources.
        
        Aggregates:
        1. Universe Gossip (Shared Collection):
           - Must be type="gossip"
           - Must NOT be from self
           - Must have bot_name in "eligible_recipients" (Privacy Check)
           
        2. Cross-Bot Chat (Per-Bot Collection):
           - Must be type="gossip" AND is_cross_bot=True
           
        Args:
            bot_name: The bot requesting gossip
            hours: Look back window in hours
            
        Returns:
            List of gossip items
        """
        gossip = []
        threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
        threshold_iso = threshold.isoformat()
        
        if not db_manager.qdrant_client:
            return []
            
        # 1. Query Shared Artifacts (Universe Gossip)
        try:
            shared_results = await db_manager.qdrant_client.scroll(
                collection_name=self.COLLECTION_NAME,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="type", match=MatchValue(value="gossip")),
                        # PRIVACY CHECK: Only show if this bot was eligible to receive it
                        FieldCondition(key="eligible_recipients", match=MatchValue(value=bot_name))
                    ],
                    must_not=[
                        # Don't show own gossip
                        FieldCondition(key="source_bot", match=MatchValue(value=bot_name))
                    ]
                ),
                limit=10,
                with_payload=True,
                with_vectors=False
            )
            
            for point in shared_results[0]:
                if point.payload:
                    ts = point.payload.get("created_at", "")
                    if ts >= threshold_iso:
                        gossip.append({
                            "source_bot": point.payload.get("source_bot", "another character"),
                            "content": point.payload.get("content", ""),
                            "topic": point.payload.get("topic", ""),
                            "is_cross_bot": False,
                            "source": "universe"
                        })
        except Exception as e:
            logger.warning(f"Failed to fetch shared gossip for {bot_name}: {e}")

        # 2. Query Per-Bot Collection (Cross-Bot Chat)
        try:
            # Per-bot collection name convention
            bot_collection = f"whisperengine_memory_{bot_name}"
            
            crossbot_results = await db_manager.qdrant_client.scroll(
                collection_name=bot_collection,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="type", match=MatchValue(value="gossip")),
                        FieldCondition(key="is_cross_bot", match=MatchValue(value=True))
                    ]
                ),
                limit=10,
                with_payload=True,
                with_vectors=False
            )
            
            for point in crossbot_results[0]:
                if point.payload:
                    ts = point.payload.get("timestamp", "")
                    if ts >= threshold_iso:
                        gossip.append({
                            "source_bot": point.payload.get("source_bot", "another character"),
                            "content": point.payload.get("content", ""),
                            "topic": point.payload.get("topic", ""),
                            "is_cross_bot": True,
                            "source": "direct_chat"
                        })
        except Exception as e:
            # It's okay if collection doesn't exist yet
            logger.debug(f"Failed to fetch cross-bot gossip for {bot_name}: {e}")
            
        return gossip

# Global singleton
shared_artifact_manager = SharedArtifactManager()
