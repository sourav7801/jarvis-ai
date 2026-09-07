"""JARVIS V8/V9 Project Completion / Executive Center.

A loopback-only operator console for repository completion, runtime posture,
approvals, mission queue, executive planning, code intelligence, memory, model
telemetry, market events and governed strategy research. It contains no
broker-order surface.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import urllib.parse
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Callable

from config import HYBRID_MEMORY_DB, MISSION_STATE_FILE
from omni.loopback_http import exclusive_server
from omni.service_health_contract import ServiceHealthClock
from omni.subsystem_snapshot import SubsystemSnapshotCollector, sanitize_error


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "workstation" / "completion_console_static"
HOST = os.getenv("JARVIS_COMPLETION_HOST", "127.0.0.1").strip()
PORT = int(os.getenv("JARVIS_COMPLETION_PORT", "8799"))
HEALTH = ServiceHealthClock("JARVIS_COMPLETION_CENTER", "8.0")
SNAPSHOTS = SubsystemSnapshotCollector(max_inflight=8)
_APPROVAL_ID = re.compile(r"^approval-[0-9a-f]{16}$")


def _safe_call(name: str, function: Callable[[], Any]) -> dict[str, Any]:
    """Compatibility helper used by older Completion Center consumers."""

    try:
        value = function()
        return {"success": True, "name": name, "data": value}
    except Exception as exc:
        return {
            "success": False,
            "name": name,
            "error": f"{type(exc).__name__}: {sanitize_error(exc)}"[:500],
        }


def _memory_snapshot() -> dict[str, Any]:
    path = Path(HYBRID_MEMORY_DB)
    result = {
        "exists": path.exists(),
        "database": str(path),
        "records": 0,
        "bytes": path.stat().st_size if path.exists() else 0,
        "read_only_snapshot": True,
    }
    if not path.exists():
        return result
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=3)
    try:
        row = connection.execute("SELECT COUNT(*) FROM memories").fetchone()
        result["records"] = int(row[0]) if row else 0
        kinds = connection.execute(
            "SELECT kind, COUNT(*) AS count FROM memories GROUP BY kind ORDER BY count DESC"
        ).fetchall()
        result["kinds"] = {str(kind): int(count) for kind, count in kinds}
    finally:
        connection.close()
    return result


def _mission_state() -> dict[str, Any]:
    path = Path(MISSION_STATE_FILE)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            latest = dict(value.get("latest_mission") or {})
            return {
                "mission_count": len(value.get("missions") or []),
                "latest_id": latest.get("id"),
                "latest_title": latest.get("title"),
                "latest_status": latest.get("status"),
                "selected_agents": latest.get("selected_agents") or [],
                "approval_locks": latest.get("approval_locks") or [],
            }
    except (FileNotFoundError, OSError, ValueError, TypeError):
        pass
    return {"mission_count": 0, "latest_id": None, "latest_status": "READY"}


# Overview providers are deliberately lazy.  Import or runtime failure in one
# subsystem is captured by SubsystemSnapshotCollector instead of preventing the
# rest of the Completion Center from rendering.
def _completion_provider() -> Any:
    from omni.project_completion import snapshot
    return snapshot()


def _workspaces_provider() -> Any:
    from omni.workspace_command_center import snapshot
    return snapshot()


def _executive_provider() -> Any:
    from omni.executive_control_plane import EXECUTIVE_CONTROL_PLANE
    return EXECUTIVE_CONTROL_PLANE.status()


def _approvals_provider() -> Any:
    from omni.approval_queue import approval_queue
    return {
        "pending": list(approval_queue.pending()),
        "external_actions": "APPROVAL_GATED",
    }


def _mission_queue_provider() -> Any:
    from omni.mission_queue import MISSION_QUEUE
    return MISSION_QUEUE.snapshot()


def _code_provider() -> Any:
    from omni.code_intelligence import CODE_INTELLIGENCE
    return CODE_INTELLIGENCE.snapshot(include_records=False)


def _model_router_provider() -> Any:
    from omni.model_router_telemetry import MODEL_ROUTER_TELEMETRY
    return MODEL_ROUTER_TELEMETRY.status()


def _market_events_provider() -> Any:
    from workstation.market_event_bus import MARKET_EVENT_BUS
    return MARKET_EVENT_BUS.snapshot(limit=25)


def _strategy_provider() -> Any:
    from omni.trading_intelligence.champion_challenger import CHAMPION_CHALLENGER
    return CHAMPION_CHALLENGER.snapshot(limit=30)


def _overview_providers() -> dict[str, Callable[[], Any]]:
    return {
        "completion": _completion_provider,
        "workspaces": _workspaces_provider,
        "executive": _executive_provider,
        "approvals": _approvals_provider,
        "missions": _mission_state,
        "mission_queue": _mission_queue_provider,
        "code_intelligence": _code_provider,
        "memory": _memory_snapshot,
        "model_router": _model_router_provider,
        "market_events": _market_events_provider,
        "strategy_governance": _strategy_provider,
    }


def _subsystem_data(subsystems: dict[str, dict[str, Any]], name: str) -> Any:
    record = subsystems.get(name) or {}
    return record.get("data") if record.get("healthy") else None


def overview_payload() -> dict[str, Any]:
    subsystems = SNAPSHOTS.collect(_overview_providers(), timeout=2.0)
    overall = "READY" if subsystems and all(row.get("healthy") for row in subsystems.values()) else "DEGRADED"

    # Preserve the historical top-level fields while adding per-subsystem health.
    # Memory historically returned a safe-call envelope, so expose the new richer
    # envelope there while the other fields keep their raw-data shape.
    return {
        "success": True,
        "service": "JARVIS_COMPLETION_CENTER",
        "version": "8.0",
        "overall": overall,
        "subsystems": subsystems,
        "completion": _subsystem_data(subsystems, "completion"),
        "workspaces": _subsystem_data(subsystems, "workspaces"),
        "executive": _subsystem_data(subsystems, "executive"),
        "approvals": _subsystem_data(subsystems, "approvals"),
        "missions": _subsystem_data(subsystems, "missions"),
        "mission_queue": _subsystem_data(subsystems, "mission_queue"),
        "code_intelligence": _subsystem_data(subsystems, "code_intelligence"),
        "memory": subsystems.get("memory"),
        "model_router": _subsystem_data(subsystems, "model_router"),
        "market_events": _subsystem_data(subsystems, "market_events"),
        "strategy_governance": _subsystem_data(subsystems, "strategy_governance"),
        "safety": {
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
            "automatic_production_strategy_rewrite": False,
            "external_actions": "APPROVAL_GATED",
        },
    }


class CompletionHandler(BaseHTTPRequestHandler):
    server_version = "JARVISCompletion/8.0"

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def send_json(self, payload: Any, status: int = 200) -> None:
        raw = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def send_file(self, path: Path, content_type: str) -> None:
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(STATIC.resolve())
            raw = resolved.read_bytes()
        except (FileNotFoundError, OSError, ValueError):
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body(self) -> dict[str, Any]:
        try:
            length = min(max(int(self.headers.get("Content-Length", "0")), 0), 100_000)
            value = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            return dict(value) if isinstance(value, dict) else {}
        except (ValueError, TypeError):
            return {}

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)
        if path == "/":
            return self.send_file(STATIC / "index.html", "text/html; charset=utf-8")
        if path == "/app.js":
            return self.send_file(STATIC / "app.js", "application/javascript; charset=utf-8")
        if path == "/style.css":
            return self.send_file(STATIC / "style.css", "text/css; charset=utf-8")
        if path == "/api/health":
            HEALTH.mark_success()
            return self.send_json(
                HEALTH.payload(
                    status="READY",
                    healthy=True,
                    dependencies={"repository": "READY", "executive_control_plane": "READY"},
                    completion_center=True,
                    executive_control_plane=True,
                    engine_ready=True,
                )
            )
        if path == "/api/overview":
            try:
                payload = overview_payload()
                if payload.get("overall") == "READY":
                    HEALTH.mark_success()
                return self.send_json(payload)
            except Exception as exc:
                # This is reserved for failure of the aggregation boundary itself;
                # individual subsystem failures are already isolated and remain 200.
                HEALTH.mark_error(exc)
                return self.send_json(
                    {
                        "success": False,
                        "message": f"{type(exc).__name__}: {sanitize_error(exc)}"[:500],
                        "paper_only": True,
                        "live_execution": False,
                    },
                    500,
                )
        if path == "/api/completion":
            from omni.project_completion import snapshot
            return self.send_json(snapshot())
        if path == "/api/executive":
            from omni.executive_control_plane import EXECUTIVE_CONTROL_PLANE
            return self.send_json(EXECUTIVE_CONTROL_PLANE.status())
        if path == "/api/executive/plan":
            from omni.executive_control_plane import EXECUTIVE_CONTROL_PLANE
            text = str((params.get("text") or [""])[0]).strip()
            if not text:
                return self.send_json({"success": False, "message": "text required"}, 400)
            return self.send_json(EXECUTIVE_CONTROL_PLANE.plan(text))
        if path == "/api/code":
            from omni.code_intelligence import CODE_INTELLIGENCE
            query = str((params.get("q") or [""])[0])
            if query:
                return self.send_json({"success": True, "query": query, "results": CODE_INTELLIGENCE.search(query)})
            return self.send_json(CODE_INTELLIGENCE.snapshot(include_records=False))
        if path == "/api/model-router":
            from omni.model_router_telemetry import MODEL_ROUTER_TELEMETRY
            return self.send_json(MODEL_ROUTER_TELEMETRY.status())
        if path == "/api/mission-queue":
            from omni.mission_queue import MISSION_QUEUE
            return self.send_json(MISSION_QUEUE.snapshot())
        if path == "/api/market-events":
            from workstation.market_event_bus import MARKET_EVENT_BUS
            return self.send_json(MARKET_EVENT_BUS.snapshot(limit=100))
        if path == "/api/strategy-governance":
            from omni.trading_intelligence.champion_challenger import CHAMPION_CHALLENGER
            return self.send_json(CHAMPION_CHALLENGER.snapshot())
        if path == "/api/approvals":
            from omni.approval_queue import approval_queue
            return self.send_json(
                {
                    "success": True,
                    "pending": list(approval_queue.pending()),
                    "automatic_approval": False,
                    "external_execution": False,
                }
            )
        if path == "/api/memory":
            return self.send_json(_memory_snapshot())
        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._body()
        if path in {"/api/approvals/approve", "/api/approvals/reject"}:
            from omni.approval_queue import approval_queue
            approval_id = str(body.get("approval_id") or "").strip()
            if not _APPROVAL_ID.fullmatch(approval_id):
                return self.send_json({"success": False, "message": "Invalid approval ID."}, 400)
            try:
                record = (
                    approval_queue.approve(approval_id)
                    if path.endswith("/approve")
                    else approval_queue.reject(approval_id)
                )
                return self.send_json(
                    {
                        "success": True,
                        "record": record,
                        "consumed": False,
                        "external_action_executed": False,
                    }
                )
            except (KeyError, RuntimeError, PermissionError) as exc:
                return self.send_json({"success": False, "message": sanitize_error(exc)[:400]}, 409)
        self.send_error(404)


def main() -> int:
    server = exclusive_server(HOST, PORT, CompletionHandler)
    print("=" * 72)
    print("JARVIS V8/V9 PROJECT COMPLETION / EXECUTIVE CENTER")
    print("=" * 72)
    print(f"Console: http://{HOST}:{PORT}")
    print("Mode: LOCAL / GOVERNED / PAPER-RESEARCH")
    print("Live broker execution: LOCKED")
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
