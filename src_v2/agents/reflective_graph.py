import asyncio
import base64
import httpx
import operator
from typing import List, Optional, Callable, Awaitable, Tuple, Dict, Any, TypedDict, Annotated, Union, Literal
from loguru import logger
from langsmith import traceable
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, BaseMessage, AIMessage
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, END

from src_v2.agents.llm_factory import create_llm
from src_v2.config.constants import get_image_format_for_provider
from src_v2.tools.memory_tools import (
    SearchSummariesTool, 
    SearchEpisodesTool, 
    LookupFactsTool, 
    UpdateFactsTool, 
    UpdatePreferencesTool,
    ExploreGraphTool,
    DiscoverCommonGroundTool,
    CharacterEvolutionTool,
    SearchMyThoughtsTool,
    CreateUserGoalTool
)
from src_v2.tools.universe_tools import CheckPlanetContextTool, GetUniverseOverviewTool
from src_v2.tools.discord_tools import SearchChannelMessagesTool, SearchUserMessagesTool, GetMessageContextTool, GetRecentMessagesTool
from src_v2.tools.insight_tools import (
    AnalyzePatternsTool,
    DetectThemesTool,
    DiscoverCommunityInsightsTool
)
from src_v2.tools.image_tools import GenerateImageTool
from src_v2.tools.reminder_tools import SetReminderTool
from src_v2.tools.math_tools import CalculatorTool
from src_v2.agents.composite_tools import AnalyzeTopicTool
from src_v2.config.settings import settings
from src_v2.knowledge.document_context import has_document_context
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

    def _get_tools(self, user_id: str, guild_id: Optional[str] = None, channel: Optional[Any] = None) -> List[BaseTool]:
        character_name = settings.DISCORD_BOT_NAME or "default"
        tools = [
            # Memory & Knowledge Tools
            SearchSummariesTool(user_id=user_id),
            SearchEpisodesTool(user_id=user_id),
            LookupFactsTool(user_id=user_id, bot_name=character_name),
            UpdateFactsTool(user_id=user_id),
            UpdatePreferencesTool(user_id=user_id, character_name=character_name),
            AnalyzeTopicTool(user_id=user_id, bot_name=character_name),
            
            # Bot's Internal Experiences (diaries, dreams, observations, gossip)
            SearchMyThoughtsTool(character_name=character_name),
            
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
            
            # Math Tool
            CalculatorTool(),
        ]
        
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
        
        # Conditionally add reminder tool (Phase E5)
        if settings.ENABLE_REMINDERS and channel:
            channel_id = str(channel.id) if hasattr(channel, 'id') else None
            if channel_id:
                tools.append(SetReminderTool(
                    user_id=user_id,
                    channel_id=channel_id,
                    character_name=character_name
                ))
        
        return tools

    def _construct_prompt(self, base_system_prompt: str, detected_intents: Optional[List[str]] = None) -> str:
        # Dynamic sections based on feature flags
        creative_category = ""
        image_rules = ""
        
        if settings.ENABLE_IMAGE_GENERATION:
            creative_category = "6. Creative: generate_image\n"
            
            # Build image type hint based on detected intents
            image_type_hint = ""
            if detected_intents:
                if "image_self" in detected_intents:
                    image_type_hint = "- DETECTED INTENT: image_self - User wants a self-portrait OF YOU. You MUST call generate_image with image_type='self'.\n"
                elif "image_refine" in detected_intents:
                    image_type_hint = "- DETECTED INTENT: image_refine - User is tweaking/refining a previous image. You MUST call generate_image with image_type='refine' and include the user's modification request in your prompt.\n"
                elif "image_other" in detected_intents:
                    image_type_hint = "- DETECTED INTENT: image_other - User wants an image of something else (not you). You MUST call generate_image with image_type='other'. DO NOT describe yourself in the prompt.\n"
            
            image_rules = f"""- If the user asks you to CREATE, GENERATE, SHOW, MAKE, CHANGE, MODIFY, or REFINE an image, you MUST call the generate_image tool.
- If a detected intent starts with "image_", you MUST call generate_image. Do not just describe what you would create - actually call the tool.
- Gathering information is NOT the same as generating an image.
- After gathering context, if the task requires an image, call generate_image with a detailed prompt.
- CRITICAL: The generate_image tool does NOT have access to your internal thoughts or previous reasoning steps. You MUST copy all relevant visual details from your thoughts into the 'prompt' argument. Do not use vague prompts like "what I described" or "the scene above".
- Set image_type correctly: 'self' for self-portraits of YOU, 'refine' for tweaking previous images, 'other' for everything else.
- CRITICAL: If image_type='other', do NOT include your own physical description in the prompt. Describe the subject (user, object, scene) only.
{image_type_hint}"""

        return f"""You are a reflective AI agent designed to answer complex questions deeply.
You have access to tools to recall memories, facts, summaries, explore your knowledge graph, discover common ground, check your relationship status, analyze conversation patterns, search recent channel messages, and generate images.

CRITICAL: When asked to search, explore, analyze, or look up information, you MUST call the appropriate tool IMMEDIATELY in your response. Do not describe what you will do - just do it by including the tool call.

CHARACTER CONTEXT:
{base_system_prompt}

AVAILABLE TOOL CATEGORIES:
1. Memory & Knowledge: search_archived_summaries, search_specific_memories, lookup_user_facts, update_user_facts, analyze_topic
2. My Inner Life: search_my_thoughts (my diaries, dreams, observations, gossip, epiphanies)
3. Graph & Relationships: explore_knowledge_graph, discover_common_ground, get_character_evolution
4. Introspection: analyze_conversation_patterns, detect_recurring_themes
5. Context: check_planet_context (current server), get_universe_overview (all planets/channels)
6. Discord Search: search_channel_messages (keyword search), search_user_messages (specific person), get_message_context (context around a message), get_recent_messages (latest messages)
7. Utility: set_reminder (schedule a reminder for the user), calculator (perform math calculations)
{creative_category}
TOOL USAGE RULES:
{image_rules}- set_reminder: Use when the user asks to be reminded of something at a specific time. Call set_reminder with the content and time_string.
- calculator: Use when the user asks for a math calculation, unit conversion, or any quantitative problem.
- search_my_thoughts: Use when asked about MY dreams, MY diary, MY journal, MY observations, or what I've been thinking about. This searches MY internal experiences, not the user's memories.
- search_specific_memories: Use for the USER's past conversations, quotes, or details they mentioned. NOT for my internal experiences.
- search_channel_messages: Use when asked "what did I just say?", "what happened earlier?", or to find recent messages by keyword.
- search_user_messages: Use when asked "what did [name] say?" or to find messages from a specific person.
- get_message_context: Use when a reply references an older message and you need surrounding context.
- get_recent_messages: Use for "catch me up", "what's happening?", or general channel awareness.
- explore_knowledge_graph: Use when asked about connections, relationships, network, or graph exploration.
- discover_common_ground: Use when asked about shared interests or common ground.
- get_character_evolution: Use when asked about your relationship, trust level, or closeness.
- analyze_conversation_patterns / detect_recurring_themes: Use for patterns, themes, or frequent topics.
- get_universe_overview: Use for questions about 'all planets', 'everywhere', or 'the universe'.

DOCUMENT HANDLING:
- If the user shares a document, you'll see a PREVIEW in their message.
- Use search_specific_memories to retrieve full document content if needed.
"""

    async def _execute_tool_wrapper(self, tool_call: Any, tools: List[BaseTool], callback: Optional[Callable[[str], Awaitable[None]]]) -> ToolMessage:
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
            # Truncate to 200 chars for preview, but indicate if there's more
            preview = (obs_str[:200] + "...") if len(obs_str) > 200 else obs_str
            await callback(f"✅ *{tool_name}*: {preview}")

        return ToolMessage(
            content=str(observation),
            tool_call_id=tool_call_id,
            name=tool_name
        )

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
            response = await llm_with_tools.ainvoke(safe_messages)
        except Exception as e:
            logger.error(f"LLM invocation failed: {e}")
            return {"messages": [AIMessage(content="I encountered an error while thinking.")], "steps": state['steps'] + 1}

        # Stream thought if callback exists and it's not a tool call
        if isinstance(response, AIMessage) and response.content and callback and response.tool_calls:
            await callback(f"💭 {response.content}")

        return {"messages": [response], "steps": state['steps'] + 1}

    async def execute_tools(self, state: AgentState):
        messages = state['messages']
        last_message = messages[-1]
        tools = state['tools']
        callback = state['callback']
        
        if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
            return {"messages": []}

        tasks = []
        for tool_call in last_message.tool_calls:
            # tool_call is a dict in newer langchain versions (ToolCall TypedDict)
            tasks.append(self._execute_tool_wrapper(tool_call, tools, callback))
        
        tool_messages = await asyncio.gather(*tasks)
        
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
                if tool_name == "search_specific_memories":
                    hints.append(f"The search in 'search_specific_memories' returned no results. Try using 'search_summaries' for broader context, or refine your search query to be less specific.")
                elif tool_name == "lookup_user_facts":
                    hints.append("Fact lookup failed. Try 'search_specific_memories' to find where this might have been discussed, or 'search_summaries'.")
                elif tool_name == "search_summaries":
                    hints.append("Summary search failed. Try 'search_episodes' for raw conversation logs if you need specific details.")
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
        
        if state['steps'] >= state['max_steps']:
            return "end"
        
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "tools"
        
        # No tool calls - still go through critic to check for "promised but not delivered"
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
        detected_intents: Optional[List[str]] = None
    ) -> Tuple[str, List[BaseMessage]]:
        """
        Runs the ReAct loop using LangGraph.
        """
        # 1. Initialize Tools
        tools = self._get_tools(user_id, guild_id, channel)
        
        # 2. Construct System Prompt
        full_prompt = self._construct_prompt(system_prompt, detected_intents or [])
        
        # Inject few-shot examples (same as original)
        if settings.ENABLE_TRACE_LEARNING:
            try:
                collection_name = f"whisperengine_memory_{settings.DISCORD_BOT_NAME or 'default'}"
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
            image_format = get_image_format_for_provider(provider)
            
            if image_format == "base64":
                async with httpx.AsyncClient() as client:
                    for img_url in image_urls:
                        try:
                            img_response = await client.get(img_url, timeout=10.0)
                            img_response.raise_for_status()
                            img_b64 = base64.b64encode(img_response.content).decode('utf-8')
                            mime_type = img_response.headers.get("content-type", "image/png")
                            user_message_content.append({
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime_type};base64,{img_b64}"}
                            })
                        except Exception as e:
                            logger.error(f"Failed to download/encode image {img_url}: {e}")
                            user_message_content.append({
                                "type": "image_url",
                                "image_url": {"url": img_url}
                            })
            else:
                for img_url in image_urls:
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
        # Edge: Tools -> Critic (after tool execution)
        workflow.add_edge("tools", "critic")
        
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
            return str(last_message.content), messages
        
        return "I apologize, I reached my reasoning limit and couldn't finish.", messages
