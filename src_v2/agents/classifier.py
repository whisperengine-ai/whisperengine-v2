from typing import Literal, List, Optional
from loguru import logger
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage

from src_v2.agents.llm_factory import create_llm

class ComplexityClassifier:
    """
    Determines if a user message requires 'Fast Mode' (Simple) or 'Reflective Mode' (Complex).
    """
    def __init__(self):
        # Use 'router' mode for potentially faster/cheaper model, 0.0 temp for consistency
        self.llm = create_llm(temperature=0.0, mode="router")

    async def classify(self, text: str, chat_history: Optional[List[BaseMessage]] = None) -> Literal["SIMPLE", "COMPLEX_LOW", "COMPLEX_MID", "COMPLEX_HIGH"]:
        """
        Classifies the input text as SIMPLE or COMPLEX with granularity.
        
        SIMPLE: Greetings, direct questions, casual chat, simple facts.
        COMPLEX_LOW: Requires 1-2 tool calls (e.g. simple fact lookup).
        COMPLEX_MID: Requires 3-5 tool calls (e.g. synthesis of multiple facts).
        COMPLEX_HIGH: Requires 6+ tool calls (e.g. deep reasoning, multi-step research).
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
2. COMPLEX_LOW: Needs 1-2 simple lookups (e.g. "Where did you grow up?", "What is your favorite color?").
3. COMPLEX_MID: Needs 3-5 steps. Synthesis of multiple facts, emotional analysis, or moderate reasoning.
4. COMPLEX_HIGH: Needs 6+ steps. Deep philosophical questions, complex multi-step research, or very ambiguous queries requiring exploration.

Output ONLY one of: 'SIMPLE', 'COMPLEX_LOW', 'COMPLEX_MID', 'COMPLEX_HIGH'."""

        user_content = f"{context_str}User Input: {text}"

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content)
        ]

        try:
            response = await self.llm.ainvoke(messages)
            content = response.content.strip().upper()
            
            if "COMPLEX_HIGH" in content:
                return "COMPLEX_HIGH"
            elif "COMPLEX_MID" in content:
                return "COMPLEX_MID"
            elif "COMPLEX_LOW" in content:
                return "COMPLEX_LOW"
            elif "COMPLEX" in content: # Fallback for older models
                return "COMPLEX_MID"
            return "SIMPLE"
            
        except Exception as e:
            logger.error(f"Error in ComplexityClassifier: {e}")
            # Fail safe to SIMPLE mode to avoid breaking flow
            return "SIMPLE"
