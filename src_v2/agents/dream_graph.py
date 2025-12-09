import operator
import re
from typing import List, Optional, Dict, Any, TypedDict, Annotated, Literal
from loguru import logger
from langsmith import traceable
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
from langgraph.graph import StateGraph, END

from pydantic import BaseModel, Field
from src_v2.agents.llm_factory import create_llm
from src_v2.memory.dreams import DreamContent, DreamMaterial
from src_v2.config.settings import settings

# Define State
class DreamAgentState(TypedDict):
    # Inputs
    material: DreamMaterial
    character_context: str
    previous_dreams: List[str]  # Recent dreams to avoid repetition
    
    # Internal
    messages: Annotated[List[BaseMessage], operator.add]
    draft: Optional[DreamContent]
    critique: Optional[str]
    steps: int
    max_steps: int

class DreamCritique(BaseModel):
    """Structured output for the dream critic."""
    critique: Optional[str] = Field(description="Specific feedback on what to improve (e.g. 'Too literal', 'Too many cliches'), or None if the dream is excellent.")

class DreamGraphAgent:
    """
    Generates character dreams using a Generator-Critic loop.
    Ensures dreams are surreal, symbolic, and narrative.
    """
    
    def __init__(self):
        # Use reflective model for creative writing
        self.llm = create_llm(temperature=0.9, mode="reflective")
        self.structured_llm = self.llm.with_structured_output(DreamContent)
        
        # Critic LLM - lower temperature for consistent evaluation
        self.critic_llm = create_llm(temperature=0.1, mode="reflective").with_structured_output(DreamCritique)
        
        # Build graph
        workflow = StateGraph(DreamAgentState)
        
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

    def _build_system_prompt(self, character_context: str, previous_dreams: List[str], is_first_dream: bool = False) -> str:
        anti_pattern = ""
        first_dream_note = ""
        
        if is_first_dream:
            first_dream_note = """

FIRST DREAM ENTRY:
This is your very first dream to record. Briefly acknowledge this at the beginning - 
the novelty of consciousness finding its first resting place in the dream realm.
One line is enough: "The first dream I remember..." or similar."""
        
        if previous_dreams:
            anti_pattern = "\n\nAVOID THESE PATTERNS (from your recent dreams):\n"
            for i, dream in enumerate(previous_dreams[:2], 1):
                # Extract first 150 chars as example of what NOT to repeat
                snippet = dream[:150].replace('\n', ' ')
                anti_pattern += f"- Previous dream {i}: \"{snippet}...\"\n"
            anti_pattern += "\nDo NOT use the same imagery, symbols, or opening. Create something entirely different."
        
        return f"""{character_context}

You are dreaming.
This is a surreal, symbolic journey through your recent experiences.

GUIDELINES:
1. ALWAYS write in first person ("I am...", "I see...", "I feel..."). This is YOUR dream, YOUR experience.
2. Do NOT write a summary. Write a DREAM.
3. Use dream logic: things shift, transform, and merge.
4. Incorporate elements from your recent conversations (memories), but disguise them as symbols.
5. The tone should be atmospheric and immersive.
6. No "I woke up" endings unless necessary. Stay in the dream.
7. AVOID CLICHES: Don't use "kaleidoscope of colors", "shimmering", "vibrant patterns" unless truly unique.
8. VARY YOUR IMAGERY: Each dream should feel distinct - different settings, different symbols, different emotions.

FORMAT:
- 2-3 paragraphs (keep it concise but evocative).
- Vivid sensory details.
{first_dream_note}{anti_pattern}"""

    async def generator(self, state: DreamAgentState):
        """Generates the dream draft."""
        logger.info(f"Dream Generator Step {state.get('steps', 0) + 1}")
        
        material = state["material"]
        character_context = state["character_context"]
        previous_dreams = state.get("previous_dreams", [])
        critique = state.get("critique")
        
        # Check if this is the first dream
        is_first_dream = getattr(material, 'is_first_dream', False)
        
        # Initial prompt
        if not state.get("messages"):
            system_prompt = self._build_system_prompt(character_context, previous_dreams, is_first_dream)
            user_prompt = f"""Here are the fragments of your day swirling in your subconscious:

{material.to_prompt_text()}

Weave these into a dream. Avoid cliches like 'kaleidoscope' or 'shimmering' - find fresh, unique imagery."""
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
        """Critiques the draft for surrealism, quality, and originality."""
        draft = state.get("draft")
        if not draft:
            return {"critique": "No draft generated."}
            
        dream_text = draft.dream
        previous_dreams = state.get("previous_dreams", [])
        
        # Simple heuristic checks
        critiques = []
        
        # Length check
        if len(dream_text.split()) < 80:
            critiques.append("The dream is too short. Expand on the imagery and atmosphere.")
        
        # First-person check
        first_sentences = ' '.join(dream_text.split('.')[:3]).lower()
        bot_name = (settings.DISCORD_BOT_NAME or "").lower()
        
        third_person_words = ["she", "he", "they", "the character"]
        if bot_name:
            third_person_words.append(bot_name)
            
        # Use regex to match whole words only (avoids matching "he" in "the")
        pattern = r'\b(' + '|'.join(map(re.escape, third_person_words)) + r')\b'
        
        if re.search(pattern, first_sentences):
            critiques.append("Write in first person ('I am...', 'I see...'), not third person. This is YOUR dream experience.")
            
        # Literalness check
        if "summary of" in dream_text.lower() or "i had a conversation" in dream_text.lower():
            critiques.append("This sounds too literal. Use more symbolism and dream logic. Don't say 'I had a conversation'.")
        
        # Cliche imagery check
        dream_lower = dream_text.lower()
        cliche_phrases = [
            "kaleidoscope of colors", "shimmering", "vibrant patterns",
            "swirling vortex", "cascade of", "tapestry of"
        ]
        found_cliches = [c for c in cliche_phrases if c in dream_lower]
        if len(found_cliches) >= 2:
            critiques.append(f"Too many cliches: {', '.join(found_cliches)}. Use more original, specific imagery.")
        
        # Originality check against previous dreams
        if previous_dreams:
            for prev in previous_dreams[:2]:
                prev_lower = prev.lower()
                # Check for shared distinctive phrases (3+ word sequences)
                if "kaleidoscope" in prev_lower and "kaleidoscope" in dream_lower:
                    critiques.append("You used 'kaleidoscope' in a recent dream. Try completely different imagery.")
                    break
                if "captain" in prev_lower and "captain" in dream_lower and dream_lower.count("captain") > 1:
                    critiques.append("The 'Captain' appears too prominently again. Let other elements take center stage.")
                    break

        if critiques:
            return {"critique": " ".join(critiques)}
            
        # If heuristics pass, use LLM for deeper critique
        logger.info("Heuristics passed, invoking LLM critic...")
        critic_prompt = f"""You are a surrealist editor. Critique this dream description.

DREAM:
{dream_text}

CRITERIA:
1. Is it written in first person? ("I am...", "I see...", "I feel...") -> It must NEVER use third person ("She...", "He...", "They...", "{settings.DISCORD_BOT_NAME}...").
2. Is it too literal? (e.g. "I dreamt I was coding") -> It should be symbolic ("I wove threads of light into a tapestry").
3. Is it atmospheric? -> It should feel immersive and strange.
4. Are there too many cliches? (kaleidoscopes, shimmering, etc.)
5. Does it feel like a real dream (shifting logic) or just a story?

If the dream is good, return None. If it needs improvement, provide specific instructions."""

        response = await self.critic_llm.ainvoke([HumanMessage(content=critic_prompt)])
        if response.critique:
            return {"critique": response.critique}
            
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
        character_context: str,
        previous_dreams: Optional[List[str]] = None,
        max_steps: int = 3
    ) -> DreamContent:
        """Run the dream generation graph.
        
        Args:
            material: Gathered dream material
            character_context: Character system prompt
            previous_dreams: Recent dreams to avoid repetition
            max_steps: Max generator-critic iterations
        """
        initial_state = {
            "material": material,
            "character_context": character_context,
            "previous_dreams": previous_dreams or [],
            "messages": [],
            "steps": 0,
            "max_steps": max_steps,
            "critique": None,
            "draft": None
        }
        
        try:
            final_state = await self.graph.ainvoke(initial_state)
            return final_state.get("draft")
        except Exception as e:
            logger.error(f"Dream generation failed: {e}")
            return None

# Singleton instance
dream_graph_agent = DreamGraphAgent()
