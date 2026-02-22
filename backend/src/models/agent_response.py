from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel


class IntentType(str, Enum):
    CLARIFICATION_NEEDED = "clarification_needed"
    ARCHITECTURE_ADVICE = "architecture_advice"
    MODIFY_DIAGRAM = "modify_diagram"
    ANALYZE_CONTEXT = "analyze_context"
    MULTI_AGENT = "multi_agent"
    GENERAL = "general"


class AgentResponse(BaseModel):
    text: str
    agent_used: str
    diagram_update: Optional[str] = None
    metadata: Dict = {}
