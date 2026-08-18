from __future__ import annotations

from typing import Any

from core.types import ToolCall, ToolResult
from tools.registry import get_tool


class ToolExecutor:
    def execute(self, call: ToolCall) -> ToolResult:
        definition = get_tool(call.name)

        if definition is None:
            return ToolResult(
                success=False,
                tool=call.name,
                error=f"Unknown tool: {call.name}",
                message=f"Tool '{call.name}' is not registered.",
            )

        try:
            raw: Any = definition.function(**call.arguments)

            # Preserve your existing tools that already return dictionaries.
            if isinstance(raw, dict) and "success" in raw:
                return ToolResult(
                    success=bool(raw.get("success")),
                    tool=str(raw.get("tool", call.name)),
                    data=raw.get("data"),
                    message=str(raw.get("message", "")),
                    error=raw.get("error"),
                )

            return ToolResult(
                success=True,
                tool=call.name,
                data=raw,
                message=str(raw) if raw is not None else "",
            )

        except TypeError as exc:
            return ToolResult(
                success=False,
                tool=call.name,
                error=f"Invalid arguments: {exc}",
                message=f"Could not execute '{call.name}' because its arguments were invalid.",
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                tool=call.name,
                error=f"{type(exc).__name__}: {exc}",
                message=f"Tool '{call.name}' failed.",
            )
