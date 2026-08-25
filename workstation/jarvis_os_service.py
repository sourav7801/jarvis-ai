from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from omni.os_control_plane import jarvis_os


HOST = os.getenv("JARVIS_OS_HOST", "127.0.0.1")
PORT = int(os.getenv("JARVIS_OS_PORT", "8795"))


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, default=str, ensure_ascii=False).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "JarvisOSV6/1.0"

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def send_json(self, payload: Any, status: int = 200) -> None:
        raw = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if self.path == "/health":
            return self.send_json(
                {
                    "success": True,
                    "system": "JARVIS_OS",
                    "version": "V6",
                    "mode": "GOVERNED_AUTONOMY",
                    "live_trading": "LOCKED",
                }
            )
        if self.path == "/status":
            return self.send_json(jarvis_os.status())
        if self.path == "/capabilities":
            return self.send_json(jarvis_os.capability_report())
        if self.path == "/improvement-review":
            return self.send_json(jarvis_os.improvement_review())
        if self.path == "/events":
            try:
                from omni.os_control_plane import _read_jsonl

                return self.send_json(
                    {
                        "success": True,
                        "events": _read_jsonl(jarvis_os.event_path, limit=200),
                    }
                )
            except Exception as exc:
                return self.send_json({"success": False, "message": str(exc)}, 500)
        self.send_error(404)

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except Exception:
            body = {}

        if self.path == "/goal":
            objective = str(body.get("objective") or "").strip()
            if len(objective) < 4:
                return self.send_json({"success": False, "message": "Objective is required."}, 400)
            return self.send_json({"success": True, "goal": jarvis_os.record_goal(objective)})

        if self.path == "/outcome":
            capability = str(body.get("capability") or "unknown")
            success = bool(body.get("success"))
            return self.send_json(
                {
                    "success": True,
                    "event": jarvis_os.record_outcome(
                        capability,
                        success=success,
                        duration_ms=body.get("duration_ms"),
                        error=body.get("error"),
                        metadata=body.get("metadata") if isinstance(body.get("metadata"), dict) else None,
                    ),
                }
            )

        self.send_error(404)


def run() -> None:
    jarvis_os.emit("OS_SERVICE_START", host=HOST, port=PORT)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"JARVIS OS V6 control plane listening on http://{HOST}:{PORT}")
    try:
        server.serve_forever(poll_interval=0.25)
    finally:
        server.server_close()
        jarvis_os.emit("OS_SERVICE_STOP", host=HOST, port=PORT)


if __name__ == "__main__":
    run()
