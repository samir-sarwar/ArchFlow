import json

from src.services.file_processor import FileProcessor
from src.utils import logger
from src.utils.validators import validate_file_type, validate_file_size

file_processor = FileProcessor()


def lambda_handler(event, context):
    """Handle file upload requests and generate presigned URLs."""
    logger.info("File upload event received")

    try:
        body = json.loads(event.get("body", "{}"))
        session_id = body.get("sessionId")
        file_name = body.get("fileName")
        content_type = body.get("contentType")
        file_size = body.get("fileSize", 0)

        if not all([session_id, file_name, content_type]):
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing required fields"}),
            }

        if not validate_file_type(content_type):
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f"Unsupported file type: {content_type}"}),
            }

        if not validate_file_size(file_size):
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "File too large (max 10MB)"}),
            }

        file_key = f"{session_id}/{file_name}"
        upload_url = file_processor.generate_presigned_upload_url(file_key, content_type)

        return {
            "statusCode": 200,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({
                "uploadUrl": upload_url,
                "fileKey": file_key,
            }),
        }

    except Exception as e:
        logger.error("File upload error", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }
