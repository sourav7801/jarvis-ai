"""Own and reconcile the local JARVIS service processes.

This launcher is deliberately limited to local process health.  It never imports
broker clients or order APIs.  Trading execution remains inside the existing
paper-only Quant boundary.
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
import webbrowser
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, TextIO


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ManagedService:
    name: str
    argv: tuple[str, ...]
    health_url: str
    expected_service: str
    port: int
    health_markers: tuple[str, ...] = ()
    environment: tuple[tuple[str, str], ...] = ()


@dataclass
class ServiceRuntime:
    process: Any | None = None
    log_handle: TextIO | None = None
    state: str = "STOPPED"
    pid: int | None = None
    last_exit_code: int | None = None
    last_ready_at: str | None = None
    next_start_at: float = 0.0
    restart_times: deque[float] = field(default_factory=deque)
    quarantined: bool = False


class JarvisRuntimeSupervisor:
    """Reconcile a bounded set of local JARVIS services.

    Existing healthy services are adopted without being killed.  Unknown
    processes occupying a JARVIS port fail closed.  Only child processes
    started by this supervisor are terminated during an intentional shutdown.
    """

    def __init__(
        self,
        *,
        root: Path | str = ROOT,
        services: Iterable[ManagedService] | None = None,
        browser: bool = True,
        poll_seconds: float = 2.0,
        restart_limit: int = 5,
        restart_window_seconds: float = 600.0,
    ) -> None:
        self.root = Path(root).resolve()
        self.services = tuple(services or default_services(self.root))
        self.browser = bool(browser)
        self.poll_seconds = max(0.25, float(poll_seconds))
        self.restart_limit = max(1, int(restart_limit))
        self.restart_window_seconds = max(10.0, float(restart_window_seconds))
        self.state_dir = self.root / "data" / "reliability" / "runtime"
        self.event_log = self.state_dir / "events.jsonl"
        self.state_path = self.state_dir / "state.json"
        self.runtime = {service.name: ServiceRuntime() for service in self.services}
        self._browser_opened = False

    @staticmethod
    def _port_open(host: str, port: int, timeout: float = 0.25) -> bool:
        try:
            with socket.create_connection((host, int(port)), timeout=timeout):
                return True
        except OSError:
            return False

    @staticmethod
    def _health_payload(url: str, timeout: float = 1.5) -> dict[str, Any] | None:
        try:
            request = urllib.request.Request(
                url,
                headers={"Accept": "application/json", "User-Agent": "JARVIS-Runtime-Supervisor/1.0"},
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read(200_000)
            payload = json.loads(raw.decode("utf-8", errors="replace"))
            return payload if isinstance(payload, dict) else None
        except (OSError, ValueError):
            return None

    @staticmethod
    def _health_page(url: str, timeout: float = 1.5) -> str | None:
        try:
            request = urllib.request.Request(
                url,
                headers={"Accept": "text/html", "User-Agent": "JARVIS-Runtime-Supervisor/1.0"},
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read(256_000)
            return raw.decode("utf-8", errors="replace")
        except (OSError, ValueError):
            return None

    def _record(self, event: str, service: ManagedService, **detail: Any) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "service": service.name,
            **detail,
        }
        with self.event_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")

    @staticmethod
    def _close_log(runtime: ServiceRuntime) -> None:
        if runtime.log_handle is not None:
            try:
                runtime.log_handle.close()
            except OSError:
                pass
            runtime.log_handle = None

    def _spawn(self, service: ManagedService, runtime: ServiceRuntime, now: float) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.state_dir / f"{service.name}.log"
        log_handle = log_path.open("a", encoding="utf-8", buffering=1)
        environment = os.environ.copy()
        environment.update(dict(service.environment))
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        try:
            process = subprocess.Popen(
                list(service.argv),
                cwd=self.root,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                creationflags=flags,
            )
        except Exception:
            log_handle.close()
            raise
        runtime.process = process
        runtime.log_handle = log_handle
        runtime.pid = int(process.pid)
        runtime.last_exit_code = None
        runtime.state = "STARTING"
        runtime.restart_times.append(now)
        runtime.next_start_at = now + self.poll_seconds
        self._record(
            "SERVICE_STARTED",
            service,
            pid=runtime.pid,
            argv=list(service.argv),
            log=str(log_path),
            paper_only=True,
            live_execution=False,
        )

    def _purge_restart_window(self, runtime: ServiceRuntime, now: float) -> None:
        cutoff = now - self.restart_window_seconds
        while runtime.restart_times and runtime.restart_times[0] < cutoff:
            runtime.restart_times.popleft()

    def _service_snapshot(self, service: ManagedService, runtime: ServiceRuntime) -> dict[str, Any]:
        return {
            "state": runtime.state,
            "pid": runtime.pid,
            "port": service.port,
            "health_url": service.health_url,
            "last_exit_code": runtime.last_exit_code,
            "last_ready_at": runtime.last_ready_at,
            "restart_count_in_window": len(runtime.restart_times),
            "quarantined": runtime.quarantined,
        }

    def _persist_snapshot(self, payload: dict[str, Any]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        temporary.replace(self.state_path)

    def reconcile_once(self, *, now: float | None = None) -> dict[str, Any]:
        tick = time.monotonic() if now is None else float(now)
        for service in self.services:
            runtime = self.runtime[service.name]
            payload = (
                self._health_payload(service.health_url)
                if service.expected_service
                else None
            )
            json_ready = bool(
                service.expected_service
                and payload
                and str(payload.get("service") or "") == service.expected_service
            )
            page_ready = False
            if service.health_markers:
                page = self._health_page(service.health_url)
                page_ready = bool(page) and all(marker in page for marker in service.health_markers)
            if json_ready or page_ready:
                owned = runtime.process is not None and runtime.process.poll() is None
                runtime.state = "READY_OWNED" if owned else "READY_EXTERNAL"
                runtime.pid = int(runtime.process.pid) if owned else None
                runtime.last_ready_at = datetime.now(timezone.utc).isoformat()
                continue

            if runtime.process is not None:
                exit_code = runtime.process.poll()
                if exit_code is None:
                    runtime.state = "STARTING"
                    continue
                runtime.last_exit_code = int(exit_code)
                self._record("SERVICE_EXITED", service, pid=runtime.pid, exit_code=runtime.last_exit_code)
                runtime.process = None
                runtime.pid = None
                self._close_log(runtime)

            if self._port_open("127.0.0.1", service.port):
                first_conflict = runtime.state != "PORT_CONFLICT"
                runtime.state = "PORT_CONFLICT"
                if first_conflict:
                    self._record(
                        "PORT_CONFLICT",
                        service,
                        port=service.port,
                        detail="Port is occupied but the expected health contract did not respond.",
                    )
                continue

            self._purge_restart_window(runtime, tick)
            if runtime.quarantined or len(runtime.restart_times) >= self.restart_limit:
                if not runtime.quarantined:
                    runtime.quarantined = True
                    self._record(
                        "SERVICE_QUARANTINED",
                        service,
                        restart_count=len(runtime.restart_times),
                        window_seconds=self.restart_window_seconds,
                    )
                runtime.state = "QUARANTINED"
                continue
            if tick < runtime.next_start_at:
                runtime.state = "BACKOFF"
                continue

            try:
                self._spawn(service, runtime, tick)
            except Exception as exc:
                runtime.state = "START_FAILED"
                runtime.next_start_at = tick + min(30.0, 2.0 ** len(runtime.restart_times))
                self._record(
                    "SERVICE_START_FAILED",
                    service,
                    error=f"{type(exc).__name__}: {exc}"[:500],
                )

        services = {
            service.name: self._service_snapshot(service, self.runtime[service.name])
            for service in self.services
        }
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "running": True,
            "services": services,
            "paper_only": True,
            "live_execution": False,
        }
        self._persist_snapshot(payload)
        return payload

    def _open_browser_when_ready(self, payload: dict[str, Any]) -> None:
        if self._browser_opened or not self.browser:
            return
        master = payload.get("services", {}).get("master", {})
        if str(master.get("state") or "").startswith("READY"):
            webbrowser.open("http://127.0.0.1:8797")
            self._browser_opened = True

    def stop_owned_services(self) -> None:
        for service in reversed(self.services):
            runtime = self.runtime[service.name]
            process = runtime.process
            if process is None or process.poll() is not None:
                self._close_log(runtime)
                continue
            self._record("SERVICE_STOP_REQUESTED", service, pid=runtime.pid)
            try:
                process.terminate()
                process.wait(timeout=5.0)
            except Exception:
                try:
                    process.kill()
                    process.wait(timeout=3.0)
                except Exception:
                    pass
            finally:
                self._close_log(runtime)

    def run_forever(self) -> int:
        print("JARVIS runtime supervisor started.")
        print("Master: http://127.0.0.1:8797")
        print("Quant:  http://127.0.0.1:8787")
        print("Mode: PAPER / RESEARCH; live execution remains locked.")
        print("Keep this window open. Press Ctrl+C to stop owned JARVIS services.")
        try:
            while True:
                payload = self.reconcile_once()
                self._open_browser_when_ready(payload)
                time.sleep(self.poll_seconds)
        except KeyboardInterrupt:
            print("\nStopping supervised JARVIS services...")
            return 0
        finally:
            self.stop_owned_services()


def default_services(root: Path = ROOT) -> tuple[ManagedService, ...]:
    python = str(Path(sys.executable).resolve())
    nautilus_python = str(os.getenv("JARVIS_NAUTILUS_PY") or python)
    candidates = (
        ManagedService(
            name="master",
            argv=(python, str(root / "start_jarvis_v3.py")),
            health_url="http://127.0.0.1:8797/",
            expected_service="",
            port=8797,
            health_markers=("JARVIS", "OMNI OPERATING COMMAND CENTER"),
            environment=(("JARVIS_NO_BROWSER", "1"),),
        ),
        ManagedService(
            name="quant",
            argv=(python, str(root / "start_jarvis_quant_terminal.py")),
            health_url="http://127.0.0.1:8787/api/health",
            expected_service="JARVIS_QUANT_TERMINAL",
            port=8787,
            environment=(("JARVIS_AUTO_PAPER_START", "1"),),
        ),
        ManagedService(
            name="nautilus",
            argv=(nautilus_python, str(root / "start_jarvis_nautilus_core.py")),
            health_url="http://127.0.0.1:8792/health",
            expected_service="JARVIS_NAUTILUS_QUANT_CORE",
            port=8792,
        ),
    )
    return tuple(service for service in candidates if Path(service.argv[-1]).exists())


def main() -> int:
    browser = str(os.getenv("JARVIS_NO_BROWSER", "0")).strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }
    return JarvisRuntimeSupervisor(browser=browser).run_forever()


if __name__ == "__main__":
    raise SystemExit(main())
