"""
WhisperEngine Chat API Models

Pydantic models for API request/response validation.
"""

from typing import Optional, Dict, Any, List
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
        examples=[{"channel_name": "general", "guild_id": "123456789"}]
    )
    force_mode: Optional[str] = Field(
        default=None,
        description="Override the auto-detected complexity mode. Options: 'fast' (single-pass LLM, no tools), 'reflective' (full ReAct reasoning). If not set, mode is auto-detected.",
        examples=["fast", "reflective"]
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
    # Debug/diagnostic fields
    mode: Optional[str] = Field(
        default=None,
        description="Processing mode used: 'fast', 'agency', 'reflective', or 'blocked'."
    )
    complexity: Optional[str] = Field(
        default=None,
        description="Complexity classification: 'SIMPLE', 'COMPLEX_LOW', 'COMPLEX_MID', 'COMPLEX_HIGH', or 'MANIPULATION'."
    )
    model_used: Optional[str] = Field(
        default=None,
        description="The LLM model that generated the response (e.g., 'openai/gpt-4o')."
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


# ============================================================================
# Diagnostic Endpoints (for testing and regression)
# ============================================================================

class DiagnosticsResponse(BaseModel):
    """Full system diagnostics for a bot."""
    
    bot_name: str = Field(..., description="Character name")
    llm_models: Dict[str, str] = Field(
        default_factory=dict,
        description="Configured LLM models (main, reflective, router)"
    )
    database_status: Dict[str, bool] = Field(
        default_factory=dict,
        description="Connection status for each database"
    )
    feature_flags: Dict[str, bool] = Field(
        default_factory=dict,
        description="Enabled feature flags"
    )
    queue_depths: Dict[str, int] = Field(
        default_factory=dict,
        description="Number of pending jobs in each worker queue"
    )
    uptime_seconds: float = Field(0.0, description="Seconds since bot started")
    version: str = Field("unknown", description="Bot version")


class UserStateRequest(BaseModel):
    """Request to get user state for testing."""
    
    user_id: str = Field(..., description="User ID to look up")


class UserStateResponse(BaseModel):
    """User state for regression testing."""
    
    user_id: str
    trust_score: int = Field(0, description="Current trust score")
    trust_level: str = Field("Stranger", description="Trust level label")
    memory_count: int = Field(0, description="Number of stored memories")
    recent_memories: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Last 5 memories for verification"
    )
    knowledge_facts: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Known facts about this user"
    )


class ConversationRequest(BaseModel):
    """Multi-turn conversation test request."""
    
    user_id: str = Field(..., description="User ID for the conversation")
    messages: List[str] = Field(
        ..., 
        description="List of messages to send in sequence",
        min_length=1
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Shared context for all messages"
    )
    delay_between_ms: int = Field(
        default=500,
        description="Delay between messages in milliseconds"
    )


class ConversationTurn(BaseModel):
    """A single turn in a conversation."""
    
    user_message: str
    bot_response: str
    processing_time_ms: float
    mode: Optional[str] = None
    complexity: Optional[str] = None


class ConversationResponse(BaseModel):
    """Multi-turn conversation test response."""
    
    success: bool
    user_id: str
    bot_name: str
    turns: List[ConversationTurn]
    total_time_ms: float
    memory_stored: bool = True


class ClearUserDataRequest(BaseModel):
    """Request to clear user data for test isolation."""
    
    user_id: str = Field(..., description="User ID to clear")
    clear_memories: bool = Field(True, description="Clear vector memories")
    clear_trust: bool = Field(True, description="Reset trust score")
    clear_knowledge: bool = Field(False, description="Clear knowledge graph facts")


class ClearUserDataResponse(BaseModel):
    """Response from clearing user data."""
    
    success: bool
    user_id: str
    memories_cleared: int = 0
    trust_reset: bool = False
    knowledge_cleared: int = 0


# ============================================================================
# User-Facing Graph (E28)
# ============================================================================

class UserGraphRequest(BaseModel):
    """Request for user knowledge graph visualization."""
    
    user_id: str = Field(..., description="User ID to get graph for")
    depth: int = Field(
        default=2,
        description="Max depth to traverse from user node (1-4)",
        ge=1,
        le=4
    )
    include_other_users: bool = Field(
        default=False,
        description="Include other users connected through shared entities"
    )
    max_nodes: int = Field(
        default=50,
        description="Maximum nodes to return (10-100)",
        ge=10,
        le=100
    )


class GraphNode(BaseModel):
    """A node in the user graph visualization."""
    
    id: str = Field(..., description="Unique node ID")
    label: str = Field(..., description="Node type (User, Entity, Character, Topic)")
    name: str = Field(..., description="Display name")
    score: float = Field(0.0, description="Relevance score from graph walk")
    properties: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional node properties"
    )


class GraphEdge(BaseModel):
    """An edge in the user graph visualization."""
    
    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    edge_type: str = Field(..., description="Relationship type (FACT, KNOWS, MENTIONED, etc.)")
    properties: Dict[str, Any] = Field(
        default_factory=dict,
        description="Edge properties (predicate, count, etc.)"
    )


class GraphCluster(BaseModel):
    """A thematic cluster of related nodes."""
    
    theme: str = Field(..., description="Cluster theme/topic")
    node_ids: List[str] = Field(..., description="Node IDs in this cluster")
    cohesion_score: float = Field(0.0, description="How tightly connected the cluster is")


class UserGraphResponse(BaseModel):
    """Response with user's knowledge graph subgraph for D3.js visualization."""
    
    success: bool
    user_id: str
    bot_name: str
    nodes: List[GraphNode] = Field(default_factory=list, description="Graph nodes")
    edges: List[GraphEdge] = Field(default_factory=list, description="Graph edges")
    clusters: List[GraphCluster] = Field(default_factory=list, description="Thematic clusters")
    stats: Dict[str, Any] = Field(
        default_factory=dict,
        description="Graph statistics (node_count, edge_count, depth, etc.)"
    )
