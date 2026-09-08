from __future__ import annotations

import urllib.parse
from threading import RLock
from typing import Any

from workstation import quant_terminal_v2 as quant
from workstation.quant_terminal_v141_bridge import QuantTerminalV141Handler, _sizing_plan


_LOCK = RLock()
_INSTALLED = False
DEFAULT_PROFILES = ("5m_only", "10m_only", "15m_only", "adaptive_intraday", "swing")


def _persist_forensics(
    *,
    symbol: str,
    profile: str,
    scan: dict[str, Any],
    reasoning: dict[str, Any],
    decision: dict[str, Any],
    sizing: dict[str, Any],
    stop_reason: str,
) -> None:
    """Record bounded high-information stages for an explicit persisted trace."""
    try:
        from workstation.execution_forensics_v15 import EXECUTION_FORENSICS_V15

        base_payload = {
            "candidate_side": scan.get("candidate_side"),
            "legacy_score": scan.get("score"),
            "legacy_qualified": scan.get("qualified"),
            "entry": scan.get("entry"),
            "stop": scan.get("stop"),
            "target": scan.get("target"),
            "risk_reward": scan.get("risk_reward"),
        }
        EXECUTION_FORENSICS_V15.record(
            "DISCOVERY",
            symbol=symbol,
            profile=profile,
            reason="VERIFIED_SCAN_SAMPLE" if scan.get("success") else "DATA_UNAVAILABLE",
            payload=base_payload,
        )
        if reasoning.get("success"):
            EXECUTION_FORENSICS_V15.record(
                "BELIEF_UPDATE",
                symbol=symbol,
                profile=profile,
                reason=str((reasoning.get("market_belief") or {}).get("signal_freshness") or "BELIEF_BUILT"),
                payload={"market_belief": reasoning.get("market_belief"), "data_provenance": reasoning.get("data_provenance")},
            )
            EXECUTION_FORENSICS_V15.record(
                "HYPOTHESIS_BUILD",
                symbol=symbol,
                profile=profile,
                reason=str((reasoning.get("dominant_hypothesis") or {}).get("name") or "HYPOTHESES_BUILT"),
                payload={"hypotheses": list(reasoning.get("hypotheses") or [])[:4]},
            )
        EXECUTION_FORENSICS_V15.record(
            "DECISION",
            symbol=symbol,
            profile=profile,
            reason=str(decision.get("action") or "WAIT"),
            payload={
                "expected_value_r": decision.get("expected_value_r"),
                "confidence": decision.get("confidence"),
                "hard_blockers": decision.get("hard_blockers"),
                "risk_multiplier": decision.get("risk_multiplier"),
            },
        )
        EXECUTION_FORENSICS_V15.record(
            "PORTFOLIO_ALLOCATION",
            symbol=symbol,
            profile=profile,
            reason="BETTER_OPPORTUNITY_AVAILABLE" if decision.get("better_opportunity_available") else "UTILITY_ALLOCATED",
            payload={
                "portfolio_adjusted_utility": decision.get("portfolio_adjusted_utility"),
                "opportunity_rank": decision.get("opportunity_rank"),
                "opportunity_count": decision.get("opportunity_count"),
                "portfolio_allocation_multiplier": decision.get("portfolio_allocation_multiplier"),
                "portfolio_correlation_utility_multiplier": decision.get("portfolio_correlation_utility_multiplier"),
            },
        )
        EXECUTION_FORENSICS_V15.record(
            "SIZE_PLAN",
            symbol=symbol,
            profile=profile,
            reason="SIZE_READY" if sizing.get("success") else str(sizing.get("reason") or stop_reason),
            payload={
                "success": sizing.get("success"),
                "quantity": sizing.get("quantity"),
                "risk_multiplier": decision.get("risk_multiplier"),
                "pipeline_stop_reason": stop_reason,
            },
        )
    except Exception:
        # Forensics are observability only and must never block paper decisions.
        pass


def _reason_profile(symbol: str, profile: str, *, persist: bool = False) -> dict[str, Any]:
    from omni.trading_intelligence.autonomous_decision_engine_v15 import AUTONOMOUS_DECISION_ENGINE_V15

    scan = quant.scan_payload(symbol, profile=profile)
    allowed = ("LONG",) if profile == "investment" else ("LONG", "SHORT")
    decision = AUTONOMOUS_DECISION_ENGINE_V15.evaluate(scan, allowed_sides=allowed)
    reasoning = decision.get("market_reasoning_v15") if isinstance(decision.get("market_reasoning_v15"), dict) else {}
    belief_update = None
    if persist and reasoning.get("success"):
        try:
            from workstation.market_belief_store_v15 import MARKET_BELIEF_STORE_V15
            belief_update = MARKET_BELIEF_STORE_V15.record(reasoning)
        except Exception as exc:
            belief_update = {"success": False, "reason": f"{type(exc).__name__}: {exc}"[:300]}
    sizing = _sizing_plan(scan, decision)
    stages = {
        "DISCOVERED": bool(scan.get("success")),
        "BELIEF_BUILT": bool(reasoning.get("success")),
        "HYPOTHESES_BUILT": bool(reasoning.get("hypotheses")),
        "RISK_MODEL_BUILT": bool(
            scan.get("entry") is not None
            and scan.get("stop") is not None
            and scan.get("target") is not None
        ),
        "PORTFOLIO_UTILITY_EVALUATED": True,
        "ACTIONABLE": decision.get("executable") is True,
        "SIZE_PLANNED": sizing.get("success") is True,
    }
    hard = [str(item) for item in list(decision.get("hard_blockers") or [])]
    if not stages["DISCOVERED"]:
        stop_reason = "DATA_UNAVAILABLE"
    elif not stages["RISK_MODEL_BUILT"]:
        stop_reason = "INVALID_RISK_LEVELS"
    elif hard:
        stop_reason = hard[0]
    elif float(decision.get("expected_value_r") or 0.0) <= 0.0:
        stop_reason = "NON_POSITIVE_CONTEXTUAL_EV"
    elif decision.get("executable") is not True:
        stop_reason = "BETTER_OPPORTUNITY_AVAILABLE" if decision.get("better_opportunity_available") else "PORTFOLIO_UTILITY_WAIT"
    elif sizing.get("success") is not True:
        stop_reason = str(sizing.get("reason") or "POSITION_SIZE_PLAN_FAILED")
    else:
        stop_reason = "READY_FOR_PAPER_DESK_OPEN"

    if persist:
        _persist_forensics(
            symbol=str(scan.get("symbol") or symbol).upper(),
            profile=str(scan.get("profile") or profile),
            scan=scan,
            reasoning=reasoning,
            decision=decision,
            sizing=sizing,
            stop_reason=stop_reason,
        )

    return {
        "success": bool(scan.get("success")),
        "symbol": scan.get("symbol") or symbol,
        "profile": scan.get("profile") or profile,
        "timeframe": scan.get("timeframe"),
        "candidate_side": scan.get("candidate_side"),
        "legacy_score": scan.get("score"),
        "legacy_qualified": scan.get("qualified"),
        "entry": scan.get("entry"),
        "stop": scan.get("stop"),
        "target": scan.get("target"),
        "risk_reward": scan.get("risk_reward"),
        "risk_geometry": scan.get("risk_geometry_v141") or {},
        "market_reasoning": reasoning,
        "decision": decision,
        "sizing": sizing,
        "belief_update": belief_update,
        "stages": stages,
        "pipeline_stop_reason": stop_reason,
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
    }


def reasoning_trace(symbol: str = "BTC", *, persist: bool = False) -> dict[str, Any]:
    canonical = str(symbol or "BTC").strip().upper() or "BTC"
    rows = [_reason_profile(canonical, profile, persist=persist) for profile in DEFAULT_PROFILES]
    ranked = sorted(
        rows,
        key=lambda row: (
            float((row.get("decision") or {}).get("portfolio_adjusted_utility") or -999.0),
            float((row.get("decision") or {}).get("expected_value_r") or -999.0),
        ),
        reverse=True,
    )
    best = ranked[0] if ranked else None
    actionable = [row for row in rows if (row.get("decision") or {}).get("executable") is True]
    size_ready = [row for row in rows if (row.get("sizing") or {}).get("success") is True]
    return {
        "success": any(row.get("success") for row in rows),
        "version": "15.0",
        "service": "JARVIS_QUANT_V15_REASONING_TRACE",
        "symbol": canonical,
        "samples": rows,
        "profiles": list(DEFAULT_PROFILES),
        "actionable_count": len(actionable),
        "size_ready_count": len(size_ready),
        "best_sample": best,
        "best_action": (best.get("decision") or {}).get("action") if best else None,
        "best_expected_value_r": (best.get("decision") or {}).get("expected_value_r") if best else None,
        "best_portfolio_utility": (best.get("decision") or {}).get("portfolio_adjusted_utility") if best else None,
        "best_legacy_score": best.get("legacy_score") if best else None,
        "execution_pipeline_ready": bool(size_ready),
        "data_connectivity_is_not_execution_proof": True,
        "forensics_persisted": bool(persist),
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
    }


def _position_intelligence() -> dict[str, Any]:
    from workstation.position_intelligence_v15 import POSITION_INTELLIGENCE_V15
    return POSITION_INTELLIGENCE_V15.snapshot()


def _causal_reviews(limit: int = 30) -> dict[str, Any]:
    from omni.trading_intelligence.causal_trade_review_v15 import CAUSAL_TRADE_REVIEW_V15
    from workstation.paper_autonomy_engine import paper_desk
    try:
        rows = list(paper_desk.closed_positions(max(1, min(int(limit), 100))))
    except Exception as exc:
        return {
            "success": False,
            "version": "15.0",
            "service": "JARVIS_V15_CAUSAL_REVIEWS",
            "reason": f"{type(exc).__name__}: {exc}"[:300],
            "paper_only": True,
            "live_execution": False,
        }
    reviews = [CAUSAL_TRADE_REVIEW_V15.review(row) for row in rows]
    return {
        "success": True,
        "version": "15.0",
        "service": "JARVIS_V15_CAUSAL_REVIEWS",
        "reviews": reviews,
        "count": len(reviews),
        "decision_quality_separate_from_outcome": True,
        "paper_only": True,
        "live_execution": False,
    }


class QuantTerminalV15Handler(QuantTerminalV141Handler):
    _jarvis_v15_reasoning = True
    server_version = "JARVISQuant-V15Bridge/1.0"

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)
        if path == "/v15_market_reasoning_runtime.js":
            return self.send_file(quant.STATIC / "v15_market_reasoning_runtime.js", "application/javascript; charset=utf-8")
        if path == "/api/v15/reasoning-trace":
            symbol = str((params.get("symbol") or ["BTC"])[0]).strip().upper() or "BTC"
            persist = str((params.get("persist") or ["0"])[0]).lower() in {"1", "true", "yes"}
            return self.send_json(reasoning_trace(symbol, persist=persist))
        if path == "/api/v15/market-beliefs":
            symbol = str((params.get("symbol") or ["BTC"])[0]).strip().upper() or "BTC"
            profile = str((params.get("profile") or ["5m_only"])[0]).strip() or "5m_only"
            from workstation.market_belief_store_v15 import MARKET_BELIEF_STORE_V15
            return self.send_json(MARKET_BELIEF_STORE_V15.history(symbol, profile, limit=30))
        if path == "/api/v15/position-intelligence":
            return self.send_json(_position_intelligence())
        if path == "/api/v15/causal-trade-review":
            return self.send_json(_causal_reviews(30))
        if path == "/api/v15/execution-forensics":
            symbol = str((params.get("symbol") or [""])[0]).strip().upper()
            from workstation.execution_forensics_v15 import EXECUTION_FORENSICS_V15
            return self.send_json(EXECUTION_FORENSICS_V15.snapshot(symbol=symbol or None, limit=160))
        if path == "/api/v15/status":
            from omni.trading_intelligence.autonomous_decision_engine_v15 import AUTONOMOUS_DECISION_ENGINE_V15
            from workstation.v15_runtime_bridges import status as runtime_status
            from workstation.position_intelligence_v15 import POSITION_INTELLIGENCE_V15
            return self.send_json({
                "success": True,
                "version": "15.0",
                "service": "JARVIS_QUANT_V15_AUTONOMOUS_MARKET_REASONING",
                "runtime": runtime_status(),
                "decision": AUTONOMOUS_DECISION_ENGINE_V15.status(),
                "position_intelligence": POSITION_INTELLIGENCE_V15.status(),
                "v141_endpoints_preserved": True,
                "invalid_risk_levels_hard_blocker_preserved": True,
                "paper_only": True,
                "live_execution": False,
                "automatic_broker_order": False,
            })
        return super().do_GET()


def install_quant_terminal_v15_bridge() -> dict[str, Any]:
    global _INSTALLED
    with _LOCK:
        if getattr(quant.Handler, "_jarvis_v15_reasoning", False):
            _INSTALLED = True
            return status()
        quant.Handler = QuantTerminalV15Handler
        _INSTALLED = True
        return status()


def status() -> dict[str, Any]:
    with _LOCK:
        installed = _INSTALLED or getattr(quant.Handler, "_jarvis_v15_reasoning", False)
    asset = quant.STATIC / "v15_market_reasoning_runtime.js"
    return {
        "success": True,
        "version": "15.0",
        "service": "JARVIS_QUANT_V15_HTTP_BRIDGE",
        "installed": bool(installed),
        "v141_endpoints_preserved": True,
        "v15_reasoning_asset": asset.is_file(),
        "decision_authority": "PORTFOLIO_ADJUSTED_CONTEXTUAL_UTILITY_CONTINUOUS_RISK",
        "execution_forensics_stages": True,
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
    }


__all__ = ["QuantTerminalV15Handler", "install_quant_terminal_v15_bridge", "reasoning_trace", "status"]
