import asyncio
import base64
import httpx
from typing import List, Optional, Callable, Awaitable, Tuple, Dict, Any
from loguru import logger
from langsmith import traceable
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, BaseMessage, AIMessage
from langchain_core.tools import BaseTool

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
from src_v2.agents.composite_tools import AnalyzeTopicTool
from src_v2.config.settings import settings
from src_v2.knowledge.document_context import has_document_context
from src_v2.memory.traces import trace_retriever

class ReflectiveAgent:
    """
    Executes a ReAct (Reasoning + Acting) loop to handle complex queries.
    Uses native LLM tool calling for reliability.
    
    Max steps are dynamically set by the caller based on complexity:
    - COMPLEX_MID: 10 steps
    - COMPLEX_HIGH: 15 steps
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
                logger.debug("Sanitizer: Skipping duplicate AIMessage")
                sanitized[-1] = msg  # Replace with newer one
            else:
                sanitized.append(msg)
        
        return sanitized

    @traceable(name="ReflectiveAgent.run", run_type="chain")
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
        Runs the ReAct loop and returns the final response and the full execution trace.
        """
        # 1. Initialize Tools
        tools = self._get_tools(user_id, guild_id, channel)
        
        # 2. Construct System Prompt with Few-Shot Traces (Phase 3.2)
        full_prompt = self._construct_prompt(system_prompt, detected_intents or [])
        
        # Inject few-shot examples from similar successful traces
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

        # 3. Prepare User Message (Text or Multimodal)
        user_message_content: Any = user_input
        
        if image_urls and settings.LLM_SUPPORTS_VISION:
            user_message_content = [{"type": "text", "text": user_input}]
            
            # Check if provider requires base64 encoding or supports direct URLs
            # Note: We use REFLECTIVE_LLM_PROVIDER if set, otherwise LLM_PROVIDER
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

        # 4. Initialize Loop
        messages: List[BaseMessage] = [SystemMessage(content=full_prompt)]
        
        # Inject Chat History
        if chat_history:
            # We only need the last few messages to resolve context
            # Reflective mode is expensive, so we limit context to last 6 messages (~3 turns)
            recent_history = chat_history[-6:]
            
            # Filter out failure responses that might create negative feedback loops
            # (LLM seeing its own failures and learning to fail again)
            failure_phrases = [
                "I'm not sure how to answer that",
                "I apologize, I reached my reasoning limit",
                "I'm having a bit of trouble thinking"
            ]
            filtered_history = []
            for msg in recent_history:
                if hasattr(msg, 'content') and isinstance(msg.content, str):
                    if any(phrase in msg.content for phrase in failure_phrases):
                        logger.debug(f"Filtered out failure message from history: {msg.content[:50]}...")
                        continue
                filtered_history.append(msg)
            
            messages.extend(filtered_history)
            
        messages.append(HumanMessage(content=user_message_content))
        
        # Bind tools to LLM
        llm_with_tools = self.llm.bind_tools(tools)
        
        steps = 0
        tools_used = 0
        
        # Max steps set by caller based on complexity (required parameter)
        if not max_steps_override:
            raise ValueError("max_steps_override is required - set by complexity level in engine.py")
        current_max_steps = max_steps_override
        
        logger.info(f"Starting Reflective Mode (Native) for user {user_id} (Max Steps: {current_max_steps})")

        empty_response_retries = 0
        max_empty_retries = 3  # Max nudge attempts before giving up

        while steps < current_max_steps:
            steps += 1
            
            # Invoke LLM
            try:
                safe_messages = self._sanitize_history(messages)
                if settings.DEBUG:
                    logger.debug(f"Sanitized message types: {[type(m).__name__ for m in safe_messages]}")
                response = await llm_with_tools.ainvoke(safe_messages)
            except Exception as e:
                # Safety Fallback: If we already have an answer (tools were used), return it
                if tools_used > 0:
                    # Find the last AIMessage with content (the proposed answer)
                    for msg in reversed(messages):
                        if isinstance(msg, AIMessage) and msg.content and not getattr(msg, 'tool_calls', None):
                            logger.warning(f"LLM failed ({e}). Falling back to last AI response.")
                            return str(msg.content), messages
                
                logger.error(f"LLM invocation failed: {e}")
                return "I encountered an error while thinking.", messages

            messages.append(response)
            
            # Handle empty responses (LLM gave up after tool execution)
            if not response.content and not response.tool_calls:
                empty_response_retries += 1
                logger.warning(f"LLM returned empty response at step {steps}. Retry {empty_response_retries}/{max_empty_retries}")
                
                # Recovery: If we just executed tools and haven't exhausted retries, nudge the LLM
                if empty_response_retries <= max_empty_retries:
                    # Remove the empty response from history
                    messages.pop()
                    
                    # Find the last tool output to reference in the nudge
                    last_tool_output = None
                    for msg in reversed(messages):
                        if isinstance(msg, ToolMessage):
                            last_tool_output = msg.content[:200] if msg.content else None
                            break
                    
                    # Add a contextual nudge message
                    if tools_used > 0 and last_tool_output:
                        nudge_content = f"You called a tool and received this output: '{last_tool_output}...'. Now provide a helpful response to the user based on this information. Do NOT return an empty response."
                    elif tools_used > 0:
                        nudge_content = "You received tool output but haven't responded. Please provide a helpful response based on the tool results."
                    elif has_document_context(user_input):
                        nudge_content = "The user shared a document with you. Please acknowledge what they shared and respond thoughtfully."
                    else:
                        nudge_content = "You returned an empty response. Please use a tool or provide a final answer to the user's question."
                    
                    # Avoid User->User sequence which crashes some providers
                    if messages and isinstance(messages[-1], HumanMessage):
                        # Create NEW message to avoid mutating shared state
                        merged = str(messages[-1].content) + f"\n\n(SYSTEM NOTE: {nudge_content})"
                        messages[-1] = HumanMessage(content=merged)
                    else:
                        messages.append(HumanMessage(content=nudge_content))
                    
                    # Don't increment steps for this retry
                    steps -= 1
                    continue
                else:
                    # Exhausted retries, fall through to the empty content handler below
                    logger.warning(f"Exhausted {max_empty_retries} recovery attempts. Giving up.")
            
            # 1. Handle Text Content (Thought or Final Answer)
            content = response.content
            if content:
                content_str = str(content)
                
                # Only stream if it's NOT the final answer (i.e., if there are tool calls)
                # If there are no tool calls, this content IS the final answer, so we shouldn't stream it to the "thinking" block.
                if response.tool_calls and callback:
                    await callback(f"💭 {content_str}")
                
                logger.debug(f"Reflective Step {steps} content: {content_str[:100]}...")

            # 2. Handle Tool Calls
            if response.tool_calls:
                # Update stats
                tools_used += len(response.tool_calls)
                
                # Create tasks for all tools to run in parallel
                tasks = []
                for tool_call in response.tool_calls:
                    tasks.append(self._execute_tool_wrapper(tool_call, tools, callback))
                
                # Execute in parallel
                # We use gather to ensure we get results in the same order as tool_calls
                # The callbacks inside _execute_tool_wrapper will still fire as they complete (streaming)
                tool_messages = await asyncio.gather(*tasks)
                
                # Append all tool outputs to history
                messages.extend(tool_messages)
                
                # Loop continues to let LLM process observations
                continue
            
            else:
                # No tool calls -> Final Answer
                # If content is empty (rare but possible with some models), try to use tool outputs
                if not content:
                    # Check if we have tool outputs we can use for a fallback response
                    if tools_used > 0:
                        logger.warning("LLM returned empty content after tool execution. Attempting fallback synthesis.")
                        # Find the last tool messages and synthesize a response
                        tool_outputs = []
                        for msg in reversed(messages):
                            if isinstance(msg, ToolMessage):
                                tool_outputs.insert(0, f"{msg.name}: {msg.content}")
                            elif isinstance(msg, AIMessage) and msg.tool_calls:
                                break  # Stop at the AI message that called the tools
                        
                        if tool_outputs:
                            # Try one more time with a direct synthesis prompt
                            synthesis_prompt = (
                                f"Based on these tool results, provide a helpful response to the user:\n\n"
                                + "\n".join(tool_outputs) +
                                "\n\nRespond naturally and helpfully. Do not call any more tools."
                            )
                            messages.append(HumanMessage(content=synthesis_prompt))
                            try:
                                # Use base LLM without tools for synthesis
                                synthesis_response = await self.llm.ainvoke(messages)
                                if synthesis_response.content:
                                    logger.info(f"Fallback synthesis successful after {steps} steps.")
                                    return str(synthesis_response.content), messages
                            except Exception as e:
                                logger.error(f"Fallback synthesis failed: {e}")
                        
                        # If synthesis also failed, return with tool context
                        return "I found some information but had trouble formulating a response. Please try asking again.", messages
                    
                    return "I'm not sure how to answer that.", messages
                
                logger.info(f"Reflective Mode finished in {steps} steps using {tools_used} tools.")
                return str(content), messages
        
        return "I apologize, I reached my reasoning limit and couldn't finish.", messages

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
            # Truncate to 200 chars for preview, but indicate if there's more
            preview = (obs_str[:200] + "...") if len(obs_str) > 200 else obs_str
            await callback(f"✅ *{tool_name}*: {preview}")

        return ToolMessage(
            content=str(observation),
            tool_call_id=tool_call_id,
            name=tool_name
        )

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
7. Utility: set_reminder (schedule a reminder for the user)
{creative_category}
TOOL USAGE RULES:
{image_rules}- set_reminder: Use when the user asks to be reminded of something at a specific time. Call set_reminder with the content and time_string.
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
