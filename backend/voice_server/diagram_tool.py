"""
Diagram generation tool for the ArchFlow voice server.

Generates Mermaid.js diagrams via Bedrock Converse API (Nova Lite).
Self-contained — does not import from the Lambda backend (src/).
"""

import asyncio
import json
import logging
import os
import re
from functools import partial

import boto3

logger = logging.getLogger(__name__)

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

Diagram type — match the diagram structure to the user's intent:

USER JOURNEY / USER FLOW / PROCESS diagrams (when the user says "user journey", "user flow", \
"user experience", "process flow", "workflow", or describes steps a person takes):
- Use `flowchart TD` or `flowchart LR`
- Nodes represent: user actions, screens/pages, decision points, outcomes
- Do NOT add infrastructure nodes (databases, API gateways, load balancers, queues, caches)
- Use diamond shapes `{Decision?}` for user decisions, rounded `(Action)` for user actions
- Subgraphs represent phases or stages of the journey (e.g., "Onboarding", "Checkout"), not service tiers
- Edge labels describe user intent ("clicks buy", "submits form", "confirms"), not protocols or HTTP methods

SEQUENCE diagrams:
- Focus on actor-to-actor interactions and request/response flows
- Participants are actors, services, or systems — not internal classes or functions
- Use `activate`/`deactivate` for long-running interactions
- Use `alt`/`opt`/`loop` fragments for conditional or repeated flows

ER diagrams:
- Focus on entities (tables/collections), their attributes, and relationships
- Use proper cardinality notation: `||--o{`, `}o--||`, etc.
- Do NOT add service or infrastructure nodes — only data entities

C4 diagrams:
- Follow C4 model conventions for the chosen level (Context, Container, Component)

ARCHITECTURE / INFRASTRUCTURE diagrams (default when discussing services, APIs, cloud, backends):
- Default to `flowchart TD` (top-down) with the entry point at the top
- Group related nodes into subgraphs to contain connections and reduce line crossings:
  - Databases and storage in a "Data Stores" subgraph at the bottom
  - Core services in their own logical subgraph(s)
- Use dotted arrows `-.->` for background/non-critical-path connections
- Arrange nodes in logical tiers (entry → services → data) to create a clean hierarchical layout

Detail level — respond to depth cues in the user's request:
- When the user says "add more detail", "go deeper", "expand", "break down", or "less abstract":
  - Identify nodes that represent high-level abstractions (e.g., "Backend", "Auth Service")
  - Replace them with subgraphs containing their internal components
  - Add intermediate steps between existing nodes (e.g., validation, caching, transformation)
  - Increase node count by roughly 50-100% relative to the current diagram
  - Preserve the overall structure — deepening adds WITHIN existing groups, not beside them
- When the user says "simplify", "high level", "overview", "zoom out", or "more abstract":
  - Collapse subgraphs into single representative nodes
  - Remove intermediate steps, keep only primary flows
  - Reduce node count by roughly 30-50%
  - Merge closely related nodes into one
- When modifying an existing diagram with depth changes, adjust its granularity — do not regenerate from scratch.

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
"""

# ── Mermaid validation (inline, adapted from src/services/diagram_validator.py) ──

_VALID_TYPE_PATTERNS = [
    (r"^flowchart\s+(TD|TB|BT|RL|LR)", "flowchart"),
    (r"^graph\s+(TD|TB|BT|RL|LR)", "flowchart"),
    (r"^sequenceDiagram", "sequence"),
    (r"^erDiagram", "er"),
    (r"^C4Context", "c4_context"),
    (r"^C4Container", "c4_container"),
    (r"^C4Component", "c4_component"),
    (r"^(stateDiagram|classDiagram|gantt|pie|mindmap|gitGraph|xychart)", "other"),
]


def _validate_mermaid(syntax: str) -> tuple[bool, str | None]:
    """Validate Mermaid syntax. Returns (is_valid, error_message)."""
    if not syntax or not syntax.strip():
        return False, "Empty diagram syntax"

    lines = syntax.strip().splitlines()
    first_line = lines[0].strip()

    # Check diagram type
    matched = False
    for pattern, _ in _VALID_TYPE_PATTERNS:
        if re.match(pattern, first_line, re.IGNORECASE):
            matched = True
            break
    if not matched:
        return False, f"Invalid diagram type: '{first_line}'"

    # Check balanced brackets
    open_to_close = {"[": "]", "(": ")", "{": "}"}
    close_to_open = {v: k for k, v in open_to_close.items()}
    stack: list[str] = []
    for line in lines[1:]:
        if line.strip().startswith("%%"):
            continue
        in_quote = False
        for ch in line:
            if ch == '"':
                in_quote = not in_quote
            if in_quote:
                continue
            if ch in open_to_close:
                stack.append(ch)
            elif ch in close_to_open:
                expected = close_to_open[ch]
                if stack and stack[-1] == expected:
                    stack.pop()

    if stack:
        return False, f"Unbalanced brackets: unclosed {stack}"

    return True, None


def _clean_code_fences(text: str) -> str:
    """Strip markdown code fences from LLM output."""
    cleaned = text.strip()
    if cleaned.startswith("```mermaid"):
        cleaned = cleaned[len("```mermaid"):].strip()
    if cleaned.startswith("```"):
        cleaned = cleaned[3:].strip()
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()
    return cleaned


class DiagramTool:
    """Generates Mermaid diagrams using Bedrock Converse API."""

    def __init__(self, region: str = "us-east-1"):
        self.region = region
        self.model_id = os.environ.get(
            "BEDROCK_MODEL_LITE", "us.amazon.nova-2-lite-v1:0"
        )
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = boto3.client("bedrock-runtime", region_name=self.region)
        return self._client

    def _call_converse(self, prompt: str, system_prompt: str) -> str:
        """Synchronous Converse API call (runs in thread pool)."""
        kwargs = {
            "modelId": self.model_id,
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"maxTokens": 2048, "topP": 0.9, "temperature": 0.7},
        }
        if system_prompt:
            kwargs["system"] = [{"text": system_prompt}]

        response = self.client.converse(**kwargs)
        return response["output"]["message"]["content"][0]["text"]

    async def generate(
        self,
        request: str,
        current_diagram: str | None = None,
        conversation_history: str | None = None,
    ) -> dict:
        """
        Generate or update a Mermaid diagram.

        Returns:
            {"diagram": str, "summary": str} on success
            {"error": str} on failure
        """
        if current_diagram:
            history_section = (
                f"\nConversation context:\n{conversation_history}\n"
                if conversation_history
                else ""
            )
            prompt = (
                f"You are MODIFYING an existing architecture diagram. "
                f"Do NOT create a new diagram from scratch.\n\n"
                f"TASK: Apply ONLY the change described in the change request below.\n\n"
                f"EXISTING DIAGRAM (this is the base — preserve everything "
                f"not mentioned in the change request):\n{current_diagram}\n"
                f"{history_section}\n"
                f"CHANGE REQUEST: {request}\n\n"
                f"RULES — CRITICAL:\n"
                f"1. Start from the EXISTING DIAGRAM above as your base. Copy it exactly.\n"
                f"2. Apply ONLY the specific change(s) mentioned in the change request.\n"
                f"3. Preserve ALL existing nodes, subgraphs, connections, "
                f"and labels not directly affected by the change.\n"
                f"4. Do NOT reorganise, rename, or remove nodes the user did not mention.\n"
                f"5. If adding a new node, choose a node ID consistent with the existing naming convention.\n"
                f"6. Exception: if the user explicitly says 'start over', 'redesign', "
                f"'create a new diagram', or 'from scratch', ignore rules 1-5 and generate a new diagram.\n"
                f"7. Depth changes: if the change request asks for more or less detail, adjust the "
                f"granularity of the existing diagram (expand abstractions into subgraphs with internal "
                f"components, or collapse subgraphs into single nodes) rather than adding unrelated nodes.\n\n"
                f"Output ONLY valid Mermaid.js syntax. "
                f"Do not wrap in code fences. Do not include any explanation."
            )
        else:
            history_section = (
                f"Conversation context:\n{conversation_history}\n\n"
                if conversation_history
                else ""
            )
            prompt = (
                f"Based on this architecture request, generate a new Mermaid.js diagram.\n\n"
                f"{history_section}"
                f"Request:\n{request}\n\n"
                f"Output ONLY valid Mermaid.js syntax. "
                f"Do not wrap in code fences. Do not include any explanation."
            )

        loop = asyncio.get_event_loop()

        try:
            logger.info("Generating diagram via Converse API (model=%s)", self.model_id)
            raw = await loop.run_in_executor(
                None, partial(self._call_converse, prompt, DIAGRAM_GENERATOR_PROMPT)
            )
        except Exception as exc:
            logger.error("Converse API call failed: %s", exc)
            return {"error": f"Failed to generate diagram: {exc}"}

        cleaned = _clean_code_fences(raw)
        is_valid, error = _validate_mermaid(cleaned)

        # Retry once if invalid
        if not is_valid:
            logger.warning("Generated diagram invalid (%s), retrying", error)
            retry_prompt = (
                f"The Mermaid syntax you generated has this error: {error}. "
                f"Fix it and return ONLY valid Mermaid syntax — no explanation, no code fences.\n\n"
                f"Broken syntax:\n{cleaned}"
            )
            try:
                raw_retry = await loop.run_in_executor(
                    None,
                    partial(self._call_converse, retry_prompt, DIAGRAM_GENERATOR_PROMPT),
                )
                cleaned = _clean_code_fences(raw_retry)
                is_valid, error = _validate_mermaid(cleaned)
            except Exception as exc:
                logger.error("Diagram retry failed: %s", exc)
                return {"error": f"Diagram generation failed after retry: {exc}"}

        if not is_valid:
            return {"error": f"Could not generate valid diagram: {error}"}

        # Count nodes for summary
        node_count = len(
            {m.group(1).lower() for m in re.finditer(r"\b(\w+)\s*[\[\({<]", cleaned)}
        )

        summary = f"Generated a diagram with {node_count} components."
        logger.info("Diagram generated: %d chars, %d nodes", len(cleaned), node_count)

        return {"diagram": cleaned, "summary": summary}
