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
from src_v2.tools.math_tools import CalculatorTool
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
- calculator: Perform mathematical calculations
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

    # Minimal prompt for router LLM - just tool selection, no character personality
    ROUTER_SYSTEM_PROMPT = """You are a tool router for an AI companion. Your ONLY job is to decide which tools (if any) to call based on the user's message.

RULES:
1. If the user is just saying "hi" or casual chat, you MAY call lookup_user_facts to personalize (find their name).
2. If the user asks about past conversations or memories, call the appropriate search tool.
3. If the user asks about the universe, planets, servers, or channels, use check_planet_context or get_universe_overview.
4. If the user wants an image generated, call generate_image.
5. If the user needs a calculation, call calculator.
6. You can call multiple tools if needed.
7. If no tools are needed, just respond with an empty message (no content).

Do NOT generate a conversational response. Just decide on tools or respond empty."""

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
        - Router LLM (fast/cheap): Decides which tools to call (minimal prompt)
        - Main LLM (quality): Final character voice response (full character prompt)
        """
        # 1. Initialize Tools (Subset of full tools)
        tools = self._get_tools(user_id, guild_id, character_name, channel)
        router_with_tools = self.router_llm.bind_tools(tools)
        
        # 2. Build ROUTER messages (minimal prompt for tool selection only)
        # The router doesn't need the full character prompt - just tool awareness
        router_prompt = self.ROUTER_SYSTEM_PROMPT + self._get_agency_prompt()
        router_messages: List[BaseMessage] = [SystemMessage(content=router_prompt)]
        
        # Add filtered chat history (text-only, last 4 messages for context)
        # Router doesn't need images - just conversational context for pronoun resolution
        if chat_history:
            router_history = self._filter_history_for_router(chat_history[-4:])
            router_messages.extend(router_history)
        
        # 3. Prepare user message (text or multimodal with images)
        # Note: For router, we only send text (router doesn't need to see images)
        router_messages.append(HumanMessage(content=user_input))
        
        # Prepare full multimodal content for main LLM (used later)
        user_message_content = await self._prepare_user_message(user_input, image_urls)
        if image_urls:
            logger.info(f"CharacterAgent: Prepared multimodal message with {len(image_urls)} image(s), content_type={type(user_message_content)}")
        
        try:
            # 4. First LLM Call (Router) - Decide to use tool or not
            if callback:
                await callback("🔍 *Checking my memory...*")
                
            response = await router_with_tools.ainvoke(router_messages)
            
            # Debug logging
            logger.debug(f"CharacterAgent Router Response: content='{response.content}' tool_calls={response.tool_calls}")
            
            # 5. Handle Tool Calls (if any)
            # Check if response has tool_calls attribute (AIMessage)
            if isinstance(response, AIMessage) and response.tool_calls:
                # Build the MAIN LLM messages with full character prompt
                # (Router used minimal prompt, now we need full character voice)
                # NOTE: We don't add agency prompt - main LLM has no tools bound, just processes results
                main_messages: List[BaseMessage] = [SystemMessage(content=system_prompt)]
                if chat_history:
                    main_messages.extend(chat_history)
                main_messages.append(HumanMessage(content=user_message_content))
                main_messages.append(response)  # Include tool call decision

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
                        tool_tasks.append(self._execute_tool(selected_tool, tool_call, main_messages))
                    else:
                        logger.warning(f"CharacterAgent: Tool {tool_name} not found in available tools.")
                
                # Wait for all tools
                if tool_tasks:
                    await asyncio.gather(*tool_tasks)
                
                # 6. Final Response after tool outputs
                # Add guidance for handling empty/unhelpful tool results
                tool_results = [m for m in main_messages if isinstance(m, ToolMessage)]
                empty_results = any(
                    "no relevant" in (m.content or "").lower() or 
                    "not found" in (m.content or "").lower() or
                    "no results" in (m.content or "").lower() or
                    not m.content or m.content.strip() == ""
                    for m in tool_results
                )
                
                if empty_results:
                    # Guide the model to respond naturally even without tool results
                    main_messages.append(SystemMessage(content="The tool search didn't find specific information, but that's okay. Respond naturally to the user based on what you do know. Don't mention that you couldn't find anything - just have a genuine conversation."))
                
                # If images were included, remind the model to look at them
                if image_urls:
                    main_messages.append(SystemMessage(content="The user shared an image with you. Make sure to describe or comment on what you see in the image."))
                
                final_response = await self.llm.ainvoke(main_messages)
                logger.debug(f"CharacterAgent: Final LLM response after tools: content='{final_response.content[:200] if final_response.content else 'EMPTY'}' tool_calls={final_response.tool_calls}")
                
                # Handle case where model tries to chain tools (returns another tool call instead of text)
                if isinstance(final_response, AIMessage) and final_response.tool_calls and not final_response.content:
                    logger.warning("CharacterAgent: Model attempted to chain tools (not supported). Forcing text response.")
                    # We can't execute more tools. Just ask for a response.
                    main_messages.append(SystemMessage(content="You have used your allowed tool. Please provide a response to the user now based on the information you have."))
                    final_response = await self.llm.ainvoke(main_messages)

                if not final_response.content:
                    logger.warning(f"CharacterAgent: Final response after tools is empty. Messages: {len(main_messages)}, last tool results: {[m for m in main_messages if isinstance(m, ToolMessage)]}")
                return str(final_response.content) or "I'm having a bit of trouble processing that. Could you say it again?"
            
            # No tool used - pass through main LLM for character voice
            # The router decided no tools needed, now get the quality response with full character prompt
            # NOTE: We don't add agency prompt here since main LLM has no tools bound
            main_messages: List[BaseMessage] = [SystemMessage(content=system_prompt)]
            if chat_history:
                main_messages.extend(chat_history)
            main_messages.append(HumanMessage(content=user_message_content))
            
            # If images were included, remind the model to look at them
            if image_urls:
                main_messages.append(SystemMessage(content="The user shared an image with you. Make sure to describe or comment on what you see in the image."))
            
            final_response = await self.llm.ainvoke(main_messages)
            if not final_response.content:
                # Log more details about the request to diagnose image issues
                has_images = any(
                    isinstance(m.content, list) and any(
                        isinstance(c, dict) and c.get("type") in ("image_url", "image")
                        for c in m.content
                    )
                    for m in main_messages if hasattr(m, 'content')
                )
                logger.warning(
                    f"CharacterAgent: Main LLM returned empty content. "
                    f"has_images={has_images}, model={settings.LLM_MODEL_NAME}, "
                    f"response={final_response}"
                )
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

    def _filter_history_for_router(self, chat_history: List[BaseMessage]) -> List[BaseMessage]:
        """Filters chat history for the router LLM.
        
        Removes images and extracts only text content to reduce token usage.
        The router doesn't need vision - it just needs conversational context
        for pronoun resolution ("do that again", "search for what I mentioned").
        
        Args:
            chat_history: List of messages (may contain multimodal content)
            
        Returns:
            List of text-only messages suitable for router
        """
        filtered: List[BaseMessage] = []
        
        for msg in chat_history:
            content = msg.content
            
            # Handle multimodal content (list of content blocks)
            if isinstance(content, list):
                # Extract just text parts, skip images
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                    elif isinstance(part, str):
                        text_parts.append(part)
                
                text_content = " ".join(text_parts).strip()
                if text_content:
                    # Preserve message type (Human/AI/System)
                    filtered.append(type(msg)(content=text_content))
                else:
                    # Image-only message - add placeholder
                    filtered.append(type(msg)(content="[User shared an image]"))
            else:
                # Already text-only, keep as-is
                filtered.append(msg)
        
        return filtered

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
            
        # Add Math Tool
        tools.append(CalculatorTool())
        
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
            if image_urls:
                logger.warning(f"CharacterAgent: Images provided but LLM_SUPPORTS_VISION={settings.LLM_SUPPORTS_VISION}, skipping images")
            return user_input
        
        logger.info(f"CharacterAgent: Building multimodal content for {len(image_urls)} image(s), provider={settings.LLM_PROVIDER}")
        
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
                        logger.debug(f"CharacterAgent: Downloading image from {img_url[:100]}...")
                        img_response = await client.get(img_url, timeout=10.0)
                        img_response.raise_for_status()
                        
                        img_b64 = base64.b64encode(img_response.content).decode('utf-8')
                        mime_type = img_response.headers.get("content-type", "image/png")
                        
                        content.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{img_b64}"}
                        })
                        logger.info(f"CharacterAgent: Encoded image to base64, size={len(img_b64)} chars, mime={mime_type}")
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
            logger.info(f"CharacterAgent: Using direct image URLs for {settings.LLM_PROVIDER}")
        
        logger.info(f"CharacterAgent: Final multimodal content has {len(content)} parts")
        return content
