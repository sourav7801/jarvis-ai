"""Bounded system diagnostics and self-repair proposals for JARVIS V10.

Diagnostics observe loopback services, repository/runtime state, mission leases
and storage pressure. They never kill unknown processes or perform destructive
recovery. Only explicitly enumerated reversible internal recoveries are
executable here.
"""
from __future__ import annotations

import json
import shutil
import socket
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_STATE = ROOT / "data" / "reliability" / "runtime" / "state.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=0.35):
            return True
    except OSError:
        return False


def _http_json(url: str) -> dict[str, Any] | None:
    try:
        request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "JARVIS-V10-Diagnostics"})
        with urllib.request.urlopen(request, timeout=1.5) as response:
            raw = response.read(250_000)
        value = json.loads(raw.decode("utf-8", errors="replace"))
        return value if isinstance(value, dict) else None
    except Exception:
        return None


def _runtime_snapshot() -> dict[str, Any]:
    try:
        value = json.loads(RUNTIME_STATE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (FileNotFoundError, OSError, ValueError, TypeError):
        return {}


class SystemDiagnostics:
    SERVICES = (
        ("master", 8797, "http://127.0.0.1:8797/api/health"),
        ("quant", 8787, "http://127.0.0.1:8787/api/health"),
        ("completion", 8799, "http://127.0.0.1:8799/api/health"),
    )

    def inspect(self) -> dict[str, Any]:
        services: list[dict[str, Any]] = []
        incidents: list[dict[str, Any]] = []
        proposals: list[dict[str, Any]] = []
        for name, port, health_url in self.SERVICES:
            open_ = _port_open(port)
            health = _http_json(health_url) if open_ else None
            expected = str((health or {}).get("service") or "")
            healthy = bool(open_ and health and (expected or (health or {}).get("healthy") is True))
            state = "READY" if healthy else ("PORT_CONFLICT_OR_WRONG_SERVICE" if open_ else "DOWN")
            row = {
                "name": name,
                "port": port,
                "health_url": health_url,
                "port_open": open_,
                "healthy": healthy,
                "state": state,
                "reported_service": expected or None,
            }
            services.append(row)
            if not healthy:
                incident = {
                    "incident_id": f"service:{name}",
                    "kind": "SERVICE_HEALTH",
                    "severity": "HIGH" if name in {"master", "quant"} else "MEDIUM",
                    "state": state,
                    "detail": f"{name} is not answering its expected loopback health contract.",
                }
                incidents.append(incident)
                proposals.append({
                    "proposal_id": f"recover:{name}",
                    "action": "RESTART_JARVIS_SUPERVISOR" if not open_ else "INVESTIGATE_PORT_OWNER",
                    "target": name,
                    "automatic": False,
                    "reason": "Unknown processes must never be killed; supervisor restart is operator-governed.",
                    "risk": "LOW" if not open_ else "MEDIUM",
                })

        usage = shutil.disk_usage(ROOT)
        free_fraction = usage.free / max(usage.total, 1)
        disk = {
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "free_fraction": round(free_fraction, 4),
            "state": "READY" if free_fraction >= 0.08 else "PRESSURE",
        }
        if free_fraction < 0.08:
            incidents.append({
                "incident_id": "storage:root",
                "kind": "DISK_PRESSURE",
                "severity": "HIGH" if free_fraction < 0.03 else "MEDIUM",
                "state": "PRESSURE",
                "detail": "Repository volume has low free space.",
            })
            proposals.append({
                "proposal_id": "storage:cleanup",
                "action": "REVIEW_JARVIS_CACHE_AND_LOG_RETENTION",
                "target": str(ROOT),
                "automatic": False,
                "reason": "Deletion is not performed automatically.",
                "risk": "MEDIUM",
            })

        queue_snapshot: dict[str, Any] = {}
        try:
            from omni.mission_queue import MISSION_QUEUE
            recovered = MISSION_QUEUE.recover_expired_leases()
            queue_snapshot = MISSION_QUEUE.snapshot(limit=30)
            if recovered:
                incidents.append({
                    "incident_id": "missions:expired-leases",
                    "kind": "MISSION_RECOVERY",
                    "severity": "LOW",
                    "state": "RECOVERED",
                    "detail": f"Recovered {recovered} expired mission lease(s) back to the queue.",
                })
        except Exception as exc:
            queue_snapshot = {"success": False, "error_type": type(exc).__name__}

        runtime = _runtime_snapshot()
        result = {
            "success": True,
            "version": "10.0",
            "generated_at": _now(),
            "services": services,
            "disk": disk,
            "mission_queue": queue_snapshot,
            "runtime_supervisor": runtime,
            "incidents": incidents,
            "recovery_proposals": proposals,
            "overall": "READY" if not [i for i in incidents if i.get("severity") in {"HIGH", "MEDIUM"} and i.get("state") != "RECOVERED"] else "DEGRADED",
            "automatic_repair_scope": ["RECOVER_EXPIRED_MISSION_LEASES", "REFRESH_WORLD_MODEL"],
            "unknown_process_termination": False,
            "external_actions": "APPROVAL_GATED",
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }
        try:
            from omni.cognitive_event_bus import COGNITIVE_EVENT_BUS, CognitiveEventType
            for incident in incidents[:20]:
                event = CognitiveEventType.SERVICE_RECOVERED if incident.get("state") == "RECOVERED" else CognitiveEventType.SERVICE_DEGRADED
                COGNITIVE_EVENT_BUS.publish(
                    event,
                    source="system_diagnostics",
                    subject=str(incident.get("incident_id")),
                    payload=incident,
                    provenance={"scope": "JARVIS_LOCAL_SYSTEM", "observation_only": True},
                )
        except Exception:
            pass
        return result

    def apply_safe_recovery(self, action: str) -> dict[str, Any]:
        normalized = str(action or "").strip().upper()
        if normalized == "RECOVER_EXPIRED_MISSION_LEASES":
            from omni.mission_queue import MISSION_QUEUE
            count = MISSION_QUEUE.recover_expired_leases()
            return {
                "success": True,
                "action": normalized,
                "recovered": count,
                "destructive": False,
                "external_action": False,
            }
        if normalized == "REFRESH_WORLD_MODEL":
            from omni.world_model import WORLD_MODEL
            return {
                "success": True,
                "action": normalized,
                "result": WORLD_MODEL.refresh_local(),
                "destructive": False,
                "external_action": False,
            }
        raise PermissionError("Only explicitly bounded reversible internal recovery actions are available.")

    def status(self) -> dict[str, Any]:
        payload = self.inspect()
        return {
            "success": True,
            "version": "10.0",
            "service": "JARVIS_SYSTEM_DIAGNOSTICS",
            "overall": payload["overall"],
            "incidents": payload["incidents"],
            "recovery_proposals": payload["recovery_proposals"],
            "automatic_repair_scope": payload["automatic_repair_scope"],
            "unknown_process_termination": False,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }


SYSTEM_DIAGNOSTICS = SystemDiagnostics()

__all__ = ["SYSTEM_DIAGNOSTICS", "SystemDiagnostics"]
