import asyncio
from typing import List, Optional, Callable, Awaitable, Tuple, Any
from loguru import logger
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, BaseMessage, AIMessage
from langchain_core.tools import BaseTool

from src_v2.agents.llm_factory import create_llm
from src_v2.tools.memory_tools import (
    SearchSummariesTool, 
    SearchEpisodesTool, 
    LookupFactsTool, 
    ExploreGraphTool,
    DiscoverCommonGroundTool
)
from src_v2.tools.image_tools import GenerateImageTool
from src_v2.config.settings import settings

class CharacterAgent:
    """
    Tier 2 Agent: Capable of a single tool call before responding.
    Used for 'MODERATE' complexity queries where full ReAct loop is overkill.
    """
    def __init__(self):
        # Use main LLM (usually faster/cheaper than reflective)
        self.llm = create_llm(temperature=0.7, mode="main")

    async def run(
        self, 
        user_input: str, 
        user_id: str, 
        system_prompt: str, 
        chat_history: Optional[List[BaseMessage]] = None,
        callback: Optional[Callable[[str], Awaitable[None]]] = None,
        guild_id: Optional[str] = None
    ) -> str:
        """
        Executes a single-step tool lookup if needed, then generates response.
        """
        # 1. Initialize Tools (Subset of full tools)
        tools = self._get_tools(user_id, guild_id)
        llm_with_tools = self.llm.bind_tools(tools)
        
        # 2. Construct Messages
        messages: List[BaseMessage] = [SystemMessage(content=system_prompt)]
        if chat_history:
            messages.extend(chat_history)
        messages.append(HumanMessage(content=user_input))
        
        try:
            # 3. First LLM Call - Decide to use tool or not
            if callback:
                await callback("💭 *Thinking...*")
                
            response = await llm_with_tools.ainvoke(messages)
            messages.append(response)
            
            # 4. Handle Tool Calls (if any)
            # Check if response has tool_calls attribute (AIMessage)
            if isinstance(response, AIMessage) and response.tool_calls:
                # Execute tools in parallel
                tool_tasks = []
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    
                    # Find matching tool
                    selected_tool = next((t for t in tools if t.name == tool_name), None)
                    
                    if selected_tool:
                        if callback:
                            await callback(f"🛠️ *Using {tool_name}...*")
                        
                        # Create coroutine for tool execution
                        tool_tasks.append(self._execute_tool(selected_tool, tool_call, messages))
                
                # Wait for all tools
                if tool_tasks:
                    await asyncio.gather(*tool_tasks)
                
                # 5. Final Response after tool outputs
                final_response = await self.llm.ainvoke(messages)
                return str(final_response.content)
            
            # No tool used, return direct response
            return str(response.content)
            
        except Exception as e:
            logger.error(f"CharacterAgent failed: {e}")
            return "I'm having a bit of trouble thinking clearly right now. Can you say that again?"

    async def _execute_tool(self, tool: BaseTool, tool_call: dict, messages: List[BaseMessage]):
        """Executes a tool and appends the result to messages."""
        try:
            result = await tool.ainvoke(tool_call["args"])
            messages.append(ToolMessage(
                tool_call_id=tool_call["id"],
                name=tool_call["name"],
                content=str(result)
            ))
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            messages.append(ToolMessage(
                tool_call_id=tool_call["id"],
                name=tool_call["name"],
                content=f"Error: {str(e)}"
            ))

    def _get_tools(self, user_id: str, guild_id: Optional[str] = None) -> List[BaseTool]:
        """Returns the subset of tools available to CharacterAgent."""
        # guild_id is reserved for future guild-specific tools
        _ = guild_id 
        return [
            SearchSummariesTool(user_id=user_id),
            SearchEpisodesTool(user_id=user_id),
            LookupFactsTool(user_id=user_id),
            ExploreGraphTool(user_id=user_id),
            DiscoverCommonGroundTool(user_id=user_id),
            GenerateImageTool(user_id=user_id)
        ]
