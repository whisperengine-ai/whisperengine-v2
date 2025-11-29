import re
from datetime import datetime, timedelta
from typing import Type, List, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from loguru import logger

from src_v2.memory.manager import memory_manager
from src_v2.knowledge.manager import knowledge_manager
from src_v2.evolution.trust import trust_manager
from src_v2.config.settings import settings

class SearchSummariesInput(BaseModel):
    query: str = Field(description="The topic or concept to search for in past conversation summaries.")
    time_range: Optional[str] = Field(description="Optional time range (e.g., 'last week', 'yesterday').", default=None)

class SearchSummariesTool(BaseTool):
    name: str = "search_archived_summaries"
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
    name: str = "search_specific_memories"
    description: str = "Searches for specific details, quotes, or moments in conversation history. Use this for specific questions like 'What was that boat name?'."
    args_schema: Type[BaseModel] = SearchEpisodesInput
    user_id: str = Field(exclude=True)

    def _run(self, query: str) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, query: str) -> str:
        try:
            # Use standard memory search (episodes)
            results = await memory_manager.search_memories(query, self.user_id)
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
                return "No substantive memories found matching your query."
            
            # Limit results for Reflective Mode to reduce token bloat
            limit = settings.REFLECTIVE_MEMORY_RESULT_LIMIT
            filtered_results = filtered_results[:limit]
            
            formatted = "\n".join([f"- {r['content']}" for r in filtered_results])
            return f"Found {len(filtered_results)} Episodes (top matches):\n{formatted}"
        except Exception as e:
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
            # Use the new smart query method
            result = await knowledge_manager.query_graph(self.user_id, query, self.bot_name)
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
    name: str = "update_user_preferences"
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
    name: str = "explore_knowledge_graph"
    description: str = "Explores the knowledge graph to find connections and relationships. Use this when the user asks 'what is connected?', 'who else?', 'what do you know about the network?', or wants to explore relationships beyond specific facts."
    args_schema: Type[BaseModel] = ExploreGraphInput
    user_id: str = Field(exclude=True)
    bot_name: str = Field(default="default", exclude=True)

    def _run(self, start_node: Optional[str] = "user", depth: Optional[int] = 2) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, start_node: Optional[str] = "user", depth: Optional[int] = 2) -> str:
        try:
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
    name: str = "discover_common_ground"
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
    name: str = "get_character_evolution"
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
