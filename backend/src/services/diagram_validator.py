import re
from src.models.diagram import DiagramState, DiagramType
from src.utils import logger

# Maps first-line regex patterns to DiagramType values (checked case-insensitively)
_VALID_TYPE_PATTERNS: list[tuple[str, DiagramType]] = [
    (r"^flowchart\s+(TD|TB|BT|RL|LR)", DiagramType.FLOWCHART),
    (r"^graph\s+(TD|TB|BT|RL|LR)", DiagramType.FLOWCHART),
    (r"^sequenceDiagram", DiagramType.SEQUENCE),
    (r"^erDiagram", DiagramType.ER),
    (r"^C4Context", DiagramType.C4_CONTEXT),
    (r"^C4Container", DiagramType.C4_CONTAINER),
    (r"^C4Component", DiagramType.C4_COMPONENT),
    # Lenient catch-all for other standard Mermaid diagram starters
    (r"^(stateDiagram|classDiagram|gantt|pie|mindmap|gitGraph|xychart)", DiagramType.FLOWCHART),
]

# Mermaid keywords that are not node IDs
_MERMAID_KEYWORDS = frozenset({
    "subgraph", "end", "graph", "flowchart", "style", "classdef", "class",
    "direction", "participant", "actor", "note", "loop", "alt", "else",
    "opt", "sequencediagram", "erdiagram", "c4context", "c4container",
    "c4component", "statesdiagram", "classdiagram", "gantt", "pie",
    "mindmap", "gitgraph", "xychart", "td", "tb", "bt", "rl", "lr",
})

_NODE_DEF_RE = re.compile(r"\b(\w+)\s*[\[\({<]")
_ARROW_SOURCE_RE = re.compile(r"\b(\w+)\s*(?:-->|---|\.->|===>|--o|--x|==>|-\.-)")


def validate_mermaid_syntax(syntax: str) -> DiagramState:
    """
    Validate Mermaid.js syntax and return diagram state.

    Args:
        syntax: Raw Mermaid.js syntax string

    Returns:
        DiagramState with validation results
    """
    logger.info("Validating Mermaid syntax", extra={"syntax_length": len(syntax)})

    if not syntax or not syntax.strip():
        return DiagramState(
            syntax=syntax or "",
            is_valid=False,
            error_message="Empty diagram syntax",
        )

    lines = syntax.strip().splitlines()
    first_line = lines[0].strip()

    # 1. Validate type declaration on the first line
    diagram_type: DiagramType | None = None
    for pattern, dtype in _VALID_TYPE_PATTERNS:
        if re.match(pattern, first_line, re.IGNORECASE):
            diagram_type = dtype
            break

    if diagram_type is None:
        return DiagramState(
            syntax=syntax,
            is_valid=False,
            error_message=f"Invalid or missing diagram type declaration: '{first_line}'",
        )

    # 2. Balanced bracket check across body lines
    open_to_close = {"[": "]", "(": ")", "{": "}"}
    close_to_open = {v: k for k, v in open_to_close.items()}
    stack: list[str] = []

    for line in lines[1:]:
        stripped = line.strip()
        if stripped.startswith("%%"):
            continue  # skip comments

        in_quote = False
        for ch in line:
            if ch == '"':
                in_quote = not in_quote
            if in_quote:
                continue
            if ch in open_to_close:
                stack.append(ch)
            elif ch in close_to_open:
                expected_open = close_to_open[ch]
                if stack and stack[-1] == expected_open:
                    stack.pop()
                # If mismatched or empty stack, skip — Mermaid is lenient in label text

    if stack:
        return DiagramState(
            syntax=syntax,
            diagram_type=diagram_type,
            is_valid=False,
            error_message=f"Unbalanced brackets in diagram body: unclosed {stack}",
        )

    # 3. Count unique node IDs from body lines
    node_ids: set[str] = set()
    for line in lines[1:]:
        stripped = line.strip()
        if stripped.startswith("%%"):
            continue
        for match in _NODE_DEF_RE.finditer(line):
            candidate = match.group(1).lower()
            if candidate not in _MERMAID_KEYWORDS:
                node_ids.add(candidate)
        for match in _ARROW_SOURCE_RE.finditer(line):
            candidate = match.group(1).lower()
            if candidate not in _MERMAID_KEYWORDS:
                node_ids.add(candidate)

    return DiagramState(
        syntax=syntax,
        diagram_type=diagram_type,
        is_valid=True,
        node_count=len(node_ids),
    )


def detect_diagram_type(syntax: str) -> DiagramType:
    """Detect the type of Mermaid diagram from syntax."""
    syntax_lower = syntax.strip().lower()

    if syntax_lower.startswith(("graph", "flowchart")):
        return DiagramType.FLOWCHART
    elif syntax_lower.startswith("sequencediagram"):
        return DiagramType.SEQUENCE
    elif syntax_lower.startswith("erdiagram"):
        return DiagramType.ER
    elif "c4context" in syntax_lower:
        return DiagramType.C4_CONTEXT
    elif "c4container" in syntax_lower:
        return DiagramType.C4_CONTAINER

    return DiagramType.FLOWCHART
