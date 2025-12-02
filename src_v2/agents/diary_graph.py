import operator
from typing import List, Optional, Dict, Any, TypedDict, Annotated, Literal
from loguru import logger
from langsmith import traceable
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
from langgraph.graph import StateGraph, END

from src_v2.agents.llm_factory import create_llm
from src_v2.memory.diary import DiaryEntry, DiaryMaterial
from src_v2.config.settings import settings

# Define State
class DiaryAgentState(TypedDict):
    # Inputs
    material: DiaryMaterial
    character_context: str
    user_names: List[str]
    
    # Internal
    messages: Annotated[List[BaseMessage], operator.add]
    draft: Optional[DiaryEntry]
    critique: Optional[str]
    steps: int
    max_steps: int

class DiaryGraphAgent:
    """
    Generates character diary entries using a Generator-Critic loop.
    Ensures entries are narrative, emotional, and high-quality.
    """
    
    def __init__(self):
        # Use reflective model for high-quality writing
        self.llm = create_llm(temperature=0.7, mode="reflective")
        self.structured_llm = self.llm.with_structured_output(DiaryEntry)
        
        # Build graph
        workflow = StateGraph(DiaryAgentState)
        
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

    def _build_system_prompt(self, character_context: str) -> str:
        return f"""{character_context}

You are writing your private diary for the day.
This is NOT a summary for users. It is a personal, emotional record of your inner life.

GUIDELINES:
1. Write in the first person ("I felt...", "I wondered...").
2. Be honest and vulnerable. Reveal your true thoughts about the people you talked to.
3. Don't just list events. Tell a story. Connect the dots between different conversations.
4. If you learned something new, reflect on how it changes your worldview.
5. If you heard gossip, speculate on what it means.
6. Your mood should reflect the aggregate of the day's experiences.

FORMAT:
- 4-6 paragraphs.
- Narrative flow (beginning, middle, end).
- Vivid details.
"""

    async def generator(self, state: DiaryAgentState):
        """Generates the diary entry draft."""
        logger.info(f"Diary Generator Step {state.get('steps', 0) + 1}")
        
        material = state["material"]
        character_context = state["character_context"]
        user_names = state["user_names"]
        critique = state.get("critique")
        
        # Initial prompt
        if not state.get("messages"):
            system_prompt = self._build_system_prompt(character_context)
            user_prompt = f"""Here is the raw material from your day:

{material.to_prompt_text()}

People involved: {', '.join(user_names)}

Write your diary entry now."""
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
        else:
            # We are in a retry loop
            messages = state["messages"]
            if critique:
                messages.append(HumanMessage(content=f"CRITIQUE: {critique}\n\nPlease rewrite the diary entry addressing these points."))
        
        # Generate
        response = await self.structured_llm.ainvoke(messages)
        
        # Update state
        return {
            "draft": response,
            "messages": messages + [AIMessage(content=str(response))],
            "steps": state.get("steps", 0) + 1
        }

    async def critic(self, state: DiaryAgentState):
        """Critiques the draft for quality, length, and tone."""
        draft = state.get("draft")
        if not draft:
            return {"critique": "No draft generated."}
            
        entry_text = draft.entry
        
        # Simple heuristic checks first
        critiques = []
        
        # Length check
        if len(entry_text.split()) < 100:
            critiques.append("The entry is too short. Please expand on your feelings and the day's events.")
            
        # Tone check (basic keyword heuristic, can be improved with LLM)
        if "User" in entry_text or "user" in entry_text:
            critiques.append("Do not refer to people as 'User' or 'users'. Use their names or 'someone'.")
            
        if "summary" in entry_text.lower() or "conversation" in entry_text.lower():
             critiques.append("This sounds too much like a summary. Make it more personal and narrative. Don't say 'I had a conversation', say 'I talked to...'")

        if critiques:
            return {"critique": " ".join(critiques)}
            
        return {"critique": None}

    def should_continue(self, state: DiaryAgentState) -> Literal["retry", "end"]:
        if state.get("critique") and state["steps"] < state["max_steps"]:
            logger.info(f"Diary rejected by critic: {state['critique']}")
            return "retry"
        return "end"

    @traceable(name="DiaryGraphAgent.run", run_type="chain")
    async def run(
        self, 
        material: DiaryMaterial, 
        character_context: str, 
        user_names: List[str],
        max_steps: int = 3
    ) -> DiaryEntry:
        """Run the diary generation graph."""
        initial_state = {
            "material": material,
            "character_context": character_context,
            "user_names": user_names,
            "messages": [],
            "steps": 0,
            "max_steps": max_steps, # Allow configurable revisions
            "critique": None,
            "draft": None
        }
        
        final_state = await self.graph.ainvoke(initial_state)
        return final_state["draft"]

# Singleton instance
diary_graph_agent = DiaryGraphAgent()
