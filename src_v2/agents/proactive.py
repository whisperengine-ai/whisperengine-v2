from typing import Optional, Dict, Any, List
from datetime import datetime
from loguru import logger
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, BaseMessage
from langchain_core.language_models.chat_models import BaseChatModel

from src_v2.agents.llm_factory import create_llm
from src_v2.core.character import character_manager
from src_v2.memory.manager import memory_manager
from src_v2.knowledge.manager import knowledge_manager
from src_v2.evolution.trust import trust_manager
from src_v2.universe.manager import universe_manager
from src_v2.config.settings import settings
from src_v2.evolution.drives import Drive

class ProactiveAgent:
    """
    Generates context-aware opening messages to initiate conversation with the user.
    """
    def __init__(self) -> None:
        self.llm: BaseChatModel = create_llm(temperature=0.8) # Higher temp for creativity

    async def generate_opener(
        self, 
        user_id: str, 
        user_name: str, 
        character_name: str, 
        is_public: bool = False, 
        channel_id: Optional[str] = None,
        drive: Optional[Drive] = None
    ) -> Optional[str]:
        """
        Generates a proactive opening message based on recent memories and knowledge.
        
        Args:
            user_id: Discord user ID
            user_name: Discord user name
            character_name: Bot character name
            is_public: If True, generates a privacy-safe message for public channels
            channel_id: If provided, retrieves channel-specific conversation history
            drive: The internal drive motivating this initiation (Phase 3.3)
        """
        try:
            # 1. Load Character
            character = character_manager.get_character(character_name)
            if not character:
                logger.error(f"Character {character_name} not found.")
                return None

            # 2. Gather Context
            # We want recent memories to know what we last talked about
            # If channel_id provided, get channel-specific history (more relevant for public channels)
            recent_history: List[BaseMessage]
            if channel_id:
                recent_history = await memory_manager.get_recent_history(
                    user_id, character_name, channel_id=channel_id, limit=5
                )
            else:
                recent_history = await memory_manager.get_recent_history(user_id, character_name, limit=5)
            
            # Format recent memories for the prompt
            recent_memories_str = ""
            if recent_history:
                for msg in recent_history:
                    role = "User" if isinstance(msg, HumanMessage) else character.name
                    recent_memories_str += f"{role}: {msg.content}\n"
            else:
                recent_memories_str = "(No recent history available)"

            # We want knowledge facts to ask about specific things (e.g., "How is your cat?")
            knowledge_facts: str = await knowledge_manager.get_user_knowledge(user_id)
            
            # If public message, sanitize knowledge to remove sensitive topics
            if is_public and knowledge_facts:
                # Filter out potentially sensitive information
                sensitive_keywords: List[str] = [
                    "health", "medical", "doctor", "therapy", "medication",
                    "finance", "money", "debt", "salary", "income",
                    "secret", "private", "confidential",
                    "relationship", "dating", "partner", "divorce",
                    "legal", "lawsuit", "arrest", "crime"
                ]
                
                lines: List[str] = knowledge_facts.split("\n")
                safe_lines: List[str] = []
                for line in lines:
                    line_lower: str = line.lower()
                    if not any(keyword in line_lower for keyword in sensitive_keywords):
                        safe_lines.append(line)
                
                knowledge_facts = "\n".join(safe_lines) if safe_lines else "(Using general knowledge only for public message)"
            
            # We want relationship status to know the tone
            relationship: Dict[str, Any] = await trust_manager.get_relationship_level(user_id, character_name)

            # 3. Construct Prompt
            privacy_instruction: str = ""
            channel_context: str = ""
            
            if is_public:
                privacy_instruction = """
⚠️ PRIVACY WARNING: This message will be sent in a PUBLIC CHANNEL where others can see it.
- Do NOT mention sensitive personal details (health, finances, relationships, secrets, etc.)
- Keep it light, friendly, and appropriate for a group setting
- If you can't find a safe topic, use a generic friendly greeting instead
"""
                if channel_id and recent_history:
                    # Public channel with history - these topics are safe since they were already discussed publicly
                    channel_context = """
✅ SAFE CONTEXT: The recent conversation topics below were already discussed in THIS PUBLIC CHANNEL.
You CAN reference these topics safely since they were public conversations.
Look for unfinished discussions or topics the user didn't respond to - this is your chance to follow up!
"""
            else:
                # Private DM - all topics are fair game
                channel_context = "(Private conversation - all known topics are available)"
            
            # Prepare variables for the template
            current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            universe_overview = await universe_manager.get_universe_overview()
            universe_context = f"Planets: {universe_overview.get('planet_count', 0)}\n"
            universe_context += f"Inhabitants: {universe_overview.get('total_inhabitants', 0)}\n"
            universe_context += f"Top Topics: {', '.join(universe_overview.get('top_universal_topics', []))}"

            # Drive Context (Phase 3.3)
            drive_context = ""
            if drive:
                drive_context = f"""
[INTERNAL DRIVE]
You are reaching out because you feel: {drive.name.upper()} ({drive.description})
This feeling is motivating you to connect. Let this feeling color your message tone.
"""

            system_prompt = f"""You are {character.name}.
{character.system_prompt}

TASK:
You are initiating a conversation with the user after a period of silence.
Your goal is to send a friendly, relevant opening message.
Do NOT say "Hello" or "Hi" generically.
Reference a specific topic from the past or a fact you know about them.
Keep it short (1-2 sentences).
Be natural, like a friend texting another friend.

Look for:
- Unfinished conversations where the user stopped responding
- Questions you asked that weren't answered
- Topics that were left hanging without closure
- Things they mentioned wanting to do or work on

{privacy_instruction}
{channel_context}
{drive_context}

[RELATIONSHIP STATUS]
Level: {relationship.get('level', 'Stranger')}
Trust: {relationship.get('trust_score', 0)}

[KNOWN FACTS]
{knowledge_facts}
"""

            prompt: ChatPromptTemplate = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", "Generate a proactive opening message now.")
            ])

            # 4. Generate
            chain = prompt | self.llm
            response = await chain.ainvoke({
                "user_name": user_name,
                "current_datetime": current_datetime,
                "universe_context": universe_context,
                "knowledge_context": knowledge_facts,  # Using knowledge_facts for knowledge_context
                "recent_memories": recent_memories_str
            })
            
            content = response.content
            opener: str
            if isinstance(content, str):
                opener = content.strip()
            else:
                # Handle list content (rare for text-only models but possible in LangChain)
                opener = str(content).strip()

            logger.info(f"Generated proactive opener for {user_id}: {opener}")
            return opener

        except Exception as e:
            logger.error(f"Failed to generate proactive opener: {e}")
            return None

proactive_agent = ProactiveAgent()
