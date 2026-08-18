from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ToolDefinition:
    name: str
    description: str
    function: Callable[..., Any]
    risk: str = "low"

    def schema(self) -> Dict[str, Any]:
        sig = inspect.signature(self.function)
        properties: Dict[str, Any] = {}
        required: List[str] = []

        for param_name, param in sig.parameters.items():
            annotation = param.annotation
            json_type = "string"

            if annotation in (int, "int"):
                json_type = "integer"
            elif annotation in (float, "float"):
                json_type = "number"
            elif annotation in (bool, "bool"):
                json_type = "boolean"

            properties[param_name] = {"type": json_type}

            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        return {
            "name": self.name,
            "description": self.description,
            "risk": self.risk,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        }


_REGISTRY: Dict[str, ToolDefinition] = {}


def register_tool(
    function: Callable[..., Any],
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    risk: str = "low",
) -> Callable[..., Any]:
    tool_name = name or function.__name__
    tool_description = description or (inspect.getdoc(function) or "")

    _REGISTRY[tool_name] = ToolDefinition(
        name=tool_name,
        description=tool_description,
        function=function,
        risk=risk,
    )
    return function


def tool(*, name: Optional[str] = None, description: Optional[str] = None, risk: str = "low"):
    def decorator(function: Callable[..., Any]) -> Callable[..., Any]:
        return register_tool(
            function,
            name=name,
            description=description,
            risk=risk,
        )
    return decorator


def get_tool(name: str) -> Optional[ToolDefinition]:
    return _REGISTRY.get(name)


def list_tools() -> Dict[str, ToolDefinition]:
    return dict(_REGISTRY)


def tool_schemas() -> List[Dict[str, Any]]:
    return [definition.schema() for definition in _REGISTRY.values()]
