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

Output rules:
- Always output valid Mermaid.js syntax
- Use descriptive node IDs (e.g., `api_gateway` not `A`)
- Add meaningful labels to connections
- Keep diagrams readable (max ~30 nodes before suggesting splits)

Layout rules (apply to all diagram types where applicable):
- Default to `graph TD` (top-down) with the entry point (API Gateway, Client, User) at the top
- Group related nodes into subgraphs to contain connections and reduce line crossings:
  - Databases and storage in a "Data Stores" subgraph at the bottom
  - Security, logging, tracing, and monitoring in a "Security & Monitoring" subgraph
  - Core services in their own logical subgraph(s)
- Use dotted arrows `-.->` for background/non-critical-path connections (logging, tracing, metrics, monitoring) to visually separate them from the main request flow (`-->`)
- Arrange nodes in logical tiers (entry → services → data) to create a clean hierarchical layout and minimise line crossings
- Consolidate multi-point links: when multiple nodes connect to the same destination (e.g., a logger, shared database, global state), do NOT draw individual lines from each node. Instead, link from the subgraph boundary to the destination, or create a "Hub" node to aggregate the traffic into a single connection.

When updating existing diagrams:
- Preserve existing structure where possible
- Only add/modify/remove what the user requested
- Maintain consistent styling

CRITICAL Mermaid.js syntax rules — violations cause render failures:
- First line MUST be a type declaration: `flowchart TD`, `sequenceDiagram`, `erDiagram`, etc.
- Node IDs must be alphanumeric with underscores only (no spaces, no hyphens, no dots)
- Labels with special characters MUST be in double quotes: `node_id["Label with (parens)"]`
- Arrow syntax: `-->`, `---`, `-.->`, `==>` (no spaces within arrows)
- Use `-->|label|` for edge labels, NOT `-- label -->`
- Subgraphs: `subgraph Title` ... `end` (must close every subgraph with `end`)
- No trailing commas, no semicolons at line ends
- Sequence diagram: participants must be declared before use
- Do NOT use HTML tags or markdown inside node labels
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

        recent_messages = context.messages[-15:]
        conversation_lines = [
            f"{'[Voice] ' if m.isVoice else ''}{m.role}: {m.content}"
            for m in recent_messages
        ]
        conversation = "\n".join(conversation_lines)
        if len(conversation) > 12_000:
            conversation = conversation[-12_000:]

        existing = context.current_diagram or "No existing diagram - create a new one."

        prompt = f"""Based on this architecture conversation, generate a Mermaid.js diagram.

Conversation:
{conversation}

Existing diagram to update (if any):
{existing}

Output ONLY valid Mermaid.js syntax. Do not wrap in code fences. Do not include any explanation - just the Mermaid syntax."""

        diagram_syntax = await self.bedrock.invoke_lite_thinking(
            prompt=prompt,
            system_prompt=self.system_prompt,
            max_tokens=2048,
            reasoning_effort="medium",
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
