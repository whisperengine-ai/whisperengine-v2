from typing import Type, Optional, List
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
import asyncio

from src_v2.tools.memory_tools import SearchSummariesTool, SearchEpisodesTool, LookupFactsTool

class AnalyzeTopicInput(BaseModel):
    topic: str = Field(description="The topic, concept, or person to analyze deeply.")

class AnalyzeTopicTool(BaseTool):
    name: str = "analyze_topic"
    description: str = "Comprehensive research tool. Searches summaries, episodes, and facts simultaneously for a given topic. Use this for broad questions to get a complete picture."
    args_schema: Type[BaseModel] = AnalyzeTopicInput
    
    user_id: str = Field(exclude=True)
    bot_name: str = Field(exclude=True)

    def _run(self, topic: str) -> str:
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, topic: str) -> str:
        # Instantiate sub-tools
        summaries_tool = SearchSummariesTool(user_id=self.user_id)
        episodes_tool = SearchEpisodesTool(user_id=self.user_id)
        facts_tool = LookupFactsTool(user_id=self.user_id, bot_name=self.bot_name)
        
        # Run in parallel
        results = await asyncio.gather(
            summaries_tool.ainvoke({"query": topic}),
            episodes_tool.ainvoke({"query": topic}),
            facts_tool.ainvoke({"query": topic})
        )
        
        summaries, episodes, facts = results
        
        return f"""
[ANALYSIS FOR: {topic}]

--- SUMMARIES ---
{summaries}

--- EPISODES ---
{episodes}

--- FACTS ---
{facts}
"""
