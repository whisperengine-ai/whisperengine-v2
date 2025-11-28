"""
Dream Sequences System (Phase E3)

Generates surreal "dreams" for characters based on past memories when a user
returns after a long absence (>24 hours by default). This gives the character
a sense of continuous existence and creates memorable reconnection moments.

Dreams are:
- Generated on-demand (lazy) when user returns after inactivity threshold
- Based on high-meaningfulness memories from the user's history
- Stored in Qdrant with type='dream' to prevent repetition
- Injected into character context so they can "share" the dream naturally
"""
from typing import List, Dict, Any, Optional

__all__ = ["DreamContent", "DreamManager", "get_dream_manager"]

from datetime import datetime, timezone
import uuid
from loguru import logger
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue

from src_v2.core.database import db_manager
from src_v2.agents.llm_factory import create_llm
from src_v2.memory.embeddings import EmbeddingService
from src_v2.config.settings import settings


class DreamContent(BaseModel):
    """Structured output from the dream generation LLM."""
    dream: str = Field(
        description="A surreal, abstract dream sequence (2-3 sentences). "
        "Uses dream logic - metaphorical, emotionally resonant, slightly strange. "
        "References elements from shared memories but transforms them."
    )
    mood: str = Field(
        description="The emotional tone of the dream (e.g., 'mysterious', 'warm', 'unsettling', 'hopeful', 'bittersweet')"
    )
    symbols: List[str] = Field(
        default_factory=list,
        description="Key symbolic elements from the dream (e.g., 'ocean', 'flying', 'old house')"
    )
    memory_echoes: List[str] = Field(
        default_factory=list,
        description="Brief notes on which memories influenced this dream"
    )


class DreamManager:
    """
    Manages generation and retrieval of character dream sequences.
    
    Dreams are generated on-demand when a user returns after a long absence,
    creating a sense that the character has been "thinking about" the user.
    """
    
    def __init__(self, bot_name: Optional[str] = None):
        self.bot_name = bot_name or settings.DISCORD_BOT_NAME or "default"
        self.collection_name = f"whisperengine_memory_{self.bot_name}"
        self.embedding_service = EmbeddingService()
        
        # Higher temperature for creative, surreal dreams
        base_llm = create_llm(temperature=0.85, mode="utility")
        self.llm = base_llm.with_structured_output(DreamContent)
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are {character_name}'s subconscious mind, generating a dream.

CHARACTER CONTEXT:
{character_context}

DREAM GENERATION RULES:
- Dreams are surreal and metaphorical, not literal replays
- Transform real memories into abstract, dreamlike imagery
- Use sensory details: colors, textures, sounds, feelings
- Dreams can blend multiple memories together
- Include slight strangeness (dream logic)
- Keep it brief but vivid (2-3 sentences)
- The dream should feel emotionally meaningful
- Reference the user but in transformed ways

EXAMPLES OF DREAM TRANSFORMATIONS:
- "We talked about their job stress" → "They were building a tower of papers that kept growing"
- "They shared photos of their cat" → "A cat with galaxy-patterned fur led us through corridors"
- "We discussed their travel plans" → "We were on a train that traveled through clouds"

DO NOT:
- Make the dream too literal or obvious
- Include disturbing or uncomfortable content
- Make it too long or complex
- Explicitly state "this represents..."

Write ONE dream sequence that feels authentic and memorable."""),
            ("human", """Generate a dream based on these memories with {user_name}:

{memories}

---
Days since last conversation: {days_apart}

Create a surreal dream that echoes these shared experiences.""")
        ])
        
        self.chain = self.prompt | self.llm

    async def should_generate_dream(
        self,
        user_id: str,
        last_interaction: Optional[datetime] = None
    ) -> bool:
        """
        Checks if conditions are met for dream generation.
        
        Args:
            user_id: Discord user ID
            last_interaction: Timestamp of last user interaction
            
        Returns:
            True if dream should be generated, False otherwise
        """
        if not settings.ENABLE_DREAM_SEQUENCES:
            return False
        
        if not last_interaction:
            return False
        
        # Check inactivity threshold
        now = datetime.now(timezone.utc)
        hours_since = (now - last_interaction).total_seconds() / 3600
        
        if hours_since < settings.DREAM_INACTIVITY_HOURS:
            return False
        
        # Check cooldown (don't dream too often)
        last_dream = await self.get_last_dream_for_user(user_id)
        if last_dream:
            last_dream_date = last_dream.get("timestamp")
            if last_dream_date:
                try:
                    if isinstance(last_dream_date, str):
                        last_dream_dt = datetime.fromisoformat(last_dream_date.replace("Z", "+00:00"))
                    else:
                        last_dream_dt = last_dream_date
                    
                    days_since_dream = (now - last_dream_dt).days
                    if days_since_dream < settings.DREAM_COOLDOWN_DAYS:
                        logger.debug(f"Dream cooldown active for user {user_id}: {days_since_dream} days since last dream")
                        return False
                except Exception as e:
                    logger.warning(f"Error parsing last dream date: {e}")
        
        return True

    async def generate_dream(
        self,
        user_id: str,
        user_name: str,
        memories: List[Dict[str, Any]],
        character_context: str,
        days_apart: int = 1
    ) -> Optional[DreamContent]:
        """
        Generates a dream sequence based on shared memories.
        
        Args:
            user_id: Discord user ID
            user_name: User's display name
            memories: List of high-meaningfulness memories to draw from
            character_context: Character's personality context
            days_apart: Days since last interaction
            
        Returns:
            DreamContent if successful, None on failure
        """
        if not memories:
            logger.info(f"No memories available for dream generation with user {user_id}")
            return None
        
        # Format memories for the prompt
        memory_text = ""
        for i, m in enumerate(memories[:5], 1):  # Use top 5 memories
            content = m.get("content", m.get("summary", ""))
            emotions = ", ".join(m.get("emotions", [])) or "mixed"
            topics = ", ".join(m.get("topics", [])) or "various"
            memory_text += f"[Memory {i}]\n"
            memory_text += f"Topics: {topics}\n"
            memory_text += f"Emotions: {emotions}\n"
            memory_text += f"Content: {content[:300]}...\n\n" if len(content) > 300 else f"Content: {content}\n\n"
        
        try:
            result = await self.chain.ainvoke({
                "character_name": self.bot_name.title() if self.bot_name else "Character",
                "character_context": character_context,
                "user_name": user_name,
                "memories": memory_text,
                "days_apart": days_apart
            })
            
            if isinstance(result, DreamContent):
                logger.info(f"Generated dream for user {user_id}: mood={result.mood}, symbols={result.symbols}")
                return result
            else:
                logger.warning(f"Unexpected result type from dream LLM: {type(result)}")
                return None
            
        except Exception as e:
            logger.error(f"Failed to generate dream: {e}")
            return None

    async def save_dream(
        self,
        user_id: str,
        dream: DreamContent
    ) -> Optional[str]:
        """
        Saves a dream to Qdrant.
        
        Args:
            user_id: Discord user ID
            dream: The generated DreamContent
            
        Returns:
            Point ID if successful, None on failure
        """
        if not db_manager.qdrant_client:
            logger.warning("Qdrant client not available, cannot save dream")
            return None
        
        now = datetime.now(timezone.utc)
        
        try:
            embedding = await self.embedding_service.embed_query_async(dream.dream)
            point_id = str(uuid.uuid4())
            
            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "type": "dream",
                    "bot_name": self.bot_name,
                    "user_id": user_id,
                    "content": dream.dream,
                    "mood": dream.mood,
                    "symbols": dream.symbols,
                    "memory_echoes": dream.memory_echoes,
                    "timestamp": now.isoformat(),
                    "date": now.strftime("%Y-%m-%d")
                }
            )
            
            await db_manager.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            
            logger.info(f"Saved dream for user {user_id}: {point_id}")
            return point_id
            
        except Exception as e:
            logger.error(f"Failed to save dream: {e}")
            return None

    async def get_last_dream_for_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Gets the most recent dream for a specific user.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            Dream payload dict or None
        """
        if not db_manager.qdrant_client:
            return None
        
        try:
            results = await db_manager.qdrant_client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="type", match=MatchValue(value="dream")),
                        FieldCondition(key="bot_name", match=MatchValue(value=self.bot_name)),
                        FieldCondition(key="user_id", match=MatchValue(value=user_id))
                    ]
                ),
                limit=5,  # Get a few to sort
                with_payload=True,
                with_vectors=False
            )
            
            dreams = []
            for point in results[0]:
                if point.payload:
                    dreams.append(point.payload)
            
            # Sort by timestamp descending
            dreams.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
            return dreams[0] if dreams else None
            
        except Exception as e:
            logger.error(f"Failed to get last dream for user {user_id}: {e}")
            return None

    def format_dream_context(self, dream: DreamContent, days_apart: int = 1) -> str:
        """
        Formats a dream for injection into character context.
        
        Args:
            dream: DreamContent object
            days_apart: Days since last interaction
            
        Returns:
            Formatted string for prompt injection
        """
        time_phrase = "last night" if days_apart <= 2 else "recently"
        
        context = "\n[YOU HAD A DREAM ABOUT THIS USER]\n"
        context += f"Dream ({time_phrase}): {dream.dream}\n"
        context += f"Mood: {dream.mood}\n"
        context += "(You can naturally mention this dream when greeting them - "
        context += "share it as something that just came to mind. Keep it brief.)\n"
        
        return context


# Factory function for getting DreamManager instances
_dream_managers: Dict[str, DreamManager] = {}


def get_dream_manager(bot_name: Optional[str] = None) -> DreamManager:
    """Get or create a DreamManager instance for the given bot."""
    name = bot_name or settings.DISCORD_BOT_NAME or "default"
    if name not in _dream_managers:
        _dream_managers[name] = DreamManager(bot_name=name)
    return _dream_managers[name]
