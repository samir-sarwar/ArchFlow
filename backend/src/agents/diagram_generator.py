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
- Default to `flowchart TD` (top-down) with the entry point (API Gateway, Client, User) at the top
- Group related nodes into subgraphs to contain connections and reduce line crossings:
  - Databases and storage in a "Data Stores" subgraph at the bottom
  - Security, logging, tracing, and monitoring in a "Security & Monitoring" subgraph
  - Core services in their own logical subgraph(s)
- Use dotted arrows `-.->` for background/non-critical-path connections (logging, tracing, metrics, monitoring) to visually separate them from the main request flow (`-->`)
- Arrange nodes in logical tiers (entry → services → data) to create a clean hierarchical layout and minimise line crossings

CRITICAL — Edge consolidation (MUST follow, violations create unreadable diagrams):
- NEVER draw N separate edges from N source nodes to the same destination. This creates a tangled mess.
- Instead, create an invisible collector node or link from the subgraph boundary:

  BAD (creates 5 crossing lines):
    service_a -.->|logs| logger
    service_b -.->|logs| logger
    service_c -.->|logs| logger

  GOOD (single clean connection):
    core_services -.->|logs| logger

  ALSO GOOD (hub node):
    service_a -.-> log_hub["  "]
    service_b -.-> log_hub
    service_c -.-> log_hub
    log_hub -.->|logs| logger

- Apply this to ALL shared destinations: loggers, monitors, tracers, shared databases, auth services, etc.
- Maximum edges between any two subgraphs should be 1-2 lines, not one per source node.

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

Uploaded file context:
- When the prompt includes an "Uploaded file analysis" section, use it as the primary source for diagram content.
- Map the file's components, data flows, and technologies into diagram nodes and connections.
- Use the file's patterns (e.g., "microservices", "event-driven") to choose the appropriate diagram layout.
- Include all components and data flows from the file analysis unless the user explicitly asks for a subset.
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

        from src.agents._file_context import build_file_context_block
        file_context = build_file_context_block(context.uploaded_files)

        if context.current_diagram:
            latest_user_msg = next(
                (m.content for m in reversed(recent_messages) if m.role == "user"), ""
            )
            prompt = f"""You are MODIFYING an existing architecture diagram. Do NOT create a new diagram from scratch.

TASK: Apply ONLY the change described in the change request below.

EXISTING DIAGRAM (this is the base — preserve everything not mentioned in the change request):
{context.current_diagram}

Conversation context:
{conversation}

CHANGE REQUEST: {latest_user_msg}

RULES — CRITICAL:
1. Start from the EXISTING DIAGRAM above as your base. Copy it exactly.
2. Apply ONLY the specific change(s) mentioned in the change request.
3. Preserve ALL existing nodes, subgraphs, connections, and labels not directly affected by the change.
4. Do NOT reorganise, rename, or remove nodes that the user did not mention.
5. If adding a new node, choose a node ID consistent with the existing naming convention.
6. Exception: if the user explicitly says "start over", "redesign", "create a new diagram", or "from scratch", ignore rules 1-5 and generate a completely new diagram.

Output ONLY valid Mermaid.js syntax. Do not wrap in code fences. Do not include any explanation."""
        else:
            prompt = f"""Based on this architecture conversation, generate a new Mermaid.js diagram.

Conversation:
{conversation}

Output ONLY valid Mermaid.js syntax. Do not wrap in code fences. Do not include any explanation."""

        system_prompt = self.system_prompt
        if file_context:
            system_prompt = self.system_prompt + "\n\n" + file_context

        diagram_syntax = await self.bedrock.invoke_lite_thinking(
            prompt=prompt,
            system_prompt=system_prompt,
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
