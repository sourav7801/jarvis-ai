from __future__ import annotations

from datetime import datetime, timezone
import math
from threading import RLock
from typing import Any


_LOCK = RLock()
_INSTALLED = False


def _f(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def _priority(row: dict[str, Any]) -> float:
    """Continuous discovery priority; never an execution score or hard cutoff."""

    state = str(row.get("state") or "NO_EDGE").upper()
    direction = str(row.get("direction") or "NEUTRAL").upper()
    state_weight = {
        "CONFIRMED_BREAKOUT": 18.0,
        "CONFIRMED_BREAKDOWN": 18.0,
        "UNCONFIRMED_BREAKOUT": 11.0,
        "UNCONFIRMED_BREAKDOWN": 11.0,
        "BREAKOUT_WATCH": 7.0,
        "BREAKDOWN_WATCH": 7.0,
    }.get(state, 0.0)
    directional = 4.0 if direction in {"BULLISH", "BEARISH"} else 0.0
    discovery_score = max(0.0, min(_f(row.get("score")), 100.0))
    quant_score = max(0.0, min(_f(row.get("quant_score")), 100.0))
    move = min(abs(_f(row.get("percent_change"))), 8.0)
    volume = min(max(_f(row.get("volume_ratio"), 1.0) - 1.0, 0.0), 5.0)
    # Scores are continuous ranking features only. There is deliberately no
    # score >= X condition anywhere in V12 adaptive discovery enrollment.
    return 0.42 * discovery_score + 0.22 * quant_score + state_weight + directional + 1.2 * move + 2.0 * volume


def _unique_symbols(rows: list[dict[str, Any]], limit: int) -> list[str]:
    result: list[str] = []
    for row in rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        if symbol and symbol not in result:
            result.append(symbol)
        if len(result) >= max(1, int(limit)):
            break
    return result


def install_adaptive_discovery_bridge() -> dict[str, Any]:
    """Replace fixed candidate-cutoff enrollment with bounded adaptive ranking.

    The broad scanner's historical `candidate` and score fields remain visible
    for compatibility. V12 auto-enrollment instead considers every successful,
    auto-paper-eligible completed-bar discovery row, ranks the pool continuously,
    and sends only a bounded top-N watchlist to each horizon. Each target engine
    then recomputes its own adaptive expected value from verified execution-time
    evidence. No discovery number has entry authority.
    """

    global _INSTALLED
    with _LOCK:
        if _INSTALLED:
            return status()

        from workstation import multi_market_scanner as scanner_module
        scanner_cls = scanner_module.MultiMarketScanner
        if getattr(scanner_cls, "_v12_adaptive_discovery_installed", False):
            _INSTALLED = True
            return status()

        original_status = scanner_cls.status

        def adaptive_enroll(self: Any) -> None:
            pool = [
                dict(row)
                for row in list(getattr(self, "_results", []) or [])
                if isinstance(row, dict)
                and row.get("success") is True
                and row.get("auto_paper_eligible") is True
                and str(row.get("symbol") or "").strip()
            ]
            for row in pool:
                row["adaptive_discovery_priority"] = round(_priority(row), 4)
            pool.sort(key=lambda row: float(row.get("adaptive_discovery_priority") or -999.0), reverse=True)

            intraday_rows = pool[:8]
            swing_rows = pool[:10]
            investment_rows = [
                row for row in pool
                if str(row.get("direction") or "").upper() == "BULLISH"
                and str(row.get("state") or "").upper() not in {
                    "CONFIRMED_BREAKDOWN", "UNCONFIRMED_BREAKDOWN", "BREAKDOWN_WATCH"
                }
            ][:6]

            intraday_symbols = _unique_symbols(intraday_rows, 8)
            swing_symbols = _unique_symbols(swing_rows, 10)
            investment_symbols = _unique_symbols(investment_rows, 6)

            from workstation.paper_portfolio_controller import paper_portfolio_controller

            routing_plan = {
                "INTRADAY": intraday_symbols,
                "SWING": swing_symbols,
                "INVESTMENT": investment_symbols,
            }
            with paper_portfolio_controller._lock:
                engines = dict(paper_portfolio_controller.engines)
            for bucket, symbols in routing_plan.items():
                engine = engines.get(bucket)
                if engine is None or not symbols or not hasattr(engine, "add_symbols"):
                    continue
                engine.add_symbols(symbols, cap=16 if bucket == "INTRADAY" else 24)
                try:
                    running = bool(engine.status().get("running"))
                except Exception:
                    running = False
                if running:
                    trigger = getattr(engine, "trigger_candidate_scan", None) or getattr(engine, "trigger_scan", None)
                    if callable(trigger):
                        trigger()

            routing = {
                "routed_at": datetime.now(timezone.utc).isoformat(),
                "source": "MULTI_MARKET_DISCOVERY_V12_ADAPTIVE_TOP_N",
                "discovery_pool": len(pool),
                "discovery_candidates_legacy": sum(1 for row in pool if row.get("candidate") is True),
                "intraday_symbols": intraday_symbols,
                "swing_symbols": swing_symbols,
                "investment_symbols": investment_symbols,
                "discovery_scores": {
                    str(row.get("symbol") or "").strip().upper(): _f(row.get("score"))
                    for row in pool[:12]
                },
                "adaptive_priorities": {
                    str(row.get("symbol") or "").strip().upper(): row.get("adaptive_discovery_priority")
                    for row in pool[:12]
                },
                "contract": "ADAPTIVE_TOP_N_DISCOVERY_NO_FIXED_SCORE_CUTOFF",
                "discovery_score_execution_authority": False,
                "routing_priority_execution_authority": False,
                "paper_only": True,
                "live_execution": False,
            }
            with paper_portfolio_controller._lock:
                paper_portfolio_controller._last_candidate_routing = dict(routing)
            self._v12_last_adaptive_routing = dict(routing)
            self._v12_last_adaptive_routing_completed_at = getattr(self, "_completed_at", None)

        def status_v12(self: Any) -> dict[str, Any]:
            payload = dict(original_status(self))
            routing = dict(getattr(self, "_v12_last_adaptive_routing", {}) or {})
            payload["adaptive_governed_routing"] = routing
            payload["adaptive_governed_routing_completed_at"] = getattr(
                self, "_v12_last_adaptive_routing_completed_at", None
            )
            payload["routing_contract"] = "ADAPTIVE_PORTFOLIO_HORIZON_CONTROLLER_ONLY"
            payload["score_contract"] = {
                "score_kind": "DISCOVERY_OBSERVABILITY",
                "timeframe": "1d",
                "execution_authority": False,
                "fixed_score_cutoff_is_auto_enrollment_authority": False,
                "routing_model": "BOUNDED_CONTINUOUS_TOP_N_PRIORITY",
                "message": (
                    "All successful auto-paper-eligible discovery rows may compete for bounded top-N routing. "
                    "Legacy discovery score and candidate flags remain observable but do not decide paper entry."
                ),
            }
            payload["paper_only"] = True
            payload["live_execution"] = False
            return payload

        scanner_cls._enroll_candidates_locked = adaptive_enroll
        scanner_cls.status = status_v12
        scanner_cls._v12_adaptive_discovery_installed = True
        _INSTALLED = True
        return status()


def status() -> dict[str, Any]:
    with _LOCK:
        return {
            "success": True,
            "version": "12.0",
            "installed": _INSTALLED,
            "routing_model": "BOUNDED_CONTINUOUS_TOP_N_PRIORITY",
            "legacy_candidate_flag_is_routing_authority": False if _INSTALLED else None,
            "legacy_discovery_score_cutoff_is_routing_authority": False if _INSTALLED else None,
            "discovery_execution_authority": False,
            "paper_only": True,
            "live_execution": False,
            "automatic_broker_order": False,
        }


__all__ = ["install_adaptive_discovery_bridge", "status"]
