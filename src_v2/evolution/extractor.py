from typing import Dict, Any
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from loguru import logger
from src_v2.agents.llm_factory import create_llm

class PreferenceResult(BaseModel):
    preferences: Dict[str, Any] = Field(
        description="Dictionary of extracted preferences. Keys should be snake_case. Values can be strings, booleans, or numbers.",
        default_factory=dict
    )

class PreferenceExtractor:
    def __init__(self):
        base_llm = create_llm(temperature=0.0)
        self.llm = base_llm.with_structured_output(PreferenceResult)
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert User Preference Analyst.
Your task is to extract explicit configuration preferences from user messages.

TARGET PREFERENCES:
1. **verbosity**: 'short', 'medium', 'long', 'dynamic' (e.g., "be concise", "give me detailed answers")
2. **style**: 'casual', 'formal', 'matching' (e.g., "talk to me like a friend", "be professional")
3. **nickname**: string (e.g., "call me Dave")
4. **topics_to_avoid**: string (e.g., "don't talk about politics")
5. **use_emojis**: boolean (e.g., "stop using emojis", "I love emojis")
6. **Any other explicit instruction** about how the bot should behave.

RULES:
- Only extract preferences if the user EXPLICITLY requests a change in behavior.
- Ignore factual statements (use FactExtractor for those).
- Ignore transient requests (e.g., "write a short poem" is a task, not a preference).
- If no preferences are found, return an empty dictionary.

EXAMPLES:
User: "Please keep your answers short."
Result: {{ "preferences": {{ "verbosity": "short" }} }}

User: "Call me Captain from now on."
Result: {{ "preferences": {{ "nickname": "Captain" }} }}

User: "I hate it when you use emojis."
Result: {{ "preferences": {{ "use_emojis": false }} }}

User: "I like pizza."
Result: {{ "preferences": {{}} }} (This is a fact, not a preference)
"""),
            ("human", "{input}")
        ])
        
        self.chain = self.prompt | self.llm

    async def extract_preferences(self, text: str) -> Dict[str, Any]:
        """
        Extracts preferences from text. Returns a dictionary of key-value pairs.
        """
        try:
            result = await self.chain.ainvoke({"input": text})
            return result.preferences
        except Exception as e:
            logger.error(f"Preference extraction failed: {e}")
            return {}

# Global instance
preference_extractor = PreferenceExtractor()
