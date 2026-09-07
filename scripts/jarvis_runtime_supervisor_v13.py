"""JARVIS V13 adaptive intelligence runtime supervisor.

Preserves V12/V11/V8 ownership checks while requiring contextual decision
identity on active Master/Quant/Completion surfaces. Unknown processes are never
terminated. No broker order API is imported here.
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
from scripts.jarvis_runtime_supervisor_v12 import (  # noqa: E402
    MASTER_HOST,
    MASTER_PORT,
    QUANT_HOST,
    QUANT_PORT,
    QUANT_BASE,
    COMPLETION_HOST,
    COMPLETION_PORT,
    COMPLETION_BASE,
    _json_http,
    _reclaim_listener,
    _trusted_master_process as _trusted_master_process_v12,
    _trusted_completion_process as _trusted_completion_process_v12,
    master_v8_surface_status,
    v12_services,
)
from scripts.jarvis_runtime_supervisor_v62 import _port_open  # noqa: E402

MASTER_BASE = f"http://{MASTER_HOST}:{MASTER_PORT}"


def master_v13_surface_status() -> dict[str, Any]:
    v8 = master_v8_surface_status()
    authority_status, authority = _json_http(MASTER_BASE + "/api/v13/paper-authority")
    current = bool(
        v8.get("current")
        and authority_status == 200
        and authority.get("success") is True
        and authority.get("version") == "13.0"
        and authority.get("service") == "JARVIS_MASTER_V13_CONTEXTUAL_BRIDGE"
        and authority.get("contextual_bridge_installed") is True
        and authority.get("decision_authority") == "CONTEXTUAL_EXPECTED_VALUE_NOT_STATIC_SCORE"
        and authority.get("live_execution") is False
        and authority.get("automatic_broker_order") is False
    )
    return {
        "current": current,
        "v8": v8,
        "authority_status": authority_status,
        "service": authority.get("service"),
        "decision_authority": authority.get("decision_authority"),
        "contextual_bridge_installed": authority.get("contextual_bridge_installed"),
    }


def quant_v13_surface_status() -> dict[str, Any]:
    health_status, health = _json_http(QUANT_BASE + "/api/health")
    controller_status, controller = _json_http(QUANT_BASE + "/api/paper/portfolio-controller", timeout=4.0)
    mandates = controller.get("mandates") if isinstance(controller.get("mandates"), dict) else {}
    intraday = mandates.get("INTRADAY") if isinstance(mandates.get("INTRADAY"), dict) else {}
    lanes = intraday.get("lanes") if isinstance(intraday.get("lanes"), dict) else {}
    contextual = any(
        isinstance(value, dict)
        and (
            value.get("decision_authority") == "CONTEXTUAL_EXPECTED_VALUE_NOT_STATIC_SCORE"
            or (value.get("adaptive_intelligence") or {}).get("decision_authority") == "CONTEXTUAL_EXPECTED_VALUE_NOT_STATIC_SCORE"
        )
        for value in lanes.values()
    )
    if not lanes:
        contextual = intraday.get("decision_authority") == "CONTEXTUAL_EXPECTED_VALUE_NOT_STATIC_SCORE"
    current = bool(
        health_status == 200
        and str(health.get("service") or "") == "JARVIS_QUANT_TERMINAL"
        and controller_status == 200
        and controller.get("success") is True
        and contextual
        and controller.get("live_execution") is False
    )
    return {
        "current": current,
        "health_status": health_status,
        "service": health.get("service"),
        "controller_status": controller_status,
        "contextual_authority": contextual,
        "active_mandates": controller.get("active_mandates") or [],
        "paper_only": True,
        "live_execution": False,
    }


def completion_v13_surface_status() -> dict[str, Any]:
    status, payload = _json_http(COMPLETION_BASE + "/api/v13/status")
    current = bool(
        status == 200
        and payload.get("success") is True
        and payload.get("version") == "13.0"
        and payload.get("service") == "JARVIS_ADAPTIVE_INTELLIGENCE_OPERATING_SYSTEM"
        and payload.get("decision_authority") == "CONTEXTUAL_EXPECTED_VALUE_NOT_STATIC_SCORE"
        and payload.get("runtime_bridge_installed") is True
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
        "runtime_bridge_installed": payload.get("runtime_bridge_installed"),
    }


def _trusted_master_process(info: dict[str, Any]) -> bool:
    if _trusted_master_process_v12(info):
        return True
    root = str(ROOT).lower().rstrip("\\/")
    command = str(info.get("CommandLine") or "").lower()
    executable = str(info.get("ExecutablePath") or "").lower()
    return bool(
        (executable.startswith(root + "\\") or root in command)
        and ("start_jarvis_master_v13.py" in command or "jarvis_runtime_supervisor_v13" in command)
    )


def _trusted_completion_process(info: dict[str, Any]) -> bool:
    if _trusted_completion_process_v12(info):
        return True
    root = str(ROOT).lower().rstrip("\\/")
    command = str(info.get("CommandLine") or "").lower()
    executable = str(info.get("ExecutablePath") or "").lower()
    return bool(
        (executable.startswith(root + "\\") or root in command)
        and ("completion_console_v13" in command or "jarvis_runtime_supervisor_v13" in command)
    )


def reclaim_obsolete_master_listener() -> dict[str, Any]:
    surface = master_v13_surface_status() if _port_open(MASTER_HOST, MASTER_PORT) else {"current": False}
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
    from scripts.jarvis_runtime_supervisor_v62 import _trusted_jarvis_process

    surface = quant_v13_surface_status() if _port_open(QUANT_HOST, QUANT_PORT) else {"current": False}
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
    surface = completion_v13_surface_status() if _port_open(COMPLETION_HOST, COMPLETION_PORT) else {"current": False}
    result = _reclaim_listener(
        host=COMPLETION_HOST,
        port=COMPLETION_PORT,
        current=bool(surface.get("current")),
        trusted=_trusted_completion_process,
        label="COMPLETION",
    )
    result["surface"] = surface
    return result


def v13_services(root: Path = ROOT) -> tuple[ManagedService, ...]:
    python = str(Path(sys.executable).resolve())
    master_wrapper = root / "start_jarvis_master_v13.py"
    services: list[ManagedService] = []
    for service in v12_services(root):
        if service.name == "master":
            services.append(ManagedService(
                name="master",
                argv=(python, str(master_wrapper)),
                health_url=MASTER_BASE + "/api/v13/paper-authority",
                expected_service="JARVIS_MASTER_V13_CONTEXTUAL_BRIDGE",
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
            services.append(ManagedService(
                name=service.name,
                argv=service.argv,
                health_url=service.health_url,
                expected_service=service.expected_service,
                port=service.port,
                health_markers=service.health_markers,
                environment=tuple(environment.items()),
            ))
            continue
        if service.name == "completion":
            services.append(ManagedService(
                name=service.name,
                argv=service.argv,
                health_url=COMPLETION_BASE + "/api/v13/status",
                expected_service="JARVIS_ADAPTIVE_INTELLIGENCE_OPERATING_SYSTEM",
                port=service.port,
                health_markers=(),
                environment=service.environment,
            ))
            continue
        services.append(service)
    return tuple(services)


def main() -> int:
    print("JARVIS V13 adaptive intelligence runtime preflight...")
    quant = reclaim_obsolete_quant_listener()
    print("Quant ownership preflight:", quant.get("action"))
    master = reclaim_obsolete_master_listener()
    print("Master ownership preflight:", master.get("action"))
    completion = reclaim_obsolete_completion_listener()
    print("Completion ownership preflight:", completion.get("action"))
    print("Starting V13 supervised services: protected V8 Master, contextual Quant, Nautilus, V13 Completion.")
    print("Contextual expected-value paper intelligence enabled; scores remain observability only.")
    print("Live broker execution remains locked.")
    browser = str(os.getenv("JARVIS_NO_BROWSER", "0")).strip().lower() not in {"1", "true", "yes", "on"}
    return JarvisRuntimeSupervisor(
        root=ROOT,
        services=v13_services(ROOT),
        browser=browser,
    ).run_forever()


if __name__ == "__main__":
    raise SystemExit(main())
