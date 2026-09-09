"""JARVIS V16 canonical tool contract.

This module gives every workstation capability one predictable description and
one governance path.  It is deliberately independent of any model provider.
Existing V15 tools can be adapted into this registry without being rewritten.

Consequential actions remain approval gated.  Live broker execution is blocked
at the contract layer as an additional defence; the trading runtime remains
paper-only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import re
from threading import RLock
from typing import Any, Callable, Mapping


class ToolRisk(str, Enum):
    READ = "read"
    LOCAL_WRITE = "local_write"
    CONSEQUENTIAL = "consequential"
    BLOCKED = "blocked"


_NAMESPACED_NAME = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
_FORBIDDEN_LIVE_CAPABILITIES = {
    "trading.live_order",
    "trading.broker_order",
    "broker.place_order",
    "broker.modify_order",
    "broker.cancel_order",
    "broker.submit_order",
}


@dataclass(frozen=True)
class ToolSpec:
    name: str
    capability: str
    description: str
    risk: ToolRisk = ToolRisk.READ
    input_schema: Mapping[str, Any] = field(default_factory=dict)
    output_schema: Mapping[str, Any] = field(default_factory=dict)
    timeout_seconds: float = 30.0
    idempotent: bool = True
    requires_approval: bool | None = None
    source: str = "v16"
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not _NAMESPACED_NAME.fullmatch(str(self.name or "")):
            raise ValueError(f"tool name must be namespaced (for example file.read): {self.name!r}")
        if not str(self.capability or "").strip():
            raise ValueError("capability is required")
        if float(self.timeout_seconds) <= 0.0:
            raise ValueError("timeout_seconds must be greater than zero")
        if self.capability in _FORBIDDEN_LIVE_CAPABILITIES:
            raise ValueError(f"live broker capability is forbidden in JARVIS V16: {self.capability}")

    @property
    def approval_required(self) -> bool:
        if self.requires_approval is not None:
            return bool(self.requires_approval)
        return self.risk == ToolRisk.CONSEQUENTIAL

    def public_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["risk"] = self.risk.value
        payload["requires_approval"] = self.approval_required
        return payload


@dataclass(frozen=True)
class ToolResult:
    success: bool
    tool: str
    payload: Any = None
    error: str | None = None
    approval_required: bool = False
    blocked: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ToolRegistryV16:
    """Thread-safe capability inventory and execution gateway.

    Executors are kept in memory while serializable ToolSpecs are exposed to the
    planner.  This prevents model/planner code from receiving raw credentials or
    arbitrary Python callables.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._specs: dict[str, ToolSpec] = {}
        self._executors: dict[str, Callable[..., Any]] = {}

    def register(
        self,
        spec: ToolSpec,
        executor: Callable[..., Any] | None = None,
        *,
        replace: bool = False,
    ) -> ToolSpec:
        with self._lock:
            if spec.name in self._specs and not replace:
                raise ValueError(f"tool already registered: {spec.name}")
            self._specs[spec.name] = spec
            if executor is not None:
                self._executors[spec.name] = executor
            elif replace:
                self._executors.pop(spec.name, None)
        return spec

    def unregister(self, name: str) -> None:
        with self._lock:
            self._specs.pop(name, None)
            self._executors.pop(name, None)

    def get(self, name: str) -> ToolSpec | None:
        with self._lock:
            return self._specs.get(str(name))

    def inventory(self) -> dict[str, Any]:
        with self._lock:
            specs = [self._specs[name].public_dict() for name in sorted(self._specs)]
        return {
            "success": True,
            "version": "16.0",
            "service": "JARVIS_V16_CANONICAL_TOOL_REGISTRY",
            "tool_count": len(specs),
            "tools": specs,
            "consequential_actions_approval_gated": True,
            "live_broker_execution": False,
            "automatic_broker_order": False,
        }

    def execute(
        self,
        name: str,
        arguments: Mapping[str, Any] | None = None,
        *,
        approval_granted: bool = False,
    ) -> ToolResult:
        tool_name = str(name)
        with self._lock:
            spec = self._specs.get(tool_name)
            executor = self._executors.get(tool_name)
        if spec is None:
            return ToolResult(False, tool_name, error="TOOL_NOT_FOUND")
        if spec.risk == ToolRisk.BLOCKED:
            return ToolResult(False, tool_name, error="TOOL_BLOCKED", blocked=True)
        if spec.approval_required and not approval_granted:
            return ToolResult(False, tool_name, error="APPROVAL_REQUIRED", approval_required=True)
        if executor is None:
            return ToolResult(False, tool_name, error="TOOL_EXECUTOR_UNAVAILABLE")
        try:
            payload = executor(**dict(arguments or {}))
        except Exception as exc:  # execution failures must be explicit, never fabricated
            return ToolResult(False, tool_name, error=f"{type(exc).__name__}: {exc}"[:1000])
        return ToolResult(True, tool_name, payload=payload)


def _legacy_risk(value: str | None) -> ToolRisk:
    token = str(value or "").strip().lower()
    if token in {"read_only", "read"}:
        return ToolRisk.READ
    if token in {"low", "local_write"}:
        return ToolRisk.LOCAL_WRITE
    if token in {"medium", "high", "approval", "consequential"}:
        return ToolRisk.CONSEQUENTIAL
    if token == "blocked":
        return ToolRisk.BLOCKED
    return ToolRisk.CONSEQUENTIAL


def legacy_action_specs() -> list[ToolSpec]:
    """Expose the existing action-engine inventory through the V16 contract.

    This is metadata-only adaptation; it does not replace V15 execution paths.
    """

    try:
        from omni.action_engine import action_engine
        from tools.capabilities import capabilities_for

        status = action_engine.status()
        policy = dict(status.get("policy") or {})
    except Exception:
        return []

    specs: list[ToolSpec] = []
    for legacy_name, risk_name in sorted(policy.items()):
        capabilities = sorted(capabilities_for(legacy_name)) or [f"legacy.{legacy_name}"]
        # One legacy callable may advertise multiple low-level capabilities; the
        # canonical planning surface remains one namespaced tool.
        specs.append(
            ToolSpec(
                name=f"legacy.{legacy_name}",
                capability=capabilities[0],
                description=f"Compatibility adapter for existing JARVIS tool '{legacy_name}'.",
                risk=_legacy_risk(risk_name),
                idempotent=str(risk_name).lower() in {"read", "read_only"},
                source="v15_action_engine",
                tags=tuple(capabilities),
            )
        )
    return specs


CANONICAL_TOOL_REGISTRY_V16 = ToolRegistryV16()


def install_legacy_tool_metadata(registry: ToolRegistryV16 | None = None) -> dict[str, Any]:
    target = registry or CANONICAL_TOOL_REGISTRY_V16
    installed = 0
    for spec in legacy_action_specs():
        try:
            target.register(spec)
            installed += 1
        except ValueError:
            pass
    return {
        "success": True,
        "installed": installed,
        "registry": target.inventory(),
    }


__all__ = [
    "ToolRisk",
    "ToolSpec",
    "ToolResult",
    "ToolRegistryV16",
    "CANONICAL_TOOL_REGISTRY_V16",
    "install_legacy_tool_metadata",
    "legacy_action_specs",
]
