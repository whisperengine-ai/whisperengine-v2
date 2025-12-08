from typing import List, Optional
import uuid
from loguru import logger
from pydantic import BaseModel, Field

from src_v2.core.database import db_manager
from src_v2.memory.manager import MemoryManager

class SummaryResult(BaseModel):
    summary: str = Field(description="The concise summary of the conversation. Include key topics and facts.")
    meaningfulness_score: int = Field(description="A score from 1-5 indicating how meaningful/deep the conversation was. 1=Trivial, 5=Profound.")
    emotions: List[str] = Field(description="List of prevailing emotions detected in the conversation.")
    topics: List[str] = Field(default_factory=list, description="List of 1-5 key topics or themes discussed (e.g., 'career anxiety', 'favorite movies', 'childhood memories').")

class SummaryManager:
    def __init__(self, bot_name: Optional[str] = None):
        self.memory_manager = MemoryManager(bot_name=bot_name)

    async def save_summary(self, session_id: str, user_id: str, result: SummaryResult, user_name: Optional[str] = None) -> bool:
        """
        Saves the summary to Postgres and Qdrant.
        
        Args:
            user_name: User's display name (for diary provenance)
            
        Returns:
            True if saved successfully, False otherwise
        """
        if not db_manager.postgres_pool:
            return False

        try:
            # 1. Save to Postgres
            summary_id = uuid.uuid4()
            async with db_manager.postgres_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO v2_summaries (id, session_id, content, meaningfulness_score)
                    VALUES ($1, $2, $3, $4)
                """, summary_id, session_id, result.summary, result.meaningfulness_score)
            
            logger.info(f"Summary saved to Postgres: {summary_id}")
            
            # Call MemoryManager to save vector
            embedding_id = await self.memory_manager.save_summary_vector(
                session_id=session_id,
                user_id=user_id,
                content=result.summary,
                meaningfulness_score=result.meaningfulness_score,
                emotions=result.emotions,
                topics=result.topics,
                user_name=user_name
            )
            
            if embedding_id:
                # Update Postgres with embedding_id
                async with db_manager.postgres_pool.acquire() as conn:
                    await conn.execute("""
                        UPDATE v2_summaries 
                        SET embedding_id = $1 
                        WHERE id = $2
                    """, uuid.UUID(embedding_id), summary_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save summary to DB: {e}")
            return False
