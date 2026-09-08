from __future__ import annotations

from threading import RLock
from typing import Any


_LOCK = RLock()
_INSTALLED = False
_ENGINE_HOOKS_INSTALLED = False
DECISION_AUTHORITY = "PORTFOLIO_ADJUSTED_CONTEXTUAL_UTILITY_CONTINUOUS_RISK"


def _install_engine_hooks() -> dict[str, Any]:
    global _ENGINE_HOOKS_INSTALLED
    from workstation.adaptive_paper_autonomy_engine import AdaptivePaperAutonomyEngine

    current_scan = AdaptivePaperAutonomyEngine.scan_once
    if getattr(current_scan, "_jarvis_v15_reasoning", False):
        _ENGINE_HOOKS_INSTALLED = True
        return {"success": True, "installed": True}

    current_status = AdaptivePaperAutonomyEngine.status

    def v15_status(self):
        payload = dict(current_status(self))
        try:
            from omni.trading_intelligence.autonomous_decision_engine_v15 import AUTONOMOUS_DECISION_ENGINE_V15
            intelligence = AUTONOMOUS_DECISION_ENGINE_V15.status()
        except Exception:
            intelligence = {"success": False, "decision_authority": DECISION_AUTHORITY}
        payload["adaptive_intelligence"] = {
            **dict(payload.get("adaptive_intelligence") or {}),
            **intelligence,
            "strategy_version": "QUANT_AUTONOMOUS_MARKET_REASONING_V15",
            "v141_risk_geometry_preserved": True,
        }
        payload["decision_authority"] = DECISION_AUTHORITY
        payload["portfolio_opportunity_cost"] = True
        payload["multi_hypothesis_reasoning"] = True
        payload["market_belief_model"] = True
        payload["paper_only"] = True
        payload["live_execution"] = False
        payload["automatic_broker_order"] = False
        return payload

    def v15_scan_once(self):
        result = current_scan(self)
        if not isinstance(result, dict):
            return result
        result = dict(result)
        result["decision_authority"] = DECISION_AUTHORITY
        result["autonomous_market_reasoning_v15"] = True
        result["portfolio_opportunity_cost"] = True
        try:
            from workstation.execution_forensics_v15 import EXECUTION_FORENSICS_V15
            for opened in list(result.get("opened") or [])[:8]:
                if isinstance(opened, dict):
                    EXECUTION_FORENSICS_V15.record(
                        "POSITION_OPENED",
                        symbol=str(opened.get("symbol") or ""),
                        profile=str(result.get("profile") or ""),
                        reason=str(opened.get("reason") or "PAPER_POSITION_OPENED"),
                        payload=opened,
                    )
            for reason, count in list((result.get("rejection_counts") or {}).items())[:24]:
                if int(count or 0) > 0:
                    EXECUTION_FORENSICS_V15.record(
                        "PAPER_DESK_REJECTED",
                        profile=str(result.get("profile") or ""),
                        reason=str(reason),
                        payload={"count": int(count or 0)},
                    )
        except Exception:
            pass
        return result

    v15_status._jarvis_v15_status = True
    v15_status._jarvis_v15_original = current_status
    v15_scan_once._jarvis_v15_reasoning = True
    v15_scan_once._jarvis_v15_original = current_scan
    AdaptivePaperAutonomyEngine.status = v15_status
    AdaptivePaperAutonomyEngine.scan_once = v15_scan_once
    _ENGINE_HOOKS_INSTALLED = True
    return {"success": True, "installed": True}


def install_v15_runtime_bridges() -> dict[str, Any]:
    """Install V15 reasoning as the final paper decision authority.

    Installation order is intentional: V14.1 first restores valid verified risk
    geometry, then V15 replaces only the final policy object used by the paper
    engines/direct paper command/sampler. V15 cannot increase V14 risk and does
    not expose broker order methods.
    """

    global _INSTALLED
    with _LOCK:
        if _INSTALLED:
            return status()

        from workstation.v141_runtime_bridges import install_v141_runtime_bridges
        v141 = install_v141_runtime_bridges()

        from omni.trading_intelligence.autonomous_decision_engine_v15 import (
            AUTONOMOUS_DECISION_ENGINE_V15,
            POLICY_VERSION,
        )
        from workstation import adaptive_paper_autonomy_engine as adaptive_engine_module
        from workstation import adaptive_direct_trade_bridge as direct_bridge_module
        from workstation import adaptive_market_sampler as sampler_module
        from workstation.paper_execution_sizing_v13 import install_v13_execution_sizing_bridge

        sizing = install_v13_execution_sizing_bridge()
        adaptive_engine_module.ADAPTIVE_OPPORTUNITY_POLICY = AUTONOMOUS_DECISION_ENGINE_V15
        adaptive_engine_module.POLICY_VERSION = POLICY_VERSION
        adaptive_engine_module.STRATEGY_VERSION = "QUANT_AUTONOMOUS_MARKET_REASONING_V15"
        direct_bridge_module.ADAPTIVE_OPPORTUNITY_POLICY = AUTONOMOUS_DECISION_ENGINE_V15
        sampler_module.ADAPTIVE_OPPORTUNITY_POLICY = AUTONOMOUS_DECISION_ENGINE_V15

        hooks = _install_engine_hooks()
        _INSTALLED = bool(v141.get("installed") and sizing.get("installed") and hooks.get("installed"))
        return {
            **status(),
            "v141": v141,
            "execution_sizing": sizing,
            "engine_hooks": hooks,
        }


def status() -> dict[str, Any]:
    with _LOCK:
        installed = _INSTALLED
        hooks = _ENGINE_HOOKS_INSTALLED
    try:
        from workstation.v141_runtime_bridges import status as v141_status
        risk_geometry = v141_status()
    except Exception:
        risk_geometry = {"installed": False, "scan_wrapper_installed": False}
    try:
        from workstation.paper_execution_sizing_v13 import status as sizing_status
        sizing = sizing_status()
    except Exception:
        sizing = {"installed": False}
    return {
        "success": True,
        "version": "15.0",
        "service": "JARVIS_AUTONOMOUS_MARKET_REASONING_V15",
        "installed": installed,
        "engine_hooks_installed": hooks,
        "decision_authority": DECISION_AUTHORITY,
        "v141_risk_geometry_installed": risk_geometry.get("installed") is True,
        "scan_wrapper_installed": risk_geometry.get("scan_wrapper_installed") is True,
        "invalid_risk_levels_hard_blocker_preserved": True,
        "continuous_positive_contextual_ev_preserved": True,
        "market_belief_model": True,
        "multi_hypothesis_reasoning": True,
        "portfolio_opportunity_cost": True,
        "position_intelligence": True,
        "causal_trade_review": True,
        "execution_forensics": True,
        "fractional_constraint_aware_sizing": sizing.get("installed") is True,
        "portfolio_allocator_can_only_reduce_v14_risk": True,
        "legacy_score_execution_authority": False,
        "watching_is_terminal_state": False,
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
        "automatic_production_strategy_rewrite": False,
        "external_actions": "APPROVAL_GATED",
    }


__all__ = ["install_v15_runtime_bridges", "status", "DECISION_AUTHORITY"]
