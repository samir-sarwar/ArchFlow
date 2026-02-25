import asyncio
import json
import os

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
        # Send error back to client before returning
        _send_to_client(connection_id, {
            "type": "error",
            "payload": {"message": "Something went wrong. Please try again."},
        })
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


def handle_connect(event, connection_id):
    """Handle new WebSocket connection."""
    logger.info("Client connected", extra={"connection_id": connection_id})
    return {"statusCode": 200}


def handle_disconnect(event, connection_id):
    """Handle WebSocket disconnection."""
    logger.info("Client disconnected", extra={"connection_id": connection_id})
    return {"statusCode": 200}


def handle_message(event, connection_id):
    """Handle incoming WebSocket messages — routes text and voice actions."""
    body = json.loads(event.get("body", "{}"))
    action = body.get("action", "message")
    session_id = body.get("sessionId")

    logger.info(
        "WebSocket message",
        extra={"connection_id": connection_id, "action": action},
    )

    if action == "voice":
        return _handle_voice_message(body, connection_id, session_id)

    if action == "sync_diagram":
        return _handle_sync_diagram(body, connection_id, session_id)

    if action == "restore_session":
        return _handle_restore_session(body, connection_id, session_id)

    if action == "file_uploaded":
        return _handle_file_uploaded(body, connection_id, session_id)

    return _handle_text_message(body, connection_id, session_id)


def _handle_text_message(body, connection_id, session_id):
    """Handle a text chat message."""
    text = body.get("text", "")
    current_diagram = body.get("currentDiagram")

    if not text:
        _send_to_client(connection_id, {
            "type": "error",
            "payload": {"message": "No text provided."},
        })
        return {"statusCode": 400}

    loop = asyncio.new_event_loop()
    try:
        response = loop.run_until_complete(
            _process_message(session_id, text, current_diagram=current_diagram)
        )
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

    _send_to_client(connection_id, response_payload)

    return {"statusCode": 200}


def _handle_voice_message(body, connection_id, session_id):
    """Handle a voice message: transcribe audio then route through orchestrator."""
    import base64
    from src.services.voice_handler import process_voice_stream

    audio_b64 = body.get("audio", "")
    current_diagram = body.get("currentDiagram")
    if not audio_b64:
        _send_to_client(connection_id, {
            "type": "error",
            "payload": {"message": "No audio data provided."},
        })
        return {"statusCode": 400}

    audio_bytes = base64.b64decode(audio_b64)

    # Step 1: Transcribe audio via Nova Sonic
    loop = asyncio.new_event_loop()
    try:
        voice_result = loop.run_until_complete(
            process_voice_stream(audio_bytes, session_id or "")
        )
    finally:
        loop.close()

    transcription = voice_result.get("transcription", "")
    if not transcription:
        _send_to_client(connection_id, {
            "type": "error",
            "payload": {"message": "Could not transcribe audio. Please try again."},
        })
        return {"statusCode": 400}

    # Step 2: Route transcription through existing orchestrator pipeline
    loop = asyncio.new_event_loop()
    try:
        response = loop.run_until_complete(
            _process_message(session_id, transcription, current_diagram=current_diagram)
        )
    finally:
        loop.close()

    response_payload = {
        "type": "ai_response",
        "sessionId": response["session_id"],
        "payload": {
            "text": response["text"],
            "agent": response["agent"],
            "transcription": transcription,
        },
    }

    if response.get("diagram"):
        response_payload["payload"]["diagram"] = response["diagram"]

    _send_to_client(connection_id, response_payload)

    return {"statusCode": 200}


def _handle_sync_diagram(body, connection_id, session_id):
    """Handle a diagram sync from the manual editor."""
    syntax = body.get("syntax", "")
    if not session_id or not syntax:
        return {"statusCode": 400}

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(
            state_manager.save_diagram_version(
                session_id, syntax, description="Manual edit"
            )
        )
    finally:
        loop.close()

    return {"statusCode": 200}


def _handle_restore_session(body, connection_id, session_id):
    """Restore a previous session: return full state to client."""
    if not session_id:
        _send_to_client(connection_id, {
            "type": "error",
            "payload": {"message": "No sessionId provided for restore."},
        })
        return {"statusCode": 400}

    loop = asyncio.new_event_loop()
    try:
        context = loop.run_until_complete(
            state_manager.get_session(session_id)
        )
    except (SessionNotFoundError, SessionExpiredError):
        _send_to_client(connection_id, {
            "type": "session_expired",
            "payload": {"message": "Session not found or expired."},
        })
        return {"statusCode": 200}
    finally:
        loop.close()

    _send_to_client(connection_id, {
        "type": "session_restored",
        "sessionId": session_id,
        "payload": {
            "messages": [m.model_dump() for m in context.messages],
            "currentDiagram": context.current_diagram,
            "diagramVersions": [v.model_dump() for v in context.diagram_versions],
            "uploadedFiles": context.uploaded_files,
        },
    })

    return {"statusCode": 200}


async def _process_message(
    session_id: str | None, text: str, current_diagram: str | None = None
) -> dict:
    """Process a user message through the orchestrator."""
    # Get or create session
    if session_id:
        context = await state_manager.get_session(session_id)
    else:
        session_id = await state_manager.create_session()
        context = await state_manager.get_session(session_id)

    # Override backend diagram with frontend's version (manual edits safety net)
    if current_diagram:
        context.current_diagram = current_diagram

    # Add user message
    user_msg = Message(role="user", content=text)
    context.messages.append(user_msg)
    await state_manager.add_message(session_id, user_msg)

    # Route through orchestrator
    response = await orchestrator.route_request(text, context)

    # Save assistant message
    assistant_msg = Message(
        role="assistant", content=response.text, agent=response.agent_used
    )
    await state_manager.add_message(session_id, assistant_msg)

    # Save diagram version if updated
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
        _send_to_client(connection_id, {
            "type": "error",
            "payload": {"message": "Missing fileKey or sessionId."},
        })
        return {"statusCode": 400}

    # Send processing status immediately
    _send_to_client(connection_id, {
        "type": "file_status",
        "sessionId": session_id,
        "payload": {"fileKey": file_key, "status": "processing"},
    })

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            _process_uploaded_file(session_id, file_key, file_name, content_type)
        )
    except Exception as e:
        logger.error("File processing error", exc_info=True)
        _send_to_client(connection_id, {
            "type": "file_status",
            "sessionId": session_id,
            "payload": {
                "fileKey": file_key,
                "status": "error",
                "message": str(e),
            },
        })
        return {"statusCode": 500}
    finally:
        loop.close()

    # Send analysis result back
    _send_to_client(connection_id, {
        "type": "file_analysis",
        "sessionId": session_id,
        "payload": {
            "fileKey": file_key,
            "fileName": file_name,
            "status": "ready",
            "analysis": result.get("analysis", {}),
            "summary": result.get("summary", ""),
        },
    })

    # If analysis produced a diagram, send that too
    if result.get("diagram"):
        _send_to_client(connection_id, {
            "type": "diagram_update",
            "sessionId": session_id,
            "payload": {"diagram": result["diagram"]},
        })

    return {"statusCode": 200}


async def _process_uploaded_file(session_id, file_key, file_name, content_type):
    """Process uploaded file: extract text, analyze, store in session."""
    context_analyzer = orchestrator.agents["context"]

    # Run analysis
    if content_type.startswith("image/"):
        result = await context_analyzer.analyze_image(file_key)
    else:
        result = await context_analyzer.process_document(file_key, content_type)

    analysis = result.get("analysis", {})

    # Build summary text
    if isinstance(analysis, dict):
        summary = analysis.get("summary", "Analysis complete.")
    else:
        summary = str(analysis)[:500]

    # Store file metadata + analysis in the session
    file_metadata = {
        "file_key": file_key,
        "file_name": file_name,
        "content_type": content_type,
        "status": "ready",
        "analysis_summary": summary,
    }

    context = await state_manager.get_session(session_id)
    uploaded_files = context.uploaded_files + [file_metadata]
    await state_manager.update_session(session_id, {"uploaded_files": uploaded_files})

    # Add a system message so other agents have context about the upload
    system_msg = Message(
        role="assistant",
        content=f"[File analyzed: {file_name}] {summary}",
        agent="context_analyzer",
    )
    await state_manager.add_message(session_id, system_msg)

    # Check if a diagram was generated (from image analysis)
    diagram = None
    if isinstance(analysis, str):
        import re
        mermaid_match = re.search(r"```mermaid\s*\n(.*?)```", analysis, re.DOTALL)
        if mermaid_match:
            diagram = mermaid_match.group(1).strip()
            await state_manager.save_diagram_version(
                session_id, diagram, description=f"Generated from {file_name}"
            )

    return {"analysis": analysis, "summary": summary, "diagram": diagram}


def _send_to_client(connection_id: str, payload: dict) -> None:
    """Send a message back to the WebSocket client."""
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
