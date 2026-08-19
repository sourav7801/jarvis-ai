from __future__ import annotations

from typing import Any, Iterable

from omni.trading_intelligence.autonomous_paper_trader import AutonomousPaperTrader
from omni.trading_intelligence.quant_firm_engine import decide
from workstation.quant_terminal_v2 import candles_payload, normalize_symbol, normalize_timeframe


DEFAULT_UNIVERSE = (
    "NIFTY",
    "BANKNIFTY",
    "SENSEX",
    "CRUDEOIL",
    "GOLD",
    "SILVER",
    "NATURALGAS",
    "BTC",
    "ETH",
    "SOL",
)


PAPER_TRADER = AutonomousPaperTrader(
    equity=100000.0,
    risk_fraction=0.005,
    min_score=64.0,
    max_open_positions=4,
    max_daily_loss_fraction=0.02,
)


def _candles(symbol: str, timeframe: str, bars: int = 350) -> list[dict[str, Any]]:
    payload = candles_payload(symbol, timeframe, bars)
    return list(payload.get("candles") or []) if payload.get("success") else []


def decision_payload(symbol: str, timeframe: str = "5m") -> dict[str, Any]:
    canonical = normalize_symbol(symbol)
    tf = normalize_timeframe(timeframe)
    candles = _candles(canonical, tf)
    if len(candles) < 60:
        return {
            "success": False,
            "symbol": canonical,
            "timeframe": tf,
            "message": "Insufficient verified candles for Quant Firm decision.",
            "paper_only": True,
            "live_execution": False,
        }
    result = decide(canonical, tf, candles).to_dict()
    result["success"] = True
    return result


def autonomous_paper_payload(symbol: str, timeframe: str = "5m") -> dict[str, Any]:
    canonical = normalize_symbol(symbol)
    tf = normalize_timeframe(timeframe)
    candles = _candles(canonical, tf)
    if len(candles) < 60:
        return {
            "success": False,
            "symbol": canonical,
            "timeframe": tf,
            "risk_gate": "INSUFFICIENT_VERIFIED_DATA",
            "paper_intent": None,
            "paper_only": True,
            "live_execution": False,
        }
    result = PAPER_TRADER.evaluate(canonical, tf, candles)
    result["success"] = True
    result["symbol"] = canonical
    result["timeframe"] = tf
    return result


def scan_universe_payload(
    universe: Iterable[str] = DEFAULT_UNIVERSE,
    timeframe: str = "5m",
) -> dict[str, Any]:
    tf = normalize_timeframe(timeframe)
    rows = []
    for raw_symbol in universe:
        symbol = normalize_symbol(raw_symbol)
        try:
            rows.append(decision_payload(symbol, tf))
        except Exception as exc:
            rows.append(
                {
                    "success": False,
                    "symbol": symbol,
                    "timeframe": tf,
                    "message": str(exc)[:300],
                    "paper_only": True,
                    "live_execution": False,
                }
            )
    ranked = sorted(
        rows,
        key=lambda row: float(row.get("score") or 0.0),
        reverse=True,
    )
    return {
        "success": True,
        "timeframe": tf,
        "results": ranked,
        "paper_only": True,
        "live_execution": False,
    }
