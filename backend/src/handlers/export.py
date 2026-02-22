import json

from src.services.state_manager import ConversationStateManager
from src.utils import logger

state_manager = ConversationStateManager()


def lambda_handler(event, context):
    """Handle diagram export and share link generation."""
    logger.info("Export event received")

    try:
        path = event.get("path", "")
        body = json.loads(event.get("body", "{}"))
        session_id = body.get("sessionId")

        if not session_id:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing sessionId"}),
            }

        if path.endswith("/share"):
            return handle_share(session_id, body)
        else:
            return handle_export(session_id, body)

    except Exception as e:
        logger.error("Export error", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }


def handle_export(session_id: str, body: dict) -> dict:
    """Generate diagram export in requested format."""
    export_format = body.get("format", "mermaid")
    # TODO: Implement PNG/SVG/Mermaid export
    return {
        "statusCode": 200,
        "headers": {"Access-Control-Allow-Origin": "*"},
        "body": json.dumps({"message": f"Export as {export_format}"}),
    }


def handle_share(session_id: str, body: dict) -> dict:
    """Generate a shareable link for the diagram."""
    # TODO: Create share record and return URL
    return {
        "statusCode": 200,
        "headers": {"Access-Control-Allow-Origin": "*"},
        "body": json.dumps({"message": "Share link generated"}),
    }
