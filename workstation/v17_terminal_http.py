"""V17 HTTP layer for the professional autonomous-options PAPER terminal.

This wraps the canonical V16 terminal handler without creating another trading
engine. It adds the V17 status/preferences/autopilot boundary while preserving
V16 as the execution and ledger authority.
"""
from __future__ import annotations

import math
import urllib.parse
from typing import Any

from workstation.v16_terminal_http import build_handler as build_v16_handler
from workstation.v17_autopilot_preferences import load_preferences, save_preferences
from workstation.v17_crypto_paper_lane import crypto_paper_lane

V17_STATUS_PATH = "/api/v17/trading/status"
V17_PREFERENCES_PATH = "/api/v17/autopilot/preferences"
V17_CONTROL_PATH = "/api/v17/autopilot/control"

_ROUTE_META = {
    "INTRADAY": {"label": "Intraday", "execution_workspace": "INTRADAY", "horizon": "SESSION"},
    "SWING": {"label": "Swing", "execution_workspace": "SWING", "horizon": "MULTI_SESSION"},
    "INVESTMENT": {"label": "Investment", "execution_workspace": "INVESTMENT", "horizon": "POSITIONAL"},
    "OPTIONS": {"label": "Options", "execution_workspace": "INTRADAY", "horizon": "INTRADAY_DERIVATIVES"},
}


def _route_metadata(workspace: str) -> dict:
    raw = str(workspace or "INTRADAY").strip().upper()
    requested = raw if raw in _ROUTE_META else "INTRADAY"
    meta = dict(_ROUTE_META[requested])
    return {
        "id": requested,
        "requested_workspace": requested,
        "execution_workspace": meta["execution_workspace"],
        "label": meta["label"],
        "horizon": meta["horizon"],
        "fallback_applied": raw not in _ROUTE_META,
        "requested_raw": raw,
    }


def _normalize_capital_fraction(value: Any) -> float:
    """Accept 0.5, 50 or '50%' and reject unsafe/ambiguous ranges."""
    if isinstance(value, str):
        token = value.strip()
        percent = token.endswith("%")
        if percent:
            token = token[:-1].strip()
        number = float(token)
        if percent:
            number /= 100.0
    else:
        number = float(value)
    if not math.isfinite(number):
        raise ValueError("Options capital percentage must be finite")
    if 1.0 < number <= 100.0:
        number /= 100.0
    if not 0.05 <= number <= 1.0:
        raise ValueError("Options capital must be between 5% and 100%")
    return number


def _preference_updates(body: dict[str, Any]) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    if "options_capital_percent" in body:
        updates["options_capital_fraction"] = _normalize_capital_fraction(body["options_capital_percent"])
    elif "options_capital_fraction" in body:
        updates["options_capital_fraction"] = _normalize_capital_fraction(body["options_capital_fraction"])
    for key in ("one_touch_autopilot", "chart_first_options", "learning_enabled", "start_workspaces"):
        if key in body:
            updates[key] = body[key]
    return updates


def _safety(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    result = dict(payload or {})
    result.update(
        {
            "mode": "PAPER_RESEARCH_ONLY",
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
            "live_orders_locked": True,
            "daily_rebalance": False,
            "cross_workspace_top_up": False,
            "production_code_rewrite": False,
        }
    )
    return result


def _crypto_lane_status() -> dict[str, Any]:
    try:
        return dict(crypto_paper_lane.status())
    except Exception as exc:
        return _safety(
            {
                "success": False,
                "service": "JARVIS_V17_CANONICAL_CRYPTO_UNDERLYING_PAPER",
                "running": False,
                "state": "PROBLEM",
                "reason": "CRYPTO_PAPER_STATUS_UNAVAILABLE",
                "message": f"{type(exc).__name__}: {exc}"[:400],
                "positions": [],
                "open_positions": 0,
                "last_rows_summary": [],
            }
        )


def _autopilot_control(runtime: Any, body: dict[str, Any]) -> dict[str, Any]:
    action = str(body.get("action") or "").strip().lower()
    if action in {"resume", "run"}:
        action = "start"
    if action in {"stop", "pause", "pause_new_entries", "stop_scanner"}:
        action = "stop"
    if action not in {"start", "stop"}:
        raise ValueError("Choose V17 autopilot action start or stop")

    updates = _preference_updates(body)
    preferences = save_preferences(updates) if updates else load_preferences()
    targets = list(preferences["start_workspaces"])
    workspaces = targets if action == "start" else ["INTRADAY", "SWING", "INVESTMENT"]
    runtime_action = "start" if action == "start" else "pause"
    results: dict[str, dict[str, Any]] = {}
    for workspace in workspaces:
        try:
            results[workspace] = dict(runtime.control(workspace, runtime_action))
        except Exception as exc:
            results[workspace] = {
                "success": False,
                "state": "PROBLEM",
                "reason": type(exc).__name__,
                "message": str(exc)[:300],
            }

    try:
        if action == "start":
            results["CRYPTO_UNDERLYING"] = dict(crypto_paper_lane.start())
        else:
            results["CRYPTO_UNDERLYING"] = dict(crypto_paper_lane.stop_new_entries())
    except Exception as exc:
        results["CRYPTO_UNDERLYING"] = {
            "success": False,
            "state": "PROBLEM",
            "reason": type(exc).__name__,
            "message": str(exc)[:300],
            "paper_only": True,
            "live_execution": False,
        }

    success = all(item.get("success") is True for item in results.values())
    states = {
        name: item.get("state") or ("RUNNING" if item.get("running") else "PAUSED")
        for name, item in results.items()
    }
    return _safety(
        {
            "success": success,
            "service": "JARVIS_V17_ONE_TOUCH_AUTOPILOT",
            "action": action.upper(),
            "results": results,
            "states": states,
            "preferences": preferences,
            "options_capital_fraction": preferences["options_capital_fraction"],
            "message": (
                "V17 PAPER autopilot started canonical sessions plus BTC/ETH/SOL adaptive underlying scanning."
                if action == "start"
                else "V17 new-entry sessions paused, including crypto underlying scanning; existing Paper Desk positions remain managed."
            ),
        }
    )


def _fyers_stream_status() -> dict:
    startup: dict = {}
    payload: dict | None = None
    try:
        from workstation import quant_terminal_v2

        startup = dict(getattr(quant_terminal_v2, "LIVE_BRIDGE_STARTUP", {}) or {})
        bridge_payload = quant_terminal_v2._bridge_request("/api/status", timeout=0.35)
        if isinstance(bridge_payload, dict):
            payload = dict(bridge_payload)
            payload["bridge_reachable"] = True
        else:
            startup_state = str(startup.get("state") or "NOT_STARTED").upper()
            if startup_state in {"STARTING", "STARTING_OR_RECONNECTING"}:
                state, running = "RECONNECTING", True
            elif startup_state == "AVAILABLE":
                state, running = "CONNECTING", True
            else:
                state, running = "DISCONNECTED", False
            payload = {
                "provider": "FYERS",
                "transport": "DATA_WEBSOCKET",
                "state": state,
                "running": running,
                "connected": False,
                "fresh": False,
                "error": startup.get("error"),
                "bridge_reachable": False,
            }
    except Exception as exc:
        payload = {
            "provider": "FYERS",
            "transport": "DATA_WEBSOCKET",
            "state": "UNAVAILABLE",
            "running": False,
            "connected": False,
            "fresh": False,
            "error": f"{type(exc).__name__}: {exc}",
            "bridge_reachable": False,
        }

    if not payload.get("state"):
        if payload.get("connected"):
            payload["state"] = "CONNECTED"
        elif payload.get("running"):
            payload["state"] = "RECONNECTING"
        else:
            payload["state"] = "DISCONNECTED"
    if "fresh" not in payload:
        payload["fresh"] = payload.get("state") == "CONNECTED"

    payload["startup"] = startup
    payload["data_only"] = True
    payload["read_only"] = True
    payload["order_socket_enabled"] = False
    payload["live_order_execution"] = False
    return payload


def _v17_status(runtime, workspace: str) -> dict:
    route = _route_metadata(workspace)
    safety = _safety()
    market_data = {
        "primary_provider": "FYERS",
        "read_only": True,
        "stream": _fyers_stream_status(),
    }
    preferences = load_preferences()
    crypto_status = _crypto_lane_status()

    service = getattr(runtime, "v17_autonomy_service", None)
    if service is None:
        return {
            "success": False,
            "service": "JARVIS_V17_AUTONOMOUS_OPTIONS_PAPER_RUNTIME",
            "version": "17.2",
            "installed": False,
            "reason": "V17_AUTONOMY_SERVICE_NOT_INSTALLED",
            "workspace": route["requested_workspace"],
            "execution_workspace": route["execution_workspace"],
            "route": route,
            "market_data": market_data,
            "autopilot_preferences": preferences,
            "crypto_underlying_paper": crypto_status,
            **safety,
        }

    payload = dict(service.status(route["execution_workspace"]))
    payload.update(
        {
            "success": True,
            "service": "JARVIS_V17_AUTONOMOUS_OPTIONS_PAPER_RUNTIME",
            "version": "17.2",
            "runtime_identity": "V17_AUTONOMOUS_OPTIONS",
            "verified_parent": "V16_TRADING_CONVERGENCE",
            "workspace": route["requested_workspace"],
            "execution_workspace": route["execution_workspace"],
            "route": route,
            "market_data": market_data,
            "autopilot_preferences": preferences,
            "crypto_underlying_paper": crypto_status,
            **safety,
        }
    )
    return payload


def build_handler(base, runtime):
    V16Handler = build_v16_handler(base, runtime)

    class V17TerminalHandler(V16Handler):
        server_version = "JarvisQuantV17/1.4"

        def _serve_v17_root(self):
            from workstation.quant_terminal_v2 import STATIC

            html = (STATIC / "index.html").read_text(encoding="utf-8")
            html = html.replace('<script src="/paper_desk_runtime.js"></script>', "")
            html = html.replace("V15 AUTONOMOUS MARKET REASONING · PAPER / RESEARCH", "V17 AUTONOMOUS OPTIONS RUNTIME · PAPER / RESEARCH")
            html = html.replace("JARVIS Quant V15 ·", "JARVIS Quant V17 · autonomous options ·")
            html = html.replace("JARVIS V15 reasons across verified market state", "JARVIS V17 uses the verified V15 reasoning core across market state")
            injection = (
                '<script>window.JARVIS_V16_CANONICAL=true;window.JARVIS_V17_RUNTIME=true;window.JARVIS_V17_SINGLE_OPTION_CONTROLLER=true;</script>'
                '<script src="/v17_live_fetch_scheduler.js?v=170102"></script>'
                '<link rel="stylesheet" href="/v16_autonomy_runtime.css">'
                '<script defer src="/v16_autonomy_runtime.js"></script>'
                '<script defer src="/v16_option_decision_runtime.js"></script>'
                '<script defer src="/v16_workspace_router.js"></script>'
                '<script defer src="/v16_option_readiness_runtime.js"></script>'
                '<script defer src="/v17_runtime.js?v=170100"></script>'
                '<script defer src="/v17_crypto_paper_runtime.js?v=170200"></script>'
            )
            content = html.replace("</head>", injection + "</head>").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(content)
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                pass

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)

            if parsed.path == "/" and self._local():
                return self._serve_v17_root()

            if parsed.path in {"/v17_runtime.js", "/v17_live_fetch_scheduler.js", "/v17_crypto_paper_runtime.js"} and self._local():
                from workstation.quant_terminal_v2 import STATIC
                return self.send_file(STATIC / parsed.path.lstrip("/"), "application/javascript; charset=utf-8")

            if parsed.path == V17_PREFERENCES_PATH:
                if not self._local():
                    return self.send_json(_safety({"success": False, "reason": "LOCAL_TERMINAL_ONLY"}), 403)
                return self.send_json(_safety({"success": True, "preferences": load_preferences()}))

            if parsed.path == V17_STATUS_PATH:
                if not self._local():
                    return self.send_json(_safety({"success": False, "reason": "LOCAL_TERMINAL_ONLY"}), 403)
                params = urllib.parse.parse_qs(parsed.query)
                workspace = str(params.get("workspace", ["INTRADAY"])[0]).upper()
                return self.send_json(_v17_status(runtime, workspace))

            return super().do_GET()

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path not in {V17_PREFERENCES_PATH, V17_CONTROL_PATH}:
                return super().do_POST()
            if not self._authorized_v16_write():
                return self.send_json(
                    _safety(
                        {
                            "success": False,
                            "reason": "LOCAL_SESSION_TOKEN_REQUIRED",
                            "message": "Refresh this local terminal before changing V17 PAPER state.",
                        }
                    ),
                    403,
                )
            try:
                body = self._v16_body()
                if parsed.path == V17_PREFERENCES_PATH:
                    preferences = save_preferences(_preference_updates(body))
                    return self.send_json(_safety({"success": True, "preferences": preferences}))
                return self.send_json(_autopilot_control(runtime, body))
            except (ValueError, KeyError, TypeError) as exc:
                return self.send_json(_safety({"success": False, "message": str(exc)}), 400)

    return V17TerminalHandler


__all__ = [
    "V17_STATUS_PATH",
    "V17_PREFERENCES_PATH",
    "V17_CONTROL_PATH",
    "_autopilot_control",
    "_crypto_lane_status",
    "_fyers_stream_status",
    "_normalize_capital_fraction",
    "_preference_updates",
    "_route_metadata",
    "_v17_status",
    "build_handler",
]
