from __future__ import annotations

import threading
from dataclasses import asdict, dataclass
from typing import Any, Callable


IndicatorFunction = Callable[[list[dict[str, Any]]], Any]


@dataclass(frozen=True)
class IndicatorPlugin:
    name: str
    version: str
    description: str
    source: str
    proprietary: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class IndicatorPluginRegistry:
    """Safe in-process registry for verified indicator implementations.

    The registry does not execute arbitrary formula strings or remote code. A
    plugin must provide a callable implementation explicitly. This lets JARVIS
    support proprietary/custom indicators without inventing their formulas.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._metadata: dict[str, IndicatorPlugin] = {}
        self._functions: dict[str, IndicatorFunction] = {}

    def register(
        self,
        *,
        name: str,
        function: IndicatorFunction,
        version: str = "1",
        description: str = "",
        source: str = "LOCAL_VERIFIED_IMPLEMENTATION",
        proprietary: bool = False,
        replace: bool = False,
    ) -> dict[str, Any]:
        key = str(name or "").strip().upper()
        if not key:
            raise ValueError("Indicator name is required")
        if not callable(function):
            raise TypeError("Indicator implementation must be callable")
        with self._lock:
            if key in self._functions and not replace:
                raise ValueError(f"Indicator already registered: {key}")
            plugin = IndicatorPlugin(
                name=key,
                version=str(version or "1"),
                description=str(description or ""),
                source=str(source or "LOCAL_VERIFIED_IMPLEMENTATION"),
                proprietary=bool(proprietary),
            )
            self._metadata[key] = plugin
            self._functions[key] = function
        return {"success": True, "plugin": plugin.to_dict()}

    def unregister(self, name: str) -> bool:
        key = str(name or "").strip().upper()
        with self._lock:
            existed = key in self._functions
            self._functions.pop(key, None)
            self._metadata.pop(key, None)
            return existed

    def evaluate(self, name: str, candles: list[dict[str, Any]]) -> dict[str, Any]:
        key = str(name or "").strip().upper()
        with self._lock:
            function = self._functions.get(key)
            metadata = self._metadata.get(key)
        if function is None or metadata is None:
            return {
                "success": False,
                "indicator": key,
                "reason": "INDICATOR_NOT_REGISTERED",
            }
        try:
            value = function(candles)
        except Exception as exc:
            return {
                "success": False,
                "indicator": key,
                "reason": "INDICATOR_EVALUATION_FAILED",
                "message": f"{type(exc).__name__}: {exc}"[:500],
            }
        return {
            "success": True,
            "indicator": key,
            "metadata": metadata.to_dict(),
            "value": value,
        }

    def evaluate_all(self, candles: list[dict[str, Any]]) -> dict[str, Any]:
        with self._lock:
            names = list(self._functions)
        return {name: self.evaluate(name, candles) for name in names}

    def describe(self) -> list[dict[str, Any]]:
        with self._lock:
            return [plugin.to_dict() for plugin in self._metadata.values()]


indicator_registry = IndicatorPluginRegistry()
