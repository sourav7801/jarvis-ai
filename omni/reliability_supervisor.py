from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = ROOT / "data" / "reliability"
INCIDENT_LOG = STATE_DIR / "incidents.jsonl"

PROTECTED_CORE = (
    "omni/model_router.py",
    "omni/model_provider.py",
    "omni/agent_registry.py",
    "omni/collaboration_runtime.py",
    "omni/runtime.py",
    "omni/hybrid_memory.py",
)


@dataclass(frozen=True)
class ProbeResult:
    name: str
    ok: bool
    status: str
    detail: str = ""
    repairable: bool = False
    repair_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReliabilitySupervisor:
    """Bounded self-diagnosis and safe self-repair supervisor.

    V1 deliberately separates diagnosis from source-code mutation. It can repair
    only pre-approved runtime failures. Code changes remain in the existing
    Dev Agent / test / Protected-Core pipeline.
    """

    def __init__(self, root: Path | str = ROOT) -> None:
        self.root = Path(root).resolve()
        self.state_dir = self.root / "data" / "reliability"
        self.incident_log = self.state_dir / "incidents.jsonl"

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def _run(self, *args: str, timeout: float = 12.0) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(value) for value in args],
            cwd=self.root,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )

    def _git(self, *args: str) -> str:
        completed = self._run("git", *args)
        if completed.returncode != 0:
            return ""
        return completed.stdout.strip()

    @staticmethod
    def _tcp_open(host: str, port: int, timeout: float = 0.8) -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False

    @staticmethod
    def _http_json(url: str, timeout: float = 1.2) -> dict[str, Any] | None:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "JARVIS-Reliability/1.0"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read(200_000)
            value = json.loads(raw.decode("utf-8", errors="replace"))
            return value if isinstance(value, dict) else None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Probes
    # ------------------------------------------------------------------

    def probe_git(self) -> ProbeResult:
        branch = self._git("branch", "--show-current") or "UNKNOWN"
        head = self._git("rev-parse", "--short", "HEAD") or "UNKNOWN"
        status = self._git("status", "--porcelain")
        dirty = bool(status)
        return ProbeResult(
            "git",
            True,
            "DIRTY" if dirty else "CLEAN",
            f"branch={branch}; head={head}; working_tree={'dirty' if dirty else 'clean'}",
        )

    def probe_protected_core(self) -> ProbeResult:
        try:
            from omni.core_integrity import verify_protected_core

            result = verify_protected_core()
            ok = bool(getattr(result, "ok", False))
            detail = str(getattr(result, "message", "") or "")
            return ProbeResult(
                "protected_core",
                ok,
                "PASS" if ok else "FAIL",
                detail or ("Protected Core verified." if ok else "Protected Core verification failed."),
            )
        except Exception as exc:
            return ProbeResult(
                "protected_core",
                False,
                "ERROR",
                f"{type(exc).__name__}: {exc}",
            )

    def probe_ui(self) -> ProbeResult:
        open_ = self._tcp_open("127.0.0.1", 8797)
        if open_:
            return ProbeResult(
                "jarvis_ui",
                True,
                "ONLINE",
                "127.0.0.1:8797",
            )
        return ProbeResult(
            "jarvis_ui",
            True,
            "STOPPED",
            "127.0.0.1:8797 is not running.",
        )

    def probe_native_voice(self) -> ProbeResult:
        payload = self._http_json("http://127.0.0.1:8798/health")
        ok = bool(payload and payload.get("success"))
        if ok:
            detail = "Native voice control service responded on 127.0.0.1:8798."
        else:
            detail = "Native voice control service did not pass the local health probe."
        launcher = self.root / "start_jarvis_native_voice.ps1"
        return ProbeResult(
            "native_voice",
            ok,
            "ONLINE" if ok else "OFFLINE",
            detail,
            repairable=launcher.exists(),
            repair_id="restart_native_voice" if launcher.exists() else None,
        )

    def probe_service_lifecycle(self) -> ProbeResult:
        ui_online = self._tcp_open("127.0.0.1", 8797)
        voice_online = bool(
            self._http_json("http://127.0.0.1:8798/health")
        )

        if ui_online and voice_online:
            return ProbeResult(
                "service_lifecycle",
                True,
                "COORDINATED",
                "UI and native voice are both online.",
            )

        if not ui_online and not voice_online:
            return ProbeResult(
                "service_lifecycle",
                True,
                "STOPPED",
                "UI and native voice are both stopped.",
            )

        if not ui_online and voice_online:
            return ProbeResult(
                "service_lifecycle",
                False,
                "ORPHANED_VOICE",
                "Native voice is running while JARVIS UI is stopped.",
                repairable=True,
                repair_id="stop_orphan_native_voice",
            )

        return ProbeResult(
            "service_lifecycle",
            False,
            "VOICE_MISSING",
            "JARVIS UI is online but native voice is unavailable.",
            repairable=True,
            repair_id="restart_native_voice",
        )

    def probe_voice_source(self) -> ProbeResult:
        path = self.root / "workstation" / "jarvis_os_v3_assets" / "app.js"
        if not path.exists():
            return ProbeResult("voice_source", False, "MISSING", str(path))
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return ProbeResult("voice_source", False, "ERROR", str(exc))
        checks = {
            "hybrid_voice": "JARVIS_V32_HYBRID_VOICE" in text,
            "command_busy_guard": "commandInFlight" in text,
            "recognition_restart": "scheduleListen" in text,
            "stop_interrupt": "interrupt" in text and "speechSynthesis.cancel" in text,
        }
        missing = [name for name, present in checks.items() if not present]
        return ProbeResult(
            "voice_source",
            not missing,
            "PASS" if not missing else "DEGRADED",
            "markers=" + ",".join(name for name, present in checks.items() if present)
            + ("; missing=" + ",".join(missing) if missing else ""),
        )

    def probe_trading_safety(self) -> ProbeResult:
        suspicious: list[str] = []
        scan_files = (
            self.root / "workstation" / "jarvis_os_v3.py",
            self.root / "workstation" / "jarvis_os_v3_assets" / "app.js",
        )
        patterns = ("place_order(", "placeOrder(", "submit_order(", "live_order(")
        for path in scan_files:
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for pattern in patterns:
                if pattern in text:
                    suspicious.append(f"{path.name}:{pattern}")
        return ProbeResult(
            "trading_safety",
            not suspicious,
            "LOCKED" if not suspicious else "REVIEW",
            "No direct live-order call found in V3 UI boundary."
            if not suspicious
            else "Potential live-order markers: " + ", ".join(suspicious),
        )

    def probe_python_compile(self) -> ProbeResult:
        targets = [
            self.root / "workstation" / "jarvis_os_v3.py",
            self.root / "agents" / "trading_agent.py",
        ]
        targets = [path for path in targets if path.exists()]
        if not targets:
            return ProbeResult("python_compile", False, "MISSING", "No probe targets found.")
        completed = self._run(
            sys.executable,
            "-m",
            "py_compile",
            *(str(path) for path in targets),
            timeout=20,
        )
        ok = completed.returncode == 0
        return ProbeResult(
            "python_compile",
            ok,
            "PASS" if ok else "FAIL",
            (completed.stderr or completed.stdout or f"compiled {len(targets)} files").strip(),
        )

    def probes(self) -> tuple[ProbeResult, ...]:
        return (
            self.probe_git(),
            self.probe_protected_core(),
            self.probe_ui(),
            self.probe_native_voice(),
            self.probe_service_lifecycle(),
            self.probe_voice_source(),
            self.probe_trading_safety(),
            self.probe_python_compile(),
        )

    # ------------------------------------------------------------------
    # Incident persistence / learning
    # ------------------------------------------------------------------

    def _record(self, payload: dict[str, Any]) -> None:
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            with self.incident_log.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
        except OSError:
            pass

    def recent_incidents(self, limit: int = 20) -> list[dict[str, Any]]:
        if not self.incident_log.exists():
            return []
        try:
            lines = self.incident_log.read_text(encoding="utf-8").splitlines()[-max(1, min(limit, 100)) :]
        except OSError:
            return []
        result: list[dict[str, Any]] = []
        for line in lines:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                result.append(item)
        return result

    # ------------------------------------------------------------------
    # Safe repairs
    # ------------------------------------------------------------------

    def repair(self, repair_id: str) -> dict[str, Any]:
        allowlist = {
            "restart_native_voice",
            "stop_orphan_native_voice",
        }

        if repair_id not in allowlist:
            return {
                "success": False,
                "repair": repair_id,
                "message": "Repair is not in the Reliability Supervisor safe-runtime allowlist.",
            }

        if repair_id == "stop_orphan_native_voice":
            completed = self._run(
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                "Get-Process JarvisVoiceService -ErrorAction SilentlyContinue | Stop-Process -Force",
                timeout=8,
            )
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                if not self._tcp_open("127.0.0.1", 8798):
                    return {
                        "success": True,
                        "repair": repair_id,
                        "message": "Orphan native voice service stopped and port 8798 was released.",
                    }
                time.sleep(0.25)
            return {
                "success": False,
                "repair": repair_id,
                "message": (
                    "Native voice stop was attempted but port 8798 is still open. "
                    f"PowerShell return code={completed.returncode}."
                ),
            }

        launcher = self.root / "start_jarvis_native_voice.ps1"
        if not launcher.exists():
            return {"success": False, "repair": repair_id, "message": "Native voice launcher is missing."}

        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            subprocess.Popen(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(launcher),
                ],
                cwd=self.root,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
            )
        except Exception as exc:
            return {
                "success": False,
                "repair": repair_id,
                "message": f"Failed to start native voice service: {type(exc).__name__}: {exc}",
            }

        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            if self.probe_native_voice().ok:
                return {
                    "success": True,
                    "repair": repair_id,
                    "message": "Native voice service restarted and passed its local health probe.",
                }
            time.sleep(0.35)

        return {
            "success": False,
            "repair": repair_id,
            "message": "Native voice restart was attempted but the service did not become healthy in time.",
        }

    # ------------------------------------------------------------------
    # Public operations
    # ------------------------------------------------------------------

    def diagnose(self) -> dict[str, Any]:
        started = time.monotonic()
        results = self.probes()
        failures = [item for item in results if not item.ok]
        repairable = [item.repair_id for item in failures if item.repairable and item.repair_id]

        incidents = []
        for item in failures:
            severity = (
                "critical"
                if item.name in {"protected_core", "trading_safety", "python_compile"}
                else "degraded"
            )
            incidents.append(
                {
                    "component": item.name,
                    "signature": f"{item.name}:{item.status}".lower(),
                    "severity": severity,
                    "status": item.status,
                    "detail": item.detail,
                    "repairable": item.repairable,
                    "repair_id": item.repair_id,
                }
            )

        payload = {
            "success": not failures,
            "mode": "diagnose",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "duration_ms": round((time.monotonic() - started) * 1000, 1),
            "health": "HEALTHY" if not failures else "DEGRADED",
            "probes": [item.to_dict() for item in results],
            "failures": [item.name for item in failures],
            "incidents": incidents,
            "repairable": repairable,
            "protected_core": next((item.ok for item in results if item.name == "protected_core"), False),
            "live_execution": "LOCKED",
        }
        self._record(payload)
        payload["message"] = self.format_report(payload)
        return payload

    def diagnose_and_repair(self) -> dict[str, Any]:
        before = self.diagnose()
        repairs: list[dict[str, Any]] = []
        for repair_id in before.get("repairable", []):
            repairs.append(self.repair(str(repair_id)))
        after = self.diagnose()
        result = {
            "success": bool(after.get("success")),
            "mode": "repair",
            "before": before,
            "repairs": repairs,
            "after": after,
            "protected_core": after.get("protected_core", False),
            "live_execution": "LOCKED",
        }
        self._record(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "mode": "repair_result",
                "success": result["success"],
                "repairs": repairs,
                "after_failures": after.get("failures", []),
            }
        )
        result["message"] = self.format_repair_report(result)
        return result

    def improvement_plan(self) -> dict[str, Any]:
        diagnosis = self.diagnose()
        incidents = self.recent_incidents(25)
        counts: dict[str, int] = {}
        for incident in incidents:
            for failure in incident.get("failures", []) or []:
                key = str(failure)
                counts[key] = counts.get(key, 0) + 1

        priorities: list[str] = []
        if counts.get("native_voice", 0):
            priorities.append("Harden native voice startup/recovery and measure recognition availability.")
        if counts.get("voice_source", 0):
            priorities.append("Run the voice state-machine regression suite before promotion.")
        if counts.get("python_compile", 0):
            priorities.append("Block promotion until the compile failure is repaired in an isolated branch.")
        if not priorities:
            priorities.append("System baseline is stable; focus next on latency, semantic-routing accuracy, and runtime benchmarks.")

        result = {
            "success": True,
            "mode": "improvement_plan",
            "diagnosis": diagnosis,
            "incident_counts": counts,
            "priorities": priorities,
            "promotion_policy": {
                "protected_core_must_pass": True,
                "full_regression_required": True,
                "runtime_benchmark_required": True,
                "live_trading_changes_auto_promote": False,
                "credentials_auto_access": False,
            },
        }
        result["message"] = self.format_improvement_report(result)
        return result

    @staticmethod
    def format_report(payload: dict[str, Any]) -> str:
        lines = [
            "JARVIS RELIABILITY DIAGNOSTIC",
            "--------------------------------------------------",
            f"Health: {payload.get('health', 'UNKNOWN')}",
            f"Protected Core: {'PASS' if payload.get('protected_core') else 'FAIL'}",
            "Live broker execution: LOCKED",
            "",
            "PROBES",
        ]
        for probe in payload.get("probes", []):
            status = str(probe.get("status") or "")
            marker = (
                "INFO"
                if status == "STOPPED" and probe.get("ok")
                else ("PASS" if probe.get("ok") else "FAIL")
            )
            lines.append(
                f"- {probe.get('name')}: {marker} / {status} - {probe.get('detail', '')}"
            )
        repairable = payload.get("repairable", [])
        if repairable:
            lines.extend(["", "SAFE REPAIRS AVAILABLE", *[f"- {item}" for item in repairable]])
        return "\n".join(lines)

    @staticmethod
    def format_repair_report(payload: dict[str, Any]) -> str:
        after = payload.get("after", {})
        lines = [
            "JARVIS RELIABILITY SELF-REPAIR",
            "--------------------------------------------------",
        ]
        repairs = payload.get("repairs", [])
        if not repairs:
            lines.append("No allowlisted runtime repair was required or available.")
        for item in repairs:
            lines.append(f"- {item.get('repair')}: {'PASS' if item.get('success') else 'FAIL'} - {item.get('message')}")
        lines.extend(
            [
                "",
                f"Final health: {after.get('health', 'UNKNOWN')}",
                f"Protected Core: {'PASS' if after.get('protected_core') else 'FAIL'}",
                "Live broker execution: LOCKED",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def format_improvement_report(payload: dict[str, Any]) -> str:
        lines = [
            "JARVIS RELIABILITY IMPROVEMENT PLAN",
            "--------------------------------------------------",
        ]
        lines.extend(f"- {item}" for item in payload.get("priorities", []))
        lines.extend(
            [
                "",
                "Promotion gate: Protected Core + full regression + runtime benchmark.",
                "Live-trading or credential boundary changes are never auto-promoted.",
            ]
        )
        return "\n".join(lines)


reliability_supervisor = ReliabilitySupervisor()
