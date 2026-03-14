"""Async repo analysis Lambda — invoked asynchronously by the WebSocket handler.

Receives {session_id, repo_url}, fetches repo context, analyses with Nova Lite
thinking mode, and stores the result in the DynamoDB session so the frontend
can poll for it via check_repo_status.
"""

import asyncio

from src.services.bedrock_client import BedrockClient
from src.services.github_fetcher import fetch_repo_context, parse_github_url
from src.services.repo_analyzer import analyze_repo
from src.services.state_manager import state_manager
from src.utils import logger


def lambda_handler(event, context):
    session_id = event["session_id"]
    repo_url = event["repo_url"]

    logger.info("Repo analyzer invoked", extra={"session_id": session_id, "repo_url": repo_url})

    # Fetch repo context via GitHub API
    repo_data = fetch_repo_context(repo_url)
    if repo_data.get("error"):
        _store_error(session_id, repo_url, repo_data["error"])
        return {"status": "error", "error": repo_data["error"]}

    assembled_text = repo_data.get("assembled_text", "")
    if not assembled_text:
        _store_error(session_id, repo_url, "Could not extract content from the repository.")
        return {"status": "error", "error": "empty assembled_text"}

    owner = repo_data["owner"]
    repo = repo_data["repo"]

    # Analyze with Nova Lite thinking — no time pressure in this Lambda
    bedrock = BedrockClient()
    loop = asyncio.new_event_loop()
    try:
        analysis = loop.run_until_complete(analyze_repo(assembled_text, bedrock))
    finally:
        loop.close()

    summary = (
        analysis.get("summary", "Repository analyzed successfully.")
        if isinstance(analysis, dict)
        else str(analysis)[:500]
    )

    _store_result(session_id, owner, repo, summary, analysis)
    logger.info("Repo analysis complete", extra={"session_id": session_id, "repo": f"{owner}/{repo}"})
    return {"status": "ok"}


def _store_result(session_id: str, owner: str, repo: str, summary: str, analysis):
    """Store completed analysis in the session's uploaded_files."""
    file_key = f"github://{owner}/{repo}"
    file_metadata = {
        "file_key": file_key,
        "file_name": f"{repo} (GitHub)",
        "content_type": "application/x-github-repo",
        "status": "ready",
        "analysis_summary": summary,
        "file_analysis": analysis,
    }
    _upsert_uploaded_file(session_id, file_key, file_metadata)


def _store_error(session_id: str, repo_url: str, error_msg: str):
    """Store error result so polling can report it."""
    parsed = parse_github_url(repo_url)
    owner = parsed["owner"] if parsed else "unknown"
    repo = parsed["repo"] if parsed else "unknown"
    file_key = f"github://{owner}/{repo}"
    file_metadata = {
        "file_key": file_key,
        "file_name": f"{repo} (GitHub)",
        "content_type": "application/x-github-repo",
        "status": "error",
        "analysis_summary": error_msg,
        "file_analysis": {"error": error_msg},
    }
    _upsert_uploaded_file(session_id, file_key, file_metadata)
    logger.error("Repo analysis failed", extra={"session_id": session_id, "error": error_msg})


def _upsert_uploaded_file(session_id: str, file_key: str, file_metadata: dict):
    """Insert or replace a file entry in the session's uploaded_files list."""
    loop = asyncio.new_event_loop()
    try:
        ctx = loop.run_until_complete(state_manager.get_session(session_id))
        updated = [f for f in ctx.uploaded_files if f.get("file_key") != file_key]
        updated.append(file_metadata)
        loop.run_until_complete(state_manager.update_session(session_id, {"uploaded_files": updated}))
    finally:
        loop.close()
