from __future__ import annotations

from threading import RLock
from typing import Any


_LOCK = RLock()
_INSTALLED = False
MAX_ROUTED_DISCOVERIES = 14


def _rank(row: dict[str, Any]) -> tuple[float, float, float]:
    score = float(row.get("score") or 0.0)
    quant = float(row.get("quant_score") or 0.0)
    state = str(row.get("state") or "").upper()
    direction = str(row.get("direction") or "").upper()
    quant_side = str(row.get("quant_side") or "").upper()
    expected = "LONG" if direction == "BULLISH" else "SHORT" if direction == "BEARISH" else "WAIT"
    structure_bonus = {
        "CONFIRMED_BREAKOUT": 15.0,
        "CONFIRMED_BREAKDOWN": 15.0,
        "UNCONFIRMED_BREAKOUT": 8.0,
        "UNCONFIRMED_BREAKDOWN": 8.0,
        "BREAKOUT_WATCH": 4.0,
        "BREAKDOWN_WATCH": 4.0,
    }.get(state, 0.0)
    agreement = 8.0 if quant_side == expected and expected != "WAIT" else -5.0 if quant_side in {"LONG", "SHORT"} and expected != "WAIT" else 0.0
    priority = 0.55 * score + 0.30 * quant + structure_bonus + agreement
    return priority, score, quant


def _eligible_rows(scanner: Any) -> list[dict[str, Any]]:
    rows = []
    for raw in list(getattr(scanner, "_results", []) or []):
        if not isinstance(raw, dict) or raw.get("success") is not True or raw.get("auto_paper_eligible") is not True:
            continue
        direction = str(raw.get("direction") or "").upper()
        if direction not in {"BULLISH", "BEARISH"}:
            continue
        row = dict(raw)
        priority, score, quant = _rank(row)
        row["candidate"] = True
        row["v13_discovery_priority"] = round(priority, 4)
        row["legacy_discovery_score"] = score
        row["legacy_quant_score"] = quant
        row["discovery_score_is_execution_authority"] = False
        rows.append(row)
    rows.sort(key=lambda item: _rank(item), reverse=True)
    return rows[:MAX_ROUTED_DISCOVERIES]


def install_adaptive_discovery_router_v13() -> dict[str, Any]:
    """Replace the scanner's fixed discovery candidate cutoff with bounded top-N routing.

    This affects only which verified completed-bar names are sent for deeper
    horizon evaluation. It does not authorize a paper trade and it does not
    bypass V13/V12 data, accounting or portfolio safety.
    """

    global _INSTALLED
    with _LOCK:
        if _INSTALLED:
            return status()
        from workstation import multi_market_scanner as scanner_module

        scanner_cls = scanner_module.MultiMarketScanner
        if getattr(scanner_cls, "_v13_adaptive_discovery_installed", False):
            _INSTALLED = True
            return status()
        original_status = scanner_cls.status

        def adaptive_enroll(self: Any) -> None:
            rows = _eligible_rows(self)
            if rows:
                from workstation.paper_portfolio_controller import paper_portfolio_controller

                routing = paper_portfolio_controller.enroll_discovery_candidates(rows)
            else:
                routing = {
                    "routed_at": None,
                    "source": "V13_CONTINUOUS_DISCOVERY",
                    "discovery_candidates": 0,
                    "intraday_symbols": [],
                    "swing_symbols": [],
                    "investment_symbols": [],
                    "contract": "TOP_N_DISCOVERY_ONLY_NOT_EXECUTION_AUTHORITY",
                    "paper_only": True,
                    "live_execution": False,
                }
            self._v13_last_adaptive_routing = dict(routing)
            self._v13_last_adaptive_discoveries = rows

        def status_v13(self: Any) -> dict[str, Any]:
            payload = dict(original_status(self))
            payload["v13_adaptive_discovery"] = list(getattr(self, "_v13_last_adaptive_discoveries", []) or [])
            payload["v13_adaptive_routing"] = dict(getattr(self, "_v13_last_adaptive_routing", {}) or {})
            payload["discovery_authority"] = "BOUNDED_CONTINUOUS_TOP_N_NOT_FIXED_SCORE_GATE"
            payload["static_discovery_score_gate"] = False
            payload["max_routed_discoveries"] = MAX_ROUTED_DISCOVERIES
            payload["score_contract"] = {
                "score_kind": "DISCOVERY_FEATURE",
                "execution_authority": False,
                "fixed_discovery_score_gate": False,
                "routing": "CONTINUOUS_TOP_N",
                "message": "Verified directional discoveries are ranked continuously; horizon engines independently decide PRIMARY/PROBE/WAIT.",
            }
            payload["paper_only"] = True
            payload["live_execution"] = False
            return payload

        scanner_cls._enroll_candidates_locked = adaptive_enroll
        scanner_cls.status = status_v13
        scanner_cls._v13_adaptive_discovery_installed = True
        _INSTALLED = True
        return status()


def status() -> dict[str, Any]:
    with _LOCK:
        return {
            "success": True,
            "version": "13.0",
            "installed": _INSTALLED,
            "discovery_authority": "BOUNDED_CONTINUOUS_TOP_N_NOT_FIXED_SCORE_GATE",
            "static_discovery_score_gate": False if _INSTALLED else None,
            "max_routed_discoveries": MAX_ROUTED_DISCOVERIES,
            "execution_authority": False,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }


__all__ = ["install_adaptive_discovery_router_v13", "status"]
