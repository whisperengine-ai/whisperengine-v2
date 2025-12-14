"""
WhisperEngine Chat API Routes

This module defines the REST API endpoints for interacting with WhisperEngine characters.
"""

from fastapi import APIRouter, HTTPException
from src_v2.api.models import (
    ChatRequest, ChatResponse, HealthResponse,
    DiagnosticsResponse, UserStateRequest, UserStateResponse,
    ConversationRequest, ConversationResponse, ConversationTurn,
    ClearUserDataRequest, ClearUserDataResponse,
    UserGraphRequest, UserGraphResponse, GraphNode, GraphEdge, GraphCluster
)
from src_v2.agents.engine import AgentEngine
from src_v2.config.settings import settings
from src_v2.core.character import character_manager
from src_v2.core.database import db_manager
from src_v2.memory.manager import memory_manager
from src_v2.evolution.trust import trust_manager
from src_v2.knowledge.manager import knowledge_manager
from src_v2.knowledge.walker import GraphWalker
from datetime import datetime
import time
import asyncio
from loguru import logger

router = APIRouter(tags=["chat"])
agent_engine = AgentEngine()
_start_time = time.time()  # Track uptime


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
        # Determine mode override
        force_fast = request.force_mode == "fast"
        force_reflective = request.force_mode == "reflective"
        
        # Generate response with metadata
        result = await agent_engine.generate_response(
            character=character,
            user_message=request.message,
            user_id=request.user_id,
            context_variables=request.context or {},
            return_metadata=True,
            force_reflective=force_reflective,
            force_fast=force_fast
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        return ChatResponse(
            success=True,
            response=result.response,
            timestamp=datetime.now(),
            bot_name=bot_name,
            processing_time_ms=processing_time,
            memory_stored=True,
            mode=result.mode,
            complexity=result.complexity,
            model_used=result.model_used
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


# ============================================================================
# Diagnostic Endpoints (for testing and regression)
# ============================================================================

@router.get(
    "/api/diagnostics",
    response_model=DiagnosticsResponse,
    summary="Get system diagnostics",
    description="Returns bot configuration, database status, and feature flags for testing.",
    tags=["diagnostics"]
)
async def get_diagnostics() -> DiagnosticsResponse:
    """Get full system diagnostics for testing."""
    bot_name = settings.DISCORD_BOT_NAME or "unknown"
    
    # Check database connections
    db_status = {
        "postgres": db_manager.postgres_pool is not None,
        "qdrant": db_manager.qdrant_client is not None,
        "neo4j": db_manager.neo4j_driver is not None,
        "redis": db_manager.redis_client is not None,
    }
    
    # Get model config
    llm_models = {
        "main": settings.LLM_MODEL_NAME,
        "reflective": settings.REFLECTIVE_LLM_MODEL_NAME if settings.ENABLE_REFLECTIVE_MODE else settings.LLM_MODEL_NAME,
        "router": settings.ROUTER_LLM_MODEL_NAME or "openai/gpt-4o-mini",
    }
    
    # Feature flags
    feature_flags = {
        "reflective_mode": settings.ENABLE_REFLECTIVE_MODE,
        "fact_extraction": settings.ENABLE_RUNTIME_FACT_EXTRACTION,
        "preference_extraction": settings.ENABLE_PREFERENCE_EXTRACTION,
        "proactive_messaging": settings.ENABLE_PROACTIVE_MESSAGING,
    }
    
    # Queue depths (pending jobs in each worker queue)
    queue_depths = {}
    try:
        if db_manager.redis_client:
            # arq uses sorted sets for queues
            queue_names = [
                ("cognition", "arq:cognition"),
                ("sensory", "arq:sensory"),
                ("action", "arq:action"),
                ("social", "arq:social"),
            ]
            for name, key in queue_names:
                depth = await db_manager.redis_client.zcard(key)
                queue_depths[name] = depth or 0
    except Exception as e:
        logger.warning(f"Could not fetch queue depths: {e}")
        queue_depths = {"error": str(e)}
    
    # Get version
    try:
        with open("VERSION", "r") as f:
            version = f.read().strip()
    except Exception:
        version = "unknown"
    
    return DiagnosticsResponse(
        bot_name=bot_name,
        llm_models=llm_models,
        database_status=db_status,
        feature_flags=feature_flags,
        queue_depths=queue_depths,
        uptime_seconds=time.time() - _start_time,
        version=version
    )


@router.post(
    "/api/user-state",
    response_model=UserStateResponse,
    summary="Get user state for testing",
    description="Returns trust level, memories, and knowledge for a user. Useful for regression testing.",
    tags=["diagnostics"]
)
async def get_user_state(request: UserStateRequest) -> UserStateResponse:
    """Get user state including trust, memories, and knowledge."""
    bot_name = settings.DISCORD_BOT_NAME
    user_id = request.user_id
    
    # Get trust level
    trust_info = await trust_manager.get_relationship_level(user_id, bot_name)
    
    # Get recent memories (last 5) - use a general search
    # IMPORTANT: Pass collection_name to avoid worker context issues
    try:
        collection_name = f"whisperengine_memory_{bot_name}"
        memories = await memory_manager.search_memories(
            query="conversation history",  # Generic query
            user_id=user_id,
            limit=5,
            collection_name=collection_name
        )
        memory_list = [
            {"content": m.get("content", "")[:200], "score": m.get("score", 0)}
            for m in memories
        ]
    except Exception as e:
        logger.warning(f"Could not fetch memories: {e}")
        memory_list = []
    
    # Get knowledge - use existing get_user_knowledge method
    try:
        knowledge_str = await knowledge_manager.get_user_knowledge(user_id, limit=10)
        # Parse into list of facts
        fact_list = [{"fact": line} for line in knowledge_str.split("\n") if line.strip()]
    except Exception as e:
        logger.warning(f"Could not fetch knowledge: {e}")
        fact_list = []
    
    return UserStateResponse(
        user_id=user_id,
        trust_score=trust_info.get("trust_score", 0),
        trust_level=trust_info.get("level_label", "Stranger"),
        memory_count=len(memory_list),
        recent_memories=memory_list,
        knowledge_facts=fact_list
    )


@router.post(
    "/api/conversation",
    response_model=ConversationResponse,
    summary="Multi-turn conversation test",
    description="Send multiple messages in sequence to test conversation flow and memory.",
    tags=["diagnostics"]
)
async def conversation_test(request: ConversationRequest) -> ConversationResponse:
    """Run a multi-turn conversation test."""
    bot_name = settings.DISCORD_BOT_NAME
    character = character_manager.get_character(bot_name)
    
    if not character:
        raise HTTPException(status_code=500, detail=f"Character {bot_name} not found")
    
    turns = []
    total_start = time.time()
    
    for i, message in enumerate(request.messages):
        start_time = time.time()
        
        try:
            result = await agent_engine.generate_response(
                character=character,
                user_message=message,
                user_id=request.user_id,
                context_variables=request.context or {},
                return_metadata=True
            )
            
            processing_time = (time.time() - start_time) * 1000
            
            turns.append(ConversationTurn(
                user_message=message,
                bot_response=result.response,
                processing_time_ms=processing_time,
                mode=result.mode,
                complexity=result.complexity
            ))
            
            # Delay between messages (if not last message)
            if i < len(request.messages) - 1 and request.delay_between_ms > 0:
                await asyncio.sleep(request.delay_between_ms / 1000.0)
                
        except Exception as e:
            logger.error(f"Conversation turn {i} failed: {e}")
            turns.append(ConversationTurn(
                user_message=message,
                bot_response=f"[ERROR: {str(e)}]",
                processing_time_ms=0
            ))
    
    total_time = (time.time() - total_start) * 1000
    
    return ConversationResponse(
        success=all("[ERROR:" not in t.bot_response for t in turns),
        user_id=request.user_id,
        bot_name=bot_name,
        turns=turns,
        total_time_ms=total_time
    )


@router.post(
    "/api/clear-user-data",
    response_model=ClearUserDataResponse,
    summary="Clear user data for test isolation",
    description="Clears memories and trust for a user. Use for test setup/teardown.",
    tags=["diagnostics"]
)
async def clear_user_data(request: ClearUserDataRequest) -> ClearUserDataResponse:
    """Clear user data for test isolation."""
    bot_name = settings.DISCORD_BOT_NAME
    user_id = request.user_id
    
    memories_cleared = 0
    trust_reset = False
    knowledge_cleared = 0
    
    # Clear memories (uses existing clear_memory method)
    if request.clear_memories:
        try:
            await memory_manager.clear_memory(user_id, bot_name)
            memories_cleared = 1  # Method doesn't return count, but it clears
        except Exception as e:
            logger.error(f"Failed to clear memories: {e}")
    
    # Reset trust - update to 0
    if request.clear_trust:
        try:
            async with db_manager.postgres_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE v2_user_relationships 
                    SET trust_score = 0, unlocked_traits = '[]'::jsonb
                    WHERE user_id = $1 AND character_name = $2
                """, user_id, bot_name)
            trust_reset = True
        except Exception as e:
            logger.error(f"Failed to reset trust: {e}")
    
    # Clear knowledge graph facts (optional)
    if request.clear_knowledge:
        try:
            async with db_manager.neo4j_driver.session() as session:
                result = await session.run("""
                    MATCH (u:User {id: $user_id})-[r]-(n)
                    WHERE r.bot_name = $bot_name
                    DELETE r
                    RETURN count(r) as deleted
                """, user_id=user_id, bot_name=bot_name)
                record = await result.single()
                knowledge_cleared = record["deleted"] if record else 0
        except Exception as e:
            logger.error(f"Failed to clear knowledge: {e}")
    
    return ClearUserDataResponse(
        success=True,
        user_id=user_id,
        memories_cleared=memories_cleared,
        trust_reset=trust_reset,
        knowledge_cleared=knowledge_cleared
    )


@router.post(
    "/api/user-graph",
    response_model=UserGraphResponse,
    summary="Get user's knowledge graph for visualization",
    description="""
    Returns the user's knowledge graph subgraph in a D3.js-compatible format.
    
    The graph walks from the user node, discovering connected entities, topics,
    and relationships. Use this for:
    - Visualizing what the bot knows about a user
    - Debugging knowledge graph content
    - Building interactive graph UIs
    
    **Performance**: Graph walk typically takes 200-500ms for depth 2, 
    500-1500ms for depth 3-4.
    """,
    tags=["diagnostics"]
)
async def get_user_graph(request: UserGraphRequest) -> UserGraphResponse:
    """Get user's knowledge graph for visualization."""
    bot_name = settings.DISCORD_BOT_NAME
    user_id = request.user_id
    
    # Check if Neo4j is available
    if not db_manager.neo4j_driver:
        raise HTTPException(
            status_code=503,
            detail="Knowledge graph (Neo4j) is not available"
        )
    
    try:
        start_time = time.time()
        
        # Use GraphWalker to explore from the user's node
        walker = GraphWalker()
        result = await walker.explore(
            seed_ids=[user_id],
            user_id=user_id,
            bot_name=bot_name,
            max_depth=request.depth,
            max_nodes=request.max_nodes,
            serendipity=0.05,  # Low serendipity for user-facing view
            min_score=0.2
        )
        
        # Filter out other users if requested
        nodes_to_include = result.nodes
        if not request.include_other_users:
            nodes_to_include = [
                n for n in result.nodes 
                if n.label != "User" or n.id == user_id
            ]
        
        # Build node ID set for edge filtering
        included_ids = {n.id for n in nodes_to_include}
        
        # Filter edges to only include nodes we're keeping
        edges_to_include = [
            e for e in result.edges
            if e.source_id in included_ids and e.target_id in included_ids
        ]
        
        # Convert to API response format
        api_nodes = [
            GraphNode(
                id=n.id,
                label=n.label,
                name=n.name,
                score=n.score,
                properties=n.properties
            )
            for n in nodes_to_include
        ]
        
        api_edges = [
            GraphEdge(
                source=e.source_id,
                target=e.target_id,
                edge_type=e.edge_type,
                properties=e.properties
            )
            for e in edges_to_include
        ]
        
        api_clusters = [
            GraphCluster(
                theme=c.theme,
                node_ids=[n.id for n in c.nodes if n.id in included_ids],
                cohesion_score=c.cohesion_score
            )
            for c in result.clusters
            if any(n.id in included_ids for n in c.nodes)
        ]
        
        processing_time = (time.time() - start_time) * 1000
        
        return UserGraphResponse(
            success=True,
            user_id=user_id,
            bot_name=bot_name,
            nodes=api_nodes,
            edges=api_edges,
            clusters=api_clusters,
            stats={
                "node_count": len(api_nodes),
                "edge_count": len(api_edges),
                "cluster_count": len(api_clusters),
                "max_depth": request.depth,
                "processing_time_ms": round(processing_time, 2),
                "walk_stats": result.walk_stats
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get user graph for {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve user graph: {str(e)}"
        )
