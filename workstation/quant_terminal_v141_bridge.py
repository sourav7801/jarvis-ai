"""V14.1 Quant overlay for verified risk geometry and execution tracing."""
from __future__ import annotations

import urllib.parse
from threading import RLock
from typing import Any

from workstation import quant_terminal_v2 as quant
from workstation.quant_terminal_v14_bridge import QuantTerminalV14Handler


_LOCK = RLock()
_INSTALLED = False
DEFAULT_TRACE_PROFILES = ("5m_only", "10m_only", "15m_only", "adaptive_intraday", "swing")


def _bucket_for_profile(profile: str) -> tuple[str, float]:
    token = str(profile or "").lower()
    if token == "swing":
        return "SWING", 0.30
    if token == "investment":
        return "INVESTMENT", 0.20
    return "INTRADAY", 0.50


def _sizing_plan(scan: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    if decision.get("executable") is not True:
        return {"success": False, "reason": "DECISION_NOT_EXECUTABLE"}
    symbol = str(scan.get("symbol") or "").upper()
    side = str(decision.get("side") or "").upper()
    entry = scan.get("entry")
    stop = scan.get("stop")
    target = scan.get("target")
    if side not in {"LONG", "SHORT"} or entry is None or stop is None or target is None:
        return {"success": False, "reason": "INVALID_RISK_LEVELS"}

    try:
        from workstation.paper_autonomy_engine import paper_desk
        from workstation.paper_execution_sizing_v13 import plan_auto_quantity
        from workstation.paper_market_data import PAPER_MARKET_DATA

        instrument_spec = PAPER_MARKET_DATA.instrument_spec(symbol)
        valuation_multiplier = 1.0
        if symbol in {"BTC", "ETH", "SOL", "BNB", "XRP"}:
            quote = PAPER_MARKET_DATA.quote(symbol)
            native_ltp = float(quote.get("native_ltp") or 0.0)
            valuation_ltp = float(quote.get("valuation_ltp") or 0.0)
            if not quote.get("success") or native_ltp <= 0.0 or valuation_ltp <= 0.0:
                return {"success": False, "reason": "VALUATION_FX_UNAVAILABLE"}
            valuation_multiplier = valuation_ltp / native_ltp
        bucket, allocation = _bucket_for_profile(str(scan.get("profile") or ""))
        request = {
            "symbol": symbol,
            "side": side,
            "entry": float(entry),
            "stop": float(stop),
            "target": float(target),
            "quantity": None,
            "timeframe": str(scan.get("timeframe") or ""),
            "strategy": "V14_1_EXECUTION_TRACE",
            "score": float(scan.get("score") or 0.0),
            "source": "V14_1_READ_ONLY_TRACE",
            "asset_type": "CRYPTO" if symbol in {"BTC", "ETH", "SOL", "BNB", "XRP"} else "MARKET",
            "risk_multiplier": float(decision.get("risk_multiplier") or 0.0),
            "valuation_multiplier": valuation_multiplier,
            "instrument_spec": instrument_spec,
            "portfolio_bucket": bucket,
            "bucket_allocation_fraction": allocation,
        }
        plan = plan_auto_quantity(paper_desk, request)
        return dict(plan) if isinstance(plan, dict) else {"success": False, "reason": "SIZING_PLAN_INVALID"}
    except Exception as exc:
        return {"success": False, "reason": f"{type(exc).__name__}: {exc}"[:300]}


def _trace_profile(symbol: str, profile: str) -> dict[str, Any]:
    from omni.trading_intelligence.continuous_execution_policy_v14 import (
        CONTINUOUS_EXECUTION_POLICY_V14,
    )

    scan = quant.scan_payload(symbol, profile=profile)
    allowed_sides = ("LONG",) if profile == "investment" else ("LONG", "SHORT")
    decision = CONTINUOUS_EXECUTION_POLICY_V14.evaluate(scan, allowed_sides=allowed_sides)
    geometry = scan.get("risk_geometry_v141") if isinstance(scan.get("risk_geometry_v141"), dict) else {}
    sizing = _sizing_plan(scan, decision)

    stages = {
        "DISCOVERED": bool(scan.get("success")),
        "DIRECTION_FOUND": str(scan.get("candidate_side") or "").upper() in {"LONG", "SHORT"},
        "RISK_MODEL_BUILT": bool(
            geometry.get("success")
            or (
                scan.get("entry") is not None
                and scan.get("stop") is not None
                and scan.get("target") is not None
            )
        ),
        "CONTEXTUAL_EV_EVALUATED": True,
        "ACTIONABLE": decision.get("executable") is True,
        "SIZE_PLANNED": sizing.get("success") is True,
    }

    hard = [str(item) for item in list(decision.get("hard_blockers") or [])]
    if not stages["DISCOVERED"]:
        stop_reason = "DATA_UNAVAILABLE"
    elif not stages["DIRECTION_FOUND"]:
        stop_reason = "NO_DIRECTIONAL_EDGE"
    elif not stages["RISK_MODEL_BUILT"]:
        stop_reason = str(geometry.get("reason") or "INVALID_RISK_LEVELS")
    elif hard:
        stop_reason = hard[0]
    elif float(decision.get("expected_value_r") or 0.0) <= 0.0:
        stop_reason = "NON_POSITIVE_CONTEXTUAL_EV"
    elif decision.get("executable") is not True:
        stop_reason = "DECISION_NOT_EXECUTABLE"
    elif sizing.get("success") is not True:
        stop_reason = str(sizing.get("reason") or "POSITION_SIZE_PLAN_FAILED")
    else:
        stop_reason = "READY_FOR_PAPER_DESK_OPEN"

    return {
        "success": bool(scan.get("success")),
        "symbol": scan.get("symbol") or symbol,
        "profile": scan.get("profile") or profile,
        "timeframe": scan.get("timeframe"),
        "candidate_side": scan.get("candidate_side"),
        "legacy_side": scan.get("side"),
        "legacy_score": scan.get("score"),
        "legacy_qualified": scan.get("qualified"),
        "legacy_blockers": list(scan.get("blockers") or []),
        "entry": scan.get("entry"),
        "stop": scan.get("stop"),
        "target": scan.get("target"),
        "risk_reward": scan.get("risk_reward"),
        "risk_geometry": geometry,
        "decision": decision,
        "sizing": sizing,
        "stages": stages,
        "pipeline_stop_reason": stop_reason,
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
    }


def execution_trace(symbol: str = "BTC") -> dict[str, Any]:
    canonical = str(symbol or "BTC").strip().upper() or "BTC"
    rows = [_trace_profile(canonical, profile) for profile in DEFAULT_TRACE_PROFILES]
    ranked = sorted(
        rows,
        key=lambda row: (
            float((row.get("decision") or {}).get("expected_value_r") or -999.0),
            float((row.get("decision") or {}).get("confidence") or 0.0),
        ),
        reverse=True,
    )
    best = ranked[0] if ranked else None
    actionable = [row for row in rows if (row.get("decision") or {}).get("executable") is True]
    size_ready = [row for row in rows if (row.get("sizing") or {}).get("success") is True]
    return {
        "success": any(row.get("success") for row in rows),
        "version": "14.1",
        "service": "JARVIS_QUANT_V141_EXECUTION_TRACE",
        "symbol": canonical,
        "profiles": list(DEFAULT_TRACE_PROFILES),
        "samples": rows,
        "data_sample_pass": any(row.get("success") for row in rows),
        "actionable_count": len(actionable),
        "size_ready_count": len(size_ready),
        "best_sample": best,
        "best_expected_value_r": (best.get("decision") or {}).get("expected_value_r") if best else None,
        "best_action": (best.get("decision") or {}).get("action") if best else None,
        "best_legacy_score": best.get("legacy_score") if best else None,
        "execution_pipeline_ready": bool(size_ready),
        "data_pass_is_not_execution_pass": True,
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
    }


class QuantTerminalV141Handler(QuantTerminalV14Handler):
    _jarvis_v141_risk_geometry = True
    server_version = "JARVISQuant-V14.1Bridge/1.0"

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)
        if path == "/v141_risk_geometry_runtime.js":
            return self.send_file(
                quant.STATIC / "v141_risk_geometry_runtime.js",
                "application/javascript; charset=utf-8",
            )
        if path == "/api/v14.1/risk-geometry":
            symbol = str((params.get("symbol") or ["BTC"])[0]).strip().upper() or "BTC"
            profile = str((params.get("profile") or ["5m_only"])[0]).strip() or "5m_only"
            payload = quant.scan_payload(symbol, profile=profile)
            return self.send_json({
                "success": bool(payload.get("success")),
                "version": "14.1",
                "service": "JARVIS_QUANT_V141_RISK_GEOMETRY",
                "symbol": payload.get("symbol") or symbol,
                "profile": payload.get("profile") or profile,
                "candidate_side": payload.get("candidate_side"),
                "legacy_score": payload.get("score"),
                "legacy_qualified": payload.get("qualified"),
                "entry": payload.get("entry"),
                "stop": payload.get("stop"),
                "target": payload.get("target"),
                "risk_reward": payload.get("risk_reward"),
                "blockers": payload.get("blockers") or [],
                "geometry": payload.get("risk_geometry_v141") or {},
                "paper_only": True,
                "live_execution": False,
                "automatic_broker_order": False,
            })
        if path == "/api/v14.1/execution-trace":
            symbol = str((params.get("symbol") or ["BTC"])[0]).strip().upper() or "BTC"
            return self.send_json(execution_trace(symbol))
        if path == "/api/v14.1/status":
            from workstation.v141_runtime_bridges import status as runtime_status
            return self.send_json({
                "success": True,
                "version": "14.1",
                "service": "JARVIS_QUANT_V141_RISK_GEOMETRY_CONVERGENCE",
                "runtime": runtime_status(),
                "decision_authority": "POSITIVE_CONTEXTUAL_EXPECTED_VALUE_CONTINUOUS_RISK",
                "invalid_risk_levels_hard_blocker_preserved": True,
                "v141_ui_asset": (quant.STATIC / "v141_risk_geometry_runtime.js").is_file(),
                "paper_only": True,
                "live_execution": False,
                "automatic_broker_order": False,
            })
        return super().do_GET()


def install_quant_terminal_v141_bridge() -> dict[str, Any]:
    global _INSTALLED
    with _LOCK:
        if getattr(quant.Handler, "_jarvis_v141_risk_geometry", False):
            _INSTALLED = True
            return status()
        quant.Handler = QuantTerminalV141Handler
        _INSTALLED = True
        return status()


def status() -> dict[str, Any]:
    with _LOCK:
        installed = _INSTALLED or getattr(quant.Handler, "_jarvis_v141_risk_geometry", False)
    asset = quant.STATIC / "v141_risk_geometry_runtime.js"
    return {
        "success": True,
        "version": "14.1",
        "service": "JARVIS_QUANT_V141_HTTP_BRIDGE",
        "installed": bool(installed),
        "v14_endpoints_preserved": True,
        "risk_geometry_endpoint": "/api/v14.1/risk-geometry",
        "execution_trace_endpoint": "/api/v14.1/execution-trace",
        "v141_ui_asset": asset.is_file(),
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
    }


__all__ = [
    "QuantTerminalV141Handler",
    "install_quant_terminal_v141_bridge",
    "execution_trace",
    "status",
]
