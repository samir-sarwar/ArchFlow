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


def validate_file_type(content_type: str) -> bool:
    return content_type in ALLOWED_FILE_TYPES


def validate_file_size(size_bytes: int) -> bool:
    return 0 < size_bytes <= MAX_FILE_SIZE_BYTES
