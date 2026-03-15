"""
Nova Lite triage agent for text messages in the voice server.

Classifies incoming text requests and either handles them directly via
Nova Lite (fast/cheap) or defers to Nova Sonic (for diagram generation
that requires tool use).
"""

import asyncio
import json
import logging
import os

import boto3
import websockets

from .db_client import VoiceSessionDBClient

logger = logging.getLogger(__name__)

MODEL_LITE = os.environ.get("BEDROCK_MODEL_LITE", "us.amazon.nova-2-lite-v1:0")

TRIAGE_PROMPT = """You are a request classifier for an architecture diagramming tool.

Classify the user's message as either "lite" or "sonic":

- "sonic" — The user wants to CREATE, MODIFY, VISUALIZE, or DRAW a diagram or architecture.
  Keywords: "create", "build", "design", "draw", "diagram", "visualize", "show me", "add X to the diagram", "update the diagram", "modify the architecture".

- "lite" — Everything else: greetings, architecture advice questions, trade-off analysis, clarification questions, general chat, recalling previous conversation, asking about uploaded files.

Respond with ONLY "lite" or "sonic", nothing else."""

LITE_SYSTEM_PROMPT = (
    "You are ArchFlow, an expert AI software architect. "
    "You help users design software system architecture through natural conversation. "
    "Give detailed, structured responses using markdown formatting. "
    "You can use bullet points, headers, and code blocks since the user will read your response. "
    "Keep responses focused and under 300 words unless the topic requires more depth."
)


async def classify_text_complexity(
    text: str,
    session_id: str | None,
    region: str,
    db_client: VoiceSessionDBClient,
) -> str:
    """Classify text as 'lite' (Nova Lite can handle) or 'sonic' (needs Nova Sonic).

    Uses a quick Nova Lite call with low token budget for fast classification.
    """
    client = boto3.client("bedrock-runtime", region_name=region)

    # Include recent history for context
    history_hint = ""
    if session_id:
        try:
            history = await asyncio.to_thread(db_client.get_session_history, session_id)
            recent = [
                m for m in (history or [])[-4:]
                if m.get("role") in ("user", "assistant")
                and isinstance(m.get("content"), str)
                and m["content"].strip()
            ]
            if recent:
                lines = [
                    f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content'].strip()[:150]}"
                    for m in recent
                ]
                history_hint = "Recent conversation:\n" + "\n".join(lines) + "\n\n"
        except Exception as e:
            logger.warning("Triage: failed to fetch history: %s", e)

    prompt = f"{history_hint}User message to classify: {text}"

    try:
        response = await asyncio.to_thread(
            client.converse,
            modelId=MODEL_LITE,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            system=[{"text": TRIAGE_PROMPT}],
            inferenceConfig={"maxTokens": 32, "temperature": 0.1},
        )
        result = response["output"]["message"]["content"][0]["text"].strip().lower()
        classification = "sonic" if "sonic" in result else "lite"
        logger.info("Triage classification: %r -> %s", text[:80], classification)
        return classification
    except Exception as e:
        logger.error("Triage classification failed, defaulting to sonic: %s", e)
        return "sonic"


async def handle_text_via_lite(
    websocket,
    text: str,
    session_id: str | None,
    current_diagram: str | None,
    region: str,
    db_client: VoiceSessionDBClient,
    build_history_summary,
    build_file_context_summary,
    wait_for_analyses=None,
):
    """Process a text message using Nova Lite Converse API (fast path).

    Sends response in the same ai_response format as the Sonic path so the
    frontend needs no changes.
    """
    import uuid as _uuid

    # Generate a sessionId if none was provided
    if not session_id:
        session_id = str(_uuid.uuid4())
        logger.info("Text-via-lite: created new session %s", session_id)
        try:
            await websocket.send(json.dumps({
                "type": "voice_session_started",
                "sessionId": session_id,
            }))
        except websockets.exceptions.ConnectionClosed:
            return

    client = boto3.client("bedrock-runtime", region_name=region)

    # Build system prompt with context
    system_prompt = LITE_SYSTEM_PROMPT

    if current_diagram:
        system_prompt += f"\n\nCurrent architecture diagram:\n{current_diagram}"

    # Inject conversation history + file context
    if session_id:
        try:
            if wait_for_analyses:
                history, uploaded_files = await asyncio.gather(
                    asyncio.to_thread(db_client.get_session_history, session_id),
                    wait_for_analyses(db_client, session_id, region),
                )
            else:
                history, uploaded_files = await asyncio.gather(
                    asyncio.to_thread(db_client.get_session_history, session_id),
                    asyncio.to_thread(db_client.get_uploaded_files, session_id),
                )
            summary = build_history_summary(history)
            file_summary = build_file_context_summary(uploaded_files)
            enrichment = "\n\n".join(filter(None, [summary, file_summary]))
            if enrichment:
                system_prompt += "\n\n" + enrichment
                logger.info(
                    "Injected %d chars of context into text-via-lite prompt",
                    len(enrichment),
                )
        except Exception as e:
            logger.error("Failed to inject context for text-via-lite: %s", e)

    # Save user message to DynamoDB before calling the model
    if session_id:
        try:
            await asyncio.to_thread(
                db_client.append_voice_interaction,
                session_id, text, "", False,
            )
        except Exception as e:
            logger.error("Failed to save user text message to DB: %s", e)

    # Call Nova Lite
    try:
        response = await asyncio.to_thread(
            client.converse,
            modelId=MODEL_LITE,
            messages=[{"role": "user", "content": [{"text": text}]}],
            system=[{"text": system_prompt}],
            inferenceConfig={"maxTokens": 4096, "topP": 0.9, "temperature": 0.7},
        )
        response_text = response["output"]["message"]["content"][0]["text"]
    except Exception as e:
        logger.error("Nova Lite converse failed: %s", e, exc_info=True)
        try:
            await websocket.send(json.dumps({
                "type": "error",
                "payload": {"message": f"Failed to get AI response: {e}"},
            }))
        except Exception:
            pass
        return

    logger.info("Text-via-lite response: %d chars", len(response_text))

    # Send response in the same format as the Sonic path
    response_msg = {
        "type": "ai_response",
        "payload": {
            "text": response_text or "(No response received)",
            "agent": "architecture_advisor",
            "transcription": "",
            "hasAudio": False,
        },
    }
    if session_id:
        response_msg["sessionId"] = session_id

    try:
        await websocket.send(json.dumps(response_msg))
    except websockets.exceptions.ConnectionClosed:
        pass

    # Save assistant response to DynamoDB
    if session_id:
        try:
            await asyncio.to_thread(
                db_client.append_voice_interaction,
                session_id, "", response_text, False,
            )
        except Exception as e:
            logger.error("Failed to save lite response to DB: %s", e)
