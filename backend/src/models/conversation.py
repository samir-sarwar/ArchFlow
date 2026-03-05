from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: str  # "user" | "assistant"
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    agent: Optional[str] = None  # Which agent responded
    isVoice: Optional[bool] = None  # Indicates if message came from voice


class DiagramVersion(BaseModel):
    version: int
    syntax: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    description: Optional[str] = None


class ConversationContext(BaseModel):
    session_id: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    last_activity: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    messages: List[Message] = Field(default_factory=list)
    current_diagram: Optional[str] = None
    diagram_versions: List[DiagramVersion] = Field(default_factory=list)
    uploaded_files: List[Dict] = Field(default_factory=list)
    metadata: Dict = Field(default_factory=lambda: {
        "requirements": {},
        "architecture_decisions": [],
    })
