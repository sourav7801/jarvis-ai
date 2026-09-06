"""JARVIS V6.2 runtime preflight and supervisor wrapper.

Purpose:
- refuse to adopt an old Quant listener that happens to expose the same
  JARVIS_QUANT_TERMINAL service name;
- reclaim only trusted local JARVIS processes that are serving an obsolete
  Quant surface on port 8787;
- then delegate normal lifecycle management to jarvis_runtime_supervisor.py.

This module has no broker-order surface. Trading remains paper/research only.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from scripts.jarvis_runtime_supervisor import JarvisRuntimeSupervisor


ROOT = Path(__file__).resolve().parents[1]
QUANT_HOST = "127.0.0.1"
QUANT_PORT = 8787
QUANT_BASE = f"http://{QUANT_HOST}:{QUANT_PORT}"
REQUIRED_QUANT_PATHS = (
    "/intelligence.html",
    "/lightweight-charts.standalone.production.js",
    "/adaptive_brain_runtime.js",
)


def _port_open(host: str, port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except OSError:
        return False


def _http(url: str, timeout: float = 1.5) -> tuple[int | None, bytes]:
    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "JARVIS-V6.2-Runtime-Preflight/1.0"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status), response.read(256_000)
    except urllib.error.HTTPError as exc:
        try:
            return int(exc.code), exc.read(256_000)
        except Exception:
            return int(exc.code), b""
    except (OSError, ValueError):
        return None, b""


def quant_surface_status() -> dict[str, Any]:
    health_status, health_raw = _http(QUANT_BASE + "/api/health")
    health: dict[str, Any] = {}
    if health_status == 200:
        try:
            value = json.loads(health_raw.decode("utf-8", errors="replace"))
            if isinstance(value, dict):
                health = value
        except ValueError:
            pass

    routes: dict[str, int | None] = {}
    for path in REQUIRED_QUANT_PATHS:
        status, _raw = _http(QUANT_BASE + path)
        routes[path] = status

    current = bool(
        health_status == 200
        and str(health.get("service") or "") == "JARVIS_QUANT_TERMINAL"
        and all(routes[path] == 200 for path in REQUIRED_QUANT_PATHS)
    )
    return {
        "current": current,
        "health_status": health_status,
        "service": health.get("service"),
        "version": health.get("version"),
        "status": health.get("status"),
        "routes": routes,
    }


def _powershell_json(command: str) -> Any:
    if os.name != "nt":
        return None
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        return json.loads(result.stdout)
    except ValueError:
        return None


def _listener_pids(port: int) -> list[int]:
    if os.name != "nt":
        return []
    command = (
        f"$rows=Get-NetTCPConnection -LocalPort {int(port)} -State Listen "
        "-ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique;"
        "@($rows) | ConvertTo-Json -Compress"
    )
    value = _powershell_json(command)
    if isinstance(value, int):
        return [int(value)]
    if isinstance(value, list):
        return sorted({int(item) for item in value if str(item).isdigit()})
    return []


def _process_info(pid: int) -> dict[str, Any]:
    if os.name != "nt":
        return {}
    command = (
        f"$p=Get-CimInstance Win32_Process -Filter \"ProcessId={int(pid)}\" "
        "-ErrorAction SilentlyContinue;"
        "if($p){$p | Select-Object ProcessId,Name,ExecutablePath,CommandLine | ConvertTo-Json -Compress}"
    )
    value = _powershell_json(command)
    return dict(value) if isinstance(value, dict) else {}


def _trusted_jarvis_process(info: dict[str, Any]) -> bool:
    root = str(ROOT).lower().rstrip("\\/")
    executable = str(info.get("ExecutablePath") or "").lower()
    command = str(info.get("CommandLine") or "").lower()
    approved_markers = (
        "start_jarvis_quant_terminal.py",
        "workstation.quant_terminal_v2",
        "jarvis_runtime_supervisor.py",
        "jarvis_runtime_supervisor_v62.py",
    )
    root_owned = executable.startswith(root + "\\") or root in command
    role_owned = any(marker in command for marker in approved_markers)
    return bool(root_owned and (role_owned or "\\.venv" in executable))


def _kill_tree(pid: int) -> None:
    result = subprocess.run(
        ["taskkill", "/PID", str(int(pid)), "/T", "/F"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Unable to stop stale JARVIS process PID {pid}: "
            f"{(result.stderr or result.stdout or '').strip()}"
        )


def reclaim_obsolete_quant_listener() -> dict[str, Any]:
    if not _port_open(QUANT_HOST, QUANT_PORT):
        return {"action": "NO_LISTENER", "stopped": []}

    surface = quant_surface_status()
    if surface.get("current"):
        return {"action": "CURRENT_SURFACE_PRESENT", "surface": surface, "stopped": []}

    pids = _listener_pids(QUANT_PORT)
    if not pids:
        raise RuntimeError(
            "Port 8787 is occupied by an incompatible service, but its owning PID could not be resolved. "
            "Refusing to kill an unknown process."
        )

    stopped: list[int] = []
    for pid in pids:
        if pid == os.getpid():
            continue
        info = _process_info(pid)
        if not _trusted_jarvis_process(info):
            raise RuntimeError(
                "Port 8787 is occupied by a process that cannot be proven to belong to C:\\Jarvis. "
                f"PID={pid}, Name={info.get('Name')}, Executable={info.get('ExecutablePath')}. "
                "Refusing to terminate it automatically."
            )
        print(
            "RUNTIME PREFLIGHT > stopping obsolete trusted Quant listener "
            f"PID {pid} ({info.get('ExecutablePath') or info.get('Name') or 'python'})"
        )
        _kill_tree(pid)
        stopped.append(pid)

    deadline = time.monotonic() + 8.0
    while time.monotonic() < deadline:
        if not _port_open(QUANT_HOST, QUANT_PORT):
            break
        time.sleep(0.2)
    if _port_open(QUANT_HOST, QUANT_PORT):
        raise RuntimeError("Port 8787 remained occupied after stopping the obsolete trusted listener.")

    return {"action": "OBSOLETE_LISTENER_RECLAIMED", "surface": surface, "stopped": stopped}


def main() -> int:
    print("JARVIS V6.2 runtime preflight...")
    result = reclaim_obsolete_quant_listener()
    print("Runtime preflight:", result.get("action"))
    if result.get("surface"):
        print("Previous Quant surface:", json.dumps(result["surface"], default=str))
    print("Starting supervised JARVIS services.")
    print("Paper/research mode only. Live broker execution remains locked.")
    return JarvisRuntimeSupervisor().run_forever()


if __name__ == "__main__":
    raise SystemExit(main())
