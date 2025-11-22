import re
from typing import List, Dict, Any, Optional
from loguru import logger
from langchain_core.messages import HumanMessage
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
        self.llm = create_llm(temperature=0.1, mode="reflective")
        self.max_steps = settings.REFLECTIVE_MAX_STEPS

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
        tools_used = 0
        
        logger.info(f"Starting Reflective Mode for user {user_id}")

        while steps < self.max_steps:
            steps += 1
            
            # Prepare prompt with scratchpad
            current_prompt = f"{full_prompt}\n\nQuestion: {user_input}\nThought:{scratchpad}"
            
            # Call LLM with stop sequence to prevent hallucinating observations
            messages = [HumanMessage(content=current_prompt)]
            # Bind stop sequence for this call
            llm_with_stop = self.llm.bind(stop=["Observation:"])
            response = await llm_with_stop.ainvoke(messages)
            text = response.content
            if isinstance(text, list):
                text = " ".join([str(item) for item in text])
            
            # Safety: If stop sequence failed and Observation leaked, truncate it
            if "Observation:" in text:
                text = text.split("Observation:")[0].rstrip()
            
            # Log raw output for debugging
            logger.debug(f"Reflective Step {steps} raw output: {text[:300]}...")
            
            # Append to scratchpad (the LLM's output)
            scratchpad += text
            
            # Parse output for Action
            # We use a stricter regex that expects the text to end or hit a newline after input
            action_match = re.search(r"Action:\s*(.+?)\s*\nAction Input:\s*(.+?)(?:\n|$)", text, re.DOTALL)
            
            if action_match:
                action = action_match.group(1).strip()
                action_input = action_match.group(2).strip()
                
                logger.info(f"Reflective Step {steps}: {action} -> {action_input[:50]}...")
                tools_used += 1
                
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
                continue
            
            # Check for Final Answer AFTER checking for actions
            if "Final Answer:" in text:
                if tools_used == 0:
                    logger.warning("Reflective Mode tried to finish without using tools. Forcing continuation.")
                    scratchpad += "\n[SYSTEM: You must use at least one tool before providing Final Answer. Choose a tool now.]\nThought:"
                    continue
                    
                final_answer = text.split("Final Answer:")[-1].strip()
                logger.info(f"Reflective Mode finished in {steps} steps using {tools_used} tools.")
                return final_answer
            
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
            LookupFactsTool(user_id=user_id, bot_name=character_name),
            UpdateFactsTool(user_id=user_id),
            UpdatePreferencesTool(user_id=user_id, character_name=character_name)
        ]

    def _construct_prompt(self, base_system_prompt: str, tool_descriptions: str, tool_names: str) -> str:
        # Include explicit examples to guide the LLM
        
        return f"""You are an AI assistant that uses tools to answer questions accurately.

AVAILABLE TOOLS:
{tool_descriptions}

STRICT FORMAT - You must follow this format EXACTLY:

Thought: [describe what you need to do]
Action: [ONE tool name from: {tool_names}]
Action Input: [the input for that tool]

After each tool returns an "Observation:", continue with another Thought/Action OR finish with:

Thought: I have enough information now
Final Answer: [response in the character voice below]

EXAMPLE 1:
Question: What did the user tell me about their dog?
Thought: I need to search for past mentions of the user's dog
Action: search_specific_memories
Action Input: dog pet animal

[You would then see an Observation with the results]

EXAMPLE 2:
Question: What topics have we discussed over the past week?
Thought: I should search the conversation summaries for recent topics
Action: search_archived_summaries
Action Input: recent conversations topics discussed

CRITICAL RULES:
1. ALWAYS start with Action (not Final Answer) on your first response
2. Output Action and Action Input on separate lines
3. For questions about past conversations or "first conversation", use search_archived_summaries or search_specific_memories
4. If tools return no results, acknowledge that in Final Answer

CHARACTER CONTEXT (use this voice for Final Answer only):
{base_system_prompt}

Now begin!
"""
