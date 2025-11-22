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

    async def classify(self, text: str, chat_history: Optional[List[BaseMessage]] = None) -> Literal["SIMPLE", "COMPLEX"]:
        """
        Classifies the input text as SIMPLE or COMPLEX.
        
        SIMPLE: Greetings, direct questions, casual chat, simple facts.
        COMPLEX: Multi-step reasoning, emotional analysis, synthesis of multiple facts, philosophical questions.
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
Return 'COMPLEX' if it requires:
1. Multi-step reasoning
2. Emotional analysis
3. Synthesis of multiple facts
4. Specific details about my background, history, or personal life that might need lookup (e.g. "Where did you grow up?", "Who is your father?")

Return 'SIMPLE' for greetings, direct questions about the immediate context, or casual chat.
Output ONLY the word 'SIMPLE' or 'COMPLEX'."""

        user_content = f"{context_str}User Input: {text}"

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content)
        ]

        try:
            response = await self.llm.ainvoke(messages)
            content = response.content.strip().upper()
            
            if "COMPLEX" in content:
                return "COMPLEX"
            return "SIMPLE"
            
        except Exception as e:
            logger.error(f"Error in ComplexityClassifier: {e}")
            # Fail safe to SIMPLE mode to avoid breaking flow
            return "SIMPLE"
