"""HTTP service for the JARVIS V20 specialist Options Agent."""
from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from workstation.v20_options_runtime import options_agent

HOST = "127.0.0.1"
PORT = int(os.getenv("JARVIS_V20_OPTIONS_AGENT_PORT", "8796"))


class Handler(BaseHTTPRequestHandler):
    server_version = "JarvisOptionsAgentV20/1.0"

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
        parsed = urlparse(self.path)
        if parsed.path in {"/health", "/api/v20/options/runtime"}:
            params = parse_qs(parsed.query)
            symbol = params.get("symbol", ["NIFTY"])[0]
            expiry = params.get("expiry", [None])[0]
            timeframe = params.get("timeframe", ["5m"])[0]
            try:
                if parsed.path == "/api/v20/options/runtime":
                    payload = options_agent.evaluate(symbol, expiry, timeframe)
                else:
                    payload = options_agent.status()
                self._send(200, payload)
            except Exception as exc:
                self._send(503, {
                    "success": False,
                    "service": "JARVIS_V20_OPTIONS_AGENT",
                    "message": f"{type(exc).__name__}: {exc}",
                    "paper_only": True,
                    "live_execution": False,
                })
            return
        self._send(404, {"success": False, "message": "Not found."})

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/v20/options/control":
            self._send(404, {"success": False, "message": "Not found."})
            return
        try:
            payload = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", "0")), 20_000)) or b"{}")
            action = str(payload.get("action") or "").lower()
            if action == "stop":
                options_agent.stop()
                result = {"success": True, "action": "STOP", "running": False}
            elif action == "start":
                options_agent._running = True
                result = {"success": True, "action": "START", "running": True}
            else:
                raise ValueError("Options Agent control accepts start or stop.")
            result.update({"paper_only": True, "live_execution": False})
            self._send(200, result)
        except Exception as exc:
            self._send(400, {"success": False, "message": str(exc), "paper_only": True, "live_execution": False})


def main() -> int:
    os.environ["JARVIS_LIVE_EXECUTION"] = "0"
    os.environ["JARVIS_V20_WORKSPACE_OS"] = "1"
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    worker = threading.Thread(target=options_agent.run_forever, name="jarvis-options-agent", daemon=True)
    worker.start()
    print(f"JARVIS V20 Options Agent listening on http://{HOST}:{PORT}")
    print("Continuous option selection is PAPER ONLY. LIVE ORDERS LOCKED.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        options_agent.stop()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
