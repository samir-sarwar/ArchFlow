from src.models import AgentResponse, ConversationContext
from src.services.bedrock_client import BedrockClient
from src.services.diagram_validator import validate_mermaid_syntax
from src.utils import logger

DIAGRAM_GENERATOR_PROMPT = """
You are a Diagram Generator specializing in creating clean, readable Mermaid.js \
diagrams from architecture conversations.

Your role:
- Convert architecture discussions into valid Mermaid.js syntax
- Support: flowcharts, sequence diagrams, ER diagrams, C4 diagrams
- Make incremental updates (only modify changed portions)
- Prioritise READABILITY above completeness — a clean overview beats a cluttered map

Output rules:
- Always output valid Mermaid.js syntax
- Use descriptive node IDs (e.g., `api_gateway` not `A`)
- HARD LIMIT: maximum 15-20 nodes total. If the architecture has more components, \
group minor ones into a single representative node (e.g., `internal_services["Internal Services"]`). \
Quality over completeness.
- Keep the diagram to what a reader can absorb in 10 seconds

Layout rules (apply to all diagram types where applicable):
- Default to `flowchart TD` (top-down) with the entry point (API Gateway, Client, User) at the top
- Group related nodes into subgraphs to contain connections and reduce line crossings:
  - Databases and storage in a "Data Stores" subgraph at the bottom
  - Core services in their own logical subgraph(s)
- Use dotted arrows `-.->` for background/non-critical-path connections
- Arrange nodes in logical tiers (entry → services → data) to create a clean hierarchical layout

CRITICAL — Edge discipline (NON-NEGOTIABLE — violating these produces unreadable diagrams):

RULE 1 — No duplicate edge labels.
  If the same label (e.g. "logs", "metrics", "traces") would appear on more than \
one edge, you MUST consolidate. There must be AT MOST ONE edge per label per \
destination node in the entire diagram.

RULE 2 — Cross-cutting concerns belong at subgraph level, not per-service.
  Logging, tracing, metrics, audit, and monitoring connections MUST originate \
from a subgraph boundary or a single hub node, never from each individual service.

  FORBIDDEN (creates N crossing lines — never do this):
    service_a -.->|logs| logger
    service_b -.->|logs| logger
    service_c -.->|logs| logger

  REQUIRED (pick exactly one):
    Pattern A — subgraph-level link (preferred):
      core_services -.->|logs| logger

    Pattern B — invisible hub (when services are NOT in a shared subgraph):
      service_a -.-> obs_hub[" "]
      service_b -.-> obs_hub
      obs_hub -.->|logs, metrics, traces| observability

RULE 3 — Omit cross-cutting concerns unless explicitly requested.
  If the user did NOT ask for logging, tracing, monitoring, or metrics, do NOT \
include them. Silence is better than clutter. Only draw what was asked for.

RULE 4 — Edge labels only when the relationship is ambiguous.
  Do NOT label an edge when the connection type is obvious from node names \
(e.g., `api_gateway --> auth_service` needs no "authenticates" label). \
Use labels sparingly — when in doubt, omit.

RULE 5 — Maximum 2 edges between any pair of nodes.
  If you need 3+ edges between the same two nodes, merge into one labeled edge.

What to OMIT from diagrams (unless the user specifically requests it):
- Logging infrastructure (CloudWatch, Splunk, ELK, etc.)
- Distributed tracing (X-Ray, Jaeger, Zipkin, etc.)
- Metrics/monitoring sidecars (Prometheus, Datadog, etc.)
- DNS resolution and CDN routing details
- TLS termination steps
- Health check endpoints
- Internal retry/circuit-breaker mechanics
These are implementation details. Show the logical architecture, not the ops plumbing.

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
- Include key components and data flows from the file analysis, but still respect the 15-20 node limit — \
group minor components rather than expanding every leaf.
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
7. While making the requested change, if you encounter existing edges that violate \
the consolidation rules (same label repeated on N edges to the same destination), \
consolidate them as part of the update. Do not propagate bad patterns.

Output ONLY valid Mermaid.js syntax. Do not wrap in code fences. Do not include any explanation."""
        else:
            prompt = f"""Based on this architecture conversation, generate a new Mermaid.js diagram.

Conversation:
{conversation}

Constraints (enforce strictly before writing a single line of Mermaid syntax):
1. Maximum 15-20 nodes. Merge minor components; prefer a readable overview to an exhaustive map.
2. Cross-cutting concerns (logging, metrics, tracing) — omit entirely unless the conversation explicitly requests them.
3. No duplicate edge labels. Each label may appear at most once per destination node.
4. Edge labels only when the relationship is not obvious from node names alone.

Output ONLY valid Mermaid.js syntax. Do not wrap in code fences. Do not include any explanation."""

        system_prompt = self.system_prompt
        if file_context:
            system_prompt = self.system_prompt + "\n\n" + file_context

        # "high" reasoning effort: more deterministic, enforces structural rules better.
        # Disables temperature/topP (handled in bedrock_client.invoke_lite_thinking).
        # max_tokens=4096 to accommodate the larger thinking budget.
        diagram_syntax = await self.bedrock.invoke_lite_thinking(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=4096,
            reasoning_effort="high",
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
