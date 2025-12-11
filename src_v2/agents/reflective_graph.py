import asyncio
import httpx
import operator
import re
from typing import List, Optional, Callable, Awaitable, Tuple, Dict, Any, TypedDict, Annotated, Union, Literal
from loguru import logger
from langsmith import traceable
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, BaseMessage, AIMessage
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, END

from src_v2.agents.llm_factory import create_llm
from src_v2.config.constants import should_use_base64
from src_v2.utils.image_utils import process_image_for_llm
from src_v2.utils.llm_retry import invoke_with_retry, get_image_error_message
from src_v2.tools.memory_tools import (
    SearchSummariesTool, SearchEpisodesTool, LookupFactsTool,
    UpdateFactsTool, UpdatePreferencesTool, SearchMyThoughtsTool, RecallBotConversationTool,
    CreateUserGoalTool, ExploreGraphTool, DiscoverCommonGroundTool,
    CharacterEvolutionTool, ReadFullMemoryTool
)
from src_v2.tools.document_tools import ReadDocumentTool
from src_v2.agents.composite_tools import AnalyzeTopicTool
from src_v2.tools.universe_tools import CheckPlanetContextTool, GetUniverseOverviewTool, GetSiblingBotInfoTool
from src_v2.tools.discord_tools import SearchChannelMessagesTool, SearchUserMessagesTool, GetMessageContextTool, GetRecentMessagesTool
from src_v2.tools.insight_tools import (
    AnalyzePatternsTool,
    DetectThemesTool,
    DiscoverCommunityInsightsTool
)
from src_v2.tools.image_tools import GenerateImageTool
from src_v2.tools.math_tools import CalculatorTool
from src_v2.tools.web_search import WebSearchTool
from src_v2.tools.web_reader import ReadWebPageTool
from src_v2.config.settings import settings
from src_v2.memory.traces import trace_retriever

# Define State
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    steps: int
    tools: List[BaseTool]
    callback: Optional[Callable[[str], Awaitable[None]]]
    max_steps: int

class ReflectiveGraphAgent:
    """
    Executes a ReAct (Reasoning + Acting) loop using LangGraph.
    This replaces the manual loop in ReflectiveAgent with a graph-based approach.
    """
    def __init__(self):
        self.llm = create_llm(temperature=0.1, mode="reflective")

    def _sanitize_history(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """
        Ensures message history complies with strict LLM provider rules (e.g. Anthropic).
        - Merges consecutive User messages.
        - Ensures proper User/Assistant alternation (excluding ToolMessages which follow AIMessages).
        """
        sanitized: List[BaseMessage] = []
        for msg in messages:
            if not sanitized:
                sanitized.append(msg)
                continue
            
            last_msg = sanitized[-1]
            
            # Merge consecutive HumanMessages
            if isinstance(msg, HumanMessage) and isinstance(last_msg, HumanMessage):
                last_content = str(last_msg.content)
                new_content = str(msg.content)
                merged_content = f"{last_content}\n\n{new_content}"
                # Create NEW message to avoid mutating shared state
                sanitized[-1] = HumanMessage(content=merged_content)
            # Skip consecutive AIMessages (keep only the last one)
            elif isinstance(msg, AIMessage) and isinstance(last_msg, AIMessage):
                # logger.debug("Sanitizer: Skipping duplicate AIMessage")
                sanitized[-1] = msg  # Replace with newer one
            else:
                sanitized.append(msg)
        
        return sanitized

    def _get_tools(self, user_id: str, guild_id: Optional[str] = None, channel: Optional[Any] = None, character_name: Optional[str] = None) -> List[BaseTool]:
        bot_name = character_name or settings.DISCORD_BOT_NAME or "default"
        tools = [
            # Memory & Knowledge Tools
            SearchSummariesTool(user_id=user_id),
            SearchEpisodesTool(user_id=user_id),
            LookupFactsTool(user_id=user_id, bot_name=bot_name),
            UpdateFactsTool(user_id=user_id),
            UpdatePreferencesTool(user_id=user_id, character_name=bot_name),
            AnalyzeTopicTool(user_id=user_id, bot_name=bot_name),
            
            # Document Tool
            ReadDocumentTool(user_id=user_id, character_name=bot_name),
            ReadFullMemoryTool(),
            
            # Bot's Internal Experiences (diaries, dreams, observations, gossip)
            SearchMyThoughtsTool(character_name=bot_name),
            
            # Cross-Bot Memory Recall (what did I talk about with other bots?)
            RecallBotConversationTool(character_name=character_name),
            
            # User-Requested Goals (help me with X, remind me about Y)
            CreateUserGoalTool(user_id=user_id, character_name=character_name),
            
            # Graph & Relationship Tools
            ExploreGraphTool(user_id=user_id, bot_name=character_name),
            DiscoverCommonGroundTool(user_id=user_id, bot_name=character_name),
            CharacterEvolutionTool(user_id=user_id, character_name=character_name),
            
            # Introspection & Pattern Tools
            AnalyzePatternsTool(user_id=user_id, bot_name=character_name),
            DetectThemesTool(user_id=user_id, bot_name=character_name),
            
            # Community/Cross-Bot Discovery (Phase E13.1)
            DiscoverCommunityInsightsTool(character_name=character_name),
            
            # Context Tools
            CheckPlanetContextTool(guild_id=guild_id),
            GetUniverseOverviewTool(),
            GetSiblingBotInfoTool(character_name=character_name),
            
            # Math Tool
            CalculatorTool(),
        ]
        
        # Conditionally add web search tool
        if settings.ENABLE_WEB_SEARCH:
            tools.append(WebSearchTool())
        
        if settings.ENABLE_WEB_READER:
            tools.append(ReadWebPageTool())
        
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
            tools.append(GenerateImageTool(character_name=character_name, user_id=user_id))
        
        return tools

    def _construct_prompt(self, base_system_prompt: str, detected_intents: Optional[List[str]] = None) -> str:
        """
        Constructs a clean, well-organized system prompt for the reflective agent.
        
        Structure:
        1. Role & Character Context
        2. Available Tools (organized by category)
        3. Tool Usage Guide (when to use each tool)
        4. Special Handling Notes
        """
        detected_intents = detected_intents or []
        
        # Build tool categories list
        tool_categories = [
            "1. Memory & Knowledge: old_summaries, mem_search, full_memory, lookup_user_facts, update_user_facts, analyze_topic, read_document",
            "2. My Inner Life: search_my_thoughts (my diaries, dreams, observations, gossip, epiphanies)",
            "3. Graph & Relationships: graph_walk, common_ground, char_evolve",
            "4. Introspection: conv_patterns, find_themes",
            "5. Context: planet_ctx (current server), universe (all planets/channels), sibling_info (other bots in the family)",
            "6. Discord Search: chan_search, user_search (humans only), msg_context, recent_msgs",
            "7. Utility: calculator (math calculations)" + (", web_search (internet search)" if settings.ENABLE_WEB_SEARCH else ""),
        ]
        
        # Add optional categories based on feature flags
        if settings.ENABLE_IMAGE_GENERATION:
            tool_categories.append("9. Creative: generate_image (create images)")
        
        tool_categories_text = "\n".join(tool_categories)
        
        # Build tool usage guide - each tool gets ONE clear description
        tool_guide_entries = [
            # Memory tools
            ("read_document", "Read the full content of an attached file. Use this when the user says 'check this out' or asks about a file."),
            ("full_memory", "Fetch the COMPLETE content of a fragmented memory. ALWAYS use this when: (1) you see [Fragment X/Y] in search results and the user asks for 'full text', 'exact words', or 'complete message', OR (2) the fragment seems cut off mid-sentence. Pass the message ID shown in parentheses."),
            ("mem_search", "Search the USER's past conversations, quotes, or things they mentioned."),
            ("old_summaries", "Search summarized conversation history for broader context."),
            ("lookup_user_facts", "Look up stored facts about the user (preferences, background, etc.)."),
            ("update_user_facts", "Store new facts learned about the user."),
            ("analyze_topic", "Deep analysis of a topic combining multiple memory sources."),
            
            # Inner life
            ("search_my_thoughts", "Search MY internal experiences: diaries, dreams, observations, gossip. Use for 'what have you been thinking about?' or 'tell me about your dreams'."),
            
            # Graph tools
            ("graph_walk", "Explore connections and relationships in the knowledge graph."),
            ("common_ground", "Find shared interests or experiences with the user."),
            ("char_evolve", "Check relationship status, trust level, or how we've grown closer."),
            
            # Introspection
            ("conv_patterns", "Analyze patterns in our conversations over time."),
            ("find_themes", "Identify recurring themes or topics we discuss."),
            
            # Context
            ("planet_ctx", "Get context about the current server/planet."),
            ("universe", "Get overview of all planets/servers in the universe."),
            ("sibling_info", "Get info about sibling bots (Dotty, Elena, Aria, etc.). Use when: user mentions another bot's name, asks 'do you know [bot]?', shares a document about a bot, or asks about your AI friends/siblings."),
            
            # Discord search
            ("chan_search", "Search recent channel messages by keyword. Use for 'what did I just say?' or 'what happened earlier?'."),
            ("user_search", "Search messages from a specific HUMAN. Use for 'what did [human name] say?'. NOT for bots - use sibling_info instead."),
            ("msg_context", "Get surrounding context for a specific message."),
            ("recent_msgs", "Get latest messages. Use for 'catch me up' or 'what's happening?'."),
            
            # Utility
            ("calculator", "Perform math calculations, unit conversions, or quantitative problems."),
        ]
        
        # Conditionally add web search to tool guide
        if settings.ENABLE_WEB_SEARCH:
            tool_guide_entries.append(
                ("web_search", "CALL THIS TOOL to search the internet when user asks for current events, recent news, live data, or facts beyond your training data. Examples: 'latest Bitcoin price', 'news about AI psychosis', 'current weather'. Use this instead of saying you cannot access the web.")
            )
        
        # Add optional tools
        if settings.ENABLE_IMAGE_GENERATION:
            tool_guide_entries.append(
                ("generate_image", "Generate an image. Use when user asks to CREATE, GENERATE, SHOW, MAKE, or DRAW an image. Include all visual details in the prompt - the tool cannot see your previous thoughts.")
            )
        
        tool_guide_text = "\n".join(f"- {name}: {desc}" for name, desc in tool_guide_entries)
        
        # Build detected intent hints (if any)
        intent_hints = []
        if "image_self" in detected_intents:
            intent_hints.append("DETECTED: User wants a self-portrait OF YOU. Call generate_image with image_type='self'.")
        if "image_refine" in detected_intents:
            intent_hints.append("DETECTED: User is refining a previous image. Call generate_image with image_type='refine'.")
        if "image_other" in detected_intents:
            intent_hints.append("DETECTED: User wants an image of something else. Call generate_image with image_type='other'. Do NOT include your appearance.")
        
        if "search" in detected_intents:
            intent_hints.append("DETECTED: User wants WEB SEARCH. Call web_search with their query immediately. Do not use memory tools or say you cannot access the web.")
        
        intent_section = ""
        if intent_hints:
            intent_section = "\n\nDETECTED INTENTS:\n" + "\n".join(f"⚡ {hint}" for hint in intent_hints)
        
        # Build special notes section
        special_notes = """
IMPORTANT NOTES:
- Voice messages and audio responses are handled AUTOMATICALLY by the system based on user request. You do NOT need to call any tool for voice/audio.
- When calling generate_image, copy ALL visual details into the prompt. The tool cannot see your reasoning.
- If image_type='other', describe the subject only - do NOT include your own appearance.
- When asked to search/explore/analyze, call the tool immediately. Don't just describe what you'll do.
- If the user shares a document, you'll see a PREVIEW. Use read_document to get full content.
- MEMORY FRAGMENTS: When search results show [Fragment X/Y], that memory was split into Y parts. If the user asks for 'full text', 'exact details', or 'complete message', you MUST call read_full_memory with the ID shown in parentheses to retrieve the complete content."""

        return f"""You are a reflective AI agent designed to answer complex questions through careful reasoning and tool use.

CHARACTER CONTEXT:
{base_system_prompt}

AVAILABLE TOOLS:
{tool_categories_text}

TOOL USAGE GUIDE:
{tool_guide_text}
{special_notes}{intent_section}
"""

    async def _execute_tool_wrapper(self, tool_call: Any, tools: List[BaseTool]) -> tuple[ToolMessage, str]:
        """
        Executes a single tool. Returns (ToolMessage, tool_name) for batched callbacks.
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

        return ToolMessage(
            content=str(observation),
            tool_call_id=tool_call_id,
            name=tool_name
        ), tool_name

    # --- Graph Nodes ---

    async def call_model(self, state: AgentState):
        messages = state['messages']
        tools = state['tools']
        callback = state['callback']
        
        # Sanitize history
        safe_messages = self._sanitize_history(messages)
        
        # Bind tools
        llm_with_tools = self.llm.bind_tools(tools)
        
        try:
            # LLM call with retry for transient errors (500s, rate limits, etc.)
            response = await invoke_with_retry(llm_with_tools.ainvoke, safe_messages, max_retries=3)
        except Exception as e:
            logger.error(f"LLM invocation failed: {e}")
            # Check for image-specific errors (animated GIF, format issues, etc.)
            image_error = get_image_error_message(e)
            if image_error:
                return {"messages": [AIMessage(content=image_error)], "steps": state['steps'] + 1}
            return {"messages": [AIMessage(content="I encountered an error while thinking.")], "steps": state['steps'] + 1}

        # Stream thought if callback exists and the model is reasoning (has content)
        # ONLY show reasoning if the model is ALSO calling tools (explaining the tool choice).
        # If there are no tool_calls, this is the final answer - don't show it in the
        # thinking/status message, as it will be streamed as the actual response.
        if isinstance(response, AIMessage) and response.content and callback:
            if response.tool_calls:
                # Log the raw content for debugging (some models include tool syntax in content)
                content_str = str(response.content)
                logger.debug(f"AIMessage with tool_calls - content preview: {content_str[:200]}...")
                # Show the reasoning that explains why the tool is being called
                await callback(f"💭 {response.content}")

        return {"messages": [response], "steps": state['steps'] + 1}

    async def execute_tools(self, state: AgentState):
        messages = state['messages']
        last_message = messages[-1]
        tools = state['tools']
        callback = state['callback']
        
        if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
            return {"messages": []}

        # Fire "searching" callback BEFORE parallel execution
        tool_names = [tc["name"] for tc in last_message.tool_calls]
        if callback and settings.REFLECTIVE_STATUS_VERBOSITY != "none":
            if len(tool_names) == 1:
                await callback(f"TOOLS:🔍 Using {tool_names[0]}...")
            else:
                await callback(f"TOOLS:🔍 Using {len(tool_names)} tools: {', '.join(tool_names)}...")

        # Execute all tools in parallel (no per-tool callbacks)
        tasks = []
        for tool_call in last_message.tool_calls:
            tasks.append(self._execute_tool_wrapper(tool_call, tools))
        
        results = await asyncio.gather(*tasks)
        
        # Unpack results
        tool_messages = [r[0] for r in results]
        executed_names = [r[1] for r in results]
        
        # Fire ONE batched callback after all tools complete
        if callback and settings.REFLECTIVE_STATUS_VERBOSITY == "detailed":
            # Detailed mode: show each tool result
            for msg, name in zip(tool_messages, executed_names):
                obs_str = str(msg.content)
                preview = (obs_str[:150] + "...") if len(obs_str) > 150 else obs_str
                await callback(f"RESULT:✅ *{name}*: {preview}")
        elif callback and settings.REFLECTIVE_STATUS_VERBOSITY == "minimal":
            # Minimal mode: just show completion summary
            await callback(f"RESULT:✅ Completed {len(executed_names)} tool(s)")
        
        return {"messages": tool_messages}

    async def critic(self, state: AgentState):
        """
        Critic Node: Inspects tool outputs and agent responses for issues.
        
        Detects:
        1. Tool failures (errors, empty results) → suggests alternatives
        2. "Promised but not delivered" → agent describes generating/creating but didn't call tool
        
        This provides 'autonomy' by allowing the agent to self-correct without hardcoded loops.
        """
        messages = state['messages']
        hints = []
        
        # Get the last AIMessage (agent's response)
        last_ai_message = None
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                last_ai_message = msg
                break
        
        # --- Check 1: "Promised but not delivered" detection ---
        # If the agent TEXT mentions generating/creating an image but didn't call the tool
        if last_ai_message and last_ai_message.content and not last_ai_message.tool_calls:
            content_lower = str(last_ai_message.content).lower()
            
            # Image generation promise patterns
            image_promise_patterns = [
                "let me generate", "i'll generate", "i will generate",
                "let me create", "i'll create", "i will create an image",
                "generating an image", "creating an image",
                "here's the image", "here is the image",
                "[generates image", "[creating image",
                "let me draw", "i'll draw", "i will draw",
                "let me visualize", "i'll visualize",
            ]
            
            has_image_promise = any(pattern in content_lower for pattern in image_promise_patterns)
            
            if has_image_promise and settings.ENABLE_IMAGE_GENERATION:
                hints.append(
                    "You described generating/creating an image but did NOT call the generate_image tool. "
                    "You MUST actually call generate_image with a detailed prompt to create the image. "
                    "Do not just describe what you would create - call the tool NOW."
                )
                logger.warning("Critic: Detected 'promised but not delivered' image generation")
            
            # Voice/audio promise patterns
            audio_promise_patterns = [
                "let me say that", "i'll speak", "sending audio",
                "here's the voice", "recording a message",
            ]
            
            has_audio_promise = any(pattern in content_lower for pattern in audio_promise_patterns)
            
            if has_audio_promise and settings.ENABLE_VOICE_RESPONSES:
                hints.append(
                    "You described sending audio but voice generation is triggered by user request, not tool calls. "
                    "If the user asked for audio, just respond naturally - voice will be synthesized automatically."
                )
        
        # --- Check 3: Fragment expansion detection ---
        # If we found a fragment but didn't expand it, and the user asked for full text
        found_fragment = False
        expanded_fragment = False
        
        # Scan tool outputs for fragments
        for msg in reversed(messages):
            if isinstance(msg, ToolMessage):
                if "[Fragment" in str(msg.content):
                    found_fragment = True
                if msg.name == "read_full_memory":
                    expanded_fragment = True
            elif isinstance(msg, HumanMessage):
                # Stop scanning at the last user message
                break
        
        if found_fragment and not expanded_fragment:
            # 1. Check if user explicitly asked for full text (Strong Signal)
            user_wants_full_text = False
            for msg in reversed(messages):
                if isinstance(msg, HumanMessage) and not str(msg.content).startswith("[SYSTEM NOTE:"):
                    user_text = str(msg.content).lower()
                    if any(p in user_text for p in ["full text", "complete message", "exact words", "whole thing", "rest of the message", "read the full"]):
                        user_wants_full_text = True
                    break
            
            # 2. Check if agent expressed uncertainty (Weak Signal)
            agent_uncertain = False
            if last_ai_message and last_ai_message.content:
                content_lower = str(last_ai_message.content).lower()
                uncertainty_phrases = [
                    "incomplete", "fragmented", "missing sections", "cut off", "truncated", 
                    "don't have the full", "fragments", "uncertain", "hitting a wall", "partial",
                    "can't see the whole", "can't read the whole", "pieces"
                ]
                if any(phrase in content_lower for phrase in uncertainty_phrases):
                    agent_uncertain = True

            if user_wants_full_text or agent_uncertain:
                hints.append(
                    "You found a memory fragment (marked [Fragment X/Y]) but did not read the full content. "
                    "The user wants the full text OR you expressed uncertainty. "
                    "You MUST call 'read_full_memory' with the ID from the fragment (e.g. ID: 12345) to retrieve the complete message."
                )

        # --- Check 2: Tool failure detection (original logic) ---
        tool_messages = []
        for msg in reversed(messages):
            if isinstance(msg, ToolMessage):
                tool_messages.append(msg)
            elif isinstance(msg, AIMessage):
                break  # Stop at the previous AI message
        
        for msg in tool_messages:
            content = str(msg.content).lower()
            # Check for common failure patterns
            if "error" in content or "not found" in content or "no results" in content or not content.strip():
                tool_name = msg.name
                
                # Strategy: Suggest alternatives based on the specific failure
                if tool_name == "mem_search":
                    hints.append(f"The search in 'mem_search' returned no results. Try using 'old_summaries' for broader context, or refine your search query to be less specific.")
                elif tool_name == "lookup_user_facts":
                    hints.append("Fact lookup failed. Try 'mem_search' to find where this might have been discussed, or 'old_summaries'.")
                elif tool_name == "old_summaries":
                    hints.append("Summary search failed. Try 'mem_search' for raw conversation logs if you need specific details.")
                elif tool_name == "generate_image":
                    hints.append("Image generation failed. Check if the prompt is appropriate and try again with a simpler description.")
                else:
                    hints.append(f"Tool '{tool_name}' returned no results. Consider trying a different tool or strategy.")
        
        if hints:
            # Combine hints into a single system note
            hint_text = " | ".join(hints)
            logger.info(f"Critic Node: Injecting self-correction hint: {hint_text}")
            # We use HumanMessage to "nudge" the model effectively
            return {"messages": [HumanMessage(content=f"[SYSTEM NOTE: {hint_text}]")]}
            
        return {"messages": []}

    def should_continue(self, state: AgentState) -> Literal["tools", "critic", "end"]:
        """
        Determine next step after agent response.
        
        Flow:
        - If tool_calls → "tools" → execute → critic → agent
        - If no tool_calls → "critic" → check for "promised but not delivered" → maybe back to agent
        - If max steps → "end"
        """
        messages = state['messages']
        last_message = messages[-1]
        
        # Soft limit check: If approaching max steps, force a conclusion
        if state['steps'] >= state['max_steps']:
            return "end"
        
        # If we are 2 steps away from the limit, inject a "wrap up" hint
        # This isn't a node transition, but we can modify the state in place if needed
        # or rely on the critic to catch it.
        # For now, we just enforce the hard limit.
        
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "tools"
            
        return "critic"

    def should_loop_after_critic(self, state: AgentState) -> Literal["agent", "end"]:
        """
        After critic runs, decide if we need to loop back to agent.
        If critic added a hint message, loop back. Otherwise, end.
        """
        messages = state['messages']
        
        # Check if the last message is a [SYSTEM NOTE:...] hint from critic
        if messages:
            last_message = messages[-1]
            if isinstance(last_message, HumanMessage):
                content = str(last_message.content)
                if content.startswith("[SYSTEM NOTE:"):
                    # Safety check: Don't loop if we're at the limit
                    if state['steps'] >= state['max_steps']:
                        return "end"
                    logger.debug("Critic injected hint, looping back to agent")
                    return "agent"
        
        return "end"

    @traceable(name="ReflectiveGraphAgent.run", run_type="chain")
    async def run(
        self, 
        user_input: str, 
        user_id: str, 
        system_prompt: str, 
        chat_history: Optional[List[BaseMessage]] = None,
        callback: Optional[Callable[[str], Awaitable[None]]] = None, 
        image_urls: Optional[List[str]] = None,
        max_steps_override: Optional[int] = None,
        guild_id: Optional[str] = None,
        channel: Optional[Any] = None,
        detected_intents: Optional[List[str]] = None,
        character_name: Optional[str] = None
    ) -> Tuple[str, List[BaseMessage]]:
        """
        Runs the ReAct loop using LangGraph.
        """
        # 1. Initialize Tools
        tools = self._get_tools(user_id, guild_id, channel, character_name)
        
        # 2. Construct System Prompt
        full_prompt = self._construct_prompt(system_prompt, detected_intents or [])
        
        # Inject few-shot examples (same as original)
        if settings.ENABLE_TRACE_LEARNING:
            try:
                bot_name = character_name or settings.DISCORD_BOT_NAME or "default"
                collection_name = f"whisperengine_memory_{bot_name}"
                traces = await trace_retriever.get_relevant_traces(
                    query=user_input,
                    user_id=user_id,
                    collection_name=collection_name
                )
                if traces:
                    few_shot_section = trace_retriever.format_few_shot_section(traces)
                    full_prompt = f"{full_prompt}\n\n{few_shot_section}"
                    if callback:
                        await callback(f"📚 Found {len(traces)} similar solved problems")
            except Exception as e:
                logger.warning(f"Failed to inject few-shot traces: {e}")

        # 3. Prepare User Message
        user_message_content: Any = user_input
        if image_urls and settings.LLM_SUPPORTS_VISION:
            user_message_content = [{"type": "text", "text": user_input}]
            provider = settings.REFLECTIVE_LLM_PROVIDER or settings.LLM_PROVIDER
            
            async with httpx.AsyncClient() as client:
                for img_url in image_urls:
                    if should_use_base64(img_url, provider):
                        try:
                            img_response = await client.get(img_url, timeout=10.0)
                            img_response.raise_for_status()
                            # Process image (handles animated GIFs by extracting first frame)
                            mime_type = img_response.headers.get("content-type", "image/png")
                            img_b64, mime_type = process_image_for_llm(img_response.content, mime_type)
                            user_message_content.append({
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime_type};base64,{img_b64}"}
                            })
                        except Exception as e:
                            logger.error(f"Failed to download/encode image {img_url}: {e}")
                            # Don't fallback to raw Discord CDN URL - it won't work for external LLMs
                            user_message_content.append({"type": "text", "text": "[An image was shared but could not be processed]"})
                    else:
                        user_message_content.append({
                            "type": "image_url",
                            "image_url": {"url": img_url}
                        })

        # 4. Build Initial Messages
        initial_messages: List[BaseMessage] = [SystemMessage(content=full_prompt)]
        
        if chat_history:
            recent_history = chat_history[-6:]
            failure_phrases = [
                "I'm not sure how to answer that",
                "I apologize, I reached my reasoning limit",
                "I'm having a bit of trouble thinking"
            ]
            filtered_history = []
            for msg in recent_history:
                if hasattr(msg, 'content') and isinstance(msg.content, str):
                    if any(phrase in msg.content for phrase in failure_phrases):
                        continue
                filtered_history.append(msg)
            initial_messages.extend(filtered_history)
            
        initial_messages.append(HumanMessage(content=user_message_content))

        # 5. Build Graph
        workflow = StateGraph(AgentState)
        
        workflow.add_node("agent", self.call_model)
        workflow.add_node("tools", self.execute_tools)
        workflow.add_node("critic", self.critic)
        
        workflow.set_entry_point("agent")
        
        workflow.add_conditional_edges(
            "agent",
            self.should_continue,
            {
                "tools": "tools",
                "critic": "critic",  # No tool calls → critic checks for "promised but not delivered"
                "end": END
            }
        )
        # Edge: Tools -> Agent (after tool execution, agent processes results)
        workflow.add_edge("tools", "agent")
        
        # Edge: Critic -> conditionally back to Agent or END
        workflow.add_conditional_edges(
            "critic",
            self.should_loop_after_critic,
            {
                "agent": "agent",  # Critic detected issue → loop back
                "end": END         # No issues → finish
            }
        )
        
        app = workflow.compile()
        
        # 6. Run Graph
        max_steps = max_steps_override or 10
        logger.info(f"Starting Reflective Mode (LangGraph) for user {user_id} (Max Steps: {max_steps})")
        
        final_state = await app.ainvoke({
            "messages": initial_messages,
            "steps": 0,
            "tools": tools,
            "callback": callback,
            "max_steps": max_steps
        })
        
        messages = final_state["messages"]
        last_message = messages[-1]
        
        if isinstance(last_message, AIMessage):
            final_content = str(last_message.content)
            # Log for debugging: detect if final response contains tool-like syntax
            if any(marker in final_content for marker in ['{"', '"}', 'search_my_thoughts', 'mem_search', 'full_memory']):
                logger.warning(f"Final AIMessage contains tool-like syntax. Has tool_calls: {bool(last_message.tool_calls)}. Preview: {final_content[:300]}...")
            return final_content, messages
        
        # Fallback if we ended on a tool message or something else
        # Try to find the last AI message in the chain
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content:
                return str(msg.content), messages
                
        return "I apologize, I reached my reasoning limit and couldn't finish.", messages
