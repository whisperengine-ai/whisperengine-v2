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
from zoneinfo import ZoneInfo
import uuid
from loguru import logger
from langchain_core.prompts import ChatPromptTemplate
from src_v2.utils.validation import smart_truncate
from src_v2.memory.models import MemorySourceType
from src_v2.memory.autonomous_actions import get_autonomous_actions, DIARY_AUTONOMOUS_ACTION_LIMIT
from pydantic import BaseModel, Field
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue

from src_v2.core.database import db_manager
from src_v2.agents.llm_factory import create_llm
from src_v2.memory.embeddings import EmbeddingService
from src_v2.config.settings import settings
from src_v2.safety.content_review import content_safety_checker
from src_v2.utils.name_resolver import get_name_resolver
from src_v2.core.provenance import ProvenanceCollector
from src_v2.utils.time_utils import get_configured_timezone


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
    
    # Autonomous activity (Phase E35 - Bot's own posts/replies)
    autonomous_actions: List[Dict[str, Any]] = Field(default_factory=list, description="Bot's autonomous posts and replies")
    
    # Time period context (spans since last diary entry)
    last_entry_date: Optional[str] = Field(default=None, description="Date of last diary entry (YYYY-MM-DD)")
    days_since_last_entry: Optional[int] = Field(default=None, description="Days since last diary entry")
    is_first_entry: bool = Field(default=False, description="True if this is the character's first diary entry")
    
    # Graph Walker integration (Phase E19)
    graph_walk_interpretation: str = Field(default="", description="Interpretation from GraphWalker exploration")
    graph_walk_clusters: List[str] = Field(default_factory=list, description="Thematic clusters discovered by GraphWalker")
    
    def richness_score(self) -> int:
        """
        Calculate a richness score based on available material.
        
        Scoring:
        - Summaries: 3 points each (primary content)
        - Autonomous actions: 1 point each (bot's own posts/replies - less weight than interactions)
        - Observations: 2 points each (bot's own experiences)
        - Gossip: 2 points each (social context)
        - Epiphanies: 2 points each (insights)
        - New facts: 1 point each (learned info)
        - Goals: 0 points (static, always available)
        
        Returns:
            Integer score representing material richness
        """
        return (
            len(self.summaries) * 3 +
            len(self.autonomous_actions) * 1 +  # Reduced: Own output is less important than interactions
            len(self.observations) * 2 +
            len(self.gossip) * 2 +
            len(self.epiphanies) * 2 +
            len(self.new_facts) * 1
        )
    
    def is_sufficient(self) -> bool:
        """Check if we have enough material to generate a diary."""
        # If always generate is on, we don't need summaries
        if settings.DIARY_ALWAYS_GENERATE:
            return True
            
        # Need at least some summaries OR some autonomous actions
        # Autonomous activity alone is worth writing about
        return len(self.summaries) >= 1 or len(self.autonomous_actions) >= 1
    
    def is_rich_enough(self, min_score: Optional[int] = None) -> bool:
        """
        Check if we have enough VARIETY of material to avoid hollow entries.
        
        Args:
            min_score: Minimum richness score required (uses settings.DIARY_MIN_RICHNESS if None)
                       - 5 = ~2 conversations, or 1 conversation + some observations
                       
        Returns:
            True if material is rich enough for a quality entry
        """
        threshold = min_score if min_score is not None else settings.DIARY_MIN_RICHNESS
        return self.richness_score() >= threshold
    
    def to_prompt_text(self) -> str:
        """Format all material for the diary generation prompt."""
        sections = []
        
        # Add time period context at the beginning
        if self.is_first_entry:
            sections.append("## Time Period")
            sections.append("This is my FIRST diary entry. I should introduce myself and reflect on my early experiences.")
            sections.append("")
        elif self.days_since_last_entry is not None:
            sections.append("## Time Period")
            if self.days_since_last_entry == 1:
                sections.append(f"Last entry: yesterday ({self.last_entry_date})")
            elif self.days_since_last_entry <= 3:
                sections.append(f"Last entry: {self.days_since_last_entry} days ago ({self.last_entry_date})")
            elif self.days_since_last_entry <= 7:
                sections.append(f"Last entry: about a week ago ({self.last_entry_date}). It's been a while since I wrote.")
            else:
                sections.append(f"Last entry: {self.days_since_last_entry} days ago ({self.last_entry_date}). It's been too long since I last wrote!")
            sections.append("")
        
        if self.summaries:
            sections.append("## Conversations Since Last Entry")
            for i, s in enumerate(self.summaries[:10], 1):
                emotions = ", ".join(s.get("emotions", [])) or "neutral"
                topics = ", ".join(s.get("topics", [])) or "general chat"
                sections.append(f"[Session {i}]")
                sections.append(f"Emotions: {emotions}")
                sections.append(f"Topics: {topics}")
                sections.append(f"Summary: {s.get('content', 'No summary')}\n")
        else:
            if not self.autonomous_actions:
                # Only say "quiet day" if we also had no autonomous activity
                sections.append("## Conversations Today")
                sections.append("No conversations occurred today. The day was quiet and solitary. Reflect on this silence, your internal state, and your observations of the world.")
        
        # Autonomous Activity (Phase E35) - Bot's own posts and replies
        if self.autonomous_actions:
            sections.append("\n## My Own Actions Today")
            sections.append("These are things I chose to do on my own initiative (not in response to direct mentions):")
            for action in self.autonomous_actions[:5]: # Limit to top 5 to avoid diary domination
                action_type = action.get("action_type", "post")
                channel = action.get("channel_name", "a channel")
                content = smart_truncate(action.get("content", ""), max_length=200)
                context = action.get("context", "")
                
                if action_type == "reply":
                    sections.append(f"- I replied in #{channel}: \"{content}\"")
                    if context:
                        sections.append(f"  (responding to: {smart_truncate(context, max_length=100)})")
                elif action_type == "react":
                    emoji = action.get("emoji", "👍")
                    sections.append(f"- I reacted with {emoji} in #{channel}")
                else:  # post
                    sections.append(f"- I posted in #{channel}: \"{content}\"")
        
        if self.observations:
            sections.append("\n## Things I Noticed Today")
            for obs in self.observations[:5]:
                # Observations from Neo4j have user_id, predicate, object (not content)
                # Format them as natural language without exposing raw IDs
                predicate = obs.get('predicate', '').replace('_', ' ').lower()
                obj = obs.get('object', '')
                if predicate and obj:
                    sections.append(f"- Someone {predicate} {obj}")
                elif obs.get('content'):
                    # Fallback for observations that do have content field
                    sections.append(f"- {obs.get('content', '')} ({obs.get('type', 'observation')})")
        
        if self.gossip:
            sections.append("\n## What I Heard From Others")
            for g in self.gossip[:3]:
                source = g.get("source_bot", "someone")
                raw_content = g.get("content", "")
                content = smart_truncate(raw_content, max_length=150)
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


class DiaryManager:
    """
    Manages generation and retrieval of character diary entries.
    """
    
    def __init__(self, bot_name: Optional[str] = None):
        self.bot_name = bot_name or settings.DISCORD_BOT_NAME or "default"
        self.collection_name = f"whisperengine_memory_{self.bot_name}"
        self.embedding_service = EmbeddingService()
        # Note: Diary generation now uses DiaryGraphAgent (LangGraph)
        # Legacy prompt/chain removed - see src_v2/agents/diary_graph.py

    async def gather_diary_material(self, hours: int = None) -> DiaryMaterial:
        """
        Gathers material from all available sources for diary generation.
        
        The time period spans from the last diary entry to now. If no previous
        diary exists, defaults to 7 days (one week lookback for first entry).
        
        Sources:
        - Session summaries (Qdrant)
        - Bot observations (Neo4j)
        - Gossip memories (Qdrant)
        - Recently learned facts (Neo4j)
        - Character goals (config)
        
        Args:
            hours: Override for lookback period (if None, calculated from last diary)
        
        Returns:
            DiaryMaterial container with all gathered content
        """
        material = DiaryMaterial()
        
        try:
            # Determine time period since last diary entry
            last_entry = await self.get_latest_diary_with_date()
            
            if last_entry:
                last_date_str = last_entry.get("date", "")
                if last_date_str:
                    try:
                        last_date = datetime.strptime(last_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                        days_since = (datetime.now(timezone.utc) - last_date).days
                        material.last_entry_date = last_date_str
                        material.days_since_last_entry = max(1, days_since)  # At least 1 day
                        material.is_first_entry = False
                        # Calculate hours from days (add a buffer for same-day edge case)
                        hours = hours or (days_since * 24 + 12)  # Extra 12 hours buffer
                    except ValueError:
                        # Date parsing failed, use default
                        hours = hours or 24
                        material.is_first_entry = False
                else:
                    hours = hours or 24
                    material.is_first_entry = False
            else:
                # No previous diary - this is the first entry
                material.is_first_entry = True
                hours = hours or (7 * 24)  # 1 week lookback for first entry
                logger.info(f"First diary entry for {self.bot_name}, looking back {hours} hours (1 week)")
            
            from src_v2.memory.manager import MemoryManager
            memory_manager = MemoryManager(bot_name=self.bot_name)
            
            # Run parallel fetches with calculated hours
            results = await asyncio.gather(
                memory_manager.get_summaries_since(hours=hours, limit=50),  # More summaries for longer periods
                self._get_observations(),
                self._get_gossip(hours),
                self._get_new_facts(hours),
                self._get_epiphanies(hours),
                self._get_goals(),
                self._get_autonomous_actions(hours),  # Phase E35: Bot's own posts/replies
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
            if not isinstance(results[6], Exception):
                material.autonomous_actions = results[6]
            
            # Optional: GraphWalker integration for discovering hidden connections
            if settings.ENABLE_GRAPH_WALKER:
                try:
                    from src_v2.knowledge.walker import GraphWalkerAgent
                    
                    # Extract user names from today's interactions (resolved from IDs if needed)
                    today_interactions: List[str] = []  # Will store resolved names, not raw IDs
                    name_resolver = get_name_resolver()
                    
                    for summary in material.summaries:
                        # Use user_name if available, otherwise resolve the ID
                        if summary.get("user_name") and summary["user_name"] != "someone":
                            today_interactions.append(summary["user_name"])
                        elif summary.get("user_id"):
                            resolved_name = await name_resolver.resolve_user_id(str(summary["user_id"]))
                            today_interactions.append(resolved_name)
                    
                    # Also include other bots from gossip (cross-bot conversations)
                    other_bots: List[str] = []
                    for gossip in material.gossip[:5]:
                        source = gossip.get("source_bot")
                        if source and source != "another character":
                            other_bots.append(source.lower())
                    
                    if today_interactions or other_bots:
                        # GraphWalkerAgent uses character_name
                        walker_agent = GraphWalkerAgent(character_name=self.bot_name)
                        # Use first user as primary seed, others as context
                        # Include other bots as seeds so we explore bot-to-bot relationships
                        primary_user = today_interactions[0] if today_interactions else self.bot_name
                        all_interactions = list(set(today_interactions[:5] + other_bots[:3]))
                        
                        graph_result = await walker_agent.explore_for_diary(
                            user_id=primary_user,
                            today_interactions=all_interactions
                        )
                        
                        # Store interpretation and clusters in DiaryMaterial fields
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
                            f"{len(graph_result.clusters)} clusters for diary (seeds: {len(all_interactions)} users/bots)"
                        )
                except Exception as e:
                    logger.warning(f"GraphWalker failed for diary (continuing without): {e}")
            
            logger.info(
                f"Gathered diary material for {self.bot_name}: "
                f"{len(material.summaries)} summaries, {len(material.autonomous_actions)} autonomous actions, "
                f"{len(material.observations)} observations, {len(material.gossip)} gossip, "
                f"{len(material.new_facts)} facts, {len(material.epiphanies)} epiphanies"
            )
            
        except Exception as e:
            logger.error(f"Failed to gather diary material: {type(e).__name__}: {e}")
        
        return material
    
    async def _get_observations(self) -> List[Dict[str, Any]]:
        """Get recent observations made by this bot."""
        try:
            from src_v2.knowledge.manager import knowledge_manager
            return await knowledge_manager.get_recent_observations_by(self.bot_name, limit=10)
        except Exception as e:
            logger.debug(f"Failed to get observations for diary: {e}")
            return []
    
    async def _get_autonomous_actions(self, hours: int) -> List[Dict[str, Any]]:
        """Get the bot's own autonomous posts and replies. Delegates to shared utility."""
        return await get_autonomous_actions(
            collection_name=self.collection_name,
            hours=hours,
            limit=DIARY_AUTONOMOUS_ACTION_LIMIT
        )
    
    async def _get_gossip(self, hours: int) -> List[Dict[str, Any]]:
        """Get gossip from both shared artifacts and per-bot collection.
        
        Delegates to SharedArtifactManager.get_gossip_for_bot() which handles:
        1. Universe event gossip (shared artifacts) with privacy checks
        2. Cross-bot conversations (per-bot collection)
        """
        try:
            from src_v2.memory.shared_artifacts import shared_artifact_manager
            return await shared_artifact_manager.get_gossip_for_bot(self.bot_name, hours)
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
            
            # Defensive: check results tuple
            if not results or not isinstance(results, tuple) or len(results) < 1:
                return []
            
            points = results[0] or []
            epiphanies = []
            for point in points:
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
        character_context: str,
        override: bool = False
    ) -> Tuple[Optional[DiaryEntry], List[Dict[str, Any]]]:
        """
        Generates a diary entry from gathered material (multi-source).
        
        Args:
            material: DiaryMaterial with all sources
            character_context: Character's personality context
            override: If True, ignore sufficiency check
            
        Returns:
            Tuple of (DiaryEntry, provenance_data) if successful
        """
        # Note: Absence tracking is now handled in diary_tasks.py with streak linking.
        # This method just returns None for insufficient material.
        if not override and not material.is_sufficient():
            logger.info(f"Insufficient diary material for {self.bot_name}")
            return None, []
        
        # Check richness - skip hollow entries even if ALWAYS_GENERATE is on
        richness = material.richness_score()
        if not override and not material.is_rich_enough():
            logger.info(
                f"Skipping diary for {self.bot_name}: richness score {richness} < 5. "
                f"Material: {len(material.summaries)} summaries, {len(material.observations)} observations, "
                f"{len(material.gossip)} gossip, {len(material.epiphanies)} epiphanies"
            )
            return None, []
        
        logger.info(f"Generating diary with richness score {richness}")
        
        collector = ProvenanceCollector("diary", self.bot_name)
        
        # Resolve all user IDs to names upfront for provenance and generation
        name_resolver = get_name_resolver()
        resolved_names_cache: Dict[str, str] = {}  # Cache resolved names for this generation
        
        async def get_display_name(summary: Dict[str, Any]) -> str:
            """Get display name from summary, resolving ID if needed."""
            if summary.get("user_name") and summary["user_name"] != "someone":
                return summary["user_name"]
            user_id = summary.get("user_id")
            if user_id:
                if str(user_id) not in resolved_names_cache:
                    resolved_names_cache[str(user_id)] = await name_resolver.resolve_user_id(str(user_id))
                return resolved_names_cache[str(user_id)]
            return "someone"
        
        # Add provenance for each source (with resolved names)
        for s in material.summaries[:10]:
            display_name = await get_display_name(s)
            collector.add_conversation(
                who=display_name,
                topic=", ".join(s.get("topics", ["chat"])),
                where="chat",
                when="today",
                technical={"session_id": s.get("session_id")}
            )
        
        for obs in material.observations[:5]:
            collector.add_observation(obs.get("content", "")[:100])
        
        try:
            # Escape curly braces in character_context to prevent LangChain template interpretation
            safe_context = character_context.replace("{", "{{").replace("}", "}}")
            
            logger.info("Using LangGraph Diary Agent")
            from src_v2.agents.diary_graph import diary_graph_agent
            
            # Extract user names from summaries for the agent (resolved)
            user_names = []
            for s in material.summaries:
                user_names.append(await get_display_name(s))
            user_names = list(set(user_names))
            
            # Fetch previous diary entries for anti-pattern injection
            previous_entries = []
            try:
                recent_diaries = await self.get_recent_diary(days=3)
                previous_entries = [d.get("content", "") for d in recent_diaries if d.get("content")]
            except Exception as e:
                logger.debug(f"Could not fetch previous diaries for anti-pattern: {e}")
            
            result = await diary_graph_agent.run(
                material=material,
                character_context=safe_context,
                user_names=user_names,
                previous_entries=previous_entries
            )
            
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
        user_names: List[str],
        override: bool = False
    ) -> Tuple[Optional[DiaryEntry], List[Dict[str, Any]]]:
        """
        Generates a diary entry from the day's session summaries.
        (Legacy method - now uses enhanced material gathering)
        
        Args:
            summaries: List of summary dicts with 'content', 'emotions', 'topics'
            character_context: Character's purpose, drives, and constitution (from core.yaml)
            user_names: List of display names the character interacted with today
            override: If True, ignore sufficiency check
            
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
        
        return await self.generate_diary_from_material(material, character_context, override=override)

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
                    "source_type": MemorySourceType.DIARY.value,
                    "bot_name": self.bot_name,
                    "date": date_str,
                    "content": entry.entry,
                    "mood": entry.mood,
                    "notable_users": entry.notable_users,
                    "themes": entry.themes,
                    "emotional_highlights": entry.emotional_highlights,
                    "provenance": provenance or [],
                    "timestamp": entry_date.isoformat(),
                    "visibility": "private",  # Character's private diary
                    # ADR-014: Author tracking - diaries are bot-authored
                    "author_id": self.bot_name,
                    "author_is_bot": True,
                    "author_name": self.bot_name
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
            logger.error(f"Failed to save diary entry: {type(e).__name__}: {e}")
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
            
            # Handle scroll result - it's a tuple of (points, next_page_offset)
            if not results or not isinstance(results, tuple) or len(results) < 1:
                logger.debug(f"No diary scroll results for {self.bot_name}")
                return []
            
            points = results[0] or []
            entries = []
            for point in points:
                payload = point.payload
                if payload and payload.get("date", "") >= threshold_str:
                    entries.append(payload)
            
            # Sort by date descending
            entries.sort(key=lambda x: x.get("date", ""), reverse=True)
            
            return entries[:days]
            
        except Exception as e:
            logger.error(f"Failed to retrieve recent diaries: {type(e).__name__}: {e}")
            return []

    async def get_latest_diary(self) -> Optional[Dict[str, Any]]:
        """
        Gets the most recent diary entry.
        
        Returns:
            Diary payload dict or None
        """
        entries = await self.get_recent_diary(days=1)
        return entries[0] if entries else None

    async def get_latest_diary_with_date(self) -> Optional[Dict[str, Any]]:
        """
        Gets the most recent diary entry regardless of how old it is.
        
        Unlike get_latest_diary() which only looks back 1 day, this method
        searches all diary entries to find the absolute most recent one.
        Used for calculating time spans between diary entries.
        
        Returns:
            Diary payload dict with 'date' field, or None if no diaries exist
        """
        if not db_manager.qdrant_client:
            return None
        
        try:
            # Scroll through diary entries without date filter
            results = await db_manager.qdrant_client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="type", match=MatchValue(value="diary")),
                        FieldCondition(key="bot_name", match=MatchValue(value=self.bot_name))
                    ]
                ),
                limit=10,  # Get a few to find the most recent
                with_payload=True,
                with_vectors=False
            )
            
            # Defensive: check results tuple
            if not results or not isinstance(results, tuple) or len(results) < 1:
                return None
            
            points = results[0] or []
            if not points:
                return None
            
            # Find the entry with the most recent date
            entries = [p.payload for p in points if p.payload and p.payload.get("date")]
            if not entries:
                return None
            
            # Sort by date descending and return the most recent
            entries.sort(key=lambda x: x.get("date", ""), reverse=True)
            return entries[0]
            
        except Exception as e:
            logger.debug(f"Failed to get latest diary with date: {e}")
            return None

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
            logger.error(f"Failed to search diaries: {type(e).__name__}: {e}")
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
            
            # Defensive: check results tuple
            if not results or not isinstance(results, tuple) or len(results) < 1:
                return False
            
            points = results[0] or []
            return len(points) > 0
            
        except Exception as e:
            logger.error(f"Failed to check for today's diary: {type(e).__name__}: {e}")
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
            
            # Add timestamp header with mood-aware formatting
            tz = get_configured_timezone()
            now = datetime.now(tz)
            date_str = now.strftime("%B %d, %Y")
            time_str = now.strftime("%I:%M %p %Z")
            
            # Header and opener based on mood category
            mood_lower = (entry.mood or "").lower()
            
            dark_moods = {"frustrated", "anxious", "melancholic", "conflicted", "sad", "exhausted", "overwhelmed"}
            joyful_moods = {"joyful", "euphoric", "grateful", "excited", "delighted", "happy"}
            peaceful_moods = {"peaceful", "content", "serene", "calm", "satisfied"}
            
            if any(m in mood_lower for m in dark_moods):
                header = "🌧️ A DIFFICULT DAY"
                opener = "*Today was hard.*\n\n"
            elif any(m in mood_lower for m in joyful_moods):
                header = "☀️ A WONDERFUL DAY"
                opener = "*What a day!*\n\n"
            elif any(m in mood_lower for m in peaceful_moods):
                header = "📝 DIARY ENTRY"
                opener = "*A quiet day to reflect.*\n\n"
            else:
                header = "📝 DIARY ENTRY"
                opener = ""
            
            formatted = f"{header} — {date_str}, {time_str}\n\n{opener}{result.content.strip()}"
            return formatted
            
        except Exception as e:
            logger.error(f"Failed to create public diary version: {type(e).__name__}: {e}")
            return None


# Factory function for getting DiaryManager instances
_diary_managers: Dict[str, DiaryManager] = {}

def get_diary_manager(bot_name: Optional[str] = None) -> DiaryManager:
    """Get or create a DiaryManager instance for the given bot."""
    name = bot_name or settings.DISCORD_BOT_NAME or "default"
    if name not in _diary_managers:
        _diary_managers[name] = DiaryManager(bot_name=name)
    return _diary_managers[name]
