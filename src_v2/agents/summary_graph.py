import operator
import json
import re
from typing import List, Optional, Dict, Any, TypedDict, Annotated
from loguru import logger
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage

from src_v2.agents.llm_factory import create_llm
from src_v2.memory.summarizer import SummaryResult

# Define State
class SummaryAgentState(TypedDict):
    # Inputs
    conversation_text: str
    
    # Internal
    summary_result: Optional[SummaryResult]
    critique: Optional[str]
    steps: int
    max_steps: int

class SummaryGraphAgent:
    """
    Generates conversation summaries using a Generator-Critic loop.
    Ensures summaries capture emotional nuance and key facts.
    """
    
    def __init__(self):
        # Use main model for summarization (high quality for important memory artifacts)
        # Summaries are async background jobs and affect all future retrievals,
        # so quality > speed here.
        # Note: We use a sanitizer fallback to handle if the model outputs fenced JSON.
        self.llm = create_llm(temperature=0.3, mode="main", max_tokens=1024)
        self.structured_llm = self.llm.with_structured_output(SummaryResult)
        
        # Build graph
        workflow = StateGraph(SummaryAgentState)
        
        workflow.add_node("generator", self.generator)
        workflow.add_node("critic", self.critic)
        
        workflow.set_entry_point("generator")
        workflow.add_edge("generator", "critic")  # generator always goes to critic
        workflow.add_conditional_edges(
            "critic",
            self.should_continue,
            {
                "retry": "generator",
                "end": END
            }
        )
        
        self.graph = workflow.compile()

    def _clean_json_text(self, text: str) -> Optional[str]:
        """Attempt to extract a valid JSON object from LLM text.
        Handles fenced blocks (```json ... ```), and generic text with embedded JSON.
        Returns the JSON substring or None if not found.
        """
        if not text:
            return None
        s = text.strip()
        # Try to extract fenced JSON block
        fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", s, flags=re.IGNORECASE | re.DOTALL)
        if fence_match:
            return fence_match.group(1).strip()
        # Fallback: find first '{' and last '}'
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end != -1 and start < end:
            return s[start:end+1]
        return None

    async def generator(self, state: SummaryAgentState):
        """Generates the summary draft."""
        steps = state.get("steps", 0) + 1
        logger.info(f"Summary Generator Step {steps}")
        
        conversation_text = state["conversation_text"]
        critique = state.get("critique")
        
        system_prompt = """You are an expert conversation summarizer for an AI companion.
Your goal is to compress the conversation into a concise summary that preserves context for future recall.

RULES:
1. Focus on FACTS, TOPICS, and USER OPINIONS.
2. Ignore generic greetings ("Hi", "Hello") unless they are the only content.
3. Rate "Meaningfulness" (1-5):
   - 1: Small talk, greetings, short jokes.
   - 3: Hobbies, daily events, opinions.
   - 5: Deep emotional sharing, philosophy, life goals, trauma.
4. Detect Emotions: List 2-3 dominant emotions.
5. Extract Topics: List 1-5 key topics or themes (e.g., 'career anxiety', 'favorite movies', 'childhood memories').
   These topics help maintain narrative continuity across sessions.

OUTPUT INSTRUCTION:
You MUST output a valid JSON object matching the provided schema. Do not include any markdown formatting, code blocks, or conversational text.
"""

        if critique:
            if critique == "No summary generated.":
                user_prompt = f"""The previous attempt failed to generate a valid summary. Please try again, ensuring you output VALID JSON matching the schema.

Original Conversation:
{conversation_text}"""
            else:
                user_prompt = f"""The previous summary was critiqued. Please improve it based on this feedback:
{critique}

Original Conversation:
{conversation_text}"""
        else:
            user_prompt = f"Conversation to summarize:\n{conversation_text}"

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        try:
            result = await self.structured_llm.ainvoke(messages)
        except Exception as e:
            logger.warning(f"Summary generation failed (attempt {steps}): {e}")
            # Fallback: request raw output and sanitize JSON fences
            try:
                raw = await self.llm.ainvoke(messages)
                raw_text = getattr(raw, "content", str(raw))
                cleaned = self._clean_json_text(raw_text)
                if cleaned:
                    try:
                        data = json.loads(cleaned)
                        result = SummaryResult.model_validate(data)
                        logger.info("Summary fallback succeeded by cleaning fenced JSON.")
                    except Exception as e2:
                        logger.warning(f"Summary fallback parse failed: {e2}")
                        result = None
                else:
                    result = None
            except Exception as e3:
                logger.warning(f"Summary raw fallback failed: {e3}")
                result = None
        
        return {
            "summary_result": result,
            "steps": steps
        }

    async def critic(self, state: SummaryAgentState):
        """Critiques the summary for quality and emotional depth."""
        result = state["summary_result"]
        conversation_text = state["conversation_text"]
        
        if not result:
            return {"critique": "No summary generated."}
        
        # If meaningfulness is high (>3) but summary is short, request more detail
        if result.meaningfulness_score > 3 and len(result.summary.split()) < 20:
            return {"critique": "The conversation was rated as meaningful, but the summary is too brief. Please expand on the emotional content and key insights."}
            
        # If emotions are missing for a meaningful conversation
        if result.meaningfulness_score >= 3 and not result.emotions:
            return {"critique": "This was a meaningful conversation but no emotions were listed. Please identify the prevailing emotions."}
            
        # If topics are missing
        if not result.topics and len(conversation_text) > 200:
             return {"critique": "Please identify at least one key topic or theme from this conversation."}

        # Otherwise, approve
        return {"critique": None}

    def should_continue(self, state: SummaryAgentState):
        """Decides whether to retry or end."""
        critique = state.get("critique")
        steps = state.get("steps", 0)
        max_steps = state.get("max_steps", 3)
        
        if critique and steps < max_steps:
            logger.info(f"Summary critique: {critique}. Retrying...")
            return "retry"
        
        return "end"

    async def run(self, conversation_text: str) -> Optional[SummaryResult]:
        """Run the summarization graph."""
        try:
            initial_state = {
                "conversation_text": conversation_text,
                "summary_result": None,
                "critique": None,
                "steps": 0,
                "max_steps": 3
            }
            
            final_state = await self.graph.ainvoke(initial_state)
            return final_state.get("summary_result")
            
        except Exception as e:
            logger.error(f"Summary graph failed: {e}")
            return None

# Singleton
summary_graph_agent = SummaryGraphAgent()
