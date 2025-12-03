import asyncio
import operator
from typing import List, Optional, Tuple, Dict, Any, TypedDict, Annotated, Literal
from loguru import logger
from langsmith import traceable
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, BaseMessage, AIMessage
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, END

from src_v2.agents.llm_factory import create_llm
from src_v2.tools.insight_tools import get_insight_tools_with_existing
from src_v2.config.settings import settings

# Define State
class InsightAgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    steps: int
    artifacts_generated: List[str]
    tools: List[BaseTool]
    max_steps: int

class InsightGraphAgent:
    """
    Executes a ReAct loop for background analysis of user conversations using LangGraph.
    """
    
    def __init__(self):
        # Use reflective model for insight analysis - needs good tool use and reasoning
        self.llm = create_llm(temperature=0.3, mode="reflective")
    
    def _construct_prompt(self, character_name: str, trigger: str) -> str:
        """Builds the system prompt for insight analysis."""
        return f"""You are the Insight Agent for {character_name}, an AI companion.
Your job is to analyze user conversations and generate useful artifacts for future interactions.

TRIGGER: {trigger}
- 'volume': User has sent many messages recently
- 'time': Scheduled periodic analysis
- 'session_end': Conversation session just ended
- 'feedback': User gave positive reactions recently
- 'reflective_completion': A reflective reasoning session just completed (analyze the trace)

YOUR GOALS:
1. ANALYZE patterns in the user's conversation style and topics
2. DETECT recurring themes they care about
3. GENERATE epiphanies - spontaneous realizations that {character_name} can reference later
4. STORE reasoning traces - successful approaches for similar future queries. IMPORTANT: Estimate the complexity (SIMPLE, COMPLEX_LOW, COMPLEX_MID, COMPLEX_HIGH) of the query so we can allocate resources correctly next time.
5. LEARN response patterns - what styles resonate with this user

RULES:
- Be thoughtful but efficient (max 5 tool calls)
- Only generate artifacts if you find something meaningful
- Epiphanies should feel natural, not robotic ("I just realized..." not "Analysis shows...")
- Focus on emotional and relational insights, not just facts
- When storing reasoning traces, accurately estimate complexity (e.g. multi-step research is COMPLEX_HIGH, simple lookups are COMPLEX_LOW)

When done, provide a brief summary of what you learned."""
    
    def _build_analysis_request(self, trigger: str, recent_context: Optional[str] = None) -> str:
        """Builds the initial analysis request."""
        base = f"Please analyze this user's conversation patterns and generate any useful insights."
        
        if trigger == "feedback":
            base += " They recently gave positive feedback, so focus on what resonated with them."
        elif trigger == "session_end":
            base += " Their session just ended, so look for themes from this conversation."
        elif trigger == "volume":
            base += " They've been very active, so look for patterns in their engagement."
        elif trigger == "reflective_completion":
            base = "A reflective reasoning session just completed. Analyze the trace below and store it as a reasoning pattern for similar future queries. Focus on: query type, tools used, and complexity level."
            
        if recent_context:
            base += f"\n\nRecent context:\n{recent_context}"
            
        return base

    async def _execute_tool_wrapper(self, tool_call: Any, tools: List[BaseTool]) -> Tuple[ToolMessage, Optional[str]]:
        """Executes a tool and returns the message and artifact name if generated."""
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_call_id = tool_call["id"]
        
        logger.info(f"Insight Agent executing: {tool_name}")
        
        selected_tool = next((t for t in tools if t.name == tool_name), None)
        artifact = None
        
        if selected_tool:
            try:
                observation = await selected_tool.ainvoke(tool_args)
                # Track artifact generation
                if tool_name in ["generate_epiphany", "store_reasoning_trace", "learn_response_pattern"]:
                    artifact = tool_name
            except Exception as e:
                observation = f"Error: {e}"
                logger.error(f"Insight tool {tool_name} failed: {e}")
        else:
            observation = f"Tool {tool_name} not found"
            
        return ToolMessage(
            content=str(observation),
            tool_call_id=tool_call_id,
            name=tool_name
        ), artifact

    # --- Graph Nodes ---

    async def agent_node(self, state: InsightAgentState):
        messages = state['messages']
        tools = state['tools']
        
        llm_with_tools = self.llm.bind_tools(tools)
        
        try:
            response = await llm_with_tools.ainvoke(messages)
            return {"messages": [response], "steps": state['steps'] + 1}
        except Exception as e:
            logger.error(f"Insight Agent LLM failed: {e}")
            return {"messages": [AIMessage(content="Analysis failed due to error.")], "steps": state['steps'] + 1}

    async def tools_node(self, state: InsightAgentState):
        messages = state['messages']
        last_message = messages[-1]
        tools = state['tools']
        
        if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
            return {"messages": []}
            
        tasks = []
        for tool_call in last_message.tool_calls:
            tasks.append(self._execute_tool_wrapper(tool_call, tools))
            
        results = await asyncio.gather(*tasks)
        
        tool_messages = []
        new_artifacts = []
        
        for msg, artifact in results:
            tool_messages.append(msg)
            if artifact:
                new_artifacts.append(artifact)
                
        return {
            "messages": tool_messages, 
            "artifacts_generated": state['artifacts_generated'] + new_artifacts
        }

    def should_continue(self, state: InsightAgentState) -> Literal["tools", "end"]:
        messages = state['messages']
        last_message = messages[-1]
        
        if state['steps'] >= state['max_steps']:
            return "end"
            
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "tools"
            
        return "end"

    async def _check_data_availability(
        self,
        user_id: str,
        character_name: str,
        trigger: str,
        recent_context: Optional[str]
    ) -> tuple[bool, str]:
        """
        Check if there's enough data to run insight analysis.
        
        Returns:
            (has_enough_data, reason) - If False, reason explains why.
        """
        # If we have explicit recent_context, we have enough data
        if recent_context and len(recent_context) > 50:
            return True, "Has recent context provided"
        
        # For reflective_completion trigger, we always run (trace analysis)
        if trigger == "reflective_completion":
            return True, "Reflective completion trigger"
        
        # Check database for user interaction history
        from src_v2.core.database import db_manager
        
        if not db_manager.postgres_pool:
            return False, "Database not available"
        
        try:
            async with db_manager.postgres_pool.acquire() as conn:
                # Check recent message count (last 24h)
                message_count = await conn.fetchval("""
                    SELECT COUNT(*) FROM v2_chat_history 
                    WHERE user_id = $1 AND character_name = $2
                    AND created_at > NOW() - INTERVAL '24 hours'
                """, user_id, character_name)
                
                if message_count < 5:
                    return False, f"Only {message_count} messages in last 24h (need 5+)"
                
                return True, f"{message_count} messages in last 24h"
                
        except Exception as e:
            logger.error(f"Data availability check failed: {e}")
            # On error, proceed anyway (fail-open for insights)
            return True, f"Check failed, proceeding: {e}"

    @traceable(name="InsightGraphAgent.analyze", run_type="chain")
    async def analyze(
        self,
        user_id: str,
        character_name: str,
        trigger: str = "volume",
        recent_context: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Runs insight analysis for a user using LangGraph.
        """
        # Check data availability before expensive LLM calls
        has_data, reason = await self._check_data_availability(user_id, character_name, trigger, recent_context)
        if not has_data:
            logger.info(f"Insight analysis skipped for user {user_id}: {reason}")
            return True, f"Skipped: {reason}. No LLM calls made."
        
        logger.info(f"InsightGraphAgent starting analysis for user {user_id} (trigger: {trigger}): {reason}")
        
        # 1. Initialize Tools
        tools = get_insight_tools_with_existing(user_id, character_name)
        
        # 2. Construct Prompts
        system_prompt = self._construct_prompt(character_name, trigger)
        user_message = self._build_analysis_request(trigger, recent_context)
        
        initial_messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]
        
        # 3. Build Graph
        workflow = StateGraph(InsightAgentState)
        
        workflow.add_node("agent", self.agent_node)
        workflow.add_node("tools", self.tools_node)
        
        workflow.set_entry_point("agent")
        
        workflow.add_conditional_edges(
            "agent",
            self.should_continue,
            {
                "tools": "tools",
                "end": END
            }
        )
        workflow.add_edge("tools", "agent")
        
        app = workflow.compile()
        
        # 4. Run Graph
        try:
            final_state = await app.ainvoke({
                "messages": initial_messages,
                "steps": 0,
                "artifacts_generated": [],
                "tools": tools,
                "max_steps": 5
            })
            
            artifacts = final_state.get("artifacts_generated", [])
            summary = f"Analysis complete. Artifacts: {', '.join(artifacts) if artifacts else 'none'}"
            logger.info(f"InsightGraphAgent finished for user {user_id}: {summary}")
            return True, summary
            
        except Exception as e:
            logger.error(f"InsightGraphAgent failed for user {user_id}: {e}")
            return False, str(e)

# Singleton instance
insight_graph_agent = InsightGraphAgent()
