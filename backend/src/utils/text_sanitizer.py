"""Post-processing utility to strip markdown formatting from agent responses."""

import re


def strip_markdown(text: str) -> str:
    """Remove markdown formatting syntax while preserving readable structure.

    Strips headings (#), bold/italic (** / *), and backtick code markers.
    Preserves list markers (- and 1.) and whitespace/newline structure.
    """
    if not text:
        return text

    # Remove code fences (``` ... ```) but keep content
    result = re.sub(r"```\w*\n?", "", text)

    # Remove inline backticks but keep content
    result = re.sub(r"`([^`]+)`", r"\1", result)

    # Remove heading markers (# at start of line)
    result = re.sub(r"^#{1,6}\s+", "", result, flags=re.MULTILINE)

    # Remove bold/italic markers (** and *)
    # Bold first (greedy), then italic
    result = re.sub(r"\*\*(.+?)\*\*", r"\1", result)
    result = re.sub(r"\*(.+?)\*", r"\1", result)
    result = re.sub(r"__(.+?)__", r"\1", result)
    result = re.sub(r"_(.+?)_", r"\1", result)

    # Remove horizontal rules (---, ***, ___)
    result = re.sub(r"^[-*_]{3,}\s*$", "", result, flags=re.MULTILINE)

    # Collapse 3+ consecutive blank lines into 2
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result.strip()
