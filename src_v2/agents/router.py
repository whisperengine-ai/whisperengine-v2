from typing import List, Dict, Any, Optional
from loguru import logger
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import BaseTool
from datetime import datetime
import time
from influxdb_client import Point

from src_v2.agents.llm_factory import create_llm
from src_v2.tools.memory_tools import SearchSummariesTool, SearchEpisodesTool, LookupFactsTool, UpdateFactsTool, UpdatePreferencesTool
from src_v2.tools.universe_tools import CheckPlanetContextTool
from src_v2.tools.image_tools import GenerateImageTool
from src_v2.agents.composite_tools import AnalyzeTopicTool
from src_v2.config.settings import settings
from src_v2.core.database import db_manager

class CognitiveRouter:
    """
    The 'Brain' of the agent. Decides which memory tools to use based on the user's input.
    Implements 'Reasoning Transparency' by logging why a tool was chosen.
    """
    def __init__(self):
        self.llm = create_llm(temperature=0.0, mode="router") # Low temp for deterministic routing

    async def route_and_retrieve(self, user_id: str, query: str, chat_history: Optional[List[BaseMessage]] = None, guild_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyzes the query, selects tools, executes them, and returns the context.
        
        Returns:
            Dict with keys:
            - context: str (The gathered information)
            - reasoning: str (Why the tools were chosen)
            - tool_calls: List[str] (Names of tools called)
        """
        
        # 1. Instantiate tools with the current user_id
        # Note: UpdatePreferencesTool needs character_name, which we can get from settings
        character_name = settings.DISCORD_BOT_NAME or "default"
        
        tools = [
            SearchSummariesTool(user_id=user_id),
            SearchEpisodesTool(user_id=user_id),
            LookupFactsTool(user_id=user_id),
            UpdateFactsTool(user_id=user_id),
            UpdatePreferencesTool(user_id=user_id, character_name=character_name),
            AnalyzeTopicTool(user_id=user_id, bot_name=character_name),
            CheckPlanetContextTool(guild_id=guild_id),
            GenerateImageTool(character_name=character_name)
        ]
        
        # 2. Bind tools to LLM
        llm_with_tools = self.llm.bind_tools(tools)
        
        # 3. Create System Prompt
        system_prompt = """You are the Cognitive Router for an advanced AI companion.
Your goal is to determine if the user's message requires retrieving external memory, facts, or generating media.

AVAILABLE TOOLS:
- search_archived_summaries: For broad topics, past events, or "what did we talk about last week?".
- search_specific_memories: For specific details, quotes, or "what was the name of that movie?".
- lookup_user_facts: For biographical info about the user (name, pets, location, preferences).
- update_user_facts: For when the user explicitly corrects a fact or says something has changed (e.g., "I moved to Seattle", "I don't like pizza anymore").
- update_user_preferences: For when the user explicitly changes a configuration setting (e.g., "stop calling me Captain", "change verbosity to short").
- analyze_topic: For comprehensive research on a broad topic. Searches summaries, episodes, and facts simultaneously. Use this for "tell me everything about X" or complex questions.
- check_planet_context: For questions about "where are we?", "who is here?", or details about the current server/planet.
- generate_image: For when the user asks to see something, asks for a selfie, or asks you to draw/imagine something.

RULES:
1. If the user is just saying "hi" or small talk, you MAY call lookup_user_facts to personalize the greeting (e.g. to find their name), but avoid heavy memory searches.
2. If the user asks a question that requires memory or media generation, CALL the appropriate tool.
3. You can call multiple tools if needed.
4. Use the provided chat history to resolve pronouns (e.g., "he", "it", "that") to specific entities.

Analyze the user's input and decide."""

        messages: List[BaseMessage] = [SystemMessage(content=system_prompt)]
        
        # Add recent history (last 3 messages) to help with context resolution
        if chat_history:
            # We only need the last few messages to resolve context
            recent_history = chat_history[-3:]
            # Cast to BaseMessage to satisfy type checker if needed, though list extension works at runtime
            messages.extend(recent_history)

        messages.append(HumanMessage(content=query))
        
        # 4. Invoke LLM
        try:
            response = await llm_with_tools.ainvoke(messages)
        except Exception as e:
            logger.error(f"Router LLM invocation failed: {e}")
            return {"context": "", "reasoning": "Error in router", "tool_calls": []}

        tool_calls = response.tool_calls
        context_parts = []
        executed_tool_names = []
        
        # 5. Execute Tools
        if tool_calls:
            logger.info(f"Router decided to call {len(tool_calls)} tools: {[tc['name'] for tc in tool_calls]}")
            
            async def execute_tool(tc):
                tool_name = tc['name']
                tool_args = tc['args']
                
                # Find the matching tool instance
                tool_instance = next((t for t in tools if t.name == tool_name), None)
                
                start_time = time.time()
                success = False
                
                if tool_instance:
                    try:
                        logger.debug(f"Executing {tool_name} with args: {tool_args}")
                        # We use ainvoke directly. The user_id is already in the tool instance.
                        result = await tool_instance.ainvoke(tool_args)
                        success = True
                        return tool_name, f"--- Result from {tool_name} ---\n{result}", start_time, success
                    except Exception as e:
                        logger.error(f"Tool execution failed for {tool_name}: {e}")
                        return tool_name, f"Error executing {tool_name}: {e}", start_time, success
                else:
                    logger.warning(f"LLM called unknown tool: {tool_name}")
                    return tool_name, None, start_time, False

            # Execute all tools in parallel
            import asyncio
            results = await asyncio.gather(*[execute_tool(tc) for tc in tool_calls])
            
            for tool_name, result, start_time, success in results:
                executed_tool_names.append(tool_name)
                if result:
                    context_parts.append(result)
                
                # Log tool usage to InfluxDB
                if db_manager.influxdb_write_api:
                    try:
                        duration_ms = (time.time() - start_time) * 1000
                        point = Point("tool_usage") \
                            .tag("tool_name", tool_name) \
                            .tag("user_id", user_id) \
                            .tag("bot_name", character_name) \
                            .field("duration_ms", duration_ms) \
                            .field("success", success) \
                            .time(datetime.utcnow())
                        
                        db_manager.influxdb_write_api.write(
                            bucket=settings.INFLUXDB_BUCKET,
                            org=settings.INFLUXDB_ORG,
                            record=point
                        )
                    except Exception as e:
                        logger.error(f"Failed to log tool usage: {e}")

            reasoning = f"Decided to call: {', '.join(executed_tool_names)}"
        else:
            logger.info("Router decided NO tools were needed.")
            reasoning = "No memory retrieval needed (Small talk / Immediate context)."

        return {
            "context": "\n\n".join(context_parts),
            "reasoning": reasoning,
            "tool_calls": executed_tool_names
        }
