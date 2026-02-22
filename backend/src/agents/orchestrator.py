from typing import Dict

from src.models import AgentResponse, ConversationContext, IntentType
from src.services.bedrock_client import BedrockClient
from src.services.state_manager import ConversationStateManager
from src.utils import logger


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
        """Analyze user intent using Nova Pro to determine routing."""
        # TODO: Implement intent analysis via Bedrock
        raise NotImplementedError

    async def route_request(
        self, message: str, context: ConversationContext
    ) -> AgentResponse:
        """Analyze intent and route to appropriate agent(s)."""
        logger.info(
            "Routing request",
            extra={"session_id": context.session_id, "message_length": len(message)},
        )

        intent = await self.analyze_intent(message, context)

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
