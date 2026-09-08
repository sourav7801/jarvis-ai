"""JARVIS V14 autonomous execution intelligence runtime supervisor.

Preserves the protected V8 Master and all prior ownership rules while requiring
V14 continuous positive-EV paper authority on Master, Quant and Completion.
Unknown processes are never terminated. No broker-order API is imported.
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
from scripts import jarvis_runtime_supervisor_v13 as v13  # noqa: E402
from scripts.jarvis_runtime_supervisor_v62 import _port_open, _trusted_jarvis_process  # noqa: E402

MASTER_HOST = v13.MASTER_HOST
MASTER_PORT = v13.MASTER_PORT
MASTER_BASE = f"http://{MASTER_HOST}:{MASTER_PORT}"
QUANT_HOST = v13.QUANT_HOST
QUANT_PORT = v13.QUANT_PORT
QUANT_BASE = v13.QUANT_BASE
COMPLETION_HOST = v13.COMPLETION_HOST
COMPLETION_PORT = v13.COMPLETION_PORT
COMPLETION_BASE = v13.COMPLETION_BASE
_json_http = v13._json_http
_reclaim_listener = v13._reclaim_listener


def master_v14_surface_status() -> dict[str, Any]:
    v13_status = v13.master_v13_surface_status()
    status, payload = _json_http(MASTER_BASE + "/api/v14/paper-authority")
    current = bool(
        v13_status.get("current")
        and status == 200
        and payload.get("success") is True
        and payload.get("version") == "14.0"
        and payload.get("service") == "JARVIS_MASTER_V14_AUTONOMOUS_EXECUTION_BRIDGE"
        and payload.get("v14_bridge_installed") is True
        and payload.get("decision_authority") == "POSITIVE_CONTEXTUAL_EXPECTED_VALUE_CONTINUOUS_RISK"
        and payload.get("arbitrary_confidence_execution_gate") is False
        and payload.get("watching_is_terminal_state") is False
        and payload.get("paper_only") is True
        and payload.get("live_execution") is False
        and payload.get("automatic_broker_order") is False
    )
    return {
        "current": current,
        "v13": v13_status,
        "status": status,
        "service": payload.get("service"),
        "decision_authority": payload.get("decision_authority"),
    }


def quant_v14_surface_status() -> dict[str, Any]:
    status, payload = _json_http(QUANT_BASE + "/api/v14/execution-authority", timeout=5.0)
    controller_status, controller = _json_http(QUANT_BASE + "/api/paper/portfolio-controller", timeout=5.0)
    policy = payload.get("policy") if isinstance(payload.get("policy"), dict) else {}
    runtime = payload.get("runtime") if isinstance(payload.get("runtime"), dict) else {}
    sizing = payload.get("sizing") if isinstance(payload.get("sizing"), dict) else {}
    current = bool(
        status == 200
        and payload.get("success") is True
        and payload.get("version") == "14.0"
        and payload.get("service") == "JARVIS_QUANT_V14_EXECUTION_AUTHORITY"
        and policy.get("decision_authority") == "POSITIVE_CONTEXTUAL_EXPECTED_VALUE_CONTINUOUS_RISK"
        and policy.get("arbitrary_confidence_execution_gate") is False
        and policy.get("positive_ev_boundary_r") == 0.0
        and runtime.get("installed") is True
        and runtime.get("watching_is_terminal_state") is False
        and sizing.get("installed") is True
        and controller_status == 200
        and controller.get("success") is True
        and payload.get("live_execution") is False
        and payload.get("automatic_broker_order") is False
    )
    return {
        "current": current,
        "status": status,
        "service": payload.get("service"),
        "controller_status": controller_status,
        "decision_authority": policy.get("decision_authority"),
        "fractional_sizing": sizing.get("installed"),
    }


def completion_v14_surface_status() -> dict[str, Any]:
    status, payload = _json_http(COMPLETION_BASE + "/api/v14/status")
    current = bool(
        status == 200
        and payload.get("success") is True
        and payload.get("version") == "14.0"
        and payload.get("service") == "JARVIS_AUTONOMOUS_EXECUTION_INTELLIGENCE_OS"
        and payload.get("decision_authority") == "POSITIVE_CONTEXTUAL_EXPECTED_VALUE_CONTINUOUS_RISK"
        and payload.get("runtime_bridge_installed") is True
        and payload.get("fractional_sizing_installed") is True
        and payload.get("permanent_agents") == 29
        and payload.get("system_planes_do_not_count_as_agents") is True
        and payload.get("paper_only") is True
        and payload.get("live_execution") is False
        and payload.get("automatic_broker_order") is False
        and payload.get("automatic_production_strategy_rewrite") is False
    )
    return {
        "current": current,
        "status": status,
        "version": payload.get("version"),
        "service": payload.get("service"),
        "decision_authority": payload.get("decision_authority"),
    }


def _trusted_master_process(info: dict[str, Any]) -> bool:
    if v13._trusted_master_process(info):
        return True
    root = str(ROOT).lower().rstrip("\\/")
    command = str(info.get("CommandLine") or "").lower()
    executable = str(info.get("ExecutablePath") or "").lower()
    return bool(
        (executable.startswith(root + "\\") or root in command)
        and ("start_jarvis_master_v14.py" in command or "jarvis_runtime_supervisor_v14" in command)
    )


def _trusted_completion_process(info: dict[str, Any]) -> bool:
    if v13._trusted_completion_process(info):
        return True
    root = str(ROOT).lower().rstrip("\\/")
    command = str(info.get("CommandLine") or "").lower()
    executable = str(info.get("ExecutablePath") or "").lower()
    return bool(
        (executable.startswith(root + "\\") or root in command)
        and ("completion_console_v14" in command or "jarvis_runtime_supervisor_v14" in command)
    )


def reclaim_obsolete_master_listener() -> dict[str, Any]:
    surface = master_v14_surface_status() if _port_open(MASTER_HOST, MASTER_PORT) else {"current": False}
    result = _reclaim_listener(
        host=MASTER_HOST,
        port=MASTER_PORT,
        current=bool(surface.get("current")),
        trusted=_trusted_master_process,
        label="MASTER",
    )
    result["surface"] = surface
    return result


def reclaim_obsolete_quant_listener() -> dict[str, Any]:
    surface = quant_v14_surface_status() if _port_open(QUANT_HOST, QUANT_PORT) else {"current": False}
    result = _reclaim_listener(
        host=QUANT_HOST,
        port=QUANT_PORT,
        current=bool(surface.get("current")),
        trusted=_trusted_jarvis_process,
        label="QUANT",
    )
    result["surface"] = surface
    return result


def reclaim_obsolete_completion_listener() -> dict[str, Any]:
    surface = completion_v14_surface_status() if _port_open(COMPLETION_HOST, COMPLETION_PORT) else {"current": False}
    result = _reclaim_listener(
        host=COMPLETION_HOST,
        port=COMPLETION_PORT,
        current=bool(surface.get("current")),
        trusted=_trusted_completion_process,
        label="COMPLETION",
    )
    result["surface"] = surface
    return result


def v14_services(root: Path = ROOT) -> tuple[ManagedService, ...]:
    python = str(Path(sys.executable).resolve())
    master_wrapper = root / "start_jarvis_master_v14.py"
    services: list[ManagedService] = []
    for service in v13.v13_services(root):
        if service.name == "master":
            services.append(ManagedService(
                name="master",
                argv=(python, str(master_wrapper)),
                health_url=MASTER_BASE + "/api/v14/paper-authority",
                expected_service="JARVIS_MASTER_V14_AUTONOMOUS_EXECUTION_BRIDGE",
                port=service.port,
                health_markers=(),
                environment=service.environment,
            ))
            continue
        if service.name == "quant":
            environment = dict(service.environment)
            environment["JARVIS_AUTO_PAPER_START"] = "0"
            environment["JARVIS_V12_AUTO_PAPER_START"] = "1"
            environment["JARVIS_V13_CONTEXTUAL_INTELLIGENCE"] = "1"
            environment["JARVIS_V14_CONTINUOUS_EXECUTION"] = "1"
            services.append(ManagedService(
                name="quant",
                argv=service.argv,
                health_url=QUANT_BASE + "/api/v14/execution-authority",
                expected_service="JARVIS_QUANT_V14_EXECUTION_AUTHORITY",
                port=service.port,
                health_markers=(),
                environment=tuple(environment.items()),
            ))
            continue
        if service.name == "completion":
            services.append(ManagedService(
                name="completion",
                argv=service.argv,
                health_url=COMPLETION_BASE + "/api/v14/status",
                expected_service="JARVIS_AUTONOMOUS_EXECUTION_INTELLIGENCE_OS",
                port=service.port,
                health_markers=(),
                environment=service.environment,
            ))
            continue
        services.append(service)
    return tuple(services)


def main() -> int:
    print("JARVIS V14 autonomous execution runtime preflight...")
    quant = reclaim_obsolete_quant_listener()
    print("Quant ownership preflight:", quant.get("action"))
    master = reclaim_obsolete_master_listener()
    print("Master ownership preflight:", master.get("action"))
    completion = reclaim_obsolete_completion_listener()
    print("Completion ownership preflight:", completion.get("action"))
    print("Starting protected V8 Master + V14 continuous-EV Quant + Nautilus + V14 Completion.")
    print("Positive contextual EV can execute with uncertainty-scaled paper risk.")
    print("Live broker execution remains locked.")
    browser = str(os.getenv("JARVIS_NO_BROWSER", "0")).strip().lower() not in {"1", "true", "yes", "on"}
    return JarvisRuntimeSupervisor(
        root=ROOT,
        services=v14_services(ROOT),
        browser=browser,
    ).run_forever()


if __name__ == "__main__":
    raise SystemExit(main())
