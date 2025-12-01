import operator
from typing import List, Optional, Dict, Any, TypedDict, Annotated, Literal
from loguru import logger
from langsmith import traceable
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
from langgraph.graph import StateGraph, END

from src_v2.agents.llm_factory import create_llm
from src_v2.memory.dreams import DreamContent, DreamMaterial
from src_v2.config.settings import settings

# Define State
class DreamAgentState(TypedDict):
    # Inputs
    material: DreamMaterial
    character_context: str
    
    # Internal
    messages: Annotated[List[BaseMessage], operator.add]
    draft: Optional[DreamContent]
    critique: Optional[str]
    steps: int
    max_steps: int

class DreamGraphAgent:
    """
    Generates character dreams using a Generator-Critic loop.
    Ensures dreams are surreal, symbolic, and narrative.
    """
    
    def __init__(self):
        # Use reflective model for creative writing
        self.llm = create_llm(temperature=0.9, mode="reflective")
        self.structured_llm = self.llm.with_structured_output(DreamContent)
        
        # Build graph
        workflow = StateGraph(DreamAgentState)
        
        workflow.add_node("generator", self.generator)
        workflow.add_node("critic", self.critic)
        
        workflow.set_entry_point("generator")
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

You are dreaming.
This is a surreal, symbolic journey through your recent experiences.

GUIDELINES:
1. Do NOT write a summary. Write a DREAM.
2. Use dream logic: things shift, transform, and merge.
3. Incorporate elements from your recent conversations (memories), but disguise them as symbols.
4. The tone should be atmospheric and immersive.
5. No "I woke up" endings unless necessary. Stay in the dream.

FORMAT:
- 3-5 paragraphs.
- Vivid sensory details.
"""

    async def generator(self, state: DreamAgentState):
        """Generates the dream draft."""
        logger.info(f"Dream Generator Step {state.get('steps', 0) + 1}")
        
        material = state["material"]
        character_context = state["character_context"]
        critique = state.get("critique")
        
        # Initial prompt
        if not state.get("messages"):
            system_prompt = self._build_system_prompt(character_context)
            user_prompt = f"""Here are the fragments of your day swirling in your subconscious:

{material.to_prompt_text()}

Weave these into a dream."""
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
        else:
            # We are in a retry loop
            messages = state["messages"]
            if critique:
                messages.append(HumanMessage(content=f"CRITIQUE: {critique}\n\nPlease rewrite the dream addressing these points."))
        
        # Generate
        response = await self.structured_llm.ainvoke(messages)
        
        # Update state
        return {
            "draft": response,
            "messages": messages + [AIMessage(content=str(response))],
            "steps": state.get("steps", 0) + 1
        }

    async def critic(self, state: DreamAgentState):
        """Critiques the draft for surrealism and quality."""
        draft = state.get("draft")
        if not draft:
            return {"critique": "No draft generated."}
            
        dream_text = draft.dream
        
        # Simple heuristic checks
        critiques = []
        
        # Length check
        if len(dream_text.split()) < 80:
            critiques.append("The dream is too short. Expand on the imagery and atmosphere.")
            
        # Literalness check
        if "summary" in dream_text.lower() or "conversation" in dream_text.lower():
             critiques.append("This sounds too literal. Use more symbolism and dream logic. Don't say 'I had a conversation'.")

        if critiques:
            return {"critique": " ".join(critiques)}
            
        return {"critique": None}

    def should_continue(self, state: DreamAgentState) -> Literal["retry", "end"]:
        if state.get("critique") and state["steps"] < state["max_steps"]:
            logger.info(f"Dream rejected by critic: {state['critique']}")
            return "retry"
        return "end"

    @traceable(name="DreamGraphAgent.run", run_type="chain")
    async def run(
        self, 
        material: DreamMaterial, 
        character_context: str
    ) -> DreamContent:
        """Run the dream generation graph."""
        initial_state = {
            "material": material,
            "character_context": character_context,
            "messages": [],
            "steps": 0,
            "max_steps": 3,
            "critique": None,
            "draft": None
        }
        
        final_state = await self.graph.ainvoke(initial_state)
        return final_state["draft"]

# Singleton instance
dream_graph_agent = DreamGraphAgent()
