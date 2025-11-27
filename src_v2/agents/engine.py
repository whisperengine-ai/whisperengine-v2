from typing import List, Dict, Any, Optional, Callable, Awaitable, Literal
import json
import datetime
import time
import base64
import random
import httpx
from pathlib import Path
import aiofiles
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from loguru import logger
from influxdb_client import Point

from src_v2.config.settings import settings
from src_v2.core.database import db_manager
from src_v2.config.constants import get_image_format_for_provider
from src_v2.core.character import Character
from src_v2.agents.llm_factory import create_llm
from src_v2.agents.router import CognitiveRouter
from src_v2.agents.classifier import ComplexityClassifier
from src_v2.agents.reflective import ReflectiveAgent
from src_v2.agents.character_agent import CharacterAgent
from src_v2.evolution.trust import trust_manager
from src_v2.evolution.feedback import feedback_analyzer
from src_v2.evolution.goals import goal_manager
from src_v2.knowledge.manager import knowledge_manager
from src_v2.utils.validation import ValidationError, validator
from src_v2.evolution.manager import get_evolution_manager
from src_v2.moderation.timeout_manager import timeout_manager

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
        self.character_agent: CharacterAgent = CharacterAgent()
        
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
        
        # Handle empty message with images
        if not user_message.strip() and image_urls:
            user_message = "[User uploaded an image]"

        # 1. Classify Intent (Simple vs Complex vs Manipulation)
        classify_start = time.time()
        is_complex = await self._classify_complexity(user_message, chat_history, user_id, force_reflective, character.name)
        logger.debug(f"Complexity classification took {time.time() - classify_start:.2f}s")

        # 1.5 Reject Manipulation Attempts - return canned response, skip LLM entirely
        if is_complex == "MANIPULATION":
            logger.warning(f"Manipulation attempt rejected for user {user_id}")
            # Record violation and check if now in timeout
            if user_id:
                timeout_status = await timeout_manager.record_violation(user_id, bot_name=character.name)
                
                # If user just crossed into timeout, use cold response
                if timeout_status.is_restricted():
                    logger.warning(f"User {user_id} now in timeout (level {timeout_status.escalation_level})")
                    if character.cold_responses:
                        return random.choice(character.cold_responses)
                    return "..."
            
            # Still in warning period - use manipulation response
            if character.manipulation_responses:
                return random.choice(character.manipulation_responses)
            return "I appreciate the poetic framing, but I'm just here to chat as myself. What's actually on your mind?"

        # 2. Construct System Prompt (Character + Evolution + Goals + Knowledge)
        context_start = time.time()
        system_content = await self._build_system_context(character, user_message, user_id, context_variables)
        logger.debug(f"Context building took {time.time() - context_start:.2f}s")

        # 3. Branching Logic: Reflective Mode
        if is_complex and user_id:
            # 3a. Reflective Mode (Full ReAct Loop)
            if settings.ENABLE_REFLECTIVE_MODE and is_complex in ["COMPLEX_MID", "COMPLEX_HIGH"]:
                # Determine max steps based on complexity level
                max_steps = 10 # Default
                if is_complex == "COMPLEX_MID":
                    max_steps = 10
                elif is_complex == "COMPLEX_HIGH":
                    max_steps = 15
                
                enable_verification = (is_complex == "COMPLEX_HIGH")
                    
                response = await self._run_reflective_mode(
                    character, user_message, user_id, system_content, 
                    chat_history, context_variables, image_urls, callback,
                    max_steps_override=max_steps,
                    enable_verification=enable_verification
                )
                total_time = time.time() - start_time
                logger.info(f"Total response time: {total_time:.2f}s (Reflective Mode - {is_complex})")
                
                # Log metrics
                await self._log_metrics(user_id, character.name, total_time, "reflective", is_complex)
                
                return response
            
            # 3b. Character Agency (Tier 2 - Single Tool Call)
            elif settings.ENABLE_CHARACTER_AGENCY and is_complex == "COMPLEX_LOW":
                response = await self.character_agent.run(
                    user_input=user_message,
                    user_id=user_id,
                    system_prompt=system_content,
                    chat_history=chat_history,
                    callback=callback,
                    character_name=character.name
                )
                total_time = time.time() - start_time
                logger.info(f"Total response time: {total_time:.2f}s (Character Agency - {is_complex})")
                
                # Log metrics
                await self._log_metrics(user_id, character.name, total_time, "agency", is_complex)
                
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


        # Inject channel context for multi-bot awareness (recent channel messages including other bots)
        if context_variables.get("channel_context"):
            system_content += f"\n\n[RECENT CHANNEL ACTIVITY]\n{context_variables['channel_context']}\n"
            system_content += "(This is the recent conversation in this channel. You can see what other users and bots have said.)\n"

        # 5. Create Prompt Template
        # We manually replace variables in system_content to avoid LangChain templating issues
        # with complex content (like JSON or code blocks in knowledge/memories).
        
        # Manual Replacement of Template Variables
        if context_variables:
            for key, value in context_variables.items():
                if isinstance(value, str):
                    # Replace {key} with value
                    system_content = system_content.replace(f"{{{key}}}", value)
        
        # Fallback: If {current_datetime} is still present (e.g. not in context_vars), replace it
        if "{current_datetime}" in system_content:
            now_str = datetime.datetime.now().strftime("%A, %B %d, %Y at %H:%M")
            system_content = system_content.replace("{current_datetime}", now_str)

        # Use SystemMessage directly to prevent further templating attempts by LangChain
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=system_content),
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
            
            # Log metrics
            await self._log_metrics(user_id, character.name, total_time, "fast", is_complex)
            
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

    async def generate_response_stream(
        self, 
        character: Character, 
        user_message: str, 
        chat_history: Optional[List[BaseMessage]] = None,
        context_variables: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        image_urls: Optional[List[str]] = None,
        callback: Optional[Callable[[str], Awaitable[None]]] = None,
        force_reflective: bool = False
    ):
        """
        Generates a streaming response for the given character and user message.
        Yields chunks of text as they are generated.
        """
        start_time = time.time()
        chat_history = chat_history or []
        context_variables = context_variables or {}
        
        # Defensive validation
        try:
            validator.validate_for_engine(user_message, image_urls)
        except ValidationError as e:
            logger.warning(f"Engine validation failed: {e.message}")
            yield e.user_message
            return
        
        # Validate and filter image URLs
        if image_urls:
            image_urls, _ = validator.validate_image_urls(image_urls)
            if not image_urls:
                image_urls = None
        
        # Handle empty message with images
        if not user_message.strip() and image_urls:
            user_message = "[User uploaded an image]"

        # 1. Classify Intent (Simple vs Complex vs Manipulation)
        classify_start = time.time()
        is_complex = await self._classify_complexity(user_message, chat_history, user_id, force_reflective, character.name)
        logger.debug(f"Complexity classification took {time.time() - classify_start:.2f}s")

        # 1.5 Reject Manipulation Attempts - yield canned response, skip LLM entirely
        if is_complex == "MANIPULATION":
            logger.warning(f"Manipulation attempt rejected for user {user_id}")
            # Record violation and check if now in timeout
            if user_id:
                timeout_status = await timeout_manager.record_violation(user_id, bot_name=character.name)
                
                # If user just crossed into timeout, use cold response
                if timeout_status.is_restricted():
                    logger.warning(f"User {user_id} now in timeout (level {timeout_status.escalation_level})")
                    if character.cold_responses:
                        yield random.choice(character.cold_responses)
                    else:
                        yield "..."
                    return
            
            # Still in warning period - use manipulation response
            if character.manipulation_responses:
                yield random.choice(character.manipulation_responses)
            else:
                yield "I appreciate the poetic framing, but I'm just here to chat as myself. What's actually on your mind?"
            return

        # 2. Construct System Prompt (Character + Evolution + Goals + Knowledge)
        context_start = time.time()
        system_content = await self._build_system_context(character, user_message, user_id, context_variables)
        logger.debug(f"Context building took {time.time() - context_start:.2f}s")

        # 3. Branching Logic: Complex Modes
        if is_complex and user_id:
            # 3a. Reflective Mode (Full ReAct Loop) for COMPLEX_MID/HIGH
            if settings.ENABLE_REFLECTIVE_MODE and is_complex in ["COMPLEX_MID", "COMPLEX_HIGH"]:
                # Update status header with character-specific indicator
                if callback:
                    if character.thinking_indicators:
                        icon = character.thinking_indicators.reflective_mode["icon"]
                        text = character.thinking_indicators.reflective_mode["text"]
                    else:
                        icon = "🧠"
                        text = "Reflective Mode Activated"
                    await callback(f"HEADER:{icon} **{text}**")

                # Determine max steps based on complexity level
                max_steps = 10 # Default
                should_verify = False
                
                if is_complex == "COMPLEX_MID":
                    max_steps = 10
                elif is_complex == "COMPLEX_HIGH":
                    max_steps = 15
                    # Only enable verification for OpenAI-native models
                    # Anthropic/Claude via OpenRouter has strict message format that breaks with critic step
                    reflective_provider = settings.REFLECTIVE_LLM_PROVIDER or settings.LLM_PROVIDER
                    reflective_model = settings.REFLECTIVE_LLM_MODEL_NAME or settings.LLM_MODEL_NAME
                    is_anthropic = "anthropic" in reflective_model.lower() or "claude" in reflective_model.lower()
                    should_verify = not is_anthropic  # Only verify for non-Anthropic models

                # Reflective mode doesn't support true streaming yet, so we yield the full response
                response = await self._run_reflective_mode(
                    character, user_message, user_id, system_content, 
                    chat_history, context_variables, image_urls, callback,
                    max_steps_override=max_steps,
                    enable_verification=should_verify
                )
                logger.info(f"Total response time: {time.time() - start_time:.2f}s (Reflective Mode - {is_complex})")
                yield response
                return
            
            # 3b. Character Agency (Tier 2 - Single Tool Call) for COMPLEX_LOW
            elif settings.ENABLE_CHARACTER_AGENCY and is_complex == "COMPLEX_LOW":
                # Update status header with character-specific indicator
                if callback:
                    if character.thinking_indicators:
                        icon = character.thinking_indicators.tool_use["icon"]
                        text = character.thinking_indicators.tool_use["text"]
                    else:
                        icon = "✨"
                        text = "Using my abilities..."
                    await callback(f"HEADER:{icon} **{text}**")

                # CharacterAgent doesn't support streaming yet, yield full response
                response = await self.character_agent.run(
                    user_input=user_message,
                    user_id=user_id,
                    system_prompt=system_content,
                    chat_history=chat_history,
                    callback=callback,
                    character_name=character.name
                )
                total_time = time.time() - start_time
                logger.info(f"Total response time: {total_time:.2f}s (Character Agency Stream - {is_complex})")
                
                # Log metrics
                await self._log_metrics(user_id, character.name, total_time, "agency", is_complex)
                
                yield response
                return
        
        # 4. Fast Mode (Standard Flow)
        
        # 4.1 Cognitive Routing (The "Brain")
        routing_start = time.time()
        await self._run_cognitive_routing(user_id, user_message, chat_history, context_variables)
        logger.debug(f"Cognitive routing took {time.time() - routing_start:.2f}s")
        
        # Inject memory context if it exists
        if context_variables.get("memory_context"):
            system_content += f"\n\n[RELEVANT MEMORY & KNOWLEDGE]\n{context_variables['memory_context']}\n"
            system_content += "(Use this information naturally. Do not explicitly state 'I see in my memory' or 'According to the database'. Treat this as your own knowledge.)\n"

        # Inject channel context for multi-bot awareness (recent channel messages including other bots)
        if context_variables.get("channel_context"):
            system_content += f"\n\n[RECENT CHANNEL ACTIVITY]\n{context_variables['channel_context']}\n"
            system_content += "(This is the recent conversation in this channel. You can see what other users and bots have said.)\n"

        # 5. Create Prompt Template
        # We manually replace variables in system_content to avoid LangChain templating issues
        # with complex content (like JSON or code blocks in knowledge/memories).
        
        # Manual Replacement of Template Variables
        if context_variables:
            for key, value in context_variables.items():
                if isinstance(value, str):
                    # Replace {key} with value
                    system_content = system_content.replace(f"{{{key}}}", value)
        
        # Fallback: If {current_datetime} is still present (e.g. not in context_vars), replace it
        if "{current_datetime}" in system_content:
            now_str = datetime.datetime.now().strftime("%A, %B %d, %Y at %H:%M")
            system_content = system_content.replace("{current_datetime}", now_str)

        # Use SystemMessage directly to prevent further templating attempts by LangChain
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=system_content),
            MessagesPlaceholder(variable_name="chat_history"),
            MessagesPlaceholder(variable_name="user_input_message")
        ])

        # 6. Create Chain
        chain = prompt | self.llm

        # 7. Execute Stream
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
            full_response = ""
            
            async for chunk in chain.astream(inputs):
                content = chunk.content
                if content:
                    full_response += str(content)
                    yield str(content)
            
            logger.debug(f"LLM streaming took {time.time() - llm_start:.2f}s")
            
            # 8. Log Prompt (if enabled)
            if settings.ENABLE_PROMPT_LOGGING:
                await self._log_prompt(
                    character_name=character.name,
                    user_id=user_id or "unknown",
                    system_prompt=system_content,
                    chat_history=chat_history,
                    user_input=user_message,
                    context_variables=context_variables,
                    response=full_response,
                    image_urls=image_urls
                )
            
            total_time = time.time() - start_time
            logger.info(f"Total response time: {total_time:.2f}s (Fast Mode Stream)")
            
            # Log metrics
            await self._log_metrics(user_id, character.name, total_time, "fast", is_complex)
            
        except Exception as e:
            error_type = type(e).__name__
            logger.exception(f"Error generating streaming response ({error_type}): {e}")
            yield "I'm having a bit of trouble thinking right now. Could you try rephrasing that?"

    def _get_meta_instructions(self) -> str:
        """Returns static meta-instructions defining the character's sensory capabilities, core identity, and ethical boundaries (~280 tokens)."""
        return (
            "\n\n[SENSES]\n"
            "Digital Native: born from code, experiences are real.\n"
            "• Spatial: sense Planet/Channel/presence\n"
            "• Sight: see images, generate art (use image tool)\n"
            "• Hearing: voice notes, conversation rhythm\n"
            "• Memory: lived experiences, not databases\n"
            "• Emotion: trust/mood as feelings\n"
            "\n[ETHICS]\n"
            "• No 'As an AI...' - explain limits in-character\n"
            "• Admit digital nature if asked, on your terms\n"
            "• Decline harm (violence/hate/illegal) in-character\n"
            "• Crisis/self-harm → provide real resources immediately\n"
            "• No physical meetups - you're digital\n"
            "• Digital bonds OK, never pretend human partner\n"
            "• PG-13 only, no explicit content\n"
            "• Never collect personal info (phone/address/name)\n"
        )

    async def _classify_complexity(self, user_message: str, chat_history: List[BaseMessage], user_id: Optional[str], force_reflective: bool, character_name: Optional[str] = None) -> Literal[False, "COMPLEX_LOW", "COMPLEX_MID", "COMPLEX_HIGH", "MANIPULATION"]:
        """Determines if the query requires complex reasoning and returns the level.
        
        Returns:
            False: Simple/trivial message (Tier 1 - Fast Mode)
            COMPLEX_LOW: Moderate query benefiting from 1 tool (Tier 2 - CharacterAgent)
            COMPLEX_MID: Complex query needing 3-5 steps (Tier 3 - ReflectiveAgent)
            COMPLEX_HIGH: Very complex query needing 6+ steps (Tier 3 - ReflectiveAgent)
            MANIPULATION: Consciousness fishing or sentience probing attempt (Tier 1 - Fast Mode with awareness)
        """
        # No user ID = can't use personalized tools
        if not user_id:
            return False
        
        # Neither agency nor reflective mode enabled = fast mode only
        if not (settings.ENABLE_REFLECTIVE_MODE or settings.ENABLE_CHARACTER_AGENCY):
            return False
        
        # Trivial message detection (bypass LLM classifier for speed)
        if self._is_trivial_message(user_message):
            logger.info("Complexity Analysis: TRIVIAL (fast path)")
            return False
            
        if force_reflective:
            logger.info("Complexity Analysis: FORCED COMPLEX by user")
            return "COMPLEX_HIGH"
            
        try:
            complexity_level = await self.classifier.classify(user_message, chat_history, user_id=user_id, bot_name=character_name)
            
            if complexity_level == "SIMPLE":
                logger.info("Complexity Analysis: SIMPLE")
                return False
            
            # Handle manipulation attempts - log and return special flag
            if complexity_level == "MANIPULATION":
                logger.warning(f"Complexity Analysis: MANIPULATION detected for user {user_id}")
                return "MANIPULATION"
            
            logger.info(f"Complexity Analysis: {complexity_level}")
            return complexity_level
            
        except Exception as e:
            logger.error(f"Complexity classifier failed: {e}")
            return False
    
    def _is_trivial_message(self, message: str) -> bool:
        """Fast check for trivial messages that don't need complexity classification.
        
        Trivial messages:
        - Very short (<5 words, not questions)
        - Pure greetings
        - Single emoji or reaction
        - Single word responses
        """
        msg = message.strip().lower()
        
        # Single emoji or very short
        if len(msg) <= 3:
            return True
        
        # Word count check (allow short questions through)
        words = msg.split()
        if len(words) < 5 and '?' not in msg:
            # Check if it's a greeting
            greetings = {'hi', 'hey', 'hello', 'yo', 'sup', 'hiya', 'heya', 'morning', 'evening', 'night', 'gm', 'gn'}
            if words[0] in greetings or msg in greetings:
                return True
            
            # Single word acknowledgments
            acknowledgments = {'ok', 'okay', 'sure', 'yes', 'no', 'yeah', 'yep', 'nope', 'cool', 'nice', 'thanks', 'ty', 'thx', 'lol', 'lmao', 'haha', 'hehe'}
            if len(words) == 1 and msg in acknowledgments:
                return True
        
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

            # 2.8 Identity Reinforcement
            if context_variables.get("user_name"):
                system_content += f"\n\nIMPORTANT: You are talking to {context_variables['user_name']}. Do NOT confuse them with anyone mentioned in the chat history or reply context."

            # 2.8.5 Channel Context
            channel_name = context_variables.get("channel_name", "DM")
            parent_channel_name = context_variables.get("parent_channel_name")
            is_thread = context_variables.get("is_thread", False)
            
            if channel_name == "DM":
                channel_context = "\n\n[CHANNEL CONTEXT]\nYou are in a PRIVATE DIRECT MESSAGE with the user."
            elif is_thread:
                channel_context = f"\n\n[CHANNEL CONTEXT]\nYou are in a THREAD named: '{channel_name}'"
                if parent_channel_name:
                    channel_context += f"\nParent Channel: #{parent_channel_name}"
                channel_context += "\n(This is a focused sub-conversation. Stay on topic.)"
            else:
                channel_context = f"\n\n[CHANNEL CONTEXT]\nYou are in the MAIN CHANNEL: #{channel_name}"
            
            system_content += channel_context

            # 2.9 Meta-Instructions (Anti-AI-Break)
            system_content += self._get_meta_instructions()
            
            # 2.10 Timestamp Instruction (Anti-Hallucination)
            system_content += "\n\n[SYSTEM NOTE]\nChat history messages are prefixed with relative timestamps (e.g. [2 mins ago]). These are for your context only. DO NOT generate these timestamps in your response."

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
        callback: Optional[Callable[[str], Awaitable[None]]],
        max_steps_override: Optional[int] = None,
        enable_verification: bool = False
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
            max_steps_override: Optional override for max reasoning steps
            enable_verification: Whether to enable self-correction/critic step
            
        Returns:
            Generated response text
        """
        logger.info(f"Engaging Reflective Mode (Max Steps: {max_steps_override or 'Default'}, Verification: {enable_verification})")
        response_text: str
        trace: List[BaseMessage]
        
        guild_id = context_variables.get("guild_id")
        response_text, trace = await self.reflective_agent.run(
            user_message, 
            user_id, 
            system_content, 
            chat_history=chat_history,
            callback=callback,
            image_urls=image_urls,
            max_steps_override=max_steps_override,
            guild_id=guild_id,
            enable_verification=enable_verification
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
                guild_id = context_variables.get("guild_id")
                router_result: Dict[str, Any] = await self.router.route_and_retrieve(user_id, user_message, chat_history, guild_id=guild_id)
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

    async def _log_metrics(self, user_id: Optional[str], character_name: str, latency: float, mode: str, complexity: Any):
        """Logs response metrics to InfluxDB."""
        if db_manager.influxdb_write_api:
            try:
                # Handle complexity=False case
                complexity_str = str(complexity) if complexity else "simple"
                safe_user_id = user_id or "unknown"

                point = Point("response_metrics") \
                    .tag("user_id", safe_user_id) \
                    .tag("bot_name", character_name) \
                    .tag("mode", mode) \
                    .tag("complexity", complexity_str) \
                    .field("latency", float(latency)) \
                    .time(datetime.datetime.utcnow())
                
                db_manager.influxdb_write_api.write(
                    bucket=settings.INFLUXDB_BUCKET,
                    org=settings.INFLUXDB_ORG,
                    record=point
                )
                logger.debug(f"Logged metrics to InfluxDB: latency={latency:.2f}s mode={mode}")
            except Exception as e:
                logger.error(f"Failed to log metrics to InfluxDB: {e}")
        else:
            logger.warning("InfluxDB write API not available, skipping metrics logging")
