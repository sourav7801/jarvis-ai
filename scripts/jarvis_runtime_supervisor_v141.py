"""JARVIS V14.1 risk-geometry convergence runtime supervisor.

Preserves the protected V8 Master, V14 continuous-EV authority and all prior
process ownership rules while requiring verified risk-geometry reconstruction
in canonical Master, Quant and Completion processes. Unknown processes are
never terminated. No broker-order API is imported.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.jarvis_runtime_supervisor import JarvisRuntimeSupervisor, ManagedService  # noqa: E402
from scripts import jarvis_runtime_supervisor_v14 as v14  # noqa: E402
from scripts.jarvis_runtime_supervisor_v62 import _port_open, _trusted_jarvis_process  # noqa: E402

MASTER_HOST = v14.MASTER_HOST
MASTER_PORT = v14.MASTER_PORT
MASTER_BASE = v14.MASTER_BASE
QUANT_HOST = v14.QUANT_HOST
QUANT_PORT = v14.QUANT_PORT
QUANT_BASE = v14.QUANT_BASE
COMPLETION_HOST = v14.COMPLETION_HOST
COMPLETION_PORT = v14.COMPLETION_PORT
COMPLETION_BASE = v14.COMPLETION_BASE
_json_http = v14._json_http
_reclaim_listener = v14._reclaim_listener


def master_v141_surface_status() -> dict[str, Any]:
    v14_status = v14.master_v14_surface_status()
    status, payload = _json_http(MASTER_BASE + "/api/v14.1/paper-authority")
    current = bool(
        v14_status.get("current")
        and status == 200
        and payload.get("success") is True
        and payload.get("version") == "14.1"
        and payload.get("service") == "JARVIS_MASTER_V141_RISK_GEOMETRY_BRIDGE"
        and payload.get("v141_bridge_installed") is True
        and payload.get("scan_wrapper_installed") is True
        and payload.get("legacy_qualification_required_for_geometry") is False
        and payload.get("invalid_risk_levels_hard_blocker_preserved") is True
        and payload.get("decision_authority") == "POSITIVE_CONTEXTUAL_EXPECTED_VALUE_CONTINUOUS_RISK"
        and payload.get("paper_only") is True
        and payload.get("live_execution") is False
        and payload.get("automatic_broker_order") is False
    )
    return {"current": current, "v14": v14_status, "status": status, "service": payload.get("service")}


def quant_v141_surface_status() -> dict[str, Any]:
    status, payload = _json_http(QUANT_BASE + "/api/v14.1/status", timeout=6.0)
    runtime = payload.get("runtime") if isinstance(payload.get("runtime"), dict) else {}
    current = bool(
        status == 200
        and payload.get("success") is True
        and payload.get("version") == "14.1"
        and payload.get("service") == "JARVIS_QUANT_V141_RISK_GEOMETRY_CONVERGENCE"
        and runtime.get("installed") is True
        and runtime.get("scan_wrapper_installed") is True
        and runtime.get("upstream_legacy_qualification_can_suppress_geometry") is False
        and payload.get("invalid_risk_levels_hard_blocker_preserved") is True
        and payload.get("decision_authority") == "POSITIVE_CONTEXTUAL_EXPECTED_VALUE_CONTINUOUS_RISK"
        and payload.get("paper_only") is True
        and payload.get("live_execution") is False
        and payload.get("automatic_broker_order") is False
    )
    return {"current": current, "status": status, "service": payload.get("service")}


def completion_v141_surface_status() -> dict[str, Any]:
    status, payload = _json_http(COMPLETION_BASE + "/api/v14.1/status", timeout=6.0)
    current = bool(
        status == 200
        and payload.get("success") is True
        and payload.get("version") == "14.1"
        and payload.get("service") == "JARVIS_RISK_GEOMETRY_CONVERGENCE_OS"
        and payload.get("runtime_bridge_installed") is True
        and payload.get("scan_wrapper_installed") is True
        and payload.get("quant_risk_geometry_ready") is True
        and payload.get("legacy_qualification_required_for_geometry") is False
        and payload.get("invalid_risk_levels_hard_blocker_preserved") is True
        and payload.get("permanent_agents") == 29
        and payload.get("paper_only") is True
        and payload.get("live_execution") is False
        and payload.get("automatic_broker_order") is False
        and payload.get("automatic_production_strategy_rewrite") is False
    )
    return {"current": current, "status": status, "service": payload.get("service")}


def _trusted_master_process(info: dict[str, Any]) -> bool:
    if v14._trusted_master_process(info):
        return True
    root = str(ROOT).lower().rstrip("\\/")
    command = str(info.get("CommandLine") or "").lower()
    executable = str(info.get("ExecutablePath") or "").lower()
    return bool(
        (executable.startswith(root + "\\") or root in command)
        and ("start_jarvis_master_v141.py" in command or "jarvis_runtime_supervisor_v141" in command)
    )


def _trusted_completion_process(info: dict[str, Any]) -> bool:
    if v14._trusted_completion_process(info):
        return True
    root = str(ROOT).lower().rstrip("\\/")
    command = str(info.get("CommandLine") or "").lower()
    executable = str(info.get("ExecutablePath") or "").lower()
    return bool(
        (executable.startswith(root + "\\") or root in command)
        and ("completion_console_v141" in command or "jarvis_runtime_supervisor_v141" in command)
    )


def reclaim_obsolete_master_listener() -> dict[str, Any]:
    surface = master_v141_surface_status() if _port_open(MASTER_HOST, MASTER_PORT) else {"current": False}
    result = _reclaim_listener(host=MASTER_HOST, port=MASTER_PORT, current=bool(surface.get("current")), trusted=_trusted_master_process, label="MASTER")
    result["surface"] = surface
    return result


def reclaim_obsolete_quant_listener() -> dict[str, Any]:
    surface = quant_v141_surface_status() if _port_open(QUANT_HOST, QUANT_PORT) else {"current": False}
    result = _reclaim_listener(host=QUANT_HOST, port=QUANT_PORT, current=bool(surface.get("current")), trusted=_trusted_jarvis_process, label="QUANT")
    result["surface"] = surface
    return result


def reclaim_obsolete_completion_listener() -> dict[str, Any]:
    surface = completion_v141_surface_status() if _port_open(COMPLETION_HOST, COMPLETION_PORT) else {"current": False}
    result = _reclaim_listener(host=COMPLETION_HOST, port=COMPLETION_PORT, current=bool(surface.get("current")), trusted=_trusted_completion_process, label="COMPLETION")
    result["surface"] = surface
    return result


def v141_services(root: Path = ROOT) -> tuple[ManagedService, ...]:
    python = str(Path(sys.executable).resolve())
    master_wrapper = root / "start_jarvis_master_v141.py"
    services: list[ManagedService] = []
    for service in v14.v14_services(root):
        if service.name == "master":
            services.append(ManagedService(
                name="master",
                argv=(python, str(master_wrapper)),
                health_url=MASTER_BASE + "/api/v14.1/paper-authority",
                expected_service="JARVIS_MASTER_V141_RISK_GEOMETRY_BRIDGE",
                port=service.port,
                health_markers=(),
                environment=service.environment,
            ))
            continue
        if service.name == "quant":
            environment = dict(service.environment)
            environment["JARVIS_V141_RISK_GEOMETRY"] = "1"
            services.append(ManagedService(
                name="quant",
                argv=service.argv,
                health_url=QUANT_BASE + "/api/v14.1/status",
                expected_service="JARVIS_QUANT_V141_RISK_GEOMETRY_CONVERGENCE",
                port=service.port,
                health_markers=(),
                environment=tuple(environment.items()),
            ))
            continue
        if service.name == "completion":
            services.append(ManagedService(
                name="completion",
                argv=service.argv,
                health_url=COMPLETION_BASE + "/api/v14.1/status",
                expected_service="JARVIS_RISK_GEOMETRY_CONVERGENCE_OS",
                port=service.port,
                health_markers=(),
                environment=service.environment,
            ))
            continue
        services.append(service)
    return tuple(services)


def main() -> int:
    print("JARVIS V14.1 risk-geometry runtime preflight...")
    quant = reclaim_obsolete_quant_listener()
    print("Quant ownership preflight:", quant.get("action"))
    master = reclaim_obsolete_master_listener()
    print("Master ownership preflight:", master.get("action"))
    completion = reclaim_obsolete_completion_listener()
    print("Completion ownership preflight:", completion.get("action"))
    print("Starting protected V8 Master + V14.1 risk-geometry Quant + Nautilus + V14.1 Completion.")
    print("Legacy score qualification no longer controls whether valid risk geometry exists.")
    print("INVALID_RISK_LEVELS remains hard only when verified completed-bar geometry cannot be built.")
    print("Live broker execution remains locked.")
    browser = str(os.getenv("JARVIS_NO_BROWSER", "0")).strip().lower() not in {"1", "true", "yes", "on"}
    return JarvisRuntimeSupervisor(root=ROOT, services=v141_services(ROOT), browser=browser).run_forever()


if __name__ == "__main__":
    raise SystemExit(main())
