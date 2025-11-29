"""
Insight Agent - Background agentic processing for learning and epiphanies.

This agent runs in a separate worker container and analyzes conversations
to extract:
- Reasoning traces (successful patterns for reuse)
- Epiphanies (spontaneous realizations about users)  
- Response patterns (what styles resonate with each user)
"""
import asyncio
from typing import List, Optional, Tuple, Dict, Any
from loguru import logger
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, BaseMessage
from langchain_core.tools import BaseTool

from src_v2.agents.llm_factory import create_llm
from src_v2.tools.insight_tools import get_insight_tools
from src_v2.config.settings import settings


class InsightAgent:
    """
    Executes a ReAct loop for background analysis of user conversations.
    Unlike the real-time ReflectiveAgent, this runs asynchronously and
    generates artifacts (epiphanies, traces, patterns) for future use.
    """
    
    def __init__(self):
        # Use reflective model for insight analysis - needs good tool use and reasoning
        self.llm = create_llm(temperature=0.3, mode="reflective")
        self.max_steps = 5  # Keep it short - insights should be quick
    
    async def analyze(
        self,
        user_id: str,
        character_name: str,
        trigger: str = "volume",
        recent_context: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Runs insight analysis for a user.
        
        Args:
            user_id: Discord user ID to analyze
            character_name: Character/bot name
            trigger: What triggered this analysis (volume, time, session_end, feedback)
            recent_context: Optional recent conversation context to analyze
            
        Returns:
            Tuple of (success: bool, summary: str)
        """
        logger.info(f"InsightAgent starting analysis for user {user_id} (trigger: {trigger})")
        
        # 1. Initialize Tools
        tools = get_insight_tools(user_id, character_name)
        
        # 2. Construct System Prompt
        system_prompt = self._construct_prompt(character_name, trigger)
        
        # 3. Build initial user message
        user_message = self._build_analysis_request(trigger, recent_context)
        
        # 4. Initialize conversation
        messages: List[BaseMessage] = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]
        
        # 5. Bind tools to LLM
        llm_with_tools = self.llm.bind_tools(tools)
        
        steps = 0
        artifacts_generated = []
        
        try:
            while steps < self.max_steps:
                steps += 1
                
                # Invoke LLM
                response = await llm_with_tools.ainvoke(messages)
                messages.append(response)
                
                # Log thinking
                if response.content:
                    logger.debug(f"Insight Step {steps}: {str(response.content)[:100]}...")
                
                # Handle Tool Calls
                if response.tool_calls:
                    for tool_call in response.tool_calls:
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]
                        tool_call_id = tool_call["id"]
                        
                        logger.info(f"Insight Agent executing: {tool_name}")
                        
                        # Find and execute tool
                        selected_tool = next((t for t in tools if t.name == tool_name), None)
                        
                        if selected_tool:
                            try:
                                observation = await selected_tool.ainvoke(tool_args)
                                
                                # Track artifact generation
                                if tool_name in ["generate_epiphany", "store_reasoning_trace", "learn_response_pattern"]:
                                    artifacts_generated.append(tool_name)
                                    
                            except Exception as e:
                                observation = f"Error: {e}"
                                logger.error(f"Insight tool {tool_name} failed: {e}")
                        else:
                            observation = f"Tool {tool_name} not found"
                        
                        messages.append(ToolMessage(
                            content=str(observation),
                            tool_call_id=tool_call_id,
                            name=tool_name
                        ))
                    
                    continue
                else:
                    # No more tool calls - analysis complete
                    break
            
            summary = f"Analysis complete in {steps} steps. Artifacts: {', '.join(artifacts_generated) if artifacts_generated else 'none'}"
            logger.info(f"InsightAgent finished for user {user_id}: {summary}")
            return True, summary
            
        except Exception as e:
            logger.error(f"InsightAgent failed for user {user_id}: {e}")
            return False, str(e)
    
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


# Singleton instance
insight_agent = InsightAgent()
