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
from workstation.v17_cross_market_control_plane import cross_market_control_plane
from workstation.v17_option_data_lanes import OPTION_DATA_LANES

V17_STATUS_PATH = "/api/v17/trading/status"
V17_PREFERENCES_PATH = "/api/v17/autopilot/preferences"
V17_CONTROL_PATH = "/api/v17/autopilot/control"
V17_PERFORMANCE_PATH = "/api/v17/diagnostics/performance"

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
    if action in {"stop", "pause", "pause_new_entries", "stop_scanner", "stop_for_day"}:
        action = "stop"
    if action not in {"start", "stop"}:
        raise ValueError("Choose V17 autopilot action start or stop")

    updates = _preference_updates(body)
    updates["armed"] = action == "start"
    preferences = save_preferences(updates)
    control = cross_market_control_plane.reconcile(
        runtime,
        preferences=preferences,
        force=True,
        crypto_lane=crypto_paper_lane,
    )
    results = dict(control.get("lanes") or {})
    success = not bool(control.get("last_error"))
    states = {
        name: item.get("state") or ("RUNNING" if item.get("running") else "PAUSED")
        for name, item in results.items()
        if isinstance(item, dict)
    }
    return _safety(
        {
            "success": success,
            "service": "JARVIS_V17_ONE_TOUCH_AUTOPILOT",
            "version": "17.4.1",
            "action": action.upper(),
            "armed": bool(preferences.get("armed")),
            "results": results,
            "states": states,
            "control_plane": control,
            "preferences": preferences,
            "options_capital_fraction": preferences["options_capital_fraction"],
            "message": (
                "V17.4.1 PAPER control plane armed. India follows its session, MCX follows its session, and BTC/ETH/SOL resumes 24/7 after restarts."
                if action == "start"
                else "V17.4.1 PAPER control plane disarmed. New entries stay paused after restarts; existing Paper Desk positions remain managed."
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



def _performance_payload() -> dict:
    from workstation.terminal_data import ANALYSIS_POOL, MARKET_CACHE
    from workstation import quant_terminal_v2

    cache = MARKET_CACHE.status()
    stream = _fyers_stream_status()
    return _safety(
        {
            "success": True,
            "service": "JARVIS_V17_PERFORMANCE_DIAGNOSTICS",
            "version": "17.4.1",
            "server": {
                "market_cache": cache,
                "analysis_pool": {
                    "workers": getattr(ANALYSIS_POOL, "workers", None),
                    "capacity": getattr(ANALYSIS_POOL, "capacity", None),
                },
                "display_history": quant_terminal_v2.display_history_metrics(),
                "fyers_stream": {
                    "connected": bool(stream.get("connected")),
                    "running": bool(stream.get("running")),
                    "snapshots": stream.get("snapshots"),
                    "error": stream.get("error"),
                    "service": stream.get("service"),
                    "version": stream.get("version"),
                },
            },
            "browser_metrics_source": "window.JARVIS_V17_DATA_PLANE.snapshot()",
            "notes": "Read-only diagnostics. Display-history cache is chart-only and never execution evidence.",
        }
    )


def _v17_status(runtime, workspace: str) -> dict:
    route = _route_metadata(workspace)
    safety = _safety()
    preferences = load_preferences()
    # V17 status is a read-only heartbeat. It must never reconcile/start/pause
    # trading lanes as a side effect of the browser polling the status endpoint.
    control_plane = cross_market_control_plane.status(preferences=preferences)
    crypto_status = _crypto_lane_status()
    stream = _fyers_stream_status()

    fyers_state = str(stream.get("state") or "").upper()
    if stream.get("connected") is True and stream.get("fresh") is not False:
        fyers_health = "READY"
    elif fyers_state in {"CONNECTING", "RECONNECTING"} or stream.get("running"):
        fyers_health = "RECONNECTING"
    else:
        fyers_health = "OFFLINE"

    crypto_rows = crypto_status.get("last_rows_summary") or []
    crypto_ready = any(
        isinstance(row, dict) and row.get("success") is not False
        for row in crypto_rows
    )
    crypto_health = "READY" if crypto_ready else (
        "DEGRADED" if crypto_status.get("running") else "OFFLINE"
    )
    mcx = crypto_status.get("mcx_underlying_paper") or {}
    mcx_health = "CLOSED" if mcx.get("session_open") is False else fyers_health

    feeds = {
        "FYERS_STREAM": {"state": fyers_health, "read_only": True},
        "FYERS_HISTORY": {
            "state": "READY" if fyers_health == "READY" else "DEGRADED",
            "read_only": True,
        },
        "INDIA_INDEX_OPTIONS": {"state": fyers_health, "execution": "PAPER_ONLY"},
        "MCX_FUTURES": {"state": mcx_health, "execution": "PAPER_ONLY"},
        "BINANCE_PUBLIC": {"state": crypto_health, "execution": "PAPER_ONLY"},
        "DERIBIT_RESEARCH": {"state": "READY", "execution": "RESEARCH_ONLY"},
        "CANONICAL_PAPER_STATE": {"state": "READY", "execution": "PAPER_ONLY"},
    }
    feed_states = [value["state"] for value in feeds.values()]
    if all(state in {"READY", "CLOSED"} for state in feed_states):
        overall = "READY"
    elif any(state == "READY" for state in feed_states):
        overall = "PARTIAL"
    elif any(state in {"DEGRADED", "RECONNECTING"} for state in feed_states):
        overall = "DEGRADED"
    else:
        overall = "OFFLINE"

    market_data = {
        "primary_provider": "FYERS",
        "read_only": True,
        "state": overall,
        "feeds": feeds,
        "stream": stream,
    }

    service = getattr(runtime, "v17_autonomy_service", None)
    if service is None:
        return {
            "success": False,
            "service": "JARVIS_V17_AUTONOMOUS_OPTIONS_PAPER_RUNTIME",
            "version": "17.4.1",
            "installed": False,
            "reason": "V17_AUTONOMY_SERVICE_NOT_INSTALLED",
            "workspace": route["requested_workspace"],
            "execution_workspace": route["execution_workspace"],
            "route": route,
            "market_data": market_data,
            "autopilot_preferences": preferences,
            "control_plane": control_plane,
            "crypto_underlying_paper": crypto_status,
            **safety,
        }

    payload = dict(service.status(route["execution_workspace"]))
    payload.update(
        {
            "success": True,
            "service": "JARVIS_V17_AUTONOMOUS_OPTIONS_PAPER_RUNTIME",
            "version": "17.4.1",
            "runtime_identity": "V17_AUTONOMOUS_OPTIONS",
            "verified_parent": "V16_TRADING_CONVERGENCE",
            "workspace": route["requested_workspace"],
            "execution_workspace": route["execution_workspace"],
            "route": route,
            "market_data": market_data,
            "autopilot_preferences": preferences,
            "control_plane": control_plane,
            "crypto_underlying_paper": crypto_status,
            **safety,
        }
    )
    return payload


def _option_chain_lane(workspace: str, symbol: str, expiry: str | None, wait: float = 0.0) -> dict[str, Any]:
    result = OPTION_DATA_LANES.chain_request(workspace, symbol, expiry, wait=wait)
    if result.get("pending"):
        return _safety({
            "success": True,
            "pending": True,
            "module": "option-chain",
            "symbol": str(symbol).upper(),
            "expiry": expiry,
            "message": result.get("message"),
            "lane": "V17_ISOLATED_OPTION_CHAIN",
        })
    if result.get("success") is not True:
        return _safety(result)
    payload = dict(result.get("result") or {})
    payload["pending"] = False
    payload["lane"] = "V17_ISOLATED_OPTION_CHAIN"
    payload["cache_hit"] = bool(result.get("cache_hit"))
    return _safety(payload)


def _option_chart_lane(provider: str, instrument: str, timeframe: str, bars: int) -> dict[str, Any]:
    result = OPTION_DATA_LANES.chart_request(provider, instrument, timeframe, bars)
    if result.get("success") is not True:
        payload = _safety(result)
        payload["lane"] = "V17_ISOLATED_OPTION_CHART"
        return payload
    payload = _safety(dict(result.get("result") or {}))
    payload["lane"] = "V17_ISOLATED_OPTION_CHART"
    payload["cache_hit"] = bool(result.get("cache_hit"))
    return payload


def build_handler(base, runtime):
    V16Handler = build_v16_handler(base, runtime)

    class V17TerminalHandler(V16Handler):
        server_version = "JarvisQuantV20/1.0"

        def _serve_v17_root(self):
            from workstation.quant_terminal_v2 import STATIC

            html = (STATIC / "index.html").read_text(encoding="utf-8")
            html = html.replace('<script src="/paper_desk_runtime.js"></script>', "")
            html = html.replace('<link rel="stylesheet" href="/style.css">', '<link rel="stylesheet" href="/style.css?v=170404">')
            html = html.replace('<script src="/app.js"></script>', '<script src="/app.js?v=170405"></script>')

            # V17 owns the professional Options surface. Do not load the old
            # V12-V16 browser overlay runtimes alongside it: several of those
            # start their own polling/observation loops and assume the legacy
            # manual option-ticket DOM.
            legacy_scripts = (
                "session_hotfix.js",
                "v12_paper_intelligence.js",
                "v13_contextual_paper_runtime.js",
                "v14_execution_runtime.js",
                "v141_risk_geometry_runtime.js",
                "v15_market_reasoning_runtime.js",
                "v16_workspace.js",
                "v16_option_execution.js",
                "v16_option_readiness_runtime.js",
                "v16_option_decision_runtime.js",
                "v16_option_experience_runtime.js",
                "adaptive_brain_runtime.js",
                "advanced_terminal_runtime.js",
                "scan_consistency_hotfix.js",
            )
            for asset in legacy_scripts:
                html = html.replace(f'<script src="/{asset}"></script>', "")

            # Remove the legacy inline V16 option/readiness/pinning block. It
            # contains its own timers and targets DOM elements that V17 no
            # longer mounts.
            inline_start = html.find('<script>\n(() => {\n  "use strict";\n  const $ = id => document.getElementById(id);')
            if inline_start >= 0 and 'function refreshTruthfulOptionGates()' in html[inline_start:inline_start + 6000]:
                inline_end = html.find("</script>", inline_start)
                if inline_end >= 0:
                    html = html[:inline_start] + html[inline_end + len("</script>"):]
            html = html.replace("V15 AUTONOMOUS MARKET REASONING · PAPER / RESEARCH", "V19 WORKSPACE OS · PAPER / RESEARCH")
            html = html.replace("JARVIS Quant V15 ·", "JARVIS Quant V19 · workspace OS ·")
            html = html.replace("JARVIS V15 reasons across verified market state", "JARVIS V17 uses the verified V15 reasoning core across market state")
            injection = (
                '<script>window.JARVIS_V16_CANONICAL=true;window.JARVIS_V17_RUNTIME=true;window.JARVIS_V18_OPTIONS_WORKBENCH=false;window.JARVIS_V19_WORKSPACE_OS=false;window.JARVIS_V20_WORKSPACE_OS=true;</script>'
                '<script src="/v17_live_fetch_scheduler.js?v=170403"></script>'
                '<script defer src="/v17_runtime.js?v=170403"></script>'
                '<link rel="stylesheet" href="/v20_workspace_os.css?v=200101"><script defer src="/v20_workspace_os.js?v=200101"></script>'
                '<script defer src="/v17_crypto_paper_runtime.js?v=170301"></script>'
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

            # Option-chain analysis is isolated from the generic research pool.
            # A slow FYERS call can therefore never consume the workers used by
            # workspace state, chart hydration, or unrelated intelligence.
            if parsed.path == "/api/v19/workspace/state" and self._local():
                params = urllib.parse.parse_qs(parsed.query)
                workspace = str(params.get("workspace", ["INTRADAY"])[0]).upper()
                if workspace not in {"INTRADAY", "SWING", "INVESTMENT", "OPTIONS"}:
                    workspace = "INTRADAY"
                provider = provider_payload()
                provider_ready, provider_error = provider_health_state(provider)
                if provider_ready:
                    HEALTH.mark_success()
                else:
                    HEALTH.mark_error(provider_error or "FYERS_BRIDGE_DEGRADED")
                payload = {
                    "success": True,
                    "workspace": workspace,
                    "server": {"version": self.server_version, "live_execution": False, "paper_only": True},
                    "provider": provider,
                    "health": HEALTH.payload(
                        status="READY" if provider_ready else "DEGRADED",
                        healthy=True,
                        dependencies={"fyers_bridge": "READY" if provider_ready else "DEGRADED"},
                        engine_ready=True,
                    ),
                }
                try:
                    from workstation.paper_autonomy_engine import paper_autonomy
                    payload["paper"] = paper_autonomy.status()
                except Exception as exc:
                    payload["paper"] = {"status": "UNAVAILABLE", "message": _safe_message(exc)}
                if workspace == "OPTIONS":
                    try:
                        from workstation.options_readiness import options_readiness_payload
                        payload["options"] = options_readiness_payload()
                    except Exception as exc:
                        payload["options"] = {"success": False, "status": "DEGRADED", "message": _safe_message(exc)}
                return self.send_json(payload)

            if parsed.path == "/api/v17/options/chain" and self._local():
                params = urllib.parse.parse_qs(parsed.query)
                workspace = str(params.get("workspace", ["OPTIONS"])[0]).upper()
                symbol = str(params.get("symbol", ["NIFTY"])[0]).upper()
                expiry = params.get("expiry", [None])[0] or None
                payload = _option_chain_lane(workspace, symbol, expiry, wait=5.0)
                return self.send_json(payload, 503 if payload.get("success") is False else 200)

            if parsed.path == "/api/terminal/module" and self._local():
                params = urllib.parse.parse_qs(parsed.query)
                module = str(params.get("module", [""])[0]).strip().lower()
                if module in {"option-chain", "oi-iv"}:
                    workspace = str(params.get("workspace", ["INTRADAY"])[0]).upper()
                    symbol = str(params.get("symbol", ["NIFTY"])[0]).upper()
                    expiry = params.get("expiry", [None])[0] or None
                    payload = _option_chain_lane(workspace, symbol, expiry)
                    return self.send_json(payload, 503 if payload.get("success") is False else 200)

            # Option premium candles get their own bounded worker too. The chart
            # request may time out, but only this lane is affected.
            if parsed.path == "/api/option-candles" and self._local():
                params = urllib.parse.parse_qs(parsed.query)
                provider = str(params.get("provider", [""])[0])
                instrument = str(params.get("instrument", [""])[0])
                timeframe = str(params.get("timeframe", ["5m"])[0])
                try:
                    bars = int(params.get("bars", ["500"])[0])
                except (TypeError, ValueError):
                    bars = 500
                return self.send_json(_option_chart_lane(provider, instrument, timeframe, bars))

            if parsed.path == "/" and self._local():
                return self._serve_v17_root()

            if parsed.path in {"/v17_runtime.js", "/v17_live_fetch_scheduler.js", "/v17_crypto_paper_runtime.js", "/v17_options_runtime.js", "/v18_options_workbench.js", "/v20_workspace_os.js"} and self._local():
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

            if parsed.path == V17_PERFORMANCE_PATH:
                if not self._local():
                    return self.send_json(_safety({"success": False, "reason": "LOCAL_TERMINAL_ONLY"}), 403)
                return self.send_json(_performance_payload())

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
    "V17_PERFORMANCE_PATH",
    "_autopilot_control",
    "_crypto_lane_status",
    "_fyers_stream_status",
    "_normalize_capital_fraction",
    "_preference_updates",
    "_performance_payload",
    "_route_metadata",
    "_v17_status",
    "build_handler",
]
