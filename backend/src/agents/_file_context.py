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
            if analysis.get("architecture_style"):
                parts.append(f"Architecture style: {analysis['architecture_style']}")
            for key in ("components", "patterns", "technologies", "external_services", "infrastructure"):
                items = analysis.get(key, [])
                if items and isinstance(items, list):
                    parts.append(f"{key.replace('_', ' ').title()}: {', '.join(str(i) for i in items)}")
            # Format data_flows as structured relationships for diagram generation
            data_flows = analysis.get("data_flows", [])
            if data_flows and isinstance(data_flows, list):
                flow_lines = []
                for flow in data_flows:
                    if isinstance(flow, dict):
                        src = flow.get("source", "?")
                        tgt = flow.get("target", "?")
                        proto = flow.get("protocol", "")
                        desc = flow.get("description", "")
                        label = f" ({proto})" if proto else ""
                        flow_lines.append(f"  {src} → {tgt}{label}: {desc}" if desc else f"  {src} → {tgt}{label}")
                    else:
                        flow_lines.append(f"  {flow}")
                if flow_lines:
                    parts.append("Data flows:\n" + "\n".join(flow_lines))
            if analysis.get("repo_structure_summary"):
                parts.append(f"Structure: {analysis['repo_structure_summary']}")
            reqs = analysis.get("requirements")
            if isinstance(reqs, dict):
                for rtype in ("functional", "non_functional"):
                    r_list = reqs.get(rtype, [])
                    if r_list and isinstance(r_list, list):
                        parts.append(f"{rtype.replace('_', ' ').title()} requirements: {', '.join(str(r) for r in r_list)}")
            elif isinstance(reqs, list) and reqs:
                parts.append(f"Requirements: {', '.join(str(r) for r in reqs)}")
            constraints = analysis.get("constraints", [])
            if constraints and isinstance(constraints, list):
                parts.append(f"Constraints: {', '.join(str(c) for c in constraints)}")
        else:
            parts.append(str(analysis)[:2000])

        block = "\n".join(parts)
        if total + len(block) > max_chars:
            break
        lines.append(block)
        total += len(block)

    return "\n".join(lines) if len(lines) > 1 else ""
