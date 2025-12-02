import operator
from typing import List, Optional, Dict, Any, TypedDict, Annotated
from loguru import logger
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage

from src_v2.agents.llm_factory import create_llm
from src_v2.knowledge.extractor import FactExtractionResult, Fact

# Define State
class KnowledgeAgentState(TypedDict):
    # Inputs
    text: str
    
    # Internal
    facts: Optional[List[Fact]]
    critique: Optional[str]
    steps: int
    max_steps: int

class KnowledgeGraphAgent:
    """
    Extracts knowledge graph facts using an Extractor-Validator loop.
    Prevents common hallucinations (e.g. User IS_A Cat) and ensures schema compliance.
    """
    
    def __init__(self):
        # Use utility model for extraction (low temp)
        self.llm = create_llm(temperature=0.0, mode="utility")
        self.structured_llm = self.llm.with_structured_output(FactExtractionResult)
        
        # Build graph
        workflow = StateGraph(KnowledgeAgentState)
        
        workflow.add_node("extractor", self.extractor)
        workflow.add_node("validator", self.validator)
        
        workflow.set_entry_point("extractor")
        workflow.add_edge("extractor", "validator")  # extractor always goes to validator
        workflow.add_conditional_edges(
            "validator",
            self.should_continue,
            {
                "retry": "extractor",
                "end": END
            }
        )
        
        self.graph = workflow.compile()

    async def extractor(self, state: KnowledgeAgentState):
        """Extracts facts from text."""
        steps = state.get("steps", 0) + 1
        logger.info(f"Knowledge Extractor Step {steps}")
        
        text = state["text"]
        critique = state.get("critique")
        
        system_prompt = """You are an expert Knowledge Graph Engineer. 
Your task is to extract structured facts from user messages to build a knowledge graph about the user.

Extract facts in the format: (Subject)-[PREDICATE]->(Object).
- Subject should usually be 'User' if the user is talking about themselves.
- Predicates should be UPPERCASE verbs (e.g., LIKES, OWNS, LIVES_IN, HAS_JOB, HAS_PET_NAMED, IS_A).
- Objects should be specific entities.

CRITICAL - COMMON MISTAKES TO AVOID:
1. PET OWNERSHIP: When user mentions having a pet with a name:
   - "I have a cat named Luna" → (User)-[HAS_PET_NAMED]->(Luna) AND (Luna)-[IS_A]->(Cat)
   - "My dog Max" → (User)-[HAS_PET_NAMED]->(Max) AND (Max)-[IS_A]->(Dog)
   - NEVER extract (User)-[IS_A]->(Cat) or (User)-[IS_A]->(Dog) - the USER is a HUMAN, not an animal!
   
2. IS_A should only be used for the USER when describing their profession, role, or identity:
   - "I am a developer" → (User)-[IS_A]->(Developer) ✓
   - "I am a teacher" → (User)-[IS_A]->(Teacher) ✓
   - "I have a cat" → (User)-[IS_A]->(Cat) ✗ WRONG! Use HAS_PET instead.

3. For pets, always create TWO facts:
   - One linking User to the pet's name (HAS_PET_NAMED)
   - One describing what kind of animal the pet is (PetName IS_A Animal)

Only extract facts that are explicitly stated and have long-term value (e.g., names, pets, location, preferences, identity traits).
Ignore transient states (e.g., "I am hungry", "I am walking").
Ignore behavioral configuration preferences (e.g., "speak less", "use emojis", "change style") - these are handled by a separate system.
"""

        if critique:
            user_prompt = f"""The previous extraction contained errors. Please fix them based on this feedback:
{critique}

Original Text:
{text}"""
        else:
            user_prompt = f"Extract facts from:\n{text}"

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        result = await self.structured_llm.ainvoke(messages)
        
        return {
            "facts": result.facts if result else [],
            "steps": steps
        }

    async def validator(self, state: KnowledgeAgentState):
        """Validates extracted facts for common errors."""
        facts = state.get("facts", [])
        
        if not facts:
            return {"critique": None}
            
        critiques = []
        
        for fact in facts:
            # Check for User IS_A Animal
            if fact.subject.lower() == "user" and fact.predicate == "IS_A":
                animal_types = ["cat", "dog", "bird", "fish", "hamster", "pet"]
                if fact.object.lower() in animal_types:
                    critiques.append(f"ERROR: User cannot be a {fact.object}. Use HAS_PET relationship instead.")
            
            # Check for self-referential loops
            if fact.subject == fact.object:
                critiques.append(f"ERROR: Subject and Object cannot be the same ({fact.subject}).")
                
        if critiques:
            return {"critique": "\n".join(critiques)}
            
        return {"critique": None}

    def should_continue(self, state: KnowledgeAgentState):
        """Decides whether to retry or end."""
        critique = state.get("critique")
        steps = state.get("steps", 0)
        max_steps = state.get("max_steps", 3)
        
        if critique and steps < max_steps:
            logger.info(f"Knowledge critique: {critique}. Retrying...")
            return "retry"
        
        return "end"

    async def run(self, text: str) -> List[Fact]:
        """Run the knowledge extraction graph."""
        try:
            initial_state = {
                "text": text,
                "facts": [],
                "critique": None,
                "steps": 0,
                "max_steps": 3
            }
            
            final_state = await self.graph.ainvoke(initial_state)
            return final_state.get("facts", [])
            
        except Exception as e:
            logger.error(f"Knowledge graph failed: {e}")
            return []

# Singleton
knowledge_graph_agent = KnowledgeGraphAgent()
