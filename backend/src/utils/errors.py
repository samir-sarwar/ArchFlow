class ArchFlowError(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, user_message: str | None = None):
        self.message = message
        self.user_message = user_message or "An error occurred. Please try again."
        super().__init__(self.message)


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
