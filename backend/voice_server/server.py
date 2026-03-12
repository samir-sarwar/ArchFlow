"""
ArchFlow Voice WebSocket Server.

Phase 2 fixes:
  - Added _bootstrap_aws_credentials() for SSO/profile support.
  - Replaced _forward_responses (blind relay) with _handle_nova_events that
    TRANSLATES raw Nova Sonic events into the ArchFlow message format the
    frontend already knows how to handle.
  - Server now owns promptEnd/sessionEnd lifecycle: it sends them to Bedrock
    after receiving completionEnd, not the browser.
"""

import argparse
import asyncio
import http.server
import json
import logging
import os
import threading
import warnings
from http import HTTPStatus

import boto3
import websockets

from .session_manager import S2sSessionManager
from .db_client import VoiceSessionDBClient

warnings.filterwarnings("ignore")

LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
logging.basicConfig(level=LOGLEVEL, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ─── Credential bootstrap ───

def _bootstrap_aws_credentials(profile: str | None = None):
    """Pull creds from boto3 (SSO-aware) and inject into env vars for Smithy SDK."""
    try:
        profile = profile or os.environ.get("AWS_PROFILE")
        session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        creds = session.get_credentials()
        if creds is None:
            logger.warning("No AWS credentials found via boto3.")
            return

        frozen = creds.get_frozen_credentials()
        os.environ["AWS_ACCESS_KEY_ID"] = frozen.access_key
        os.environ["AWS_SECRET_ACCESS_KEY"] = frozen.secret_key
        if frozen.token:
            os.environ["AWS_SESSION_TOKEN"] = frozen.token
        else:
            os.environ.pop("AWS_SESSION_TOKEN", None)

        if not os.environ.get("AWS_DEFAULT_REGION"):
            os.environ["AWS_DEFAULT_REGION"] = session.region_name or "us-east-1"

        logger.info(
            "AWS credentials bootstrapped via boto3 (profile=%s, access_key_prefix=%s)",
            profile or "default",
            frozen.access_key[:8],
        )
    except Exception as exc:
        logger.error("Failed to bootstrap AWS credentials: %s", exc)
        logger.error("Run: aws sso login --profile <your-profile>")


# ─── Health check ───

class _HealthCheckHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/health"):
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"healthy"}')
        else:
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()

    def log_message(self, *_):
        pass


def _start_health_server(host: str, port: int):
    try:
        httpd = http.server.HTTPServer((host, port), _HealthCheckHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        logger.info("Health check server listening on %s:%d/health", host, port)
    except Exception as exc:
        logger.warning("Could not start health check server: %s", exc)


# ─── History summary builder ───

def _build_history_summary(history: list[dict], max_chars: int = 1500) -> str:
    """Build a compact conversation summary to append to the system prompt."""
    relevant = [
        m for m in history
        if m.get("role") in ("user", "assistant")
        and isinstance(m.get("content"), str)
        and m["content"].strip()
    ]
    if not relevant:
        return ""
    # Last 10 messages (5 turns) for meaningful architecture context
    recent = relevant[-10:]
    lines = ["Relevant prior conversation:"]
    total = 0
    for msg in recent:
        role = "User" if msg["role"] == "user" else "Assistant"
        snippet = msg["content"].strip().replace("\n", " ")[:250]
        line = f"- {role}: {snippet}"
        if total + len(line) > max_chars:
            break
        lines.append(line)
        total += len(line)
    return "\n".join(lines) if len(lines) > 1 else ""


def _build_file_context_summary(uploaded_files: list[dict], max_chars: int = 2000) -> str:
    """Build a file analysis summary for the voice system prompt."""
    analyzed = [f for f in uploaded_files if f.get("file_analysis")]
    if not analyzed:
        return ""

    lines = ["Uploaded file context:"]
    total = 0
    for f in analyzed:
        analysis = f["file_analysis"]
        name = f.get("file_name", "file")
        parts = [f"- {name}:"]
        if isinstance(analysis, dict):
            if analysis.get("summary"):
                parts.append(f"  Summary: {analysis['summary'][:200]}")
            for key in ("components", "technologies", "patterns", "data_flows"):
                items = analysis.get(key, [])
                if items and isinstance(items, list):
                    parts.append(f"  {key.replace('_', ' ').title()}: {', '.join(str(i) for i in items[:10])}")
            reqs = analysis.get("requirements")
            if isinstance(reqs, dict):
                for rtype in ("functional", "non_functional"):
                    r_list = reqs.get(rtype, [])
                    if r_list and isinstance(r_list, list):
                        parts.append(f"  {rtype.replace('_', ' ').title()} requirements: {', '.join(str(r) for r in r_list[:5])}")
            constraints = analysis.get("constraints", [])
            if constraints and isinstance(constraints, list):
                parts.append(f"  Constraints: {', '.join(str(c) for c in constraints[:5])}")
        else:
            parts.append(f"  {str(analysis)[:300]}")

        block = "\n".join(parts)
        if total + len(block) > max_chars:
            break
        lines.append(block)
        total += len(block)

    return "\n".join(lines) if len(lines) > 1 else ""


# ─── Nova Sonic → ArchFlow event translator ───

async def _handle_nova_events(websocket, stream_manager: S2sSessionManager, session_id: str | None, db_client: VoiceSessionDBClient, is_voice: bool = True):
    """
    Read raw Nova Sonic events from the output queue and translate them
    into ArchFlow WebSocket messages for the browser.

    Completion signals by model version:
      nova-sonic-v1:0   → promptEnd or sessionEnd
      nova-2-sonic-v1:0 → completionEnd

    We handle all three so the code works regardless of which model is running.
    """
    user_texts: list[str] = []
    assistant_texts: list[str] = []
    current_role: str | None = None
    has_audio: bool = False

    async def _send(payload: dict):
        try:
            await websocket.send(json.dumps(payload))
        except websockets.exceptions.ConnectionClosed:
            pass

    async def _flush_response():
        """Send the assembled ai_response + audio_end to the browser."""
        full_text = " ".join(assistant_texts).strip()
        transcription = " ".join(user_texts).strip()

        logger.info(
            "Flushing response — transcription=%d chars, response=%d chars, audio=%s, is_voice=%s",
            len(transcription), len(full_text), has_audio, is_voice,
        )

        response_msg = {
            "type": "ai_response",
            "payload": {
                "text": full_text or "(No text response received)",
                "agent": "architecture_advisor",
                "transcription": transcription,
                "hasAudio": has_audio,
            },
        }
        if session_id:
            response_msg["sessionId"] = session_id
        await _send(response_msg)

        if has_audio:
            await _send({"type": "audio_end"})

        if session_id and db_client and (transcription or full_text):
            try:
                await asyncio.to_thread(
                    db_client.append_voice_interaction,
                    session_id, transcription, full_text, is_voice,
                )
            except Exception as e:
                logger.error("Failed to save voice interaction to DB: %s", e)

    try:
        while True:
            # Once we have assistant text, use a short timeout on the queue so we
            # don't wait 59 seconds for audio that awscrt drops (cancelled-Future bug).
            # If promptEnd arrives before the timeout we proceed normally; otherwise
            # we flush the text response immediately and close.
            try:
                # Use a generous timeout (30s) matching the frontend's safety timeout.
                # The stream should end naturally via completionEnd/promptEnd/sessionEnd.
                # The old 5s timeout was killing streams while Nova was still generating audio.
                timeout = 30.0 if assistant_texts else None
                response = await asyncio.wait_for(
                    stream_manager.output_queue.get(), timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Queue timeout (30s) after assistant text — stream stalled, flushing"
                )
                await _flush_response()
                await stream_manager.close()
                break

            # Sentinel: stream ended
            if "_stream_ended" in response:
                err = response.get("_error")
                if err and "Invalid input" not in err and "Timed out" not in err:
                    logger.warning("Stream ended with error: %s", err)
                    await _send({"type": "error", "payload": {"message": f"Voice stream error: {err}"}})
                elif assistant_texts or user_texts:
                    # Stream closed while we had partial content — flush it
                    await _flush_response()
                break

            evt = response.get("event", {})
            event_type = list(evt.keys())[0] if evt else "unknown"
            logger.debug("Nova event: %s | role=%s", event_type, current_role)

            # ── Skip tool protocol events (internal to Nova Sonic) ──
            if "toolUse" in evt:
                logger.info("toolUse event — tool=%s (handled by session_manager)", evt["toolUse"].get("toolName"))
                continue

            if "toolResult" in evt:
                logger.debug("toolResult event (internal)")
                continue

            # ── Track role per content block ──
            if "contentStart" in evt:
                current_role = evt["contentStart"].get("role")
                content_type = evt["contentStart"].get("type")
                # Skip tool-related content blocks
                if content_type == "TOOL" or current_role == "TOOL":
                    logger.info("contentStart — type=TOOL (skipping)")
                    continue
                logger.info("contentStart — role=%s", current_role)

            # ── Text output ──
            elif "textOutput" in evt:
                text = evt["textOutput"].get("content", "")
                if current_role == "USER":
                    user_texts.append(text)
                    logger.info("Transcription chunk: %r", text[:80])
                    await _send({
                        "type": "voice_transcription",
                        "payload": {"text": " ".join(user_texts)},
                    })
                elif current_role == "ASSISTANT":
                    assistant_texts.append(text)
                    logger.info("Assistant text chunk: %r", text[:80])

            # ── Audio output — stream immediately, don't wait for completion ──
            elif "audioOutput" in evt:
                audio_b64 = evt["audioOutput"].get("content", "")
                if audio_b64:
                    has_audio = True
                    logger.debug("audioOutput chunk: %d chars base64", len(audio_b64))
                    await _send({
                        "type": "audio_chunk",
                        "payload": {"audio": audio_b64},
                    })

            elif "contentEnd" in evt:
                end_type = evt["contentEnd"].get("type")
                if end_type == "TOOL":
                    logger.info("contentEnd — type=TOOL (skipping)")
                    continue
                logger.info("contentEnd — role=%s", current_role)

            # ── Completion signals — any of these means the response is done ──

            elif "completionEnd" in evt:
                # nova-2-sonic-v1:0 sends this
                logger.info("completionEnd received")
                await _flush_response()
                prompt_name = stream_manager.prompt_name
                if prompt_name and stream_manager.is_active:
                    await stream_manager.send_raw_event(
                        {"event": {"promptEnd": {"promptName": prompt_name}}}
                    )
                if stream_manager.is_active:
                    await stream_manager.send_raw_event({"event": {"sessionEnd": {}}})
                await stream_manager.close()
                break

            elif "promptEnd" in evt:
                # nova-sonic-v1:0 sends this instead of completionEnd
                logger.info("promptEnd received — treating as completion")
                await _flush_response()
                await stream_manager.close()
                break

            elif "sessionEnd" in evt:
                logger.info("sessionEnd received from Bedrock")
                if assistant_texts or user_texts:
                    await _flush_response()
                await stream_manager.close()
                break

            else:
                logger.debug("Unhandled Nova event type: %s", event_type)

    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.error("Nova event handler error: %s", exc, exc_info=True)
        await _send({
            "type": "error",
            "payload": {"message": "Voice processing failed. Please try again."},
        })



# ─── Text-via-Sonic handler ───

async def _handle_text_via_sonic(
    websocket,
    text: str,
    session_id: str | None,
    current_diagram: str | None,
    region: str,
    db_client: VoiceSessionDBClient,
):
    """
    Process a text chat message through Nova Sonic's bidirectional stream.

    Opens a fresh stream, sends the system prompt + user text as cross-modal
    input, collects the text response (discards audio), and sends ai_response
    back to the browser.
    """
    import uuid as _uuid
    from .s2s_events import S2sEvent, ARCHFLOW_SYSTEM_PROMPT, ARCHFLOW_TOOL_CONFIG

    # Generate a sessionId if none was provided (first-ever message)
    if not session_id:
        session_id = str(_uuid.uuid4())
        logger.info("Text-via-sonic: created new session %s", session_id)
        try:
            await websocket.send(json.dumps({
                "type": "voice_session_started",
                "sessionId": session_id,
            }))
        except websockets.exceptions.ConnectionClosed:
            return

    stream_manager = S2sSessionManager(region=region)

    # Diagram callback — same as voice path
    async def _on_diagram(diagram_syntax: str):
        if session_id:
            await asyncio.to_thread(db_client.save_diagram, session_id, diagram_syntax)
        try:
            await websocket.send(json.dumps({
                "type": "diagram_update",
                "payload": {"diagram": diagram_syntax},
            }))
        except websockets.exceptions.ConnectionClosed:
            pass

    stream_manager.on_diagram_generated = _on_diagram

    try:
        await stream_manager.initialize_stream()
    except Exception as exc:
        logger.error("Failed to init Nova Sonic for text: %s", exc, exc_info=True)
        try:
            await websocket.send(json.dumps({
                "type": "error",
                "payload": {"message": f"Failed to connect to AI: {exc}"},
            }))
        except Exception:
            pass
        return

    prompt_name = str(_uuid.uuid4())

    # Collect responses via the nova event handler (is_voice=False for text chat)
    nova_task = asyncio.create_task(
        _handle_nova_events(websocket, stream_manager, session_id, db_client, is_voice=False)
    )

    try:
        # 1. sessionStart
        await stream_manager.send_raw_event(
            S2sEvent.session_start()
        )

        # 2. promptStart (with tool config, text + audio output config)
        await stream_manager.send_raw_event(
            S2sEvent.prompt_start(prompt_name, tool_config=ARCHFLOW_TOOL_CONFIG)
        )
        stream_manager.prompt_name = prompt_name

        # 3. System prompt (enriched with history + file context)
        system_content_name = str(_uuid.uuid4())
        system_prompt = ARCHFLOW_SYSTEM_PROMPT

        # For text chat, add more detailed output instructions
        system_prompt += (
            "\n\nIMPORTANT: The user is typing, not speaking. "
            "Give detailed, structured responses using markdown formatting. "
            "You can use longer responses with bullet points, headers, and code blocks since "
            "the user will read (not listen to) your response."
        )

        if current_diagram:
            system_prompt += f"\n\nCurrent architecture diagram:\n{current_diagram}"
            stream_manager.current_diagram = current_diagram

        # Inject session history + file context
        if session_id:
            try:
                history, uploaded_files = await asyncio.gather(
                    asyncio.to_thread(db_client.get_session_history, session_id),
                    asyncio.to_thread(db_client.get_uploaded_files, session_id),
                )
                summary = _build_history_summary(history)
                file_summary = _build_file_context_summary(uploaded_files)
                if summary:
                    stream_manager.conversation_history = summary
                enrichment = "\n\n".join(filter(None, [summary, file_summary]))
                if enrichment:
                    system_prompt += "\n\n" + enrichment
                    logger.info(
                        "Injected %d chars of context into text-via-sonic prompt",
                        len(enrichment),
                    )
            except Exception as e:
                logger.error("Failed to inject context for text-via-sonic: %s", e)

        await stream_manager.send_raw_event(
            S2sEvent.content_start_text(prompt_name, system_content_name)
        )
        await stream_manager.send_raw_event(
            S2sEvent.text_input(prompt_name, system_content_name, system_prompt)
        )
        await stream_manager.send_raw_event(
            S2sEvent.content_end(prompt_name, system_content_name)
        )

        # 4. Save user message to DynamoDB BEFORE sending to Sonic
        #    (so history is visible to both voice and text sessions)
        if session_id:
            try:
                await asyncio.to_thread(
                    db_client.append_voice_interaction,
                    session_id, text, "", False,
                )
            except Exception as e:
                logger.error("Failed to save user text message to DB: %s", e)

        # 5. User text message (cross-modal text input)
        user_content_name = str(_uuid.uuid4())
        await stream_manager.send_raw_event(
            S2sEvent.content_start_user_text(prompt_name, user_content_name)
        )
        await stream_manager.send_raw_event(
            S2sEvent.text_input(prompt_name, user_content_name, text)
        )
        await stream_manager.send_raw_event(
            S2sEvent.content_end(prompt_name, user_content_name)
        )

        # 6. Send a brief silence audio block to trigger Sonic's turn detection.
        #    Cross-modal text input requires an active audio stream — without this,
        #    Sonic waits indefinitely for audio and times out after 55 seconds.
        import base64
        audio_content_name = str(_uuid.uuid4())
        # 200ms of silence at 16kHz, 16-bit mono = 6400 bytes
        silence = base64.b64encode(b'\x00' * 6400).decode('utf-8')
        await stream_manager.send_raw_event(
            S2sEvent.content_start_audio(prompt_name, audio_content_name)
        )
        await stream_manager.send_raw_event(
            S2sEvent.audio_input(prompt_name, audio_content_name, silence)
        )
        await stream_manager.send_raw_event(
            S2sEvent.content_end(prompt_name, audio_content_name)
        )

        logger.info(
            "Text-via-sonic: sent user message (%d chars) + silence for session %s",
            len(text), session_id,
        )

        # 5. Wait for Nova to finish (completionEnd → flush → cleanup)
        try:
            await asyncio.wait_for(nova_task, timeout=60.0)
        except asyncio.TimeoutError:
            logger.error("Text-via-sonic: response timed out after 60s")
            nova_task.cancel()
            try:
                await websocket.send(json.dumps({
                    "type": "error",
                    "payload": {"message": "Response timed out. Please try again."},
                }))
            except Exception:
                pass

    except Exception as exc:
        logger.error("Text-via-sonic error: %s", exc, exc_info=True)
        try:
            await websocket.send(json.dumps({
                "type": "error",
                "payload": {"message": "Failed to process text message. Please try again."},
            }))
        except Exception:
            pass
    finally:
        await stream_manager.close()


# ─── WebSocket handler ───

async def _websocket_handler(websocket):
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    stream_manager: S2sSessionManager | None = None
    nova_task: asyncio.Task | None = None
    session_id: str | None = None
    system_content_name: str | None = None
    
    # Initialize DB client safely within handler
    db_client = VoiceSessionDBClient(region_name=region)

    logger.info("New WebSocket connection from %s", websocket.remote_address)

    async def _cleanup():
        nonlocal stream_manager, nova_task
        if nova_task and not nova_task.done():
            nova_task.cancel()
            try:
                await nova_task
            except asyncio.CancelledError:
                pass
            nova_task = None
        if stream_manager:
            await stream_manager.close()
            stream_manager = None

    try:
        async for raw_message in websocket:
            try:
                data = json.loads(raw_message)
                if "body" in data:
                    data = json.loads(data["body"])
                if "event" not in data:
                    continue

                event_type = list(data["event"].keys())[0]
                logger.debug("Received event: %s", event_type)

                # ── text_message: text chat routed through Sonic ──
                if event_type == "text_message":
                    tm = data["event"]["text_message"]
                    tm_text = tm.get("text", "")
                    tm_session = tm.get("sessionId") or session_id
                    tm_diagram = tm.get("currentDiagram")
                    if tm_text:
                        logger.info(
                            "text_message received (%d chars, session=%s)",
                            len(tm_text), tm_session,
                        )
                        # Run in a separate task so it doesn't block voice events
                        asyncio.create_task(
                            _handle_text_via_sonic(
                                websocket, tm_text, tm_session,
                                tm_diagram, region, db_client,
                            )
                        )
                    continue

                # ── sessionStart: open a new Nova Sonic stream ──
                if event_type == "sessionStart":
                    await _cleanup()  # clean up any previous session

                    # Extract sessionId if provided by frontend
                    session_id = data["event"]["sessionStart"].get("sessionId")

                    logger.info("sessionStart — initialising Nova Sonic stream (region=%s, session_id=%s)", region, session_id)
                    stream_manager = S2sSessionManager(region=region)
                    # Set up diagram callback before initializing
                    async def _on_diagram(diagram_syntax: str):
                        if session_id:
                            await asyncio.to_thread(db_client.save_diagram, session_id, diagram_syntax)
                        try:
                            await websocket.send(json.dumps({
                                "type": "diagram_update",
                                "payload": {"diagram": diagram_syntax},
                            }))
                        except websockets.exceptions.ConnectionClosed:
                            pass

                    stream_manager.on_diagram_generated = _on_diagram

                    try:
                        await stream_manager.initialize_stream()
                        # Start the translator task
                        nova_task = asyncio.create_task(
                            _handle_nova_events(websocket, stream_manager, session_id, db_client)
                        )
                        logger.info("Nova Sonic stream ready")
                    except Exception as exc:
                        logger.error("Failed to init Nova Sonic: %s", exc, exc_info=True)
                        try:
                            await websocket.send(json.dumps({
                                "type": "error",
                                "payload": {"message": f"Failed to connect to voice AI: {exc}"},
                            }))
                        except Exception:
                            pass
                        stream_manager = None
                        continue

                    # Forward sessionStart to Bedrock (strip non-protocol sessionId field)
                    forwarded = dict(data)
                    forwarded["event"] = dict(data["event"])
                    forwarded["event"]["sessionStart"] = {
                        k: v for k, v in data["event"]["sessionStart"].items()
                        if k != "sessionId"
                    }
                    await stream_manager.send_raw_event(forwarded)

                # ── sessionEnd from BROWSER: forward then cleanup ──
                # (In normal flow the server closes the session after completionEnd.
                #  sessionEnd from browser is treated as a hard stop / page close.)
                elif event_type == "sessionEnd":
                    if stream_manager and stream_manager.is_active:
                        await stream_manager.send_raw_event(data)
                    await _cleanup()

                # ── All other events: forward when a live stream exists ──
                elif stream_manager and stream_manager.is_active:
                    if event_type == "promptStart":
                        stream_manager.prompt_name = data["event"]["promptStart"]["promptName"]
                        await stream_manager.send_raw_event(data)

                    elif event_type == "contentStart":
                        content_type = data["event"]["contentStart"].get("type")
                        role = data["event"]["contentStart"].get("role")
                        if content_type == "AUDIO":
                            stream_manager.audio_content_name = (
                                data["event"]["contentStart"]["contentName"]
                            )
                        if role == "SYSTEM":
                            system_content_name = data["event"]["contentStart"]["contentName"]
                        await stream_manager.send_raw_event(data)

                    elif event_type == "audioInput":
                        prompt_name = data["event"]["audioInput"]["promptName"]
                        content_name = data["event"]["audioInput"]["contentName"]
                        audio_b64 = data["event"]["audioInput"]["content"]
                        stream_manager.add_audio_chunk(prompt_name, content_name, audio_b64)

                    elif event_type == "textInput":
                        content = data["event"]["textInput"].get("content", "")
                        content_name = data["event"]["textInput"].get("contentName", "")
                        # Extract current diagram from system prompt if present
                        if "Current architecture diagram:" in content:
                            stream_manager.current_diagram = content.split(
                                "Current architecture diagram:\n", 1
                            )[-1].strip()
                            logger.info("Extracted current diagram context (%d chars)", len(stream_manager.current_diagram))
                        # If this is the system prompt block and we have a session, enrich with history
                        if system_content_name and content_name == system_content_name and session_id:
                            try:
                                history, uploaded_files = await asyncio.gather(
                                    asyncio.to_thread(db_client.get_session_history, session_id),
                                    asyncio.to_thread(db_client.get_uploaded_files, session_id),
                                )
                                summary = _build_history_summary(history)
                                file_summary = _build_file_context_summary(uploaded_files)
                                # Store history on stream manager so DiagramTool can use it
                                if summary:
                                    stream_manager.conversation_history = summary
                                enrichment = "\n\n".join(filter(None, [summary, file_summary]))
                                if enrichment:
                                    enriched = dict(data)
                                    enriched["event"] = dict(data["event"])
                                    enriched["event"]["textInput"] = dict(data["event"]["textInput"])
                                    enriched["event"]["textInput"]["content"] = content + "\n\n" + enrichment
                                    logger.info("Injecting context (%d chars) into system prompt for session %s", len(enrichment), session_id)
                                    await stream_manager.send_raw_event(enriched)
                                else:
                                    logger.info(
                                        "No enrichment context for session %s (history=%d msgs, files=%d)",
                                        session_id, len(history), len(uploaded_files),
                                    )
                                    await stream_manager.send_raw_event(data)
                            except Exception as e:
                                logger.error("Failed to inject context into system prompt: %s", e, exc_info=True)
                                await stream_manager.send_raw_event(data)
                        else:
                            await stream_manager.send_raw_event(data)

                    elif event_type == "contentEnd":
                        await stream_manager.send_raw_event(data)

                    else:
                        await stream_manager.send_raw_event(data)

            except json.JSONDecodeError:
                logger.warning("Non-JSON WebSocket message received")
            except Exception as exc:
                logger.error("Error processing message: %s", exc, exc_info=True)

    except websockets.exceptions.ConnectionClosed:
        logger.info("WebSocket connection closed")
    finally:
        await _cleanup()


# ─── Entry point ───

async def _main(host: str, port: int, health_port: int | None, profile: str | None):
    _bootstrap_aws_credentials(profile=profile)
    if health_port:
        _start_health_server(host, health_port)

    async with websockets.serve(_websocket_handler, host, port):
        logger.info("ArchFlow voice server listening on ws://%s:%d", host, port)
        await asyncio.Future()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ArchFlow Voice WebSocket Server")
    parser.add_argument("--host", default=os.environ.get("HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("WS_PORT", "8081")))
    parser.add_argument("--health-port", type=int, default=None)
    parser.add_argument("--profile", default=os.environ.get("AWS_PROFILE"))
    args = parser.parse_args()

    try:
        asyncio.run(_main(args.host, args.port, args.health_port, args.profile))
    except KeyboardInterrupt:
        logger.info("Voice server stopped")
