"""JARVIS V7 Project Completion Center.

A loopback-only operator console for repository completion, runtime posture,
approvals, mission queue, code intelligence, memory, model telemetry, market
events and governed strategy research.  It contains no broker-order surface.
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


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "workstation" / "completion_console_static"
HOST = os.getenv("JARVIS_COMPLETION_HOST", "127.0.0.1").strip()
PORT = int(os.getenv("JARVIS_COMPLETION_PORT", "8799"))
HEALTH = ServiceHealthClock("JARVIS_COMPLETION_CENTER", "7.0")
_APPROVAL_ID = re.compile(r"^approval-[0-9a-f]{16}$")


def _safe_call(name: str, function: Callable[[], Any]) -> dict[str, Any]:
    try:
        value = function()
        return {"success": True, "name": name, "data": value}
    except Exception as exc:
        return {
            "success": False,
            "name": name,
            "error": f"{type(exc).__name__}: {exc}"[:500],
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


def overview_payload() -> dict[str, Any]:
    from omni.project_completion import snapshot as completion_snapshot
    from omni.workspace_command_center import snapshot as workspace_snapshot
    from omni.code_intelligence import CODE_INTELLIGENCE
    from omni.model_router_telemetry import MODEL_ROUTER_TELEMETRY
    from omni.mission_queue import MISSION_QUEUE
    from omni.approval_queue import approval_queue
    from omni.trading_intelligence.champion_challenger import CHAMPION_CHALLENGER
    from workstation.market_event_bus import MARKET_EVENT_BUS

    return {
        "success": True,
        "service": "JARVIS_COMPLETION_CENTER",
        "version": "7.0",
        "completion": completion_snapshot(),
        "workspaces": workspace_snapshot(),
        "approvals": {
            "pending": list(approval_queue.pending()),
            "external_actions": "APPROVAL_GATED",
        },
        "missions": _mission_state(),
        "mission_queue": MISSION_QUEUE.snapshot(),
        "code_intelligence": CODE_INTELLIGENCE.snapshot(include_records=False),
        "memory": _safe_call("memory", _memory_snapshot),
        "model_router": MODEL_ROUTER_TELEMETRY.status(),
        "market_events": MARKET_EVENT_BUS.snapshot(limit=25),
        "strategy_governance": CHAMPION_CHALLENGER.snapshot(limit=30),
        "safety": {
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
            "automatic_production_strategy_rewrite": False,
            "external_actions": "APPROVAL_GATED",
        },
    }


class CompletionHandler(BaseHTTPRequestHandler):
    server_version = "JARVISCompletion/7.0"

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
                    dependencies={"repository": "READY"},
                    completion_center=True,
                    engine_ready=True,
                )
            )
        if path == "/api/overview":
            try:
                return self.send_json(overview_payload())
            except Exception as exc:
                HEALTH.mark_error(exc)
                return self.send_json(
                    {
                        "success": False,
                        "message": f"{type(exc).__name__}: {exc}"[:500],
                        "paper_only": True,
                        "live_execution": False,
                    },
                    500,
                )
        if path == "/api/completion":
            from omni.project_completion import snapshot
            return self.send_json(snapshot())
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
                return self.send_json({"success": False, "message": str(exc)[:400]}, 409)
        self.send_error(404)


def main() -> int:
    server = exclusive_server(HOST, PORT, CompletionHandler)
    print("=" * 72)
    print("JARVIS V7 PROJECT COMPLETION CENTER")
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
