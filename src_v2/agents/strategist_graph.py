"""
Goal Strategist Graph Agent

LangGraph-based agent for nightly goal planning and strategy generation.
Uses tools to explore options, check progress, and propose updates.

Replaces the single-shot GoalStrategist with a multi-step planning loop.
"""
import operator
from typing import List, Optional, Dict, Any, TypedDict, Annotated, Literal
from loguru import logger
from langsmith import traceable
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field, field_validator

from src_v2.agents.llm_factory import create_llm
from src_v2.core.database import db_manager
from src_v2.core.behavior import load_behavior_profile
from src_v2.config.settings import settings
from src_v2.utils.llm_retry import invoke_with_retry


# ============================================================================
# Output Models
# ============================================================================

class GoalStrategy(BaseModel):
    goal_slug: str = Field(description="The goal this strategy is for")
    strategy: str = Field(description="Natural strategy framed as internal desire")
    reasoning: str = Field(description="Why this approach makes sense")
    confidence: float = Field(ge=0, le=1, description="Confidence in this strategy")


class NewGoal(BaseModel):
    slug: str = Field(description="Unique snake_case identifier")
    description: str = Field(description="What the character wants to accomplish")
    success_criteria: str = Field(description="Specific observable outcome")
    priority: int = Field(ge=1, le=10, description="Priority 1-10 (1=highest, 10=lowest)")
    category: str = Field(description="community_growth, personal_growth, or investigation")
    reasoning: str = Field(description="Why this goal fits now")

    @field_validator("priority", mode="before")
    @classmethod
    def clamp_priority(cls, v: Any) -> int:
        """Clamp priority to valid range 1-10, handling LLM edge cases."""
        if v is None:
            return 5  # Default to medium priority
        try:
            val = int(v)
            return max(1, min(10, val))  # Clamp to 1-10
        except (ValueError, TypeError):
            return 5


class StrategistOutput(BaseModel):
    strategies: List[GoalStrategy] = Field(default_factory=list, description="Strategies for existing goals")
    new_goals: List[NewGoal] = Field(default_factory=list, description="New goals to create")
    summary: str = Field(description="Brief summary of strategist session")


# ============================================================================
# State
# ============================================================================

class StrategistState(TypedDict):
    # Inputs
    character_name: str
    character_identity: str
    
    # Gathered data
    existing_goals: List[Dict[str, Any]]
    community_themes: str
    user_facts: Dict[str, str]  # user_id -> facts summary
    
    # Processing
    messages: Annotated[List[BaseMessage], operator.add]
    tools: List[BaseTool]
    steps: int
    max_steps: int
    
    # Output
    output: Optional[StrategistOutput]


# ============================================================================
# Tools for Strategist
# ============================================================================

class GetActiveGoalsTool(BaseTool):
    """Gets all active goals for the character."""
    name: str = "get_active_goals"
    description: str = "Get all active goals for this character, including progress and current strategies."
    
    character_name: str = Field(exclude=True)
    
    def _run(self) -> str:
        raise NotImplementedError("Use _arun")
    
    async def _arun(self) -> str:
        try:
            if not db_manager.postgres_pool:
                return "Database not available."
            
            async with db_manager.postgres_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT slug, description, success_criteria,
                           current_strategy, source, category, target_user_id
                    FROM v2_goals 
                    WHERE character_name = $1
                    AND (expires_at IS NULL OR expires_at > NOW())
                    AND is_active = true
                    ORDER BY priority DESC
                    LIMIT 20
                """, self.character_name)
                
                if not rows:
                    return "No active goals found."
                
                result = []
                for row in rows:
                    user_note = f" (for user {row['target_user_id']})" if row['target_user_id'] else ""
                    strategy_note = f"\n  Current strategy: {row['current_strategy']}" if row['current_strategy'] else ""
                    result.append(f"""
- [{row['slug']}] {row['description']}{user_note}
  Category: {row['category']} | Source: {row['source']}
  Criteria: {row['success_criteria']}{strategy_note}
""")
                
                return "\n".join(result)
                
        except Exception as e:
            logger.error(f"Failed to get goals: {e}")
            return f"Error: {e}"


class GetCommunityThemesTool(BaseTool):
    """Gets recent community themes from summaries."""
    name: str = "get_community_themes"
    description: str = "Get trending topics and themes from recent community conversations."
    
    character_name: str = Field(exclude=True)
    
    def _run(self) -> str:
        raise NotImplementedError("Use _arun")
    
    async def _arun(self) -> str:
        try:
            from src_v2.memory.manager import memory_manager
            
            collection = f"whisperengine_memory_{self.character_name}"
            summaries = await memory_manager.get_summaries_since(
                hours=48,
                limit=20,
                collection_name=collection
            )
            
            if not summaries:
                return "No recent community activity found."
            
            from collections import Counter
            topics = []
            emotions = []
            
            for s in summaries:
                topics.extend(s.get("topics", []))
                emotions.extend(s.get("emotions", []))
            
            topic_counts = Counter(topics).most_common(10)
            emotion_counts = Counter(emotions).most_common(5)
            
            result = ["Trending topics (last 48h):"]
            for topic, count in topic_counts:
                result.append(f"  - {topic}: {count} mentions")
            
            result.append("\nPrevailing emotions:")
            for emotion, count in emotion_counts:
                result.append(f"  - {emotion}: {count} occurrences")
            
            return "\n".join(result)
            
        except Exception as e:
            logger.error(f"Failed to get community themes: {e}")
            return f"Error: {e}"


class GetUserFactsTool(BaseTool):
    """Gets facts about a specific user for goal strategy."""
    name: str = "get_user_facts"
    description: str = "Get known facts about a specific user from knowledge graph. Use this before generating a strategy for user-specific goals."
    
    character_name: str = Field(exclude=True)
    
    class InputSchema(BaseModel):
        user_id: str = Field(description="The user ID to query facts for")
    
    args_schema: type = InputSchema
    
    def _run(self, user_id: str) -> str:
        raise NotImplementedError("Use _arun")
    
    async def _arun(self, user_id: str) -> str:
        try:
            if not db_manager.neo4j_driver:
                return f"Knowledge graph not available."
            
            async with db_manager.neo4j_driver.session() as session:
                result = await session.run("""
                    MATCH (u:User {id: $user_id})-[r]->(e)
                    RETURN type(r) as relationship, e.name as entity
                    ORDER BY r.confidence DESC
                    LIMIT 10
                """, user_id=user_id)
                
                records = await result.data()
                
                if not records:
                    return f"No facts found for user {user_id}."
                
                facts = [f"Facts about user {user_id}:"]
                for record in records:
                    facts.append(f"  - User {record['relationship'].lower()} {record['entity']}")
                
                return "\n".join(facts)
                
        except Exception as e:
            logger.error(f"Failed to get user facts: {e}")
            return f"Error: {e}"


class GetRecentHistoryTool(BaseTool):
    """Gets recent chat history with a user."""
    name: str = "get_recent_history"
    description: str = "Get recent conversation history with a specific user. Useful for understanding context before generating strategies."
    
    character_name: str = Field(exclude=True)
    
    class InputSchema(BaseModel):
        user_id: str = Field(description="The user ID to get history for")
    
    args_schema: type = InputSchema
    
    def _run(self, user_id: str) -> str:
        raise NotImplementedError("Use _arun")
    
    async def _arun(self, user_id: str) -> str:
        try:
            if not db_manager.postgres_pool:
                return "Database not available."
            
            async with db_manager.postgres_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT role, content 
                    FROM v2_chat_history 
                    WHERE user_id = $1 AND character_name = $2
                    ORDER BY timestamp DESC 
                    LIMIT 10
                """, user_id, self.character_name)
                
                if not rows:
                    return f"No recent history with user {user_id}."
                
                lines = [f"Recent conversation with user {user_id}:"]
                for row in reversed(rows):
                    role = "User" if row["role"] == "user" else self.character_name
                    content = row["content"][:150]
                    lines.append(f"  {role}: {content}...")
                
                return "\n".join(lines)
                
        except Exception as e:
            logger.error(f"Failed to get history: {e}")
            return f"Error: {e}"


def get_strategist_tools(character_name: str) -> List[BaseTool]:
    """Creates tools for the strategist agent."""
    return [
        GetActiveGoalsTool(character_name=character_name),
        GetCommunityThemesTool(character_name=character_name),
        GetUserFactsTool(character_name=character_name),
        GetRecentHistoryTool(character_name=character_name),
    ]


# ============================================================================
# Graph Agent
# ============================================================================

class StrategistGraphAgent:
    """
    LangGraph agent for goal strategy and planning.
    
    Flow:
    1. Gather: Get current goals and community themes
    2. Reason: Use ReAct loop to explore options and check user facts
    3. Synthesize: Generate strategies and propose new goals
    """
    
    def __init__(self):
        self.llm = create_llm(temperature=0.7, mode="reflective")
        self.structured_llm = self.llm.with_structured_output(StrategistOutput)
        
        # Build graph
        workflow = StateGraph(StrategistState)
        
        workflow.add_node("gather", self.gather_context)
        workflow.add_node("reason", self.reason_step)
        workflow.add_node("synthesize", self.synthesize_output)
        
        workflow.set_entry_point("gather")
        workflow.add_edge("gather", "reason")
        workflow.add_conditional_edges(
            "reason",
            self.should_continue,
            {
                "continue": "reason",
                "synthesize": "synthesize"
            }
        )
        workflow.add_edge("synthesize", END)
        
        self.graph = workflow.compile()
    
    def should_continue(self, state: StrategistState) -> Literal["continue", "synthesize"]:
        """Decide whether to continue reasoning or synthesize."""
        messages = state["messages"]
        last_message = messages[-1] if messages else None
        
        # If last message has tool calls, continue
        if last_message and isinstance(last_message, AIMessage) and last_message.tool_calls:
            if state["steps"] < state["max_steps"]:
                return "continue"
        
        return "synthesize"
    
    @traceable(name="strategist_gather")
    async def gather_context(self, state: StrategistState) -> Dict[str, Any]:
        """Gather initial context using tools."""
        import asyncio
        
        tools = get_strategist_tools(state["character_name"])
        
        # Get goals and themes in parallel
        goals_result, themes_result = await asyncio.gather(
            tools[0]._arun(),  # active goals
            tools[1]._arun(),  # community themes
            return_exceptions=True
        )
        
        goals_text = goals_result if not isinstance(goals_result, Exception) else "Error fetching goals"
        themes_text = themes_result if not isinstance(themes_result, Exception) else "Error fetching themes"
        
        system_prompt = f"""You are the Goal Strategist for {state['character_name']}.
Your job is to analyze goals and generate strategies for achieving them.

CHARACTER IDENTITY:
{state['character_identity']}

CURRENT GOALS:
{goals_text}

COMMUNITY THEMES (recent activity):
{themes_text}

YOUR TASKS:
1. For each goal WITHOUT a strategy, generate a natural strategy
2. Identify if any NEW goals should be created based on community themes
3. Use tools to get more context about specific users if needed

STRATEGY RULES:
- Frame strategies as internal desires, not commands
  Good: "I'm curious to learn more about their creative projects"
  Bad: "Ask user about hobbies"
- Strategies should be achievable in a single conversation
- Base strategies on what we KNOW about the user (use tools to check)

NEW GOAL RULES:
- Only suggest 1-2 new goals if there's a clear gap or opportunity
- Goals must align with character identity
- Goals expire after 30 days (community trends change)
- Don't duplicate existing goals

AVAILABLE TOOLS:
- get_user_facts(user_id): Get known facts about a user
- get_recent_history(user_id): Get recent conversation history

When you have enough information, stop using tools and I will ask for your final output."""

        return {
            "messages": [SystemMessage(content=system_prompt)],
            "tools": tools,
            "steps": 0
        }
    
    @traceable(name="strategist_reason")
    async def reason_step(self, state: StrategistState) -> Dict[str, Any]:
        """ReAct step: reason about goals and optionally use tools."""
        
        tools = state["tools"]
        messages = state["messages"]
        
        # Bind tools to LLM
        llm_with_tools = self.llm.bind_tools(tools)
        
        # Add reasoning prompt if this is the first step
        if state["steps"] == 0:
            messages = messages + [HumanMessage(content="Analyze the goals and decide if you need more information about any users. Use tools to gather context, then stop when ready.")]
        
        # LLM call with retry for transient errors
        response = await invoke_with_retry(llm_with_tools.ainvoke, messages, max_retries=3)
        new_messages: List[BaseMessage] = [response]
        
        # Execute any tool calls
        if isinstance(response, AIMessage) and response.tool_calls:
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_id = tool_call["id"]
                
                logger.info(f"Strategist executing: {tool_name}({tool_args})")
                
                selected_tool = next((t for t in tools if t.name == tool_name), None)
                if selected_tool:
                    try:
                        if tool_args:
                            result = await selected_tool._arun(**tool_args)
                        else:
                            result = await selected_tool._arun()
                    except Exception as e:
                        result = f"Error: {e}"
                else:
                    result = f"Tool {tool_name} not found"
                
                new_messages.append(ToolMessage(content=result, tool_call_id=tool_id))
        
        return {
            "messages": new_messages,
            "steps": state["steps"] + 1
        }
    
    @traceable(name="strategist_synthesize")
    async def synthesize_output(self, state: StrategistState) -> Dict[str, Any]:
        """Generate final structured output."""
        
        synthesis_prompt = """Based on your analysis, generate the final StrategistOutput.

For strategies:
- Only generate for goals that don't have a current_strategy
- Frame as natural internal desires
- Include confidence score (0.4+ to be used)

For new goals:
- Only if there's a clear opportunity from community themes
- 1-2 max, must align with character identity
- Include reasoning

Provide a brief summary of what you accomplished."""

        messages = state["messages"] + [HumanMessage(content=synthesis_prompt)]
        
        try:
            # LLM call with retry for transient errors
            output = await invoke_with_retry(self.structured_llm.ainvoke, messages, max_retries=3)
            return {"output": output}
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            return {"output": StrategistOutput(strategies=[], new_goals=[], summary=f"Error: {e}")}
    
    async def _check_data_availability(self, character_name: str) -> tuple[bool, str]:
        """
        Check if there's enough data to run the strategist.
        
        Returns:
            (has_enough_data, reason) - If False, reason explains why.
        """
        if not db_manager.postgres_pool:
            return False, "Database not available"
        
        try:
            async with db_manager.postgres_pool.acquire() as conn:
                # Check if we have any active goals for this character
                goal_count = await conn.fetchval("""
                    SELECT COUNT(*) FROM v2_goals 
                    WHERE character_name = $1
                    AND (expires_at IS NULL OR expires_at > NOW())
                    AND is_active = true
                """, character_name)
                
                # Check if we have any recent community activity (last 48h)
                from src_v2.memory.manager import memory_manager
                collection = f"whisperengine_memory_{character_name}"
                
                try:
                    summaries = await memory_manager.get_summaries_since(
                        hours=48,
                        limit=5,
                        collection_name=collection
                    )
                    has_community_data = len(summaries) > 0 if summaries else False
                except Exception:
                    has_community_data = False
                
                # Need at least goals OR community data to be useful
                if goal_count == 0 and not has_community_data:
                    return False, "No active goals and no recent community activity"
                
                # If we only have goals without strategies, that's still useful
                if goal_count > 0:
                    goals_without_strategy = await conn.fetchval("""
                        SELECT COUNT(*) FROM v2_goals 
                        WHERE character_name = $1
                        AND (expires_at IS NULL OR expires_at > NOW())
                        AND is_active = true
                        AND (current_strategy IS NULL OR current_strategy = '')
                    """, character_name)
                    
                    if goals_without_strategy > 0:
                        return True, f"{goals_without_strategy} goals need strategies"
                
                # If we have community data, we might find new goal opportunities
                if has_community_data:
                    return True, "Has community data to analyze"
                
                # All goals already have strategies and no community data
                return False, "All goals have strategies, no new opportunities"
                
        except Exception as e:
            logger.error(f"Data availability check failed: {e}")
            return False, f"Check failed: {e}"

    @traceable(name="strategist_graph_run")
    async def run(self, character_name: str) -> Optional[StrategistOutput]:
        """
        Main entry point for nightly goal strategist.
        
        Returns:
            StrategistOutput with strategies and new goals
        """
        # Check data availability before expensive LLM calls
        has_data, reason = await self._check_data_availability(character_name)
        if not has_data:
            logger.info(f"Strategist skipped for {character_name}: {reason}")
            return StrategistOutput(
                strategies=[],
                new_goals=[],
                summary=f"Skipped: {reason}. No LLM calls made."
            )
        
        logger.info(f"Strategist starting for {character_name}: {reason}")
        
        # Load character identity
        character_identity = "A helpful AI assistant."
        try:
            character_dir = f"characters/{character_name}"
            behavior = load_behavior_profile(character_dir)
            if behavior:
                character_identity = behavior.to_prompt_section()
        except Exception:
            pass
        
        initial_state: StrategistState = {
            "character_name": character_name,
            "character_identity": character_identity,
            "existing_goals": [],
            "community_themes": "",
            "user_facts": {},
            "messages": [],
            "tools": [],
            "steps": 0,
            "max_steps": 5,  # Allow up to 5 tool calls
            "output": None,
        }
        
        try:
            final_state = await self.graph.ainvoke(initial_state)
            return final_state.get("output")
        except Exception as e:
            logger.error(f"Strategist graph failed: {e}")
            return None


# ============================================================================
# Persistence Helpers
# ============================================================================

async def save_strategist_output(
    character_name: str,
    output: StrategistOutput
) -> Dict[str, Any]:
    """Saves strategist output to the database."""
    from datetime import datetime, timedelta
    
    results = {
        "strategies_applied": 0,
        "goals_created": 0
    }
    
    if not db_manager.postgres_pool:
        return results
    
    try:
        async with db_manager.postgres_pool.acquire() as conn:
            # 1. Apply strategies
            for strategy in output.strategies:
                if strategy.confidence >= 0.4:
                    await conn.execute("""
                        UPDATE v2_goals 
                        SET current_strategy = $1
                        WHERE character_name = $2 AND slug = $3
                    """, strategy.strategy, character_name, strategy.goal_slug)
                    results["strategies_applied"] += 1
                    logger.info(f"Applied strategy for goal '{strategy.goal_slug}'")
            
            # 2. Create new goals
            expires_at = datetime.now() + timedelta(days=30)
            
            for goal in output.new_goals:
                exists = await conn.fetchval("""
                    SELECT id FROM v2_goals 
                    WHERE character_name = $1 AND slug = $2
                """, character_name, goal.slug)
                
                if not exists:
                    await conn.execute("""
                        INSERT INTO v2_goals (
                            character_name, slug, description, success_criteria,
                            priority, source, category, expires_at
                        )
                        VALUES ($1, $2, $3, $4, $5, 'strategic', $6, $7)
                    """, 
                        character_name, 
                        goal.slug, 
                        goal.description,
                        goal.success_criteria,
                        goal.priority,
                        goal.category,
                        expires_at
                    )
                    results["goals_created"] += 1
                    logger.info(f"Created strategic goal '{goal.slug}' (expires: {expires_at.date()})")
                    
    except Exception as e:
        logger.error(f"Failed to save strategist output: {e}")
    
    return results


# Singleton instance
strategist_graph_agent = StrategistGraphAgent()
