import re

MAX_MESSAGE_LENGTH = 10000
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
ALLOWED_FILE_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "image/png",
    "image/jpeg",
    "audio/webm",
    "audio/ogg",
    "audio/mp4",
}
SESSION_ID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def validate_session_id(session_id: str) -> bool:
    return bool(SESSION_ID_PATTERN.match(session_id))


def validate_message(message: str) -> bool:
    return 0 < len(message.strip()) <= MAX_MESSAGE_LENGTH


def validate_file_type(content_type: str) -> bool:
    return content_type in ALLOWED_FILE_TYPES


def validate_file_size(size_bytes: int) -> bool:
    return 0 < size_bytes <= MAX_FILE_SIZE_BYTES
