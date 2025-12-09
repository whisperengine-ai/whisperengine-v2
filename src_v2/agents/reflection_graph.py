"""
Reflection Graph Agent

LangGraph-based agent for analyzing user patterns across summaries,
knowledge graph, and observations. Generates insights and infers goals.

Replaces the single-shot ReflectionEngine with a multi-step reasoning loop.
"""
import operator
from typing import List, Optional, Dict, Any, TypedDict, Annotated, Literal
from loguru import logger
from langsmith import traceable
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field

from src_v2.agents.llm_factory import create_llm
from src_v2.core.database import db_manager
from src_v2.core.behavior import load_behavior_profile
from src_v2.config.settings import settings


# ============================================================================
# Output Models
# ============================================================================

class InferredGoal(BaseModel):
    slug: str = Field(description="Unique snake_case identifier for the goal")
    description: str = Field(description="What the character should work towards with this user")
    success_criteria: str = Field(description="How to know when the goal is achieved")
    priority: int = Field(default=5, description="Priority 1-10")
    reasoning: str = Field(description="Why this goal was inferred from patterns")


class ReflectionOutput(BaseModel):
    insights: List[str] = Field(description="High-level insights about the USER's personality, values, and behavior patterns")
    updated_traits: List[str] = Field(description="Personality traits observed in the USER (not the character)")
    inferred_goals: List[InferredGoal] = Field(default_factory=list, description="Goals the character should pursue with this user, inferred from patterns")


# ============================================================================
# State
# ============================================================================

class ReflectionState(TypedDict):
    # Inputs
    user_id: str
    character_name: str
    character_identity: str
    
    # Gathered data
    summaries: List[Dict[str, Any]]
    facts: List[str]
    observations: List[str]
    
    # Processing
    messages: Annotated[List[BaseMessage], operator.add]
    steps: int
    max_steps: int
    
    # Output
    output: Optional[ReflectionOutput]


# ============================================================================
# Tools for Reflection
# ============================================================================

class QuerySummariesTool(BaseTool):
    """Queries recent conversation summaries."""
    name: str = "query_summaries"
    description: str = "Get recent conversation summaries for the user. Returns summaries with timestamps and meaningfulness scores."
    
    user_id: str = Field(exclude=True)
    character_name: str = Field(exclude=True)
    
    def _run(self) -> str:
        raise NotImplementedError("Use _arun")
    
    async def _arun(self) -> str:
        try:
            if not db_manager.postgres_pool:
                return "Database not available."
            
            async with db_manager.postgres_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT s.content, s.meaningfulness_score, sess.start_time
                    FROM v2_summaries s
                    JOIN v2_conversation_sessions sess ON s.session_id = sess.id
                    WHERE sess.user_id = $1 AND sess.character_name = $2
                    ORDER BY sess.start_time DESC
                    LIMIT 10
                """, self.user_id, self.character_name)
                
                if not rows:
                    return "No summaries found for this user."
                
                result = []
                for row in rows:
                    result.append(f"[{row['start_time'].strftime('%Y-%m-%d')}] (Score: {row['meaningfulness_score']}) {row['content']}")
                
                return "\n".join(result)
                
        except Exception as e:
            logger.error(f"Failed to query summaries: {e}")
            return f"Error querying summaries: {e}"


class QueryKnowledgeGraphTool(BaseTool):
    """Queries the knowledge graph for user facts."""
    name: str = "query_knowledge_graph"
    description: str = "Get known facts about the user from the knowledge graph. Returns relationships and entities."
    
    user_id: str = Field(exclude=True)
    character_name: str = Field(exclude=True)
    
    def _run(self) -> str:
        raise NotImplementedError("Use _arun")
    
    async def _arun(self) -> str:
        try:
            if not db_manager.neo4j_driver:
                return "Knowledge graph not available."
            
            async with db_manager.neo4j_driver.session() as session:
                result = await session.run("""
                    MATCH (u:User {id: $user_id})-[r]->(e)
                    RETURN type(r) as relationship, labels(e)[0] as entity_type, e.name as entity, r.confidence as confidence
                    ORDER BY r.confidence DESC
                    LIMIT 20
                """, user_id=self.user_id)
                
                records = await result.data()
                
                if not records:
                    return "No facts found in knowledge graph for this user."
                
                facts = []
                for record in records:
                    conf = record.get('confidence', 'unknown')
                    facts.append(f"- User {record['relationship'].lower()} {record['entity']} ({record['entity_type']}) [confidence: {conf}]")
                
                return "\n".join(facts)
                
        except Exception as e:
            logger.error(f"Failed to query knowledge graph: {e}")
            return f"Error querying knowledge graph: {e}"


class QueryObservationsTool(BaseTool):
    """Queries stigmergic observations about the user."""
    name: str = "query_observations"
    description: str = "Get observations made about this user by any bot (mood patterns, behavior trends)."
    
    user_id: str = Field(exclude=True)
    character_name: str = Field(exclude=True)
    
    def _run(self) -> str:
        raise NotImplementedError("Use _arun")
    
    async def _arun(self) -> str:
        try:
            if not db_manager.neo4j_driver:
                return "Knowledge graph not available."
            
            async with db_manager.neo4j_driver.session() as session:
                result = await session.run("""
                    MATCH (u:User {id: $user_id})<-[:ABOUT]-(o:Observation)
                    RETURN o.type as type, o.content as content, o.observer as observer, o.timestamp as timestamp
                    ORDER BY o.timestamp DESC
                    LIMIT 10
                """, user_id=self.user_id)
                
                records = await result.data()
                
                if not records:
                    return "No observations found for this user."
                
                observations = []
                for record in records:
                    observations.append(f"- [{record['type']}] {record['content']} (by {record['observer']})")
                
                return "\n".join(observations)
                
        except Exception as e:
            logger.error(f"Failed to query observations: {e}")
            return f"Error querying observations: {e}"


class GetExistingInsightsTool(BaseTool):
    """Gets existing insights about the user to avoid duplication."""
    name: str = "get_existing_insights"
    description: str = "Get insights already stored for this user to avoid generating duplicates."
    
    user_id: str = Field(exclude=True)
    character_name: str = Field(exclude=True)
    
    def _run(self) -> str:
        raise NotImplementedError("Use _arun")
    
    async def _arun(self) -> str:
        try:
            if not db_manager.postgres_pool:
                return "Database not available."
            
            async with db_manager.postgres_pool.acquire() as conn:
                data = await conn.fetchval("""
                    SELECT insights 
                    FROM v2_user_relationships 
                    WHERE user_id = $1 AND character_name = $2
                """, self.user_id, self.character_name)
                
                if not data:
                    return "No existing insights found."
                
                if isinstance(data, list):
                    return "Existing insights:\n" + "\n".join(f"- {i}" for i in data)
                return f"Existing insights: {data}"
                
        except Exception as e:
            logger.error(f"Failed to get existing insights: {e}")
            return f"Error: {e}"


def get_reflection_tools(user_id: str, character_name: str) -> List[BaseTool]:
    """Creates tools for the reflection agent."""
    return [
        QuerySummariesTool(user_id=user_id, character_name=character_name),
        QueryKnowledgeGraphTool(user_id=user_id, character_name=character_name),
        QueryObservationsTool(user_id=user_id, character_name=character_name),
        GetExistingInsightsTool(user_id=user_id, character_name=character_name),
    ]


# ============================================================================
# Graph Agent
# ============================================================================

class ReflectionGraphAgent:
    """
    LangGraph agent for deep reflection on user patterns.
    
    Flow:
    1. Gather: Query summaries, knowledge graph, observations in parallel
    2. Synthesize: Analyze patterns and generate insights
    3. Validate: Check against existing insights to avoid duplicates
    4. Output: Return structured ReflectionOutput
    """
    
    def __init__(self):
        self.llm = create_llm(temperature=0.4, mode="reflective")
        self.structured_llm = self.llm.with_structured_output(ReflectionOutput)
        
        # Build graph
        workflow = StateGraph(ReflectionState)
        
        workflow.add_node("gather", self.gather_data)
        workflow.add_node("synthesize", self.synthesize_insights)
        
        workflow.set_entry_point("gather")
        workflow.add_edge("gather", "synthesize")
        workflow.add_edge("synthesize", END)
        
        self.graph = workflow.compile()
    
    @traceable(name="reflection_gather")
    async def gather_data(self, state: ReflectionState) -> Dict[str, Any]:
        """Gather all relevant data using tools."""
        import asyncio
        
        tools = get_reflection_tools(state["user_id"], state["character_name"])
        
        # Run all queries in parallel
        results = await asyncio.gather(
            tools[0]._arun(),  # summaries
            tools[1]._arun(),  # knowledge graph
            tools[2]._arun(),  # observations
            tools[3]._arun(),  # existing insights
            return_exceptions=True
        )
        
        summaries_text = results[0] if not isinstance(results[0], Exception) else "Error fetching summaries"
        facts_text = results[1] if not isinstance(results[1], Exception) else "Error fetching facts"
        observations_text = results[2] if not isinstance(results[2], Exception) else "Error fetching observations"
        existing_text = results[3] if not isinstance(results[3], Exception) else ""
        
        return {
            "messages": [
                SystemMessage(content=f"""You are analyzing patterns about USER {state['user_id']} from the perspective of {state['character_name']}.

IMPORTANT: You are analyzing THE USER, not the character. The character context below is provided so you understand the relationship dynamic and can phrase goals in the character's voice.

CHARACTER CONTEXT (for voice/perspective, NOT the subject of analysis):
{state['character_identity']}

GATHERED DATA ABOUT THE USER:

## Recent Conversation Summaries (user's interactions with this character):
{summaries_text}

## Knowledge Graph Facts (what we know about the user):
{facts_text}

## Observations from Bots (patterns noticed about the user):
{observations_text}

## Existing User Insights (avoid duplicates):
{existing_text}
""")
            ]
        }
    
    @traceable(name="reflection_synthesize")
    async def synthesize_insights(self, state: ReflectionState) -> Dict[str, Any]:
        """Synthesize insights from gathered data."""
        
        synthesis_prompt = f"""Based on the data gathered, generate a ReflectionOutput analyzing THE USER (not {state['character_name']}).

CRITICAL: You are profiling the HUMAN USER, not the AI character. The insights and traits describe the user's personality.

RULES:
1. Insights should be HIGH-LEVEL observations about THE USER (not just facts we already know)
   - Good: "The user values authenticity and dislikes small talk"
   - Bad: "The user has a cat named Whiskers" (this is a fact, not an insight)
   - Bad: "{state['character_name']} values connection" (this describes the character, not the user)

2. Traits should be THE USER's PERSONALITY characteristics
   - Good: "Introverted", "Analytical", "Empathetic"
   - Bad: "Works in tech" (this is a fact about the user)
   - Bad: "Warm and curious" (unless this describes THE USER, not the character)

3. Inferred Goals should be things {state['character_name']} should work towards WITH this user:
   - Only generate if there's a CLEAR pattern in the user's behavior (mentioned 3+ times, expressed need)
   - Goals describe what the CHARACTER should do FOR/WITH the user
   - Use the character's voice/style in the goal descriptions
   - Example: "Help the user explore their interest in philosophy" (goal for character to pursue)

4. Avoid duplicating existing insights.

5. If you don't have enough data for meaningful insights about the user, return empty lists.

Generate the structured output now, focusing on THE USER's patterns and personality."""

        messages = state["messages"] + [HumanMessage(content=synthesis_prompt)]
        
        try:
            output = await self.structured_llm.ainvoke(messages)
            return {"output": output}
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            return {"output": ReflectionOutput(insights=[], updated_traits=[], inferred_goals=[])}
    
    async def _check_data_availability(self, user_id: str, character_name: str) -> tuple[bool, str]:
        """
        Check if there's enough data to run reflection analysis.
        
        Returns:
            (has_enough_data, reason) - If False, reason explains why.
        """
        if not db_manager.postgres_pool:
            return False, "Database not available"
        
        try:
            async with db_manager.postgres_pool.acquire() as conn:
                # Check for summaries (primary data source)
                summary_count = await conn.fetchval("""
                    SELECT COUNT(*) 
                    FROM v2_summaries s
                    JOIN v2_conversation_sessions sess ON s.session_id = sess.id
                    WHERE sess.user_id = $1 AND sess.character_name = $2
                """, user_id, character_name)
                
                if summary_count == 0:
                    # Check if we at least have some chat history
                    history_count = await conn.fetchval("""
                        SELECT COUNT(*) FROM v2_chat_history 
                        WHERE user_id = $1 AND character_name = $2
                    """, user_id, character_name)
                    
                    if history_count < 10:
                        return False, f"Insufficient data: {summary_count} summaries, {history_count} messages"
                
                return True, f"{summary_count} summaries available"
                
        except Exception as e:
            logger.error(f"Data availability check failed: {e}")
            return False, f"Check failed: {e}"

    @traceable(name="reflection_graph_analyze")
    async def analyze(
        self,
        user_id: str,
        character_name: str
    ) -> Optional[ReflectionOutput]:
        """
        Main entry point for reflection analysis.
        
        Returns:
            ReflectionOutput with insights, traits, and inferred goals
        """
        # Check data availability before expensive LLM calls
        has_data, reason = await self._check_data_availability(user_id, character_name)
        if not has_data:
            logger.info(f"Reflection skipped for user {user_id}: {reason}")
            return ReflectionOutput(
                insights=[],
                updated_traits=[],
                inferred_goals=[]
            )
        
        logger.info(f"Reflection starting for user {user_id}: {reason}")
        
        # Load character identity
        character_identity = "A helpful AI assistant."
        try:
            character_dir = f"characters/{character_name}"
            behavior = load_behavior_profile(character_dir)
            if behavior:
                character_identity = behavior.to_prompt_section()
        except Exception:
            pass
        
        initial_state: ReflectionState = {
            "user_id": user_id,
            "character_name": character_name,
            "character_identity": character_identity,
            "summaries": [],
            "facts": [],
            "observations": [],
            "messages": [],
            "steps": 0,
            "max_steps": 3,
            "output": None,
        }
        
        try:
            final_state = await self.graph.ainvoke(initial_state)
            return final_state.get("output")
        except Exception as e:
            logger.error(f"Reflection graph failed: {e}")
            return None


# ============================================================================
# Persistence Helpers (moved from ReflectionEngine)
# ============================================================================

async def save_reflection_output(
    user_id: str,
    character_name: str,
    output: ReflectionOutput
) -> None:
    """Saves reflection output to the database."""
    import json
    from datetime import datetime, timedelta
    
    if not db_manager.postgres_pool:
        return
    
    try:
        async with db_manager.postgres_pool.acquire() as conn:
            # 1. Update insights in v2_user_relationships
            current_data = await conn.fetchval("""
                SELECT insights 
                FROM v2_user_relationships 
                WHERE user_id = $1 AND character_name = $2
            """, user_id, character_name)
            
            existing_insights = []
            if current_data:
                if isinstance(current_data, str):
                    existing_insights = json.loads(current_data)
                else:
                    existing_insights = current_data
            
            if not isinstance(existing_insights, list):
                existing_insights = []
            
            # Add new unique insights
            for insight in output.insights:
                if insight not in existing_insights:
                    existing_insights.append(insight)
            
            # Cap at 20 insights
            MAX_INSIGHTS = 20
            if len(existing_insights) > MAX_INSIGHTS:
                existing_insights = existing_insights[-MAX_INSIGHTS:]
            
            await conn.execute("""
                UPDATE v2_user_relationships
                SET insights = $1, updated_at = NOW()
                WHERE user_id = $2 AND character_name = $3
            """, json.dumps(existing_insights), user_id, character_name)
            
            logger.info(f"Updated insights for user {user_id}: {len(output.insights)} new insights")
            
            # 2. Save inferred goals
            if output.inferred_goals:
                expires_at = datetime.now() + timedelta(days=14)
                
                for goal in output.inferred_goals:
                    exists = await conn.fetchval("""
                        SELECT id FROM v2_goals 
                        WHERE character_name = $1 AND slug = $2
                    """, character_name, goal.slug)
                    
                    if not exists:
                        await conn.execute("""
                            INSERT INTO v2_goals (
                                character_name, slug, description, success_criteria, 
                                priority, source, category, current_strategy,
                                target_user_id, expires_at
                            )
                            VALUES ($1, $2, $3, $4, $5, 'inferred', 'user_specific', $6, $7, $8)
                        """, 
                            character_name, 
                            goal.slug, 
                            goal.description, 
                            goal.success_criteria,
                            goal.priority,
                            goal.reasoning,
                            user_id,
                            expires_at
                        )
                        logger.info(f"Created inferred goal '{goal.slug}' for {character_name}/{user_id}")
            
            # 3. Save traits to Neo4j knowledge graph
            if output.updated_traits:
                from src_v2.universe.manager import universe_manager
                for trait in output.updated_traits:
                    try:
                        await universe_manager.add_user_trait(
                            user_id=user_id,
                            trait=trait,
                            category="personality",
                            learned_by=character_name,
                            confidence=0.7
                        )
                    except Exception as trait_error:
                        logger.warning(f"Failed to save trait '{trait}': {trait_error}")
                
                logger.info(f"Saved {len(output.updated_traits)} traits for user {user_id}")
                        
    except Exception as e:
        logger.error(f"Failed to save reflection output: {e}")


# Singleton instance
reflection_graph_agent = ReflectionGraphAgent()
