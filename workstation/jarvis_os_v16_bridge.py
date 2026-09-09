"""V16 workstation bridge layered on the verified V15 protected Master.

The protected V8 Master identity and V15 market reasoning stay intact.  V16 adds
managed Files/Artifacts/Workspaces/Capabilities APIs only.  All local writes are
loopback-authorized using the existing Master token path.
"""

from __future__ import annotations

import base64
import json
from typing import Any
from urllib.parse import parse_qs, urlparse

from omni.loopback_http import exclusive_server
from workstation import jarvis_os_v15_bridge as v15


HOST = v15.HOST
PORT = v15.PORT
_MAX_JSON_BODY = 140 * 1024 * 1024


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
        "permanent_agents": 29,
        "system_planes_do_not_count_as_agents": True,
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
        "automatic_production_strategy_rewrite": False,
        "external_actions": "APPROVAL_GATED",
    }


class V16BridgeHandler(v15.V15BridgeHandler):
    server_version = "JarvisOSV8-V16Bridge/1.0"

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

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
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
