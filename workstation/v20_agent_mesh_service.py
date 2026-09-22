"""HTTP control/health service for the JARVIS V20 multi-agent mesh."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from workstation.v20_agent_mesh import agent_mesh, ROLE_TO_AGENT

HOST = "127.0.0.1"
PORT = int(os.getenv("JARVIS_V20_AGENT_MESH_PORT", "8795"))


class Handler(BaseHTTPRequestHandler):
    server_version = "JarvisAgentMeshV20/1.0"

    def log_message(self, *_args):
        return

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path)
        if path.path in {"/health", "/api/v20/agents/status"}:
            self._send(200, agent_mesh.status())
            return
        if path.path == "/api/v20/agents/task":
            task_id = parse_qs(path.query).get("id", [""])[0]
            self._send(200, agent_mesh.task_status(task_id))
            return
        if path.path == "/api/v20/agents/capabilities":
            self._send(200, {
                "success": True,
                "service": "JARVIS_V20_MULTI_AGENT_MESH",
                "roles": ROLE_TO_AGENT,
                "paper_only": True,
                "live_execution": False,
            })
            return
        self._send(404, {"success": False, "message": "Not found."})

    def do_POST(self):
        path = urlparse(self.path)
        if path.path != "/api/v20/agents/dispatch":
            self._send(404, {"success": False, "message": "Not found."})
            return
        try:
            length = min(int(self.headers.get("Content-Length", "0")), 200_000)
            payload = json.loads(self.rfile.read(length) or b"{}")
            task = agent_mesh.submit(
                payload.get("role"),
                payload.get("prompt"),
                payload.get("context"),
            )
            self._send(202, task)
        except ValueError as exc:
            self._send(400, {"success": False, "message": str(exc)})
        except Exception as exc:
            self._send(500, {
                "success": False,
                "message": f"{type(exc).__name__}: {exc}",
            })


def main() -> int:
    os.environ["JARVIS_LIVE_EXECUTION"] = "0"
    os.environ["JARVIS_V20_WORKSPACE_OS"] = "1"
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"JARVIS V20 multi-agent mesh listening on http://{HOST}:{PORT}")
    print("Agents run concurrently through the existing capability registry.")
    print("Paper-only boundary: LIVE EXECUTION LOCKED.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
        agent_mesh.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
