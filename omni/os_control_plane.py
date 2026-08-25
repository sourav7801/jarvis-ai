from __future__ import annotations

import json
import os
import platform
import re
import shutil
import socket
import sys
import threading
import time
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = PROJECT_ROOT / "data" / "jarvis_os" / "state.json"
EVENT_PATH = PROJECT_ROOT / "data" / "jarvis_os" / "events.jsonl"
FAILURE_PATH = PROJECT_ROOT / "data" / "jarvis_os" / "failures.jsonl"


SERVICE_ENDPOINTS = {
    "master": "http://127.0.0.1:8797/api/health",
    "quant_terminal": "http://127.0.0.1:8787/api/health",
    "fyers_bridge": "http://127.0.0.1:8790/api/status",
    "nautilus_core": "http://127.0.0.1:8792/health",
}


SAFE_AUTONOMOUS = {"read_only", "low", "reversible_local"}
APPROVAL_REQUIRED = {
    "destructive",
    "external_write",
    "credential",
    "financial",
    "production",
    "publish",
    "communication",
}
ABSOLUTELY_LOCKED = {"live_trading"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any, maximum: int = 1000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:maximum]


def _json_write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    temporary.replace(path)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, default=str, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path, limit: int = 500) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()[-limit:]:
            try:
                value = json.loads(line)
            except Exception:
                continue
            if isinstance(value, dict):
                rows.append(value)
    except OSError:
        return []
    return rows


def _http_json(url: str, timeout: float = 0.6) -> dict[str, Any] | None:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "JARVIS-OS/6.0"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            value = json.loads(response.read().decode("utf-8", errors="replace"))
            return value if isinstance(value, dict) else {"value": value}
    except Exception:
        return None


@dataclass(frozen=True)
class Capability:
    name: str
    kind: str
    risk: str
    description: str
    source: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ApprovalDecision:
    mode: str
    allowed: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class JarvisOSControlPlane:
    """Persistent AI operating layer above Windows and JARVIS subsystems.

    This is not an OS kernel replacement. It is the governed control plane that
    inventories capabilities, observes service health, records outcomes, learns
    from recurring failure classes, and exposes stable OS-level commands.
    """

    def __init__(
        self,
        *,
        state_path: Path | str | None = None,
        event_path: Path | str | None = None,
        failure_path: Path | str | None = None,
    ) -> None:
        self.state_path = Path(state_path or STATE_PATH)
        self.event_path = Path(event_path or EVENT_PATH)
        self.failure_path = Path(failure_path or FAILURE_PATH)
        self._lock = threading.RLock()
        self._state: dict[str, Any] = {
            "version": "JARVIS_OS_V6",
            "mode": "GOVERNED_AUTONOMY",
            "started_at": utc_now(),
            "runs": 0,
            "successes": 0,
            "failures": 0,
            "capability_stats": {},
            "latest_goal": None,
            "latest_event": None,
            "self_improvement": {
                "production_self_modification": False,
                "research_hypotheses_only": True,
                "promotion_requires_tests": True,
            },
        }
        self._load()

    def _load(self) -> None:
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                self._state.update(payload)
        except Exception:
            return

    def _save(self) -> None:
        _json_write_atomic(self.state_path, self._state)

    def emit(self, event_type: str, **payload: Any) -> dict[str, Any]:
        event = {
            "id": uuid4().hex,
            "timestamp": utc_now(),
            "type": str(event_type or "EVENT").upper(),
            **payload,
        }
        with self._lock:
            _append_jsonl(self.event_path, event)
            self._state["latest_event"] = event
            self._save()
        return event

    def capability_inventory(self) -> list[Capability]:
        capabilities: list[Capability] = []

        try:
            from tools.registry import list_tools

            for name, definition in sorted(list_tools().items()):
                capabilities.append(
                    Capability(
                        name=name,
                        kind="tool",
                        risk=str(getattr(definition, "risk", "unknown") or "unknown"),
                        description=_clean(getattr(definition, "description", ""), 500),
                        source=getattr(definition.function, "__module__", "tools"),
                    )
                )
        except Exception:
            pass

        try:
            from omni.agent_registry import default_agent_specs

            for spec in default_agent_specs():
                capabilities.append(
                    Capability(
                        name=spec.name,
                        kind="agent",
                        risk="governed",
                        description=_clean(getattr(spec, "label", spec.name), 500),
                        source=getattr(spec, "module", "agents"),
                    )
                )
        except Exception:
            pass

        names = {(item.kind, item.name) for item in capabilities}
        for name, description in (
            ("mission_control", "Durable multi-agent outcome orchestration."),
            ("hybrid_memory", "Persistent preference, project, decision, and conversation memory."),
            ("quant_intelligence", "Paper-only quantitative research and portfolio subsystem."),
            ("voice_runtime", "Local voice input/output runtime."),
            ("os_control_plane", "Health, capability, event, policy, and improvement control plane."),
        ):
            if ("subsystem", name) not in names:
                capabilities.append(
                    Capability(name, "subsystem", "governed", description, "JARVIS")
                )
        return capabilities

    def approval_for(self, risk: str) -> ApprovalDecision:
        risk_value = _clean(risk, 100).lower().replace("-", "_").replace(" ", "_")
        if risk_value in ABSOLUTELY_LOCKED:
            return ApprovalDecision("LOCKED", False, "This capability is disabled by policy.")
        if risk_value in APPROVAL_REQUIRED:
            return ApprovalDecision(
                "EXPLICIT_APPROVAL_REQUIRED",
                False,
                "Consequential action requires fresh scoped user approval.",
            )
        if risk_value in SAFE_AUTONOMOUS or risk_value in {"governed", "unknown", ""}:
            return ApprovalDecision(
                "AUTONOMOUS_WITH_AUDIT",
                True,
                "Local/read-only/reversible work may run autonomously with audit logging.",
            )
        return ApprovalDecision(
            "EXPLICIT_APPROVAL_REQUIRED",
            False,
            "Unclassified risk defaults to approval required.",
        )

    def service_health(self) -> dict[str, Any]:
        services: dict[str, Any] = {}
        for name, url in SERVICE_ENDPOINTS.items():
            started = time.perf_counter()
            payload = _http_json(url)
            services[name] = {
                "online": payload is not None,
                "latency_ms": round((time.perf_counter() - started) * 1000.0, 2),
                "payload": payload,
            }
        return services

    def machine_health(self) -> dict[str, Any]:
        disk = shutil.disk_usage(PROJECT_ROOT)
        return {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "pid": os.getpid(),
            "cpu_count": os.cpu_count(),
            "disk_total_gb": round(disk.total / (1024 ** 3), 2),
            "disk_free_gb": round(disk.free / (1024 ** 3), 2),
            "project_root": str(PROJECT_ROOT),
        }

    def status(self) -> dict[str, Any]:
        capabilities = self.capability_inventory()
        services = self.service_health()
        online = sum(1 for item in services.values() if item.get("online"))
        with self._lock:
            state = json.loads(json.dumps(self._state, default=str))
        return {
            "success": True,
            "system": "JARVIS_OS",
            "version": "V6",
            "mode": state.get("mode"),
            "machine": self.machine_health(),
            "services": services,
            "service_online_count": online,
            "service_total": len(services),
            "capability_count": len(capabilities),
            "agent_count": sum(1 for item in capabilities if item.kind == "agent"),
            "tool_count": sum(1 for item in capabilities if item.kind == "tool"),
            "runs": state.get("runs", 0),
            "successes": state.get("successes", 0),
            "failures": state.get("failures", 0),
            "latest_goal": state.get("latest_goal"),
            "self_improvement": state.get("self_improvement"),
            "live_trading": "LOCKED",
        }

    def record_goal(self, objective: str) -> dict[str, Any]:
        goal = {
            "id": uuid4().hex[:12],
            "objective": _clean(objective, 4000),
            "created_at": utc_now(),
            "status": "ACCEPTED",
        }
        with self._lock:
            self._state["latest_goal"] = goal
            self._save()
        self.emit("GOAL_ACCEPTED", goal=goal)
        return goal

    def record_outcome(
        self,
        capability: str,
        *,
        success: bool,
        duration_ms: float | None = None,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        capability = _clean(capability, 200) or "unknown"
        with self._lock:
            self._state["runs"] = int(self._state.get("runs", 0)) + 1
            key = "successes" if success else "failures"
            self._state[key] = int(self._state.get(key, 0)) + 1
            stats = self._state.setdefault("capability_stats", {}).setdefault(
                capability,
                {"runs": 0, "successes": 0, "failures": 0, "duration_ms_total": 0.0},
            )
            stats["runs"] += 1
            stats["successes" if success else "failures"] += 1
            stats["duration_ms_total"] += float(duration_ms or 0.0)
            self._save()

        payload = {
            "capability": capability,
            "success": bool(success),
            "duration_ms": duration_ms,
            "error": _clean(error, 2000) if error else None,
            "metadata": metadata or {},
        }
        event = self.emit("CAPABILITY_OUTCOME", **payload)
        if not success:
            self.record_failure(capability, error or "unknown failure", metadata=metadata)
        return event

    @staticmethod
    def _failure_signature(message: str) -> str:
        value = _clean(message, 1200).lower()
        value = re.sub(r"[a-f0-9]{7,40}", "<sha>", value)
        value = re.sub(r"\b\d+(?:\.\d+)+\b", "<version>", value)
        value = re.sub(r"\b\d+\b", "<n>", value)
        value = re.sub(r"[a-z]:\\[^\s]+", "<path>", value)
        return value[:500]

    def record_failure(
        self,
        capability: str,
        error: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        record = {
            "timestamp": utc_now(),
            "capability": _clean(capability, 200),
            "error": _clean(error, 3000),
            "signature": self._failure_signature(error),
            "metadata": metadata or {},
        }
        _append_jsonl(self.failure_path, record)
        return record

    def improvement_review(self, limit: int = 500) -> dict[str, Any]:
        failures = _read_jsonl(self.failure_path, limit=limit)
        signatures = Counter(row.get("signature") or "unknown" for row in failures)
        capabilities = Counter(row.get("capability") or "unknown" for row in failures)
        recurring = [
            {"signature": signature, "count": count}
            for signature, count in signatures.most_common(10)
            if count >= 2
        ]
        proposals = []
        for item in recurring:
            proposals.append(
                {
                    "type": "RESEARCH_HYPOTHESIS",
                    "problem": item["signature"],
                    "occurrences": item["count"],
                    "recommended_next_step": (
                        "Create a minimal reproduction, patch on a safety branch, add a regression test, "
                        "run targeted and full regressions, then promote only after evidence passes."
                    ),
                }
            )
        return {
            "success": True,
            "failures_reviewed": len(failures),
            "top_failure_capabilities": dict(capabilities.most_common(10)),
            "recurring_failure_classes": recurring,
            "research_proposals": proposals,
            "production_self_modification": False,
            "promotion_requires_tests": True,
        }

    def capability_report(self) -> dict[str, Any]:
        items = [item.to_dict() for item in self.capability_inventory()]
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in items:
            grouped[item["kind"]].append(item)
        return {
            "success": True,
            "count": len(items),
            "groups": dict(grouped),
            "approval_model": {
                "safe_local": "AUTONOMOUS_WITH_AUDIT",
                "consequential": "EXPLICIT_APPROVAL_REQUIRED",
                "live_trading": "LOCKED",
            },
        }


_OS_STATUS_RE = re.compile(
    r"\b(?:jarvis\s+os\s+status|os\s+status|system\s+health|jarvis\s+health|control\s+plane\s+status)\b",
    re.IGNORECASE,
)
_OS_CAPABILITY_RE = re.compile(
    r"\b(?:what\s+can\s+you\s+do|show\s+(?:all\s+)?capabilities|show\s+(?:all\s+)?skills|jarvis\s+capabilities|agent\s+capabilities)\b",
    re.IGNORECASE,
)
_OS_REVIEW_RE = re.compile(
    r"\b(?:analy[sz]e\s+(?:your\s+)?mistakes|self\s+review|improvement\s+review|what\s+are\s+you\s+failing\s+at|learn\s+from\s+failures)\b",
    re.IGNORECASE,
)


def os_command_kind(text: str) -> str | None:
    value = str(text or "")
    if _OS_STATUS_RE.search(value):
        return "STATUS"
    if _OS_CAPABILITY_RE.search(value):
        return "CAPABILITIES"
    if _OS_REVIEW_RE.search(value):
        return "IMPROVEMENT_REVIEW"
    return None


def os_command_payload(text: str) -> dict[str, Any] | None:
    kind = os_command_kind(text)
    if kind is None:
        return None
    if kind == "STATUS":
        payload = jarvis_os.status()
        payload.update(
            {
                "action": "jarvis_os_status",
                "speech": (
                    f"JARVIS OS V6 control plane is online. "
                    f"{payload['service_online_count']} of {payload['service_total']} local services responded, "
                    f"with {payload['agent_count']} registered agents and {payload['tool_count']} tools."
                ),
            }
        )
        return payload
    if kind == "CAPABILITIES":
        payload = jarvis_os.capability_report()
        payload.update(
            {
                "action": "jarvis_os_capabilities",
                "speech": (
                    f"JARVIS currently exposes {payload['count']} governed capabilities across tools, agents, and subsystems."
                ),
            }
        )
        return payload
    payload = jarvis_os.improvement_review()
    payload.update(
        {
            "action": "jarvis_os_improvement_review",
            "speech": (
                f"JARVIS reviewed {payload['failures_reviewed']} recorded failures and found "
                f"{len(payload['recurring_failure_classes'])} recurring failure classes. "
                "Any improvement remains a tested research proposal until promoted through regression gates."
            ),
        }
    )
    return payload


jarvis_os = JarvisOSControlPlane()
