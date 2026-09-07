"""JARVIS V12 runtime wrapper.

Preserves V6.2 Quant ownership protection, V8 Master identity checks and V11
Completion trust rules, then requires the V12 Adaptive Market Intelligence
identity on port 8799. Unknown processes are never terminated. No broker/order
API is imported or exposed here.
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
from scripts.jarvis_runtime_supervisor_v8 import (  # noqa: E402
    reclaim_obsolete_master_listener,
    v8_services,
)
from scripts.jarvis_runtime_supervisor_v62 import (  # noqa: E402
    _http,
    _kill_tree,
    _listener_pids,
    _port_open,
    _process_info,
    reclaim_obsolete_quant_listener,
)

COMPLETION_HOST = "127.0.0.1"
COMPLETION_PORT = 8799
COMPLETION_BASE = f"http://{COMPLETION_HOST}:{COMPLETION_PORT}"


def completion_v12_surface_status() -> dict[str, Any]:
    status, raw = _http(COMPLETION_BASE + "/api/v12/status")
    payload: dict[str, Any] = {}
    if status == 200:
        try:
            parsed = json.loads(raw.decode("utf-8", errors="replace"))
            payload = parsed if isinstance(parsed, dict) else {}
        except ValueError:
            payload = {}
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
        "paper_only": payload.get("paper_only"),
        "live_execution": payload.get("live_execution"),
    }


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


def reclaim_obsolete_completion_listener() -> dict[str, Any]:
    if not _port_open(COMPLETION_HOST, COMPLETION_PORT):
        return {"action": "NO_LISTENER", "stopped": []}

    surface = completion_v12_surface_status()
    if surface.get("current"):
        return {"action": "CURRENT_V12_COMPLETION_PRESENT", "surface": surface, "stopped": []}

    pids = _listener_pids(COMPLETION_PORT)
    if not pids:
        raise RuntimeError(
            "Port 8799 is occupied by a non-V12 surface, but its owning PID could not be resolved. "
            "Refusing to terminate an unknown process."
        )

    stopped: list[int] = []
    for pid in pids:
        if pid == os.getpid():
            continue
        info = _process_info(pid)
        if not _trusted_completion_process(info):
            raise RuntimeError(
                "Port 8799 is occupied by a process that cannot be proven to be the JARVIS Completion Center. "
                f"PID={pid}, Name={info.get('Name')}, Executable={info.get('ExecutablePath')}."
            )
        print(f"V12 PREFLIGHT > stopping obsolete trusted Completion listener PID {pid}")
        _kill_tree(pid)
        stopped.append(pid)

    deadline = time.monotonic() + 8.0
    while time.monotonic() < deadline and _port_open(COMPLETION_HOST, COMPLETION_PORT):
        time.sleep(0.2)
    if _port_open(COMPLETION_HOST, COMPLETION_PORT):
        raise RuntimeError("Port 8799 remained occupied after stopping the obsolete trusted Completion listener.")
    return {"action": "OBSOLETE_COMPLETION_RECLAIMED", "surface": surface, "stopped": stopped}


def v12_services(root: Path = ROOT) -> tuple[ManagedService, ...]:
    services: list[ManagedService] = []
    for service in v8_services(root):
        if service.name != "completion":
            services.append(service)
            continue
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
    return tuple(services)


def main() -> int:
    print("JARVIS V12 runtime preflight...")
    quant = reclaim_obsolete_quant_listener()
    print("Quant ownership preflight:", quant.get("action"))
    master = reclaim_obsolete_master_listener()
    print("Master ownership preflight:", master.get("action"))
    completion = reclaim_obsolete_completion_listener()
    print("Completion ownership preflight:", completion.get("action"))
    print("Starting V12 supervised services: Master, Quant, Nautilus, Completion Center.")
    print("Adaptive expected-value paper intelligence enabled. Static score thresholds are not execution authority.")
    print("Governed local actions + paper/research only. Live broker execution remains locked.")
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
