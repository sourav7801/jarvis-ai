from __future__ import annotations

from threading import RLock
from typing import Any

from omni.trading_intelligence.adaptive_opportunity_policy import ADAPTIVE_OPPORTUNITY_POLICY


_LOCK = RLock()
_INSTALLED = False


def install_adaptive_direct_trade_bridge() -> dict[str, Any]:
    """Make legacy paper-control routes use V12 adaptive authority.

    The legacy router/endpoints are retained for compatibility, but their
    paper-autonomy singleton and direct qualification hooks are redirected to
    V12 adaptive expected-value intelligence. Live-entry drift checks,
    accounting and persistent Paper Desk risk remain unchanged.
    """

    global _INSTALLED
    with _LOCK:
        if _INSTALLED:
            return status()

        from workstation import paper_trade_action_router as router
        from workstation import paper_autonomy_engine as legacy_autonomy_module
        from workstation.adaptive_paper_autonomy_engine import adaptive_paper_autonomy

        # Existing /api/paper/autonomy routes import this module-level name at
        # request time. Rebinding it keeps the protected HTTP surface while
        # removing the old static-score singleton from canonical V12 authority.
        legacy_autonomy_module.paper_autonomy = adaptive_paper_autonomy

        if getattr(router, "_v12_adaptive_direct_installed", False):
            _INSTALLED = True
            return status()

        original_consensus = router._consensus_payload

        def adaptive_consensus(symbol: str, profile: str = "intraday") -> dict[str, Any]:
            payload = dict(original_consensus(symbol, profile))
            payload["legacy_qualified"] = bool(payload.get("qualified"))
            payload["legacy_side"] = payload.get("side")
            decision = ADAPTIVE_OPPORTUNITY_POLICY.evaluate(payload)
            payload["adaptive_decision"] = decision
            payload["decision_authority"] = "ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE"
            payload["qualified"] = bool(decision.get("executable"))
            payload["side"] = decision.get("side") if decision.get("executable") else "WAIT"
            payload["paper_only"] = True
            payload["live_execution"] = False
            return payload

        def adaptive_qualified(row: dict[str, Any]) -> bool:
            decision = row.get("adaptive_decision") if isinstance(row.get("adaptive_decision"), dict) else None
            if decision is None:
                decision = ADAPTIVE_OPPORTUNITY_POLICY.evaluate(row)
                row["adaptive_decision"] = decision
            return bool(
                row.get("success")
                and decision.get("executable") is True
                and str(decision.get("side") or "").upper() in {"LONG", "SHORT"}
                and row.get("entry") is not None
                and row.get("stop") is not None
                and row.get("target") is not None
            )

        def adaptive_arm(profile: str = "intraday") -> dict[str, Any]:
            from workstation.paper_portfolio_controller import paper_portfolio_controller

            normalized = str(profile or "intraday").strip().lower()
            bucket = "SWING" if normalized == "swing" else "INVESTMENT" if normalized == "investment" else "INTRADAY"
            result = paper_portfolio_controller.start_bucket(bucket, scan_now=True)
            return {
                **dict(result),
                "decision_authority": "ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE",
                "paper_only": True,
                "live_execution": False,
            }

        router._consensus_payload = adaptive_consensus
        router._qualified = adaptive_qualified
        router._arm_autonomy = adaptive_arm
        router._v12_adaptive_direct_installed = True
        _INSTALLED = True
        return status()


def status() -> dict[str, Any]:
    with _LOCK:
        return {
            "success": True,
            "version": "12.0",
            "installed": _INSTALLED,
            "direct_trade_authority": "ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE",
            "legacy_autonomy_endpoint_redirected": _INSTALLED,
            "legacy_static_68_gate": False if _INSTALLED else None,
            "legacy_static_18_rr_gate": False if _INSTALLED else None,
            "live_entry_drift_check_preserved": True,
            "persistent_paper_risk_preserved": True,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }


__all__ = ["install_adaptive_direct_trade_bridge", "status"]
