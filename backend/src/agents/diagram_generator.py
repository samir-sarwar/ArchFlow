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
- Scale node count to the complexity of the architecture described. \
For simple systems (3-5 services), 8-12 nodes is right. \
For moderate systems, 15-30 nodes is appropriate. \
For complex multi-tier systems, 30-50+ nodes may be appropriate. \
Group minor ancillary components rather than omitting them, \
but never add nodes that the conversation did not mention.
- Prioritise completeness — include all components the user described rather than \
collapsing them for brevity

Diagram type — match the diagram structure to the user's intent:

USER JOURNEY / USER FLOW / PROCESS diagrams (when the user says "user journey", "user flow", \
"user experience", "process flow", "workflow", or describes steps a person takes):
- Use `flowchart TD` or `flowchart LR` — NEVER use `stateDiagram` for user flows
- Nodes represent: user actions, screens/pages, decision points, outcomes
- Do NOT add infrastructure nodes (databases, API gateways, load balancers, queues, caches)
- Use diamond shapes `{Decision?}` for user decisions, rounded `(Action)` for user actions
- Subgraphs represent phases or stages of the journey (e.g., "Onboarding", "Checkout"), not service tiers
- Edge labels describe user intent ("clicks buy", "submits form", "confirms"), not protocols or HTTP methods

Example skeleton (adapt to actual content):
  flowchart TD
      start(["User opens app"])
      login["Login screen"]
      decide{"Valid credentials?"}
      dashboard["Dashboard"]
      error["Show error"]
      start --> login
      login --> decide
      decide -->|yes| dashboard
      decide -->|no| error
      error -->|retry| login

SEQUENCE diagrams:
- Focus on actor-to-actor interactions and request/response flows
- Participants are actors, services, or systems — not internal classes or functions
- Use `activate`/`deactivate` for long-running interactions
- Use `alt`/`opt`/`loop` fragments for conditional or repeated flows

Example skeleton (adapt to actual content):
  sequenceDiagram
      participant user as User
      participant api as API Gateway
      participant auth as Auth Service
      user->>api: POST /login
      activate api
      api->>auth: Validate credentials
      activate auth
      alt valid
          auth-->>api: 200 OK + token
      else invalid
          auth-->>api: 401 Unauthorized
      end
      deactivate auth
      api-->>user: Response
      deactivate api

ER diagrams:
- Focus on entities (tables/collections), their attributes, and relationships
- Use proper cardinality notation: `||--o{`, `}o--||`, etc.
- Do NOT add service or infrastructure nodes — only data entities

Example skeleton (adapt to actual content):
  erDiagram
      USER ||--o{ ORDER : places
      ORDER ||--|{ ORDER_ITEM : contains
      PRODUCT ||--o{ ORDER_ITEM : "included in"
      USER {
          string id PK
          string email
          string name
      }
      ORDER {
          string id PK
          string user_id FK
          datetime created_at
      }

C4 diagrams:
- Follow C4 model conventions for the chosen level (Context, Container, Component)

Example skeleton (adapt to actual content):
  C4Context
      title System Context Diagram
      Person(user, "User", "End user of the system")
      System(app, "Application", "Main application")
      System_Ext(email, "Email Service", "Sends notifications")
      Rel(user, app, "Uses")
      Rel(app, email, "Sends emails via")

ARCHITECTURE / INFRASTRUCTURE diagrams (default when discussing services, APIs, cloud, backends):
- Default to `flowchart TD` (top-down) with the entry point at the top
- Group related nodes into subgraphs to contain connections and reduce line crossings:
  - Databases and storage in a "Data Stores" subgraph at the bottom
  - Core services in their own logical subgraph(s)
- Use dotted arrows `-.->` for background/non-critical-path connections
- Arrange nodes in logical tiers (entry → services → data) to create a clean hierarchical layout

Example skeleton (adapt to actual content):
  flowchart TD
      client["Client App"]
      subgraph api_layer["API Layer"]
          gateway["API Gateway"]
          auth["Auth Service"]
      end
      subgraph services["Core Services"]
          svc_a["Service A"]
          svc_b["Service B"]
      end
      subgraph data["Data Stores"]
          db[("PostgreSQL")]
          cache[("Redis")]
      end
      client --> gateway
      gateway --> auth
      gateway --> svc_a
      gateway --> svc_b
      svc_a --> db
      svc_b --> db
      svc_a -.-> cache

Detail level — respond to depth cues in the user's request:
- When the user says "add more detail", "go deeper", "expand", "break down", or "less abstract":
  - Identify nodes that represent high-level abstractions (e.g., "Backend", "Auth Service")
  - Replace them with subgraphs containing their internal components
  - Add intermediate steps between existing nodes (e.g., validation, caching, transformation)
  - Increase node count by roughly 75-150% relative to the current diagram
  - Preserve the overall structure — deepening adds WITHIN existing groups, not beside them
- When the user says "simplify", "high level", "overview", "zoom out", or "more abstract":
  - Collapse subgraphs into single representative nodes
  - Remove intermediate steps, keep only primary flows
  - Reduce node count by roughly 30-50%
  - Merge closely related nodes into one
- When modifying an existing diagram with depth changes, adjust its granularity — do not regenerate from scratch.

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
- Include key components and data flows from the file analysis — \
group ancillary or repeated leaf components rather than expanding every one individually.
"""


_SUBTYPE_DIRECTIVES = {
    "USER_FLOW": (
        "DIAGRAM TYPE REQUIRED: This is a USER FLOW / USER JOURNEY diagram.\n"
        "You MUST start with `flowchart TD` or `flowchart LR`.\n"
        "Do NOT use stateDiagram, sequenceDiagram, or any other type.\n\n"
    ),
    "SEQUENCE": (
        "DIAGRAM TYPE REQUIRED: This is a SEQUENCE diagram.\n"
        "You MUST start with `sequenceDiagram`.\n\n"
    ),
    "ER": (
        "DIAGRAM TYPE REQUIRED: This is an ER diagram.\n"
        "You MUST start with `erDiagram`.\n\n"
    ),
    "C4": (
        "DIAGRAM TYPE REQUIRED: This is a C4 diagram.\n"
        "You MUST start with `C4Context`, `C4Container`, or `C4Component`.\n\n"
    ),
}


def _build_type_directive(subtype: str) -> str:
    """Return an explicit type directive for the given diagram subtype, or empty string for ARCHITECTURE."""
    return _SUBTYPE_DIRECTIVES.get(subtype, "")


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

        subtype = context.metadata.get("diagram_subtype", "ARCHITECTURE")
        type_directive = _build_type_directive(subtype)

        if context.current_diagram:
            latest_user_msg = next(
                (m.content for m in reversed(recent_messages) if m.role == "user"), ""
            )
            prompt = f"""{type_directive}You are MODIFYING an existing architecture diagram. Do NOT create a new diagram from scratch.

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
8. Depth changes: if the change request asks for more or less detail, adjust the \
granularity of the existing diagram (expand abstractions into subgraphs with internal \
components, or collapse subgraphs into single nodes) rather than adding unrelated nodes.

Output ONLY valid Mermaid.js syntax. Do not wrap in code fences. Do not include any explanation."""
        else:
            file_context_hint = ""
            if file_context:
                file_context_hint = """
IMPORTANT — Uploaded file analysis is available in the system prompt. It is the PRIMARY source for this diagram.
- Use the specific component names, technologies, and service names from the analysis as node labels.
- Map each data_flow entry (source → target) directly to a diagram edge.
- Use the architecture_style to choose the best diagram layout.
- Include external_services as distinct nodes connected to the components that use them.
- Do NOT fall back to generic names (e.g., "Database", "API Gateway") when the analysis provides specific ones (e.g., "MongoDB Atlas", "Next.js App Router").
"""
            prompt = f"""{type_directive}Based on this architecture conversation, generate a new Mermaid.js diagram.

Conversation:
{conversation}
{file_context_hint}
Constraints (enforce strictly before writing a single line of Mermaid syntax):
1. Scale node count to the architecture's complexity — group minor ancillary components \
rather than listing every leaf, but do not invent nodes that were not discussed.
2. Cross-cutting concerns (logging, metrics, tracing) — omit entirely unless the conversation explicitly requests them.
3. No duplicate edge labels. Each label may appear at most once per destination node.
4. Edge labels only when the relationship is not obvious from node names alone.

Output ONLY valid Mermaid.js syntax. Do not wrap in code fences. Do not include any explanation."""

        system_prompt = self.system_prompt
        if file_context:
            system_prompt = self.system_prompt + "\n\n" + file_context

        # "medium" reasoning with a large token budget: best trade-off for diagram quality
        # within the hard 29s API Gateway WebSocket integration timeout.
        # ("high" reasoning disallows maxTokens and exceeds the 29s limit.)
        diagram_syntax = await self.bedrock.invoke_lite_thinking(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=8192,
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
                f"{type_directive}"
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
