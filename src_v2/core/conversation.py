"""
Unified Conversation Service

SINGLE entry point for ALL message processing, regardless of transport:
- Discord (message_handler.py)
- HTTP API (routes.py)  
- Daily Life polling (execute.py)
- Cross-bot conversations

This ensures consistent processing: memory, knowledge, sessions, summarization.
Bot messages are first-class citizens - same processing as human users.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, TYPE_CHECKING, Callable, Awaitable
from datetime import datetime
from loguru import logger
import asyncio

from src_v2.config.settings import settings
from src_v2.memory.models import MemorySourceType

if TYPE_CHECKING:
    from src_v2.core.character import Character


@dataclass
class ConversationContext:
    """Input context for a conversation turn."""
    
    # Required
    user_id: str
    user_name: str
    character_name: str
    user_message: str
    
    # Optional context
    channel_id: Optional[str] = None
    channel_name: Optional[str] = None
    server_id: Optional[str] = None
    message_id: Optional[str] = None
    
    # Flags
    is_cross_bot: bool = False
    source_bot_name: Optional[str] = None  # If is_cross_bot, which bot sent it
    
    # Transport origin (for debugging/metrics)
    origin: str = "unknown"  # "discord", "api", "daily_life", "cross_bot"
    
    # Additional context variables for the LLM
    extra_context: Dict[str, Any] = field(default_factory=dict)
    
    # Pre-fetched context (to avoid duplicate queries)
    prefetched_memories: Optional[List[Any]] = None
    prefetched_knowledge: Optional[str] = None
    chat_history: Optional[List[Any]] = None
    past_summaries: Optional[str] = None


@dataclass
class ConversationResult:
    """Output from a conversation turn."""
    
    response: str
    success: bool = True
    
    # Metadata
    session_id: Optional[str] = None
    response_message_id: Optional[str] = None  # Populated after sending
    mode: str = "fast"  # "fast" or "reflective"
    
    # Error handling
    error: Optional[str] = None


class ConversationService:
    """
    Unified service for processing conversation turns.
    
    This is the SINGLE source of truth for:
    1. Generating AI responses
    2. Storing messages to memory (both user and AI)
    3. Managing sessions
    4. Triggering background learning
    5. Checking for summarization
    
    All transports (Discord, API, Daily Life) should use this.
    """
    
    def __init__(self):
        self._initialized = False
    
    async def process_turn(
        self,
        context: ConversationContext,
        character: "Character",
        send_callback: Optional[Callable[..., Awaitable[Any]]] = None,
        reflective_callback: Optional[Callable[..., Awaitable[Any]]] = None,
        force_fast: bool = False,
        force_reflective: bool = False,
    ) -> ConversationResult:
        """
        Process a single conversation turn.
        
        Args:
            context: The conversation context (user, message, metadata)
            character: The character configuration
            send_callback: Optional async callback to send the response (for streaming)
                          If None, response is returned but not sent.
            reflective_callback: Optional callback for reflective mode status updates
            force_fast: Force fast mode (skip reflective)
            force_reflective: Force reflective mode
            
        Returns:
            ConversationResult with response and metadata
        """
        from src_v2.agents.engine import AgentEngine
        from src_v2.memory.manager import memory_manager
        from src_v2.memory.session import session_manager
        from src_v2.discord.handlers.message_handler import enqueue_background_learning
        
        try:
            # 1. Session Management
            session_id = await session_manager.get_active_session(
                context.user_id, 
                context.character_name
            )
            if not session_id:
                session_id = await session_manager.create_session(
                    context.user_id, 
                    context.character_name
                )
                logger.debug(f"[Conversation] Created session {session_id} for {context.user_name}")
            
            # 2. Build context variables for LLM
            context_vars = {
                "user_name": context.user_name,
                "current_datetime": datetime.now().strftime("%B %d, %Y at %I:%M %p"),
                "channel_name": context.channel_name or "DM",
                "is_cross_bot": context.is_cross_bot,
                **context.extra_context,
            }
            
            # Add pre-fetched context if provided
            if context.prefetched_memories:
                context_vars["prefetched_memories"] = context.prefetched_memories
            if context.prefetched_knowledge:
                context_vars["prefetched_knowledge"] = context.prefetched_knowledge
            if context.chat_history:
                context_vars["chat_history"] = context.chat_history
            if context.past_summaries:
                context_vars["past_summaries"] = context.past_summaries
            
            # 3. Generate response via AgentEngine
            engine = AgentEngine()
            
            result = await engine.generate_response(
                character=character,
                user_message=context.user_message,
                user_id=context.user_id,
                context_variables=context_vars,
                return_metadata=True,
                force_fast=force_fast,
                force_reflective=force_reflective,
                callback=reflective_callback,
            )
            
            # Handle both string and structured result
            if isinstance(result, str):
                response_text = result
                mode = "fast"
            else:
                response_text = getattr(result, 'response', str(result))
                mode = getattr(result, 'mode', 'fast')
            
            # 3b. Send response (if callback provided) to get ID for memory
            sent_message_id = None
            if send_callback:
                try:
                    # Callback should return the message ID or object with .id
                    sent_result = await send_callback(response_text)
                    if sent_result:
                        if hasattr(sent_result, 'id'):
                            sent_message_id = str(sent_result.id)
                        else:
                            sent_message_id = str(sent_result)
                except Exception as send_err:
                    logger.error(f"[Conversation] Send callback failed: {send_err}")
                    # Continue to store memory even if send failed (so we have record of intent)
            
            # 4. Store THEIR message to memory
            incoming_source = (
                MemorySourceType.GOSSIP if context.is_cross_bot 
                else MemorySourceType.HUMAN_DIRECT
            )
            
            await memory_manager.add_message(
                user_id=context.user_id,
                character_name=context.character_name,
                role="human",
                content=context.user_message,
                channel_id=context.channel_id,
                message_id=context.message_id,
                user_name=context.user_name,
                source_type=incoming_source,
                metadata={
                    "is_cross_bot": context.is_cross_bot,
                    "source_bot": context.source_bot_name,
                    "origin": context.origin,
                }
            )
            
            # 5. Store OUR response to memory
            await memory_manager.add_message(
                user_id=context.user_id,
                character_name=context.character_name,
                role="ai",
                content=response_text,
                channel_id=context.channel_id,
                message_id=sent_message_id,  # Now populated if sent
                user_name=context.user_name,
                source_type=MemorySourceType.INFERENCE,
                metadata={
                    "is_cross_bot": context.is_cross_bot,
                    "responding_to": context.source_bot_name if context.is_cross_bot else context.user_name,
                    "origin": context.origin,
                }
            )
            
            logger.debug(f"[Conversation] Saved turn with {context.user_name} ({context.origin})")
            
            # 6. Background learning (currently a no-op, triggers at session end)
            await enqueue_background_learning(
                user_id=context.user_id,
                message_content=context.user_message,
                character_name=context.character_name,
                context=context.origin,
            )
            
            return ConversationResult(
                response=response_text,
                success=True,
                session_id=session_id,
                mode=mode,
                response_message_id=sent_message_id,
            )
            
        except Exception as e:
            logger.error(f"[Conversation] Error processing turn: {e}")
            return ConversationResult(
                response="",
                success=False,
                error=str(e),
            )
    
    async def trigger_summarization_check(
        self,
        session_id: str,
        user_id: str,
        user_name: str,
        channel_id: Optional[str] = None,
        server_id: Optional[str] = None,
        force: bool = False,
        message_handler: Optional[Any] = None,
    ) -> None:
        """
        Check if session needs summarization.
        
        This is separate from process_turn because some transports
        want to trigger this after sending the response (not before).
        
        If message_handler is provided, uses its _check_and_summarize method.
        Otherwise, this is a no-op (summarization will be triggered by the
        transport's own logic).
        """
        if message_handler and hasattr(message_handler, '_check_and_summarize'):
            try:
                asyncio.create_task(
                    message_handler._check_and_summarize(
                        session_id=session_id,
                        user_id=user_id,
                        user_name=user_name,
                        channel_id=channel_id,
                        server_id=server_id,
                        force_processing=force,
                    )
                )
                logger.debug(f"[Conversation] Triggered summarization check for session {session_id}")
            except Exception as e:
                logger.warning(f"[Conversation] Summarization check failed: {e}")
        else:
            # No message handler available - summarization will be handled
            # by the transport's own mechanism (or skipped for API calls)
            logger.debug(f"[Conversation] Skipping summarization (no handler)")


# Global singleton
conversation_service = ConversationService()
