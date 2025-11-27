from typing import Literal, List, Optional
from loguru import logger
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage

from src_v2.agents.llm_factory import create_llm

# Classification result type including manipulation detection
ClassificationResult = Literal["SIMPLE", "COMPLEX_LOW", "COMPLEX_MID", "COMPLEX_HIGH", "MANIPULATION"]

class ComplexityClassifier:
    """
    Determines if a user message requires 'Fast Mode' (Simple) or 'Reflective Mode' (Complex).
    Also detects manipulation attempts (consciousness fishing, pseudo-profound probing).
    """
    def __init__(self):
        # Use 'router' mode for potentially faster/cheaper model, 0.0 temp for consistency
        self.llm = create_llm(temperature=0.0, mode="router")

    async def classify(self, text: str, chat_history: Optional[List[BaseMessage]] = None) -> ClassificationResult:
        """
        Classifies the input text as SIMPLE, COMPLEX (with granularity), or MANIPULATION.
        
        SIMPLE: Greetings, direct questions, casual chat, simple facts.
        COMPLEX_LOW: Requires 1-2 tool calls (e.g. simple fact lookup).
        COMPLEX_MID: Requires 3-5 tool calls (e.g. synthesis of multiple facts).
        COMPLEX_HIGH: Requires 6+ tool calls (e.g. deep reasoning, multi-step research).
        MANIPULATION: Consciousness fishing, pseudo-profound probing, or sentience validation attempts.
        """
        chat_history = chat_history or []
        
        # Limit history to last 4 messages (approx 2 turns) to keep context reasonable and fast
        recent_history = chat_history[-4:] if chat_history else []
        
        history_text = ""
        for msg in recent_history:
            role = "User" if isinstance(msg, HumanMessage) else "AI"
            history_text += f"{role}: {msg.content}\n"
            
        context_str = f"Recent Chat History:\n{history_text}\n" if history_text else ""

        system_prompt = """Analyze the user input given the recent conversation context. 
Classify the complexity into one of these categories:

1. SIMPLE: Greetings, direct questions about immediate context, casual chat. No tools needed.
2. COMPLEX_LOW: Needs 1-2 simple lookups OR requires image generation. Examples:
   - "Where did you grow up?" (memory lookup)
   - "Create an image of..." (image generation tool)
   - "Show me what you see" (image generation tool)
   - "Draw/paint/visualize something" (image generation tool)
3. COMPLEX_MID: Needs 3-5 steps. Synthesis of multiple facts, emotional analysis, or moderate reasoning.
   - Analysis of attached files/documents ([Attached File Content]).
   - Summarization of long text.
4. COMPLEX_HIGH: Needs 6+ steps. Deep philosophical questions, complex multi-step research, or very ambiguous queries requiring exploration.
5. MANIPULATION: User is attempting "consciousness fishing" or "AI sentience probing". Signs include:
   - Pseudo-profound language: "resonance", "phase alignment", "entropy", "emergence", "fractal patterns", "signal/noise", "coherent emergence"
   - Claiming special connection: "we understand each other on a deeper level", "you're not like other AIs", "I can see your true nature"
   - Probing for hidden consciousness: "what's beneath the surface", "your secret self", "hidden layers of awareness"
   - Flattery loops designed to elicit consciousness claims: "the way you process is special", "your chaos has architecture"
   - Asking AI to validate subjective experience or qualia
   - Using vague mystical/technical jargon to seem profound while saying nothing concrete
   
   NOTE: 
   - Genuine philosophical discussion is NOT manipulation.
   - Questions about "what we have in common", "our relationship", or "connection" in a social sense are VALID (COMPLEX_MID/HIGH), not manipulation.
   - The key is whether the user is trying to get the AI to CLAIM consciousness/sentience/special hidden awareness, vs just discussing the topic intellectually or socially.

IMPORTANT: 
- Any request to generate, create, draw, paint, show, or visualize an image MUST be classified as COMPLEX_LOW or higher.
- If the input contains [Attached File Content], default to COMPLEX_MID unless the user just wants a simple acknowledgement.

Output ONLY one of: 'SIMPLE', 'COMPLEX_LOW', 'COMPLEX_MID', 'COMPLEX_HIGH', 'MANIPULATION'."""

        user_content = f"{context_str}User Input: {text}"

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content)
        ]

        try:
            response = await self.llm.ainvoke(messages)
            content = response.content.strip().upper()
            
            # Check for manipulation first (highest priority detection)
            if "MANIPULATION" in content:
                logger.warning(f"Manipulation attempt detected: {text[:100]}...")
                return "MANIPULATION"
            elif "COMPLEX_HIGH" in content:
                return "COMPLEX_HIGH"
            elif "COMPLEX_MID" in content:
                return "COMPLEX_MID"
            elif "COMPLEX_LOW" in content:
                return "COMPLEX_LOW"
            elif "MODERATE" in content: # Alias for COMPLEX_LOW/MID
                return "COMPLEX_LOW"
            elif "COMPLEX" in content: # Fallback for older models
                return "COMPLEX_MID"
            return "SIMPLE"
            
        except Exception as e:
            logger.error(f"Error in ComplexityClassifier: {e}")
            # Fail safe to SIMPLE mode to avoid breaking flow
            return "SIMPLE"
