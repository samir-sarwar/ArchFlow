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
        self, request: str, current_diagram: str | None = None
    ) -> dict:
        """
        Generate or update a Mermaid diagram.

        Returns:
            {"diagram": str, "summary": str} on success
            {"error": str} on failure
        """
        existing = current_diagram or "No existing diagram - create a new one."

        prompt = (
            f"Based on this architecture request, generate a Mermaid.js diagram.\n\n"
            f"Request:\n{request}\n\n"
            f"Existing diagram to update (if any):\n{existing}\n\n"
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
