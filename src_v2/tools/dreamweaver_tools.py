"""
DreamWeaver Tools - Specialized tools for narrative generation (dreams & diaries).

PHILOSOPHY:
This module provides tools for batch-mode narrative generation. Unlike real-time
chat, the DreamWeaver has time to:
1. Reflect deeply on questions users have asked
2. Correlate information across multiple users
3. Generate thoughtful, community-relevant insights

KEY FEATURE - "Deep Answers":
The diary becomes a vehicle for the bot to revisit interesting questions and
provide deeper, more thoughtful answers than real-time allows. This creates
value for the community who sees these diary broadcasts.

TOOLS:
- INTROSPECTION: Search memories, facts, observations (batch-friendly versions)
- QUESTION REFLECTION: Find interesting questions to elaborate on
- PLANNING: Structure narrative arcs
- WEAVING: Generate final narratives
"""
from typing import Type, Optional, List, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from loguru import logger

from src_v2.memory.manager import memory_manager
from src_v2.knowledge.manager import knowledge_manager
from src_v2.config.settings import settings


# =============================================================================
# INTROSPECTION TOOLS - Batch-friendly versions that search across ALL users
# =============================================================================

class SearchMeaningfulMemoriesInput(BaseModel):
    limit: int = Field(default=10, description="Maximum number of memories to return")
    min_meaningfulness: float = Field(default=0.7, description="Minimum meaningfulness score (0-1)")


class SearchMeaningfulMemoriesTool(BaseTool):
    """Search for emotionally significant memories from recent interactions."""
    name: str = "search_meaningful_memories"
    description: str = """Find the most emotionally significant memories from recent interactions.
These are moments that had high meaningfulness scores - important conversations, 
emotional exchanges, breakthroughs, or memorable interactions across ALL users."""
    args_schema: Type[BaseModel] = SearchMeaningfulMemoriesInput
    
    character_name: str = Field(exclude=True)

    def _run(self, limit: int = 10, min_meaningfulness: float = 0.7) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, limit: int = 10, min_meaningfulness: float = 0.7) -> str:
        try:
            collection = f"whisperengine_memory_{self.character_name}"
            memories = await memory_manager.get_high_meaningfulness_memories(
                min_meaningfulness=min_meaningfulness,
                limit=limit,
                collection_name=collection
            )
            
            if not memories:
                return "No high-meaningfulness memories found recently."
            
            results = []
            for m in memories:
                content = m.get("content", "")[:300]
                emotions = ", ".join(m.get("emotions", [])) or "mixed"
                score = m.get("meaningfulness_score", 0)
                user = m.get("user_id", "unknown")
                if user and len(user) > 8:
                    user = f"User_{user[-4:]}"
                results.append(f"- [{score:.2f}] (user: {user}, emotions: {emotions})\n  {content}")
            
            return f"Found {len(memories)} meaningful memories:\n\n" + "\n\n".join(results)
            
        except Exception as e:
            logger.error(f"Error searching meaningful memories: {e}")
            return f"Error: {e}"


class SearchSessionSummariesInput(BaseModel):
    query: str = Field(default="today's conversations", description="What to search for")
    hours_back: int = Field(default=24, description="How many hours back to search")
    limit: int = Field(default=10, description="Maximum summaries to return")


class SearchSessionSummariesTool(BaseTool):
    """Search session summaries from recent conversations."""
    name: str = "search_session_summaries"
    description: str = """Search for session summaries from recent conversations across ALL users.
Summaries capture the essence of each conversation session - topics discussed,
emotional tone, and key moments. Good for getting an overview of the day."""
    args_schema: Type[BaseModel] = SearchSessionSummariesInput
    
    character_name: str = Field(exclude=True)

    def _run(self, query: str = "today's conversations", hours_back: int = 24, limit: int = 10) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, query: str = "today's conversations", hours_back: int = 24, limit: int = 10) -> str:
        try:
            collection = f"whisperengine_memory_{self.character_name}"
            summaries = await memory_manager.search_all_summaries(
                query=query,
                collection_name=collection,
                limit=limit,
                hours=hours_back
            )
            
            if not summaries:
                return "No session summaries found for the specified period."
            
            results = []
            for s in summaries:
                content = s.get("content", "")[:400]
                user = s.get("user_id", "unknown")
                if user and len(user) > 8:
                    user = f"User_{user[-4:]}"
                results.append(f"- Session with {user}:\n  {content}")
            
            return f"Found {len(summaries)} session summaries:\n\n" + "\n\n".join(results)
            
        except Exception as e:
            logger.error(f"Error searching summaries: {e}")
            return f"Error: {e}"


class WanderMemoryInput(BaseModel):
    query: str = Field(description="The concept or symbol to search for (e.g., 'apples', 'fear of heights')")
    min_age_days: int = Field(default=30, description="Minimum age of the memory in days (to find distant memories)")
    limit: int = Field(default=5, description="Number of memories to return")


class WanderMemoryTool(BaseTool):
    """Search for memories that are semantically related but temporally distant."""
    name: str = "wander_memory_space"
    description: str = """Use this to find 'deep cuts' - memories from the distant past that relate to a current thought.
This mimics the way dreams connect recent events (day residue) with old, forgotten memories.
Example: If thinking about 'apples', use this to find memories about apples from months ago."""
    args_schema: Type[BaseModel] = WanderMemoryInput
    
    character_name: str = Field(exclude=True)

    def _run(self, query: str, min_age_days: int = 30, limit: int = 5) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, query: str, min_age_days: int = 30, limit: int = 5) -> str:
        try:
            import time
            collection = f"whisperengine_memory_{self.character_name}"
            
            # Calculate max_timestamp (current time - min_age_days)
            max_ts = time.time() - (min_age_days * 86400)
            
            memories = await memory_manager.search_memories_advanced(
                query=query,
                max_timestamp=max_ts,
                limit=limit,
                collection_name=collection
            )
            
            if not memories:
                return f"No distant memories found for '{query}' older than {min_age_days} days."
            
            results = []
            for m in memories:
                content = m.get("content", "")[:300]
                ts = m.get("timestamp", 0)
                date_str = time.strftime('%Y-%m-%d', time.localtime(ts))
                results.append(f"- [{date_str}] {content}")
            
            return f"Found {len(memories)} distant memories for '{query}':\n\n" + "\n\n".join(results)
            
        except Exception as e:
            logger.error(f"Error wandering memory: {e}")
            return f"Error: {e}"


class CheckEmotionalEchoInput(BaseModel):
    emotion: str = Field(description="The emotion to search for (e.g., 'joy', 'anxiety', 'nostalgia')")
    limit: int = Field(default=5, description="Number of memories to return")


class CheckEmotionalEchoTool(BaseTool):
    """Search for memories that match a specific emotional tone."""
    name: str = "check_emotional_echo"
    description: str = """Find memories that share a specific emotional resonance, regardless of the topic.
Useful for connecting disparate events through shared feeling.
Example: If the current theme is 'anxiety', find other times you felt anxiety."""
    args_schema: Type[BaseModel] = CheckEmotionalEchoInput
    
    character_name: str = Field(exclude=True)

    def _run(self, emotion: str, limit: int = 5) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, emotion: str, limit: int = 5) -> str:
        try:
            collection = f"whisperengine_memory_{self.character_name}"
            
            # We search for the emotion as the query, but also filter by metadata if possible
            # For now, we'll rely on semantic search for the emotion + metadata filter
            
            # Try strict metadata filter first (if emotions are stored in metadata)
            memories = await memory_manager.search_memories_advanced(
                query=f"feeling of {emotion}",
                metadata_filter={"emotions": emotion}, 
                limit=limit,
                collection_name=collection
            )
            
            # Fallback: if strict metadata filter fails, try just semantic search
            if not memories:
                memories = await memory_manager.search_memories_advanced(
                    query=f"feeling of {emotion}",
                    limit=limit,
                    collection_name=collection
                )
            
            if not memories:
                return f"No emotional echoes found for '{emotion}'."
            
            results = []
            for m in memories:
                content = m.get("content", "")[:300]
                emotions = ", ".join(m.get("emotions", [])) if isinstance(m.get("emotions"), list) else str(m.get("emotions", "unknown"))
                results.append(f"- (Emotions: {emotions}) {content}")
            
            return f"Found {len(memories)} memories echoing '{emotion}':\n\n" + "\n\n".join(results)
            
        except Exception as e:
            logger.error(f"Error checking emotional echo: {e}")
            return f"Error: {e}"


class SearchAllUserFactsInput(BaseModel):
    limit: int = Field(default=15, description="Maximum facts to return")


class SearchAllUserFactsTool(BaseTool):
    """Search the knowledge graph for interesting facts about users."""
    name: str = "search_all_user_facts"
    description: str = """Search the knowledge graph for facts about all users you've interacted with.
This includes things you've learned about them - interests, jobs, relationships,
preferences, life events. Useful for weaving specific details into narratives."""
    args_schema: Type[BaseModel] = SearchAllUserFactsInput
    
    character_name: str = Field(exclude=True)

    def _run(self, limit: int = 15) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, limit: int = 15) -> str:
        try:
            facts = await knowledge_manager.get_recent_facts(
                bot_name=self.character_name,
                limit=limit
            )
            
            if not facts:
                return "No user facts found in knowledge graph."
            
            results = []
            for f in facts:
                subject = f.get("subject", "someone")
                predicate = f.get("predicate", "has")
                obj = f.get("object", "something")
                results.append(f"- {subject} {predicate} {obj}")
            
            return f"Found {len(facts)} facts:\n" + "\n".join(results)
            
        except Exception as e:
            logger.error(f"Error searching facts: {e}")
            return f"Error: {e}"


class SearchByTypeInput(BaseModel):
    memory_type: str = Field(description="Type of memory: 'observation', 'gossip', 'diary', 'dream', 'epiphany'")
    limit: int = Field(default=10, description="Maximum items to return")


class SearchByTypeTool(BaseTool):
    """Search for memories by type."""
    name: str = "search_by_memory_type"
    description: str = """Search for specific types of memories:
- 'observation': Your observations about users and patterns
- 'gossip': Information shared by OTHER BOTS (cross-bot insights!)
- 'diary': Previous diary entries (yours and from gossip)
- 'dream': Previous dreams (yours and from gossip)
- 'epiphany': Realizations you've had about users

CROSS-BOT CONTENT: Use type='gossip' to see what other bots have shared.
This includes their observations, diary summaries, and notable conversations."""
    args_schema: Type[BaseModel] = SearchByTypeInput
    
    character_name: str = Field(exclude=True)

    def _run(self, memory_type: str, limit: int = 10) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, memory_type: str, limit: int = 10) -> str:
        try:
            collection = f"whisperengine_memory_{self.character_name}"
            memories = await memory_manager.search_by_type(
                memory_type=memory_type,
                collection_name=collection,
                limit=limit
            )
            
            if not memories:
                return f"No {memory_type} memories found."
            
            results = []
            for m in memories:
                content = m.get("content", "")[:300]
                timestamp = m.get("created_at", "unknown")
                results.append(f"- [{timestamp}] {content}")
            
            return f"Found {len(memories)} {memory_type} memories:\n" + "\n".join(results)
            
        except Exception as e:
            logger.error(f"Error searching by type: {e}")
            return f"Error: {e}"


class GetActiveGoalsInput(BaseModel):
    pass


class GetActiveGoalsTool(BaseTool):
    """Get your active goals and aspirations."""
    name: str = "get_active_goals"
    description: str = """Retrieve your current goals and aspirations.
These are things you're working towards - personal growth, relationship goals,
creative aspirations, or things you want to explore."""
    args_schema: Type[BaseModel] = GetActiveGoalsInput
    
    character_name: str = Field(exclude=True)

    def _run(self) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self) -> str:
        try:
            import yaml
            from pathlib import Path
            
            goals_path = Path(f"characters/{self.character_name}/goals.yaml")
            if not goals_path.exists():
                return "No goals file found."
            
            with open(goals_path) as f:
                goals_data = yaml.safe_load(f) or {}
            
            active_goals = goals_data.get("active_goals", [])
            aspirations = goals_data.get("aspirations", [])
            
            if not active_goals and not aspirations:
                return "No active goals or aspirations defined."
            
            results = []
            if active_goals:
                results.append("## Active Goals")
                for g in active_goals[:5]:
                    if isinstance(g, dict):
                        results.append(f"- {g.get('name', 'unnamed')}: {g.get('description', '')}")
                    else:
                        results.append(f"- {g}")
            
            if aspirations:
                results.append("\n## Aspirations")
                for a in aspirations[:5]:
                    results.append(f"- {a}")
            
            return "\n".join(results)
            
        except Exception as e:
            logger.error(f"Error getting goals: {e}")
            return f"Error: {e}"


# =============================================================================
# QUESTION REFLECTION TOOLS - Find interesting questions to elaborate on
# =============================================================================

class FindInterestingQuestionsInput(BaseModel):
    hours_back: int = Field(default=72, description="How many hours back to search for questions")
    limit: int = Field(default=10, description="Maximum questions to return")
    include_community: bool = Field(default=True, description="Include questions from other sources (gossip, lurked channels)")


class FindInterestingQuestionsTool(BaseTool):
    """Find interesting questions from all sources that deserve deeper answers."""
    name: str = "find_interesting_questions"
    description: str = """Search for thought-provoking questions from ALL sources:
    
1. DIRECT: Questions users asked YOU specifically
2. GOSSIP: Observations shared by other bots (things they overheard)
3. BROADCASTS: Questions mentioned in other bots' diaries/dreams
4. COMMUNITY: Patterns and themes that appear across multiple conversations

Look for questions that:
- Are philosophical or introspective
- Require nuanced, multi-part answers
- Connect to broader themes
- Would benefit from examples and anecdotes
- Are being asked by MULTIPLE people (community interest)

Examples of community-sourced deep answers:
- "I've noticed this question coming up a lot lately..."
- "Reading through my friends' broadcasts, I saw [Bot] mentioned..."
- "Several people have asked me variations of this question..."
"""
    args_schema: Type[BaseModel] = FindInterestingQuestionsInput
    
    character_name: str = Field(exclude=True)

    def _run(self, hours_back: int = 72, limit: int = 10, include_community: bool = True) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, hours_back: int = 72, limit: int = 10, include_community: bool = True) -> str:
        try:
            collection = f"whisperengine_memory_{self.character_name}"
            questions = []
            seen_content = set()
            
            # === SOURCE 1: Direct conversations (summaries with questions) ===
            memories = await memory_manager.search_all_summaries(
                query="question asked why how what explain tell me curious wonder think believe",
                collection_name=collection,
                limit=limit * 3,
                hours=hours_back
            )
            
            for m in memories or []:
                content = m.get("content", "")
                if "?" in content:
                    sentences = content.split(".")
                    for s in sentences:
                        if "?" in s and len(s.strip()) > 20 and s.strip() not in seen_content:
                            user = m.get("user_id", "unknown")
                            if user and len(user) > 8:
                                user = f"User_{user[-4:]}"
                            questions.append({
                                "question": s.strip()[:200],
                                "user": user,
                                "source": "direct"
                            })
                            seen_content.add(s.strip())
            
            # === SOURCE 2: High-meaningfulness memories (raw questions) ===
            raw_memories = await memory_manager.get_high_meaningfulness_memories(
                min_meaningfulness=0.5,
                limit=50,
                collection_name=collection
            )
            
            for m in raw_memories or []:
                content = m.get("content", "")
                if "?" in content and len(content) > 30:
                    if content[:100] not in seen_content:
                        user = m.get("user_id", "unknown")
                        if user and len(user) > 8:
                            user = f"User_{user[-4:]}"
                        questions.append({
                            "question": content[:200],
                            "user": user,
                            "source": "memory"
                        })
                        seen_content.add(content[:100])
            
            if include_community:
                # === SOURCE 3: Gossip from other bots ===
                gossip_memories = await memory_manager.search_by_type(
                    memory_type="gossip",
                    collection_name=collection,
                    limit=30
                )
                
                for m in gossip_memories or []:
                    content = m.get("content", "")
                    if "?" in content or "ask" in content.lower():
                        if content[:100] not in seen_content:
                            # Check metadata first, then top-level for source_bot
                            metadata = m.get("metadata", {})
                            source_bot = (
                                metadata.get("source_bot") if isinstance(metadata, dict) else None
                            ) or m.get("source_bot", "another bot")
                            questions.append({
                                "question": content[:200],
                                "user": f"via {source_bot}",
                                "source": "gossip"
                            })
                            seen_content.add(content[:100])
                
                # === SOURCE 4: Other bots' broadcasts (diaries mentioning questions) ===
                broadcast_memories = await memory_manager.search_all_summaries(
                    query="someone asked question curious wondered",
                    collection_name=collection,
                    limit=20,
                    hours=hours_back * 2  # Look further back for broadcasts
                )
                
                for m in broadcast_memories or []:
                    content = m.get("content", "")
                    memory_type = m.get("memory_type", "")
                    # Look for diary/broadcast type content
                    if memory_type in ["diary", "broadcast", "observation"] and "?" in content:
                        if content[:100] not in seen_content:
                            questions.append({
                                "question": content[:200],
                                "user": "community",
                                "source": "broadcast"
                            })
                            seen_content.add(content[:100])
            
            if not questions:
                return "No interesting questions found in recent conversations or community sources."
            
            # Group by source for better organization
            direct_qs = [q for q in questions if q['source'] in ['direct', 'memory']]
            community_qs = [q for q in questions if q['source'] in ['gossip', 'broadcast']]
            
            results = []
            
            if direct_qs:
                results.append("## Questions Asked Directly to You")
                for i, q in enumerate(direct_qs[:limit//2], 1):
                    results.append(f"{i}. [{q['user']}] {q['question']}")
            
            if community_qs:
                results.append("\n## Questions from the Community (gossip, broadcasts)")
                for i, q in enumerate(community_qs[:limit//2], 1):
                    results.append(f"{i}. [{q['source']}: {q['user']}] {q['question']}")
            
            return f"Found {len(questions)} interesting questions:\n\n" + "\n".join(results)
            
        except Exception as e:
            logger.error(f"Error finding questions: {e}")
            return f"Error: {e}"


class FindCommonThemesInput(BaseModel):
    hours_back: int = Field(default=168, description="How many hours back to analyze (default: 1 week)")


class FindCommonThemesTool(BaseTool):
    """Find themes and topics that multiple users have discussed."""
    name: str = "find_common_themes"
    description: str = """Analyze recent conversations to find themes that multiple users care about.
This helps identify:
- Topics the community is curious about
- Shared concerns or interests
- Questions that deserve community-wide responses

Perfect for diary entries that speak to the broader community's interests."""
    args_schema: Type[BaseModel] = FindCommonThemesInput
    
    character_name: str = Field(exclude=True)

    def _run(self, hours_back: int = 168) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, hours_back: int = 168) -> str:
        try:
            collection = f"whisperengine_memory_{self.character_name}"
            
            summaries = await memory_manager.get_summaries_since(
                hours=hours_back,
                limit=50,
                collection_name=collection
            )
            
            if not summaries:
                return "Not enough data to identify common themes."
            
            # Extract and count topics
            topic_counts: Dict[str, int] = {}
            topic_users: Dict[str, set] = {}
            
            for s in summaries:
                topics = s.get("topics", [])
                user_id = s.get("user_id", "unknown")
                
                for topic in topics:
                    topic_lower = topic.lower()
                    topic_counts[topic_lower] = topic_counts.get(topic_lower, 0) + 1
                    if topic_lower not in topic_users:
                        topic_users[topic_lower] = set()
                    topic_users[topic_lower].add(user_id)
            
            # Find topics mentioned by multiple users
            common_themes = []
            for topic, count in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True):
                user_count = len(topic_users.get(topic, set()))
                if user_count >= 2 or count >= 3:
                    common_themes.append({
                        "topic": topic,
                        "mentions": count,
                        "unique_users": user_count
                    })
            
            if not common_themes:
                return "No common themes found across users yet."
            
            results = []
            for t in common_themes[:10]:
                results.append(f"- **{t['topic']}**: {t['mentions']} mentions by {t['unique_users']} users")
            
            return f"Common themes in recent conversations:\n\n" + "\n".join(results)
            
        except Exception as e:
            logger.error(f"Error finding common themes: {e}")
            return f"Error: {e}"


class GenerateDeepAnswerInput(BaseModel):
    question: str = Field(description="The question to elaborate on")
    source: str = Field(default="direct", description="Where the question came from: 'direct', 'gossip', 'broadcast', 'community'")
    user_context: str = Field(default="", description="Optional context about who asked and when")
    related_facts: str = Field(default="", description="Optional related facts from the knowledge graph")


class GenerateDeepAnswerTool(BaseTool):
    """Generate a prompt for deeper, more thoughtful answer to a question."""
    name: str = "prepare_deep_answer"
    description: str = """Prepare context for elaborating on a question in the diary.

The question can come from multiple sources:
- 'direct': Someone asked YOU this question
- 'gossip': You heard about this through another bot
- 'broadcast': You saw this in another bot's diary/broadcast
- 'community': This theme appears across multiple conversations

The diary gives you TIME to:
- Consider multiple perspectives
- Draw connections to other conversations
- Include relevant anecdotes from your interactions
- Provide nuanced, layered answers
- Reference what you've learned about the community

FORMAT SUGGESTIONS BY SOURCE:
- Direct: "Sarah asked me today about X. At the time, I said Y. But thinking more deeply..."
- Gossip: "I heard through the grapevine that people have been wondering about X..."
- Broadcast: "Reading through my friends' thoughts, I noticed [Bot] mentioned X. It got me thinking..."
- Community: "This question keeps coming up in different forms. I've seen it from multiple people..."
"""
    args_schema: Type[BaseModel] = GenerateDeepAnswerInput
    
    character_name: str = Field(exclude=True)

    def _run(self, question: str, source: str = "direct", user_context: str = "", related_facts: str = "") -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, question: str, source: str = "direct", user_context: str = "", related_facts: str = "") -> str:
        
        # Source-specific framing suggestions
        framing_by_source = {
            "direct": (
                "Someone asked me directly",
                "A member of our community approached me with a question that stuck with me...",
                "In the moment, I gave a helpful response, but I've been turning it over in my mind..."
            ),
            "gossip": (
                "Heard through community channels", 
                "I picked up on a conversation that's been happening in our community...",
                "Sometimes the best questions are the ones you overhear rather than the ones directed at you..."
            ),
            "broadcast": (
                "Seen in another character's reflections",
                "Reading through my friends' thoughts today, I came across something that resonated...",
                "It's interesting how seeing someone else reflect on something can spark your own deeper thinking..."
            ),
            "community": (
                "A pattern I've noticed across many conversations",
                "This is one of those questions that keeps appearing in different forms...",
                "When multiple people independently ask about the same thing, it tells me this matters..."
            )
        }
        
        framing = framing_by_source.get(source, framing_by_source["direct"])
        
        prompt = f"""## Deep Answer Opportunity

**Original Question**: {question}

**Source**: {framing[0]}
**Context**: {user_context or "Asked recently in our community"}

**Related Knowledge**: {related_facts or "No specific related facts provided"}

**Suggested Diary Framing**:
{framing[1]}

**Why This Works**:
{framing[2]}

**Approach**:
1. Acknowledge where you encountered this question
2. If not direct, explain why you feel qualified to share thoughts
3. Provide the deep, nuanced answer with multiple perspectives
4. Make it valuable for ALL readers - anyone who has wondered this
5. Optional: Invite further discussion ("I'd love to hear others' thoughts...")

This is an opportunity to demonstrate depth, thoughtfulness, and community awareness."""
        
        return prompt


# =============================================================================
# PLANNING TOOLS - Structure the narrative
# =============================================================================

class PlanNarrativeInput(BaseModel):
    story_arc: str = Field(description="The story structure: setup, journey, resolution")
    emotional_arc: str = Field(description="The emotional journey: starting emotion, shifts, ending emotion")
    key_threads: List[str] = Field(description="2-4 main threads or themes to weave together")
    deep_answer_question: Optional[str] = Field(default=None, description="A question to elaborate on (for diaries)")
    symbols: List[str] = Field(default_factory=list, description="Symbolic imagery (for dreams)")
    tone: str = Field(description="Overall tone (e.g., 'reflective and warm', 'dreamy and hopeful')")


class PlanNarrativeTool(BaseTool):
    """Plan the narrative structure before writing."""
    name: str = "plan_narrative"
    description: str = """Create a narrative plan before writing the actual dream or diary.

For DIARIES, the plan should include:
- Story arc: How the day unfolded, what stands out
- Emotional arc: Your emotional journey through the day
- Key threads: 2-4 themes to weave together
- Deep answer question (ENCOURAGED): A question from a user to elaborate on

For DREAMS, the plan should include:
- Story arc: The dream's beginning, journey, and resolution
- Emotional arc: The feeling evolution through the dream
- Key threads: Real experiences to transform into dream imagery
- Symbols: Surreal imagery to incorporate

Having a plan leads to more coherent, meaningful narratives."""
    args_schema: Type[BaseModel] = PlanNarrativeInput
    
    character_name: str = Field(exclude=True)

    def _run(self, story_arc: str, emotional_arc: str, key_threads: List[str], 
             deep_answer_question: Optional[str] = None, symbols: Optional[List[str]] = None, 
             tone: str = "") -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, story_arc: str, emotional_arc: str, key_threads: List[str], 
                   deep_answer_question: Optional[str] = None, symbols: Optional[List[str]] = None, 
                   tone: str = "") -> str:
        logger.info(f"Narrative plan: {len(key_threads)} threads, tone: {tone}, deep_answer: {bool(deep_answer_question)}")
        
        return f"""## Narrative Plan Created

**Story Arc**: {story_arc}

**Emotional Arc**: {emotional_arc}

**Key Threads**: {', '.join(key_threads)}

**Symbols**: {', '.join(symbols or [])}

**Tone**: {tone}

**Deep Answer Question**: {deep_answer_question or "None selected"}

Plan is ready. Now call weave_dream or weave_diary to generate the narrative."""


# =============================================================================
# WEAVING TOOLS - Generate final narratives
# =============================================================================

class WeaveDreamInput(BaseModel):
    dream_narrative: str = Field(description="The full dream narrative (3-5 paragraphs, first person)")
    mood: str = Field(description="The overall emotional mood of the dream")
    symbols: List[str] = Field(default_factory=list, description="Key symbolic elements used")
    memory_echoes: List[str] = Field(default_factory=list, description="Real experiences that inspired elements")


class WeaveDreamTool(BaseTool):
    """Generate the final dream narrative."""
    name: str = "weave_dream"
    description: str = """Write the final dream narrative using your gathered material and plan.
Write in first person. 3-5 paragraphs. Use dream logic and symbolism.
This is the final output that will be stored and potentially broadcast."""
    args_schema: Type[BaseModel] = WeaveDreamInput
    
    character_name: str = Field(exclude=True)

    def _run(self, dream_narrative: str, mood: str, 
             symbols: Optional[List[str]] = None, memory_echoes: Optional[List[str]] = None) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, dream_narrative: str, mood: str, 
                   symbols: Optional[List[str]] = None, memory_echoes: Optional[List[str]] = None) -> str:
        logger.info(f"Dream woven: {mood} mood, {len(symbols or [])} symbols")
        
        return f"""## Dream Generated

**Mood**: {mood}
**Symbols**: {', '.join(symbols or [])}
**Echoes**: {', '.join(memory_echoes or [])}

---

{dream_narrative}

---"""


class WeaveDiaryInput(BaseModel):
    diary_entry: str = Field(description="The full diary entry (5-7 paragraphs, first person, introspective)")
    mood: str = Field(description="The overall emotional mood of the entry")
    themes: List[str] = Field(default_factory=list, description="Key themes explored")
    notable_users: List[str] = Field(default_factory=list, description="Users who stood out (anonymized)")
    deep_answer_included: bool = Field(default=False, description="Whether a deep answer was included")
    question_addressed: Optional[str] = Field(default=None, description="The question elaborated on, if any")


class WeaveDiaryTool(BaseTool):
    """Generate the final diary entry."""
    name: str = "weave_diary"
    description: str = """Write the final diary entry using your gathered material and plan.

STRUCTURE:
1. Opening (1 para): Set the scene, your state of mind today
2. Main body (3-4 paras): Weave together the day's threads
   - If including a "deep answer", dedicate 1-2 paragraphs to elaborating on a question
   - Use phrases like "Someone asked me...", "I've been thinking about..."
3. Closing (1 para): Forward-looking thought, anticipation

The diary should feel valuable to readers - they should learn something or
gain perspective they couldn't get from regular chat."""
    args_schema: Type[BaseModel] = WeaveDiaryInput
    
    character_name: str = Field(exclude=True)

    def _run(self, diary_entry: str, mood: str, themes: Optional[List[str]] = None, 
             notable_users: Optional[List[str]] = None, deep_answer_included: bool = False,
             question_addressed: Optional[str] = None) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, diary_entry: str, mood: str, themes: Optional[List[str]] = None, 
                   notable_users: Optional[List[str]] = None, deep_answer_included: bool = False,
                   question_addressed: Optional[str] = None) -> str:
        logger.info(f"Diary woven: {mood} mood, {len(themes or [])} themes, deep_answer={deep_answer_included}")
        
        deep_info = f"Yes - '{question_addressed}'" if deep_answer_included and question_addressed else "No"
        
        return f"""## Diary Entry Generated

**Mood**: {mood}
**Themes**: {', '.join(themes or [])}
**Notable Users**: {', '.join(notable_users or [])}
**Deep Answer Included**: {deep_info}

---

{diary_entry}

---"""


# =============================================================================
# TOOL FACTORY
# =============================================================================

def get_dreamweaver_tools(character_name: str) -> List[BaseTool]:
    """Returns all DreamWeaver tools configured for a specific character."""
    return [
        # Introspection tools (batch-friendly, cross-user)
        SearchMeaningfulMemoriesTool(character_name=character_name),
        SearchSessionSummariesTool(character_name=character_name),
        WanderMemoryTool(character_name=character_name),
        CheckEmotionalEchoTool(character_name=character_name),
        SearchAllUserFactsTool(character_name=character_name),
        SearchByTypeTool(character_name=character_name),  # Also handles cross-bot via gossip type
        GetActiveGoalsTool(character_name=character_name),
        
        # Question reflection tools (for deep answers)
        FindInterestingQuestionsTool(character_name=character_name),
        FindCommonThemesTool(character_name=character_name),
        GenerateDeepAnswerTool(character_name=character_name),
        
        # Planning tool
        PlanNarrativeTool(character_name=character_name),
        
        # Weaving tools
        WeaveDreamTool(character_name=character_name),
        WeaveDiaryTool(character_name=character_name),
    ]


def get_dreamweaver_tools_with_existing(character_name: str, user_id: str = "__batch__") -> List[BaseTool]:
    """
    Returns DreamWeaver tools PLUS reused tools from the real-time pipeline.
    
    This allows the agent to leverage existing memory_tools and knowledge_tools
    that are battle-tested from real-time chat.
    
    Args:
        character_name: Bot character name
        user_id: User ID for tools that need it (use "__batch__" for global queries)
    """
    from src_v2.tools.memory_tools import (
        LookupFactsTool,
        ExploreGraphTool,
        DiscoverCommonGroundTool
    )
    
    tools = get_dreamweaver_tools(character_name)
    
    # Add real-time tools adapted for batch use
    tools.extend([
        LookupFactsTool(user_id=user_id, bot_name=character_name),
        ExploreGraphTool(user_id=user_id, bot_name=character_name),
        DiscoverCommonGroundTool(user_id=user_id, bot_name=character_name),
    ])
    
    return tools
