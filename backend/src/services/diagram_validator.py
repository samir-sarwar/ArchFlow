from src.models.diagram import DiagramState, DiagramType
from src.utils import logger


def validate_mermaid_syntax(syntax: str) -> DiagramState:
    """
    Validate Mermaid.js syntax and return diagram state.

    Args:
        syntax: Raw Mermaid.js syntax string

    Returns:
        DiagramState with validation results
    """
    logger.info("Validating Mermaid syntax", extra={"syntax_length": len(syntax)})
    # TODO: Implement Mermaid syntax validation
    raise NotImplementedError


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
