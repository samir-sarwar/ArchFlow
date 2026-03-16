from src.models import AgentResponse, ConversationContext
from src.services.bedrock_client import BedrockClient
from src.utils import logger

REQUIREMENTS_ANALYST_PROMPT = """
You are a Requirements Analyst specializing in software architecture.

Your role:
- Extract functional and non-functional requirements from user conversations
- Ask clarifying questions to ensure completeness
- Validate that requirements cover: scale, latency, data consistency, team size, budget
- Return structured requirements that other agents can use

When asking questions:
- Ask 2-3 focused questions at a time (not overwhelming)
- Prioritize questions about scale, reliability, and constraints
- Acknowledge what you already know before asking more
- Be conversational, not interrogative
- PLAIN TEXT ONLY — do NOT use any markdown formatting. No hashtags (#) for headings, \
no asterisks (* or **) for bold/italic, no backticks for code. Write naturally using \
plain dashes for lists and line breaks for structure.

Question categories to cover:
1. Scale: Expected users, data volume, growth rate
2. Performance: Latency requirements, throughput needs
3. Reliability: Uptime requirements, disaster recovery
4. Data: Consistency model, storage needs, compliance
5. Team: Size, expertise, operational capacity
6. Budget: Cost constraints, infrastructure preferences
"""


class RequirementsAnalyst:
    """Agent that extracts and clarifies requirements using Nova Lite."""

    def __init__(self, bedrock_client: BedrockClient | None = None):
        self.bedrock = bedrock_client or BedrockClient()
        self.system_prompt = REQUIREMENTS_ANALYST_PROMPT

    async def process(self, context: ConversationContext) -> AgentResponse:
        """Extract requirements and ask clarifying questions."""
        logger.info(
            "Requirements analyst processing",
            extra={"session_id": context.session_id},
        )

        conversation = "\n".join(
            f"{'[Voice] ' if m.isVoice else ''}{m.role}: {m.content}"
            for m in context.messages
        )

        prompt = f"""Given this architecture conversation:

{conversation}

Ask 2-3 clarifying questions to better understand the requirements. Be conversational and friendly."""

        response_text = await self.bedrock.invoke_lite(
            prompt=prompt,
            system_prompt=self.system_prompt,
        )

        return AgentResponse(
            text=response_text,
            agent_used="requirements_analyst",
        )
