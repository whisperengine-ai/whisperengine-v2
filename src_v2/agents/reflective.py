import re
from typing import List, Dict, Any, Optional
from loguru import logger
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
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
    """
    def __init__(self):
        # Use 'main' mode or a specific 'reflective' mode if we had one. 
        # Using temperature=0.0 for precise tool usage reasoning.
        self.llm = create_llm(temperature=0.0, mode="main")
        self.max_steps = 5

    async def run(self, user_input: str, user_id: str, system_prompt: str) -> str:
        """
        Runs the ReAct loop and returns the final response.
        """
        # 1. Initialize Tools
        tools = self._get_tools(user_id)
        tool_map = {t.name: t for t in tools}
        tool_names = ", ".join([t.name for t in tools])
        tool_descriptions = "\n".join([f"{t.name}: {t.description}" for t in tools])

        # 2. Construct System Prompt
        full_prompt = self._construct_prompt(system_prompt, tool_descriptions, tool_names)

        # 3. Initialize Loop
        scratchpad = ""
        steps = 0
        
        logger.info(f"Starting Reflective Mode for user {user_id}")

        while steps < self.max_steps:
            steps += 1
            
            # Prepare prompt with scratchpad
            current_prompt = f"{full_prompt}\n\nQuestion: {user_input}\nThought:{scratchpad}"
            
            # Call LLM
            messages = [HumanMessage(content=current_prompt)]
            response = await self.llm.ainvoke(messages)
            text = response.content
            if isinstance(text, list):
                text = " ".join([str(item) for item in text])
            
            # Append to scratchpad (the LLM's output)
            scratchpad += text
            
            # Parse output
            action_match = re.search(r"Action:\s*(.*?)\nAction Input:\s*(.*)", text, re.DOTALL)
            
            if "Final Answer:" in text:
                final_answer = text.split("Final Answer:")[-1].strip()
                logger.info(f"Reflective Mode finished in {steps} steps.")
                return final_answer
            
            if action_match:
                action = action_match.group(1).strip()
                action_input = action_match.group(2).strip()
                
                logger.info(f"Reflective Step {steps}: {action} -> {action_input}")
                
                if action in tool_map:
                    tool = tool_map[action]
                    try:
                        # We assume tools have _arun implemented
                        observation = await tool.ainvoke(action_input)
                    except Exception as e:
                        observation = f"Error executing tool: {e}"
                else:
                    observation = f"Error: Tool '{action}' not found. Available tools: {tool_names}"
                
                # Append Observation
                scratchpad += f"\nObservation: {observation}\nThought:"
            else:
                # If no action and no final answer, the LLM might be confused or just thinking.
                # We'll force it to continue or stop if it looks like it's done.
                if steps == self.max_steps:
                    logger.warning("Reflective Mode reached max steps without Final Answer.")
                    return text # Return whatever we have
                
                # If it didn't output an action, maybe it's just monologuing. 
                # We append a newline and hope it continues or we can prompt it to act.
                scratchpad += "\n"
                
        return "I apologize, I got lost in thought and couldn't finish my reasoning."

    def _get_tools(self, user_id: str) -> List[BaseTool]:
        character_name = settings.DISCORD_BOT_NAME or "default"
        return [
            SearchSummariesTool(user_id=user_id),
            SearchEpisodesTool(user_id=user_id),
            LookupFactsTool(user_id=user_id),
            UpdateFactsTool(user_id=user_id),
            UpdatePreferencesTool(user_id=user_id, character_name=character_name)
        ]

    def _construct_prompt(self, base_system_prompt: str, tool_descriptions: str, tool_names: str) -> str:
        # We need to incorporate the character's persona into the ReAct prompt
        # so the Final Answer is in character.
        
        return f"""{base_system_prompt}

You are currently in "Deep Thinking" mode to answer a complex user query.
You need to use a reasoning loop to gather information before answering.

TOOLS AVAILABLE:
{tool_descriptions}

FORMAT INSTRUCTIONS:
Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final response to the user, written in your voice/persona.

Begin!
"""
