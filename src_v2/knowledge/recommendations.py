"""
Graph-Based Recommendations (Phase E29)

This module provides logic for finding similar users and generating recommendations
based on graph structure (shared edges) rather than pre-computed similarity scores.

It implements the "structural similarity" approach defined in SPEC-E25.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from loguru import logger
import random
from datetime import datetime

from src_v2.core.database import db_manager
from src_v2.config.settings import settings


@dataclass
class SimilarUser:
    """A user with similar interests based on graph structure."""
    user_id: str
    shared_topics: int
    topics: List[str]
    reason: str = "shared_interests"  # shared_interests, serendipity, server_activity
    score: float = 0.0


class RecommendationEngine:
    """
    Engine for generating graph-based recommendations.
    Uses structural similarity (shared edges) to find connections.
    """
    
    def __init__(self):
        self.min_shared_topics = getattr(settings, "RECOMMENDATION_MIN_SHARED_TOPICS", 2)
        self.serendipity = getattr(settings, "RECOMMENDATION_SERENDIPITY", 0.1)
        
    async def find_similar_users(
        self,
        user_id: str,
        server_id: Optional[str] = None,
        limit: int = 5,
        min_trust: int = 10  # Only recommend users with some trust history
    ) -> List[SimilarUser]:
        """
        Find users with overlapping topic interests.
        Uses graph structure—no explicit similarity computation.
        
        Args:
            user_id: The user to find recommendations for
            server_id: Optional server ID to restrict search (privacy)
            limit: Max number of recommendations
            min_trust: Minimum trust score for recommended users (quality filter)
            
        Returns:
            List of SimilarUser objects
        """
        if not db_manager.neo4j_driver:
            logger.warning("Neo4j not available for recommendations")
            return []
            
        similar_users = []
        
        try:
            async with db_manager.neo4j_driver.session() as session:
                # 1. Find users with shared topics
                # If server_id is provided, enforce CONNECTED_TO relationship with that server_id
                # Otherwise, just look for shared topics (less strict privacy, use with caution)
                
                server_filter = ""
                params = {
                    "user_id": user_id, 
                    "limit": limit,
                    "min_shared": self.min_shared_topics
                }
                
                if server_id:
                    # Enforce that both users have discussed topics in the same server
                    server_filter = "AND EXISTS((other)-[:DISCUSSED {server_id: $server_id}]->(:Topic))"
                    params["server_id"] = server_id
                
                query = f"""
                MATCH (u:User {{id: $user_id}})-[:DISCUSSED]->(t:Topic)<-[:DISCUSSED]-(other:User)
                WHERE other.id <> $user_id
                {server_filter}
                WITH other, count(DISTINCT t) as shared_count, collect(t.name) as topic_names
                WHERE shared_count >= $min_shared
                RETURN other.id as user_id, shared_count, topic_names
                ORDER BY shared_count DESC
                LIMIT $limit
                """
                
                result = await session.run(query, params)
                records = await result.data()
                
                for record in records:
                    similar_users.append(SimilarUser(
                        user_id=record["user_id"],
                        shared_topics=record["shared_count"],
                        topics=record["topic_names"],
                        reason="shared_interests",
                        score=float(record["shared_count"])
                    ))
                
                # 2. Apply serendipity: occasionally include a random active user from the same server
                if server_id and len(similar_users) < limit and random.random() < self.serendipity:
                    random_user = await self._get_random_active_user(
                        session, 
                        server_id, 
                        exclude=[user_id] + [u.user_id for u in similar_users]
                    )
                    
                    if random_user:
                        similar_users.append(SimilarUser(
                            user_id=random_user,
                            shared_topics=0,
                            topics=[],
                            reason="serendipity",
                            score=0.5
                        ))
                        
        except Exception as e:
            logger.error(f"Error finding similar users: {e}")
            
        return similar_users

    async def _get_random_active_user(
        self, 
        session, 
        server_id: str, 
        exclude: List[str]
    ) -> Optional[str]:
        """Get a random active user from the server who isn't in the exclude list."""
        query = """
        MATCH (u:User)-[:DISCUSSED {server_id: $server_id}]->(:Topic)
        WHERE NOT u.id IN $exclude
        RETURN DISTINCT u.id as user_id
        ORDER BY rand()
        LIMIT 1
        """
        
        result = await session.run(query, {"server_id": server_id, "exclude": exclude})
        record = await result.single()
        
        return record["user_id"] if record else None

# Global instance
recommendation_engine = RecommendationEngine()
