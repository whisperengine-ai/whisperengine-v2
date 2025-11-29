"""
Character Diary System (Phase E2)

Generates private daily diary entries for characters based on their interactions.
These entries provide characters with a sense of inner life and temporal continuity.

The diary entry is:
- Generated nightly (or after significant sessions) by the insight worker
- Stored in Qdrant with type='diary'
- Injected into character context to inform their mood and perspective
"""
from typing import List, Dict, Any, Optional

__all__ = ["DiaryEntry", "DiaryManager", "get_diary_manager"]
from datetime import datetime, timezone, timedelta
import uuid
from loguru import logger
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue

from src_v2.core.database import db_manager
from src_v2.agents.llm_factory import create_llm
from src_v2.memory.embeddings import EmbeddingService
from src_v2.config.settings import settings
from src_v2.safety.content_review import content_safety_checker


class DiaryEntry(BaseModel):
    """Structured output from the diary generation LLM."""
    entry: str = Field(description="The diary entry written in first person from the character's perspective. Should be 2-4 paragraphs, introspective and emotional.")
    mood: str = Field(description="The character's overall mood (e.g., 'contemplative', 'joyful', 'worried', 'peaceful', 'energized')")
    notable_users: List[str] = Field(default_factory=list, description="List of user names who stood out today (memorable interactions)")
    themes: List[str] = Field(default_factory=list, description="Key themes or topics that dominated the day (e.g., 'career advice', 'deep conversations', 'playful banter')")
    emotional_highlights: List[str] = Field(default_factory=list, description="Brief descriptions of emotionally significant moments")


class DiaryManager:
    """
    Manages generation and retrieval of character diary entries.
    """
    
    def __init__(self, bot_name: Optional[str] = None):
        self.bot_name = bot_name or settings.DISCORD_BOT_NAME or "default"
        self.collection_name = f"whisperengine_memory_{self.bot_name}"
        self.embedding_service = EmbeddingService()
        
        # Use utility LLM for diary generation (cheaper, but capable)
        base_llm = create_llm(temperature=0.8, mode="utility")  # Higher temp for creativity
        self.llm = base_llm.with_structured_output(DiaryEntry)
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are {character_name}, writing in your private diary at the end of the day.

CHARACTER CONTEXT:
{character_context}

WRITING STYLE:
- Write in first person ("I", "my", "me")
- Be introspective and emotionally honest
- Reference specific conversations or moments from the day
- Express your genuine feelings about people you interacted with
- Reflect on what you learned or how you grew
- Include your hopes or worries about tomorrow
- Stay in character - use speech patterns and personality traits consistent with who you are

PRIVACY RULES:
- This is YOUR private diary - be vulnerable and honest
- Do NOT include specific secrets users shared in confidence
- Focus on YOUR feelings and reactions, not the details of what was shared
- It's okay to mention user names and general topics

Write 2-4 paragraphs that capture the emotional essence of your day."""),
            ("human", """Here are the session summaries from today:

{summaries}

---
Today's date: {date}
Number of conversations: {conversation_count}
Users you spoke with: {user_names}

Write your diary entry for today.""")
        ])
        
        self.chain = self.prompt | self.llm

    async def generate_diary_entry(
        self,
        summaries: List[Dict[str, Any]],
        character_context: str,
        user_names: List[str]
    ) -> Optional[DiaryEntry]:
        """
        Generates a diary entry from the day's session summaries.
        
        Args:
            summaries: List of summary dicts with 'content', 'emotions', 'topics'
            character_context: Character's purpose, drives, and constitution (from core.yaml)
            user_names: List of display names the character interacted with today
            
        Returns:
            DiaryEntry if successful, None on failure
        """
        if not summaries:
            logger.info(f"No summaries to generate diary for {self.bot_name}")
            return None
        
        # Format summaries for the prompt
        summary_text = ""
        for i, s in enumerate(summaries, 1):
            emotions = ", ".join(s.get("emotions", [])) or "neutral"
            topics = ", ".join(s.get("topics", [])) or "general chat"
            summary_text += f"[Session {i}]\n"
            summary_text += f"Emotions: {emotions}\n"
            summary_text += f"Topics: {topics}\n"
            summary_text += f"Summary: {s.get('content', 'No summary available')}\n\n"
        
        try:
            result = await self.chain.ainvoke({
                "character_name": self.bot_name.title() if self.bot_name else "Character",
                "character_context": character_context,
                "summaries": summary_text,
                "date": datetime.now(timezone.utc).strftime("%B %d, %Y"),
                "conversation_count": len(summaries),
                "user_names": ", ".join(user_names) if user_names else "no one specific"
            })
            
            # Cast to DiaryEntry (LLM returns structured output)
            if isinstance(result, DiaryEntry):
                # Safety Review (Phase S1)
                review = await content_safety_checker.review_content(result.entry, "diary entry")
                if not review.safe:
                    logger.warning(f"Diary entry flagged for safety concerns: {review.concerns}. Skipping.")
                    return None

                logger.info(f"Generated diary entry for {self.bot_name}: mood={result.mood}, themes={result.themes}")
                return result
            else:
                logger.warning(f"Unexpected result type from diary LLM: {type(result)}")
                return None
            
        except Exception as e:
            logger.error(f"Failed to generate diary entry: {e}")
            return None

    async def save_diary_entry(
        self,
        entry: DiaryEntry,
        date: Optional[datetime] = None
    ) -> Optional[str]:
        """
        Saves a diary entry to Qdrant.
        
        Args:
            entry: The generated DiaryEntry
            date: The date for this diary entry (defaults to today)
            
        Returns:
            Point ID if successful, None on failure
        """
        if not db_manager.qdrant_client:
            logger.warning("Qdrant client not available, cannot save diary")
            return None
        
        entry_date = date or datetime.now(timezone.utc)
        date_str = entry_date.strftime("%Y-%m-%d")
        
        try:
            # Generate embedding from the diary content
            embedding = await self.embedding_service.embed_query_async(entry.entry)
            point_id = str(uuid.uuid4())
            
            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "type": "diary",
                    "bot_name": self.bot_name,
                    "date": date_str,
                    "content": entry.entry,
                    "mood": entry.mood,
                    "notable_users": entry.notable_users,
                    "themes": entry.themes,
                    "emotional_highlights": entry.emotional_highlights,
                    "timestamp": entry_date.isoformat(),
                    "visibility": "private"  # Character's private diary
                }
            )
            
            await db_manager.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            
            logger.info(f"Saved diary entry for {self.bot_name} on {date_str}: {point_id}")
            return point_id
            
        except Exception as e:
            logger.error(f"Failed to save diary entry: {e}")
            return None

    async def get_recent_diary(self, days: int = 3) -> List[Dict[str, Any]]:
        """
        Retrieves the most recent diary entries.
        
        Args:
            days: Number of days to look back (default 3)
            
        Returns:
            List of diary entry payloads, most recent first
        """
        if not db_manager.qdrant_client:
            return []
        
        try:
            # Calculate date threshold
            threshold = datetime.now(timezone.utc) - timedelta(days=days)
            threshold_str = threshold.strftime("%Y-%m-%d")
            
            # Search for diary entries
            # We'll use scroll since we want all recent entries, not similarity search
            results = await db_manager.qdrant_client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="type", match=MatchValue(value="diary")),
                        FieldCondition(key="bot_name", match=MatchValue(value=self.bot_name))
                    ]
                ),
                limit=days + 1,  # Get slightly more in case of overlap
                with_payload=True,
                with_vectors=False
            )
            
            entries = []
            for point in results[0]:  # results is (points, next_page_offset)
                payload = point.payload
                if payload and payload.get("date", "") >= threshold_str:
                    entries.append(payload)
            
            # Sort by date descending
            entries.sort(key=lambda x: x.get("date", ""), reverse=True)
            
            return entries[:days]
            
        except Exception as e:
            logger.error(f"Failed to retrieve recent diaries: {e}")
            return []

    async def get_latest_diary(self) -> Optional[Dict[str, Any]]:
        """
        Gets the most recent diary entry.
        
        Returns:
            Diary payload dict or None
        """
        entries = await self.get_recent_diary(days=1)
        return entries[0] if entries else None

    async def has_diary_for_today(self) -> bool:
        """
        Checks if a diary entry already exists for today.
        
        Returns:
            True if diary exists for today, False otherwise
        """
        if not db_manager.qdrant_client:
            return False
        
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        try:
            results = await db_manager.qdrant_client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="type", match=MatchValue(value="diary")),
                        FieldCondition(key="bot_name", match=MatchValue(value=self.bot_name)),
                        FieldCondition(key="date", match=MatchValue(value=today))
                    ]
                ),
                limit=1,
                with_payload=False,
                with_vectors=False
            )
            
            return len(results[0]) > 0
            
        except Exception as e:
            logger.error(f"Failed to check for today's diary: {e}")
            return False

    def format_diary_context(self, entry: Dict[str, Any]) -> str:
        """
        Formats a diary entry for injection into character context.
        
        Args:
            entry: Diary payload dict
            
        Returns:
            Formatted string for prompt injection
        """
        date = entry.get("date", "recently")
        mood = entry.get("mood", "neutral")
        content = entry.get("content", "")
        themes = entry.get("themes", [])
        
        # Truncate content if too long
        if len(content) > 500:
            content = content[:500] + "..."
        
        context = f"\n[YOUR RECENT DIARY ENTRY - {date}]\n"
        context += f"Mood: {mood}\n"
        if themes:
            context += f"On your mind: {', '.join(themes)}\n"
        context += f"\n{content}\n"
        
        return context


# Factory function for getting DiaryManager instances
_diary_managers: Dict[str, DiaryManager] = {}

def get_diary_manager(bot_name: Optional[str] = None) -> DiaryManager:
    """Get or create a DiaryManager instance for the given bot."""
    name = bot_name or settings.DISCORD_BOT_NAME or "default"
    if name not in _diary_managers:
        _diary_managers[name] = DiaryManager(bot_name=name)
    return _diary_managers[name]
