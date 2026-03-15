"""Async repo analysis Lambda — invoked asynchronously by the WebSocket handler.

Receives {session_id, repo_url}, uses Repomix to pack the repository with
compression, uploads the output to S3, and stores an S3 key reference in
DynamoDB so the frontend can poll for it via check_repo_status.
"""

import asyncio
import os

import boto3

from src.services.repo_context_service import fetch_repo_context, parse_github_url
from src.services.state_manager import ConversationStateManager
from src.utils import logger

state_manager = ConversationStateManager()
s3 = boto3.client("s3")
BUCKET = os.environ.get("UPLOADS_BUCKET", "archflow-uploads-dev")


def lambda_handler(event, context):
    session_id = event["session_id"]
    repo_url = event["repo_url"]

    logger.info("Repo analyzer invoked", extra={"session_id": session_id, "repo_url": repo_url})

    parsed = parse_github_url(repo_url)
    owner = parsed["owner"] if parsed else "unknown"
    repo = parsed["repo"] if parsed else "unknown"

    try:
        result = fetch_repo_context(repo_url)
        context_output = result["context_output"]

        _store_result(session_id, owner, repo, context_output)
        logger.info("Repo analysis complete", extra={"session_id": session_id, "repo": f"{owner}/{repo}", "chars": result["char_count"]})
        return {"status": "ok"}

    except Exception as e:
        logger.error("Repo analyzer failed", exc_info=True)
        try:
            _store_error(session_id, owner, repo, f"Analysis failed: {e}")
        except Exception:
            logger.error("Failed to store error status", exc_info=True)
        return {"status": "error", "error": str(e)}


def _store_result(session_id: str, owner: str, repo: str, packed_output: str):
    """Upload repomix output to S3 and store S3 key in DynamoDB."""
    s3_key = f"{session_id}/github/{owner}/{repo}/repomix.md"

    s3.put_object(
        Bucket=BUCKET,
        Key=s3_key,
        Body=packed_output.encode("utf-8"),
        ContentType="text/markdown",
    )
    logger.info("Uploaded repomix output to S3", extra={"s3_key": s3_key, "chars": len(packed_output)})

    file_key = f"github://{owner}/{repo}"
    file_metadata = {
        "file_key": file_key,
        "file_name": f"{repo} (GitHub)",
        "content_type": "application/x-github-repo",
        "status": "ready",
        "analysis_summary": f"Repository context (file tree + README, {len(packed_output)} chars)",
        "file_analysis": {"repomix_s3_key": s3_key},
    }
    _upsert_uploaded_file(session_id, file_key, file_metadata)


def _store_error(session_id: str, owner: str, repo: str, error_msg: str):
    """Store error result so polling can report it."""
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
