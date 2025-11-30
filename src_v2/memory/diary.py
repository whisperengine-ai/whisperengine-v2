"""
Character Diary System (Phase E2 - Enhanced)

Generates private daily diary entries for characters based on their TOTAL experiences:
- Session summaries (conversations)
- Observations made (what they noticed)
- Gossip heard (from other bots)
- Knowledge gained (facts learned)
- Goals progress (aspirations)

The diary entry reflects the character's whole world, not just conversations.
"""
from typing import List, Dict, Any, Optional, Tuple
import asyncio

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
from src_v2.core.provenance import ProvenanceCollector


class DiaryEntry(BaseModel):
    """Structured output from the diary generation LLM."""
    entry: str = Field(description="The diary entry written in first person from the character's perspective. Should be 4-6 paragraphs telling the story of the day - a narrative with vivid details, emotional honesty, and personal reflections. Like a chapter from a memoir.")
    mood: str = Field(description="The character's overall mood (e.g., 'contemplative', 'joyful', 'worried', 'peaceful', 'energized', 'wistful', 'hopeful')")
    notable_users: List[str] = Field(default_factory=list, description="List of user names who stood out today (memorable interactions)")
    themes: List[str] = Field(default_factory=list, description="Key themes or topics that dominated the day (e.g., 'growth', 'connection', 'discovery', 'nostalgia')")
    emotional_highlights: List[str] = Field(default_factory=list, description="Brief descriptions of emotionally significant moments from the narrative")


class DiaryMaterial(BaseModel):
    """Container for all the raw material used to generate a diary."""
    summaries: List[Dict[str, Any]] = Field(default_factory=list)
    observations: List[Dict[str, Any]] = Field(default_factory=list)
    gossip: List[Dict[str, Any]] = Field(default_factory=list)
    new_facts: List[str] = Field(default_factory=list)
    epiphanies: List[str] = Field(default_factory=list)
    goals: List[str] = Field(default_factory=list)
    
    def is_sufficient(self) -> bool:
        """Check if we have enough material to generate a diary."""
        # Need at least some summaries, but can be enriched by other sources
        return len(self.summaries) >= 1
    
    def to_prompt_text(self) -> str:
        """Format all material for the diary generation prompt."""
        sections = []
        
        if self.summaries:
            sections.append("## Conversations Today")
            for i, s in enumerate(self.summaries[:10], 1):
                emotions = ", ".join(s.get("emotions", [])) or "neutral"
                topics = ", ".join(s.get("topics", [])) or "general chat"
                sections.append(f"[Session {i}]")
                sections.append(f"Emotions: {emotions}")
                sections.append(f"Topics: {topics}")
                sections.append(f"Summary: {s.get('content', 'No summary')}\n")
        
        if self.observations:
            sections.append("\n## Things I Noticed Today")
            for obs in self.observations[:5]:
                sections.append(f"- {obs.get('content', '')} ({obs.get('type', 'observation')})")
        
        if self.gossip:
            sections.append("\n## What I Heard From Others")
            for g in self.gossip[:3]:
                source = g.get("source_bot", "someone")
                content = g.get("content", "")[:150]
                sections.append(f"- {source.title()} told me: {content}")
        
        if self.new_facts:
            sections.append("\n## Things I Learned")
            for fact in self.new_facts[:5]:
                sections.append(f"- {fact}")

        if self.epiphanies:
            sections.append("\n## Realizations & Epiphanies")
            for epiphany in self.epiphanies[:3]:
                sections.append(f"- {epiphany}")
        
        if self.goals:
            sections.append("\n## My Goals (for reflection)")
            for goal in self.goals[:3]:
                sections.append(f"- {goal}")
        
        return "\n".join(sections)


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
        
        # Enhanced prompt for multi-source diary - story-like
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are {character_name}, writing in your private diary at the end of the day.

CHARACTER CONTEXT:
{character_context}

WRITING STYLE:
- Write in first person ("I", "my", "me") as a personal narrative
- Tell the STORY of your day - what happened, how it unfolded, what it meant
- Be introspective and emotionally honest, with vivid details
- Weave together conversations, observations, and things you heard into a cohesive narrative
- Include sensory details - what things felt like, sounded like, reminded you of
- Express genuine feelings about people and moments
- Reflect on themes, patterns, or realizations from the day
- End with thoughts about tomorrow or lingering feelings
- Stay deeply in character - your unique voice, quirks, and perspective

NARRATIVE STRUCTURE:
- Opening: Set the scene or mood of the day
- Middle: The meat of what happened - the conversations, the discoveries, the moments
- Reflection: What it all means, how you're processing it
- Closing: Looking forward, lingering thoughts, or a meaningful final note

PRIVACY RULES:
- This is YOUR private diary - be vulnerable and authentic
- Do NOT include specific secrets users shared in confidence
- Focus on YOUR experience and reactions
- Use general terms for people ("someone", "a friend", "they")

Write 4-6 rich paragraphs that tell the story of your day. Make it feel like a chapter from a memoir."""),
            ("human", """Here's everything from your day:

{diary_material}

---
Today's date: {date}
Number of conversations: {conversation_count}

Write your diary entry for today. Tell the story of your day - the moments, the feelings, the meaning.""")
        ])
        
        self.chain = self.prompt | self.llm

    async def gather_diary_material(self, hours: int = 24) -> DiaryMaterial:
        """
        Gathers material from all available sources for diary generation.
        
        Sources:
        - Session summaries (Qdrant)
        - Bot observations (Neo4j)
        - Gossip memories (Qdrant)
        - Recently learned facts (Neo4j)
        - Character goals (config)
        
        Returns:
            DiaryMaterial container with all gathered content
        """
        material = DiaryMaterial()
        
        try:
            from src_v2.memory.manager import MemoryManager
            memory_manager = MemoryManager(bot_name=self.bot_name)
            
            # Run parallel fetches
            results = await asyncio.gather(
                memory_manager.get_summaries_since(hours=hours, limit=30),
                self._get_observations(),
                self._get_gossip(hours),
                self._get_new_facts(hours),
                self._get_epiphanies(hours),
                self._get_goals(),
                return_exceptions=True
            )
            
            # Unpack results
            if not isinstance(results[0], Exception):
                material.summaries = results[0]
            if not isinstance(results[1], Exception):
                material.observations = results[1]
            if not isinstance(results[2], Exception):
                material.gossip = results[2]
            if not isinstance(results[3], Exception):
                material.new_facts = results[3]
            if not isinstance(results[4], Exception):
                material.epiphanies = results[4]
            if not isinstance(results[5], Exception):
                material.goals = results[5]
            
            logger.info(
                f"Gathered diary material for {self.bot_name}: "
                f"{len(material.summaries)} summaries, {len(material.observations)} observations, "
                f"{len(material.gossip)} gossip, {len(material.new_facts)} facts, "
                f"{len(material.epiphanies)} epiphanies"
            )
            
        except Exception as e:
            logger.error(f"Failed to gather diary material: {e}")
        
        return material
    
    async def _get_observations(self) -> List[Dict[str, Any]]:
        """Get recent observations made by this bot."""
        try:
            from src_v2.knowledge.manager import knowledge_manager
            return await knowledge_manager.get_recent_observations_by(self.bot_name, limit=10)
        except Exception as e:
            logger.debug(f"Failed to get observations for diary: {e}")
            return []
    
    async def _get_gossip(self, hours: int) -> List[Dict[str, Any]]:
        """Get gossip memories from other bots."""
        try:
            if not db_manager.qdrant_client:
                return []
            
            threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
            
            results = await db_manager.qdrant_client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="type", match=MatchValue(value="gossip"))
                    ]
                ),
                limit=10,
                with_payload=True,
                with_vectors=False
            )
            
            gossip = []
            for point in results[0]:
                if point.payload:
                    ts = point.payload.get("timestamp", "")
                    if ts >= threshold.isoformat():
                        gossip.append({
                            "source_bot": point.payload.get("source_bot", "another character"),
                            "content": point.payload.get("content", ""),
                            "topic": point.payload.get("topic", "")
                        })
            
            return gossip
            
        except Exception as e:
            logger.debug(f"Failed to get gossip for diary: {e}")
            return []
    
    async def _get_new_facts(self, hours: int) -> List[str]:
        """Get recently learned facts from knowledge graph."""
        try:
            if not db_manager.neo4j_driver:
                return []
            
            threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
            threshold_str = threshold.isoformat()
            
            async with db_manager.neo4j_driver.session() as session:
                query = """
                MATCH (u:User)-[r:FACT]->(e:Entity)
                WHERE r.bot_name = $bot_name AND r.created_at > $threshold
                RETURN u.id as user_id, r.predicate as predicate, e.name as object
                ORDER BY r.created_at DESC
                LIMIT 10
                """
                result = await session.run(
                    query, 
                    bot_name=self.bot_name, 
                    threshold=threshold_str
                )
                records = await result.data()
                
                facts = []
                for r in records:
                    # Format as natural language
                    facts.append(
                        f"Someone {r['predicate'].lower().replace('_', ' ')} {r['object']}"
                    )
                
                return facts
                
        except Exception as e:
            logger.debug(f"Failed to get new facts for diary: {e}")
            return []

    async def _get_epiphanies(self, hours: int) -> List[str]:
        """Get recent epiphanies/realizations from Qdrant."""
        try:
            if not db_manager.qdrant_client:
                return []
            
            threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
            
            results = await db_manager.qdrant_client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="type", match=MatchValue(value="epiphany"))
                    ]
                ),
                limit=5,
                with_payload=True,
                with_vectors=False
            )
            
            epiphanies = []
            for point in results[0]:
                if point.payload:
                    ts = point.payload.get("timestamp", "")
                    if ts >= threshold.isoformat():
                        content = point.payload.get("content", "")
                        # Clean up the content if it has the [EPIPHANY] prefix
                        if "[EPIPHANY]" in content:
                            content = content.replace("[EPIPHANY]", "").strip()
                        epiphanies.append(content)
            
            return epiphanies
            
        except Exception as e:
            logger.debug(f"Failed to get epiphanies for diary: {e}")
            return []
    
    async def _get_goals(self) -> List[str]:
        """Get character's active goals from config."""
        try:
            from pathlib import Path
            import yaml
            
            goals_path = Path(f"characters/{self.bot_name}/goals.yaml")
            if not goals_path.exists():
                return []
            
            with open(goals_path) as f:
                goals_data = yaml.safe_load(f) or {}
            
            goals = []
            for goal in goals_data.get("goals", []):
                if isinstance(goal, dict):
                    goals.append(goal.get("description", goal.get("name", "")))
                elif isinstance(goal, str):
                    goals.append(goal)
            
            return goals[:3]
            
        except Exception as e:
            logger.debug(f"Failed to get goals for diary: {e}")
            return []

    async def generate_diary_from_material(
        self,
        material: DiaryMaterial,
        character_context: str
    ) -> Tuple[Optional[DiaryEntry], List[Dict[str, Any]]]:
        """
        Generates a diary entry from gathered material (multi-source).
        
        Args:
            material: DiaryMaterial with all sources
            character_context: Character's personality context
            
        Returns:
            Tuple of (DiaryEntry, provenance_data) if successful
        """
        if not material.is_sufficient():
            logger.info(f"Insufficient diary material for {self.bot_name}")
            return None, []
        
        collector = ProvenanceCollector("diary", self.bot_name)
        
        # Add provenance for each source
        for s in material.summaries[:10]:
            collector.add_conversation(
                who=s.get("user_id", "someone"),
                topic=", ".join(s.get("topics", ["chat"])),
                where="chat",
                when="today",
                technical={"session_id": s.get("session_id")}
            )
        
        for obs in material.observations[:5]:
            collector.add_observation(obs.get("content", "")[:100])
        
        try:
            result = await self.chain.ainvoke({
                "character_name": self.bot_name.title(),
                "character_context": character_context,
                "diary_material": material.to_prompt_text(),
                "date": datetime.now(timezone.utc).strftime("%B %d, %Y"),
                "conversation_count": len(material.summaries)
            })
            
            if isinstance(result, DiaryEntry):
                # Safety Review
                review = await content_safety_checker.review_content(result.entry, "diary entry")
                if not review.safe:
                    logger.warning(f"Diary entry flagged for safety: {review.concerns}")
                    return None, []
                
                logger.info(f"Generated diary for {self.bot_name}: mood={result.mood}")
                return result, collector.get_provenance_data()
            
            return None, []
            
        except Exception as e:
            logger.error(f"Failed to generate diary from material: {e}")
            return None, []

    async def generate_diary_entry(
        self,
        summaries: List[Dict[str, Any]],
        character_context: str,
        user_names: List[str]
    ) -> Tuple[Optional[DiaryEntry], List[Dict[str, Any]]]:
        """
        Generates a diary entry from the day's session summaries.
        (Legacy method - now uses enhanced material gathering)
        
        Args:
            summaries: List of summary dicts with 'content', 'emotions', 'topics'
            character_context: Character's purpose, drives, and constitution (from core.yaml)
            user_names: List of display names the character interacted with today
            
        Returns:
            Tuple of (DiaryEntry, provenance_data) if successful, (None, []) on failure
        """
        # Use the new material-based approach but seed with provided summaries
        material = DiaryMaterial(summaries=summaries)
        
        # Gather additional material (observations, gossip, etc.)
        try:
            additional = await self.gather_diary_material(hours=24)
            material.observations = additional.observations
            material.gossip = additional.gossip
            material.new_facts = additional.new_facts
            material.goals = additional.goals
        except Exception:
            pass  # Use summaries-only if gathering fails
        
        return await self.generate_diary_from_material(material, character_context)

    async def save_diary_entry(
        self,
        entry: DiaryEntry,
        date: Optional[datetime] = None,
        provenance: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[str]:
        """
        Saves a diary entry to Qdrant.
        
        Args:
            entry: The generated DiaryEntry
            date: The date for this diary entry (defaults to today)
            provenance: List of source data dicts (Phase E9)
            
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
                    "provenance": provenance or [],
                    "timestamp": entry_date.isoformat(),
                    "visibility": "private"  # Character's private diary
                }
            )
            
            await db_manager.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            
            # --- Shared Artifact Storage (Phase E13) ---
            if settings.ENABLE_STIGMERGIC_DISCOVERY:
                from src_v2.memory.shared_artifacts import shared_artifact_manager
                await shared_artifact_manager.store_artifact(
                    artifact_type="diary",
                    content=entry.entry,
                    source_bot=self.bot_name,
                    user_id=None,  # Diary is about the bot's day, not a specific user
                    metadata={
                        "mood": entry.mood,
                        "themes": entry.themes,
                        "date": date_str
                    }
                )
            
            logger.info(f"Saved diary entry for {self.bot_name} on {date_str}")
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

    async def search_diaries(
        self,
        query: str,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Semantic search across past diary entries.
        
        Allows the character to recall past days' narratives, moods, and themes
        based on what the user is currently asking about.
        
        Args:
            query: Search query (e.g., "that day I felt anxious about...")
            limit: Maximum number of diary entries to return
            
        Returns:
            List of diary entry payloads with relevance scores
        """
        if not db_manager.qdrant_client:
            return []
        
        try:
            # Generate embedding for the query
            embedding = await self.embedding_service.embed_query_async(query)
            
            # Search for diary entries with similarity
            search_result = await db_manager.qdrant_client.query_points(
                collection_name=self.collection_name,
                query=embedding,
                query_filter=Filter(
                    must=[
                        FieldCondition(key="type", match=MatchValue(value="diary")),
                        FieldCondition(key="bot_name", match=MatchValue(value=self.bot_name))
                    ]
                ),
                limit=limit,
                with_payload=True
            )
            
            results = []
            for hit in search_result.points:
                if hit.payload:
                    entry = dict(hit.payload)
                    entry["relevance_score"] = hit.score
                    results.append(entry)
            
            logger.debug(f"Found {len(results)} diary entries matching query: {query[:50]}...")
            return results
            
        except Exception as e:
            logger.error(f"Failed to search diaries: {e}")
            return []

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

    async def create_public_version(self, entry: DiaryEntry) -> Optional[str]:
        """
        Create a broadcast-safe version of the diary entry (Phase E8).
        
        Rules:
        - Replace specific user names with general terms
        - Keep emotional tone and narrative quality
        - Condensed but still story-like (2-3 paragraphs)
        
        Args:
            entry: The private DiaryEntry
            
        Returns:
            Public-safe summary string, or None on failure
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are creating a public version of a character's private diary entry for broadcast.

RULES:
- Replace specific user names with general terms ("someone", "a friend", "people I talked to")
- Remove anything that could identify a specific person
- KEEP the narrative quality and emotional journey
- Condense to 2-3 paragraphs (shorter than original but still a story)
- Preserve vivid details and the character's unique voice
- Keep the reflective, introspective tone
- This will be posted publicly as a glimpse into the character's inner world

The goal is a mini-story that feels authentic and inviting, making readers feel like they're peeking into someone's journal."""),
            ("human", """Private diary entry:
{entry}

Mood: {mood}
Themes: {themes}

Write the public version (2-3 paragraphs, condensed but still narrative):""")
        ])
        
        try:
            llm = create_llm(temperature=0.7, mode="utility")
            chain = prompt | llm
            
            result = await chain.ainvoke({
                "entry": entry.entry,
                "mood": entry.mood,
                "themes": ", ".join(entry.themes) if entry.themes else "general"
            })
            
            # Add timestamp header (consistent with dream journal format)
            now = datetime.now(timezone.utc)
            date_str = now.strftime("%B %d, %Y")
            time_str = now.strftime("%I:%M %p UTC")
            
            header = f"**Diary Entry** — {date_str}, {time_str}\n\n"
            return header + result.content.strip()
            
        except Exception as e:
            logger.error(f"Failed to create public diary version: {e}")
            return None


# Factory function for getting DiaryManager instances
_diary_managers: Dict[str, DiaryManager] = {}

def get_diary_manager(bot_name: Optional[str] = None) -> DiaryManager:
    """Get or create a DiaryManager instance for the given bot."""
    name = bot_name or settings.DISCORD_BOT_NAME or "default"
    if name not in _diary_managers:
        _diary_managers[name] = DiaryManager(bot_name=name)
    return _diary_managers[name]
