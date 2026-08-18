"""Read-only runtime manifest and diagnostics for the JARVIS control plane.

The control plane deliberately inspects agent entrypoints statically instead of
importing or executing them.  This keeps a dashboard refresh from triggering
agent side effects while still exposing useful readiness evidence.
"""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable

from .agent_registry import AgentSpec, default_agent_specs
from .contracts import utc_now
from .runtime import get_audit_store
from tools.capabilities import capabilities_for
from tools.registry import list_tools


READ_ONLY_CAPABILITIES = {
    "filesystem.read",
    "memory.read",
    "network.read",
    "research.read",
    "system.health",
    "system.read",
    "web.read",
    "web.search",
}


def is_control_plane_request(text: str) -> bool:
    """Return whether a command is asking for runtime/agent diagnostics."""

    value = " ".join(str(text or "").strip().lower().split())
    if not value:
        return False
    phrases = (
        "agent health",
        "agent status",
        "control plane",
        "system core",
        "system health",
        "system status",
        "what agents are ready",
        "which agents are ready",
        "runtime health",
        "runtime status",
        "show diagnostics",
        "open diagnostics",
    )
    return any(phrase in value for phrase in phrases)


class ControlPlane:
    """Build a bounded, secret-free runtime snapshot for the local operator."""

    def __init__(
        self,
        project_root: Path | str,
        *,
        specs: Iterable[AgentSpec] | None = None,
        tool_provider: Callable[[], dict[str, dict[str, Any]]] = list_tools,
        audit_provider: Callable[[], Any] = get_audit_store,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.specs = tuple(specs if specs is not None else default_agent_specs())
        self.tool_provider = tool_provider
        self.audit_provider = audit_provider

    def _module_path(self, spec: AgentSpec) -> Path:
        return self.project_root.joinpath(*spec.module.split(".")).with_suffix(".py")

    @staticmethod
    def _agent_authority(spec: AgentSpec) -> str:
        capabilities = set(spec.capabilities)
        if spec.name == "operator":
            return "SUPERVISED_ORCHESTRATION"
        if spec.name == "trading" or any(
            capability.startswith(("trading.", "market.", "paper."))
            for capability in capabilities
        ):
            return "RESEARCH_AND_PAPER_ONLY"
        if any(
            capability.startswith(("web.", "network.", "research."))
            for capability in capabilities
        ):
            return "READ_ONLY_NETWORK"
        if any(
            capability.startswith(("code.", "document.", "content."))
            for capability in capabilities
        ):
            return "LOCAL_GENERATION"
        return "ADVISORY_LOCAL"

    def _agent_manifest(self, spec: AgentSpec) -> dict[str, Any]:
        path = self._module_path(spec)
        status = "DISABLED" if not spec.enabled else "READY"
        diagnostic = "Static module and entrypoint validation passed."
        source = None

        if not path.is_file():
            status = "UNAVAILABLE"
            diagnostic = "The registered module file is missing."
        else:
            source = str(path.relative_to(self.project_root)).replace("\\", "/")
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                functions = {
                    node.name
                    for node in ast.walk(tree)
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
                if spec.entrypoint not in functions:
                    status = "UNAVAILABLE"
                    diagnostic = "The registered callable was not found statically."
            except (OSError, UnicodeError, SyntaxError) as error:
                status = "DEGRADED"
                diagnostic = f"Static validation failed safely: {type(error).__name__}."

        return {
            "name": spec.name,
            "label": spec.label,
            "status": status,
            "diagnostic": diagnostic,
            "module": spec.module,
            "entrypoint": spec.entrypoint,
            "source": source,
            "capabilities": sorted(spec.capabilities),
            "authority": self._agent_authority(spec),
            "isolation": spec.isolation.value,
            "input_limit": spec.max_input_chars,
            "output_limit": spec.max_output_chars,
        }

    def agent_manifests(self) -> list[dict[str, Any]]:
        return [self._agent_manifest(spec) for spec in self.specs]

    def tool_manifests(self) -> list[dict[str, Any]]:
        manifests = []
        for name, metadata in sorted(self.tool_provider().items()):
            capabilities = sorted(capabilities_for(name))
            risk = str(metadata.get("risk") or "UNKNOWN").upper()
            read_only = bool(capabilities) and set(capabilities).issubset(
                READ_ONLY_CAPABILITIES
            )
            if risk in {"HIGH", "CRITICAL", "UNKNOWN"}:
                policy = "LOCKED_WITHOUT_SCOPED_APPROVAL"
            elif read_only:
                policy = "READ_ONLY_AVAILABLE"
            else:
                policy = "LOCAL_SIDE_EFFECT"
            manifests.append(
                {
                    "name": name,
                    "description": str(metadata.get("description") or ""),
                    "risk": risk,
                    "capabilities": capabilities,
                    "policy": policy,
                }
            )
        return manifests

    def recent_trace(self, limit: int = 40) -> list[dict[str, Any]]:
        """Return audit metadata without tool arguments, outputs, or payloads."""

        safe_limit = min(max(int(limit), 1), 100)
        try:
            events = self.audit_provider().recent_events(safe_limit)
        except Exception:
            return []
        return [
            {
                "id": str(event.get("id") or ""),
                "timestamp": str(event.get("timestamp") or ""),
                "category": str(event.get("category") or "unknown"),
                "name": str(event.get("name") or "unknown"),
                "status": str(event.get("status") or "UNKNOWN"),
                "correlation_id": str(event.get("correlation_id") or ""),
            }
            for event in events[:safe_limit]
        ]

    @staticmethod
    def _mission_summary(mission_control: dict[str, Any] | None) -> dict[str, Any]:
        snapshot = mission_control or {}
        mission = snapshot.get("latest_mission") or {}
        tasks = mission.get("tasks") or []
        status_counts = Counter(str(task.get("status") or "UNKNOWN") for task in tasks)
        return {
            "mission_count": int(snapshot.get("mission_count") or 0),
            "active_id": mission.get("id"),
            "active_title": mission.get("title"),
            "active_status": mission.get("status") or "READY",
            "task_count": len(tasks),
            "task_statuses": dict(sorted(status_counts.items())),
            "approval_locks": len(mission.get("approval_locks") or []),
            "critic_verdict": (mission.get("critic") or {}).get("verdict"),
        }

    def snapshot(
        self,
        *,
        live_trading_enabled: bool,
        workstation_host: str,
        telemetry: dict[str, Any] | None = None,
        market: dict[str, Any] | None = None,
        mission_control: dict[str, Any] | None = None,
        company: dict[str, Any] | None = None,
        web: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        agents = self.agent_manifests()
        tools = self.tool_manifests()
        traces = self.recent_trace()
        agent_counts = Counter(item["status"] for item in agents)
        risk_counts = Counter(item["risk"] for item in tools)
        policy_counts = Counter(item["policy"] for item in tools)
        unavailable = agent_counts["UNAVAILABLE"] + agent_counts["DEGRADED"]
        market_stream = (market or {}).get("stream") or {}
        company_snapshot = company or {}
        web_snapshot = web or {}

        return {
            "generated_at": utc_now(),
            "status": "READY" if unavailable == 0 else "DEGRADED",
            "summary": {
                "agents_total": len(agents),
                "agents_ready": agent_counts["READY"],
                "agents_degraded": unavailable,
                "tools_total": len(tools),
                "tool_risks": dict(sorted(risk_counts.items())),
                "tool_policies": dict(sorted(policy_counts.items())),
                "audit_events_visible": len(traces),
            },
            "runtime": {
                "architecture": "LOCAL_FIRST_MODULAR_MONOLITH",
                "operator_model": "ONE_TRUSTED_OPERATOR",
                "workstation_host": workstation_host,
                "loopback_only": workstation_host.lower()
                in {"127.0.0.1", "localhost", "::1"},
                "authenticated_api": True,
                "live_trading": "ENABLED" if live_trading_enabled else "LOCKED",
                "market_data_provider": market_stream.get("provider") or "UNAVAILABLE",
                "market_data_connected": bool(market_stream.get("connected")),
                "model_actions": "SUPERVISED",
                "telemetry_available": bool((telemetry or {}).get("available")),
            },
            "guardrails": [
                "Consequential actions require scoped operator approval.",
                "Live broker order execution is not registered and remains locked.",
                "Agent readiness checks parse source without importing or executing it.",
                "Web retrieval is bounded and blocks private-network destinations.",
                "Subprocess workers are executable-allowlisted and root-bounded.",
                "Audit traces shown here omit arguments, results, secrets, and payloads.",
            ],
            "agents": agents,
            "tools": tools,
            "trace": traces,
            "missions": self._mission_summary(mission_control),
            "company": {
                "department_agents": int(company_snapshot.get("agent_count") or 0),
                "plan_count": int(company_snapshot.get("plan_count") or 0),
                "active_plan": bool(company_snapshot.get("latest_plan")),
            },
            "web": {
                "broad_search_configured": bool(
                    web_snapshot.get("broad_search_configured")
                ),
                "latest_query": (web_snapshot.get("latest") or {}).get("query"),
            },
        }


__all__ = ["ControlPlane", "is_control_plane_request"]
