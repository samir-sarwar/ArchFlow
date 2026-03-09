import asyncio
import json
import os
import re

import boto3

from src.agents import (
    ArchitectureAdvisor,
    ContextAnalyzer,
    DiagramGenerator,
    OrchestratorAgent,
    RequirementsAnalyst,
)
from src.models import Message
from src.services.bedrock_client import BedrockClient
from src.services.diagram_validator import validate_mermaid_syntax
from src.services.state_manager import ConversationStateManager
from src.utils import SessionExpiredError, SessionNotFoundError, logger

state_manager = ConversationStateManager()
api_gateway = boto3.client(
    "apigatewaymanagementapi",
    endpoint_url=os.environ.get("WEBSOCKET_API_ENDPOINT", ""),
)

# Initialize agents (shared across Lambda invocations via warm starts)
bedrock = BedrockClient()
orchestrator = OrchestratorAgent(
    bedrock_client=bedrock,
    state_manager=state_manager,
    agents={
        "advisor": ArchitectureAdvisor(bedrock_client=bedrock),
        "generator": DiagramGenerator(bedrock_client=bedrock),
        "requirements": RequirementsAnalyst(bedrock_client=bedrock),
        "context": ContextAnalyzer(bedrock_client=bedrock),
    },
)


def lambda_handler(event, context):
    """Handle WebSocket $connect, $disconnect, and $default routes."""
    route_key = event.get("requestContext", {}).get("routeKey")
    connection_id = event.get("requestContext", {}).get("connectionId")

    logger.info(
        "WebSocket event",
        extra={"route_key": route_key, "connection_id": connection_id},
    )

    try:
        if route_key == "$connect":
            return handle_connect(event, connection_id)
        elif route_key == "$disconnect":
            return handle_disconnect(event, connection_id)
        elif route_key == "$default":
            return handle_message(event, connection_id)
        else:
            return {"statusCode": 400, "body": "Unknown route"}
    except Exception as e:
        logger.error("WebSocket handler error", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({
                "type": "error",
                "payload": {"message": "Something went wrong. Please try again."},
            }),
        }


def handle_connect(event, connection_id):
    """Handle new WebSocket connection."""
    logger.info("Client connected", extra={"connection_id": connection_id})
    return {"statusCode": 200}


def handle_disconnect(event, connection_id):
    """Handle WebSocket disconnection."""
    logger.info("Client disconnected", extra={"connection_id": connection_id})
    return {"statusCode": 200}


def handle_message(event, connection_id):
    """Handle incoming WebSocket messages — routes text and utility actions.

    Note: Voice actions (voice_start, audio_chunk, voice_stop) are handled by
    the standalone voice WebSocket server (backend/voice_server/), NOT here.
    """
    body = json.loads(event.get("body", "{}"))
    action = body.get("action", "message")
    session_id = body.get("sessionId")

    logger.info(
        "WebSocket message",
        extra={"connection_id": connection_id, "action": action},
    )

    if action == "sync_diagram":
        return _handle_sync_diagram(body, connection_id, session_id)

    if action == "restore_session":
        return _handle_restore_session(body, connection_id, session_id)

    if action == "file_uploaded":
        return _handle_file_uploaded(body, connection_id, session_id)

    # Default: text chat message
    return _handle_text_message(body, connection_id, session_id)


def _handle_text_message(body, connection_id, session_id):
    """Handle a text chat message."""
    text = body.get("text", "")

    if not text:
        return {"statusCode": 200, "body": json.dumps({
            "type": "error",
            "payload": {"message": "No text provided."},
        })}

    loop = asyncio.new_event_loop()
    try:
        response = loop.run_until_complete(
            _process_message(session_id, text, current_diagram=body.get("currentDiagram"))
        )
    except Exception:
        logger.error("Text message processing failed", exc_info=True)
        return {"statusCode": 200, "body": json.dumps({
            "type": "error",
            "payload": {"message": "Failed to process your message. Please try again."},
        })}
    finally:
        loop.close()

    response_payload = {
        "type": "ai_response",
        "sessionId": response["session_id"],
        "payload": {
            "text": response["text"],
            "agent": response["agent"],
        },
    }

    if response.get("diagram"):
        response_payload["payload"]["diagram"] = response["diagram"]

    return {"statusCode": 200, "body": json.dumps(response_payload)}


def _handle_sync_diagram(body, connection_id, session_id):
    """Handle a diagram sync from the manual editor."""
    syntax = body.get("syntax", "")
    if not session_id or not syntax:
        return {"statusCode": 200, "body": json.dumps({"type": "ack"})}

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(
            state_manager.save_diagram_version(
                session_id, syntax, description="Manual edit"
            )
        )
    finally:
        loop.close()

    return {"statusCode": 200, "body": json.dumps({"type": "ack"})}


def _handle_restore_session(body, connection_id, session_id):
    """Restore a previous session: return full state to client."""
    if not session_id:
        return {"statusCode": 400, "body": json.dumps({
            "type": "error",
            "payload": {"message": "No sessionId provided for restore."},
        })}

    loop = asyncio.new_event_loop()
    session_created_fresh = False
    loop_closed = False
    try:
        context = loop.run_until_complete(
            state_manager.get_session(session_id)
        )
    except SessionNotFoundError:
        # No existing data — safe to create a blank session
        try:
            loop.run_until_complete(state_manager.create_session(session_id=session_id))
        except Exception:
            pass
        session_created_fresh = True
    except SessionExpiredError:
        # Data exists but is stale — do NOT overwrite it
        loop.close()
        loop_closed = True
        return {"statusCode": 200, "body": json.dumps({
            "type": "session_expired",
            "payload": {"message": "Session expired. Starting a new session."},
        })}
    finally:
        if not loop_closed:
            loop.close()

    if session_created_fresh:
        return {"statusCode": 200, "body": json.dumps({
            "type": "session_restored",
            "sessionId": session_id,
            "payload": {
                "messages": [],
                "currentDiagram": None,
                "diagramVersions": [],
                "uploadedFiles": [],
            },
        })}

    return {"statusCode": 200, "body": json.dumps({
        "type": "session_restored",
        "sessionId": session_id,
        "payload": {
            "messages": [m.model_dump() for m in context.messages],
            "currentDiagram": context.current_diagram,
            "diagramVersions": [v.model_dump() for v in context.diagram_versions],
            "uploadedFiles": context.uploaded_files,
        },
    })}


async def _process_message(
    session_id: str | None, text: str, current_diagram: str | None = None
) -> dict:
    """Process a user message through the orchestrator."""
    if session_id:
        context = await state_manager.get_session(session_id)
    else:
        session_id = await state_manager.create_session()
        context = await state_manager.get_session(session_id)

    # Only use the frontend's diagram if the backend has none (fresh session).
    # Otherwise trust DynamoDB state — it may contain a voice AI diagram that
    # the frontend hasn't fully synced yet.
    if current_diagram and not context.current_diagram:
        context.current_diagram = current_diagram

    user_msg = Message(role="user", content=text)
    context.messages.append(user_msg)
    await state_manager.add_message(session_id, user_msg)

    response = await orchestrator.route_request(text, context)

    assistant_msg = Message(
        role="assistant", content=response.text, agent=response.agent_used
    )
    await state_manager.add_message(session_id, assistant_msg)

    if response.diagram_update:
        await state_manager.save_diagram_version(session_id, response.diagram_update)

    return {
        "session_id": session_id,
        "text": response.text,
        "agent": response.agent_used,
        "diagram": response.diagram_update,
    }


def _handle_file_uploaded(body, connection_id, session_id):
    """Handle notification that a file was uploaded to S3."""
    file_key = body.get("fileKey", "")
    file_name = body.get("fileName", "")
    content_type = body.get("contentType", "")

    if not file_key or not session_id:
        return {"statusCode": 400, "body": json.dumps({
            "type": "error",
            "payload": {"message": "Missing fileKey or sessionId."},
        })}

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            _process_uploaded_file(session_id, file_key, file_name, content_type)
        )
    except Exception as e:
        logger.error("File processing error", exc_info=True)
        return {"statusCode": 500, "body": json.dumps({
            "type": "file_status",
            "sessionId": session_id,
            "payload": {
                "fileKey": file_key,
                "status": "error",
                "message": str(e),
            },
        })}
    finally:
        loop.close()

    response_payload = {
        "type": "file_analysis",
        "sessionId": session_id,
        "payload": {
            "fileKey": file_key,
            "fileName": file_name,
            "status": "ready",
            "analysis": result.get("analysis", {}),
            "summary": result.get("summary", ""),
        },
    }

    if result.get("diagram"):
        response_payload["payload"]["diagram"] = result["diagram"]

    return {"statusCode": 200, "body": json.dumps(response_payload)}


async def _process_uploaded_file(session_id, file_key, file_name, content_type):
    """Process uploaded file: extract text, analyze, store in session."""
    context_analyzer = orchestrator.agents["context"]

    if content_type.startswith("image/"):
        result = await context_analyzer.analyze_image(file_key)
    else:
        result = await context_analyzer.process_document(file_key, content_type)

    analysis = result.get("analysis", {})

    if isinstance(analysis, dict):
        summary = analysis.get("summary", "Analysis complete.")
    else:
        summary = str(analysis)[:500]

    file_metadata = {
        "file_key": file_key,
        "file_name": file_name,
        "content_type": content_type,
        "status": "ready",
        "analysis_summary": summary,
        "file_analysis": analysis if isinstance(analysis, dict) else {"summary": summary},
    }

    try:
        context = await state_manager.get_session(session_id)
    except (SessionNotFoundError, SessionExpiredError):
        # Session may not exist yet if file was uploaded before first message
        await state_manager.create_session(session_id=session_id)
        context = await state_manager.get_session(session_id)

    uploaded_files = context.uploaded_files + [file_metadata]
    await state_manager.update_session(session_id, {"uploaded_files": uploaded_files})

    system_msg = Message(
        role="assistant",
        content=f"[File analyzed: {file_name}] {summary}",
        agent="context_analyzer",
    )
    await state_manager.add_message(session_id, system_msg)

    diagram = None
    if isinstance(analysis, str):
        mermaid_match = re.search(r"```mermaid\s*\n(.*?)```", analysis, re.DOTALL)
        if mermaid_match:
            diagram = mermaid_match.group(1).strip()
            await state_manager.save_diagram_version(
                session_id, diagram, description=f"Generated from {file_name}"
            )

    return {"analysis": analysis, "summary": summary, "diagram": diagram}


def _send_to_client(connection_id: str, payload: dict) -> None:
    """Send a message back to the WebSocket client via API Gateway Management API."""
    try:
        api_gateway.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(payload).encode(),
        )
    except Exception:
        logger.error(
            "Failed to send to client",
            extra={"connection_id": connection_id},
            exc_info=True,
        )
