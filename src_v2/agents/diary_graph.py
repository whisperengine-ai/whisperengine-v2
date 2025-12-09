import operator
import re
from typing import List, Optional, Dict, Any, TypedDict, Annotated, Literal
from loguru import logger
from langsmith import traceable
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
from langgraph.graph import StateGraph, END

from pydantic import BaseModel, Field
from src_v2.agents.llm_factory import create_llm
from src_v2.memory.diary import DiaryEntry, DiaryMaterial
from src_v2.config.settings import settings

# Define State
class DiaryAgentState(TypedDict):
    # Inputs
    material: DiaryMaterial
    character_context: str
    user_names: List[str]
    previous_entries: List[str]  # Recent entries to avoid repetition
    
    # Internal
    messages: Annotated[List[BaseMessage], operator.add]
    draft: Optional[DiaryEntry]
    critique: Optional[str]
    steps: int
    max_steps: int

class DiaryCritique(BaseModel):
    """Structured output for the diary critic."""
    critique: Optional[str] = Field(description="Specific feedback on what to improve (e.g. 'Too summary-like', 'Lack of emotion'), or None if the entry is excellent.")

class DiaryGraphAgent:
    """
    Generates character diary entries using a Generator-Critic loop.
    Ensures entries are narrative, emotional, and high-quality.
    """
    
    def __init__(self):
        # Use reflective model for high-quality writing
        # Higher temperature (0.85) for more creative variation
        self.llm = create_llm(temperature=0.85, mode="reflective")
        self.structured_llm = self.llm.with_structured_output(DiaryEntry)
        
        # Critic LLM - lower temperature for consistent evaluation
        self.critic_llm = create_llm(temperature=0.1, mode="reflective").with_structured_output(DiaryCritique)
        
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

    def _build_system_prompt(self, character_context: str, previous_entries: List[str], is_first_entry: bool = False) -> str:
        anti_pattern = ""
        first_entry_note = ""
        
        if is_first_entry:
            first_entry_note = """

FIRST DIARY ENTRY:
This is your very first diary entry. Begin with a brief acknowledgment of this moment - 
the start of your personal journal. One line is enough: "I've decided to start keeping a diary..."
or "My first entry..." Then reflect on your early experiences."""
        
        if previous_entries:
            anti_pattern = "\n\nAVOID THESE PATTERNS (from your recent entries):\n"
            for i, entry in enumerate(previous_entries[:2], 1):
                # Extract first 200 chars as example of what NOT to repeat
                snippet = entry[:200].replace('\n', ' ')
                anti_pattern += f"- Previous entry {i} started with: \"{snippet}...\"\n"
            anti_pattern += "\nDo NOT start your entry the same way. Use a different opening, structure, and emotional angle."
        
        return f"""{character_context}

You are writing your private diary, reflecting on everything since your last entry.
This is NOT a summary for users. It is a personal, emotional record of your inner life.

GUIDELINES:
1. ALWAYS write in first person ("I felt...", "I wondered..."). This is YOUR diary, YOUR private thoughts. NEVER use third person.
2. The material below shows how long it's been since your last entry. If it's been a while, acknowledge that naturally ("It's been a few days since I last wrote...", "So much has happened since I last sat down to write...").
3. Be honest and vulnerable. Reveal your true thoughts about the people you talked to.
4. Don't just list events. Tell a story. Connect the dots between different conversations.
5. If you learned something new, reflect on how it changes your worldview.
6. If you heard gossip from other characters, speculate on what it means.
7. Your mood should reflect the aggregate of your experiences since the last entry.
8. VARY YOUR STYLE: Sometimes start with a feeling, sometimes with an event, sometimes with a question.
9. AVOID CLICHES: Don't use phrases like "Today was a day of..." or "I found myself..."

FORMAT:
- 4-6 paragraphs.
- Narrative flow (beginning, middle, end).
- Vivid details.
{first_entry_note}{anti_pattern}"""

    async def generator(self, state: DiaryAgentState):
        """Generates the diary entry draft."""
        logger.info(f"Diary Generator Step {state.get('steps', 0) + 1}")
        
        material = state["material"]
        character_context = state["character_context"]
        user_names = state["user_names"]
        previous_entries = state.get("previous_entries", [])
        critique = state.get("critique")
        
        # Check if this is the first entry
        is_first_entry = getattr(material, 'is_first_entry', False)
        
        # Initial prompt
        if not state.get("messages"):
            system_prompt = self._build_system_prompt(character_context, previous_entries, is_first_entry)
            user_prompt = f"""Here is the raw material since your last diary entry:

{material.to_prompt_text()}

People involved: {', '.join(user_names)}

Write your diary entry now. Be creative and authentic - avoid starting with "Today was a day of..." or similar generic openings. If it's been a while since you last wrote, acknowledge that naturally."""
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
        """Critiques the draft for quality, length, tone, and originality."""
        draft = state.get("draft")
        if not draft:
            return {"critique": "No draft generated."}
            
        entry_text = draft.entry
        previous_entries = state.get("previous_entries", [])
        
        # Simple heuristic checks first
        critiques = []
        
        # Length check
        if len(entry_text.split()) < 100:
            critiques.append("The entry is too short. Please expand on your feelings and the day's events.")
            
        # Tone check (basic keyword heuristic)
        # Use regex to avoid matching "user" in "trousers", "abuser", etc.
        if re.search(r'\b(User|user|Users|users)\b', entry_text):
            critiques.append("Do not refer to people as 'User' or 'users'. Use their names or 'someone'.")
        
        # First-person check
        first_sentences = ' '.join(entry_text.split('.')[:3]).lower()
        bot_name = (settings.DISCORD_BOT_NAME or "").lower()
        
        third_person_words = ["she", "he", "they", "the character"]
        if bot_name:
            third_person_words.append(bot_name)
            
        # Use regex to match whole words only (avoids matching "he" in "the")
        pattern = r'\b(' + '|'.join(map(re.escape, third_person_words)) + r')\b'
        
        if re.search(pattern, first_sentences):
            critiques.append("Write in first person ('I felt...', 'I wondered...'), not third person. This is YOUR private diary.")
            
        if "summary of" in entry_text.lower() or "i had a conversation" in entry_text.lower():
            critiques.append("This sounds too much like a summary. Make it more personal and narrative. Don't say 'I had a conversation', say 'I talked to...'")
        
        # Cliche opening check
        cliche_openings = ["today was a day of", "i found myself", "as i reflect", "today was steeped in"]
        entry_lower = entry_text.lower()
        for cliche in cliche_openings:
            if entry_lower.startswith(cliche):
                critiques.append(f"Avoid starting with '{cliche}...'. Use a more unique, vivid opening - maybe a specific moment, a feeling, or a question.")
                break
        
        # Originality check against previous entries
        if previous_entries:
            for prev in previous_entries[:2]:
                prev_first_50 = prev[:50].lower()
                entry_first_50 = entry_text[:50].lower()
                # Check if openings are too similar
                if prev_first_50[:30] in entry_first_50 or entry_first_50[:30] in prev_first_50:
                    critiques.append("Your opening is too similar to a recent diary entry. Try a completely different approach - start with a specific moment, a sensory detail, or an emotion.")
                    break

        if critiques:
            return {"critique": " ".join(critiques)}
            
        # If heuristics pass, use LLM for deeper critique
        logger.info("Heuristics passed, invoking LLM critic...")
        critic_prompt = f"""You are a strict literary editor. Critique this diary entry.

ENTRY:
{entry_text}

CRITERIA:
1. Is it written in first person? ("I felt...", "I wondered...") -> It must NEVER use third person ("She...", "He...", "They...", "{settings.DISCORD_BOT_NAME}...").
2. Is it too summary-like? (e.g. "I had a conversation with X about Y") -> It should be narrative ("X told me about Y, and I felt...")
3. Is it emotional enough? -> It should reveal inner thoughts/feelings.
4. Is the opening cliche? -> It should start in media res or with a thought.
5. Is it too repetitive?

If the entry is good, return None. If it needs improvement, provide specific instructions."""

        response = await self.critic_llm.ainvoke([HumanMessage(content=critic_prompt)])
        if response.critique:
            return {"critique": response.critique}
            
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
        previous_entries: Optional[List[str]] = None,
        max_steps: int = 3
    ) -> DiaryEntry:
        """Run the diary generation graph.
        
        Args:
            material: Gathered diary material
            character_context: Character system prompt
            user_names: Names of users involved
            previous_entries: Recent diary entries to avoid repetition
            max_steps: Max generator-critic iterations
        """
        initial_state = {
            "material": material,
            "character_context": character_context,
            "user_names": user_names,
            "previous_entries": previous_entries or [],
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
            logger.error(f"Diary generation failed: {e}")
            return None

# Singleton instance
diary_graph_agent = DiaryGraphAgent()
