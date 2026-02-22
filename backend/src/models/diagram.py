from enum import Enum
from typing import Optional

from pydantic import BaseModel


class DiagramType(str, Enum):
    FLOWCHART = "flowchart"
    SEQUENCE = "sequence"
    ER = "er"
    C4_CONTEXT = "c4_context"
    C4_CONTAINER = "c4_container"
    C4_COMPONENT = "c4_component"


class DiagramState(BaseModel):
    syntax: str
    diagram_type: DiagramType = DiagramType.FLOWCHART
    is_valid: bool = True
    error_message: Optional[str] = None
    node_count: int = 0
