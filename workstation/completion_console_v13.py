"""JARVIS V13 Adaptive Intelligence Operating Center.

Extends V12 with context-conditioned paper decisions, dynamic completed-bar
portfolio correlation, bounded decision forensics, verified options-volatility
synthesis and a governed strategy lifecycle. No live broker/order or automatic
production strategy rewrite surface is introduced.
"""
from __future__ import annotations

import urllib.parse
from typing import Any, Callable

from omni.loopback_http import exclusive_server
from omni.subsystem_snapshot import SubsystemSnapshotCollector, sanitize_error
from workstation import completion_console_v12 as v12


HOST = v12.HOST
PORT = v12.PORT
STATIC = v12.STATIC
HEALTH = v12.HEALTH
V13 = SubsystemSnapshotCollector(max_inflight=6)


def _contextual_decision() -> dict[str, Any]:
    from omni.trading_intelligence.contextual_decision_engine_v13 import CONTEXTUAL_DECISION_ENGINE_V13
    return CONTEXTUAL_DECISION_ENGINE_V13.status()


def _contextual_memory() -> dict[str, Any]:
    from omni.trading_intelligence.contextual_outcome_memory import CONTEXTUAL_OUTCOME_MEMORY
    return CONTEXTUAL_OUTCOME_MEMORY.snapshot()


def _forensics() -> dict[str, Any]:
    from omni.trading_intelligence.decision_forensics_v13 import DECISION_FORENSICS_V13
    return DECISION_FORENSICS_V13.snapshot(limit=60)


def _correlation() -> dict[str, Any]:
    from workstation.dynamic_correlation_risk_v13 import DYNAMIC_CORRELATION_RISK_V13
    return DYNAMIC_CORRELATION_RISK_V13.snapshot()


def _options() -> dict[str, Any]:
    from omni.trading_intelligence.options_volatility_synthesis_v13 import OPTIONS_VOLATILITY_SYNTHESIS_V13
    return OPTIONS_VOLATILITY_SYNTHESIS_V13.status()


def _strategy_governance() -> dict[str, Any]:
    from omni.trading_intelligence.strategy_governance_pipeline_v13 import STRATEGY_GOVERNANCE_PIPELINE_V13
    return STRATEGY_GOVERNANCE_PIPELINE_V13.snapshot(limit=60)


def _runtime_bridge() -> dict[str, Any]:
    from workstation.v13_runtime_bridges import status
    return status()


def _v13_providers() -> dict[str, Callable[[], Any]]:
    return {
        "contextual_decision_engine": _contextual_decision,
        "contextual_outcome_memory": _contextual_memory,
        "decision_forensics": _forensics,
        "dynamic_portfolio_correlation": _correlation,
        "options_volatility_synthesis": _options,
        "strategy_governance_v13": _strategy_governance,
        "v13_runtime_bridge": _runtime_bridge,
    }


def overview_payload() -> dict[str, Any]:
    payload = v12.overview_payload()
    payload["version"] = "13.0"
    advanced = V13.collect(_v13_providers(), timeout=2.5)
    payload.setdefault("subsystems", {}).update(advanced)
    for name, row in advanced.items():
        payload[name] = row.get("data") if row.get("healthy") else None
    if not all(row.get("healthy") for row in advanced.values()):
        payload["overall"] = "DEGRADED"
    payload.setdefault("advanced", {}).update({
        "contextual_expected_value": True,
        "contextual_closed_paper_outcomes": True,
        "dynamic_completed_bar_correlation": True,
        "decision_forensics": True,
        "continuous_top_n_discovery": True,
        "verified_options_volatility_synthesis": True,
        "governed_strategy_lifecycle": True,
        "quant_runtime_authoritative": True,
    })
    payload["decision_authority"] = {
        "version": "13.0",
        "model": "CONTEXTUAL_EXPECTED_VALUE_WITH_OUTCOME_MEMORY",
        "base": "V12_ADAPTIVE_EXPECTED_VALUE",
        "static_score_67_68_70": "OBSERVABILITY_ONLY",
        "static_discovery_score_gate": False,
        "dynamic_portfolio_correlation": "RISK_REDUCTION_ONLY",
        "actions": ["PRIMARY", "PROBE", "WAIT"],
    }
    payload.setdefault("safety", {}).update({
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
        "automatic_production_strategy_rewrite": False,
        "external_actions": "APPROVAL_GATED",
    })
    return payload


class CompletionHandlerV13(v12.CompletionHandlerV12):
    server_version = "JARVISCompletion/13.0"

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)
        if path == "/v13_intelligence_os.js":
            return self.send_file(STATIC / "v13_intelligence_os.js", "application/javascript; charset=utf-8")
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
                }, 500)
        if path == "/api/contextual-decision":
            return self.send_json(_contextual_decision())
        if path == "/api/contextual-memory":
            return self.send_json(_contextual_memory())
        if path == "/api/decision-forensics":
            from omni.trading_intelligence.decision_forensics_v13 import DECISION_FORENSICS_V13
            symbol = str((params.get("symbol") or [""])[0]).strip() or None
            return self.send_json(DECISION_FORENSICS_V13.snapshot(symbol=symbol, limit=100))
        if path == "/api/portfolio-correlation":
            from workstation.dynamic_correlation_risk_v13 import DYNAMIC_CORRELATION_RISK_V13
            symbol = str((params.get("symbol") or [""])[0]).strip()
            side = str((params.get("side") or [""])[0]).strip()
            profile = str((params.get("profile") or ["adaptive_intraday"])[0]).strip()
            if symbol and side:
                try:
                    return self.send_json(DYNAMIC_CORRELATION_RISK_V13.assess(
                        symbol=symbol, side=side, profile=profile,
                    ))
                except Exception as exc:
                    return self.send_json({
                        "success": False,
                        "message": sanitize_error(exc)[:500],
                        "paper_only": True,
                        "live_execution": False,
                    }, 503)
            return self.send_json(DYNAMIC_CORRELATION_RISK_V13.snapshot())
        if path == "/api/options-volatility":
            from omni.trading_intelligence.options_volatility_synthesis_v13 import OPTIONS_VOLATILITY_SYNTHESIS_V13
            symbol = str((params.get("symbol") or [""])[0]).strip().upper()
            if symbol:
                return self.send_json(OPTIONS_VOLATILITY_SYNTHESIS_V13.history(symbol))
            return self.send_json(OPTIONS_VOLATILITY_SYNTHESIS_V13.status())
        if path == "/api/strategy-governance-v13":
            return self.send_json(_strategy_governance())
        if path == "/api/v13/status":
            bridge = _runtime_bridge()
            return self.send_json({
                "success": True,
                "version": "13.0",
                "service": "JARVIS_ADAPTIVE_INTELLIGENCE_OPERATING_SYSTEM",
                "features": {
                    "v12_adaptive_market_intelligence": True,
                    "contextual_expected_value": True,
                    "closed_paper_outcome_memory": True,
                    "dynamic_completed_bar_correlation": True,
                    "decision_forensics": True,
                    "continuous_top_n_discovery": True,
                    "verified_options_volatility_synthesis": True,
                    "strategy_governance_pipeline": True,
                    "static_score_execution_authority": False,
                    "static_discovery_score_gate": False,
                },
                "runtime_bridge_installed": bool(bridge.get("installed")),
                "decision_authority": "CONTEXTUAL_EXPECTED_VALUE_NOT_STATIC_SCORE",
                "permanent_agents": 29,
                "system_planes_do_not_count_as_agents": True,
                "paper_only": True,
                "live_execution": False,
                "automatic_broker_order": False,
                "automatic_production_strategy_rewrite": False,
                "external_actions": "APPROVAL_GATED",
            })
        return super().do_GET()


def main() -> int:
    from workstation.v13_runtime_bridges import install_v13_runtime_bridges

    bridge = install_v13_runtime_bridges()
    server = exclusive_server(HOST, PORT, CompletionHandlerV13)
    print("=" * 72)
    print("JARVIS V13 ADAPTIVE INTELLIGENCE OPERATING CENTER")
    print("=" * 72)
    print(f"Console: http://{HOST}:{PORT}")
    print("Decision authority: CONTEXTUAL EV + OUTCOME MEMORY + UNCERTAINTY")
    print("Discovery: CONTINUOUS TOP-N / NO FIXED DISCOVERY SCORE GATE")
    print("Portfolio correlation: COMPLETED-BAR / RISK-REDUCTION ONLY")
    print("Decision forensics: BOUNDED / EXPLAINABLE")
    print("Options volatility: VERIFIED HISTORY ONLY / NO FAKE DEALER GAMMA")
    print("Strategy lifecycle: RESEARCH -> VALIDATED -> CHALLENGER -> PAPER SHADOW -> REVIEW -> CHAMPION")
    print("V13 bridge:", "READY" if bridge.get("installed") else "DEGRADED")
    print("Paper trading: PERMITTED")
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
