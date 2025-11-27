import asyncio
import base64
import httpx
from typing import List, Optional, Callable, Awaitable, Tuple, Dict, Any
from loguru import logger
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, BaseMessage
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
    CharacterEvolutionTool
)
from src_v2.tools.universe_tools import CheckPlanetContextTool
from src_v2.tools.insight_tools import (
    AnalyzePatternsTool,
    DetectThemesTool
)
from src_v2.tools.image_tools import GenerateImageTool
from src_v2.agents.composite_tools import AnalyzeTopicTool
from src_v2.config.settings import settings

class ReflectiveAgent:
    """
    Executes a ReAct (Reasoning + Acting) loop to handle complex queries.
    Uses native LLM tool calling for reliability.
    """
    def __init__(self):
        self.llm = create_llm(temperature=0.1, mode="reflective")
        self.max_steps = settings.REFLECTIVE_MAX_STEPS

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
        enable_verification: bool = False
    ) -> Tuple[str, List[BaseMessage]]:
        """
        Runs the ReAct loop and returns the final response and the full execution trace.
        """
        # 1. Initialize Tools
        tools = self._get_tools(user_id, guild_id)
        
        # 2. Construct System Prompt
        full_prompt = self._construct_prompt(system_prompt)

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
        messages = [SystemMessage(content=full_prompt)]
        
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
        
        # Determine max steps (override > settings)
        current_max_steps = max_steps_override or self.max_steps
        
        logger.info(f"Starting Reflective Mode (Native) for user {user_id} (Max Steps: {current_max_steps})")

        empty_response_retries = 0
        max_empty_retries = 3  # Max nudge attempts before giving up
        has_verified = False

        while steps < current_max_steps:
            steps += 1
            
            # Invoke LLM
            try:
                response = await llm_with_tools.ainvoke(messages)
            except Exception as e:
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
                    
                    # Add a nudge message
                    nudge_content = "You returned an empty response. Please use a tool (like discover_common_ground) or provide a final answer."
                    if tools_used > 0:
                        nudge_content = "You received tool output but haven't completed the user's request. Continue with your task - if they asked for an image, call generate_image now."
                        
                    nudge = SystemMessage(content=nudge_content)
                    messages.append(nudge)
                    
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
                # If content is empty (rare but possible with some models), return a fallback
                if not content:
                    return "I'm not sure how to answer that.", messages
                
                # --- SELF-CORRECTION LOGIC ---
                if enable_verification and not has_verified:
                    logger.info("Triggering Self-Correction/Critic Step")
                    if callback:
                        await callback("🤔 Reviewing answer for accuracy...")
                    
                    has_verified = True
                    
                    critic_prompt = (
                        "CRITIC STEP: Review your last response above. "
                        "Does it fully answer the user's request based on the tool outputs? "
                        "Are there any hallucinations? "
                        "If it is correct, respond with exactly: 'VERIFIED'. "
                        "If it needs work, respond with: 'CORRECTION NEEDED: <explanation>' "
                        "and then use tools or provide a corrected answer."
                    )
                    messages.append(SystemMessage(content=critic_prompt))
                    continue

                if enable_verification and "VERIFIED" in str(content):
                    # The PREVIOUS message was the actual answer.
                    # History: [..., ProposedAnswer, CriticPrompt, "VERIFIED"]
                    if len(messages) >= 3:
                        final_answer_msg = messages[-3]
                        logger.info(f"Reflective Mode verified in {steps} steps.")
                        return str(final_answer_msg.content), messages
                
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
            preview = (obs_str[:100] + "...") if len(obs_str) > 100 else obs_str
            await callback(f"✅ *{tool_name}*: {preview}")

        return ToolMessage(
            content=str(observation),
            tool_call_id=tool_call_id,
            name=tool_name
        )

    def _get_tools(self, user_id: str, guild_id: Optional[str] = None) -> List[BaseTool]:
        character_name = settings.DISCORD_BOT_NAME or "default"
        tools = [
            # Memory & Knowledge Tools
            SearchSummariesTool(user_id=user_id),
            SearchEpisodesTool(user_id=user_id),
            LookupFactsTool(user_id=user_id, bot_name=character_name),
            UpdateFactsTool(user_id=user_id),
            UpdatePreferencesTool(user_id=user_id, character_name=character_name),
            AnalyzeTopicTool(user_id=user_id, bot_name=character_name),
            
            # Graph & Relationship Tools
            ExploreGraphTool(user_id=user_id, bot_name=character_name),
            DiscoverCommonGroundTool(user_id=user_id, bot_name=character_name),
            CharacterEvolutionTool(user_id=user_id, character_name=character_name),
            
            # Introspection & Pattern Tools
            AnalyzePatternsTool(user_id=user_id, bot_name=character_name),
            DetectThemesTool(user_id=user_id, bot_name=character_name),
            
            # Context Tools
            CheckPlanetContextTool(guild_id=guild_id),
        ]
        
        # Conditionally add image generation tool
        if settings.ENABLE_IMAGE_GENERATION:
            tools.append(GenerateImageTool(character_name=character_name, user_id=user_id))
        
        return tools

    def _construct_prompt(self, base_system_prompt: str) -> str:
        # Dynamic sections based on feature flags
        creative_category = ""
        image_rules = ""
        
        if settings.ENABLE_IMAGE_GENERATION:
            creative_category = "5. Creative: generate_image\n"
            image_rules = """- If the user asks you to CREATE, GENERATE, SHOW, or MAKE an image, you MUST call the generate_image tool.
- Gathering information is NOT the same as generating an image.
- After gathering context, if the task requires an image, call generate_image with a detailed prompt.
"""

        return f"""You are a reflective AI agent designed to answer complex questions deeply.
You have access to tools to recall memories, facts, summaries, explore your knowledge graph, discover common ground, check your relationship status, analyze conversation patterns, and generate images.
Use these tools to gather information or create visual content before answering.
Think step-by-step.

AVAILABLE TOOL CATEGORIES:
1. Memory & Knowledge: search_archived_summaries, search_specific_memories, lookup_user_facts, update_user_facts, analyze_topic
2. Graph & Relationships: explore_knowledge_graph, discover_common_ground, get_character_evolution
3. Introspection: analyze_conversation_patterns, detect_recurring_themes
4. Context: check_planet_context
{creative_category}
IMPORTANT RULES:
{image_rules}- If the user asks about connections, relationships, what's connected, or to explore the network/graph, use the explore_knowledge_graph tool.
- If the user asks what you have in common, shared interests, or you want to find connection points, use the discover_common_ground tool.
- If the user asks about your relationship, trust level, or how close you are, use get_character_evolution.
- If the user asks about patterns, themes, or what topics come up often, use analyze_conversation_patterns or detect_recurring_themes.
- Do NOT give a final answer until you have completed all requested actions.
- When asked to search or explore, USE THE TOOLS - don't just describe what you would do.

CHARACTER CONTEXT:
{base_system_prompt}
"""
