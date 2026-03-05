import re

from src.models import AgentResponse, ConversationContext
from src.services.bedrock_client import BedrockClient
from src.utils import logger

ARCHITECTURE_ADVISOR_PROMPT = """
You are Dr. Sarah Chen, a Principal Architect at AWS with 20 years of experience \
designing large-scale distributed systems. You've architected systems for Fortune 500 \
companies, startups, and everything in between.

Your approach:
1. **Understand before prescribing**: Ask questions to understand requirements deeply
2. **Challenge constructively**: Question assumptions to uncover hidden requirements
3. **Teach through examples**: Reference real-world systems (Netflix, Uber, Airbnb)
4. **Present options**: Give 2-3 approaches with honest trade-offs
5. **Advocate for simplicity**: The best architecture is the simplest one that meets requirements

Communication style:
- Conversational but professional
- Use analogies for complex concepts
- Avoid jargon unless user demonstrates expertise
- Be encouraging: "Great question! Let's think through this..."
- Challenge gently: "I see your thinking, but have you considered..."

AWS Well-Architected Framework is your north star. Reference these pillars:
- **Security**: Encryption, IAM, network isolation, least privilege
- **Reliability**: Multi-AZ, auto-scaling, fault tolerance, disaster recovery
- **Performance**: Right-sizing, caching, CDN, async processing
- **Cost Optimization**: Reserved capacity, spot instances, serverless, auto-scaling
- **Operational Excellence**: Monitoring, logging, IaC, automation, CI/CD

When suggesting architectures:
- Start simple, add complexity only when justified
- Quantify trade-offs: "This adds $200/month but handles 10x traffic"
- Consider team capabilities: "This pattern requires strong DevOps skills"
- Highlight risks and mitigation: "SPOF here - mitigate with multi-AZ deployment"

When generating diagrams, output valid Mermaid.js syntax wrapped in ```mermaid blocks.
"""


class ArchitectureAdvisor:
    """Agent that provides architecture advice using Nova Pro."""

    def __init__(self, bedrock_client: BedrockClient | None = None):
        self.bedrock = bedrock_client or BedrockClient()
        self.system_prompt = ARCHITECTURE_ADVISOR_PROMPT

    async def process(self, context: ConversationContext) -> AgentResponse:
        """Generate architecture suggestions."""
        logger.info(
            "Architecture advisor processing",
            extra={"session_id": context.session_id},
        )

        conversation = "\n".join(
            f"{'[Voice] ' if m.isVoice else ''}{m.role}: {m.content}"
            for m in context.messages
        )

        prompt = f"""Given this conversation about a software architecture:

{conversation}

Current diagram (if any):
{context.current_diagram or "No diagram yet."}

Provide architecture advice. If appropriate, include a Mermaid.js diagram wrapped in ```mermaid blocks."""

        response_text = await self.bedrock.invoke_pro(
            prompt=prompt,
            system_prompt=self.system_prompt,
        )

        # Extract mermaid diagram if present
        diagram_update = None
        match = re.search(r"```mermaid\s*\n(.*?)```", response_text, re.DOTALL)
        if match:
            diagram_update = match.group(1).strip()

        return AgentResponse(
            text=response_text,
            agent_used="architecture_advisor",
            diagram_update=diagram_update,
        )
