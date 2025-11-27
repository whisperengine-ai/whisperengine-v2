"""
Insight Tools - Specialized tools for the Insight Agent to analyze conversations.
These tools support introspection, pattern detection, and artifact generation.
"""
from typing import Type, Optional, List, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from loguru import logger
import datetime

from src_v2.memory.manager import memory_manager
from src_v2.knowledge.manager import knowledge_manager
from src_v2.evolution.feedback import feedback_analyzer
from src_v2.config.settings import settings


class AnalyzePatternsInput(BaseModel):
    lookback_hours: int = Field(default=24, description="How many hours of history to analyze.")


class AnalyzePatternsTool(BaseTool):
    """Analyzes conversation patterns for a user over time."""
    name: str = "analyze_conversation_patterns"
    description: str = "Analyzes a user's conversation patterns including topics, emotional trends, and engagement styles over the specified time period."
    args_schema: Type[BaseModel] = AnalyzePatternsInput
    
    user_id: str = Field(exclude=True)
    bot_name: str = Field(default="default", exclude=True)

    def _run(self, lookback_hours: int = 24) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, lookback_hours: int = 24) -> str:
        try:
            # Get recent memories using search (existing method)
            memories = await memory_manager.search_memories(
                "conversation", 
                self.user_id, 
                limit=50,
                collection_name=f"whisperengine_memory_{self.bot_name}"
            )
            
            if not memories:
                return "No recent conversation data found for analysis."
            
            # Get feedback patterns
            feedback_insights = await feedback_analyzer.analyze_user_feedback_patterns(self.user_id)
            
            # Build summary
            question_count = 0
            
            for mem in memories:
                content = mem.get("content", "") or ""
                if "?" in content:
                    question_count += 1
                    
            return f"""Pattern Analysis for User {self.user_id}:
- Messages analyzed: {len(memories)}
- Questions asked: {question_count}
- Feedback insights: {feedback_insights.get('recommendations', [])}
- Average sentiment: {feedback_insights.get('average_score', 'N/A')}
"""
        except Exception as e:
            return f"Error analyzing patterns: {e}"


class DetectThemesInput(BaseModel):
    query: str = Field(default="themes topics interests hobbies", description="What themes to search for.")


class DetectThemesTool(BaseTool):
    """Detects recurring themes in a user's conversations."""
    name: str = "detect_recurring_themes"
    description: str = "Identifies themes that appear repeatedly in a user's conversations, such as hobbies, concerns, or life events they keep mentioning."
    args_schema: Type[BaseModel] = DetectThemesInput
    
    user_id: str = Field(exclude=True)
    bot_name: str = Field(default="default", exclude=True)

    def _run(self, query: str = "themes topics interests hobbies") -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, query: str = "themes topics interests hobbies") -> str:
        try:
            # Query knowledge graph for user facts
            facts_str = await knowledge_manager.query_graph(self.user_id, query, self.bot_name)
            
            # Get summaries for theme context
            summaries = await memory_manager.search_summaries(
                query, 
                self.user_id,
                collection_name=f"whisperengine_memory_{self.bot_name}"
            )
            
            themes = []
            if facts_str and "No relevant" not in facts_str:
                themes.append(f"Facts: {facts_str[:500]}")
                    
            if summaries:
                themes.append(f"\nRecent conversation themes from {len(summaries)} summaries available.")
                for s in summaries[:3]:
                    themes.append(f"- {s.get('content', '')[:100]}...")
                
            if not themes:
                return "No clear themes detected yet. More conversation data needed."
                
            return f"Detected Themes for User {self.user_id}:\n" + "\n".join(themes)
            
        except Exception as e:
            return f"Error detecting themes: {e}"


class GenerateEpiphanyInput(BaseModel):
    observation: str = Field(description="The observation or pattern that led to this realization.")
    epiphany_text: str = Field(description="The actual epiphany/realization to store.")


class GenerateEpiphanyTool(BaseTool):
    """Generates and stores an epiphany about a user."""
    name: str = "generate_epiphany"
    description: str = "Creates a spontaneous realization or insight about the user based on observed patterns. These epiphanies can be referenced in future conversations."
    args_schema: Type[BaseModel] = GenerateEpiphanyInput
    
    user_id: str = Field(exclude=True)
    character_name: str = Field(default="default", exclude=True)

    def _run(self, observation: str, epiphany_text: str) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, observation: str, epiphany_text: str) -> str:
        try:
            # Store epiphany as a vector memory with special type
            await memory_manager._save_vector_memory(
                user_id=self.user_id,
                role="epiphany",
                content=f"[EPIPHANY] Observation: {observation}\nRealization: {epiphany_text}",
                metadata={
                    "type": "epiphany",
                    "character_name": self.character_name,
                    "observation": observation
                },
                collection_name=f"whisperengine_memory_{self.character_name}"
            )
            
            logger.info(f"Generated epiphany for user {self.user_id}: {epiphany_text[:50]}...")
            return f"Epiphany stored successfully: '{epiphany_text}'"
            
        except Exception as e:
            return f"Error storing epiphany: {e}"


class StoreReasoningTraceInput(BaseModel):
    query_pattern: str = Field(description="A summary of the type of query (e.g., 'emotional support request').")
    successful_approach: str = Field(description="The reasoning approach that worked well.")
    tools_used: str = Field(description="Comma-separated list of tools that were effective.")
    complexity: str = Field(default="COMPLEX_MID", description="The complexity level of the query (SIMPLE, COMPLEX_LOW, COMPLEX_MID, COMPLEX_HIGH).")


class StoreReasoningTraceTool(BaseTool):
    """Stores a successful reasoning trace for future reuse."""
    name: str = "store_reasoning_trace"
    description: str = "Saves a successful reasoning pattern that can be reused for similar future queries. Helps the agent learn what approaches work."
    args_schema: Type[BaseModel] = StoreReasoningTraceInput
    
    user_id: str = Field(exclude=True)
    character_name: str = Field(default="default", exclude=True)

    def _run(self, query_pattern: str, successful_approach: str, tools_used: str, complexity: str = "COMPLEX_MID") -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, query_pattern: str, successful_approach: str, tools_used: str, complexity: str = "COMPLEX_MID") -> str:
        try:
            # Store trace as a vector memory
            trace_content = f"[REASONING TRACE] Pattern: {query_pattern}\nApproach: {successful_approach}\nTools: {tools_used}\nComplexity: {complexity}"
            
            await memory_manager._save_vector_memory(
                user_id=self.user_id,
                role="reasoning_trace",
                content=trace_content,
                metadata={
                    "type": "reasoning_trace",
                    "character_name": self.character_name,
                    "query_pattern": query_pattern,
                    "tools_used": tools_used.split(","),
                    "complexity": complexity
                },
                collection_name=f"whisperengine_memory_{self.character_name}"
            )
            
            logger.info(f"Stored reasoning trace for pattern: {query_pattern} ({complexity})")
            return f"Reasoning trace stored for pattern: {query_pattern}"
            
        except Exception as e:
            return f"Error storing reasoning trace: {e}"


class LearnResponsePatternInput(BaseModel):
    query_type: str = Field(description="Category of query (e.g., 'emotional', 'factual', 'creative').")
    response_style: str = Field(description="Description of the response style that worked.")
    example_response: str = Field(description="An example of a successful response.")
    feedback_score: float = Field(description="The feedback score (1-5) this response received.")


class LearnResponsePatternTool(BaseTool):
    """Learns a successful response pattern for future reference."""
    name: str = "learn_response_pattern"
    description: str = "Stores a successful response pattern that resonated with the user. Can be used as few-shot examples for similar future queries."
    args_schema: Type[BaseModel] = LearnResponsePatternInput
    
    user_id: str = Field(exclude=True)
    character_name: str = Field(default="default", exclude=True)

    def _run(self, query_type: str, response_style: str, example_response: str, feedback_score: float) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, query_type: str, response_style: str, example_response: str, feedback_score: float) -> str:
        try:
            # Store pattern as vector memory for later retrieval
            pattern_content = f"[RESPONSE PATTERN] Type: {query_type}\nStyle: {response_style}\nScore: {feedback_score}\nExample: {example_response[:200]}"
            
            await memory_manager._save_vector_memory(
                user_id=self.user_id,
                role="response_pattern",
                content=pattern_content,
                metadata={
                    "type": "response_pattern",
                    "character_name": self.character_name,
                    "query_type": query_type,
                    "response_style": response_style,
                    "feedback_score": feedback_score
                },
                collection_name=f"whisperengine_memory_{self.character_name}"
            )
            
            logger.info(f"Learned response pattern for {query_type} (score: {feedback_score})")
            return f"Response pattern learned for {query_type} queries (score: {feedback_score})"
            
        except Exception as e:
            return f"Error learning response pattern: {e}"


def get_insight_tools(user_id: str, character_name: str) -> List[BaseTool]:
    """Returns all insight tools configured for a specific user and character."""
    return [
        AnalyzePatternsTool(user_id=user_id, bot_name=character_name),
        DetectThemesTool(user_id=user_id, bot_name=character_name),
        GenerateEpiphanyTool(user_id=user_id, character_name=character_name),
        StoreReasoningTraceTool(user_id=user_id, character_name=character_name),
        LearnResponsePatternTool(user_id=user_id, character_name=character_name),
    ]
