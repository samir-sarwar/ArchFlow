"""GitHub context detection and fetching for the voice server.

Detects GitHub URLs in text messages, fetches the repository file tree
and README via the GitHub API, and stores the output in DynamoDB so that
subsequent AI prompts automatically include the repo context.
"""

import asyncio
import base64
import json
import logging
import os
import re
import urllib.error
import urllib.request
from datetime import datetime

import boto3

from .db_client import VoiceSessionDBClient

_s3 = boto3.client("s3")


def _get_bucket() -> str:
    """Resolve bucket at call time, not import time, so env vars set after import are picked up."""
    return os.environ.get("UPLOADS_BUCKET", "archflow-uploads-dev")

logger = logging.getLogger(__name__)

_GITHUB_URL_RE = re.compile(
    r"https?://(?:www\.)?github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)",
    re.IGNORECASE,
)

_REQUEST_TIMEOUT = 30


def detect_github_url(text: str) -> str | None:
    """Return the first GitHub repo URL found in text, or None."""
    match = _GITHUB_URL_RE.search(text)
    return match.group(0) if match else None


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
            node[parts[-1]] = None

    lines: list[str] = []

    def _render(node: dict, indent: int = 0):
        prefix = "  " * indent
        dirs = sorted(k for k, v in node.items() if v is not None)
        files = sorted(k for k, v in node.items() if v is None)
        for d in dirs:
            lines.append(f"{prefix}{d}/")
            _render(node[d], indent + 1)
        for f in files:
            lines.append(f"{prefix}{f}")

    _render(root)
    return "\n".join(lines)


def _fetch_repo_context(github_url: str) -> str:
    """Fetch lightweight repo context: file tree + README. Returns markdown string."""
    match = _GITHUB_URL_RE.search(github_url)
    if not match:
        raise RuntimeError(f"Invalid GitHub URL: {github_url}")

    owner, repo = match.group("owner"), match.group("repo")

    try:
        meta = _github_api_get(f"/repos/{owner}/{repo}")
        branch = meta.get("default_branch", "main")
        description = meta.get("description", "")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"GitHub API error {e.code} for {owner}/{repo}") from e

    logger.info("Fetching repo context for %s/%s (branch: %s)", owner, repo, branch)

    tree_items = _fetch_tree(owner, repo, branch)
    readme_content = _fetch_readme(owner, repo)
    tree_str = _format_tree(tree_items)

    sections = [f"# Repository: {owner}/{repo}"]
    if description:
        sections.append(f"\n{description}")
    sections.append(f"\n## File Structure\n```\n{tree_str}\n```")
    if readme_content:
        sections.append(f"\n## README.md\n{readme_content}")
    else:
        sections.append("\n## README.md\nNo README found.")

    return "\n".join(sections)


async def maybe_fetch_github_context(
    text: str,
    session_id: str | None,
    region: str,  # noqa: ARG001 — kept for caller compatibility
    db_client: VoiceSessionDBClient,
) -> bool:
    """If text contains a GitHub URL, fetch and store repo context. Returns True if context was added."""
    url = detect_github_url(text)
    if not url or not session_id:
        return False

    match = _GITHUB_URL_RE.search(url)
    if not match:
        return False

    owner = match.group("owner")
    repo = match.group("repo")
    cache_key = f"github://{owner}/{repo}"

    # Check if already analyzed (skip if entry is just a pending placeholder)
    existing = await asyncio.to_thread(db_client.get_uploaded_files, session_id)
    for f in existing:
        if f.get("file_key") == cache_key and f.get("file_analysis") and f.get("status") == "ready":
            logger.info("GitHub repo %s/%s already analyzed in session %s", owner, repo, session_id)
            return True

    logger.info("Detected GitHub URL in text, fetching context for %s/%s", owner, repo)

    try:
        context_output = await asyncio.to_thread(_fetch_repo_context, url)

        # Upload to S3 to avoid DynamoDB 400KB item limit
        s3_key = f"{session_id}/github/{owner}/{repo}/repomix.md"
        await asyncio.to_thread(
            _s3.put_object,
            Bucket=_get_bucket(),
            Key=s3_key,
            Body=context_output.encode("utf-8"),
            ContentType="text/markdown",
        )

        file_metadata = {
            "file_key": cache_key,
            "file_name": f"{owner}/{repo} (GitHub)",
            "content_type": "application/x-github-repo",
            "status": "ready",
            "analysis_summary": f"Repository context (file tree + README, {len(context_output)} chars)",
            "file_analysis": {"repomix_s3_key": s3_key},
        }

        _store_file_metadata(db_client, session_id, file_metadata)
        logger.info("Stored GitHub context for %s/%s in session %s", owner, repo, session_id)
        return True

    except Exception as e:
        logger.error("Failed to fetch GitHub context for %s/%s: %s", owner, repo, e, exc_info=True)
        return False


def _store_file_metadata(db_client: VoiceSessionDBClient, session_id: str, metadata: dict):
    """Upsert file metadata in the session's uploaded_files array (replaces existing entry with same file_key)."""
    now = datetime.utcnow().isoformat()
    file_key = metadata.get("file_key")
    try:
        # Read-modify-write to replace any existing entry with the same file_key
        existing = db_client.get_uploaded_files(session_id)
        updated = [f for f in existing if f.get("file_key") != file_key]
        updated.append(metadata)
        db_client.table.update_item(
            Key={"session_id": session_id},
            UpdateExpression="SET uploaded_files = :files, #la = :now",
            ExpressionAttributeNames={"#la": "last_activity"},
            ExpressionAttributeValues={
                ":files": updated,
                ":now": now,
            },
        )
    except Exception as e:
        logger.error("Failed to store GitHub file metadata: %s", e)
