"""Shared helper to format uploaded file analyses into prompt context."""


def build_file_context_block(uploaded_files: list[dict], max_chars: int = 10000) -> str:
    """Format uploaded file analyses into a prompt block for downstream agents.

    Returns an empty string when no analyzed files exist, so callers can
    safely inject the result into prompts without conditional logic.
    """
    analyzed = [f for f in uploaded_files if f.get("file_analysis")]
    if not analyzed:
        return ""

    lines = ["Uploaded file analysis (use this context when relevant):"]
    total = 0

    for f in analyzed:
        analysis = f["file_analysis"]
        file_name = f.get("file_name", "unknown")
        parts = [f"\n--- {file_name} ---"]

        if isinstance(analysis, dict):
            if analysis.get("summary"):
                parts.append(f"Summary: {analysis['summary']}")
            for key in ("components", "patterns", "technologies", "data_flows"):
                items = analysis.get(key, [])
                if items and isinstance(items, list):
                    parts.append(f"{key.replace('_', ' ').title()}: {', '.join(str(i) for i in items[:15])}")
            reqs = analysis.get("requirements")
            if isinstance(reqs, dict):
                for rtype in ("functional", "non_functional"):
                    r_list = reqs.get(rtype, [])
                    if r_list and isinstance(r_list, list):
                        parts.append(f"{rtype.replace('_', ' ').title()} requirements: {', '.join(str(r) for r in r_list[:8])}")
            elif isinstance(reqs, list) and reqs:
                parts.append(f"Requirements: {', '.join(str(r) for r in reqs[:8])}")
            constraints = analysis.get("constraints", [])
            if constraints and isinstance(constraints, list):
                parts.append(f"Constraints: {', '.join(str(c) for c in constraints[:8])}")
        else:
            parts.append(str(analysis)[:500])

        block = "\n".join(parts)
        if total + len(block) > max_chars:
            break
        lines.append(block)
        total += len(block)

    return "\n".join(lines) if len(lines) > 1 else ""
