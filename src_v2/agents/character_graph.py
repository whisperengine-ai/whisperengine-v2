import asyncio
import httpx
import operator
from typing import List, Optional, Callable, Awaitable, Tuple, Dict, Any, TypedDict, Annotated, Union, Literal
from loguru import logger
from langsmith import traceable
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, BaseMessage, AIMessage
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, END

from src_v2.agents.llm_factory import create_llm
from src_v2.config.settings import settings
from src_v2.config.constants import should_use_base64
from src_v2.utils.image_utils import process_image_for_llm
from src_v2.utils.llm_retry import invoke_with_retry
from src_v2.tools.memory_tools import (
    SearchSummariesTool, 
    SearchEpisodesTool, 
    LookupFactsTool,
    UpdateFactsTool,
    UpdatePreferencesTool,
    ExploreGraphTool,
    DiscoverCommonGroundTool,
    CharacterEvolutionTool,
    RecallBotConversationTool,
    SearchMyThoughtsTool,
    CreateUserGoalTool,
    ReadFullMemoryTool,
    FetchSessionTranscriptTool,
    SearchGraphMemoriesTool
)
from src_v2.tools.document_tools import ReadDocumentTool
from src_v2.tools.universe_tools import CheckPlanetContextTool, GetUniverseOverviewTool, GetSiblingBotInfoTool
from src_v2.tools.image_tools import GenerateImageTool
from src_v2.tools.math_tools import CalculatorTool
from src_v2.tools.discord_tools import SearchChannelMessagesTool, SearchUserMessagesTool, GetMessageContextTool, GetRecentMessagesTool
from src_v2.tools.web_search import WebSearchTool
from src_v2.tools.insight_tools import (
    AnalyzePatternsTool,
    DetectThemesTool,
    DiscoverCommunityInsightsTool
)
from src_v2.agents.composite_tools import AnalyzeTopicTool

# Define State
class CharacterAgentState(TypedDict):
    user_input: str
    user_id: str
    system_prompt: str
    chat_history: List[BaseMessage]
    image_urls: Optional[List[str]]
    
    # Internal state
    router_response: Optional[AIMessage]
    tool_messages: List[ToolMessage]
    final_response: Optional[str]
    
    # Resources
    tools: List[BaseTool]
    callback: Optional[Callable[[str], Awaitable[None]]]

class CharacterGraphAgent:
    """
    Tier 2 Agent: Capable of a single tool call before responding.
    Implemented using LangGraph.
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
- The user asks about another bot (sibling AI) in the WhisperEngine family

Available tools:
- old_summaries: Past conversations and topics (days/weeks ago)
- fetch_session_transcript: Get full transcript of a past session (use session_id from old_summaries)
- mem_search: Specific details and quotes from memory (includes [Graph: ...] context with related facts)
- graph_memory_search: Search memories using EXACT text matching in the graph (fallback when mem_search misses)
- read_document: Read the full content of an attached file
- lookup_user_facts: Facts about the user from the knowledge graph
- graph_walk: Explore connections and relationships
- common_ground: Find what you have in common
- char_evolve: Check your relationship level and trust
- planet_ctx: See the current server/planet context
- universe: View all planets and channels across the universe
- sibling_info: Learn about other bots (Dotty, Elena, etc.) - use when someone mentions a bot name
- chan_search: Find recent messages in the channel by keyword
- user_search: Find what a specific HUMAN said recently (not for bots)
- msg_context: Get context around a specific message (when replying to old messages)
- recent_msgs: Get latest channel messages without filtering (for "catch me up")
- calculator: Perform mathematical calculations
"""

    AGENCY_PROMPT_IMAGE = """- generate_image: Create images for the user
"""

    AGENCY_PROMPT_FOOTER = """
Don't use tools for:
- Simple greetings or casual chat
- Questions you can answer from general knowledge
- When the conversation is flowing naturally

IMPORTANT: 
- If the user asks about the universe, planets, servers, channels, or regions - USE the appropriate tool (universe, planet_ctx). Don't guess or give vague responses.
- If the user mentions another bot by name (Dotty, Elena, Aria, etc.) or asks "do you know X?" - USE sibling_info to check your relationship with that bot.

CRITICAL - NEVER FABRICATE MEMORIES:
- If a memory search returns "NOT IN MY RECORDS" or "No memories found", you MUST tell the user you don't have that memory stored.
- DO NOT reconstruct, imagine, or guess what a past message might have contained.
- It's better to say "I don't have that stored in my memory" than to make something up.
- If asked for exact text (poem, letter, quote), and you can't find it, say so clearly.

If you decide to use a tool, you don't need to announce it - just use the information naturally in your response. Your tool usage should feel like genuine curiosity or care, not robotic lookup.
"""

    # Minimal prompt for router LLM - just tool selection, no character personality
    ROUTER_SYSTEM_PROMPT = """You are a tool router for an AI companion. Your ONLY job is to decide which tools (if any) to call based on the user's message.

RULES:
1. If the user is just saying "hi" or casual chat, you MAY call lookup_user_facts to personalize (find their name).
2. If the user asks about past conversations or memories, call the appropriate search tool.
3. If the user asks about the universe, planets, servers, or channels, use planet_ctx or universe.
4. If the user wants an image generated, call generate_image.
5. If the user needs a calculation, call calculator.
6. You can call multiple tools if needed.
7. If no tools are needed, just respond with an empty message (no content).

Do NOT generate a conversational response. Just decide on tools or respond empty."""

    def __init__(self):
        # Router LLM for tool selection (fast/cheap)
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

    def _filter_history_for_router(self, chat_history: List[BaseMessage]) -> List[BaseMessage]:
        """Filters chat history for the router LLM (text only)."""
        filtered: List[BaseMessage] = []
        for msg in chat_history:
            content = msg.content
            if isinstance(content, list):
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                    elif isinstance(part, str):
                        text_parts.append(part)
                text_content = " ".join(text_parts).strip()
                if text_content:
                    filtered.append(type(msg)(content=text_content))
                else:
                    filtered.append(type(msg)(content="[User shared an image]"))
            else:
                filtered.append(msg)
        return filtered

    async def _prepare_user_message(self, user_input: str, image_urls: Optional[List[str]] = None) -> Any:
        """Prepares the user message content, handling text and optional images."""
        if not image_urls or not settings.LLM_SUPPORTS_VISION:
            return user_input
        
        content: List[Dict[str, Any]] = [{"type": "text", "text": user_input}]
        
        async with httpx.AsyncClient() as client:
            for img_url in image_urls:
                if should_use_base64(img_url, settings.LLM_PROVIDER):
                    try:
                        img_response = await client.get(img_url, timeout=10.0)
                        img_response.raise_for_status()
                        # Process image (handles animated GIFs by extracting first frame)
                        mime_type = img_response.headers.get("content-type", "image/png")
                        img_b64, mime_type = process_image_for_llm(img_response.content, mime_type)
                        content.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{img_b64}"}
                        })
                    except Exception as e:
                        logger.error(f"Failed to download/encode image {img_url}: {e}")
                        # Don't fallback to raw Discord CDN URL - it won't work for external LLMs
                        content.append({"type": "text", "text": "[An image was shared but could not be processed]"})
                else:
                    content.append({"type": "image_url", "image_url": {"url": img_url}})
        
        return content

    def _get_tools(self, user_id: str, guild_id: Optional[str] = None, character_name: Optional[str] = None, channel: Optional[Any] = None) -> List[BaseTool]:
        bot_name = character_name or "default"
        tools: List[BaseTool] = [
            # Memory & Knowledge Tools
            SearchSummariesTool(user_id=user_id, character_name=bot_name),
            FetchSessionTranscriptTool(),
            SearchEpisodesTool(user_id=user_id, character_name=bot_name),
            SearchGraphMemoriesTool(user_id=user_id),
            LookupFactsTool(user_id=user_id, bot_name=bot_name),
            UpdateFactsTool(user_id=user_id),
            UpdatePreferencesTool(user_id=user_id, character_name=bot_name),
            AnalyzeTopicTool(user_id=user_id, bot_name=bot_name),
            
            # Document Tools
            ReadDocumentTool(user_id=user_id, character_name=bot_name),
            ReadFullMemoryTool(),
            
            # Bot's Internal Experiences (diaries, dreams, observations, gossip)
            SearchMyThoughtsTool(character_name=bot_name),
            
            # Cross-Bot Memory Recall
            RecallBotConversationTool(character_name=bot_name),
            
            # User-Requested Goals
            CreateUserGoalTool(user_id=user_id, character_name=bot_name),
            
            # Graph & Relationship Tools
            ExploreGraphTool(user_id=user_id, bot_name=bot_name),
            DiscoverCommonGroundTool(user_id=user_id, bot_name=bot_name),
            CharacterEvolutionTool(user_id=user_id, character_name=bot_name),
            
            # Introspection & Pattern Tools
            AnalyzePatternsTool(user_id=user_id, bot_name=bot_name),
            DetectThemesTool(user_id=user_id, bot_name=bot_name),
            
            # Community/Cross-Bot Discovery
            DiscoverCommunityInsightsTool(character_name=bot_name),
            
            # Context Tools
            CheckPlanetContextTool(guild_id=guild_id),
            GetUniverseOverviewTool(),
            GetSiblingBotInfoTool(character_name=bot_name),
            
            # Math Tool
            CalculatorTool(),
        ]
        
        # Conditionally add web search tool
        if settings.ENABLE_WEB_SEARCH:
            tools.append(WebSearchTool())
        
        # Add Discord search tools if channel is available
        if channel:
            tools.extend([
                SearchChannelMessagesTool(channel=channel),
                SearchUserMessagesTool(channel=channel),
                GetMessageContextTool(channel=channel),
                GetRecentMessagesTool(channel=channel),
            ])
        
        # Conditionally add image generation tool
        if settings.ENABLE_IMAGE_GENERATION:
            tools.append(GenerateImageTool(user_id=user_id, character_name=bot_name))
        
        return tools

    async def _execute_tool_wrapper(self, tool_call: Any, tools: List[BaseTool], callback: Optional[Callable[[str], Awaitable[None]]]) -> ToolMessage:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_call_id = tool_call["id"]
        
        selected_tool = next((t for t in tools if t.name == tool_name), None)
        
        if selected_tool:
            if callback:
                await callback(f"🛠️ *Using {tool_name}...*")
            try:
                observation = await selected_tool.ainvoke(tool_args)
            except Exception as e:
                observation = f"Error executing tool: {e}"
        else:
            observation = f"Error: Tool {tool_name} not found."

        return ToolMessage(
            content=str(observation),
            tool_call_id=tool_call_id,
            name=tool_name
        )

    # --- Graph Nodes ---

    async def router_node(self, state: CharacterAgentState):
        """Decides which tools to call."""
        callback = state['callback']
        if callback:
            await callback("🔍 *Checking my memory...*")

        # Build router prompt
        router_prompt = self.ROUTER_SYSTEM_PROMPT + self._get_agency_prompt()
        messages: List[BaseMessage] = [SystemMessage(content=router_prompt)]
        
        if state['chat_history']:
            messages.extend(self._filter_history_for_router(state['chat_history'][-4:]))
        
        messages.append(HumanMessage(content=state['user_input']))
        
        # Bind tools
        router_with_tools = self.router_llm.bind_tools(state['tools'])
        
        try:
            # LLM call with retry for transient errors
            response = await invoke_with_retry(router_with_tools.ainvoke, messages, max_retries=3)
            return {"router_response": response}
        except Exception as e:
            logger.error(f"Router LLM failed: {e}")
            # Return empty AIMessage to proceed to responder without tools
            return {"router_response": AIMessage(content="")}

    async def tools_node(self, state: CharacterAgentState):
        """Executes tools if router decided to use them."""
        router_response = state['router_response']
        if not router_response or not router_response.tool_calls:
            return {"tool_messages": []}
        
        tasks = []
        for tool_call in router_response.tool_calls:
            tasks.append(self._execute_tool_wrapper(tool_call, state['tools'], state['callback']))
        
        tool_messages = await asyncio.gather(*tasks)
        return {"tool_messages": tool_messages}

    async def responder_node(self, state: CharacterAgentState):
        """Generates final response using tool outputs."""
        # Build main messages
        messages: List[BaseMessage] = [SystemMessage(content=state['system_prompt'])]
        if state['chat_history']:
            messages.extend(state['chat_history'])
        
        # Prepare multimodal user message
        user_content = await self._prepare_user_message(state['user_input'], state['image_urls'])
        messages.append(HumanMessage(content=user_content))
        
        # Add tool outputs if any - convert to SystemMessage to avoid tool_call_id compatibility issues
        # (Some models like Mistral have strict tool_call_id format requirements)
        if state['router_response'] and state['router_response'].tool_calls:
            # Summarize tool calls and results as text instead of passing raw ToolMessages
            tool_summary_parts = []
            for i, tool_call in enumerate(state['router_response'].tool_calls):
                tool_name = tool_call.get("name", "unknown")
                tool_args = tool_call.get("args", {})
                tool_result = state['tool_messages'][i].content if i < len(state['tool_messages']) else "No result"
                tool_summary_parts.append(f"[Tool: {tool_name}]\nArgs: {tool_args}\nResult: {tool_result}")
            
            tool_context = "\n\n".join(tool_summary_parts)
            messages.append(SystemMessage(content=f"[TOOL RESULTS]\n{tool_context}"))
            
            # Handle empty results guidance
            empty_results = False
            for m in state['tool_messages']:
                content_str = str(m.content) if m.content else ""
                if "no relevant" in content_str.lower() or \
                   "not found" in content_str.lower() or \
                   "no results" in content_str.lower() or \
                   not content_str.strip():
                    empty_results = True
                    break
            
            if empty_results:
                messages.append(SystemMessage(content="The tool search didn't find specific information, but that's okay. Respond naturally to the user based on what you do know. Don't mention that you couldn't find anything - just have a genuine conversation."))
        
        if state['image_urls']:
            messages.append(SystemMessage(content="The user shared an image with you. Make sure to describe or comment on what you see in the image."))

        try:
            # LLM call with retry for transient errors
            response = await invoke_with_retry(self.llm.ainvoke, messages, max_retries=3)
            response_content = str(response.content) if response.content else ""
            
            # --- Check for "promised but not delivered" ---
            # If the responder LLM says it will generate an image but didn't route to image tool
            if settings.ENABLE_IMAGE_GENERATION:
                content_lower = response_content.lower()
                image_promise_patterns = [
                    "let me generate", "i'll generate", "i will generate",
                    "let me create", "i'll create", "i will create an image",
                    "generating an image", "creating an image",
                    "here's the image", "here is the image",
                    "[generates image", "[creating image",
                    "let me draw", "i'll draw", "i will draw",
                ]
                
                # Check if image tool was actually called
                image_tool_used = False
                if state['router_response'] and state['router_response'].tool_calls:
                    for tc in state['router_response'].tool_calls:
                        if tc.get("name") == "generate_image":
                            image_tool_used = True
                            break
                
                has_image_promise = any(pattern in content_lower for pattern in image_promise_patterns)
                
                if has_image_promise and not image_tool_used:
                    logger.warning("CharacterGraphAgent: Detected 'promised but not delivered' image generation, re-routing")
                    # Re-invoke router with explicit image instruction
                    messages.append(AIMessage(content=response_content))
                    messages.append(SystemMessage(
                        content="You mentioned generating an image but did NOT use the generate_image tool. "
                               "You MUST call generate_image now to actually create the image. "
                               "Call the tool immediately."
                    ))
                    
                    # Force another router call (with retry)
                    router_with_tools = self.router_llm.bind_tools(state['tools'])
                    retry_response = await invoke_with_retry(router_with_tools.ainvoke, messages, max_retries=3)
                    
                    if retry_response.tool_calls:
                        # Execute the tool
                        for tool_call in retry_response.tool_calls:
                            if tool_call.get("name") == "generate_image":
                                tool_result = await self._execute_tool_wrapper(
                                    tool_call, state['tools'], state['callback']
                                )
                                # Now generate final response with tool result (with retry)
                                messages.append(retry_response)
                                messages.append(tool_result)
                                final_response = await invoke_with_retry(self.llm.ainvoke, messages, max_retries=3)
                                return {"final_response": str(final_response.content)}
            
            # Handle tool chaining attempt (not supported in Tier 2)
            if isinstance(response, AIMessage) and response.tool_calls and not response.content:
                messages.append(SystemMessage(content="You have used your allowed tool. Please provide a response to the user now based on the information you have."))
                response = await invoke_with_retry(self.llm.ainvoke, messages, max_retries=3)
                
            return {"final_response": str(response.content)}
        except Exception as e:
            logger.error(f"Responder LLM failed: {e}")
            return {"final_response": "I'm having a bit of trouble processing that. Could you say it again?"}

    def should_use_tools(self, state: CharacterAgentState) -> Literal["tools", "responder"]:
        router_response = state['router_response']
        if router_response and router_response.tool_calls:
            return "tools"
        return "responder"

    @traceable(name="CharacterGraphAgent.run", run_type="chain")
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
        """Executes the Character Agent workflow."""
        
        # Initialize tools
        tools = self._get_tools(user_id, guild_id, character_name, channel)
        
        # Build Graph
        workflow = StateGraph(CharacterAgentState)
        
        workflow.add_node("router", self.router_node)
        workflow.add_node("tools", self.tools_node)
        workflow.add_node("responder", self.responder_node)
        
        workflow.set_entry_point("router")
        
        workflow.add_conditional_edges(
            "router",
            self.should_use_tools,
            {
                "tools": "tools",
                "responder": "responder"
            }
        )
        
        workflow.add_edge("tools", "responder")
        workflow.add_edge("responder", END)
        
        app = workflow.compile()
        
        # Run Graph
        final_state = await app.ainvoke({
            "user_input": user_input,
            "user_id": user_id,
            "system_prompt": system_prompt,
            "chat_history": chat_history or [],
            "image_urls": image_urls,
            "tools": tools,
            "callback": callback,
            "router_response": None,
            "tool_messages": [],
            "final_response": None
        })
        
        return final_state.get("final_response") or "..."
