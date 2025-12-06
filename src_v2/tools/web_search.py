from typing import List, Dict, Any, Optional, Type
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from ddgs import DDGS
from loguru import logger
import asyncio


class WebSearchInput(BaseModel):
    """Input schema for web search tool."""
    query: str = Field(description="The search query to look up on the web")
    max_results: int = Field(default=5, description="Maximum number of results to return (1-10)")


class WebSearchTool(BaseTool):
    name: str = "web_search"
    description: str = """Search the web for current events, news, facts, or general knowledge.

USE THIS WHEN:
- User asks about recent news or current events
- User asks about something that requires up-to-date information
- User asks about a topic you don't have knowledge of
- User explicitly asks to "search" or "look up" something

DO NOT USE FOR:
- Questions about the user themselves (use memory tools instead)
- Questions about your relationship or past conversations
- Simple greetings or casual chat"""
    args_schema: Type[BaseModel] = WebSearchInput
    
    def _run(self, query: str, max_results: int = 5) -> str:
        """
        Synchronous run method (required by BaseTool, but we prefer async).
        """
        # We can't easily run async code here without an event loop, 
        # so we'll use the synchronous DDGS if available or a wrapper.
        # DDGS is synchronous by default in the library.
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
                return self._format_results(results)
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return f"Error performing web search: {str(e)}"

    async def _arun(self, query: str, max_results: int = 5) -> str:
        """
        Asynchronous run method.
        """
        # DDGS is synchronous, so we run it in a thread to avoid blocking the async loop
        return await asyncio.to_thread(self._run, query, max_results)

    def _format_results(self, results: List[Dict[str, str]]) -> str:
        if not results:
            return "No results found."
        
        formatted = []
        for i, res in enumerate(results, 1):
            formatted.append(f"Source {i}:\nTitle: {res.get('title')}\nURL: {res.get('href')}\nContent: {res.get('body')}\n")
            
        return "\n---\n".join(formatted)


# Export a singleton for direct usage
web_search_tool = WebSearchTool()
