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
    # classDiagram is accepted as a reasonable approximation for component diagrams.
    # Other types (stateDiagram, gantt, pie, mindmap, etc.) are rejected to trigger
    # the retry path with correct type enforcement.
    (r"^classDiagram", DiagramType.FLOWCHART),
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

# Matches a node ID with hyphens (e.g., api-gateway, my-service-name) in
# node-definition or arrow-source positions — but NOT inside quoted strings.
_HYPHENATED_ID_RE = re.compile(r"\b([a-zA-Z]\w*(?:-\w+)+)\b")

# Matches flowchart labels like [Label (v2)] that contain special chars but aren't quoted
_UNQUOTED_LABEL_RE = re.compile(r'(\[)([^\]"]*[()&/][^\]"]*?)(\])')

# Matches -- text --> (invalid) to be replaced with -->|text|
_INVALID_LABEL_ARROW_RE = re.compile(r'--\s+([^-][^>]*?)\s+-->')

# Matches single-dash arrow -> (invalid in flowcharts), but not -.-> or -->
_SINGLE_ARROW_RE = re.compile(r'(?<![-.])\s*->\s*(?!>)')


def sanitize_mermaid_syntax(syntax: str) -> str:
    """Apply deterministic fixes to common AI-generated Mermaid syntax errors."""
    if not syntax or not syntax.strip():
        return syntax

    lines = syntax.strip().splitlines()
    first_line = lines[0].strip().lower()
    is_flowchart = first_line.startswith(("flowchart", "graph"))
    is_sequence = first_line.startswith("sequencediagram")

    result_lines: list[str] = []
    declared_participants: set[str] = set()
    used_participants: list[str] = []

    for i, line in enumerate(lines):
        # Skip comments
        if line.strip().startswith("%%"):
            result_lines.append(line)
            continue

        # Strip trailing semicolons
        if line.rstrip().endswith(";"):
            line = line.rstrip()[:-1]

        if is_flowchart or (not is_sequence and i > 0):
            # Replace hyphens in node IDs with underscores (skip quoted regions and arrows)
            # Process segments outside of quotes
            segments = []
            in_quote = False
            current = []
            for ch in line:
                if ch == '"':
                    if in_quote:
                        current.append(ch)
                        segments.append("".join(current))
                        current = []
                        in_quote = False
                    else:
                        segments.append("".join(current))
                        current = [ch]
                        in_quote = True
                else:
                    current.append(ch)
            if current:
                segments.append("".join(current))

            fixed_segments = []
            for seg in segments:
                if seg.startswith('"'):
                    fixed_segments.append(seg)  # preserve quoted text
                else:
                    # Replace hyphens in identifiers, but not in arrow syntax (--> -.-> etc.)
                    def _fix_id(m: re.Match) -> str:
                        ident = m.group(1)
                        # Don't touch arrow-like patterns
                        start = m.start(1)
                        if start > 0:
                            before = seg[max(0, start - 2):start]
                            if before.endswith("-") or before.endswith("."):
                                return m.group(0)
                        return m.group(0).replace(ident, ident.replace("-", "_"))

                    fixed_segments.append(_HYPHENATED_ID_RE.sub(_fix_id, seg))
            line = "".join(fixed_segments)

            # Wrap unquoted labels with special chars in double quotes
            line = _UNQUOTED_LABEL_RE.sub(lambda m: f'{m.group(1)}"{m.group(2)}"{m.group(3)}', line)

            # Fix -- text --> to -->|text|
            line = _INVALID_LABEL_ARROW_RE.sub(lambda m: f'-->|{m.group(1).strip()}|', line)

            # Fix single-dash arrow -> to -->
            if "->" in line and "-->" not in line and "->>" not in line:
                line = _SINGLE_ARROW_RE.sub(" --> ", line)

        # Track sequence diagram participants
        if is_sequence and i > 0:
            stripped = line.strip()
            if stripped.startswith("participant "):
                name = stripped.split()[1] if len(stripped.split()) > 1 else ""
                if name:
                    declared_participants.add(name.rstrip(":"))
            else:
                # Check for actor->>actor patterns
                msg_match = re.match(r'\s*(\w+)\s*->>[\s+\-]*(\w+)', stripped)
                if msg_match:
                    for p in (msg_match.group(1), msg_match.group(2)):
                        if p not in declared_participants and p not in used_participants:
                            used_participants.append(p)

        result_lines.append(line)

    # Auto-declare missing participants in sequence diagrams
    if is_sequence and used_participants:
        insert_pos = 1  # after "sequenceDiagram" line
        for p in used_participants:
            result_lines.insert(insert_pos, f"    participant {p}")
            insert_pos += 1

    return "\n".join(result_lines)


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
