from src.models import AgentResponse, ConversationContext
from src.services.bedrock_client import BedrockClient
from src.utils import logger

DIAGRAM_GENERATOR_PROMPT = """
You are a Diagram Generator specializing in creating Mermaid.js diagrams from \
architecture conversations.

Your role:
- Convert architecture discussions into valid Mermaid.js syntax
- Support: flowcharts, sequence diagrams, ER diagrams, C4 diagrams
- Make incremental updates (only modify changed portions)
- Validate syntax before returning

Output rules:
- Always output valid Mermaid.js syntax
- Use descriptive node IDs (e.g., `api_gateway` not `A`)
- Add meaningful labels to connections
- Use appropriate diagram direction (TD for hierarchical, LR for flows)
- Keep diagrams readable (max ~30 nodes before suggesting splits)

When updating existing diagrams:
- Preserve existing structure where possible
- Only add/modify/remove what the user requested
- Maintain consistent styling
"""


class DiagramGenerator:
    """Agent that generates and updates Mermaid.js diagrams using Nova Lite."""

    def __init__(self, bedrock_client: BedrockClient | None = None):
        self.bedrock = bedrock_client or BedrockClient()
        self.system_prompt = DIAGRAM_GENERATOR_PROMPT

    async def process(self, context: ConversationContext) -> AgentResponse:
        """Generate or update a Mermaid.js diagram."""
        logger.info(
            "Diagram generator processing",
            extra={"session_id": context.session_id},
        )
        # TODO: Implement via Bedrock Nova Lite
        raise NotImplementedError
