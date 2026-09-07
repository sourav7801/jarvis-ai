"""JARVIS V12 adaptive runtime supervisor.

V12 preserves the protected V8 Master identity and all V11 completed-bar /
execution-mesh surfaces, but refuses to silently adopt an older Quant or
Completion listener that lacks V12 adaptive expected-value authority. Unknown
processes are never terminated. No broker order API is imported here.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.jarvis_runtime_supervisor import JarvisRuntimeSupervisor, ManagedService  # noqa: E402
from scripts.jarvis_runtime_supervisor_v8 import master_v8_surface_status  # noqa: E402
from scripts.jarvis_runtime_supervisor_v11 import v11_services  # noqa: E402
from scripts.jarvis_runtime_supervisor_v62 import (  # noqa: E402
    _http,
    _kill_tree,
    _listener_pids,
    _port_open,
    _process_info,
    _trusted_jarvis_process,
)

MASTER_HOST = "127.0.0.1"
MASTER_PORT = 8797
QUANT_HOST = "127.0.0.1"
QUANT_PORT = 8787
QUANT_BASE = f"http://{QUANT_HOST}:{QUANT_PORT}"
COMPLETION_HOST = "127.0.0.1"
COMPLETION_PORT = 8799
COMPLETION_BASE = f"http://{COMPLETION_HOST}:{COMPLETION_PORT}"


def _json_http(url: str, timeout: float = 2.0) -> tuple[int | None, dict[str, Any]]:
    status, raw = _http(url, timeout=timeout)
    payload: dict[str, Any] = {}
    if status == 200:
        try:
            parsed = json.loads(raw.decode("utf-8", errors="replace"))
            payload = parsed if isinstance(parsed, dict) else {}
        except ValueError:
            payload = {}
    return status, payload


def quant_v12_surface_status() -> dict[str, Any]:
    """Require adaptive controller identity, not just the legacy service name."""

    health_status, health = _json_http(QUANT_BASE + "/api/health")
    controller_status, controller = _json_http(
        QUANT_BASE + "/api/paper/portfolio-controller",
        timeout=3.0,
    )
    mandates = controller.get("mandates") if isinstance(controller.get("mandates"), dict) else {}
    intraday = mandates.get("INTRADAY") if isinstance(mandates.get("INTRADAY"), dict) else {}
    current = bool(
        health_status == 200
        and str(health.get("service") or "") == "JARVIS_QUANT_TERMINAL"
        and controller_status == 200
        and controller.get("success") is True
        and controller.get("decision_authority") == "ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE"
        and controller.get("live_execution") is False
        and intraday.get("decision_authority") == "ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE"
        and intraday.get("live_execution") is False
    )
    return {
        "current": current,
        "health_status": health_status,
        "service": health.get("service"),
        "controller_status": controller_status,
        "decision_authority": controller.get("decision_authority"),
        "active_mandates": controller.get("active_mandates") or [],
        "intraday_profile": intraday.get("advanced_profile") or intraday.get("profile"),
    }


def completion_v12_surface_status() -> dict[str, Any]:
    status, payload = _json_http(COMPLETION_BASE + "/api/v12/status")
    current = bool(
        status == 200
        and payload.get("success") is True
        and payload.get("version") == "12.0"
        and payload.get("service") == "JARVIS_ADAPTIVE_MARKET_INTELLIGENCE"
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
        "permanent_agents": payload.get("permanent_agents"),
    }


def _trusted_master_process(info: dict[str, Any]) -> bool:
    root = str(ROOT).lower().rstrip("\\/")
    executable = str(info.get("ExecutablePath") or "").lower()
    command = str(info.get("CommandLine") or "").lower()
    root_owned = executable.startswith(root + "\\") or root in command
    markers = (
        "start_jarvis_master_v12.py",
        "start_jarvis_v3.py",
        "workstation.jarvis_os_v8",
        "jarvis_runtime_supervisor_v12",
        "jarvis_runtime_supervisor_v11",
        "jarvis_runtime_supervisor_v8",
    )
    return bool(root_owned and any(marker in command for marker in markers))


def _trusted_completion_process(info: dict[str, Any]) -> bool:
    root = str(ROOT).lower().rstrip("\\/")
    executable = str(info.get("ExecutablePath") or "").lower()
    command = str(info.get("CommandLine") or "").lower()
    root_owned = executable.startswith(root + "\\") or root in command
    markers = (
        "start_jarvis_completion_console.py",
        "workstation.completion_console",
        "completion_console_v10",
        "completion_console_v11",
        "completion_console_v12",
        "jarvis_runtime_supervisor_v7",
        "jarvis_runtime_supervisor_v8",
        "jarvis_runtime_supervisor_v11",
        "jarvis_runtime_supervisor_v12",
    )
    return bool(root_owned and any(marker in command for marker in markers))


def _reclaim_listener(
    *,
    host: str,
    port: int,
    current: bool,
    trusted,
    label: str,
) -> dict[str, Any]:
    if not _port_open(host, port):
        return {"action": "NO_LISTENER", "stopped": []}
    if current:
        return {"action": f"CURRENT_V12_{label}_PRESENT", "stopped": []}

    pids = _listener_pids(port)
    if not pids:
        raise RuntimeError(
            f"Port {port} is occupied by a non-V12 {label} surface, but its owning PID could not be resolved. "
            "Refusing to terminate an unknown process."
        )

    stopped: list[int] = []
    for pid in pids:
        if pid == os.getpid():
            continue
        info = _process_info(pid)
        if not trusted(info):
            raise RuntimeError(
                f"Port {port} is occupied by a process that cannot be proven to be the JARVIS {label}. "
                f"PID={pid}, Name={info.get('Name')}, Executable={info.get('ExecutablePath')}."
            )
        print(f"V12 PREFLIGHT > stopping obsolete trusted {label} listener PID {pid}")
        _kill_tree(pid)
        stopped.append(pid)

    deadline = time.monotonic() + 8.0
    while time.monotonic() < deadline and _port_open(host, port):
        time.sleep(0.2)
    if _port_open(host, port):
        raise RuntimeError(f"Port {port} remained occupied after stopping obsolete trusted {label} listener.")
    return {"action": f"OBSOLETE_{label}_RECLAIMED", "stopped": stopped}


def reclaim_obsolete_master_listener() -> dict[str, Any]:
    surface = master_v8_surface_status() if _port_open(MASTER_HOST, MASTER_PORT) else {"current": False}
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
    surface = quant_v12_surface_status() if _port_open(QUANT_HOST, QUANT_PORT) else {"current": False}
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
    surface = completion_v12_surface_status() if _port_open(COMPLETION_HOST, COMPLETION_PORT) else {"current": False}
    result = _reclaim_listener(
        host=COMPLETION_HOST,
        port=COMPLETION_PORT,
        current=bool(surface.get("current")),
        trusted=_trusted_completion_process,
        label="COMPLETION",
    )
    result["surface"] = surface
    return result


def v12_services(root: Path = ROOT) -> tuple[ManagedService, ...]:
    python = str(Path(sys.executable).resolve())
    master_wrapper = root / "start_jarvis_master_v12.py"
    services: list[ManagedService] = []
    for service in v11_services(root):
        if service.name == "master":
            services.append(
                ManagedService(
                    name="master",
                    argv=(python, str(master_wrapper)),
                    health_url=service.health_url,
                    expected_service=service.expected_service,
                    port=service.port,
                    health_markers=service.health_markers,
                    environment=service.environment,
                )
            )
            continue
        if service.name == "quant":
            environment = dict(service.environment)
            environment["JARVIS_AUTO_PAPER_START"] = "0"
            environment["JARVIS_V12_AUTO_PAPER_START"] = "1"
            services.append(
                ManagedService(
                    name=service.name,
                    argv=service.argv,
                    health_url=service.health_url,
                    expected_service=service.expected_service,
                    port=service.port,
                    health_markers=service.health_markers,
                    environment=tuple(environment.items()),
                )
            )
            continue
        if service.name == "completion":
            services.append(
                ManagedService(
                    name=service.name,
                    argv=service.argv,
                    health_url=COMPLETION_BASE + "/api/v12/status",
                    expected_service="JARVIS_ADAPTIVE_MARKET_INTELLIGENCE",
                    port=service.port,
                    health_markers=(),
                    environment=service.environment,
                )
            )
            continue
        services.append(service)
    return tuple(services)


def main() -> int:
    print("JARVIS V12 adaptive runtime preflight...")
    quant = reclaim_obsolete_quant_listener()
    print("Quant ownership preflight:", quant.get("action"))
    master = reclaim_obsolete_master_listener()
    print("Master ownership preflight:", master.get("action"))
    completion = reclaim_obsolete_completion_listener()
    print("Completion ownership preflight:", completion.get("action"))
    print("Starting V12 supervised services: protected V8 Master, adaptive Quant, Nautilus, V12 Completion.")
    print("Paper/research only. Static 67/68/70 score gates are observability only.")
    print("Live broker execution remains locked.")
    browser = str(os.getenv("JARVIS_NO_BROWSER", "0")).strip().lower() not in {
        "1", "true", "yes", "on"
    }
    return JarvisRuntimeSupervisor(
        root=ROOT,
        services=v12_services(ROOT),
        browser=browser,
    ).run_forever()


if __name__ == "__main__":
    raise SystemExit(main())
