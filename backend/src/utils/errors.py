class ArchFlowError(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, user_message: str | None = None):
        self.message = message
        self.user_message = user_message or "An error occurred. Please try again."
        super().__init__(self.message)


class BedrockThrottlingError(ArchFlowError):
    """Raised when Bedrock API rate limit is hit."""

    def __init__(self):
        super().__init__(
            "Bedrock API rate limit exceeded",
            "Too many requests. Please wait a moment and try again.",
        )


class SessionExpiredError(ArchFlowError):
    """Raised when user session has expired."""

    def __init__(self):
        super().__init__(
            "Session expired",
            "Your session has expired. Please start a new conversation.",
        )


class SessionNotFoundError(ArchFlowError):
    """Raised when session ID is not found."""

    def __init__(self, session_id: str):
        super().__init__(
            f"Session {session_id} not found",
            "Session not found. Please start a new conversation.",
        )


class InvalidMermaidSyntaxError(ArchFlowError):
    """Raised when generated Mermaid syntax is invalid."""

    def __init__(self, details: str = ""):
        super().__init__(
            f"Invalid Mermaid syntax: {details}",
            "The diagram syntax is invalid. Attempting to fix...",
        )


class FileUploadError(ArchFlowError):
    """Raised when file upload fails."""

    def __init__(self, details: str = ""):
        super().__init__(
            f"File upload failed: {details}",
            "File upload failed. Please try again.",
        )


class WebSocketDisconnectedError(ArchFlowError):
    """Raised when WebSocket connection is lost."""

    def __init__(self):
        super().__init__(
            "WebSocket connection lost",
            "Connection lost. Reconnecting...",
        )
