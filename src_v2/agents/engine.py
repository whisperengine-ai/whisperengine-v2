from typing import List, Dict, Any, Optional, Callable, Awaitable, Literal, Tuple, Union
from dataclasses import dataclass, field
import json
import datetime
import time
import base64
import random
import httpx
from pathlib import Path
import aiofiles
from langsmith import traceable


@dataclass
class ResponseResult:
    """Result object containing response text and metadata."""
    response: str
    mode: str = "fast"  # "fast", "agency", "reflective"
    complexity: str = "SIMPLE"  # "SIMPLE", "COMPLEX_LOW", "COMPLEX_MID", "COMPLEX_HIGH", "MANIPULATION"
    model_used: str = ""  # The model that generated the response
    processing_time_ms: float = 0.0
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from loguru import logger
from influxdb_client.client.write.point import Point

from src_v2.config.settings import settings
from src_v2.core.database import db_manager
from src_v2.config.constants import get_image_format_for_provider
from src_v2.core.character import Character
from src_v2.agents.llm_factory import create_llm
from src_v2.agents.router import CognitiveRouter
from src_v2.agents.classifier import ComplexityClassifier
from src_v2.agents.reflective import ReflectiveAgent
from src_v2.agents.character_agent import CharacterAgent
from src_v2.agents.context_builder import ContextBuilder
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
        self.context_builder: ContextBuilder = ContextBuilder()
        
        # Dependency Injection or Default to Global Instances
        self.trust_manager: Any = trust_manager_dep or trust_manager
        self.feedback_analyzer: Any = feedback_analyzer_dep or feedback_analyzer
        self.goal_manager: Any = goal_manager_dep or goal_manager
        
        # Pre-create log directory to avoid blocking during runtime
        self.log_dir: Path = Path("logs/prompts")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("AgentEngine initialized")

    @traceable(name="AgentEngine.generate_response", run_type="chain")
    async def generate_response(
        self, 
        character: Character, 
        user_message: str, 
        chat_history: Optional[List[BaseMessage]] = None,
        context_variables: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        image_urls: Optional[List[str]] = None,
        callback: Optional[Callable[[str], Awaitable[None]]] = None,
        force_reflective: bool = False,
        force_fast: bool = False,
        return_metadata: bool = False,
        preclassified_complexity: Optional[Union[Literal[False, "COMPLEX_LOW", "COMPLEX_MID", "COMPLEX_HIGH", "MANIPULATION"], str]] = None,
        preclassified_intents: Optional[List[str]] = None
    ) -> str | ResponseResult:
        """
        Generates a response for the given character and user message.
        
        Args:
            force_reflective: If True, forces reflective (ReAct) mode regardless of complexity.
            force_fast: If True, forces fast mode (single-pass LLM, no tools) regardless of complexity.
            preclassified_complexity: Optional complexity verdict supplied by caller to avoid reclassification.
            preclassified_intents: Optional list of intents detected by caller (voice, image, etc.).
            return_metadata: If True, returns ResponseResult with metadata instead of just string.
            preclassified_complexity: Optional complexity verdict supplied by caller to avoid reclassification.
            preclassified_intents: Optional list of intents detected by caller (voice, image, etc.).
        
        Returns:
            str if return_metadata=False, ResponseResult if return_metadata=True.
        """
        # Track metadata for response
        _mode = "fast"
        _complexity = "SIMPLE"
        _model_used = settings.LLM_MODEL_NAME or "unknown"
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
        complexity_result = preclassified_complexity
        detected_intents = list(preclassified_intents or [])

        if complexity_result is None:
            complexity_result, detected_intents = await self.classify_complexity(
                user_message, chat_history, user_id, character.name,
                force_fast=force_fast, force_reflective=force_reflective
            )
            logger.debug(f"Complexity classification took {time.time() - classify_start:.2f}s")
        else:
            logger.debug("Complexity classification reused from caller")

        _complexity = complexity_result if complexity_result else "SIMPLE"

        # Promote complexity for specific intents
        # "memory" intent requires UpdateFactsTool which is only in Reflective Mode (COMPLEX_MID+)
        if "memory" in detected_intents and complexity_result not in ["COMPLEX_MID", "COMPLEX_HIGH"]:
            logger.info("Promoting complexity to COMPLEX_MID due to 'memory' intent")
            complexity_result = "COMPLEX_MID"
            _complexity = "COMPLEX_MID"

        # Handle image-related complexity:
        # - Image GENERATION intents → promote to COMPLEX_MID (needs tools)
        # - Image UPLOADS (image_urls present) → cap at COMPLEX_LOW (CharacterAgent can view images)
        image_intents = ["image_self", "image_other", "image_refine"]
        if image_urls:
            # User uploaded an image - keep in CharacterAgent (COMPLEX_LOW) for viewing
            # Don't promote to reflective mode which can't handle large base64 images well
            if complexity_result in ["COMPLEX_MID", "COMPLEX_HIGH"]:
                logger.info(f"Capping complexity to COMPLEX_LOW for image upload (was {complexity_result})")
                complexity_result = "COMPLEX_LOW"
                _complexity = "COMPLEX_LOW"
        elif any(intent in detected_intents for intent in image_intents) and complexity_result not in ["COMPLEX_MID", "COMPLEX_HIGH"]:
            # User wants to generate an image - promote to COMPLEX_MID
            logger.info(f"Promoting complexity to COMPLEX_MID due to image generation intent: {detected_intents}")
            complexity_result = "COMPLEX_MID"
            _complexity = "COMPLEX_MID"

        # 1.5 Reject Manipulation Attempts - return canned response, skip LLM entirely
        if complexity_result == "MANIPULATION":
            logger.warning(f"Manipulation attempt rejected for user {user_id}")
            _complexity = "MANIPULATION"
            _mode = "blocked"
            # Record violation and check if now in timeout
            if user_id:
                timeout_status = await timeout_manager.record_violation(user_id, bot_name=character.name)
                
                # If user just crossed into timeout, use cold response
                if timeout_status.is_restricted():
                    logger.warning(f"User {user_id} now in timeout (level {timeout_status.escalation_level})")
                    response_text = random.choice(character.cold_responses) if character.cold_responses else "..."
                    if return_metadata:
                        return ResponseResult(response=response_text, mode=_mode, complexity=_complexity, model_used="none")
                    return response_text
            
            # Still in warning period - use manipulation response
            response_text = random.choice(character.manipulation_responses) if character.manipulation_responses else "I appreciate the poetic framing, but I'm just here to chat as myself. What's actually on your mind?"
            if return_metadata:
                return ResponseResult(response=response_text, mode=_mode, complexity=_complexity, model_used="none")
            return response_text

        # 2. Construct System Prompt (Character + Evolution + Goals + Knowledge)
        context_start = time.time()
        system_content = await self._build_system_context(character, user_message, user_id, context_variables)
        logger.debug(f"Context building took {time.time() - context_start:.2f}s")

        # 3. Branching Logic: Reflective Mode
        if complexity_result and user_id:
            # 3a. Reflective Mode (Full ReAct Loop)
            if settings.ENABLE_REFLECTIVE_MODE and complexity_result in ["COMPLEX_MID", "COMPLEX_HIGH"]:
                # Determine max steps based on complexity level
                max_steps = 10 # Default
                if complexity_result == "COMPLEX_MID":
                    max_steps = 10
                elif complexity_result == "COMPLEX_HIGH":
                    max_steps = 15
                
                # Pass detected intents to reflective mode for tool guidance
                if context_variables is None:
                    context_variables = {}
                context_variables["detected_intents"] = detected_intents
                    
                response = await self._run_reflective_mode(
                    character, user_message, user_id, system_content, 
                    chat_history, context_variables, image_urls, callback,
                    max_steps_override=max_steps
                )
                total_time = time.time() - start_time
                logger.info(f"Total response time: {total_time:.2f}s (Reflective Mode - {complexity_result})")
                
                # Log metrics
                await self._log_metrics(user_id, character.name, total_time, "reflective", complexity_result)
                
                if return_metadata:
                    return ResponseResult(
                        response=response,
                        mode="reflective",
                        complexity=complexity_result,
                        model_used=settings.REFLECTIVE_LLM_MODEL_NAME or settings.LLM_MODEL_NAME or "unknown",
                        processing_time_ms=total_time * 1000
                    )
                return response
            
            # 3b. Character Agency (Tier 2 - Single Tool Call)
            # Skip CharacterAgent for image uploads - use Fast Mode instead (simpler, proven to work)
            elif settings.ENABLE_CHARACTER_AGENCY and complexity_result == "COMPLEX_LOW" and not image_urls:
                channel = context_variables.get("channel") if context_variables else None
                response = await self.character_agent.run(
                    user_input=user_message,
                    user_id=user_id,
                    system_prompt=system_content,
                    chat_history=chat_history,
                    callback=callback,
                    character_name=character.name,
                    channel=channel,
                    image_urls=image_urls
                )
                total_time = time.time() - start_time
                logger.info(f"Total response time: {total_time:.2f}s (Character Agency - {complexity_result})")
                
                # Log metrics
                await self._log_metrics(user_id, character.name, total_time, "agency", complexity_result)
                
                if return_metadata:
                    return ResponseResult(
                        response=response,
                        mode="agency",
                        complexity=complexity_result,
                        model_used=settings.LLM_MODEL_NAME or "unknown",
                        processing_time_ms=total_time * 1000
                    )
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

        # NOTE: Channel context is already injected by _build_system_context() 
        # Do NOT add it here again to avoid duplicate context

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
            await self._log_metrics(user_id, character.name, total_time, "fast", complexity_result)
            
            if return_metadata:
                return ResponseResult(
                    response=str(response.content),
                    mode="fast",
                    complexity=complexity_result or "SIMPLE",
                    model_used=settings.LLM_MODEL_NAME or "unknown",
                    processing_time_ms=total_time * 1000
                )
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
        force_reflective: bool = False,
        force_fast: bool = False,
        preclassified_complexity: Optional[Union[Literal[False, "COMPLEX_LOW", "COMPLEX_MID", "COMPLEX_HIGH", "MANIPULATION"], str]] = None,
        preclassified_intents: Optional[List[str]] = None
    ):
        """
        Generates a streaming response for the given character and user message.
        Yields chunks of text as they are generated.
        
        Args:
            force_reflective: If True, forces reflective (ReAct) mode regardless of complexity.
            force_fast: If True, forces fast mode (single-pass LLM, no tools) regardless of complexity.
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
        complexity_result = preclassified_complexity
        detected_intents = list(preclassified_intents or [])

        if complexity_result is None:
            complexity_result, detected_intents = await self.classify_complexity(
                user_message, chat_history, user_id, character.name,
                force_fast=force_fast, force_reflective=force_reflective
            )
            logger.debug(f"Complexity classification took {time.time() - classify_start:.2f}s")
        else:
            logger.debug("Complexity classification reused from caller")

        # Promote complexity for specific intents
        # "memory" intent requires UpdateFactsTool which is only in Reflective Mode (COMPLEX_MID+)
        if "memory" in detected_intents and complexity_result not in ["COMPLEX_MID", "COMPLEX_HIGH"]:
            logger.info("Promoting complexity to COMPLEX_MID due to 'memory' intent")
            complexity_result = "COMPLEX_MID"
            
        # "reminder" intent requires SetReminderTool which is only in Reflective Mode (COMPLEX_MID+)
        if "reminder" in detected_intents and complexity_result not in ["COMPLEX_MID", "COMPLEX_HIGH"]:
            logger.info("Promoting complexity to COMPLEX_MID due to 'reminder' intent")
            complexity_result = "COMPLEX_MID"

        # Handle image-related complexity:
        # - Image UPLOADS (image_urls present) → cap at COMPLEX_LOW (CharacterAgent can view images)
        # - Image GENERATION intents → promote to COMPLEX_MID (needs tools)
        image_intents = ["image_self", "image_other", "image_refine"]
        if image_urls:
            # User uploaded an image - keep in CharacterAgent (COMPLEX_LOW) for viewing
            if complexity_result in ["COMPLEX_MID", "COMPLEX_HIGH"]:
                logger.info(f"Capping complexity to COMPLEX_LOW for image upload (was {complexity_result})")
                complexity_result = "COMPLEX_LOW"
        elif any(intent in detected_intents for intent in image_intents) and complexity_result not in ["COMPLEX_MID", "COMPLEX_HIGH"]:
            # User wants to generate an image - promote to COMPLEX_MID
            logger.info(f"Promoting complexity to COMPLEX_MID due to image generation intent: {detected_intents}")
            complexity_result = "COMPLEX_MID"

        # 1.5 Reject Manipulation Attempts - yield canned response, skip LLM entirely
        if complexity_result == "MANIPULATION":
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
        if complexity_result and user_id:
            # 3a. Reflective Mode (Full ReAct Loop) for COMPLEX_MID/HIGH
            if settings.ENABLE_REFLECTIVE_MODE and complexity_result in ["COMPLEX_MID", "COMPLEX_HIGH"]:
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
                if complexity_result == "COMPLEX_MID":
                    max_steps = 10
                elif complexity_result == "COMPLEX_HIGH":
                    max_steps = 15

                # Reflective mode doesn't support true streaming yet, so we yield the full response
                response = await self._run_reflective_mode(
                    character, user_message, user_id, system_content, 
                    chat_history, context_variables, image_urls, callback,
                    max_steps_override=max_steps
                )
                logger.info(f"Total response time: {time.time() - start_time:.2f}s (Reflective Mode - {complexity_result})")
                
                # Log Prompt (if enabled)
                if settings.ENABLE_PROMPT_LOGGING:
                    await self._log_prompt(
                        character_name=character.name,
                        user_id=user_id or "unknown",
                        system_prompt=system_content,
                        chat_history=chat_history,
                        user_input=user_message,
                        context_variables=context_variables,
                        response=response,
                        image_urls=image_urls
                    )

                yield response
                return
            
            # 3b. Character Agency (Tier 2 - Single Tool Call) for COMPLEX_LOW
            # 3b. Character Agency Stream (Tier 2 - Single Tool Call)
            # Skip CharacterAgent for image uploads - use Fast Mode instead (simpler, proven to work)
            elif settings.ENABLE_CHARACTER_AGENCY and complexity_result == "COMPLEX_LOW" and not image_urls:
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
                guild_id = context_variables.get("guild_id") if context_variables else None
                channel = context_variables.get("channel") if context_variables else None
                response = await self.character_agent.run(
                    user_input=user_message,
                    user_id=user_id,
                    system_prompt=system_content,
                    chat_history=chat_history,
                    callback=callback,
                    guild_id=guild_id,
                    character_name=character.name,
                    channel=channel,
                    image_urls=image_urls
                )
                total_time = time.time() - start_time
                logger.info(f"Total response time: {total_time:.2f}s (Character Agency Stream - {complexity_result})")
                
                # Log metrics
                await self._log_metrics(user_id, character.name, total_time, "agency", complexity_result)
                
                # Log Prompt (if enabled)
                if settings.ENABLE_PROMPT_LOGGING:
                    await self._log_prompt(
                        character_name=character.name,
                        user_id=user_id or "unknown",
                        system_prompt=system_content,
                        chat_history=chat_history,
                        user_input=user_message,
                        context_variables=context_variables,
                        response=response,
                        image_urls=image_urls
                    )

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

        # NOTE: Channel context is already injected by _build_system_context() 
        # Do NOT add it here again to avoid duplicate context

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
            await self._log_metrics(user_id, character.name, total_time, "fast", complexity_result)
            
        except Exception as e:
            error_type = type(e).__name__
            logger.exception(f"Error generating streaming response ({error_type}): {e}")
            yield "I'm having a bit of trouble thinking right now. Could you try rephrasing that?"



    async def classify_complexity(
        self, 
        user_message: str, 
        chat_history: List[BaseMessage], 
        user_id: Optional[str], 
        character_name: Optional[str] = None,
        force_fast: bool = False,
        force_reflective: bool = False
    ) -> Tuple[Union[Literal[False, "COMPLEX_LOW", "COMPLEX_MID", "COMPLEX_HIGH", "MANIPULATION"], str], List[str]]:
        """Determines if the query requires complex reasoning and returns the level.
        
        Args:
            force_fast: If True, bypasses classification and returns False (fast mode).
            force_reflective: If True, bypasses classification and returns COMPLEX_HIGH.
        
        Returns:
            Tuple[Complexity, Intents]
            Complexity: False (Simple) or "COMPLEX_LOW/MID/HIGH" or "MANIPULATION"
            Intents: List of detected intents (e.g. ["voice", "image_self", "search"])
        """
        # Handle explicit overrides first (highest priority)
        if force_fast:
            logger.info("Complexity Analysis: FORCED FAST by caller")
            return False, []
        
        if force_reflective:
            logger.info("Complexity Analysis: FORCED COMPLEX by caller")
            return "COMPLEX_HIGH", []
        
        # No user ID = can't use personalized tools
        if not user_id:
            return False, []
        
        # Neither agency nor reflective mode enabled = fast mode only
        if not (settings.ENABLE_REFLECTIVE_MODE or settings.ENABLE_CHARACTER_AGENCY):
            return False, []

        # Trivial message detection (bypass LLM classifier for speed)
        if self._is_trivial_message(user_message):
            logger.info("Complexity Analysis: TRIVIAL (fast path)")
            return False, []
            
        try:
            classification_result = await self.classifier.classify(user_message, chat_history, user_id=user_id, bot_name=character_name)
            
            # Handle legacy string return (just in case)
            if isinstance(classification_result, str):
                complexity_level = classification_result
                intents = []
            else:
                complexity_level = classification_result.get("complexity", "SIMPLE")
                intents = classification_result.get("intents", [])
            
            if complexity_level == "SIMPLE":
                logger.info("Complexity Analysis: SIMPLE")
                return False, intents
            
            # Handle manipulation attempts - log and return special flag
            if complexity_level == "MANIPULATION":
                logger.warning(f"Complexity Analysis: MANIPULATION detected for user {user_id}")
                return "MANIPULATION", intents
            
            logger.info(f"Complexity Analysis: {complexity_level} (Intents: {intents})")
            return complexity_level, intents
            
        except Exception as e:
            logger.error(f"Complexity classifier failed: {e}")
            return False, []
    
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
        return await self.context_builder.build_system_context(character, user_message, user_id, context_variables)









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
        max_steps_override: Optional[int] = None
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
            
        Returns:
            Generated response text
        """
        logger.info(f"Engaging Reflective Mode (Max Steps: {max_steps_override or 'Default'})")
        response_text: str
        trace: List[BaseMessage]
        
        guild_id = context_variables.get("guild_id")
        channel = context_variables.get("channel")
        detected_intents = context_variables.get("detected_intents", [])
        response_text, trace = await self.reflective_agent.run(
            user_message, 
            user_id, 
            system_content, 
            chat_history=chat_history,
            callback=callback,
            image_urls=image_urls,
            max_steps_override=max_steps_override,
            guild_id=guild_id,
            channel=channel,
            detected_intents=detected_intents
        )
        
        # Voice Synthesis: Use Main LLM to rewrite the response
        # This ensures character consistency even when using a different reasoning model
        # We skip this if the response indicates failure or if it's very short
        if response_text and len(response_text) > 10 and not response_text.startswith("I'm not sure"):
            try:
                if callback:
                    await callback("🎙️ Synthesizing final response...")
                
                logger.info("Synthesizing reflective response with Main LLM for character voice")
                
                synthesis_messages = [
                    SystemMessage(content=system_content),
                ]
                
                # Add limited chat history for context style
                if chat_history:
                    synthesis_messages.extend(chat_history[-4:])
                
                # Add the user message
                synthesis_messages.append(HumanMessage(content=user_message))
                
                # Add the reasoning context as a system instruction
                synthesis_messages.append(SystemMessage(content=f"""[INTERNAL REASONING RESULTS]
I have processed this request and gathered the following information:
{response_text}

INSTRUCTIONS:
Using the information above, formulate a final response to the user in my authentic voice and style.
- Incorporate the facts naturally
- Maintain my personality and quirks
- Do not mention "internal reasoning" or that this information was provided
- If the reasoning output is already a good response, just polish it"""))

                # Use the Main LLM (self.llm) which holds the character persona
                synthesis_response = await self.llm.ainvoke(synthesis_messages)
                
                if synthesis_response.content:
                    response_text = str(synthesis_response.content)
            
            except Exception as e:
                logger.error(f"Voice synthesis failed, using raw reflective response: {e}")
        
        # Save reasoning trace for future reuse (Phase 3.2)
        if settings.ENABLE_TRACE_LEARNING and trace and len(trace) > 2:
            try:
                from src_v2.workers.task_queue import task_queue
                # Extract trace summary for storage
                trace_context = self._format_trace_for_storage(trace, user_message, response_text)
                await task_queue.enqueue_insight_analysis(
                    user_id=user_id,
                    character_name=character.name,
                    trigger="reflective_completion",
                    priority=4,
                    recent_context=trace_context
                )
                logger.debug(f"Enqueued trace analysis for user {user_id}")
            except Exception as trace_err:
                logger.warning(f"Failed to enqueue trace analysis: {trace_err}")
        
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
                
                # Extract channel_id from context variables
                channel_id = None
                if "channel" in context_variables:
                    channel = context_variables["channel"]
                    if hasattr(channel, "id"):
                        channel_id = str(channel.id)
                
                router_result: Dict[str, Any] = await self.router.route_and_retrieve(
                    user_id, 
                    user_message, 
                    chat_history, 
                    guild_id=guild_id,
                    channel_id=channel_id
                )
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
            # Filter out non-serializable objects from context_variables
            safe_context = {}
            for k, v in context_variables.items():
                try:
                    json.dumps(v)  # Test if serializable
                    safe_context[k] = v
                except (TypeError, ValueError):
                    safe_context[k] = f"<{type(v).__name__}>"  # Replace with type name
            
            log_data = {
                "timestamp": datetime.datetime.now().isoformat(),
                "character": character_name,
                "user_id": user_id,
                "inputs": {
                    "system_prompt": system_prompt,
                    "context_variables": safe_context,
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

    def _format_trace_for_storage(self, trace: List[BaseMessage], user_query: str, final_response: str) -> str:
        """
        Formats a reasoning trace for InsightAgent analysis.
        Extracts tool calls and reasoning steps for pattern learning.
        """
        tools_used = []
        reasoning_steps = []
        
        for msg in trace:
            if isinstance(msg, AIMessage):
                # Extract tool calls
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_name = tc.get("name")
                        if tool_name:
                            tools_used.append(tool_name)
                # Extract reasoning content
                if msg.content and len(str(msg.content)) > 10:
                    reasoning_steps.append(str(msg.content)[:200])  # Truncate long thoughts
            elif isinstance(msg, ToolMessage):
                # Tool results help understand what worked
                if msg.content and "Error" not in str(msg.content):
                    reasoning_steps.append(f"Tool {msg.name} succeeded")
        
        # Format for InsightAgent
        formatted = f"""[REFLECTIVE TRACE]
User Query: {user_query}
Tools Used: {', '.join(set(tools_used)) if tools_used else 'none'}
Reasoning Steps: {len(reasoning_steps)}
Final Response: {final_response[:150]}...

This trace represents a successful reflective reasoning session.
Analyze it to extract:
1. Query pattern type (emotional support, information lookup, creative task, etc.)
2. Effective tool combination
3. Complexity estimate (for future routing)
"""
        return formatted

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
