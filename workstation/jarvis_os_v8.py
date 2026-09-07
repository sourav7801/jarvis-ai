"""JARVIS V8 unified Master control-plane HTTP surface.

V8 preserves the proven V3/V7 workstation implementation and layers a bounded
executive intent/context/planning boundary in front of broad model routing.
Deterministic workspace commands are completed locally instead of falling
through to a chat model that may say it cannot understand them.
"""

from __future__ import annotations

import json
import secrets
import time
import traceback
from http import HTTPStatus
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from omni.conversation_turns import conversation_turns
from omni.executive_control_plane import EXECUTIVE_CONTROL_PLANE
from omni.loopback_http import exclusive_server
from omni.voice_owner_gate import VOICE_OWNER_GATE
from workstation import jarvis_os_v3 as v3


HOST = v3.HOST
PORT = v3.PORT
ROOT = Path(__file__).resolve().parents[1]
V8_ASSETS = ROOT / "workstation" / "jarvis_os_v8_assets"


class V8Handler(v3.Handler):
    server_version = "JarvisOSV8/1.0"

    def _send_v8_home(self) -> None:
        source = (v3.ASSETS / "index.html").read_text(encoding="utf-8")
        source = source.replace("__JARVIS_TOKEN__", v3.TOKEN)
        source = source.replace("JARVIS OS V3.1", "JARVIS OS V8")
        source = source.replace(
            "OMNI OPERATING COMMAND CENTER · V3.1",
            "OMNI OPERATING COMMAND CENTER · V8 UNIFIED INTELLIGENCE",
        )
        injection = '<script src="/v8_runtime.js"></script>\n'
        source = source.replace("</body>", injection + "</body>")
        payload = source.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            return self._send_v8_home()
        if parsed.path == "/v8_runtime.js":
            return self.send_asset(
                V8_ASSETS / "runtime.js",
                "application/javascript; charset=utf-8",
            )
        if parsed.path == "/api/executive/status":
            if not self.authorized():
                return self.send_json({"error": "unauthorized"}, 403)
            return self.send_json(EXECUTIVE_CONTROL_PLANE.status())
        if parsed.path == "/api/executive/plan":
            if not self.authorized():
                return self.send_json({"error": "unauthorized"}, 403)
            query = parse_qs(parsed.query)
            text = str((query.get("text") or [""])[0]).strip()
            if not text:
                return self.send_json({"error": "text required"}, 400)
            return self.send_json(EXECUTIVE_CONTROL_PLANE.plan(text))
        return super().do_GET()

    def do_POST(self) -> None:
        if self.path != "/api/command":
            return super().do_POST()

        if not self.authorized():
            return self.send_json({"error": "unauthorized"}, 403)

        length = int(self.headers.get("Content-Length", "0"))
        if length > 1_000_000:
            return self.send_json({"error": "payload too large"}, 413)
        try:
            body = self.rfile.read(length)
            data = json.loads(body.decode("utf-8") or "{}")
        except Exception:
            return self.send_json({"error": "invalid JSON"}, 400)

        text = str(data.get("text", "")).strip()
        input_mode = str(data.get("input_mode", "typed") or "typed").strip().lower()
        speech_confidence = data.get("speech_confidence")
        if not text:
            return self.send_json({"error": "command required"}, 400)

        if input_mode == "voice" and v3.uncertain_voice_transcript(text, speech_confidence):
            return self.send_json(
                {
                    "success": True,
                    "route": "VOICE_CLARIFICATION",
                    "response": (
                        f'I may have heard "{text[:240]}" incorrectly. '
                        "I will not invent its meaning. Please repeat it or type the command."
                    ),
                    "workspace_actions": [],
                }
            )

        if input_mode == "voice":
            authorization = VOICE_OWNER_GATE.authorize_voice_command(data.get("voice_verification"))
            if not authorization["allowed"]:
                return self.send_json(
                    {
                        "success": True,
                        "route": "VOICE_OWNER_REQUIRED",
                        "response": (
                            "Voice owner lock is enabled, but this utterance has no trusted local "
                            "speaker verification. I did not execute the command."
                        ),
                        "voice_owner": VOICE_OWNER_GATE.status(),
                        "workspace_actions": [],
                    }
                )

        key = v3.command_key(text)
        cached = v3.cached_command_result(key)
        if cached is not None:
            return self.send_json({**cached, "duplicate": "cached"})

        with v3.COMMAND_LOCK:
            if key in v3.COMMAND_INFLIGHT:
                return self.send_json(
                    {
                        "success": True,
                        "route": "DUPLICATE_SUPPRESSED",
                        "response": "I'm already working on that request.",
                        "workspace_actions": [],
                        "duplicate": "inflight",
                    }
                )
            v3.COMMAND_INFLIGHT.add(key)

        try:
            plan = EXECUTIVE_CONTROL_PLANE.plan(text)
            intent = dict(plan.get("intent") or {})
            actions = list(plan.get("workspace_actions") or [])

            if bool(intent.get("deterministic")) and intent.get("kind") == "WORKSPACE_CONTROL":
                route = "WORKSPACE_CONTROL"
                response = str(intent.get("response") or "Workspace command accepted.")
                raw = {
                    "intent": intent,
                    "executive_plan": plan,
                    "execution": "LOCAL_UI_ONLY",
                    "external_action_executed": False,
                }
                conversation_turns.remember(text, response, route)
            else:
                result = v3.dispatch_command(text)
                route = str(result.get("route") or "MASTER")
                response = str(result.get("response") or "Completed.")
                raw = v3.safe(result.get("raw"))

            payload = {
                "success": True,
                "route": route,
                "response": response,
                "raw": raw,
                "workspace_actions": actions,
                "executive": v3.safe(plan),
            }
            with v3.COMMAND_LOCK:
                v3.COMMAND_CACHE[key] = (time.monotonic(), payload)
            return self.send_json(payload)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            # The browser/test client may disappear after submitting a command.
            # Never recursively attempt to write an error response to a socket
            # that is already gone; command state is cleaned up in `finally`.
            return None
        except Exception as exc:
            traceback.print_exc()
            return self.send_json(
                {
                    "success": False,
                    "route": "ERROR",
                    "response": f"{type(exc).__name__}: {exc}",
                    "workspace_actions": [],
                },
                500,
            )
        finally:
            with v3.COMMAND_LOCK:
                v3.COMMAND_INFLIGHT.discard(key)


def create_server(host: str = HOST, port: int = PORT):
    return exclusive_server(host, int(port), V8Handler)


def run_server(host: str = HOST, port: int = PORT) -> None:
    server = create_server(host, port)
    print(f"JARVIS OS V8: http://{host}:{port}")
    print("Executive control plane: READY")
    print("Live broker execution: LOCKED")
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    run_server()
