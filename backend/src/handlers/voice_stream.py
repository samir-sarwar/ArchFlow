import json

from src.utils import logger


def lambda_handler(event, context):
    """Handle voice streaming input."""
    logger.info("Voice stream event received")

    try:
        body = json.loads(event.get("body", "{}"))
        session_id = body.get("sessionId")
        audio_data = body.get("audio")

        if not session_id or not audio_data:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing sessionId or audio data"}),
            }

        # TODO: Process voice stream via Nova 2 Sonic
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Voice stream processed"}),
        }

    except Exception as e:
        logger.error("Voice stream error", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }
