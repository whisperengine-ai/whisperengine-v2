import asyncio
from typing import List, Optional, Callable, Awaitable
from loguru import logger
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool

from src_v2.agents.llm_factory import create_llm
from src_v2.tools.memory_tools import (
    SearchSummariesTool, 
    SearchEpisodesTool, 
    LookupFactsTool, 
    UpdateFactsTool, 
    UpdatePreferencesTool
)
from src_v2.config.settings import settings

class ReflectiveAgent:
    """
    Executes a ReAct (Reasoning + Acting) loop to handle complex queries.
    Uses native LLM tool calling for reliability.
    """
    def __init__(self):
        self.llm = create_llm(temperature=0.1, mode="reflective")
        self.max_steps = settings.REFLECTIVE_MAX_STEPS

    async def run(self, user_input: str, user_id: str, system_prompt: str, callback: Optional[Callable[[str], Awaitable[None]]] = None) -> str:
        """
        Runs the ReAct loop and returns the final response.
        """
        # 1. Initialize Tools
        tools = self._get_tools(user_id)
        
        # 2. Construct System Prompt
        full_prompt = self._construct_prompt(system_prompt)

        # 3. Initialize Loop
        messages = [
            SystemMessage(content=full_prompt),
            HumanMessage(content=user_input)
        ]
        
        # Bind tools to LLM
        llm_with_tools = self.llm.bind_tools(tools)
        
        steps = 0
        tools_used = 0
        
        logger.info(f"Starting Reflective Mode (Native) for user {user_id}")

        while steps < self.max_steps:
            steps += 1
            
            # Invoke LLM
            response = await llm_with_tools.ainvoke(messages)
            messages.append(response)
            
            # 1. Handle Text Content (Thought or Final Answer)
            content = response.content
            if content:
                content_str = str(content)
                
                # Only stream if it's NOT the final answer (i.e., if there are tool calls)
                # If there are no tool calls, this content IS the final answer, so we shouldn't stream it to the "thinking" block.
                if response.tool_calls and callback:
                    await callback(content_str)
                
                logger.debug(f"Reflective Step {steps} content: {content_str[:100]}...")

            # 2. Handle Tool Calls
            if response.tool_calls:
                # Create tasks for all tools to run in parallel
                tasks = []
                for tool_call in response.tool_calls:
                    tasks.append(self._execute_tool_wrapper(tool_call, tools, callback))
                
                # Execute in parallel and process as they complete (Streaming)
                for task in asyncio.as_completed(tasks):
                    tool_message = await task
                    messages.append(tool_message)
                
                # Loop continues to let LLM process observations
                continue
            
            else:
                # No tool calls -> Final Answer
                # If content is empty (rare but possible with some models), return a fallback
                if not content:
                    return "I'm not sure how to answer that."
                
                logger.info(f"Reflective Mode finished in {steps} steps using {tools_used} tools.")
                return str(content)
        
        return "I apologize, I reached my reasoning limit and couldn't finish."

    async def _execute_tool_wrapper(self, tool_call: dict, tools: List[BaseTool], callback: Optional[Callable[[str], Awaitable[None]]]) -> ToolMessage:
        """
        Executes a single tool and handles logging/callbacks.
        """
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_call_id = tool_call["id"]
        
        logger.info(f"Executing Tool: {tool_name}")
        
        # Find tool instance
        selected_tool = next((t for t in tools if t.name == tool_name), None)
        
        if selected_tool:
            try:
                # Execute tool
                observation = await selected_tool.ainvoke(tool_args)
            except Exception as e:
                observation = f"Error executing tool: {e}"
        else:
            observation = f"Error: Tool {tool_name} not found."

        # Callback for observation
        if callback:
            obs_str = str(observation)
            preview = (obs_str[:100] + "...") if len(obs_str) > 100 else obs_str
            await callback(f"Observation ({tool_name}): {preview}")

        return ToolMessage(
            content=str(observation),
            tool_call_id=tool_call_id
        )

    def _get_tools(self, user_id: str) -> List[BaseTool]:
        character_name = settings.DISCORD_BOT_NAME or "default"
        return [
            SearchSummariesTool(user_id=user_id),
            SearchEpisodesTool(user_id=user_id),
            LookupFactsTool(user_id=user_id, bot_name=character_name),
            UpdateFactsTool(user_id=user_id),
            UpdatePreferencesTool(user_id=user_id, character_name=character_name)
        ]

    def _construct_prompt(self, base_system_prompt: str) -> str:
        return f"""You are a reflective AI agent designed to answer complex questions deeply.
You have access to tools to recall memories, facts, and summaries.
Use these tools to gather information before answering.
Think step-by-step.

CHARACTER CONTEXT:
{base_system_prompt}
"""
