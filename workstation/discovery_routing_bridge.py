from __future__ import annotations

from threading import RLock
from typing import Any


_LOCK = RLock()
_INSTALLED = False


def _annotate_discovery_rows(rows: Any) -> list[dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    for raw in list(rows or []):
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        row.setdefault("discovery_timeframe", "1d")
        row["score_kind"] = "DISCOVERY"
        row["execution_authority"] = False
        row["execution_score_required"] = True
        row["completed_bar_discovery"] = True
        row["suggested_execution_horizons"] = ["INTRADAY", "SWING"]
        if (
            str(row.get("direction") or "").upper() == "BULLISH"
            and str(row.get("state") or "").upper() == "CONFIRMED_BREAKOUT"
            and float(row.get("score") or 0.0) >= 65.0
        ):
            row["suggested_execution_horizons"].append("INVESTMENT")
        annotated.append(row)
    return annotated


def install_discovery_routing_bridge() -> dict[str, Any]:
    """Route scanner auto-enrollment through the portfolio horizon controller.

    Older scanner code enrolled every discovery candidate directly into the
    singleton intraday engine. V8.1 added a downstream horizon router, but the
    legacy direct auto-enroll path could still race it and trigger duplicate
    intraday scans. V11 replaces that method at runtime with one bounded,
    portfolio-aware route while leaving discovery scoring itself unchanged.

    Scanner responses are also annotated so a broad daily discovery score can
    never be confused with a horizon-specific execution score.
    """

    global _INSTALLED
    with _LOCK:
        if _INSTALLED:
            return status()

        from workstation import multi_market_scanner as scanner_module

        scanner_cls = scanner_module.MultiMarketScanner
        if getattr(scanner_cls, "_v11_governed_routing_installed", False):
            _INSTALLED = True
            return status()

        original_status = scanner_cls.status

        def governed_enroll(self: Any) -> None:
            rows = [
                dict(row)
                for row in list(getattr(self, "_results", []) or [])
                if isinstance(row, dict)
                and row.get("candidate") is True
                and row.get("auto_paper_eligible") is True
            ]
            if not rows:
                result = {
                    "routed_at": None,
                    "source": "MULTI_MARKET_DISCOVERY",
                    "discovery_candidates": 0,
                    "intraday_symbols": [],
                    "swing_symbols": [],
                    "investment_symbols": [],
                    "contract": "DISCOVERY_SCORE_IS_NOT_EXECUTION_SCORE",
                    "paper_only": True,
                    "live_execution": False,
                }
            else:
                from workstation.paper_portfolio_controller import paper_portfolio_controller

                result = paper_portfolio_controller.enroll_discovery_candidates(rows)
            self._v11_last_governed_routing = dict(result)
            self._v11_last_governed_routing_completed_at = getattr(self, "_completed_at", None)

        def status_v11(self: Any) -> dict[str, Any]:
            payload = dict(original_status(self))
            routing = dict(getattr(self, "_v11_last_governed_routing", {}) or {})
            payload["candidates"] = _annotate_discovery_rows(payload.get("candidates"))
            payload["results"] = _annotate_discovery_rows(payload.get("results"))
            payload["governed_auto_routing"] = routing
            payload["governed_auto_routing_completed_at"] = getattr(
                self, "_v11_last_governed_routing_completed_at", None
            )
            payload["routing_contract"] = "PORTFOLIO_HORIZON_CONTROLLER_ONLY"
            payload["score_contract"] = {
                "score_kind": "DISCOVERY",
                "timeframe": "1d",
                "execution_authority": False,
                "execution_score_required": True,
                "message": (
                    "Scanner score ranks completed-bar discoveries only. Each routed mandate/lane "
                    "must independently recompute execution score, pattern, R:R, freshness, session and risk gates."
                ),
            }
            payload["paper_only"] = True
            payload["live_execution"] = False
            return payload

        scanner_cls._enroll_candidates_locked = governed_enroll
        scanner_cls.status = status_v11
        scanner_cls._v11_governed_routing_installed = True
        _INSTALLED = True
        return status()


def status() -> dict[str, Any]:
    with _LOCK:
        return {
            "success": True,
            "version": "11.0",
            "installed": _INSTALLED,
            "legacy_singleton_auto_enroll": False if _INSTALLED else None,
            "portfolio_horizon_routing": True if _INSTALLED else False,
            "duplicate_router_scan_suppression": True,
            "discovery_timeframe": "1d",
            "discovery_score_is_execution_score": False,
            "execution_authority": False,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }


__all__ = ["install_discovery_routing_bridge", "status"]
