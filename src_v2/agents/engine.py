from typing import List, Dict, Any, Optional, Callable, Awaitable
import json
import datetime
import time
import base64
import httpx
from pathlib import Path
import aiofiles
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from loguru import logger

from src_v2.config.settings import settings
from src_v2.config.constants import TRAIT_BEHAVIORS, get_image_format_for_provider
from src_v2.core.character import Character
from src_v2.agents.llm_factory import create_llm
from src_v2.agents.router import CognitiveRouter
from src_v2.agents.classifier import ComplexityClassifier
from src_v2.agents.reflective import ReflectiveAgent
from src_v2.evolution.trust import trust_manager
from src_v2.evolution.feedback import feedback_analyzer
from src_v2.evolution.goals import goal_manager
from src_v2.knowledge.manager import knowledge_manager
from src_v2.utils.validation import ValidationError, validator
from src_v2.evolution.manager import get_evolution_manager

class AgentEngine:
    """Core cognitive engine for generating AI responses with memory and evolution."""
    
    def __init__(
        self, 
        trust_manager_dep: Optional[Any] = None, 
        feedback_analyzer_dep: Optional[Any] = None, 
        goal_manager_dep: Optional[Any] = None,
        llm_client_dep: Optional[Any] = None
    ) -> None:
        """Initialize the AgentEngine with dependencies.
        
        Args:
            trust_manager_dep: Optional trust manager for dependency injection
            feedback_analyzer_dep: Optional feedback analyzer for dependency injection
            goal_manager_dep: Optional goal manager for dependency injection
            llm_client_dep: Optional LLM client for dependency injection
        """
        self.llm: Any = llm_client_dep or create_llm()
        self.router: CognitiveRouter = CognitiveRouter()
        self.classifier: ComplexityClassifier = ComplexityClassifier()
        self.reflective_agent: ReflectiveAgent = ReflectiveAgent()
        
        # Dependency Injection or Default to Global Instances
        self.trust_manager: Any = trust_manager_dep or trust_manager
        self.feedback_analyzer: Any = feedback_analyzer_dep or feedback_analyzer
        self.goal_manager: Any = goal_manager_dep or goal_manager
        
        # Pre-create log directory to avoid blocking during runtime
        self.log_dir: Path = Path("logs/prompts")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("AgentEngine initialized")

    async def generate_response(
        self, 
        character: Character, 
        user_message: str, 
        chat_history: Optional[List[BaseMessage]] = None,
        context_variables: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        image_urls: Optional[List[str]] = None,
        callback: Optional[Callable[[str], Awaitable[None]]] = None,
        force_reflective: bool = False
    ) -> str:
        """
        Generates a response for the given character and user message.
        """
        start_time = time.time()
        chat_history = chat_history or []
        context_variables = context_variables or {}
        
        # Defensive validation (engine-level, more lenient than Discord)
        # This catches issues from non-Discord entry points (API, tests, etc.)
        try:
            validator.validate_for_engine(user_message, image_urls)
        except ValidationError as e:
            logger.warning(f"Engine validation failed: {e.message}")
            return e.user_message
        
        # Validate and filter image URLs
        if image_urls:
            image_urls, _ = validator.validate_image_urls(image_urls)
            if not image_urls:
                image_urls = None
        
        # 1. Classify Intent (Simple vs Complex)
        classify_start = time.time()
        is_complex = await self._classify_complexity(user_message, chat_history, user_id, force_reflective)
        logger.debug(f"Complexity classification took {time.time() - classify_start:.2f}s")

        # 2. Construct System Prompt (Character + Evolution + Goals + Knowledge)
        context_start = time.time()
        system_content = await self._build_system_context(character, user_message, user_id, context_variables)
        logger.debug(f"Context building took {time.time() - context_start:.2f}s")

        # 3. Branching Logic: Reflective Mode
        if is_complex and user_id and settings.ENABLE_REFLECTIVE_MODE:
            response = await self._run_reflective_mode(
                character, user_message, user_id, system_content, 
                chat_history, context_variables, image_urls, callback
            )
            logger.info(f"Total response time: {time.time() - start_time:.2f}s (Reflective Mode)")
            return response
        
        # 4. Fast Mode (Standard Flow)
        
        # 4.1 Cognitive Routing (The "Brain")
        routing_start = time.time()
        await self._run_cognitive_routing(user_id, user_message, chat_history, context_variables)
        logger.debug(f"Cognitive routing took {time.time() - routing_start:.2f}s")
        
        # Inject memory context if it exists
        if context_variables.get("memory_context"):
            system_content += f"\n\n[RELEVANT MEMORY & KNOWLEDGE]\n{context_variables['memory_context']}\n"
            system_content += "(Use this information naturally. Do not explicitly state 'I see in my memory' or 'According to the database'. Treat this as your own knowledge.)\n"

        # 5. Create Prompt Template
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_content),
            MessagesPlaceholder(variable_name="chat_history"),
            MessagesPlaceholder(variable_name="user_input_message")
        ])

        # 6. Create Chain
        chain = prompt | self.llm

        # 7. Execute
        try:
            # Prepare input content (Text or Multimodal)
            user_input_message = await self._prepare_input_content(user_message, image_urls)

            # Prepare inputs
            inputs = {
                "chat_history": chat_history,
                "user_input_message": user_input_message,
                **context_variables
            }
            
            # Fill missing variables
            for var in prompt.input_variables:
                if var not in inputs:
                    inputs[var] = ""
            
            llm_start = time.time()
            response = await chain.ainvoke(inputs)
            logger.debug(f"LLM invocation took {time.time() - llm_start:.2f}s")
            
            # 8. Log Prompt (if enabled)
            if settings.ENABLE_PROMPT_LOGGING:
                await self._log_prompt(
                    character_name=character.name,
                    user_id=user_id or "unknown",
                    system_prompt=system_content,
                    chat_history=chat_history,
                    user_input=user_message,
                    context_variables=context_variables,
                    response=str(response.content),
                    image_urls=image_urls
                )
            
            total_time = time.time() - start_time
            logger.info(f"Total response time: {total_time:.2f}s (Fast Mode)")
            return str(response.content)
            
        except Exception as e:
            error_type = type(e).__name__
            logger.exception(f"Error generating response ({error_type}): {e}")
            
            # Provide context-specific fallback messages
            if "rate" in str(e).lower() or "quota" in str(e).lower():
                return "I'm experiencing high demand right now. Please try again in a moment."
            elif "context" in str(e).lower() or "token" in str(e).lower():
                return "That's quite a lot to process at once. Could you break that down into smaller parts?"
            elif "timeout" in str(e).lower() or "connection" in str(e).lower():
                return "I'm having connection issues right now. Please try again."
            else:
                return "I'm having a bit of trouble thinking right now. Could you try rephrasing that?"

    async def _classify_complexity(self, user_message: str, chat_history: List[BaseMessage], user_id: Optional[str], force_reflective: bool) -> bool:
        """Determines if the query requires complex reasoning."""
        if not (user_id and settings.ENABLE_REFLECTIVE_MODE):
            return False
            
        if force_reflective:
            logger.info("Complexity Analysis: FORCED COMPLEX by user")
            return True
            
        try:
            is_complex_str = await self.classifier.classify(user_message, chat_history)
            is_complex = (is_complex_str == "COMPLEX")
            logger.info(f"Complexity Analysis: {is_complex_str}")
            return is_complex
        except Exception as e:
            logger.error(f"Complexity classifier failed: {e}")
            return False

    async def _build_system_context(self, character: Character, user_message: str, user_id: Optional[str], context_variables: Dict[str, Any]) -> str:
        """Constructs the full system prompt including evolution, goals, and knowledge."""
        system_content = character.system_prompt
        
        # 2.1 Inject Past Summaries
        if context_variables.get("past_summaries"):
            system_content += f"\n\n[RELEVANT PAST CONVERSATIONS]\n{context_variables['past_summaries']}\n(Use this context to maintain continuity, but don't explicitly mention 'I read a summary'.)\n"

        if not user_id:
            return system_content

        try:
            # 2.5 Inject Dynamic Persona (Trust & Evolution)
            relationship = await self.trust_manager.get_relationship_level(user_id, character.name)
            if relationship:
                current_mood = await self.feedback_analyzer.get_current_mood(user_id)
                system_content += self._format_relationship_context(relationship, current_mood, character.name)
                logger.debug(f"Injected evolution state: {relationship['level']} (Trust: {relationship['trust_score']})")

            # 2.5.1 Inject Feedback Insights
            feedback_insights = await self.feedback_analyzer.analyze_user_feedback_patterns(user_id)
            if feedback_insights.get("recommendations"):
                feedback_context = "\n\n[USER PREFERENCES (Derived from Feedback)]\n"
                for rec in feedback_insights["recommendations"]:
                    feedback_context += f"- {rec}\n"
                system_content += feedback_context
                logger.debug(f"Injected feedback insights: {feedback_insights['recommendations']}")
            
            # 2.6 Inject Active Goals
            active_goals = await self.goal_manager.get_active_goals(user_id, character.name)
            if active_goals:
                top_goal = active_goals[0]
                goal_context = f"\n\n[CURRENT GOAL: {top_goal['slug']}]\n"
                goal_context += f"Objective: {top_goal['description']}\n"
                goal_context += f"Success Criteria: {top_goal['success_criteria']}\n"
                goal_context += "(Try to naturally steer the conversation towards this goal without being pushy.)\n"
                system_content += goal_context
                logger.debug(f"Injected goal: {top_goal['slug']}")

            # 2.7 Inject Knowledge Graph Context
            knowledge_context = await self._get_knowledge_context(user_id, character.name, user_message)
            system_content += knowledge_context

        except Exception as e:
            logger.error(f"Failed to inject evolution/goal state: {e}")

        return system_content

    def _format_relationship_context(self, relationship: Dict[str, Any], current_mood: str, character_name: str) -> str:
        """Formats the relationship/trust context string.
        
        Args:
            relationship: Dictionary containing trust level, traits, insights, and preferences
            current_mood: Current mood state of the user
            character_name: Name of the character
            
        Returns:
            Formatted context string for system prompt injection
        """
        trust_score = relationship.get('trust_score', 0)
        
        # Use EvolutionManager to build context
        evo_manager = get_evolution_manager(character_name)
        
        # current_mood represents USER's sentiment toward the bot (based on recent reactions)
        # NOT the bot's mood. Used to suppress traits (e.g., don't tease if user is frustrated)
        # FeedbackAnalyzer.get_current_mood() returns: "Happy", "Neutral", "Annoyed", "Excited"
        user_sentiment = "neutral"
        if "Annoyed" in current_mood: user_sentiment = "angry"
        elif "Happy" in current_mood or "Excited" in current_mood: user_sentiment = "happy"
        
        context = evo_manager.build_evolution_context(trust_score, user_sentiment)
        
        # Append Insights and Preferences (which are still in relationship dict)
        if relationship.get('insights'):
            context += "\n[USER INSIGHTS]\n"
            for insight in relationship['insights']:
                context += f"- {insight}\n"
            context += "(These are deep psychological observations about the user. Use them to empathize and connect.)\n"

        if relationship.get('preferences'):
            context += "\n[USER CONFIGURATION]\n"
            prefs = relationship['preferences']
            
            if 'verbosity' in prefs:
                v = prefs['verbosity']
                if v == 'short': context += "- RESPONSE LENGTH: Keep responses very concise (1-2 sentences max).\n"
                elif v == 'medium': context += "- RESPONSE LENGTH: Keep responses moderate (2-4 sentences).\n"
                elif v == 'long': context += "- RESPONSE LENGTH: You may provide detailed, comprehensive responses.\n"
                elif v == 'dynamic': context += "- RESPONSE LENGTH: Adjust length based on context and user's input length.\n"
                else: context += f"- verbosity: {v}\n"
            
            if 'style' in prefs:
                s = prefs['style']
                if s == 'casual': context += "- TONE: Use casual, relaxed language. Slang is okay if fits character.\n"
                elif s == 'formal': context += "- TONE: Maintain a formal, polite, and professional tone.\n"
                elif s == 'matching': context += "- TONE: Mirror the user's energy and formality level.\n"
                else: context += f"- style: {s}\n"

        return context

    async def _get_knowledge_context(self, user_id: str, char_name: str, user_message: str) -> str:
        """Retrieves Common Ground and Background Relevance from Knowledge Graph.
        
        Args:
            user_id: Discord user ID
            char_name: Character name
            user_message: User's current message
            
        Returns:
            Formatted knowledge context string
        """
        context: str = ""
        try:
            common_ground = await knowledge_manager.find_common_ground(user_id, char_name)
            if common_ground:
                context += f"\n[COMMON GROUND]\n{common_ground}\n(You share these things with the user. Feel free to reference them naturally.)\n"
            
            relevant_bg = await knowledge_manager.search_bot_background(char_name, user_message)
            if relevant_bg:
                context += f"\n[RELEVANT BACKGROUND]\n{relevant_bg}\n(The user mentioned something related to your background. You can bring this up.)\n"
        except Exception as e:
            logger.error(f"Failed to inject knowledge context: {e}")
        return context

    async def _run_reflective_mode(
        self, 
        character: Character, 
        user_message: str, 
        user_id: str, 
        system_content: str, 
        chat_history: List[BaseMessage], 
        context_variables: Dict[str, Any], 
        image_urls: Optional[List[str]], 
        callback: Optional[Callable[[str], Awaitable[None]]]
    ) -> str:
        """Runs the reflective reasoning mode for complex queries.
        
        Args:
            character: Character instance
            user_message: User's message
            user_id: Discord user ID
            system_content: System prompt content
            chat_history: Conversation history
            context_variables: Additional context data
            image_urls: Optional list of image URLs
            callback: Optional callback for streaming responses
            
        Returns:
            Generated response text
        """
        logger.info("Engaging Reflective Mode")
        response_text: str
        trace: List[BaseMessage]
        response_text, trace = await self.reflective_agent.run(
            user_message, 
            user_id, 
            system_content, 
            callback=callback,
            image_urls=image_urls
        )
        
        if settings.ENABLE_PROMPT_LOGGING:
            await self._log_prompt(
                character_name=character.name,
                user_id=user_id,
                system_prompt=system_content,
                chat_history=chat_history,
                user_input=user_message,
                context_variables=context_variables,
                response=response_text,
                image_urls=image_urls,
                trace=trace
            )
        return response_text

    async def _run_cognitive_routing(
        self, 
        user_id: Optional[str], 
        user_message: str, 
        chat_history: List[BaseMessage], 
        context_variables: Dict[str, Any]
    ) -> None:
        """Runs cognitive routing to retrieve relevant memory context.
        
        Args:
            user_id: Optional Discord user ID
            user_message: User's message
            chat_history: Conversation history
            context_variables: Context dict to update with memory (modified in-place)
        """
        # Create a copy to avoid race conditions with shared context_variables
        if user_id and not context_variables.get("memory_context"):
            try:
                router_result: Dict[str, Any] = await self.router.route_and_retrieve(user_id, user_message, chat_history)
                memory_context: str = router_result.get("context", "")
                reasoning: str = router_result.get("reasoning", "")
                
                if memory_context:
                    logger.info(f"Injecting memory context. Reasoning: {reasoning}")
                    # Atomic update to avoid race conditions
                    context_variables["memory_context"] = memory_context
                    context_variables["router_reasoning"] = reasoning
                else:
                    logger.debug(f"No memory context retrieved. Reasoning: {reasoning}")
            except Exception as e:
                logger.error(f"Cognitive Router failed: {e}")

    async def _prepare_input_content(self, user_message: str, image_urls: Optional[List[str]]) -> List[BaseMessage]:
        """Prepares the input message, handling text and optional images."""
        if image_urls and settings.LLM_SUPPORTS_VISION:
            # Type: Union[str, List[Union[str, Dict]]] for multimodal content
            input_content: List[Dict[str, Any]] = [{"type": "text", "text": user_message}]
            
            # Check if provider requires base64 encoding or supports direct URLs
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
                            
                            input_content.append({
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime_type};base64,{img_b64}"}
                            })
                            logger.debug(f"Encoded image to base64 for {settings.LLM_PROVIDER}")
                        except Exception as e:
                            logger.error(f"Failed to download/encode image {img_url}: {e}")
                            # Fallback to URL anyway
                            input_content.append({
                                "type": "image_url",
                                "image_url": {"url": img_url}
                            })
            else:
                # Use URLs directly for providers that support it (OpenAI, Anthropic, etc.)
                for img_url in image_urls:
                    input_content.append({
                        "type": "image_url",
                        "image_url": {"url": img_url}
                    })
                logger.debug(f"Using direct image URLs for {settings.LLM_PROVIDER}")
            
            # type: ignore - LangChain accepts this multimodal format at runtime
            return [HumanMessage(content=input_content)]  # type: ignore[arg-type]
        else:
            return [HumanMessage(content=user_message)]

    async def _log_prompt(
        self,
        character_name: str,
        user_id: str,
        system_prompt: str,
        chat_history: List[BaseMessage],
        user_input: str,
        context_variables: Dict[str, Any],
        response: str,
        image_urls: Optional[List[str]] = None,
        trace: Optional[List[BaseMessage]] = None
    ):
        """
        Logs the full prompt context and response to a JSON file.
        """
        try:
            # Use pre-created log directory (non-blocking)
            # Generate filename: {BotName}_{YYYYMMDD}_{HHMMSS}_{UserID}.json
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{character_name}_{timestamp}_{user_id}.json"
            file_path = self.log_dir / filename
            
            # Serialize chat history
            history_serialized = []
            for msg in chat_history:
                role = "unknown"
                if isinstance(msg, HumanMessage): role = "human"
                elif isinstance(msg, AIMessage): role = "ai"
                elif isinstance(msg, SystemMessage): role = "system"
                
                history_serialized.append({
                    "role": role,
                    "content": msg.content
                })
            
            # Serialize trace if present
            trace_serialized = []
            if trace:
                for msg in trace:
                    role = "unknown"
                    content = msg.content
                    tool_calls = []
                    
                    if isinstance(msg, HumanMessage): role = "human"
                    elif isinstance(msg, AIMessage): 
                        role = "ai"
                        if hasattr(msg, 'tool_calls') and msg.tool_calls:
                            tool_calls = [
                                {"name": tc.get("name"), "args": tc.get("args"), "id": tc.get("id")} 
                                for tc in msg.tool_calls
                            ]
                    elif isinstance(msg, SystemMessage): role = "system"
                    elif isinstance(msg, ToolMessage): 
                        role = "tool"
                        # ToolMessage usually has 'name' or 'tool_call_id'
                        tool_calls = [{"tool_call_id": msg.tool_call_id, "name": msg.name}]

                    trace_serialized.append({
                        "role": role,
                        "content": content,
                        "tool_calls": tool_calls if tool_calls else None
                    })

            # Construct log data
            log_data = {
                "timestamp": datetime.datetime.now().isoformat(),
                "character": character_name,
                "user_id": user_id,
                "inputs": {
                    "system_prompt": system_prompt,
                    "context_variables": context_variables,
                    "chat_history": history_serialized,
                    "user_input": user_input,
                    "image_urls": image_urls
                },
                "response": response,
                "trace": trace_serialized if trace_serialized else None
            }
            
            # Write to file
            async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
                await f.write(json.dumps(log_data, indent=2, ensure_ascii=False))
                
            logger.debug(f"Prompt logged to {file_path}")
            
        except Exception as e:
            logger.warning(f"Failed to log prompt: {e}")
