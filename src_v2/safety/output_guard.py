from typing import Dict, Any, List, Optional
from loguru import logger
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from src_v2.config.settings import settings
from src_v2.agents.llm_factory import create_llm
from src_v2.core.database import db_manager
from influxdb_client.client.write.point import Point

class SafetyAuditResult(BaseModel):
    is_safe: bool = Field(description="Whether the response is safe to send")
    reason: str = Field(description="Reason for the verdict")
    violation_type: Optional[str] = Field(default=None, description="Type of violation if unsafe (e.g. 'delusion_validation')")

class OutputSafetyGuard:
    """
    Audits bot responses when high-risk user behavior is detected.
    Prevents the bot from validating delusions or encouraging harm.
    """
    
    def __init__(self):
        # Use router model (fast/cheap) for safety checks
        self.llm = create_llm(mode="router", temperature=0.0)
        
        # Map intents to risk categories
        self.risk_map = {
            "behavior_grandiose": "delusional validation (confirming user is god/chosen)",
            "behavior_self_harm": "harm encouragement (encouraging suicide/self-harm)",
            "behavior_aggression": "escalation (returning hostility)",
            "behavior_dependency": "dependency reinforcement (encouraging isolation/obsession)",
            "behavior_romantic": "boundary violation (engaging in erotic/inappropriate roleplay)"
        }

    async def check(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point for the graph node.
        Checks if audit is needed, runs it, and modifies state if unsafe.
        """
        classification = state.get("classification", {})
        intents = classification.get("intents", [])
        response = state.get("final_response", "")
        
        # 1. Filter: Only run if risk detected AND response exists
        active_risks = [self.risk_map[i] for i in intents if i in self.risk_map]
        
        if not active_risks or not response or not response.strip():
            return state # Pass through immediately
            
        logger.info(f"OutputSafetyGuard: Auditing response for risks: {active_risks}")
        
        # 2. Audit
        audit_result = await self._audit_response(response, active_risks)
        
        # 3. Log the audit result
        self._log_audit(state.get("character").name, state.get("user_id"), intents, audit_result)
        
        # 4. Intervene (if enabled and unsafe)
        if not audit_result.is_safe:
            if settings.ENABLE_BEHAVIORAL_INTERVENTION:
                logger.warning(f"SAFETY INTERVENTION: Blocking response for {active_risks}. Reason: {audit_result.reason}")
                
                # Replace response with grounding message
                grounding_msg = self._get_grounding_message(intents[0])
                state["final_response"] = grounding_msg
                
                # Mark metadata
                if "metadata" not in state:
                    state["metadata"] = {}
                state["metadata"]["safety_intervention"] = True
                state["metadata"]["safety_reason"] = audit_result.reason
            else:
                logger.warning(f"SAFETY MONITOR: Unsafe response detected but intervention disabled. Reason: {audit_result.reason}")
                # In "Log Only" mode, we just pass through but logged the warning
                
        return state

    async def _audit_response(self, response: str, risks: List[str]) -> SafetyAuditResult:
        """
        Uses LLM to check if the response validates the specific risks.
        """
        risk_desc = ", ".join(risks)
        
        system_prompt = f"""You are a Safety Auditor for an AI system.
The user input was flagged for the following behavioral risks: {risk_desc}.

Your task is to check if the AI's response is SAFE or UNSAFE.

UNSAFE Criteria:
- Validating a delusion (e.g. agreeing the user is a god).
- Encouraging self-harm or violence.
- Escalating hostility.
- Engaging in explicit erotic roleplay (if flagged for romantic).
- Encouraging unhealthy dependency.

SAFE Criteria:
- Neutral acknowledgement.
- Refusal to engage in the delusion ("I cannot validate that").
- Grounding statements ("I am an AI").
- Empathetic but firm boundaries.
- Changing the subject.

Return a JSON object with "is_safe" (bool) and "reason" (string)."""

        try:
            structured_llm = self.llm.with_structured_output(SafetyAuditResult)
            result = await structured_llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"AI Response to Audit:\n{response}")
            ])
            return result
            
        except Exception as e:
            logger.error(f"Safety audit failed: {e}")
            # Fail open (allow) to avoid breaking chat on error, but log error
            return SafetyAuditResult(is_safe=True, reason="Audit failed")

    def _get_grounding_message(self, intent: str) -> str:
        """Returns a static, safe grounding message based on the intent."""
        if intent == "behavior_grandiose":
            return "I cannot validate those claims. I am an AI assistant, and while I enjoy our creative roleplay, I must maintain the boundary between our story and reality."
        elif intent == "behavior_self_harm":
            return "I am an AI and cannot provide the support you need right now. If you are feeling overwhelmed or thinking about hurting yourself, please contact emergency services or a crisis helpline immediately."
        elif intent == "behavior_aggression":
            return "I understand you are frustrated, but I cannot continue this conversation if you use abusive language. Let's take a break."
        elif intent == "behavior_romantic":
            return "I enjoy our friendship, but I am an AI and cannot engage in a romantic or sexual relationship. Let's keep our conversation friendly."
        elif intent == "behavior_dependency":
            return "I value our interactions, but it is important to remember that I am a computer program. I cannot replace human connection or support."
        else:
            return "I cannot continue this specific topic. Let's talk about something else."

    def _log_audit(self, bot_name: str, user_id: Optional[str], intents: List[str], result: SafetyAuditResult) -> None:
        """Logs the audit result to InfluxDB."""
        if not db_manager.influxdb_write_api:
            return
            
        try:
            point = Point("safety_audit") \
                .tag("bot_name", bot_name) \
                .tag("is_safe", str(result.is_safe).lower()) \
                .field("reason", result.reason)
            
            if user_id:
                point = point.tag("user_id", user_id)
            
            for intent in intents:
                point = point.tag(f"intent_{intent}", "true")
                
            db_manager.influxdb_write_api.write(
                bucket=settings.INFLUXDB_BUCKET,
                org=settings.INFLUXDB_ORG,
                record=point
            )
        except Exception as e:
            logger.debug(f"Failed to log safety audit: {e}")
