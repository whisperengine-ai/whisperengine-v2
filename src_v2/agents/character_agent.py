import asyncio
import base64
from typing import List, Optional, Callable, Awaitable, Any, Dict
from loguru import logger
from langsmith import traceable
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, BaseMessage, AIMessage
from langchain_core.tools import BaseTool
import httpx

from src_v2.agents.llm_factory import create_llm
from src_v2.config.settings import settings
from src_v2.config.constants import get_image_format_for_provider
from src_v2.tools.memory_tools import (
    SearchSummariesTool, 
    SearchEpisodesTool, 
    LookupFactsTool, 
    ExploreGraphTool,
    DiscoverCommonGroundTool,
    CharacterEvolutionTool
)
from src_v2.tools.universe_tools import CheckPlanetContextTool, GetUniverseOverviewTool
from src_v2.tools.image_tools import GenerateImageTool
from src_v2.tools.discord_tools import SearchChannelMessagesTool, SearchUserMessagesTool, GetMessageContextTool, GetRecentMessagesTool

class CharacterAgent:
    """
    Tier 2 Agent: Capable of a single tool call before responding.
    Used for 'MODERATE' complexity queries where full ReAct loop is overkill.
    
    Design Philosophy:
    - Characters have agency (they decide to look things up)
    - But not unlimited agency (one tool max, no loops)
    - Tool usage reflects personality (emergent from prompt)
    - Fast enough for conversation (2-4 seconds added latency)
    """
    
    # Base prompt - image generation line is added dynamically based on feature flag
    AGENCY_PROMPT_BASE = """

## Tool Usage (Your Agency)

You have access to tools that let you look things up. Use them when:
- The user asks about something you might have discussed before
- You want to recall a specific detail to make the conversation more personal
- You genuinely need information to give a good response
- The user asks about your relationship or how close you are
- You want to find common ground or shared interests
- The user asks what they or someone else just said in the channel

Available tools:
- search_archived_summaries: Past conversations and topics (days/weeks ago)
- search_specific_memories: Specific details and quotes from memory
- lookup_user_facts: Facts about the user from the knowledge graph
- explore_knowledge_graph: Explore connections and relationships
- discover_common_ground: Find what you have in common
- get_character_evolution: Check your relationship level and trust
- check_planet_context: See the current server/planet context
- get_universe_overview: View all planets and channels across the universe
- search_channel_messages: Find recent messages in the channel by keyword
- search_user_messages: Find what a specific person said recently
- get_message_context: Get context around a specific message (when replying to old messages)
- get_recent_messages: Get latest channel messages without filtering (for "catch me up")
"""

    AGENCY_PROMPT_IMAGE = """- generate_image: Create images for the user
"""

    AGENCY_PROMPT_FOOTER = """
Don't use tools for:
- Simple greetings or casual chat
- Questions you can answer from general knowledge
- When the conversation is flowing naturally

IMPORTANT: If the user asks about the universe, planets, servers, channels, or regions - USE the appropriate tool (get_universe_overview, check_planet_context). Don't guess or give vague responses.

If you decide to use a tool, you don't need to announce it - just use the information naturally in your response. Your tool usage should feel like genuine curiosity or care, not robotic lookup.
"""

    def __init__(self):
        # Router LLM for tool selection (fast/cheap) - only decides which tools to call
        self.router_llm = create_llm(temperature=0.3, mode="router")
        # Main LLM for final character response (quality voice)
        self.llm = create_llm(temperature=0.7, mode="main")
    
    def _get_agency_prompt(self) -> str:
        """Builds the agency prompt, including image generation only if enabled."""
        prompt = self.AGENCY_PROMPT_BASE
        if settings.ENABLE_IMAGE_GENERATION:
            prompt += self.AGENCY_PROMPT_IMAGE
        prompt += self.AGENCY_PROMPT_FOOTER
        return prompt

    @traceable(name="CharacterAgent.run", run_type="chain")
    async def run(
        self, 
        user_input: str, 
        user_id: str, 
        system_prompt: str, 
        chat_history: Optional[List[BaseMessage]] = None,
        callback: Optional[Callable[[str], Awaitable[None]]] = None,
        guild_id: Optional[str] = None,
        character_name: Optional[str] = None,
        channel: Optional[Any] = None,
        image_urls: Optional[List[str]] = None
    ) -> str:
        """
        Executes a single-step tool lookup if needed, then generates response.
        
        Uses two-LLM approach:
        - Router LLM (fast/cheap): Decides which tools to call
        - Main LLM (quality): Final character voice response
        """
        # 1. Initialize Tools (Subset of full tools)
        tools = self._get_tools(user_id, guild_id, character_name, channel)
        router_with_tools = self.router_llm.bind_tools(tools)
        
        # 2. Construct Messages with agency guidance (dynamically built based on feature flags)
        enhanced_prompt = system_prompt + self._get_agency_prompt()
        messages: List[BaseMessage] = [SystemMessage(content=enhanced_prompt)]
        if chat_history:
            messages.extend(chat_history)
        
        # 3. Prepare user message (text or multimodal with images)
        user_message_content = await self._prepare_user_message(user_input, image_urls)
        messages.append(HumanMessage(content=user_message_content))
        
        try:
            # 3. First LLM Call (Router) - Decide to use tool or not
            if callback:
                await callback("🔍 *Checking my memory...*")
                
            response = await router_with_tools.ainvoke(messages)
            messages.append(response)
            
            # Debug logging
            logger.debug(f"CharacterAgent Router Response: content='{response.content}' tool_calls={response.tool_calls}")
            
            # 4. Handle Tool Calls (if any)
            # Check if response has tool_calls attribute (AIMessage)
            if isinstance(response, AIMessage) and response.tool_calls:
                # Execute tools in parallel
                tool_tasks = []
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    
                    # Find matching tool
                    selected_tool = next((t for t in tools if t.name == tool_name), None)
                    
                    if selected_tool:
                        if callback:
                            await callback(f"🛠️ *Using {tool_name}...*")
                        
                        # Create coroutine for tool execution
                        tool_tasks.append(self._execute_tool(selected_tool, tool_call, messages))
                    else:
                        logger.warning(f"CharacterAgent: Tool {tool_name} not found in available tools.")
                
                # Wait for all tools
                if tool_tasks:
                    await asyncio.gather(*tool_tasks)
                
                # 5. Final Response after tool outputs
                # Add guidance for handling empty/unhelpful tool results
                tool_results = [m for m in messages if isinstance(m, ToolMessage)]
                empty_results = any(
                    "no relevant" in (m.content or "").lower() or 
                    "not found" in (m.content or "").lower() or
                    "no results" in (m.content or "").lower() or
                    not m.content or m.content.strip() == ""
                    for m in tool_results
                )
                
                if empty_results:
                    # Guide the model to respond naturally even without tool results
                    messages.append(SystemMessage(content="The tool search didn't find specific information, but that's okay. Respond naturally to the user based on what you do know. Don't mention that you couldn't find anything - just have a genuine conversation."))
                
                final_response = await self.llm.ainvoke(messages)
                logger.debug(f"CharacterAgent: Final LLM response after tools: content='{final_response.content[:200] if final_response.content else 'EMPTY'}' tool_calls={final_response.tool_calls}")
                
                # Handle case where model tries to chain tools (returns another tool call instead of text)
                if isinstance(final_response, AIMessage) and final_response.tool_calls and not final_response.content:
                    logger.warning("CharacterAgent: Model attempted to chain tools (not supported). Forcing text response.")
                    # We can't execute more tools. Just ask for a response.
                    messages.append(SystemMessage(content="You have used your allowed tool. Please provide a response to the user now based on the information you have."))
                    final_response = await self.llm.ainvoke(messages)

                if not final_response.content:
                    logger.warning(f"CharacterAgent: Final response after tools is empty. Messages: {len(messages)}, last tool results: {[m for m in messages if isinstance(m, ToolMessage)]}")
                return str(final_response.content) or "I'm having a bit of trouble processing that. Could you say it again?"
            
            # No tool used - pass through main LLM for character voice
            # The router decided no tools needed, now get the quality response
            final_response = await self.llm.ainvoke(messages)
            if not final_response.content:
                logger.warning(f"CharacterAgent: Main LLM returned empty content. response={final_response}")
            return str(final_response.content) or "I'm having a bit of trouble thinking clearly right now. Can you say that again?"
            
        except Exception as e:
            logger.error(f"CharacterAgent failed: {e}")
            import traceback
            traceback.print_exc()
            # Don't expose internal errors to users - log them instead
            return "I'm having a bit of trouble thinking clearly right now. Can you try again in a moment?"

    async def _execute_tool(self, tool: BaseTool, tool_call: dict, messages: List[BaseMessage]):
        """Executes a tool and appends the result to messages."""
        tool_id = tool_call.get("id", "unknown_id")
        tool_name = tool_call.get("name", "unknown_tool")
        
        try:
            logger.info(f"CharacterAgent: Executing tool {tool_name} with args: {tool_call.get('args', {})}")
            result = await tool.ainvoke(tool_call["args"])
            logger.info(f"CharacterAgent: Tool {tool_name} returned: {str(result)[:200]}...")
            messages.append(ToolMessage(
                tool_call_id=tool_id,
                name=tool_name,
                content=str(result)
            ))
        except Exception as e:
            logger.error(f"Tool execution failed for {tool_name}: {e}")
            import traceback
            traceback.print_exc()
            # Provide a generic error to the LLM (it will formulate a user-friendly response)
            messages.append(ToolMessage(
                tool_call_id=tool_id,
                name=tool_name,
                content="The tool encountered an error and couldn't complete the request."
            ))

    def _get_tools(self, user_id: str, guild_id: Optional[str] = None, character_name: Optional[str] = None, channel: Optional[Any] = None) -> List[BaseTool]:
        """Returns the subset of tools available to CharacterAgent.
        
        Tier 2 tools are a curated subset focused on:
        - Memory retrieval (summaries, episodes, facts)
        - Graph exploration (relationships, common ground)
        - Universe context (planet/channel awareness)
        - Discord search (channel messages, user messages)
        - Image generation (if enabled)
        - Relationship awareness
        
        Excludes:
        - Update tools (UpdateFactsTool, UpdatePreferencesTool) - complex operations
        - Introspection tools (AnalyzePatternsTool, DetectThemesTool) - background only
        """
        # Note: bot_name and character_name are used interchangeably across tools
        # (historical inconsistency). They refer to the same value.
        bot_name = character_name or "default"
        
        tools: List[BaseTool] = [
            # Memory & Knowledge Tools
            SearchSummariesTool(user_id=user_id),
            SearchEpisodesTool(user_id=user_id),
            LookupFactsTool(user_id=user_id, bot_name=bot_name),
            
            # Graph & Relationship Tools
            ExploreGraphTool(user_id=user_id, bot_name=bot_name),
            DiscoverCommonGroundTool(user_id=user_id, bot_name=bot_name),
            CharacterEvolutionTool(user_id=user_id, character_name=bot_name),
            
            # Universe Context Tools
            CheckPlanetContextTool(guild_id=guild_id),
            GetUniverseOverviewTool(),
        ]
        
        # Add Discord search tools if channel is available (not in DM API context)
        if channel:
            tools.extend([
                SearchChannelMessagesTool(channel=channel),
                SearchUserMessagesTool(channel=channel),
                GetMessageContextTool(channel=channel),
                GetRecentMessagesTool(channel=channel),
            ])
        
        # Conditionally add image generation tool (respects feature flag)
        if settings.ENABLE_IMAGE_GENERATION:
            tools.append(GenerateImageTool(user_id=user_id, character_name=bot_name))
        
        return tools

    async def _prepare_user_message(
        self, 
        user_input: str, 
        image_urls: Optional[List[str]] = None
    ) -> Any:
        """
        Prepares the user message content, handling text and optional images.
        
        Args:
            user_input: The user's text message
            image_urls: Optional list of image URLs to include
            
        Returns:
            Either a string (text only) or a list of content blocks (multimodal)
        """
        if not image_urls or not settings.LLM_SUPPORTS_VISION:
            return user_input
        
        # Build multimodal content
        content: List[Dict[str, Any]] = [{"type": "text", "text": user_input}]
        
        # Check if provider requires base64 encoding or supports direct URLs
        # Use main LLM provider since CharacterAgent uses the main LLM for final response
        image_format = get_image_format_for_provider(settings.LLM_PROVIDER)
        
        if image_format == "base64":
            # Download and encode images for providers that require base64
            async with httpx.AsyncClient() as client:
                for img_url in image_urls:
                    try:
                        img_response = await client.get(img_url, timeout=10.0)
                        img_response.raise_for_status()
                        
                        img_b64 = base64.b64encode(img_response.content).decode('utf-8')
                        mime_type = img_response.headers.get("content-type", "image/png")
                        
                        content.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{img_b64}"}
                        })
                        logger.debug(f"CharacterAgent: Encoded image to base64 for {settings.LLM_PROVIDER}")
                    except Exception as e:
                        logger.error(f"CharacterAgent: Failed to download/encode image {img_url}: {e}")
                        # Fallback to URL anyway
                        content.append({
                            "type": "image_url",
                            "image_url": {"url": img_url}
                        })
        else:
            # Use URLs directly for providers that support it
            for img_url in image_urls:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": img_url}
                })
            logger.debug(f"CharacterAgent: Using direct image URLs for {settings.LLM_PROVIDER}")
        
        return content
