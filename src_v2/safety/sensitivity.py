"""
LLM-Based Sensitivity Detection (Phase S3)

Provides context-aware sensitivity detection for content that passes
keyword-based filters. Used primarily for Universe Events (cross-bot gossip)
to prevent sharing personal information that doesn't contain obvious keywords.

Example:
    "I finally told my mom about the situation"
    - Keywords: No sensitive keywords detected
    - LLM: "Personal family matter" → SENSITIVE → Block sharing
"""

from typing import Tuple
from pydantic import BaseModel, Field
from loguru import logger
from langchain_core.messages import SystemMessage, HumanMessage

from src_v2.agents.llm_factory import create_llm


class SensitivityResult(BaseModel):
    """Structured output from sensitivity check."""
    sensitive: bool = Field(description="Whether the content should be kept private")
    reason: str = Field(default="", description="Brief explanation of why it's sensitive or safe")


class SensitivityChecker:
    """
    LLM-based sensitivity detection for cross-bot sharing.
    
    This is a second layer of protection after keyword filtering.
    It catches context-dependent sensitivity that keywords miss.
    """
    
    def __init__(self):
        # Use router model (fast/cheap) for classification
        self.llm = create_llm(temperature=0.0, mode="router")

    async def is_sensitive(
        self, 
        content: str, 
        topic: str = "",
        event_summary: str = ""
    ) -> Tuple[bool, str]:
        """
        Check if content is too sensitive to share across bots.
        
        Args:
            content: The user's original message
            topic: The detected topic/category (e.g., "career", "family")
            event_summary: The summary that would be shared
            
        Returns:
            Tuple of (is_sensitive: bool, reason: str)
        """
        system_prompt = """You are a Privacy Guardian for an AI system.

Your job is to decide if information should be kept PRIVATE between a user and their AI companion, 
or if it's SAFE to share with other AI characters in the system (cross-bot gossip).

ALWAYS KEEP PRIVATE:
1. Personal family matters (conflicts, health of family members, estrangements)
2. Emotional vulnerabilities or struggles (even if not using "sad" keywords)
3. Workplace/school conflicts or complaints about specific people
4. Relationship dynamics (friendships going through rough patches, not just romantic)
5. Health-adjacent topics (stress, burnout, sleep issues, energy problems)
6. Financial stress (even without money keywords like "debt")
7. Secrets or confidential information (even if user doesn't say "secret")
8. Anything the user might not want repeated to others

SAFE TO SHARE:
1. General positive news (got a promotion, moving to a new city)
2. Public achievements (graduation, wedding announcement)
3. General emotional states without personal details ("having a great day")
4. Hobbies and interests
5. General life updates that aren't sensitive

Return JSON with:
- "sensitive": true if private, false if safe to share
- "reason": brief explanation (1 sentence)"""

        user_prompt = f"""Message: "{content}"
Detected topic: {topic or "general"}
Would be shared as: "{event_summary or "User shared some news"}"

Should this be kept private or is it safe for cross-bot sharing?"""

        try:
            structured_llm = self.llm.with_structured_output(SensitivityResult)
            result = await structured_llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])
            
            if isinstance(result, SensitivityResult):
                logger.debug(f"Sensitivity check: sensitive={result.sensitive}, reason={result.reason}")
                return result.sensitive, result.reason
            
            # Fallback if unexpected type
            return True, "Unexpected response type - defaulting to private"
            
        except Exception as e:
            logger.error(f"Sensitivity check failed: {e}")
            # Fail closed (private) if check fails
            return True, f"Check failed: {str(e)}"


# Global instance
sensitivity_checker = SensitivityChecker()
