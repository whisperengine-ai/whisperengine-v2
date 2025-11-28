"""
WhisperEngine Chat API Models

Pydantic models for API request/response validation.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ChatRequest(BaseModel):
    """Request model for the chat endpoint."""
    
    user_id: str = Field(
        ..., 
        description="Unique identifier for the user. Used for memory retrieval and relationship tracking.",
        examples=["user_12345", "discord_987654321"]
    )
    message: str = Field(
        ..., 
        description="The user's message to the character.",
        examples=["Hello! How are you today?", "What's your favorite book?"]
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="Additional context variables passed to the character's prompt template.",
        examples=[{"channel_name": "general", "guild_name": "My Server"}]
    )


class ChatResponse(BaseModel):
    """Response model for the chat endpoint."""
    
    success: bool = Field(
        ...,
        description="Whether the request was processed successfully."
    )
    response: str = Field(
        ...,
        description="The character's response message."
    )
    timestamp: datetime = Field(
        ...,
        description="ISO 8601 timestamp of the response."
    )
    bot_name: str = Field(
        ...,
        description="Name of the character that responded."
    )
    processing_time_ms: float = Field(
        ...,
        description="Time taken to generate the response in milliseconds."
    )
    memory_stored: bool = Field(
        default=True,
        description="Whether the interaction was stored in memory."
    )


class HealthResponse(BaseModel):
    """Response model for the health check endpoint."""
    
    status: str = Field(
        ...,
        description="Health status of the API.",
        examples=["healthy"]
    )
    timestamp: datetime = Field(
        ...,
        description="ISO 8601 timestamp of the health check."
    )
