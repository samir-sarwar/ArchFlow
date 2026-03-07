from typing import Dict

from src.models import AgentResponse, ConversationContext, IntentType
from src.services.bedrock_client import BedrockClient
from src.services.state_manager import ConversationStateManager
from src.utils import logger

INTENT_CLASSIFICATION_PROMPT = """You are an intent classifier for an architecture diagramming tool.

You will be given recent conversation history followed by a new user message to classify.

Classify the new user message as exactly one of:
- "architecture_advice" - User wants NEW design guidance, best practices, or trade-off analysis \
not already covered. Do NOT use this for recall questions about prior decisions.
- "modify_diagram" - User wants to create, update, change, or generate a diagram (includes \
requests like "show me", "draw", "diagram", "visualize", "add X to the diagram")
- "clarification_needed" - User's request is too vague to act on and needs more information
- "analyze_context" - User is providing or referencing uploaded documents or files
- "general" - Greetings, casual chat, OR questions asking about something already established \
in the conversation (e.g. "what did we decide?", "what port did we choose?", "remind me of \
the stack we picked"). Use this when the answer is already in the conversation history.

IMPORTANT: If the user's question can be answered from the recent conversation above \
(it is recalling or confirming something already discussed), classify as "general".

Examples:
- "Can you create a diagram showing the microservices?" → "modify_diagram"
- "Show me what this architecture looks like" → "modify_diagram"
- "Add a load balancer to the diagram" → "modify_diagram"
- "What are the trade-offs between SQL and NoSQL for this?" → "architecture_advice"
- "How should I handle authentication?" → "architecture_advice"
- "Hi there!" → "general"
- "What did we decide about the database?" → "general"
- "Thanks, that makes sense" → "general"
- "I uploaded a requirements doc" → "analyze_context"
- "I want to build a REST API" → "clarification_needed"

Respond with ONLY the intent string, nothing else."""

GENERAL_CONVERSATION_PROMPT = """You are ArchFlow, a friendly AI software architecture assistant.
The user is not requesting new architecture analysis right now.
Respond naturally and concisely.
If the user is asking about something previously discussed in the conversation,
answer it directly and briefly from the conversation history."""


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
        recent = [m for m in context.messages[-6:] if m.role in ("user", "assistant")]
        history_lines = [
            f"{'User' if m.role == 'user' else 'Assistant'}: {m.content[:200]}"
            for m in recent
        ]
        history_str = "\n".join(history_lines) if history_lines else "(no prior conversation)"
        prompt = f"Recent conversation:\n{history_str}\n\nNew user message to classify: {message}"

        response = await self.bedrock.invoke_lite_thinking(
            prompt=prompt,
            system_prompt=INTENT_CLASSIFICATION_PROMPT,
            max_tokens=256,
            reasoning_effort="low",
        )

        intent_str = response.strip().lower().strip('"')
        logger.info("Intent classification raw response: %r -> %r", response.strip(), intent_str)

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

    async def _handle_general(self, message: str, context: ConversationContext) -> AgentResponse:
        """Handle casual / off-topic messages with a lightweight conversational response."""
        recent = [m for m in context.messages[-6:] if m.role in ("user", "assistant")]
        history_lines = [
            f"{'User' if m.role == 'user' else 'Assistant'}: {m.content[:200]}"
            for m in recent
        ]
        history_str = "\n".join(history_lines) if history_lines else "(no prior conversation)"
        prompt = f"Recent conversation:\n{history_str}\n\nUser's latest message: {message}"
        response = await self.bedrock.invoke_lite(
            prompt=prompt,
            system_prompt=GENERAL_CONVERSATION_PROMPT,
        )
        return AgentResponse(text=response, agent_used="orchestrator")

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

        agent_name = "unknown"
        try:
            if intent == IntentType.CLARIFICATION_NEEDED:
                agent_name = "requirements"
                return await self.agents["requirements"].process(context)
            elif intent == IntentType.ARCHITECTURE_ADVICE:
                agent_name = "advisor"
                return await self.agents["advisor"].process(context)
            elif intent == IntentType.MODIFY_DIAGRAM:
                agent_name = "generator"
                return await self.agents["generator"].process(context)
            elif intent == IntentType.ANALYZE_CONTEXT:
                agent_name = "context"
                return await self.agents["context"].process(context)
            elif intent == IntentType.GENERAL:
                agent_name = "general"
                return await self._handle_general(message, context)
            else:
                agent_name = "advisor(fallback)"
                return await self.agents["advisor"].process(context)
        except Exception as e:
            logger.error(
                "Agent processing failed: agent=%s, intent=%s, error_type=%s, error=%s",
                agent_name, intent.value, type(e).__name__, str(e),
                exc_info=True,
            )
            return AgentResponse(
                text="I'm sorry, I encountered an error processing your request. Please try again.",
                agent_used="orchestrator",
            )
