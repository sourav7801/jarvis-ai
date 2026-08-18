from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolCall:
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    success: bool
    tool: str
    data: Any = None
    message: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "tool": self.tool,
            "data": self.data,
            "message": self.message,
            "error": self.error,
        }


@dataclass
class AgentDecision:
    kind: str  # "tool_call" | "final"
    tool_call: Optional[ToolCall] = None
    final_text: Optional[str] = None
    raw: Any = None


@dataclass
class ConversationMessage:
    role: str
    content: str


@dataclass
class AgentState:
    messages: List[ConversationMessage] = field(default_factory=list)
    steps: int = 0
