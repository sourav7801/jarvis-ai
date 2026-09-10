"""V16 workstation bridge layered on the verified V15 protected Master.

The protected V8 Master identity and V15 market reasoning stay intact. V16 adds
managed Files/Artifacts/Workspaces/Capabilities plus a same-origin read-only
trading gateway to the supervised professional paper terminal. The browser
never needs to address the internal trading port directly.
"""

from __future__ import annotations

import base64
import json
import os
import socket
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import parse_qs, urlparse

from omni.loopback_http import exclusive_server
from workstation import jarvis_os_v15_bridge as v15
from workstation import jarvis_os_v3 as v3


HOST = v15.HOST
PORT = v15.PORT
_MAX_JSON_BODY = 140 * 1024 * 1024
_TRADING_BASE = os.getenv("JARVIS_V16_TRADING_BASE", "http://127.0.0.1:8787").rstrip("/")
_TRADING_GET_ROUTES = {
    "/api/v16/trading/health": "/api/terminal/health",
    "/api/v16/trading/workspace-state": "/api/v16/trading/workspace-state",
    "/api/v16/trading/chart": "/api/terminal/chart",
    "/api/v16/trading/quote": "/api/terminal/quote",
    "/api/v16/trading/module": "/api/terminal/module",
}


def _v16_status() -> dict[str, Any]:
    from omni.v16_capability_registry import install_v16_capabilities, status as capability_status
    from omni.v16_file_service import MANAGED_FILE_SERVICE_V16
    from omni.v16_artifact_service import ARTIFACT_SERVICE_V16
    from omni.v16_workspace_service import WORKSPACE_SERVICE_V16

    install_v16_capabilities()
    return {
        "success": True,
        "version": "16.0",
        "service": "JARVIS_MASTER_V16_UNIFIED_WORKSTATION_BRIDGE",
        "protected_master_identity": "V8_UNIFIED_INTELLIGENCE",
        "verified_parent": "V15_AUTONOMOUS_MARKET_REASONING",
        "files": MANAGED_FILE_SERVICE_V16.status(),
        "artifacts": ARTIFACT_SERVICE_V16.status(),
        "workspaces": WORKSPACE_SERVICE_V16.status(),
        "capabilities": capability_status(),
        "trading": {
            "authority": "PROFESSIONAL_PAPER_TERMINAL",
            "workspace_state": "/api/v16/trading/workspace-state",
            "chart": "/api/v16/trading/chart",
            "health": "/api/v16/trading/health",
            "same_origin_gateway": True,
            "internal_service_exposed_to_browser": False,
            "paper_only": True,
            "live_orders_locked": True,
        },
        "permanent_agents": 29,
        "system_planes_do_not_count_as_agents": True,
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
        "automatic_production_strategy_rewrite": False,
        "external_actions": "APPROVAL_GATED",
    }


class V16BridgeHandler(v15.V15BridgeHandler):
    server_version = "JarvisOSV8-V16Bridge/1.2"

    def _json_body(self) -> dict[str, Any]:
        length_header = str(self.headers.get("Content-Length") or "0")
        try:
            length = int(length_header)
        except ValueError as exc:
            raise ValueError("invalid Content-Length") from exc
        if length <= 0:
            return {}
        if length > _MAX_JSON_BODY:
            raise ValueError("request body exceeds V16 local API limit")
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("request body must be UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("request JSON must be an object")
        return payload

    def _send_text(self, text: str, content_type: str) -> None:
        raw = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        try:
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return

    def _send_enhanced_asset(self, base_name: str, enhancement_name: str, content_type: str) -> None:
        try:
            base = (v3.ASSETS / base_name).read_text(encoding="utf-8")
            enhancement = (v3.ASSETS / enhancement_name).read_text(encoding="utf-8")
        except OSError as exc:
            return self.send_json({"success": False, "reason": f"V16_ASSET_UNAVAILABLE: {exc}"[:500]}, 500)
        separator = "\n\n/* ===== JARVIS V16 MAIN WORKSTATION ENHANCEMENT ===== */\n\n"
        return self._send_text(base + separator + enhancement, content_type)

    def _send_files_workspace(self) -> None:
        asset = v3.ASSETS / "v16_files.html"
        try:
            html = asset.read_text(encoding="utf-8").replace("__JARVIS_TOKEN__", v3.TOKEN)
        except OSError as exc:
            return self.send_json({"success": False, "reason": f"FILES_UI_UNAVAILABLE: {exc}"[:500]}, 500)
        return self._send_text(html, "text/html; charset=utf-8")

    def _proxy_trading_get(self, upstream_path: str, query: str) -> None:
        url = _TRADING_BASE + upstream_path + (("?" + query) if query else "")
        req = urllib_request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "JARVIS-V16-Master-Gateway/1.2"},
            method="GET",
        )
        try:
            with urllib_request.urlopen(req, timeout=8.0) as response:
                raw = response.read(8 * 1024 * 1024)
                status = int(response.status or 200)
        except urllib_error.HTTPError as exc:
            raw = exc.read(2 * 1024 * 1024)
            status = int(exc.code or 502)
        except (urllib_error.URLError, TimeoutError, socket.timeout, OSError) as exc:
            return self.send_json(
                {
                    "success": False,
                    "reason": "TRADING_SERVICE_UNAVAILABLE",
                    "detail": type(exc).__name__,
                    "paper_only": True,
                    "live_execution": False,
                },
                503,
            )
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self.send_json(
                {
                    "success": False,
                    "reason": "TRADING_SERVICE_INVALID_RESPONSE",
                    "paper_only": True,
                    "live_execution": False,
                },
                502,
            )
        if not isinstance(payload, dict):
            payload = {"success": False, "reason": "TRADING_SERVICE_INVALID_PAYLOAD"}
            status = 502
        payload.setdefault("paper_only", True)
        payload.setdefault("live_execution", False)
        return self.send_json(payload, status)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # Keep one protected Master UI and append V16 enhancements at serve time.
        # The underlying V15 assets remain intact for rollback and comparison.
        if path == "/app.js":
            return self._send_enhanced_asset(
                "app.js", "v16_main_trading_runtime.js", "application/javascript; charset=utf-8"
            )
        if path == "/styles.css":
            return self._send_enhanced_asset(
                "styles.css", "v16_main_trading.css", "text/css; charset=utf-8"
            )

        if path in _TRADING_GET_ROUTES:
            return self._proxy_trading_get(_TRADING_GET_ROUTES[path], parsed.query)
        if path in {"/v16/files", "/files"}:
            return self._send_files_workspace()
        if path == "/api/v16/status":
            return self.send_json(_v16_status())
        if path == "/api/v16/capabilities":
            from omni.v16_capability_registry import install_v16_capabilities
            return self.send_json(install_v16_capabilities())
        if path == "/api/v16/files":
            from omni.v16_file_service import MANAGED_FILE_SERVICE_V16
            workspace = str((params.get("workspace") or [""])[0]).strip() or None
            limit = int((params.get("limit") or ["100"])[0])
            return self.send_json(MANAGED_FILE_SERVICE_V16.list_files(workspace=workspace, limit=limit))
        if path == "/api/v16/files/search":
            from omni.v16_file_service import MANAGED_FILE_SERVICE_V16
            query = str((params.get("q") or [""])[0])
            workspace = str((params.get("workspace") or [""])[0]).strip() or None
            limit = int((params.get("limit") or ["50"])[0])
            return self.send_json(MANAGED_FILE_SERVICE_V16.search(query, workspace=workspace, limit=limit))
        if path == "/api/v16/files/text":
            from omni.v16_file_service import MANAGED_FILE_SERVICE_V16
            file_id = str((params.get("file_id") or [""])[0]).strip()
            max_chars = int((params.get("max_chars") or ["200000"])[0])
            return self.send_json(MANAGED_FILE_SERVICE_V16.extracted_text(file_id, max_chars=max_chars))
        if path == "/api/v16/workspaces":
            from omni.v16_workspace_service import WORKSPACE_SERVICE_V16
            kind = str((params.get("kind") or [""])[0]).strip() or None
            return self.send_json(WORKSPACE_SERVICE_V16.list(kind=kind))
        if path == "/api/v16/workspaces/recent":
            from omni.v16_workspace_service import WORKSPACE_SERVICE_V16
            workspace_id = str((params.get("workspace_id") or [""])[0]).strip() or None
            limit = int((params.get("limit") or ["50"])[0])
            return self.send_json(WORKSPACE_SERVICE_V16.recent_activity(workspace_id, limit=limit))
        return super().do_GET()

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if not path.startswith("/api/v16/"):
            return super().do_POST()
        if not self.authorized():
            return self.send_json({"success": False, "reason": "UNAUTHORIZED"}, 401)
        try:
            payload = self._json_body()
            if path == "/api/v16/files/upload":
                from omni.v16_file_service import MANAGED_FILE_SERVICE_V16

                encoded = payload.get("content_base64")
                if not isinstance(encoded, str) or not encoded:
                    raise ValueError("content_base64 is required")
                try:
                    content = base64.b64decode(encoded, validate=True)
                except Exception as exc:
                    raise ValueError("content_base64 is invalid") from exc
                result = MANAGED_FILE_SERVICE_V16.ingest_bytes(
                    str(payload.get("filename") or ""),
                    content,
                    workspace=str(payload.get("workspace") or "HOME"),
                )
                return self.send_json(result)

            if path == "/api/v16/artifacts/create":
                from omni.v16_artifact_service import ARTIFACT_SERVICE_V16

                result = ARTIFACT_SERVICE_V16.create(
                    str(payload.get("kind") or ""),
                    str(payload.get("filename") or ""),
                    payload.get("specification") if "specification" in payload else {},
                    workspace=str(payload.get("workspace") or "HOME"),
                    register_file=bool(payload.get("register_file", True)),
                )
                return self.send_json(result)

            if path == "/api/v16/projects/create":
                from omni.v16_workspace_service import WORKSPACE_SERVICE_V16

                result = WORKSPACE_SERVICE_V16.create_project(
                    str(payload.get("name") or ""),
                    parent_kind=str(payload.get("parent_kind") or "WORK"),
                    metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else None,
                )
                return self.send_json(result)

            if path == "/api/v16/workspaces/attach-file":
                from omni.v16_workspace_service import WORKSPACE_SERVICE_V16

                result = WORKSPACE_SERVICE_V16.attach_file(
                    str(payload.get("workspace_id") or ""),
                    str(payload.get("file_id") or ""),
                )
                return self.send_json(result)

            if path == "/api/v16/workspaces/attach-mission":
                from omni.v16_workspace_service import WORKSPACE_SERVICE_V16

                result = WORKSPACE_SERVICE_V16.attach_mission(
                    str(payload.get("workspace_id") or ""),
                    str(payload.get("mission_id") or ""),
                )
                return self.send_json(result)

            if path == "/api/v16/tools/execute":
                from omni.v16_capability_registry import install_v16_capabilities
                from omni.v16_tool_contract import CANONICAL_TOOL_REGISTRY_V16

                install_v16_capabilities()
                result = CANONICAL_TOOL_REGISTRY_V16.execute(
                    str(payload.get("tool") or ""),
                    payload.get("arguments") if isinstance(payload.get("arguments"), dict) else {},
                    approval_granted=bool(payload.get("approval_granted", False)),
                )
                return self.send_json(result.to_dict(), 200 if result.success else 409)

            return self.send_json({"success": False, "reason": "V16_ENDPOINT_NOT_FOUND"}, 404)
        except (ValueError, FileNotFoundError) as exc:
            return self.send_json({"success": False, "reason": f"{type(exc).__name__}: {exc}"[:1000]}, 400)
        except Exception as exc:
            return self.send_json({"success": False, "reason": f"{type(exc).__name__}: {exc}"[:1000]}, 500)


def create_server(host: str = HOST, port: int = PORT):
    return exclusive_server(host, int(port), V16BridgeHandler)


__all__ = ["HOST", "PORT", "V16BridgeHandler", "create_server"]
