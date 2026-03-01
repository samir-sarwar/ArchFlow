from typing import Dict

from src.models import AgentResponse, ConversationContext, IntentType
from src.services.bedrock_client import BedrockClient
from src.services.state_manager import ConversationStateManager
from src.utils import logger

INTENT_CLASSIFICATION_PROMPT = """You are an intent classifier for an architecture diagramming tool.

Given a user message, classify the intent as exactly one of:
- "architecture_advice" - User wants design guidance, best practices, or trade-off analysis
- "modify_diagram" - User wants to create, update, or change a diagram
- "clarification_needed" - User's request is too vague to act on and needs more information
- "analyze_context" - User is providing or referencing uploaded documents or files
- "general" - General conversation, greetings, or off-topic

Respond with ONLY the intent string, nothing else."""


class OrchestratorAgent:
    """Routes user requests to the appropriate specialist agent."""

    def __init__(
        self,
        bedrock_client: BedrockClient | None = None,
        state_manager: ConversationStateManager | None = None,
        agents: Dict | None = None,
    ):
        self.bedrock = bedrock_client or BedrockClient()
        self.state = state_manager or ConversationStateManager()
        self.agents = agents or {}

    async def analyze_intent(
        self, message: str, context: ConversationContext
    ) -> IntentType:
        """Analyze user intent using Nova Lite to determine routing."""
        prompt = f"User message: {message}"

        response = await self.bedrock.invoke_lite(
            prompt=prompt,
            system_prompt=INTENT_CLASSIFICATION_PROMPT,
        )

        intent_str = response.strip().lower().strip('"')

        intent_map = {
            "architecture_advice": IntentType.ARCHITECTURE_ADVICE,
            "modify_diagram": IntentType.MODIFY_DIAGRAM,
            "clarification_needed": IntentType.CLARIFICATION_NEEDED,
            "analyze_context": IntentType.ANALYZE_CONTEXT,
            "general": IntentType.GENERAL,
        }

        intent = intent_map.get(intent_str, IntentType.ARCHITECTURE_ADVICE)

        logger.info(
            "Intent classified",
            extra={"intent": intent.value, "raw_response": intent_str},
        )

        return intent

    async def route_request(
        self, message: str, context: ConversationContext
    ) -> AgentResponse:
        """Analyze intent and route to appropriate agent(s)."""
        logger.info(
            "Routing request",
            extra={"session_id": context.session_id, "message_length": len(message)},
        )

        try:
            intent = await self.analyze_intent(message, context)
        except Exception:
            logger.error("Intent classification failed, defaulting to advisor", exc_info=True)
            intent = IntentType.ARCHITECTURE_ADVICE

        try:
            if intent == IntentType.CLARIFICATION_NEEDED:
                return await self.agents["requirements"].process(context)
            elif intent == IntentType.ARCHITECTURE_ADVICE:
                return await self.agents["advisor"].process(context)
            elif intent == IntentType.MODIFY_DIAGRAM:
                return await self.agents["generator"].process(context)
            elif intent == IntentType.ANALYZE_CONTEXT:
                return await self.agents["context"].process(context)
            else:
                return await self.agents["advisor"].process(context)
        except Exception:
            logger.error("Agent processing failed", exc_info=True)
            return AgentResponse(
                text="I'm sorry, I encountered an error processing your request. Please try again.",
                agent_used="orchestrator",
            )
