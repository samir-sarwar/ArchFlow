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
from src.utils import logger

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
    """Handle incoming WebSocket messages."""
    body = json.loads(event.get("body", "{}"))
    action = body.get("action", "message")
    session_id = body.get("sessionId")
    text = body.get("text", "")

    logger.info(
        "WebSocket message",
        extra={"connection_id": connection_id, "action": action},
    )

    if not text:
        _send_to_client(connection_id, {
            "type": "error",
            "payload": {"message": "No text provided."},
        })
        return {"statusCode": 400}

    loop = asyncio.new_event_loop()
    try:
        response = loop.run_until_complete(
            _process_message(session_id, text)
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


async def _process_message(session_id: str | None, text: str) -> dict:
    """Process a user message through the orchestrator."""
    # Get or create session
    if session_id:
        context = await state_manager.get_session(session_id)
    else:
        session_id = await state_manager.create_session()
        context = await state_manager.get_session(session_id)

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
