"""Lightweight GitHub repository context for AI prompts.

Fetches just the file tree structure and README.md content via the GitHub API.
This provides enough context for AI to understand architecture without
overwhelming it with full source code.
"""

import base64
import json
import os
import re
import urllib.error
import urllib.request

from src.utils import logger

_GITHUB_URL_RE = re.compile(
    r"https?://(?:www\.)?github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)",
    re.IGNORECASE,
)

_REQUEST_TIMEOUT = 30


def parse_github_url(url: str) -> dict | None:
    """Extract owner and repo from a GitHub URL. Returns None if invalid."""
    url = url.rstrip("/").removesuffix(".git")
    match = _GITHUB_URL_RE.search(url)
    if not match:
        return None
    return {"owner": match.group("owner"), "repo": match.group("repo")}


def _github_api_get(path: str) -> dict:
    """GET from GitHub API, returns parsed JSON."""
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    url = f"https://api.github.com{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ArchFlow/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fetch_tree(owner: str, repo: str, branch: str) -> list[dict]:
    """Fetch the full recursive file tree from GitHub API."""
    data = _github_api_get(f"/repos/{owner}/{repo}/git/trees/{branch}?recursive=1")
    return data.get("tree", [])


def _fetch_readme(owner: str, repo: str) -> str:
    """Fetch README content from GitHub API. Returns empty string if not found."""
    try:
        data = _github_api_get(f"/repos/{owner}/{repo}/readme")
        content_b64 = data.get("content", "")
        return base64.b64decode(content_b64).decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return ""
        raise


def _format_tree(tree_items: list[dict]) -> str:
    """Render a clean indented directory tree from GitHub tree API items."""
    # Build a nested dict structure
    root: dict = {}
    for item in tree_items:
        path = item["path"]
        parts = path.split("/")
        node = root
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        if item["type"] == "tree":
            node.setdefault(parts[-1], {})
        else:
            node[parts[-1]] = None  # leaf file

    # Render tree recursively
    lines: list[str] = []

    def _render(node: dict, indent: int = 0):
        prefix = "  " * indent
        # Sort: directories first, then files
        dirs = sorted(k for k, v in node.items() if v is not None)
        files = sorted(k for k, v in node.items() if v is None)
        for d in dirs:
            lines.append(f"{prefix}{d}/")
            _render(node[d], indent + 1)
        for f in files:
            lines.append(f"{prefix}{f}")

    _render(root)
    return "\n".join(lines)


def fetch_repo_context(github_url: str) -> dict:
    """Fetch lightweight repo context: file tree + README.

    Returns dict with keys:
        context_output: str — formatted markdown with tree + README
        char_count: int — length of the output
    Raises RuntimeError on failure.
    """
    parsed = parse_github_url(github_url)
    if not parsed:
        raise RuntimeError(f"Invalid GitHub URL: {github_url}")

    owner, repo = parsed["owner"], parsed["repo"]

    # Resolve default branch
    try:
        meta = _github_api_get(f"/repos/{owner}/{repo}")
        branch = meta.get("default_branch", "main")
        description = meta.get("description", "")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"GitHub API error {e.code} for {owner}/{repo}") from e

    logger.info("Fetching repo context", extra={"repo": f"{owner}/{repo}", "branch": branch})

    tree_items = _fetch_tree(owner, repo, branch)
    readme_content = _fetch_readme(owner, repo)
    tree_str = _format_tree(tree_items)

    # Build the context markdown
    sections = [f"# Repository: {owner}/{repo}"]
    if description:
        sections.append(f"\n{description}")
    sections.append(f"\n## File Structure\n```\n{tree_str}\n```")
    if readme_content:
        sections.append(f"\n## README.md\n{readme_content}")
    else:
        sections.append("\n## README.md\nNo README found.")

    content = "\n".join(sections)

    logger.info(
        "Repo context fetched",
        extra={"chars": len(content), "files": len([i for i in tree_items if i["type"] == "blob"])},
    )
    return {"context_output": content, "char_count": len(content)}
