from __future__ import annotations

import ast
import importlib
import inspect
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ToolDefinition:
    name: str
    description: str
    function: Callable[..., Any]
    risk: str = "low"

    # Backward compatibility with the old dict-based registry.
    # Existing code such as workstation/app.py can continue using:
    # metadata.get("description", "")
    def get(self, key: str, default=None):
        return getattr(self, key, default)

    def __getitem__(self, key: str):
        return getattr(self, key)

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

_AUTOLOAD_DONE = False
_AUTOLOADING = False

LEGACY_TOOLS = {
    "close_application",
    "forget",
    "open_application",
    "open_file",
    "open_folder",
    "recall",
    "remember",
    "search_files",
    "show_memory",
}


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


def tool(
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    risk: str = "low",
):
    def decorator(function: Callable[..., Any]) -> Callable[..., Any]:
        return register_tool(
            function,
            name=name,
            description=description,
            risk=risk,
        )

    return decorator


def _module_name_from_path(project_root: Path, path: Path) -> Optional[str]:
    try:
        relative = path.relative_to(project_root)
    except ValueError:
        return None

    parts = list(relative.with_suffix("").parts)

    if not parts:
        return None

    # Ignore modules that cannot be imported normally.
    if any(not part.isidentifier() for part in parts):
        return None

    if parts[-1] == "__init__":
        parts = parts[:-1]

    if not parts:
        return None

    return ".".join(parts)


def _contains_target_function(path: Path, missing: set[str]) -> set[str]:
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source, filename=str(path))
    except Exception:
        return set()

    found = set()

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in missing:
                found.add(node.name)

    return found


def _autoload_legacy_tools() -> None:
    global _AUTOLOAD_DONE, _AUTOLOADING

    if _AUTOLOAD_DONE or _AUTOLOADING:
        return

    _AUTOLOADING = True

    try:
        # ----------------------------------------------------------
        # Load Phase-1 registered tools.
        # Importing this module executes its @tool decorators.
        # ----------------------------------------------------------
        try:
            importlib.import_module("tools.computer_phase1")
        except Exception as exc:
            print(
                "[REGISTRY WARNING] Could not load "
                f"tools.computer_phase1: {type(exc).__name__}: {exc}"
            )

        # ----------------------------------------------------------
        # Load original mature Jarvis tools.
        # ----------------------------------------------------------
        module_map = {
            "close_application": "tools.computer",
            "open_application": "tools.computer",
            "open_file": "tools.computer",
            "open_folder": "tools.computer",
            "search_files": "tools.computer",

            "forget": "tools.memory",
            "recall": "tools.memory",
            "remember": "tools.memory",
            "show_memory": "tools.memory",
        }

        loaded_modules = {}

        for tool_name, module_name in module_map.items():

            if tool_name in _REGISTRY:
                continue

            try:
                module = loaded_modules.get(module_name)

                if module is None:
                    module = importlib.import_module(module_name)
                    loaded_modules[module_name] = module

                candidate = getattr(module, tool_name, None)

                if callable(candidate):
                    register_tool(
                        candidate,
                        name=tool_name,
                        description=inspect.getdoc(candidate) or "",
                        risk="low",
                    )

            except Exception as exc:
                print(
                    f"[REGISTRY WARNING] Could not load {tool_name}: "
                    f"{type(exc).__name__}: {exc}"
                )

        _AUTOLOAD_DONE = True

    finally:
        _AUTOLOADING = False
def get_tool(name: str) -> Optional[ToolDefinition]:
    if name not in _REGISTRY:
        _autoload_legacy_tools()

    return _REGISTRY.get(name)


def list_tools() -> Dict[str, ToolDefinition]:
    _autoload_legacy_tools()
    return dict(_REGISTRY)


def tool_schemas() -> List[Dict[str, Any]]:
    _autoload_legacy_tools()
    return [
        definition.schema()
        for definition in _REGISTRY.values()
    ]
