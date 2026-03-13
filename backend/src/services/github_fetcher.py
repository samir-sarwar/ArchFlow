"""GitHub repository context fetcher.

Parses GitHub URLs and fetches repo metadata, directory structure,
and key files via the GitHub REST API. Returns assembled text for
AI analysis.
"""

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from src.utils import logger

# Files to prioritize fetching (order matters — most important first)
PRIORITY_FILES = [
    "README.md",
    "README.rst",
    "README",
    "package.json",
    "requirements.txt",
    "Pipfile",
    "pyproject.toml",
    "go.mod",
    "Cargo.toml",
    "pom.xml",
    "build.gradle",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "serverless.yml",
    "serverless.yaml",
    "template.yaml",
    "template.yml",
    "cdk.json",
    "tsconfig.json",
    "next.config.js",
    "next.config.ts",
    "vite.config.ts",
    "vite.config.js",
    "nuxt.config.ts",
    "angular.json",
    "architecture.md",
    "ARCHITECTURE.md",
    "docs/architecture.md",
    "docs/ARCHITECTURE.md",
]

# Glob-style patterns to match in the tree (case-insensitive prefix match)
PRIORITY_PREFIXES = [
    ".github/workflows/",
    "terraform/",
    "infra/",
    "infrastructure/",
    "deploy/",
]

# Cap on total raw content to avoid exceeding prompt limits
MAX_TOTAL_CHARS = 40_000
# Per-file cap
MAX_FILE_CHARS = 10_000
# Request timeout in seconds
REQUEST_TIMEOUT = 10

_GITHUB_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/(?P<owner>[^/]+)/(?P<repo>[^/#?.]+)"
    r"(?:/tree/(?P<branch>[^/#?]+))?",
    re.IGNORECASE,
)


def parse_github_url(url: str) -> dict[str, str | None] | None:
    """Parse a GitHub URL into owner, repo, and optional branch.

    Returns dict with keys: owner, repo, branch (or None).
    Returns None if the URL is not a valid GitHub repo URL.
    """
    url = url.strip().rstrip("/")
    # Strip .git suffix
    if url.endswith(".git"):
        url = url[:-4]

    match = _GITHUB_URL_RE.search(url)
    if not match:
        return None

    return {
        "owner": match.group("owner"),
        "repo": match.group("repo"),
        "branch": match.group("branch"),
    }


def _github_request(path: str, token: str | None = None) -> dict | str | None:
    """Make a GET request to the GitHub API. Returns parsed JSON or None on error."""
    url = f"https://api.github.com{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ArchFlow/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as e:
        logger.warning("GitHub API %s returned %d: %s", path, e.code, e.reason)
        raise
    except urllib.error.URLError as e:
        logger.warning("GitHub API request failed for %s: %s", path, e.reason)
        raise
    except json.JSONDecodeError:
        logger.warning("GitHub API returned non-JSON for %s", path)
        return None


def _fetch_file_content(owner: str, repo: str, path: str, ref: str, token: str | None = None) -> str | None:
    """Fetch raw file content from GitHub."""
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"
    headers = {"User-Agent": "ArchFlow/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.debug("Failed to fetch file %s: %s", path, e)
        return None


def fetch_repo_context(url: str, github_token: str | None = None) -> dict[str, Any]:
    """Fetch rich context from a GitHub repository.

    Returns a dict with:
        - owner, repo, branch: parsed URL components
        - metadata: repo description, language, topics, stars, etc.
        - tree_summary: formatted directory tree (top 2 levels)
        - files: dict of {path: content} for priority files
        - assembled_text: combined text blob ready for AI analysis
        - error: error message if something went wrong (partial results may still be returned)
    """
    token = github_token or os.environ.get("GITHUB_TOKEN", "").strip() or None

    parsed = parse_github_url(url)
    if not parsed:
        return {"error": f"Invalid GitHub URL: {url}"}

    owner = parsed["owner"]
    repo = parsed["repo"]
    result: dict[str, Any] = {"owner": owner, "repo": repo, "branch": None}

    # 1. Fetch repo metadata
    try:
        meta = _github_request(f"/repos/{owner}/{repo}", token)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {**result, "error": f"Repository {owner}/{repo} not found. Check the URL and ensure the repo is accessible."}
        if e.code == 403:
            return {**result, "error": "GitHub API rate limit reached or repo is private. Try again later or configure a GITHUB_TOKEN."}
        return {**result, "error": f"GitHub API error: {e.code} {e.reason}"}
    except Exception as e:
        return {**result, "error": f"Failed to reach GitHub API: {e}"}

    if not isinstance(meta, dict):
        return {**result, "error": "Unexpected GitHub API response."}

    branch = parsed["branch"] or meta.get("default_branch", "main")
    result["branch"] = branch
    result["metadata"] = {
        "description": meta.get("description", ""),
        "language": meta.get("language", ""),
        "topics": meta.get("topics", []),
        "stars": meta.get("stargazers_count", 0),
        "forks": meta.get("forks_count", 0),
        "size_kb": meta.get("size", 0),
        "default_branch": meta.get("default_branch", ""),
        "license": (meta.get("license") or {}).get("spdx_id", ""),
        "archived": meta.get("archived", False),
        "created_at": meta.get("created_at", ""),
        "updated_at": meta.get("updated_at", ""),
    }

    # 2. Fetch directory tree
    tree_paths: list[str] = []
    try:
        tree_data = _github_request(f"/repos/{owner}/{repo}/git/trees/{branch}?recursive=1", token)
        if isinstance(tree_data, dict) and "tree" in tree_data:
            tree_paths = [item["path"] for item in tree_data["tree"] if item.get("type") in ("blob", "tree")]
    except Exception as e:
        logger.warning("Failed to fetch tree for %s/%s: %s", owner, repo, e)

    # Build a compact tree summary (top 2 levels + priority file indicators)
    tree_summary = _build_tree_summary(tree_paths)
    result["tree_summary"] = tree_summary

    # 3. Identify and fetch priority files
    files_to_fetch = _identify_priority_files(tree_paths)
    fetched_files: dict[str, str] = {}
    total_chars = 0

    for file_path in files_to_fetch:
        if total_chars >= MAX_TOTAL_CHARS:
            break
        content = _fetch_file_content(owner, repo, file_path, branch, token)
        if content:
            truncated = content[:MAX_FILE_CHARS]
            if len(content) > MAX_FILE_CHARS:
                truncated += "\n[... truncated]"
            fetched_files[file_path] = truncated
            total_chars += len(truncated)

    result["files"] = fetched_files

    # 4. Assemble into a single text blob
    result["assembled_text"] = _assemble_text(owner, repo, result["metadata"], tree_summary, fetched_files)

    return result


def _build_tree_summary(paths: list[str], max_depth: int = 2) -> str:
    """Build a compact directory tree showing top-level structure."""
    if not paths:
        return "(empty repository)"

    dirs: set[str] = set()
    root_files: list[str] = []

    for p in paths:
        parts = p.split("/")
        if len(parts) == 1:
            root_files.append(p)
        else:
            # Add directories up to max_depth
            for depth in range(1, min(len(parts), max_depth + 1)):
                dirs.add("/".join(parts[:depth]) + "/")

    lines = []
    # Root files first
    for f in sorted(root_files)[:20]:
        lines.append(f"  {f}")

    # Then directories
    for d in sorted(dirs)[:40]:
        lines.append(f"  {d}")

    summary = "\n".join(lines)
    total = len(paths)
    if total > 60:
        summary += f"\n  ... and {total - 60} more files/directories"

    return summary


def _identify_priority_files(tree_paths: list[str]) -> list[str]:
    """Identify which files to fetch based on priority list and patterns."""
    path_set = set(tree_paths)
    to_fetch: list[str] = []
    seen: set[str] = set()

    # Exact matches first
    for pf in PRIORITY_FILES:
        # Case-insensitive match
        for actual in tree_paths:
            if actual.lower() == pf.lower() and actual not in seen:
                to_fetch.append(actual)
                seen.add(actual)
                break

    # Prefix pattern matches
    for prefix in PRIORITY_PREFIXES:
        for actual in tree_paths:
            if actual.lower().startswith(prefix.lower()) and actual not in seen:
                # Only fetch files, not directories (files have extensions)
                if "." in actual.split("/")[-1]:
                    to_fetch.append(actual)
                    seen.add(actual)

    # Cap to avoid too many API calls
    return to_fetch[:15]


def _assemble_text(
    owner: str,
    repo: str,
    metadata: dict,
    tree_summary: str,
    files: dict[str, str],
) -> str:
    """Assemble all fetched data into a structured text blob for AI analysis."""
    sections = []

    # Header
    sections.append(f"# GitHub Repository: {owner}/{repo}")
    if metadata.get("description"):
        sections.append(f"Description: {metadata['description']}")
    if metadata.get("language"):
        sections.append(f"Primary language: {metadata['language']}")
    if metadata.get("topics"):
        sections.append(f"Topics: {', '.join(metadata['topics'])}")
    if metadata.get("license"):
        sections.append(f"License: {metadata['license']}")
    sections.append(f"Stars: {metadata.get('stars', 0)} | Forks: {metadata.get('forks', 0)}")
    sections.append("")

    # Directory structure
    sections.append("## Directory Structure")
    sections.append(tree_summary)
    sections.append("")

    # File contents
    for path, content in files.items():
        sections.append(f"## File: {path}")
        sections.append(content)
        sections.append("")

    return "\n".join(sections)


def contains_github_url(text: str) -> str | None:
    """Check if text contains a GitHub repository URL. Returns the URL or None."""
    match = _GITHUB_URL_RE.search(text)
    if match:
        return match.group(0)
    return None
