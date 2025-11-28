"""
WhisperEngine Chat API Routes

This module defines the REST API endpoints for interacting with WhisperEngine characters.
"""

from fastapi import APIRouter, HTTPException
from src_v2.api.models import ChatRequest, ChatResponse, HealthResponse
from src_v2.agents.engine import AgentEngine
from src_v2.config.settings import settings
from src_v2.core.character import character_manager
from datetime import datetime
import time
from loguru import logger

router = APIRouter(tags=["chat"])
agent_engine = AgentEngine()


@router.post(
    "/api/chat",
    response_model=ChatResponse,
    summary="Send a message to the character",
    description="""
    Send a message to the AI character and receive a response.
    
    The character will use its memory system to recall previous interactions,
    knowledge graph for contextual facts, and the configured LLM for response generation.
    
    **Processing Time**: Typical responses take 1-5 seconds. Complex queries with
    reflective reasoning may take 10-30 seconds.
    """,
    responses={
        200: {"description": "Successful response from the character"},
        500: {"description": "Server error (character not found, LLM error, etc.)"}
    }
)
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """
    Process a chat message and generate an AI character response.
    
    Args:
        request: The chat request containing user_id, message, and optional context.
        
    Returns:
        ChatResponse with the character's response and metadata.
        
    Raises:
        HTTPException: If the bot is not configured or character is not found.
    """
    start_time = time.time()
    
    # Load character
    bot_name = settings.DISCORD_BOT_NAME
    if not bot_name:
        raise HTTPException(status_code=500, detail="Bot name not configured")
        
    character = character_manager.get_character(bot_name)
    if not character:
        raise HTTPException(status_code=500, detail=f"Character {bot_name} not found")

    try:
        # Generate response
        response_text = await agent_engine.generate_response(
            character=character,
            user_message=request.message,
            user_id=request.user_id,
            context_variables=request.context or {}
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        return ChatResponse(
            success=True,
            response=response_text,
            timestamp=datetime.now(),
            bot_name=bot_name,
            processing_time_ms=processing_time,
            memory_stored=True
        )
        
    except Exception as e:
        logger.exception("Error processing chat request")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check endpoint",
    description="Check if the API is healthy and responding.",
    responses={
        200: {"description": "API is healthy"}
    }
)
async def health_check() -> HealthResponse:
    """
    Return the health status of the API.
    
    Returns:
        HealthResponse with status and current timestamp.
    """
    return HealthResponse(status="healthy", timestamp=datetime.now())
