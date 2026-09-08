from __future__ import annotations

from threading import RLock
from typing import Any


_LOCK = RLock()
_INSTALLED = False
_ENGINE_HOOKS_INSTALLED = False
DECISION_AUTHORITY = "POSITIVE_CONTEXTUAL_EXPECTED_VALUE_CONTINUOUS_RISK"


def _install_engine_hooks() -> dict[str, Any]:
    global _ENGINE_HOOKS_INSTALLED
    from workstation.adaptive_paper_autonomy_engine import AdaptivePaperAutonomyEngine

    if getattr(AdaptivePaperAutonomyEngine.scan_once, "_jarvis_v14_lifecycle", False):
        _ENGINE_HOOKS_INSTALLED = True
        return {"success": True, "installed": True}

    original_scan_once = AdaptivePaperAutonomyEngine.scan_once
    original_status = AdaptivePaperAutonomyEngine.status

    def v14_status(self):
        payload = dict(original_status(self))
        try:
            from omni.trading_intelligence.continuous_execution_policy_v14 import (
                CONTINUOUS_EXECUTION_POLICY_V14,
            )
            intelligence = CONTINUOUS_EXECUTION_POLICY_V14.status()
        except Exception:
            intelligence = {
                "success": False,
                "decision_authority": DECISION_AUTHORITY,
            }
        payload["adaptive_intelligence"] = {
            **dict(payload.get("adaptive_intelligence") or {}),
            **intelligence,
            "strategy_version": "QUANT_AUTONOMOUS_EXECUTION_V14",
            "watching_is_terminal_state": False,
        }
        payload["decision_authority"] = DECISION_AUTHORITY
        payload["static_score_execution_authority"] = False
        payload["arbitrary_confidence_execution_gate"] = False
        payload["positive_ev_execution_boundary_r"] = 0.0
        payload["paper_only"] = True
        payload["live_execution"] = False
        payload["automatic_broker_order"] = False
        return payload

    def v14_scan_once(self):
        result = original_scan_once(self)
        try:
            from workstation.opportunity_lifecycle_v14 import OPPORTUNITY_LIFECYCLE_V14
            lifecycle = OPPORTUNITY_LIFECYCLE_V14.observe_engine(self, result)
            if isinstance(result, dict):
                result = dict(result)
                result["opportunity_lifecycle"] = lifecycle
                result["decision_authority"] = DECISION_AUTHORITY
        except Exception as exc:
            if isinstance(result, dict):
                result = dict(result)
                result["opportunity_lifecycle"] = {
                    "success": False,
                    "reason": f"{type(exc).__name__}: {exc}"[:300],
                    "paper_only": True,
                    "live_execution": False,
                }
        return result

    v14_status._jarvis_v14_status = True
    v14_status._jarvis_v14_original = original_status
    v14_scan_once._jarvis_v14_lifecycle = True
    v14_scan_once._jarvis_v14_original = original_scan_once
    AdaptivePaperAutonomyEngine.status = v14_status
    AdaptivePaperAutonomyEngine.scan_once = v14_scan_once
    _ENGINE_HOOKS_INSTALLED = True
    return {"success": True, "installed": True}


def install_v14_runtime_bridges() -> dict[str, Any]:
    """Install V14 continuous paper authority into canonical runtime objects.

    V13 remains the contextual evidence engine. V14 changes only the final paper
    execution authority: hard safety/data blockers still veto, but confidence,
    score, alignment and static R:R no longer create arbitrary binary entry
    thresholds. Positive contextual EV receives continuous, uncertainty-scaled
    paper risk and verified fractional sizing.
    """

    global _INSTALLED
    with _LOCK:
        if _INSTALLED:
            return status()

        from workstation.v13_runtime_bridges import install_v13_runtime_bridges
        v13 = install_v13_runtime_bridges()

        from omni.trading_intelligence.continuous_execution_policy_v14 import (
            CONTINUOUS_EXECUTION_POLICY_V14,
            POLICY_VERSION,
        )
        from workstation import adaptive_paper_autonomy_engine as adaptive_engine_module
        from workstation import adaptive_direct_trade_bridge as direct_bridge_module
        from workstation import adaptive_market_sampler as sampler_module
        from workstation.paper_execution_sizing_v13 import install_v13_execution_sizing_bridge

        sizing = install_v13_execution_sizing_bridge()
        adaptive_engine_module.ADAPTIVE_OPPORTUNITY_POLICY = CONTINUOUS_EXECUTION_POLICY_V14
        adaptive_engine_module.POLICY_VERSION = POLICY_VERSION
        adaptive_engine_module.STRATEGY_VERSION = "QUANT_AUTONOMOUS_EXECUTION_V14"
        direct_bridge_module.ADAPTIVE_OPPORTUNITY_POLICY = CONTINUOUS_EXECUTION_POLICY_V14
        sampler_module.ADAPTIVE_OPPORTUNITY_POLICY = CONTINUOUS_EXECUTION_POLICY_V14

        hooks = _install_engine_hooks()
        _INSTALLED = True
        return {
            **status(),
            "v13": v13,
            "execution_sizing": sizing,
            "engine_hooks": hooks,
        }


def status() -> dict[str, Any]:
    with _LOCK:
        installed = _INSTALLED
        hooks = _ENGINE_HOOKS_INSTALLED
    try:
        from workstation.paper_execution_sizing_v13 import status as sizing_status
        sizing = sizing_status()
    except Exception:
        sizing = {"installed": False}
    return {
        "success": True,
        "version": "14.0",
        "service": "JARVIS_AUTONOMOUS_EXECUTION_INTELLIGENCE_V14",
        "installed": installed,
        "engine_hooks_installed": hooks,
        "decision_authority": DECISION_AUTHORITY,
        "contextual_v13_evidence_preserved": True,
        "closed_paper_outcome_memory_preserved": True,
        "dynamic_correlation_preserved": True,
        "continuous_positive_ev_execution": True,
        "positive_ev_execution_boundary_r": 0.0,
        "uncertainty_scales_risk_not_execution": True,
        "arbitrary_confidence_execution_gate": False,
        "static_67_68_70_execution_authority": False,
        "static_alignment_execution_authority": False,
        "static_risk_reward_execution_authority": False,
        "fractional_constraint_aware_sizing": bool(sizing.get("installed")),
        "watching_is_terminal_state": False,
        "opportunity_lifecycle": True,
        "paper_only": True,
        "live_execution": False,
        "automatic_broker_order": False,
        "automatic_production_strategy_rewrite": False,
    }


__all__ = ["install_v14_runtime_bridges", "status", "DECISION_AUTHORITY"]
