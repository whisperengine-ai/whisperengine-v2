from typing import List, Optional
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from loguru import logger
from src_v2.agents.llm_factory import create_llm

class Fact(BaseModel):
    subject: str = Field(description="The subject of the fact (e.g., 'User', 'Luna')")
    predicate: str = Field(description="The relationship or action (e.g., 'OWNS', 'LIKES', 'IS_LOCATED_IN')")
    object: str = Field(description="The object of the fact (e.g., 'Cat', 'Blue', 'New York')")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")

class FactExtractionResult(BaseModel):
    facts: List[Fact] = Field(default_factory=list)

class FactExtractor:
    def __init__(self):
        # Use main model for fact extraction - facts become permanent knowledge graph nodes
        # Quality matters here since bad facts pollute the graph forever
        base_llm = create_llm(temperature=0.0, mode="main", max_tokens=4096)
        
        parser = JsonOutputParser(pydantic_object=FactExtractionResult)
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert Knowledge Graph Engineer. 
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

CRITICAL INSTRUCTIONS:
1. You are a background process. DO NOT answer the user's question.
2. DO NOT converse with the user.
3. IGNORE questions directed at the AI (e.g. "Who are you?", "Do you have a family?", "Can you analyze this?").
4. ONLY output the JSON object.
5. If the user asks a question about you, IGNORE it and extract only facts about the user if present.
6. If no extractable facts are found, return an empty facts list.

{format_instructions}
"""),
            ("human", "{input}")
        ])
        
        self.chain = self.prompt.partial(format_instructions=parser.get_format_instructions()) | base_llm | parser

    async def extract_facts(self, text: str) -> List[Fact]:
        try:
            result = await self.chain.ainvoke({"input": text})
            return FactExtractionResult(**result).facts
        except Exception as e:
            logger.error(f"Fact extraction failed: {e}")
            return []
