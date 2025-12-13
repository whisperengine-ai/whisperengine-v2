import re
from datetime import datetime, timedelta
from typing import Type, List, Optional, Literal
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from loguru import logger

from src_v2.memory.manager import memory_manager
from src_v2.knowledge.manager import knowledge_manager
from src_v2.evolution.trust import trust_manager
from src_v2.config.settings import settings


# =============================================================================
# USER-FACING INTROSPECTION TOOL - Let users ask about bot's internal life
# =============================================================================

class SearchMyThoughtsInput(BaseModel):
    thought_type: Literal["diary", "dream", "gossip", "epiphany", "any"] = Field(
        default="any",
        description="Type of thought to search. IMPORTANT: Use 'any' if the user asks for multiple types (e.g. 'diaries and dreams') or general thoughts."
    )
    query: str = Field(
        default="",
        description="Optional keyword to search for (e.g., 'loneliness', 'creativity', a person's name)"
    )
    limit: int = Field(default=3, description="Maximum results to return (1-5)")


class SearchMyThoughtsTool(BaseTool):
    """Let users explore the bot's internal experiences - diaries, dreams, observations."""
    name: str = "search_my_thoughts"
    description: str = """Search through my personal experiences and reflections.

USE THIS WHEN the user asks about:
- "What have you been dreaming about?"
- "Tell me about your diary"
- "What have you observed lately?"
- "Have you heard any gossip?"
- "What's on your mind?"
- "What did you write in your journal?"
- "What have you realized about me?"
- "Tell me about your diaries and dreams" (use thought_type='any')

Types available:
- 'diary': My personal journal entries (daily reflections)
- 'dream': Dreams I've had (surreal, symbolic experiences)
- 'observation': Things I've noticed about people and patterns
- 'gossip': Interesting things I've heard from my bot friends
- 'epiphany': Realizations and insights I've had about people
- 'any': Search across all types (use this for "diaries and dreams")

This gives users a "peek behind the curtain" into my inner life."""
    args_schema: Type[BaseModel] = SearchMyThoughtsInput
    
    character_name: str = Field(exclude=True)

    def _run(self, thought_type: str = "any", query: str = "", limit: int = 3) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, thought_type: str = "any", query: str = "", limit: int = 3) -> str:
        try:
            collection = f"whisperengine_memory_{self.character_name}"
            limit = min(max(limit, 1), 5)  # Clamp to 1-5
            
            all_results = []
            
            # Determine which types to search
            if thought_type == "any":
                types_to_search = ["diary", "dream", "gossip", "epiphany"]
            else:
                types_to_search = [thought_type]
            
            # Use semantic search for diary if query provided
            if thought_type == "diary" and query:
                from src_v2.memory.diary import get_diary_manager
                diary_manager = get_diary_manager(self.character_name)
                diary_entries = await diary_manager.search_diaries(query, limit=limit)
                
                for entry in diary_entries:
                    all_results.append({
                        "type": "diary",
                        "content": entry.get("content", "")[:400],
                        "timestamp": entry.get("date", entry.get("timestamp", "recently")),
                        "mood": entry.get("mood", ""),
                        "themes": entry.get("themes", [])
                    })
            else:
                # Fall back to type-based search
                for mem_type in types_to_search:
                    if query:
                        # Use semantic search if query provided
                        memories = await memory_manager.search_by_type_semantic(
                            memory_type=mem_type,
                            query=query,
                            collection_name=collection,
                            limit=limit if thought_type != "any" else 2
                        )
                    else:
                        # Use scroll if no query (get most recent)
                        memories = await memory_manager.search_by_type(
                            memory_type=mem_type,
                            collection_name=collection,
                            limit=limit if thought_type != "any" else 2
                        )
                    
                    for m in memories or []:
                        content = m.get("content", "")
                        
                        all_results.append({
                            "type": mem_type,
                            "content": content[:400],
                            "timestamp": m.get("created_at", m.get("timestamp", "recently"))
                        })
            
            if not all_results:
                if thought_type == "any":
                    return "I don't have any recorded thoughts yet. As I experience more, I'll have diaries, dreams, and observations to share!"
                else:
                    return f"I don't have any {thought_type} entries yet. Check back later!"
            
            results = []
            for r in all_results[:limit]:
                # Add mood/themes for diary entries if available
                extra = ""
                if r.get("mood"):
                    extra = f" (mood: {r['mood']})"
                if r.get("themes"):
                    extra += f" themes: {', '.join(r['themes'][:3])}"
                
                # Format as a recalled memory rather than a database record
                # This helps the bot feel like it's remembering, not reading
                results.append(f"[Internal Memory - {r['type'].title()}]\n{r['content']}\n(Context: {extra})")
            
            intro = f"Recalling my internal {thought_type if thought_type != 'any' else 'thoughts'}...\n\n"
            return intro + "\n\n---\n\n".join(results)
            
        except Exception as e:
            logger.error(f"Error searching my thoughts: {e}")
            return f"I had trouble accessing my thoughts: {e}"


# =============================================================================
# USER-REQUESTED GOALS - Let users ask the bot to work on something
# =============================================================================

class CreateUserGoalInput(BaseModel):
    description: str = Field(
        description="What the user wants the bot to help with or remember to do (e.g., 'help me practice Spanish', 'remind me to exercise')"
    )
    duration_days: int = Field(
        default=7,
        description="How many days this goal should be active (1-30, default 7)"
    )


class CreateUserGoalTool(BaseTool):
    """Create a goal based on user's explicit request."""
    name: str = "create_user_goal"
    description: str = """Create a personal goal when the user explicitly asks you to:
- "Help me with X"
- "I want you to remind me about Y"
- "Can you work on Z with me?"
- "Let's practice A together"
- "Keep me accountable for B"

This creates a goal that you'll actively work towards in future conversations.
Goals expire after the specified duration (default 7 days).

DO NOT use this for:
- Simple one-time requests
- Questions or information lookup
- Things that can be done immediately"""
    args_schema: Type[BaseModel] = CreateUserGoalInput
    
    user_id: str = Field(exclude=True)
    character_name: str = Field(exclude=True)

    def _run(self, description: str, duration_days: int = 7) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, description: str, duration_days: int = 7) -> str:
        from src_v2.core.database import db_manager
        from datetime import datetime, timedelta
        import re
        
        try:
            # Validate duration
            duration_days = max(1, min(30, duration_days))
            
            # Generate a slug from description
            slug = re.sub(r'[^a-z0-9]+', '_', description.lower())[:50]
            slug = f"user_{slug}_{datetime.now().strftime('%m%d')}"
            
            # Calculate expiry
            expires_at = datetime.now() + timedelta(days=duration_days)
            
            if not db_manager.postgres_pool:
                return "I couldn't save this goal right now. Please try again later."
            
            async with db_manager.postgres_pool.acquire() as conn:
                # Check if similar goal already exists
                existing = await conn.fetchval("""
                    SELECT id FROM v2_goals 
                    WHERE character_name = $1 
                    AND target_user_id = $2
                    AND description ILIKE $3
                    AND (expires_at IS NULL OR expires_at > NOW())
                """, self.character_name, self.user_id, f"%{description[:30]}%")
                
                if existing:
                    return f"I'm already working on something similar with you! I'll keep focusing on that."
                
                # Insert the goal
                await conn.execute("""
                    INSERT INTO v2_goals (
                        character_name, slug, description, success_criteria, 
                        priority, source, category, target_user_id, expires_at
                    )
                    VALUES ($1, $2, $3, $4, $5, 'user', 'user_requested', $6, $7)
                """, 
                    self.character_name,
                    slug,
                    description,
                    f"User expresses satisfaction or goal is achieved",
                    8,  # User goals are high priority
                    self.user_id,
                    expires_at
                )
                
                logger.info(f"Created user goal '{slug}' for {self.user_id} (expires: {expires_at})")
                return f"Got it! I've made a note to help you with: **{description}**. I'll keep this in mind for the next {duration_days} days."
                
        except Exception as e:
            logger.error(f"Error creating user goal: {e}")
            return f"I had trouble saving that goal, but I'll try to remember!"


# =============================================================================
# STANDARD MEMORY TOOLS
# =============================================================================

class SearchSummariesInput(BaseModel):
    query: str = Field(description="The topic or concept to search for in past conversation summaries.")
    time_range: Optional[str] = Field(description="Optional time range (e.g., 'last week', 'yesterday').", default=None)

class SearchSummariesTool(BaseTool):
    name: str = "old_summaries"
    description: str = "Searches high-level summaries of past conversations. Use this to recall topics, events, or emotional context from days or weeks ago."
    args_schema: Type[BaseModel] = SearchSummariesInput
    user_id: str = Field(exclude=True) # Exclude from LLM schema

    def _run(self, query: str, time_range: Optional[str] = None) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, query: str, time_range: Optional[str] = None) -> str:
        try:
            start_ts = self._parse_time_range(time_range) if time_range else None
            
            results = await memory_manager.search_summaries(query, self.user_id, start_timestamp=start_ts)
            if not results:
                return "No relevant summaries found."
            
            # Limit results for Reflective Mode to reduce token bloat
            limit = settings.REFLECTIVE_MEMORY_RESULT_LIMIT
            results = results[:limit]
            
            formatted = "\n".join([
                f"- [Score: {r['meaningfulness']}/5] {r['content']} ({r['timestamp'][:10]})" 
                for r in results
            ])
            return f"Found {len(results)} Summaries (top matches):\n{formatted}"
        except Exception as e:
            return f"Error searching summaries: {e}"

    def _parse_time_range(self, time_range: str) -> Optional[float]:
        """
        Parses natural language time range into a start timestamp.
        Supports: 'last X days', 'last X weeks', 'yesterday', 'last month'.
        """
        if not time_range:
            return None
            
        now = datetime.now()
        text = time_range.lower().strip()
        
        try:
            if "yesterday" in text:
                return (now - timedelta(days=1)).timestamp()
            
            if "last month" in text:
                return (now - timedelta(days=30)).timestamp()
                
            if "last year" in text:
                return (now - timedelta(days=365)).timestamp()

            # Regex for "last X days/weeks"
            match = re.search(r"last\s+(\d+)\s+(day|week|month)s?", text)
            if match:
                amount = int(match.group(1))
                unit = match.group(2)
                
                if unit == "day":
                    return (now - timedelta(days=amount)).timestamp()
                elif unit == "week":
                    return (now - timedelta(weeks=amount)).timestamp()
                elif unit == "month":
                    return (now - timedelta(days=amount * 30)).timestamp()
                    
            # Fallback for "last week" (singular)
            if "last week" in text:
                return (now - timedelta(weeks=1)).timestamp()

        except Exception:
            pass
            
        return None

class SearchEpisodesInput(BaseModel):
    query: str = Field(description="The specific detail or quote to search for.")

class SearchEpisodesTool(BaseTool):
    name: str = "mem_search"
    description: str = """Search YOUR semantic memory for past conversations with this user - including DMs, channels, and all contexts.

USE THIS WHEN:
- User references something you discussed before ("remember when...", "you said earlier...", "our conversation about...")
- User mentions feedback, suggestions, or ideas they shared with you
- Looking for specific details, quotes, or moments from ANY past conversation
- User asks "do you remember X?" about something they told you

This searches your actual memories, not just the current channel. If user mentioned something in DMs and now asks about it in a channel, you'll find it here."""
    args_schema: Type[BaseModel] = SearchEpisodesInput
    user_id: str = Field(exclude=True)
    character_name: str = Field(default="default", exclude=True)

    def _run(self, query: str) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, query: str) -> str:
        try:
            logger.info(f"[SearchEpisodesTool] Query: '{query}' for user {self.user_id}")
            
            # Use standard memory search (episodes) with correct collection
            collection_name = f"whisperengine_memory_{self.character_name}"
            results = await memory_manager.search_memories(query, self.user_id, collection_name=collection_name)
            
            # Log raw results for debugging
            if results:
                logger.debug(f"[SearchEpisodesTool] Raw results: {len(results)} memories found")
                for i, r in enumerate(results[:3]):  # Log top 3
                    score = r.get('score', 'N/A')
                    channel = r.get('channel_id', 'N/A')
                    content_preview = (r.get('content', '') or '')[:80]
                    logger.debug(f"[SearchEpisodesTool] Result {i+1}: score={score}, channel={channel}, content='{content_preview}...'")
            else:
                logger.info(f"[SearchEpisodesTool] No results for query: '{query}'")
            
            if not results:
                return "No specific memories found."
            
            # Filter out low-value results:
            # - Meta-questions about memory/channel (these are queries, not content)
            # - Very short messages
            meta_patterns = [
                "what did i say", "what have we talked", "what is in my memory",
                "what are the recent messages", "what has been discussed",
                "do you remember", "what do you know about me"
            ]
            
            filtered_results = []
            for r in results:
                content = r.get('content', '') or ''
                content_lower = content.lower()
                
                # Skip meta-questions and very short content
                is_meta_question = any(pattern in content_lower for pattern in meta_patterns)
                is_too_short = len(content.strip()) < 10
                
                if not is_meta_question and not is_too_short:
                    filtered_results.append(r)
            
            if not filtered_results:
                logger.info(f"[SearchEpisodesTool] All {len(results)} results filtered out (meta-questions or too short)")
                return "No substantive memories found matching your query."
            
            # Limit results for Reflective Mode to reduce token bloat
            limit = settings.REFLECTIVE_MEMORY_RESULT_LIMIT
            filtered_results = filtered_results[:limit]
            
            logger.info(f"[SearchEpisodesTool] Returning {len(filtered_results)} memories (limit={limit})")
            
            # Phase 2.5.1: Fetch Unified Memory Neighborhood for these results
            # This ensures the reflective agent sees the "Enriched Graph" connections
            neighborhood_text = ""
            try:
                memory_ids = [r.get("id") for r in filtered_results if r.get("id")]
                if memory_ids:
                    neighborhood = await knowledge_manager.get_memory_neighborhood(memory_ids)
                    if neighborhood:
                        seen_assoc = set()
                        lines = []
                        for item in neighborhood:
                            # Format: Entity (Predicate) or Memory: Content (Link Type)
                            if "entity" in item and "predicate" in item:
                                assoc = f"{item['entity']} ({item['predicate']})"
                                if assoc not in seen_assoc:
                                    lines.append(f"- {assoc}")
                                    seen_assoc.add(assoc)
                        
                        if lines:
                            neighborhood_text = "\n\n[Graph Connections]\n" + "\n".join(lines)
            except Exception as e:
                logger.warning(f"Failed to fetch neighborhood in tool: {e}")

            # Include relative time to help identify recent vs old memories
            formatted_lines = []
            for r in filtered_results:
                relative_time = r.get('relative_time', 'unknown time')
                content = r.get('content', '')
                
                # Add fragment indicator
                if r.get('is_chunk'):
                    idx = r.get('chunk_index', 0) + 1
                    total = r.get('chunk_total', '?')
                    content = f"[Fragment {idx}/{total}] {content}"
                    
                    # Add hint about reading full content
                    msg_id = r.get('parent_message_id') or r.get('message_id')
                    if msg_id:
                        content += f" (ID: {msg_id})"
                
                formatted_lines.append(f"- ({relative_time}) {content}")
            
            formatted = "\n".join(formatted_lines)
            return f"Found {len(filtered_results)} memories:\n{formatted}{neighborhood_text}"
        except Exception as e:
            logger.error(f"[SearchEpisodesTool] Error: {e}")
            return f"Error searching episodes: {e}"

class LookupFactsInput(BaseModel):
    query: str = Field(description="The natural language query for user facts (e.g. 'What is my dog's name?').")

class LookupFactsTool(BaseTool):
    name: str = "lookup_user_facts"
    description: str = "Retrieves structured facts about the user OR the AI character from the Knowledge Graph. Use this for verifying names, relationships, preferences, biographical info, or finding common ground."
    args_schema: Type[BaseModel] = LookupFactsInput
    user_id: str = Field(exclude=True)
    bot_name: str = Field(default="default", exclude=True)

    def _run(self, query: str) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, query: str) -> str:
        try:
            # Clean up Discord mentions in the query
            # <@123456789> -> "user with id 123456789"
            cleaned_query = re.sub(r'<@!?(\d+)>', r'user with id \1', query)
            
            # Use the smart query method first
            result = await knowledge_manager.query_graph(self.user_id, cleaned_query, self.bot_name)
            
            # If the LLM-generated query found nothing, fall back to default fact retrieval
            # This handles cases where the query was too vague or LLM generated poor Cypher
            if "No relevant information found" in result or not result.strip():
                default_facts = await knowledge_manager.get_user_knowledge(self.user_id, query=None, limit=10)
                if default_facts:
                    return f"Graph Query Result: {default_facts}"
                return "Graph Query Result: No facts stored for this user yet."
            
            return f"Graph Query Result: {result}"
        except Exception as e:
            return f"Error looking up facts: {e}"

class UpdateFactsInput(BaseModel):
    correction: str = Field(description="The user's correction or update (e.g., 'I moved to Seattle', 'I don't like pizza anymore').")

class UpdateFactsTool(BaseTool):
    name: str = "update_user_facts"
    description: str = "Updates or deletes facts in the Knowledge Graph based on user correction. Use this when the user explicitly says something has changed or was wrong."
    args_schema: Type[BaseModel] = UpdateFactsInput
    user_id: str = Field(exclude=True)

    def _run(self, correction: str) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, correction: str) -> str:
        try:
            result = await knowledge_manager.delete_fact(self.user_id, correction)
            return f"Fact Update Result: {result}"
        except Exception as e:
            return f"Error updating facts: {e}"

class UpdatePreferencesInput(BaseModel):
    action: str = Field(description="The action to perform: 'update' or 'delete'.")
    key: str = Field(description="The preference key (e.g., 'verbosity', 'nickname').")
    value: Optional[str] = Field(description="The new value (only for 'update' action).", default=None)

class UpdatePreferencesTool(BaseTool):
    name: str = "save_prefs"
    description: str = "Updates or deletes user preferences (configuration). Use this when the user explicitly changes a setting like 'stop calling me Captain' or 'change verbosity to short'."
    args_schema: Type[BaseModel] = UpdatePreferencesInput
    user_id: str = Field(exclude=True)
    character_name: str = Field(exclude=True)

    def _run(self, action: str, key: str, value: Optional[str] = None) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, action: str, key: str, value: Optional[str] = None) -> str:
        try:
            if action == "delete":
                await trust_manager.delete_preference(self.user_id, self.character_name, key)
                return f"Deleted preference: {key}"
            elif action == "update":
                await trust_manager.update_preference(self.user_id, self.character_name, key, value)
                return f"Updated preference: {key} = {value}"
            else:
                return "Invalid action. Use 'update' or 'delete'."
        except Exception as e:
            return f"Error updating preferences: {e}"

class ExploreGraphInput(BaseModel):
    start_node: Optional[str] = Field(
        description="The starting point for exploration. Use 'user' for the current user's connections, 'character' for the AI character's connections, or a specific entity name. Defaults to 'user'.",
        default="user"
    )
    depth: Optional[int] = Field(
        description="How many hops out to explore (1-3). 1 = direct connections, 2 = friends of friends, 3 = extended network. Default is 2.",
        default=2
    )

class ExploreGraphTool(BaseTool):
    name: str = "graph_walk"
    description: str = "Explores the knowledge graph to find hidden connections, thematic clusters, and relationships. Use this when the user asks 'what is connected?', 'explore the graph', 'find connections', or wants to discover relationships beyond specific facts."
    args_schema: Type[BaseModel] = ExploreGraphInput
    user_id: str = Field(exclude=True)
    bot_name: str = Field(default="default", exclude=True)

    def _run(self, start_node: Optional[str] = "user", depth: Optional[int] = 2) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, start_node: Optional[str] = "user", depth: Optional[int] = 2) -> str:
        try:
            # Use GraphWalker if enabled (Phase E19)
            if settings.ENABLE_GRAPH_WALKER:
                try:
                    from src_v2.knowledge.walker import GraphWalkerAgent
                    walker_agent = GraphWalkerAgent(character_name=self.bot_name)
                    
                    # Determine seed IDs based on start_node
                    seed_ids = []
                    if start_node == "user":
                        seed_ids.append(self.user_id)
                    elif start_node == "character":
                        seed_ids.append(self.bot_name)
                    elif start_node:
                        seed_ids.append(start_node)
                    
                    # Use explore_for_context which is optimized for query context
                    result = await walker_agent.explore_for_context(
                        user_id=self.user_id,
                        query_themes=seed_ids
                    )
                    
                    # Format result
                    lines = ["Graph Exploration Result (via GraphWalker):"]
                    if result.nodes:
                        lines.append(f"Found {len(result.nodes)} nodes and {len(result.clusters)} clusters.")
                        
                        lines.append("\nTop Nodes:")
                        for node in result.nodes[:10]:
                            lines.append(f"- {node.name} ({node.label}) [score: {node.score:.2f}]")
                            
                        if result.clusters:
                            lines.append("\nThematic Clusters:")
                            for cluster in result.clusters[:3]:
                                members = ", ".join(n.name for n in cluster.nodes[:3])
                                lines.append(f"- {cluster.theme}: {members}")
                    else:
                        lines.append("No significant connections found.")
                        
                    return "\n".join(lines)
                    
                except Exception as e:
                    # Fallback to legacy method if walker fails
                    pass

            result = await knowledge_manager.explore_graph(
                user_id=self.user_id, 
                bot_name=self.bot_name,
                start_node=start_node or "user",
                depth=min(depth or 2, 3)  # Cap at 3 for performance
            )
            return f"Graph Exploration Result:\n{result}"
        except Exception as e:
            return f"Error exploring graph: {e}"


class DiscoverCommonGroundInput(BaseModel):
    target: str = Field(description="The target to find common ground with. Defaults to 'user'.", default="user")

class DiscoverCommonGroundTool(BaseTool):
    name: str = "common_ground"
    description: str = "Discovers what you and the user have in common - shared interests, places, experiences, or values. Use this when you want to find connection points, when asked 'what do we have in common?', or to personalize the conversation with shared interests."
    args_schema: Type[BaseModel] = DiscoverCommonGroundInput
    user_id: str = Field(exclude=True)
    bot_name: str = Field(default="default", exclude=True)

    def _run(self, target: str = "user") -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, target: str = "user") -> str:
        try:
            common_ground = await knowledge_manager.find_common_ground(self.user_id, self.bot_name)
            if common_ground:
                return f"🔗 Common Ground Discovered:\n{common_ground}\n\nYou can naturally reference these shared interests to build rapport!"
            else:
                return "No common ground found yet. As you learn more about the user, shared interests may emerge."
        except Exception as e:
            return f"Error discovering common ground: {e}"


class GetEvolutionStateInput(BaseModel):
    target: str = Field(description="The target to check evolution state for. Defaults to 'user'.", default="user")

class CharacterEvolutionTool(BaseTool):
    name: str = "char_evolve"
    description: str = "Retrieves the current relationship level, trust score, and unlocked personality traits between you and the user. Use this to understand how your personality should adapt to this specific relationship."
    args_schema: Type[BaseModel] = GetEvolutionStateInput
    user_id: str = Field(exclude=True)
    character_name: str = Field(exclude=True)

    def _run(self, target: str = "user") -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, target: str = "user") -> str:
        try:
            relationship = await trust_manager.get_relationship_level(self.user_id, self.character_name)
            
            level_label = relationship.get('level_label', 'Stranger')
            output = f"""Current Relationship State:
- Trust Score: {relationship['trust_score']}/150
- Relationship Level: {level_label}
- Unlocked Traits: {', '.join(relationship['unlocked_traits']) if relationship['unlocked_traits'] else 'None yet'}

This means you should behave as a {level_label.lower()} with this user."""
            
            return output
        except Exception as e:
            return f"Error retrieving evolution state: {e}"


# =============================================================================
# CROSS-BOT MEMORY RECALL - Let bot recall conversations with other bots
# =============================================================================

class RecallBotConversationInput(BaseModel):
    bot_name: str = Field(
        description="The name of the other bot to recall conversations with (e.g., 'aetheris', 'gabriel', 'elena')"
    )
    topic: str = Field(
        default="",
        description="Optional topic to focus on (e.g., 'consciousness', 'dreams', 'philosophy')"
    )
    limit: int = Field(
        default=5,
        description="Maximum number of memories to retrieve (1-10)"
    )


class RecallBotConversationTool(BaseTool):
    """Recall past conversations with another bot character."""
    name: str = "bot_recall"
    description: str = """Recall memories of conversations you've had with another bot.

USE THIS WHEN the user asks:
- "What did you talk about with Aetheris?"
- "Do you remember your conversation with Gabriel?"
- "What does Elena think about X?" (recall what Elena said)
- "Have you discussed consciousness with any bots?"
- "Tell me about your chats with other bots"

This searches your memories of past bot-to-bot conversations, stored when you 
interacted with other AI characters in Discord channels.

IMPORTANT: Only use this for recalling conversations with OTHER BOTS, not humans.
For human conversations, use the regular memory search tools."""
    args_schema: Type[BaseModel] = RecallBotConversationInput
    
    character_name: str = Field(exclude=True)

    def _run(self, bot_name: str, topic: str = "", limit: int = 5) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, bot_name: str, topic: str = "", limit: int = 5) -> str:
        try:
            from src_v2.universe.registry import bot_registry
            
            # Get known bots
            known_bots = await bot_registry.get_known_bots()
            
            if not known_bots:
                return "I don't have access to other bot information right now. They might not be online."
            
            # Normalize bot name for lookup
            bot_name_lower = bot_name.lower().strip()
            
            # Find the bot ID
            bot_id = None
            matched_name = None
            for name, info in known_bots.items():
                if name.lower() == bot_name_lower or bot_name_lower in name.lower():
                    bot_id = info.discord_id
                    matched_name = name
                    break
            
            if not bot_id:
                available = ", ".join(known_bots.keys())
                return f"I don't know a bot named '{bot_name}'. Bots I know: {available}"
            
            # Search memories under that bot's ID
            # Cross-bot conversations are stored with user_id = other_bot's discord_id
            query = topic if topic else f"conversation with {matched_name}"
            limit = min(max(limit, 1), 10)
            
            # Use correct collection for this character
            collection_name = f"whisperengine_memory_{self.character_name}"
            memories = await memory_manager.search_memories(
                query=query,
                user_id=str(bot_id),
                limit=limit,
                collection_name=collection_name
            )
            
            if not memories:
                if topic:
                    return f"I don't recall discussing '{topic}' with {matched_name.title()}. We may not have talked about that, or it was too long ago."
                else:
                    return f"I don't have memories of conversations with {matched_name.title()} yet. We may not have interacted, or I haven't stored those conversations."
            
            # Format the memories
            results = []
            for mem in memories:
                content = mem.get("content", "")[:400]
                rel_time = mem.get("relative_time", "some time ago")
                role = mem.get("role", "unknown")
                
                # Format based on role
                if role == "human":
                    # This was the other bot speaking
                    results.append(f"**{matched_name.title()} said** ({rel_time}):\n\"{content}\"")
                else:
                    # This was our response
                    results.append(f"**I replied** ({rel_time}):\n\"{content}\"")
            
            intro = f"Recalling my conversations with {matched_name.title()}"
            if topic:
                intro += f" about '{topic}'"
            intro += "...\n\n"
            
            return intro + "\n\n".join(results)
            
        except ImportError:
            return "Cross-bot memory system is not available."
        except (ValueError, KeyError, ConnectionError, TimeoutError) as e:
            logger.error(f"Error recalling bot conversation: {e}")
            return f"I had trouble recalling those conversations: {e}"


class ReadFullMemoryInput(BaseModel):
    message_id: str = Field(description="The Discord message ID of the memory to read in full.")

class ReadFullMemoryTool(BaseTool):
    name: str = "full_memory"
    description: str = """Fetches the COMPLETE, untruncated content of a memory fragment.

USE THIS WHEN:
- Search results show [Fragment X/Y] and the user asks for "full text", "exact words", "complete message", or "all the details"
- A memory fragment appears cut off mid-sentence or mid-thought
- The user explicitly asks you to "read the full memory" or "get the rest"

Pass the message ID shown in the search result (e.g., "1234567890")."""
    args_schema: Type[BaseModel] = ReadFullMemoryInput
    
    def _run(self, message_id: str) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, message_id: str) -> str:
        try:
            content = await memory_manager.get_full_message_by_discord_id(message_id)
            if content:
                return f"Full content for message {message_id}:\n\n{content}"
            else:
                return f"Could not find full content for message {message_id}."
        except Exception as e:
            return f"Error reading memory: {e}"
