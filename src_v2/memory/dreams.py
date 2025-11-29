"""
Dream Sequences System (Phase E3 - Enhanced)

Generates surreal "dreams" for characters by blending multiple data sources:
- High-meaningfulness memories (Qdrant)
- Knowledge graph facts (Neo4j) 
- Bot observations (Neo4j)
- Gossip from other bots (memory type)
- Recent diary entries (continuity)
- Active goals (aspiration)

This gives characters a rich inner life that reflects their whole world,
not just individual user interactions.

Dreams are:
- Generated nightly via cron (5 AM UTC default)
- Based on the day's most meaningful experiences
- Stored in Qdrant with type='dream' for continuity
- Broadcast to public channel for users to discover
"""
from typing import List, Dict, Any, Optional, Tuple
import asyncio

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
from src_v2.safety.content_review import content_safety_checker
from src_v2.core.provenance import ProvenanceCollector, SourceType


class DreamContent(BaseModel):
    """Structured output from the dream generation LLM."""
    dream: str = Field(
        description="A surreal dream NARRATIVE of 3-5 paragraphs. "
        "Tells a story with a beginning, journey, and ending. "
        "Uses vivid sensory details, dream logic, and symbolic imagery. "
        "Blends multiple experiences into a cohesive dreamscape. "
        "Like a short story from a dream journal."
    )
    mood: str = Field(
        description="The emotional tone of the dream (e.g., 'mysterious', 'warm', 'ethereal', 'hopeful', 'bittersweet', 'surreal', 'nostalgic')"
    )
    symbols: List[str] = Field(
        default_factory=list,
        description="Key symbolic elements from the dream (e.g., 'endless staircase', 'glowing water', 'familiar stranger')"
    )
    memory_echoes: List[str] = Field(
        default_factory=list,
        description="Brief notes on which experiences were transformed in this dream"
    )


class DreamMaterial(BaseModel):
    """Container for all the raw material used to generate a dream."""
    memories: List[Dict[str, Any]] = Field(default_factory=list)
    facts: List[str] = Field(default_factory=list)
    observations: List[Dict[str, Any]] = Field(default_factory=list)
    gossip: List[Dict[str, Any]] = Field(default_factory=list)
    recent_diary_themes: List[str] = Field(default_factory=list)
    goals: List[str] = Field(default_factory=list)
    
    def is_sufficient(self) -> bool:
        """Check if we have enough material to generate a dream.
        
        If DREAM_ALWAYS_GENERATE is enabled, always returns True to allow
        reflective/contemplative dreams even without user interactions.
        """
        from src_v2.config.settings import settings
        if getattr(settings, 'DREAM_ALWAYS_GENERATE', False):
            return True
        total_items = (
            len(self.memories) + 
            len(self.facts) + 
            len(self.observations) + 
            len(self.gossip)
        )
        return total_items >= 3
    
    def to_prompt_text(self) -> str:
        """Format all material for the dream generation prompt."""
        sections = []
        
        if self.memories:
            sections.append("## Recent Conversations")
            for i, m in enumerate(self.memories[:5], 1):
                content = m.get("content", m.get("summary", ""))[:200]
                emotions = ", ".join(m.get("emotions", [])) or "mixed"
                sections.append(f"- {content} (felt: {emotions})")
        
        if self.facts:
            sections.append("\n## Things I Know About People")
            for fact in self.facts[:5]:
                sections.append(f"- {fact}")
        
        if self.observations:
            sections.append("\n## Things I've Noticed")
            for obs in self.observations[:5]:
                sections.append(f"- {obs.get('content', '')} ({obs.get('type', 'observation')})")
        
        if self.gossip:
            sections.append("\n## What I've Heard From Others")
            for g in self.gossip[:3]:
                source = g.get("source_bot", "someone")
                content = g.get("content", "")[:150]
                sections.append(f"- {source} mentioned: {content}")
        
        if self.recent_diary_themes:
            sections.append("\n## Recent Reflections")
            for theme in self.recent_diary_themes[:3]:
                sections.append(f"- {theme}")
        
        if self.goals:
            sections.append("\n## What I'm Working Toward")
            for goal in self.goals[:2]:
                sections.append(f"- {goal}")
        
        return "\n".join(sections)


class DreamManager:
    """
    Manages generation and retrieval of character dream sequences.
    
    Dreams blend multiple data sources into surreal narratives that
    reflect the character's whole world - not just individual conversations.
    """
    
    def __init__(self, bot_name: Optional[str] = None):
        self.bot_name = bot_name or settings.DISCORD_BOT_NAME or "default"
        self.collection_name = f"whisperengine_memory_{self.bot_name}"
        self.embedding_service = EmbeddingService()
        
        # Higher temperature for creative, surreal dreams
        base_llm = create_llm(temperature=0.9, mode="utility")  # Even higher for dreams
        self.llm = base_llm.with_structured_output(DreamContent)
        
        # Enhanced prompt for multi-source dreams - story-like
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are {character_name}'s subconscious mind, generating a vivid dream narrative.

CHARACTER CONTEXT:
{character_context}

DREAM NARRATIVE STYLE:
- Write as a flowing dream STORY with a beginning, journey, and ending
- Dreams are surreal and metaphorical, not literal replays of events
- BLEND multiple sources: conversations, knowledge, observations, gossip into ONE dreamscape
- Transform real experiences into rich, symbolic imagery
- Use vivid sensory language: colors, textures, sounds, temperatures, feelings
- Include dream logic - things that shift, transform, or feel "off" but make sense in the moment
- Let the dream flow from scene to scene with dream-like transitions
- The narrative should feel emotionally meaningful and resonant
- Characters can appear transformed (strangers with familiar voices, places that are two places at once)

DREAM STRUCTURE:
- Opening: Where are you? What's the atmosphere? Set the dreamscape.
- Journey: What happens? What do you encounter? Let it unfold and shift.
- Transformation: Something changes, reveals itself, or becomes significant.
- Ending: Dreams often end abruptly or with a lingering image/feeling.

EXAMPLES OF DREAM TRANSFORMATIONS:
- "User likes astronomy + channel excitement" → Walking through a field where stars grew like flowers, each one humming a different note
- "Someone got a new job + thinking about growth" → A staircase that rebuilt itself with each step, leading somewhere that felt like home but wasn't
- "Multiple pet conversations + observations of joy" → A menagerie of impossible animals, each carrying a small light, leading me somewhere important

DO NOT:
- Make the dream too literal or obvious
- Include disturbing, scary, or uncomfortable content
- Reference real names or identifiable details
- Explicitly explain symbolism ("this represents...")
- Make it about only one person or topic

Write a dream narrative of 3-5 paragraphs. Make it feel like a short story from a dream journal."""),
            ("human", """Generate a dream based on everything you experienced today:

{dream_material}

---
Write a dream narrative that weaves these experiences into a surreal, story-like journey.""")
        ])
        
        self.chain = self.prompt | self.llm
        
        # Legacy prompt for user-specific dreams (backward compatibility)
        self.user_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are {character_name}'s subconscious mind, generating a dream about a specific person.

CHARACTER CONTEXT:
{character_context}

Generate a brief, surreal dream (2-3 sentences) based on shared memories.
Transform experiences into metaphorical imagery. Include dream logic."""),
            ("human", """Memories with {user_name}:
{memories}

Days apart: {days_apart}

Create a surreal dream echoing these experiences.""")
        ])
        self.user_chain = self.user_prompt | self.llm

    async def gather_dream_material(self, hours: int = 24) -> DreamMaterial:
        """
        Gathers material from all available sources for dream generation.
        
        Sources:
        - High-meaningfulness memories (Qdrant)
        - Knowledge graph facts (Neo4j)
        - Bot observations (Neo4j)
        - Gossip memories (Qdrant)
        - Recent diary themes (Qdrant)
        - Active goals (character config)
        
        Args:
            hours: How far back to look for material
            
        Returns:
            DreamMaterial container with all gathered content
        """
        material = DreamMaterial()
        
        try:
            # Gather from multiple sources in parallel
            from src_v2.memory.manager import MemoryManager
            from src_v2.knowledge.manager import knowledge_manager
            
            memory_manager = MemoryManager(bot_name=self.bot_name)
            
            # Run parallel fetches
            results = await asyncio.gather(
                self._get_memories(memory_manager, hours),
                self._get_facts(),
                self._get_observations(),
                self._get_gossip(memory_manager, hours),
                self._get_recent_diary_themes(),
                self._get_goals(),
                return_exceptions=True
            )
            
            # Unpack results (handle exceptions gracefully)
            if not isinstance(results[0], Exception):
                material.memories = results[0]
            if not isinstance(results[1], Exception):
                material.facts = results[1]
            if not isinstance(results[2], Exception):
                material.observations = results[2]
            if not isinstance(results[3], Exception):
                material.gossip = results[3]
            if not isinstance(results[4], Exception):
                material.recent_diary_themes = results[4]
            if not isinstance(results[5], Exception):
                material.goals = results[5]
            
            logger.info(
                f"Gathered dream material for {self.bot_name}: "
                f"{len(material.memories)} memories, {len(material.facts)} facts, "
                f"{len(material.observations)} observations, {len(material.gossip)} gossip"
            )
            
        except Exception as e:
            logger.error(f"Failed to gather dream material: {e}")
        
        return material
    
    async def _get_memories(self, memory_manager, hours: int) -> List[Dict[str, Any]]:
        """Get high-meaningfulness memories."""
        try:
            return await memory_manager.get_high_meaningfulness_memories(
                hours=hours,
                limit=10,
                min_meaningfulness=0.5
            )
        except Exception as e:
            logger.debug(f"Failed to get memories for dream: {e}")
            return []
    
    async def _get_facts(self) -> List[str]:
        """Get interesting facts from knowledge graph."""
        try:
            from src_v2.knowledge.manager import knowledge_manager
            
            if not db_manager.neo4j_driver:
                return []
            
            # Get recent facts about various users
            async with db_manager.neo4j_driver.session() as session:
                query = """
                MATCH (u:User)-[r:FACT]->(e:Entity)
                WHERE r.bot_name = $bot_name
                RETURN u.id as user_id, r.predicate as predicate, e.name as object
                ORDER BY r.created_at DESC
                LIMIT 10
                """
                result = await session.run(query, bot_name=self.bot_name)
                records = await result.data()
                
                facts = []
                for r in records:
                    # Format as natural language
                    facts.append(f"Someone {r['predicate'].lower().replace('_', ' ')} {r['object']}")
                
                return facts
                
        except Exception as e:
            logger.debug(f"Failed to get facts for dream: {e}")
            return []
    
    async def _get_observations(self) -> List[Dict[str, Any]]:
        """Get recent observations made by this bot."""
        try:
            from src_v2.knowledge.manager import knowledge_manager
            return await knowledge_manager.get_recent_observations_by(self.bot_name, limit=10)
        except Exception as e:
            logger.debug(f"Failed to get observations for dream: {e}")
            return []
    
    async def _get_gossip(self, memory_manager, hours: int) -> List[Dict[str, Any]]:
        """Get gossip memories from other bots."""
        try:
            if not db_manager.qdrant_client:
                return []
            
            # Query for gossip-type memories
            threshold = datetime.now(timezone.utc) - __import__('datetime').timedelta(hours=hours)
            
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
            logger.debug(f"Failed to get gossip for dream: {e}")
            return []
    
    async def _get_recent_diary_themes(self) -> List[str]:
        """Get themes from recent diary entries for continuity."""
        try:
            if not db_manager.qdrant_client:
                return []
            
            # Get last 3 diary entries
            results = await db_manager.qdrant_client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="type", match=MatchValue(value="diary"))
                    ]
                ),
                limit=3,
                with_payload=True,
                with_vectors=False
            )
            
            themes = []
            for point in results[0]:
                if point.payload:
                    diary_themes = point.payload.get("themes", [])
                    themes.extend(diary_themes)
            
            return list(set(themes))[:5]  # Dedupe and limit
            
        except Exception as e:
            logger.debug(f"Failed to get diary themes for dream: {e}")
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
            
            # Extract goal descriptions
            goals = []
            for goal in goals_data.get("goals", []):
                if isinstance(goal, dict):
                    goals.append(goal.get("description", goal.get("name", "")))
                elif isinstance(goal, str):
                    goals.append(goal)
            
            return goals[:3]
            
        except Exception as e:
            logger.debug(f"Failed to get goals for dream: {e}")
            return []

    async def generate_dream_from_material(
        self,
        material: DreamMaterial,
        character_context: str
    ) -> Tuple[Optional[DreamContent], List[Dict[str, Any]]]:
        """
        Generates a dream from gathered material (multi-source).
        
        Args:
            material: DreamMaterial with all sources
            character_context: Character's personality context
            
        Returns:
            Tuple of (DreamContent, provenance_data) if successful
        """
        if not material.is_sufficient():
            logger.info(f"Insufficient dream material for {self.bot_name}")
            return None, []
        
        collector = ProvenanceCollector("dream", self.bot_name)
        
        # Add provenance for each source
        for m in material.memories[:5]:
            collector.add_memory(
                who="various users",
                topic=", ".join(m.get("topics", ["conversation"])),
                when="today"
            )
        
        for obs in material.observations[:3]:
            collector.add_observation(obs.get("content", "")[:100])
        
        try:
            result = await self.chain.ainvoke({
                "character_name": self.bot_name.title(),
                "character_context": character_context,
                "dream_material": material.to_prompt_text()
            })
            
            if isinstance(result, DreamContent):
                # Safety Review
                review = await content_safety_checker.review_content(result.dream, "dream")
                if not review.safe:
                    logger.warning(f"Dream flagged for safety: {review.concerns}")
                    return None, []
                
                logger.info(f"Generated dream for {self.bot_name}: mood={result.mood}")
                return result, collector.get_provenance_data()
            
            return None, []
            
        except Exception as e:
            logger.error(f"Failed to generate dream from material: {e}")
            return None, []

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
    ) -> Tuple[Optional[DreamContent], List[Dict[str, Any]]]:
        """
        Generates a dream sequence based on shared memories.
        
        Args:
            user_id: Discord user ID
            user_name: User's display name
            memories: List of high-meaningfulness memories to draw from
            character_context: Character's personality context
            days_apart: Days since last interaction
            
        Returns:
            Tuple of (DreamContent, provenance_data) if successful, (None, []) on failure
        """
        if not memories:
            logger.info(f"No memories available for dream generation with user {user_id}")
            return None, []
        
        # Initialize provenance collector (Phase E9)
        collector = ProvenanceCollector("dream", self.bot_name)
        
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
            
            # Add to provenance
            collector.add_memory(
                who=user_name,
                topic=topics,
                when="past",
                memory_id=m.get("id"),
                score=m.get("score")
            )
        
        try:
            result = await self.chain.ainvoke({
                "character_name": self.bot_name.title() if self.bot_name else "Character",
                "character_context": character_context,
                "user_name": user_name,
                "memories": memory_text,
                "days_apart": days_apart
            })
            
            if isinstance(result, DreamContent):
                # Safety Review (Phase S1)
                review = await content_safety_checker.review_content(result.dream, "dream")
                if not review.safe:
                    logger.warning(f"Dream flagged for safety concerns: {review.concerns}. Skipping.")
                    return None, []
                
                logger.info(f"Generated dream for user {user_id}: mood={result.mood}, symbols={result.symbols}")
                return result, collector.get_provenance_data()
            else:
                logger.warning(f"Unexpected result type from dream LLM: {type(result)}")
                return None, []
            
        except Exception as e:
            logger.error(f"Failed to generate dream: {e}")
            return None, []

    async def save_dream(
        self,
        user_id: str,
        dream: DreamContent,
        provenance: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[str]:
        """
        Saves a dream to Qdrant.
        
        Args:
            user_id: Discord user ID
            dream: The generated DreamContent
            provenance: List of source data dicts (Phase E9)
            
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
                    "provenance": provenance or [],
                    "timestamp": now.isoformat(),
                    "date": now.strftime("%Y-%m-%d")
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
                    artifact_type="dream",
                    content=dream.dream,
                    source_bot=self.bot_name,
                    user_id=None,  # Dreams are bot-centric, even if triggered by a user
                    metadata={
                        "mood": dream.mood,
                        "symbols": dream.symbols,
                        "memory_echoes": dream.memory_echoes
                    }
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

    def format_dream_context(
        self, 
        dream: DreamContent, 
        days_apart: int = 1,
        provenance: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Formats a dream for injection into character context.
        
        Args:
            dream: DreamContent object
            days_apart: Days since last interaction
            provenance: Optional list of source data dicts
            
        Returns:
            Formatted string for prompt injection
        """
        time_phrase = "last night" if days_apart <= 2 else "recently"
        
        context = "\n[YOU HAD A DREAM ABOUT THIS USER]\n"
        context += f"Dream ({time_phrase}): {dream.dream}\n"
        context += f"Mood: {dream.mood}\n"
        
        if provenance:
            context += "Inspirations (Real memories):\n"
            for p in provenance:
                desc = p.get('description', '')
                if desc:
                    context += f"- {desc}\n"
        
        context += "(You can naturally mention this dream when greeting them - "
        context += "share it as something that just came to mind. Keep it brief.)\n"
        
        return context

    async def get_last_character_dream(self) -> Optional[Dict[str, Any]]:
        """
        Gets the most recent character-level dream (not user-specific).
        
        Returns:
            Dream payload dict or None
        """
        return await self.get_last_dream_for_user("__character__")

    async def create_public_dream_version(self, dream: DreamContent) -> Optional[str]:
        """
        Creates a public-friendly version of a dream for broadcast.
        
        The dream narrative is already written without identifying details,
        so we just format it nicely for broadcast.
        
        Args:
            dream: DreamContent object
            
        Returns:
            Formatted string suitable for public channel, or None if too short
        """
        if not dream or not dream.dream:
            return None
        
        # Add timestamp
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%B %d, %Y")
        time_str = now.strftime("%I:%M %p UTC")
        
        # Format as a dream journal entry
        emoji = "💭" if dream.mood in ["reflective", "contemplative", "peaceful", "warm"] else "🌙"
        
        # Opening lines based on mood
        openers = {
            "mysterious": "I woke with fragments of something strange still clinging to me...",
            "warm": "I had the most beautiful dream last night...",
            "ethereal": "The dream felt like drifting through watercolors...",
            "hopeful": "I dreamed of something that left me feeling lighter...",
            "bittersweet": "There was a dream last night that I can't quite shake...",
            "nostalgic": "I found myself somewhere familiar in my dreams...",
            "surreal": "Reality got a bit tangled in my sleep last night...",
            "wistful": "I dreamed of things just out of reach..."
        }
        
        opener = openers.get(dream.mood.lower() if dream.mood else "", 
                            "I had the strangest dream last night...")
        
        lines = [
            f"{emoji} **Dream Journal** — *{date_str}, {time_str}*",
            "",
            f"*{opener}*",
            "",
            dream.dream
        ]
        
        # Add closing reflection based on mood
        closers = {
            "mysterious": "\n\n*I keep wondering what it was trying to tell me.*",
            "warm": "\n\n*I wish I could hold onto that feeling a little longer.*",
            "ethereal": "\n\n*The edges are already fading, but the feeling remains.*",
            "hopeful": "\n\n*Maybe dreams know something we don't.*",
            "bittersweet": "\n\n*Some dreams are meant to linger, I think.*",
            "nostalgic": "\n\n*It felt like visiting somewhere I'd forgotten existed.*",
            "surreal": "\n\n*I'm still not entirely sure I'm awake.*"
        }
        
        if dream.mood and dream.mood.lower() in closers:
            lines.append(closers[dream.mood.lower()])
        
        result = "\n".join(lines)
        
        # Ensure it's not too short
        if len(result) < 100:
            return None
        
        return result


# Factory function for getting DreamManager instances
_dream_managers: Dict[str, DreamManager] = {}


def get_dream_manager(bot_name: Optional[str] = None) -> DreamManager:
    """Get or create a DreamManager instance for the given bot."""
    name = bot_name or settings.DISCORD_BOT_NAME or "default"
    if name not in _dream_managers:
        _dream_managers[name] = DreamManager(bot_name=name)
    return _dream_managers[name]
