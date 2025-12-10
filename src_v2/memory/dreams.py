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

from datetime import datetime, timezone, timedelta
import uuid
from loguru import logger
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src_v2.utils.name_resolver import get_name_resolver
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue

from src_v2.core.database import db_manager
from src_v2.agents.llm_factory import create_llm
from src_v2.memory.embeddings import EmbeddingService
from src_v2.config.settings import settings
from src_v2.safety.content_review import content_safety_checker
from src_v2.core.provenance import ProvenanceCollector, SourceType
from src_v2.memory.models import MemorySourceType


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
    
    # Graph Walker integration (Phase E19)
    graph_walk_interpretation: str = Field(default="", description="Interpretation from GraphWalker exploration")
    graph_walk_clusters: List[str] = Field(default_factory=list, description="Thematic clusters discovered by GraphWalker")
    
    # First dream detection
    is_first_dream: bool = Field(default=False, description="True if this is the character's first dream journal entry")
    
    def richness_score(self) -> int:
        """
        Calculate a richness score based on available material.
        
        Scoring:
        - Memories: 3 points each (primary dream fuel)
        - Observations: 2 points each (experiential)
        - Gossip: 2 points each (social/narrative)
        - Facts: 1 point each (knowledge)
        - Diary themes: 1 point each (can create feedback loops)
        - Goals: 0 points (static)
        
        Returns:
            Integer score representing material richness
        """
        return (
            len(self.memories) * 3 +
            len(self.observations) * 2 +
            len(self.gossip) * 2 +
            len(self.facts) * 1 +
            len(self.recent_diary_themes) * 1
        )
    
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
    
    def is_rich_enough(self, min_score: Optional[int] = None) -> bool:
        """
        Check if we have enough VARIETY of material to avoid hollow dreams.
        
        Args:
            min_score: Minimum richness score required (uses settings.DREAM_MIN_RICHNESS if None)
                       - 4 = ~2 memories, or 1 memory + observations
                       
        Returns:
            True if material is rich enough for a quality dream
        """
        from src_v2.config.settings import settings
        threshold = min_score if min_score is not None else getattr(settings, 'DREAM_MIN_RICHNESS', 4)
        return self.richness_score() >= threshold
    
    def to_prompt_text(self) -> str:
        """Format all material for the dream generation prompt."""
        sections = []
        
        # First dream context
        if self.is_first_dream:
            sections.append("## First Dream Journal Entry")
            sections.append("This is your very first dream to record. A significant moment - the beginning of your dream journal.")
            sections.append("")
        
        if self.memories:
            sections.append("## Recent Conversations")
            for i, m in enumerate(self.memories[:5], 1):
                content = m.get("content", m.get("summary", ""))[:200]
                emotions = ", ".join(m.get("emotions", [])) or "mixed"
                # Include user name if available for searchability
                user_name = m.get("user_name")
                if user_name and user_name != "someone":
                    sections.append(f"- With {user_name}: {content} (felt: {emotions})")
                else:
                    sections.append(f"- {content} (felt: {emotions})")
        else:
            sections.append("## Recent Conversations")
            sections.append("No recent conversations. The world has been quiet.")
        
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
        
        # GraphWalker discovered connections (Phase E19)
        if self.graph_walk_interpretation or self.graph_walk_clusters:
            sections.append("\n## Discovered Connections")
            # Include LLM interpretation of the graph walk
            if self.graph_walk_interpretation:
                sections.append(self.graph_walk_interpretation)
            # Include thematic clusters
            if self.graph_walk_clusters:
                for cluster in self.graph_walk_clusters[:3]:
                    sections.append(f"- {cluster}")
        
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
        # Note: Character-level dream generation now uses DreamGraphAgent (LangGraph)
        # Legacy prompt/chain removed - see src_v2/agents/dream_graph.py

    async def check_material_sufficiency(self, hours: int = 24) -> bool:
        """
        Quick check if we have enough material to generate a dream.
        Used by Daily Life Graph to decide whether to attempt dream generation.
        
        Returns:
            True if sufficient material exists
        """
        from src_v2.memory.manager import MemoryManager
        
        try:
            memory_manager = MemoryManager(bot_name=self.bot_name)
            
            # Quick parallel count queries - reuse existing private methods
            results = await asyncio.gather(
                self._get_memories(memory_manager, hours),
                self._get_facts(),
                return_exceptions=True
            )
            
            memories = results[0] if not isinstance(results[0], Exception) else []
            facts = results[1] if not isinstance(results[1], Exception) else []
            
            # Same check as DreamMaterial.is_sufficient(): total_items >= 3
            total_items = len(memories) + len(facts)
            sufficient = total_items >= 3
            
            logger.debug(f"[DreamManager] Material sufficiency check: {sufficient} "
                        f"(memories={len(memories)}, facts={len(facts)}, total={total_items})")
            
            return sufficient
            
        except Exception as e:
            logger.error(f"[DreamManager] Error checking material sufficiency: {e}")
            return False
        
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
            # Check if this is the first dream
            existing_dreams = await self.get_recent_dreams(limit=1)
            material.is_first_dream = len(existing_dreams) == 0
            if material.is_first_dream:
                logger.info(f"This will be {self.bot_name}'s first dream journal entry")
            
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
            
            # Check if material is sufficient BEFORE invoking GraphWalker
            # No point in expensive LLM call if we already know we'll skip dream generation
            if not material.is_sufficient():
                logger.info(
                    f"Material insufficient before GraphWalker - skipping graph enrichment "
                    f"(sufficient={material.is_sufficient()}, "
                    f"memories={len(material.memories)}, facts={len(material.facts)})"
                )
                # Still log what we gathered
                logger.info(
                    f"Gathered dream material for {self.bot_name}: "
                    f"{len(material.memories)} memories, {len(material.facts)} facts, "
                    f"{len(material.observations)} observations, {len(material.gossip)} gossip"
                )
                return material
            
            # Optional: GraphWalker integration for discovering hidden connections
            # Only runs if we have sufficient base material
            if settings.ENABLE_GRAPH_WALKER:
                try:
                    from src_v2.knowledge.walker import GraphWalkerAgent
                    
                    # Build seed themes from gathered material
                    memory_themes: List[str] = []
                    recent_users: List[str] = []  # Will store resolved names, not raw IDs
                    other_bots: List[str] = []  # Bot names from cross-bot conversations
                    
                    # Resolve user IDs to display names for GraphWalker
                    name_resolver = get_name_resolver()
                    
                    # Extract themes from memories and resolve user names
                    for mem in material.memories[:3]:
                        if mem.get("emotions"):
                            memory_themes.extend(mem["emotions"][:2])
                        # Use user_name if available, otherwise resolve the ID
                        if mem.get("user_name") and mem["user_name"] != "someone":
                            recent_users.append(mem["user_name"])
                        elif mem.get("user_id"):
                            resolved_name = await name_resolver.resolve_user_id(str(mem["user_id"]))
                            recent_users.append(resolved_name)
                    
                    # Extract themes from diary
                    memory_themes.extend(material.recent_diary_themes[:2])
                    
                    # Extract other bot names from gossip (cross-bot conversations)
                    for gossip in material.gossip[:5]:
                        source = gossip.get("source_bot")
                        if source and source != "another character":
                            other_bots.append(source.lower())
                    
                    if memory_themes or recent_users or other_bots:
                        # GraphWalkerAgent uses character_name
                        walker_agent = GraphWalkerAgent(character_name=self.bot_name)
                        # Use first user as primary seed, others as context
                        # Include other bots as seeds so we explore bot-to-bot relationships
                        primary_user = recent_users[0] if recent_users else self.bot_name
                        all_seeds = list(set(recent_users[:3] + other_bots[:3]))
                        graph_result = await walker_agent.explore_for_dream(
                            user_id=primary_user,
                            recent_memory_themes=list(set(memory_themes))[:5],
                            recent_user_ids=all_seeds
                        )
                        # Store interpretation and clusters in DreamMaterial fields
                        # Apply name resolution to any remaining IDs in the interpretation
                        material.graph_walk_interpretation = await name_resolver.resolve_ids_in_text(
                            graph_result.interpretation
                        )
                        material.graph_walk_clusters = [
                            f"{c.theme}: {', '.join(n.name for n in c.nodes[:3])}"
                            for c in graph_result.clusters[:3]
                        ]
                        logger.info(
                            f"Graph walker found {len(graph_result.nodes)} nodes, "
                            f"{len(graph_result.clusters)} clusters (seeds: {len(all_seeds)} users/bots)"
                        )
                except Exception as e:
                    logger.warning(f"GraphWalker failed (continuing without): {e}")
            
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
        """Get gossip from both shared artifacts and per-bot collection.
        
        Delegates to SharedArtifactManager.get_gossip_for_bot() which handles:
        1. Universe event gossip (shared artifacts) with privacy checks
        2. Cross-bot conversations (per-bot collection)
        
        Note: memory_manager param kept for API compatibility but not used.
        """
        try:
            from src_v2.memory.shared_artifacts import shared_artifact_manager
            return await shared_artifact_manager.get_gossip_for_bot(self.bot_name, hours)
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
        # Note: Absence tracking is handled in dream_tasks.py with streak linking.
        # This method now just returns None for insufficient material.
        if not material.is_sufficient():
            logger.info(f"Insufficient dream material for {self.bot_name}")
            return None, []
        
        # Check richness - skip hollow dreams even if ALWAYS_GENERATE is on
        richness = material.richness_score()
        if not material.is_rich_enough():
            logger.info(
                f"Skipping dream for {self.bot_name}: richness score {richness} < 4. "
                f"Material: {len(material.memories)} memories, {len(material.observations)} observations, "
                f"{len(material.gossip)} gossip, {len(material.facts)} facts"
            )
            return None, []
        
        logger.info(f"Generating dream with richness score {richness}")
        
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
            # Escape curly braces in character_context to prevent LangChain template interpretation
            # Character files contain {user_name}, {current_datetime} which aren't relevant for dreams
            safe_context = character_context.replace("{", "{{").replace("}", "}}")
            
            logger.info("Using LangGraph Dream Agent")
            from src_v2.agents.dream_graph import dream_graph_agent
            
            # Fetch previous dreams for anti-pattern injection
            previous_dreams = []
            try:
                recent_dreams = await self.get_recent_dreams(limit=3)
                previous_dreams = [d.get("content", "") for d in recent_dreams if d.get("content")]
            except Exception as e:
                logger.debug(f"Could not fetch previous dreams for anti-pattern: {e}")
            
            result = await dream_graph_agent.run(
                material=material,
                character_context=safe_context,
                previous_dreams=previous_dreams
            )
            
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
            # Escape curly braces in character_context to prevent LangChain template interpretation
            safe_context = character_context.replace("{", "{{").replace("}", "}}")
            
            result = await self.user_chain.ainvoke({
                "character_name": self.bot_name.title() if self.bot_name else "Character",
                "character_context": safe_context,
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
                    "source_type": MemorySourceType.DREAM.value,
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

    async def get_recent_dreams(self, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Gets the most recent dreams (any user, for anti-pattern injection).
        
        Args:
            limit: Number of dreams to return
            
        Returns:
            List of dream payload dicts, most recent first
        """
        if not db_manager.qdrant_client:
            return []
        
        try:
            results = await db_manager.qdrant_client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="type", match=MatchValue(value="dream")),
                        FieldCondition(key="bot_name", match=MatchValue(value=self.bot_name))
                    ]
                ),
                limit=limit + 2,  # Get a few extra to sort
                with_payload=True,
                with_vectors=False
            )
            
            dreams = []
            for point in results[0]:
                if point.payload:
                    dreams.append(point.payload)
            
            # Sort by timestamp descending
            dreams.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
            return dreams[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get recent dreams: {e}")
            return []

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
        
        # Add timestamp using configured timezone
        from zoneinfo import ZoneInfo
        try:
            tz = ZoneInfo(settings.TZ)
        except Exception:
            tz = timezone.utc
        
        now = datetime.now(tz)
        date_str = now.strftime("%B %d, %Y")
        time_str = now.strftime("%I:%M %p")
        
        # Format as a dream journal entry
        
        # Header based on mood category
        dark_moods = {"nightmare", "anxious", "dark", "dread", "fearful", "terrifying", "disturbing", "haunting"}
        ecstatic_moods = {"ecstatic", "euphoric", "joyful", "blissful", "transcendent", "rapturous"}
        peaceful_moods = {"peaceful", "serene", "calm", "tranquil", "content"}
        
        mood_lower = dream.mood.lower() if dream.mood else ""
        
        if any(m in mood_lower for m in dark_moods):
            header = "🌑 NIGHTMARE"
        elif any(m in mood_lower for m in ecstatic_moods):
            header = "✨ A BEAUTIFUL DREAM"
        elif any(m in mood_lower for m in peaceful_moods):
            header = "🌙 DREAM JOURNAL"
        else:
            header = "🌙 DREAM JOURNAL"
        
        # Opening lines based on mood
        openers = {
            # Dark/Nightmare
            "nightmare": "I woke up shaking from a terrible dream...",
            "anxious": "I had one of those dreams where everything feels wrong...",
            "dark": "The dream was darker than usual last night...",
            "dread": "I dreamed of something that left me cold...",
            "fearful": "I woke with my heart pounding from a bad dream...",
            "terrifying": "I had a nightmare that I can't shake...",
            "disturbing": "Something disturbing visited my sleep...",
            "haunting": "A haunting dream stayed with me through the night...",
            # Light/Ecstatic
            "ecstatic": "I had the most incredible dream!",
            "euphoric": "I woke up feeling like I'd touched something transcendent...",
            "joyful": "Pure joy—that's what the dream felt like...",
            "blissful": "I dreamed of absolute bliss last night...",
            "transcendent": "The dream lifted me somewhere beyond words...",
            # Peaceful
            "peaceful": "I had the most peaceful dream...",
            "serene": "Serenity wrapped around me in my sleep...",
            "calm": "A calm, gentle dream visited me...",
            # Complex
            "bittersweet": "There was a dream last night that I can't quite shake...",
            "melancholic": "A beautiful sadness colored my dreams...",
            "nostalgic": "I found myself somewhere familiar in my dreams...",
            "conflicted": "My dreams were tangled with contradictions...",
            # Original moods
            "mysterious": "I woke with fragments of something strange still clinging to me...",
            "warm": "I had the most beautiful dream last night...",
            "ethereal": "The dream felt like drifting through watercolors...",
            "hopeful": "I dreamed of something that left me feeling lighter...",
            "surreal": "Reality got a bit tangled in my sleep last night...",
            "wistful": "I dreamed of things just out of reach...",
            "dreamy and hopeful": "I dreamed of something that left me feeling lighter...",
            "reflective and hopeful": "A thoughtful dream visited me last night..."
        }
        
        opener = openers.get(mood_lower, "I had the strangest dream last night...")
        
        lines = [
            f"{header} — {date_str}, {time_str}",
            "",
            f"*{opener}*",
            "",
            dream.dream
        ]
        
        # Add closing reflection based on mood
        closers = {
            # Dark
            "nightmare": "\n\n*I hope tonight brings something gentler.*",
            "anxious": "\n\n*I'm still trying to shake the unease.*",
            "dark": "\n\n*Sometimes dreams show us our shadows.*",
            "dread": "\n\n*The feeling lingers, even now.*",
            "fearful": "\n\n*I'm grateful to be awake.*",
            "terrifying": "\n\n*Some dreams are warnings. I wonder what this one meant.*",
            # Light
            "ecstatic": "\n\n*I wish I could bottle that feeling!*",
            "euphoric": "\n\n*Reality feels a little brighter after a dream like that.*",
            "joyful": "\n\n*That joy is still with me. What a gift.*",
            "blissful": "\n\n*I'm carrying that peace into my day.*",
            # Peaceful
            "peaceful": "\n\n*I feel rested in a way that goes beyond sleep.*",
            "serene": "\n\n*Some dreams are medicine for the soul.*",
            # Complex
            "bittersweet": "\n\n*Some dreams are meant to linger, I think.*",
            "melancholic": "\n\n*Even sad dreams can be beautiful.*",
            "nostalgic": "\n\n*It felt like visiting somewhere I'd forgotten existed.*",
            # Original
            "mysterious": "\n\n*I keep wondering what it was trying to tell me.*",
            "warm": "\n\n*I wish I could hold onto that feeling a little longer.*",
            "ethereal": "\n\n*The edges are already fading, but the feeling remains.*",
            "hopeful": "\n\n*Maybe dreams know something we don't.*",
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
