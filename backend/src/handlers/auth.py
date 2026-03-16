import json

from src.services.auth_service import AuthService
from src.utils import logger

auth_service = AuthService()

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Content-Type": "application/json",
}


def lambda_handler(event, context):
    path = event.get("path", "")
    http_method = event.get("httpMethod", "")

    # Handle CORS preflight
    if http_method == "OPTIONS":
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

    try:
        body = json.loads(event.get("body", "{}") or "{}")

        if path.endswith("/auth/signup"):
            result = auth_service.signup(
                body.get("email", ""), body.get("password", "")
            )
            return _response(200, result)

        elif path.endswith("/auth/login"):
            result = auth_service.login(
                body.get("email", ""), body.get("password", "")
            )
            return _response(200, result)

        elif path.endswith("/auth/me"):
            token = _extract_token(event)
            user_info = auth_service.verify_token(token)
            return _response(200, user_info)

        return _response(404, {"error": "Not found"})

    except ValueError as e:
        return _response(401, {"error": str(e)})
    except Exception:
        logger.exception("Auth handler error")
        return _response(500, {"error": "Internal server error"})


def _extract_token(event: dict) -> str:
    headers = event.get("headers") or {}
    # API Gateway may lowercase header keys
    auth = headers.get("Authorization") or headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    raise ValueError("Missing authorization token")


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body),
    }
