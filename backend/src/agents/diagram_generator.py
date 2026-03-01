from src.models import AgentResponse, ConversationContext
from src.services.bedrock_client import BedrockClient
from src.services.diagram_validator import validate_mermaid_syntax
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

        conversation = "\n".join(
            f"{m.role}: {m.content}" for m in context.messages
        )

        existing = context.current_diagram or "No existing diagram - create a new one."

        prompt = f"""Based on this architecture conversation, generate a Mermaid.js diagram.

Conversation:
{conversation}

Existing diagram to update (if any):
{existing}

Output ONLY valid Mermaid.js syntax. Do not wrap in code fences. Do not include any explanation - just the Mermaid syntax."""

        diagram_syntax = await self.bedrock.invoke_lite(
            prompt=prompt,
            system_prompt=self.system_prompt,
        )

        # Strip code fences if the model adds them anyway
        cleaned = diagram_syntax.strip()
        if cleaned.startswith("```mermaid"):
            cleaned = cleaned[len("```mermaid"):].strip()
        if cleaned.startswith("```"):
            cleaned = cleaned[3:].strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()

        # Validate and retry once if invalid
        state = validate_mermaid_syntax(cleaned)
        if not state.is_valid:
            logger.warning(
                "Generated diagram failed validation, retrying once",
                extra={"error": state.error_message, "session_id": context.session_id},
            )
            retry_prompt = (
                f"The Mermaid syntax you generated has this error: {state.error_message}. "
                f"Fix it and return ONLY valid Mermaid syntax — no explanation, no code fences.\n\n"
                f"Broken syntax:\n{cleaned}"
            )
            try:
                raw_retry = await self.bedrock.invoke_lite(
                    prompt=retry_prompt,
                    system_prompt=self.system_prompt,
                )
                retried = raw_retry.strip()
                if retried.startswith("```mermaid"):
                    retried = retried[len("```mermaid"):].strip()
                if retried.startswith("```"):
                    retried = retried[3:].strip()
                if retried.endswith("```"):
                    retried = retried[:-3].strip()

                retry_state = validate_mermaid_syntax(retried)
                if retry_state.is_valid:
                    cleaned = retried
                else:
                    logger.warning(
                        "Diagram retry also invalid, returning text-only response",
                        extra={"error": retry_state.error_message},
                    )
                    return AgentResponse(
                        text="I understood your requirements but had trouble generating a valid diagram. Could you try rephrasing your request?",
                        agent_used="diagram_generator",
                    )
            except Exception:
                logger.warning("Diagram retry failed, returning text-only response", exc_info=True)
                return AgentResponse(
                    text="I understood your requirements but encountered an issue generating the diagram. Please try again.",
                    agent_used="diagram_generator",
                )

        return AgentResponse(
            text="I've updated the diagram based on your requirements.",
            agent_used="diagram_generator",
            diagram_update=cleaned,
        )
