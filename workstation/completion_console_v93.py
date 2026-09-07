"""V9.3 Completion Center extension for world-state and cognitive-event surfaces."""
from __future__ import annotations

import urllib.parse
from typing import Any

from omni.loopback_http import exclusive_server
from omni.subsystem_snapshot import sanitize_error
from workstation import completion_console as base


HOST = base.HOST
PORT = base.PORT
STATIC = base.STATIC
HEALTH = base.HEALTH


def _world_payload(*, refresh: bool = False) -> dict[str, Any]:
    from omni.cognitive_bridges import install_cognitive_bridges, status as bridge_status
    from omni.world_model import WORLD_MODEL

    bridge = install_cognitive_bridges()
    refresh_result = WORLD_MODEL.refresh_local() if refresh else None
    return {
        "success": True,
        "version": "9.3",
        "bridge": bridge,
        "bridge_status": bridge_status(),
        "refresh": refresh_result,
        "world": WORLD_MODEL.snapshot(limit=100),
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
        "external_actions": "APPROVAL_GATED",
    }


def _cognitive_payload(*, event_type: str | None = None) -> dict[str, Any]:
    from omni.cognitive_bridges import install_cognitive_bridges
    from omni.cognitive_event_bus import COGNITIVE_EVENT_BUS

    install_cognitive_bridges()
    return COGNITIVE_EVENT_BUS.snapshot(limit=100, event_type=event_type)


def overview_payload() -> dict[str, Any]:
    """Extend the fault-isolated V9.2 overview without weakening its boundary."""

    payload = base.overview_payload()
    payload["version"] = "9.3"
    extra_health: dict[str, dict[str, Any]] = {}

    try:
        world = _world_payload(refresh=True)
        payload["world_model"] = world["world"]
        payload["cognitive_bridge"] = world["bridge_status"]
        extra_health["world_model"] = {
            "state": "READY",
            "healthy": True,
            "data": world["world"],
            "error": None,
        }
    except Exception as exc:
        payload["world_model"] = None
        payload["cognitive_bridge"] = None
        extra_health["world_model"] = {
            "state": "FAILED",
            "healthy": False,
            "data": None,
            "error": f"{type(exc).__name__}: {sanitize_error(exc)}"[:500],
        }

    try:
        events = _cognitive_payload()
        payload["cognitive_events"] = events
        extra_health["cognitive_events"] = {
            "state": "READY",
            "healthy": True,
            "data": events,
            "error": None,
        }
    except Exception as exc:
        payload["cognitive_events"] = None
        extra_health["cognitive_events"] = {
            "state": "FAILED",
            "healthy": False,
            "data": None,
            "error": f"{type(exc).__name__}: {sanitize_error(exc)}"[:500],
        }

    payload.setdefault("subsystems", {}).update(extra_health)
    if not all(row.get("healthy") for row in extra_health.values()):
        payload["overall"] = "DEGRADED"
    payload.setdefault("safety", {}).update({
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
        "external_actions": "APPROVAL_GATED",
    })
    return payload


class CompletionHandlerV93(base.CompletionHandler):
    server_version = "JARVISCompletion/9.3"

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        if path == "/v93_world.js":
            return self.send_file(STATIC / "v93_world.js", "application/javascript; charset=utf-8")

        if path == "/api/overview":
            try:
                payload = overview_payload()
                if payload.get("overall") == "READY":
                    HEALTH.mark_success()
                return self.send_json(payload)
            except Exception as exc:
                HEALTH.mark_error(exc)
                return self.send_json({
                    "success": False,
                    "message": f"{type(exc).__name__}: {sanitize_error(exc)}"[:500],
                    "paper_only": True,
                    "live_execution": False,
                    "automatic_broker_order": False,
                }, 500)

        if path == "/api/world":
            try:
                refresh = str((params.get("refresh") or [""])[0]).strip().lower() in {"1", "true", "yes"}
                return self.send_json(_world_payload(refresh=refresh))
            except Exception as exc:
                return self.send_json({
                    "success": False,
                    "message": f"{type(exc).__name__}: {sanitize_error(exc)}"[:500],
                    "paper_only": True,
                    "live_execution": False,
                }, 503)

        if path == "/api/cognitive-events":
            raw_type = str((params.get("type") or [""])[0]).strip() or None
            try:
                return self.send_json(_cognitive_payload(event_type=raw_type))
            except ValueError as exc:
                return self.send_json({"success": False, "message": sanitize_error(exc)}, 400)
            except Exception as exc:
                return self.send_json({
                    "success": False,
                    "message": f"{type(exc).__name__}: {sanitize_error(exc)}"[:500],
                    "paper_only": True,
                    "live_execution": False,
                }, 503)

        if path == "/api/cognitive-bridge":
            from omni.cognitive_bridges import install_cognitive_bridges, status

            install_cognitive_bridges()
            return self.send_json(status())

        return super().do_GET()

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/world/refresh":
            try:
                return self.send_json(_world_payload(refresh=True))
            except Exception as exc:
                return self.send_json({
                    "success": False,
                    "message": f"{type(exc).__name__}: {sanitize_error(exc)}"[:500],
                    "paper_only": True,
                    "live_execution": False,
                }, 503)
        return super().do_POST()


def main() -> int:
    server = exclusive_server(HOST, PORT, CompletionHandlerV93)
    print("=" * 72)
    print("JARVIS V9.3 COMPLETION / WORLD MODEL / COGNITIVE CENTER")
    print("=" * 72)
    print(f"Console: http://{HOST}:{PORT}")
    print("World model: PROVENANCE + FRESHNESS EXPLICIT")
    print("Cognitive bus: TYPED / BOUNDED / INTERNAL")
    print("External actions: APPROVAL GATED")
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
