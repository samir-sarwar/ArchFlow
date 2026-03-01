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


def _handle_voice_message(body, connection_id, session_id):
    """Handle a voice message: download audio from S3, process via Nova Sonic.

    Audio is uploaded to S3 by the frontend via presigned URL, then a small
    WebSocket message with the S3 key triggers this handler.  Responds via
    Management API callback (`_send_to_client`) to bypass the 29s API Gateway
    integration timeout — Nova Sonic can take 30-60s.
    """
    from src.services.voice_handler import process_voice_stream

    audio_key = body.get("audioKey", "")
    if not audio_key:
        _send_to_client(connection_id, {
            "type": "error",
            "payload": {"message": "No audio key provided."},
        })
        return {"statusCode": 200}

    # Download audio from S3
    s3 = boto3.client("s3")
    uploads_bucket = os.environ.get("UPLOADS_BUCKET", "")
    try:
        s3_response = s3.get_object(Bucket=uploads_bucket, Key=audio_key)
        audio_bytes = s3_response["Body"].read()
    except Exception:
        logger.error("Failed to download voice audio from S3", exc_info=True)
        _send_to_client(connection_id, {
            "type": "error",
            "payload": {"message": "Failed to retrieve voice audio."},
        })
        return {"statusCode": 200}

    logger.info("Downloaded voice audio from S3",
                extra={"key": audio_key, "size": len(audio_bytes)})

    _send_to_client(connection_id, {
        "type": "voice_status",
        "payload": {"stage": "converting", "message": "Converting audio..."},
    })

    # Callback to stream transcription to client as Nova Sonic produces it
    def _on_transcription(text: str):
        _send_to_client(connection_id, {
            "type": "voice_transcription",
            "payload": {"text": text},
        })

    _send_to_client(connection_id, {
        "type": "voice_status",
        "payload": {"stage": "transcribing", "message": "Transcribing speech..."},
    })

    # Process via Nova Sonic (STT + response + TTS)
    loop = asyncio.new_event_loop()
    try:
        voice_result = loop.run_until_complete(
            process_voice_stream(
                audio_bytes,
                session_id or "",
                bedrock_client=bedrock,
                on_transcription=_on_transcription,
            )
        )
    except Exception:
        logger.error("Voice stream processing failed", exc_info=True)
        _send_to_client(connection_id, {
            "type": "error",
            "payload": {"message": "Voice processing failed. Please try again."},
        })
        return {"statusCode": 200}
    finally:
        loop.close()

    transcription = voice_result.get("transcription", "")
    response_text = voice_result.get("response_text", "")
    audio_chunks = voice_result.get("audio_chunks", [])

    # Check for structured errors from voice handler
    if voice_result.get("error"):
        _send_to_client(connection_id, {
            "type": "error",
            "payload": {"message": voice_result["error"]},
        })
        return {"statusCode": 200}

    if not transcription:
        _send_to_client(connection_id, {
            "type": "error",
            "payload": {"message": "Could not transcribe audio. Please speak clearly and try again."},
        })
        return {"statusCode": 200}

    # Save messages to conversation state
    if session_id:
        loop = asyncio.new_event_loop()
        try:
            user_msg = Message(role="user", content=transcription)
            loop.run_until_complete(state_manager.add_message(session_id, user_msg))
            assistant_msg = Message(
                role="assistant", content=response_text, agent="nova_sonic"
            )
            loop.run_until_complete(
                state_manager.add_message(session_id, assistant_msg)
            )
        finally:
            loop.close()

    has_audio = len(audio_chunks) > 0

    # Send response via Management API callback (bypasses 29s route response timeout)
    _send_to_client(connection_id, {
        "type": "ai_response",
        "sessionId": session_id,
        "payload": {
            "text": response_text,
            "agent": "nova_sonic",
            "transcription": transcription,
            "hasAudio": has_audio,
        },
    })

    # Stream audio chunks to client (frontend creates chunk player on hasAudio=True)
    if has_audio:
        safe_chunks = _split_large_chunks(audio_chunks)
        for chunk in safe_chunks:
            _send_to_client(connection_id, {
                "type": "audio_chunk",
                "payload": {"audio": chunk},
            })
        _send_to_client(connection_id, {
            "type": "audio_end",
            "payload": {},
        })
        logger.info("Sent audio response", extra={"chunk_count": len(safe_chunks)})

    # Trigger diagram post-processing if response mentions architecture
    current_diagram = body.get("currentDiagram")
    _post_process_voice_diagram(response_text, connection_id, session_id, current_diagram)

    # Clean up audio file from S3 (lifecycle rule handles stragglers)
    try:
        s3.delete_object(Bucket=uploads_bucket, Key=audio_key)
    except Exception:
        pass

    return {"statusCode": 200}


_MAX_CHUNK_SIZE = 100_000  # 100KB base64 safety limit per WebSocket frame


def _split_large_chunks(chunks: list[str], max_size: int = _MAX_CHUNK_SIZE) -> list[str]:
    """Split any oversized base64 audio chunks to stay under WS frame limits."""
    result = []
    for chunk in chunks:
        while len(chunk) > max_size:
            result.append(chunk[:max_size])
            chunk = chunk[max_size:]
        if chunk:
            result.append(chunk)
    return result


def _post_process_voice_diagram(
    response_text: str, connection_id: str, session_id: str | None, current_diagram: str | None
):
    """Check if a voice response mentions architecture and generate a diagram update."""
    if not response_text or not session_id:
        return

    # Simple keyword check to avoid unnecessary Bedrock calls
    diagram_keywords = [
        "component", "service", "database", "api", "layer", "module",
        "microservice", "architecture", "diagram", "flow", "system",
    ]
    text_lower = response_text.lower()
    if not any(kw in text_lower for kw in diagram_keywords):
        return

    logger.info("Voice response may warrant diagram update, routing to generator")

    diagram_prompt = (
        f"Based on this architecture discussion, update or create a Mermaid diagram.\n\n"
        f"Discussion:\n{response_text}\n\n"
    )
    if current_diagram:
        diagram_prompt += f"Current diagram:\n```mermaid\n{current_diagram}\n```\n\n"
    diagram_prompt += (
        "Output ONLY valid Mermaid.js syntax. "
        "Do not wrap in code fences. Do not include any explanation."
    )

    loop = asyncio.new_event_loop()
    try:
        raw = loop.run_until_complete(
            bedrock.invoke_lite(prompt=diagram_prompt)
        )

        # Strip code fences if the model adds them
        cleaned = raw.strip()
        if cleaned.startswith("```mermaid"):
            cleaned = cleaned[len("```mermaid"):].strip()
        if cleaned.startswith("```"):
            cleaned = cleaned[3:].strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()

        # Validate and retry once if invalid
        if cleaned:
            state = validate_mermaid_syntax(cleaned)
            if not state.is_valid:
                logger.warning(
                    "Voice diagram failed validation, retrying once",
                    extra={"error": state.error_message},
                )
                retry_prompt = (
                    f"The Mermaid syntax has this error: {state.error_message}. "
                    f"Fix it and return ONLY valid Mermaid syntax — no explanation, no code fences.\n\n"
                    f"Broken syntax:\n{cleaned}"
                )
                try:
                    raw_retry = loop.run_until_complete(
                        bedrock.invoke_lite(prompt=retry_prompt)
                    )
                    retried = raw_retry.strip()
                    if retried.startswith("```mermaid"):
                        retried = retried[len("```mermaid"):].strip()
                    if retried.startswith("```"):
                        retried = retried[3:].strip()
                    if retried.endswith("```"):
                        retried = retried[:-3].strip()
                    cleaned = retried
                except Exception:
                    logger.warning("Voice diagram retry failed, using original", exc_info=True)

        if cleaned:
            loop.run_until_complete(
                state_manager.save_diagram_version(
                    session_id, cleaned, description="Generated from voice"
                )
            )
            _send_to_client(connection_id, {
                "type": "diagram_update",
                "sessionId": session_id,
                "payload": {"diagram": cleaned},
            })
    except Exception:
        logger.error("Diagram post-processing failed", exc_info=True)
    finally:
        loop.close()


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
    try:
        context = loop.run_until_complete(
            state_manager.get_session(session_id)
        )
    except (SessionNotFoundError, SessionExpiredError):
        return {"statusCode": 200, "body": json.dumps({
            "type": "session_expired",
            "payload": {"message": "Session not found or expired."},
        })}
    finally:
        loop.close()

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

    # Include diagram in the same response if analysis produced one
    if result.get("diagram"):
        response_payload["payload"]["diagram"] = result["diagram"]

    return {"statusCode": 200, "body": json.dumps(response_payload)}


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
