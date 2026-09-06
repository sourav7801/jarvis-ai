"""JARVIS V8 runtime wrapper.

V8 preserves the proven stale-Quant preflight and V7 service set, then adds a
Master-surface ownership check so an older 8797 process cannot masquerade as the
V8 unified intelligence OS. Only trusted C:\\Jarvis-owned Master processes may
be reclaimed. No broker or order API is imported here.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.jarvis_runtime_supervisor import (  # noqa: E402
    JarvisRuntimeSupervisor,
    ManagedService,
)
from scripts.jarvis_runtime_supervisor_v7 import v7_services  # noqa: E402
from scripts.jarvis_runtime_supervisor_v62 import (  # noqa: E402
    _http,
    _kill_tree,
    _listener_pids,
    _port_open,
    _process_info,
    reclaim_obsolete_quant_listener,
)


MASTER_HOST = "127.0.0.1"
MASTER_PORT = 8797
MASTER_BASE = f"http://{MASTER_HOST}:{MASTER_PORT}"


def master_v8_surface_status() -> dict[str, Any]:
    home_status, home_raw = _http(MASTER_BASE + "/")
    runtime_status, runtime_raw = _http(MASTER_BASE + "/v8_runtime.js")
    home = home_raw.decode("utf-8", errors="replace")
    runtime = runtime_raw.decode("utf-8", errors="replace")
    current = bool(
        home_status == 200
        and runtime_status == 200
        and "V8 UNIFIED INTELLIGENCE" in home
        and "executeWorkspaceActionsV8" in runtime
    )
    return {
        "current": current,
        "home_status": home_status,
        "runtime_status": runtime_status,
        "v8_marker": "V8 UNIFIED INTELLIGENCE" in home,
        "runtime_marker": "executeWorkspaceActionsV8" in runtime,
    }


def _trusted_master_process(info: dict[str, Any]) -> bool:
    root = str(ROOT).lower().rstrip("\\/")
    executable = str(info.get("ExecutablePath") or "").lower()
    command = str(info.get("CommandLine") or "").lower()
    root_owned = executable.startswith(root + "\\") or root in command
    markers = (
        "start_jarvis_v3.py",
        "workstation.jarvis_os_v3",
        "workstation.jarvis_os_v8",
        "jarvis_runtime_supervisor_v7",
        "jarvis_runtime_supervisor_v8",
    )
    return bool(root_owned and any(marker in command for marker in markers))


def reclaim_obsolete_master_listener() -> dict[str, Any]:
    if not _port_open(MASTER_HOST, MASTER_PORT):
        return {"action": "NO_LISTENER", "stopped": []}

    surface = master_v8_surface_status()
    if surface.get("current"):
        return {"action": "CURRENT_V8_MASTER_PRESENT", "surface": surface, "stopped": []}

    pids = _listener_pids(MASTER_PORT)
    if not pids:
        raise RuntimeError(
            "Port 8797 is occupied by a non-V8 surface, but its owning PID could not be resolved. "
            "Refusing to terminate an unknown process."
        )

    stopped: list[int] = []
    for pid in pids:
        if pid == os.getpid():
            continue
        info = _process_info(pid)
        if not _trusted_master_process(info):
            raise RuntimeError(
                "Port 8797 is occupied by a process that cannot be proven to be the JARVIS Master. "
                f"PID={pid}, Name={info.get('Name')}, Executable={info.get('ExecutablePath')}."
            )
        print(f"V8 PREFLIGHT > stopping obsolete trusted Master listener PID {pid}")
        _kill_tree(pid)
        stopped.append(pid)

    deadline = time.monotonic() + 8.0
    while time.monotonic() < deadline and _port_open(MASTER_HOST, MASTER_PORT):
        time.sleep(0.2)
    if _port_open(MASTER_HOST, MASTER_PORT):
        raise RuntimeError("Port 8797 remained occupied after stopping the obsolete trusted Master listener.")
    return {"action": "OBSOLETE_MASTER_RECLAIMED", "surface": surface, "stopped": stopped}


def v8_services(root: Path = ROOT) -> tuple[ManagedService, ...]:
    """Use the V7 service set but require V8 identity for Master adoption."""

    services: list[ManagedService] = []
    for service in v7_services(root):
        if service.name != "master":
            services.append(service)
            continue
        services.append(
            ManagedService(
                name=service.name,
                argv=service.argv,
                health_url=service.health_url,
                expected_service=service.expected_service,
                port=service.port,
                health_markers=("JARVIS", "OMNI OPERATING COMMAND CENTER", "V8 UNIFIED INTELLIGENCE"),
                environment=service.environment,
            )
        )
    return tuple(services)


def main() -> int:
    print("JARVIS V8 runtime preflight...")
    quant = reclaim_obsolete_quant_listener()
    print("Quant ownership preflight:", quant.get("action"))
    master = reclaim_obsolete_master_listener()
    print("Master ownership preflight:", master.get("action"))
    print("Starting V8 supervised services: Master, Quant, Nautilus, Completion Center.")
    print("Paper/research mode only. Live broker execution remains locked.")
    browser = str(os.getenv("JARVIS_NO_BROWSER", "0")).strip().lower() not in {
        "1", "true", "yes", "on"
    }
    return JarvisRuntimeSupervisor(
        root=ROOT,
        services=v8_services(ROOT),
        browser=browser,
    ).run_forever()


if __name__ == "__main__":
    raise SystemExit(main())
