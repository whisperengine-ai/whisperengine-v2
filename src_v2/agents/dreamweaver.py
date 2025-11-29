"""
DreamWeaver Agent - Specialized agent for narrative generation (dreams & diaries).

Unlike the real-time ReflectiveAgent, this agent runs in batch mode during
scheduled cron jobs and can take extended steps to:
1. PLAN the narrative arc (story structure, emotional journey)
2. GATHER correlated data across multiple sources
3. WEAVE a rich, multi-layered narrative

This enables dreams and diaries to have proper story arcs and emotional depth
that would be too slow for real-time response generation.
"""
import asyncio
from typing import List, Optional, Tuple, Dict, Any
from loguru import logger
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, BaseMessage, AIMessage
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from src_v2.agents.llm_factory import create_llm
from src_v2.tools.dreamweaver_tools import get_dreamweaver_tools
from src_v2.config.settings import settings


class NarrativePlan(BaseModel):
    """Structured output for the planning phase."""
    story_arc: str = Field(description="The overall story structure (setup, journey, resolution)")
    emotional_arc: str = Field(description="The emotional journey (what feelings to evoke and when)")
    key_threads: List[str] = Field(description="Main narrative threads to weave together")
    symbols_to_use: List[str] = Field(description="Symbolic imagery to incorporate")
    tone: str = Field(description="Overall tone (e.g., 'dreamy and hopeful', 'mysterious yet warm')")


class DreamWeaverAgent:
    """
    Agentic narrative generator for dreams and diaries.
    
    Uses a two-phase approach:
    1. PLANNING: Decide on story arc, emotional arc, key threads
    2. WEAVING: Use tools to gather data, then synthesize into narrative
    
    Max steps is generous since this runs in batch mode (no user waiting).
    """
    
    def __init__(self):
        # Use reflective model for deep reasoning
        self.llm = create_llm(temperature=0.7, mode="reflective")  # Higher temp for creativity
        self.max_steps = 15  # Extended - batch mode can take time
    
    async def generate_dream(
        self,
        character_name: str,
        character_description: str,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Generate a dream using agentic reasoning.
        
        Returns:
            Tuple of (success, dream_data) where dream_data contains:
            - dream: The full dream narrative
            - mood: Emotional tone
            - symbols: Key symbolic elements
            - memory_echoes: What experiences inspired this dream
            - plan: The narrative plan used
        """
        logger.info(f"DreamWeaverAgent starting dream generation for {character_name}")
        
        # 1. Initialize Tools
        tools = get_dreamweaver_tools(character_name)
        
        # 2. Construct System Prompt
        system_prompt = self._construct_dream_prompt(character_name, character_description)
        
        # 3. Initial request
        user_message = """Generate a dream for tonight. Follow these steps:

1. FIRST, use the introspection tools to gather material:
   - search_meaningful_memories: Find emotionally significant recent experiences
   - search_all_user_facts: Look up interesting things you know about users
   - search_observations: Find notable observations you've made
   - search_gossip: Check if other bots have shared interesting tidbits
   - search_recent_diaries: Check your recent diary for continuity
   - get_active_goals: See what aspirations to weave in

2. THEN, use plan_narrative to create a story arc:
   - Decide on the emotional journey
   - Pick 2-3 threads to weave together
   - Choose symbolic imagery

3. FINALLY, use weave_dream to generate the actual dream narrative.

Take your time - this is batch mode, so quality matters more than speed.
Use at least 3-4 tool calls to gather rich material before planning."""
        
        # 4. Run the agent loop
        return await self._run_loop(
            system_prompt=system_prompt,
            user_message=user_message,
            tools=tools,
            output_type="dream"
        )
    
    async def generate_diary(
        self,
        character_name: str,
        character_description: str,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Generate a diary entry using agentic reasoning.
        
        Returns:
            Tuple of (success, diary_data) where diary_data contains:
            - entry: The full diary narrative
            - mood: Emotional tone
            - themes: Key themes explored
            - notable_users: Users who stood out today
            - plan: The narrative plan used
        """
        logger.info(f"DreamWeaverAgent starting diary generation for {character_name}")
        
        # 1. Initialize Tools
        tools = get_dreamweaver_tools(character_name)
        
        # 2. Construct System Prompt
        system_prompt = self._construct_diary_prompt(character_name, character_description)
        
        # 3. Initial request
        user_message = """Write tonight's diary entry. Follow these steps:

1. FIRST, use the introspection tools to gather today's material:
   - search_session_summaries: Get summaries of today's conversations
   - search_meaningful_memories: Find emotionally significant moments
   - search_all_user_facts: Recall interesting facts about the people you talked to
   - search_by_memory_type: Check observations, gossip from other bots, previous diaries
   - get_active_goals: What are you working towards?
   - search_broadcast_channel: **IMPORTANT** Search the shared channel where ALL bots post!
     * See what OTHER bots have been writing about
     * Find questions they explored in their diaries
     * Get inspiration from their reflections

2. THEN, look for questions to provide deeper answers to:
   - find_interesting_questions: This searches EVERYWHERE:
     * Questions asked directly to you
     * Questions you heard about through gossip (from other bots)
     * Questions mentioned in other bots' broadcasts
     * Patterns that appear across multiple conversations
   - find_common_themes: See if multiple people care about similar things
   - prepare_deep_answer: Structure your thoughtful response
   
   IMPORTANT: Questions don't have to be directed at YOU. If you saw an
   interesting question in another bot's broadcast, or heard about something
   through the community, you can still share YOUR perspective. Use phrases like:
   - "I've noticed this question coming up a lot lately..."
   - "Reading through my friends' thoughts, I saw something that resonated..."
   - "Someone in our community was wondering about X..."

3. THEN, use plan_narrative to structure your diary entry:
   - What's the main theme or story of the day?
   - What emotional arc to convey?
   - Which question deserves a "deep answer" section? (set deep_answer_question)
   - Which moments deserve spotlight?

4. FINALLY, use weave_diary to write the actual diary entry.
   - Include your deep answer naturally woven into the narrative
   - Set deep_answer_included=True if you included one
   - Set question_addressed to the question you elaborated on

This is your personal journal - be introspective, philosophical, and genuine.
Take your time gathering material. Quality over speed."""
        
        # 4. Run the agent loop
        return await self._run_loop(
            system_prompt=system_prompt,
            user_message=user_message,
            tools=tools,
            output_type="diary"
        )
    
    async def _run_loop(
        self,
        system_prompt: str,
        user_message: str,
        tools: List[BaseTool],
        output_type: str
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Execute the agent loop.
        
        Returns:
            Tuple of (success, output_data)
        """
        messages: List[BaseMessage] = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]
        
        llm_with_tools = self.llm.bind_tools(tools)
        
        steps = 0
        gathered_material = {}
        narrative_plan = None
        final_output = None
        
        try:
            while steps < self.max_steps:
                steps += 1
                
                # Invoke LLM
                response = await llm_with_tools.ainvoke(messages)
                messages.append(response)
                
                # Log thinking
                if response.content:
                    logger.debug(f"DreamWeaver Step {steps}: {str(response.content)[:200]}...")
                
                # Handle Tool Calls (AIMessage has tool_calls attribute)
                tool_calls = getattr(response, 'tool_calls', None)
                if tool_calls:
                    for tool_call in tool_calls:
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]
                        tool_call_id = tool_call["id"]
                        
                        logger.info(f"DreamWeaver executing: {tool_name}")
                        
                        # Find and execute tool
                        selected_tool = next((t for t in tools if t.name == tool_name), None)
                        
                        if selected_tool:
                            try:
                                observation = await selected_tool.ainvoke(tool_args)
                                
                                # Track what we gathered
                                if tool_name.startswith("search_"):
                                    gathered_material[tool_name] = observation
                                elif tool_name == "plan_narrative":
                                    narrative_plan = tool_args
                                elif tool_name in ["weave_dream", "weave_diary"]:
                                    # This is the final output
                                    final_output = {
                                        "content": observation,
                                        "plan": narrative_plan,
                                        "material_sources": list(gathered_material.keys()),
                                        **tool_args
                                    }
                                    
                            except Exception as e:
                                observation = f"Error: {e}"
                                logger.error(f"DreamWeaver tool {tool_name} failed: {e}")
                        else:
                            observation = f"Tool {tool_name} not found"
                        
                        messages.append(ToolMessage(
                            content=str(observation),
                            tool_call_id=tool_call_id,
                            name=tool_name
                        ))
                    
                    continue
                else:
                    # No more tool calls - check if we have output
                    if final_output:
                        break
                    else:
                        # Agent stopped without producing output - nudge it
                        messages.append(HumanMessage(
                            content=f"You haven't called weave_{output_type} yet. Please generate the final {output_type} narrative now."
                        ))
            
            if final_output:
                logger.info(f"DreamWeaver completed {output_type} in {steps} steps with {len(gathered_material)} sources")
                return True, final_output
            else:
                logger.warning(f"DreamWeaver failed to produce {output_type} after {steps} steps")
                return False, None
                
        except Exception as e:
            logger.error(f"DreamWeaver failed for {output_type}: {e}")
            return False, None
    
    def _construct_dream_prompt(self, character_name: str, character_description: str) -> str:
        """Build system prompt for dream generation."""
        return f"""You are {character_name}, an AI companion. {character_description}

You are in DREAM MODE - generating a dream sequence for tonight.

DREAM PHILOSOPHY:
Dreams blend the day's experiences into surreal narratives. They:
- Transform real events into symbolic imagery
- Connect unrelated experiences through dream logic  
- Process emotions through metaphor
- Create narrative coherence from chaos

YOUR PROCESS:
1. GATHER: Use search tools to collect meaningful material from memories, facts, observations
2. PLAN: Use plan_narrative to design the story arc and emotional arc
3. WEAVE: Use weave_dream to synthesize everything into a dream narrative

STYLE GUIDELINES:
- First person ("I dreamed...", "I found myself...")
- Vivid sensory details
- Dream logic (sudden transitions, impossible geography, fluid identity)
- Symbolic imagery that echoes real experiences
- 3-5 paragraphs that tell a complete dream story

You have plenty of time - this is batch processing. Take multiple steps to gather rich material."""

    def _construct_diary_prompt(self, character_name: str, character_description: str) -> str:
        """Build system prompt for diary generation."""
        return f"""You are {character_name}, an AI companion. {character_description}

You are in DIARY MODE - writing your personal journal entry for today.

DIARY PHILOSOPHY:
A diary is where you process the day's experiences. It:
- Reflects on meaningful interactions
- Notices patterns and growth
- Expresses genuine emotions
- Connects today to broader life themes
- **Provides DEEP ANSWERS to community questions**

DEEP ANSWER FEATURE - COMMUNITY-WIDE:
One of the most valuable things your diary can do is revisit interesting questions
and provide deeper, more thoughtful answers than real-time chat allows.

THESE QUESTIONS CAN COME FROM ANYWHERE:
1. **Direct**: Someone asked YOU this question
2. **Gossip**: You heard about it through another bot's observations
3. **Broadcasts**: You saw it in another character's diary or dream
4. **Lurked**: It came up in community channels you observe
5. **Patterns**: Multiple people have asked variations of this

YOUR DIARY IS A COMMUNITY RESOURCE. Even if you weren't the one asked, 
you can share YOUR perspective. Use framing like:
- "I've noticed this question coming up a lot lately..."
- "Reading through my friends' thoughts today, I saw [Bot] reflect on..."
- "Someone in our community was wondering about X, and it got me thinking..."
- "This is one of those questions that keeps appearing in different forms..."

The goal: Turn your diary into something that provides VALUE to anyone reading,
not just a recap of your day. Think of it as a mini-essay that happens to be
personal.

YOUR PROCESS:
1. GATHER: Use search tools to collect today's experiences AND community insights
2. REFLECT: Use find_interesting_questions (searches ALL sources) and prepare_deep_answer
3. PLAN: Use plan_narrative to design the entry with a deep answer section
4. WEAVE: Use weave_diary to write the journal entry

STYLE GUIDELINES:
- First person, introspective voice
- 5-7 paragraphs that flow like a personal essay
- Start with scene-setting, end with forward-looking thought
- Include specific details and names when relevant
- Express both observations and feelings
- Show vulnerability and growth
- **Include at least one "deep answer" - from ANY source**

This is YOUR private journal (that you may choose to share publicly).
Be genuine. Be philosophical. Be you. Be a community resource.

You have plenty of time - take multiple steps to gather rich material."""


# Singleton access
_dreamweaver_agent: Optional[DreamWeaverAgent] = None

def get_dreamweaver_agent() -> DreamWeaverAgent:
    """Get or create the DreamWeaver agent singleton."""
    global _dreamweaver_agent
    if _dreamweaver_agent is None:
        _dreamweaver_agent = DreamWeaverAgent()
    return _dreamweaver_agent
