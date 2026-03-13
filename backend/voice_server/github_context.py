"""GitHub context detection and fetching for the voice server.

Detects GitHub URLs in text messages, fetches repo context,
analyzes it with Nova Lite, and stores it in DynamoDB so that
subsequent AI prompts automatically include the repo context.
"""

import asyncio
import json
import logging
import os
import re
import urllib.error
import urllib.request
from datetime import datetime

import boto3

from .db_client import VoiceSessionDBClient

logger = logging.getLogger(__name__)

MODEL_LITE = os.environ.get("BEDROCK_MODEL_LITE", "us.amazon.nova-2-lite-v1:0")

_GITHUB_URL_RE = re.compile(
    r"https?://(?:www\.)?github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)",
    re.IGNORECASE,
)

PRIORITY_FILES = [
    "README.md", "README.rst", "README",
    "package.json", "requirements.txt", "Pipfile", "pyproject.toml",
    "go.mod", "Cargo.toml", "pom.xml", "build.gradle",
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "serverless.yml", "template.yaml", "template.yml",
    "tsconfig.json", "next.config.js", "vite.config.ts",
    "architecture.md", "ARCHITECTURE.md",
]

REPO_ANALYSIS_PROMPT = """You are an expert software architect analyzing a GitHub repository.

Given the repository metadata, directory structure, and key file contents, extract:
1. Architecture Style (monolith, microservices, serverless, etc.)
2. Technology Stack (languages, frameworks, databases, cloud services)
3. System Components (services, modules, key directories)
4. Infrastructure (deployment, CI/CD, containerization)
5. Design Patterns (event-driven, CQRS, MVC, etc.)

Return structured JSON:
{
  "summary": "2-3 sentence summary",
  "architecture_style": "...",
  "components": ["..."],
  "patterns": ["..."],
  "technologies": ["..."],
  "infrastructure": ["..."],
  "requirements": {"functional": ["..."], "non_functional": ["..."]},
  "data_flows": ["..."]
}
"""

REQUEST_TIMEOUT = 10
MAX_TOTAL_CHARS = 40_000
MAX_FILE_CHARS = 10_000


def detect_github_url(text: str) -> str | None:
    """Return the first GitHub repo URL found in text, or None."""
    match = _GITHUB_URL_RE.search(text)
    return match.group(0) if match else None


async def maybe_fetch_github_context(
    text: str,
    session_id: str | None,
    region: str,
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

    # Check if already analyzed
    existing = await asyncio.to_thread(db_client.get_uploaded_files, session_id)
    for f in existing:
        if f.get("file_key") == cache_key:
            logger.info("GitHub repo %s/%s already analyzed in session %s", owner, repo, session_id)
            return True

    logger.info("Detected GitHub URL in text, fetching context for %s/%s", owner, repo)

    try:
        repo_data = await asyncio.to_thread(_fetch_repo_context, owner, repo)
        if not repo_data.get("assembled_text"):
            logger.warning("No content extracted from %s/%s", owner, repo)
            return False

        # Analyze with Nova Lite
        analysis = await asyncio.to_thread(_analyze_repo, repo_data["assembled_text"], region)

        summary = analysis.get("summary", "Repository analyzed.") if isinstance(analysis, dict) else str(analysis)[:500]

        # Store in DynamoDB uploaded_files
        file_metadata = {
            "file_key": cache_key,
            "file_name": f"{owner}/{repo} (GitHub)",
            "content_type": "application/x-github-repo",
            "status": "ready",
            "analysis_summary": summary,
            "file_analysis": analysis if isinstance(analysis, dict) else {"summary": summary},
        }

        _store_file_metadata(db_client, session_id, file_metadata)
        logger.info("Stored GitHub context for %s/%s in session %s", owner, repo, session_id)
        return True

    except Exception as e:
        logger.error("Failed to fetch/analyze GitHub repo %s/%s: %s", owner, repo, e, exc_info=True)
        return False


def _store_file_metadata(db_client: VoiceSessionDBClient, session_id: str, metadata: dict):
    """Append file metadata to the session's uploaded_files array."""
    now = datetime.utcnow().isoformat()
    try:
        db_client.table.update_item(
            Key={"session_id": session_id},
            UpdateExpression="SET uploaded_files = list_append(if_not_exists(uploaded_files, :empty), :new_file), #la = :now",
            ExpressionAttributeNames={"#la": "last_activity"},
            ExpressionAttributeValues={
                ":new_file": [metadata],
                ":empty": [],
                ":now": now,
            },
        )
    except Exception as e:
        logger.error("Failed to store GitHub file metadata: %s", e)


def _github_get(path: str, token: str | None = None):
    """GET from GitHub API, returns parsed JSON."""
    url = f"https://api.github.com{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ArchFlow/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fetch_raw_file(owner: str, repo: str, path: str, ref: str, token: str | None = None) -> str | None:
    """Fetch raw file content from GitHub."""
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"
    headers = {"User-Agent": "ArchFlow/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def _fetch_repo_context(owner: str, repo: str) -> dict:
    """Fetch repo metadata, tree, and key files. Runs in a thread."""
    token = os.environ.get("GITHUB_TOKEN", "").strip() or None

    try:
        meta = _github_get(f"/repos/{owner}/{repo}", token)
    except urllib.error.HTTPError as e:
        return {"error": f"GitHub API error {e.code}"}
    except Exception as e:
        return {"error": str(e)}

    branch = meta.get("default_branch", "main")

    # Fetch tree
    tree_paths = []
    try:
        tree_data = _github_get(f"/repos/{owner}/{repo}/git/trees/{branch}?recursive=1", token)
        if isinstance(tree_data, dict) and "tree" in tree_data:
            tree_paths = [item["path"] for item in tree_data["tree"] if item.get("type") in ("blob", "tree")]
    except Exception:
        pass

    # Build tree summary
    dirs = set()
    root_files = []
    for p in tree_paths:
        parts = p.split("/")
        if len(parts) == 1:
            root_files.append(p)
        else:
            for depth in range(1, min(len(parts), 3)):
                dirs.add("/".join(parts[:depth]) + "/")

    tree_lines = [f"  {f}" for f in sorted(root_files)[:20]]
    tree_lines += [f"  {d}" for d in sorted(dirs)[:40]]
    tree_summary = "\n".join(tree_lines)

    # Fetch priority files
    path_set_lower = {p.lower() for p in tree_paths}
    files_to_fetch = []
    for pf in PRIORITY_FILES:
        for actual in tree_paths:
            if actual.lower() == pf.lower():
                files_to_fetch.append(actual)
                break

    fetched = {}
    total = 0
    for fp in files_to_fetch[:10]:
        if total >= MAX_TOTAL_CHARS:
            break
        content = _fetch_raw_file(owner, repo, fp, branch, token)
        if content:
            truncated = content[:MAX_FILE_CHARS]
            fetched[fp] = truncated
            total += len(truncated)

    # Assemble
    sections = [f"# GitHub Repository: {owner}/{repo}"]
    if meta.get("description"):
        sections.append(f"Description: {meta['description']}")
    if meta.get("language"):
        sections.append(f"Primary language: {meta['language']}")
    topics = meta.get("topics", [])
    if topics:
        sections.append(f"Topics: {', '.join(topics)}")
    sections.append("")
    sections.append("## Directory Structure")
    sections.append(tree_summary)
    sections.append("")
    for path, content in fetched.items():
        sections.append(f"## File: {path}")
        sections.append(content)
        sections.append("")

    return {"assembled_text": "\n".join(sections)}


def _analyze_repo(assembled_text: str, region: str) -> dict:
    """Analyze repo text with Nova Lite. Runs in a thread."""
    client = boto3.client("bedrock-runtime", region_name=region)

    try:
        response = client.converse(
            modelId=MODEL_LITE,
            messages=[{"role": "user", "content": [{"text": f"Analyze this GitHub repository:\n\n{assembled_text}"}]}],
            system=[{"text": REPO_ANALYSIS_PROMPT}],
            inferenceConfig={"maxTokens": 2048, "topP": 0.9, "temperature": 0.7},
        )
        result_text = response["output"]["message"]["content"][0]["text"]

        try:
            return json.loads(result_text)
        except json.JSONDecodeError:
            import re as _re
            match = _re.search(r"```(?:json)?\s*\n(.*?)```", result_text, _re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
            return {"summary": result_text, "raw": True}

    except Exception as e:
        logger.error("Repo analysis via Nova Lite failed: %s", e)
        return {"summary": f"Analysis failed: {e}", "raw": True}
