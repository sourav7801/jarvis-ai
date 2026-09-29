"""JARVIS V20 autonomous options paper agent runtime.

This service is a specialist decision/paper lane. It consumes the canonical
V17 read-only option-chain and candle APIs, applies bounded deterministic
evidence gates, and writes only to the existing synthetic Paper Trading Desk.
Live broker execution is impossible by design.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import threading
import time
import urllib.parse
import urllib.request
from typing import Any

HOST = "127.0.0.1"
QUANT_PORT = 8787


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_json(path: str, timeout: float = 5.0) -> dict[str, Any]:
    url = f"http://{HOST}:{QUANT_PORT}{path}"
    request = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _num(value: Any) -> float | None:
    try:
        n = float(value)
        return n if n == n and abs(n) != float("inf") else None
    except (TypeError, ValueError):
        return None


def _ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    alpha = 2.0 / (period + 1.0)
    value = sum(values[:period]) / period
    for item in values[period:]:
        value = alpha * item + (1.0 - alpha) * value
    return value


def _rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    gains = []
    losses = []
    for a, b in zip(values[-period - 1:-1], values[-period:]):
        change = b - a
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    return 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))


def _underlying_signal(candles: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for row in candles:
        close = _num(row.get("close"))
        high = _num(row.get("high"))
        low = _num(row.get("low"))
        if close is not None and high is not None and low is not None:
            rows.append({"close": close, "high": high, "low": low})
    closes = [r["close"] for r in rows]
    if len(closes) < 60:
        return {"ready": False, "side": "WAIT", "score": 0.0, "reason": "UNDERLYING_HISTORY_INSUFFICIENT"}

    ema20 = _ema(closes, 20)
    ema50 = _ema(closes, 50)
    rsi = _rsi(closes)
    last = closes[-1]
    prev = closes[-2]
    momentum = ((last / prev) - 1.0) * 100.0 if prev else 0.0
    trend = 0.0
    if ema20 is not None and ema50 is not None:
        trend += 0.45 if last > ema20 else -0.45
        trend += 0.35 if ema20 > ema50 else -0.35
    if rsi is not None:
        trend += 0.15 if rsi >= 55 else -0.15 if rsi <= 45 else 0.0
    trend += max(-0.05, min(0.05, momentum / 2.0))
    side = "CALL" if trend >= 0.55 else "PUT" if trend <= -0.55 else "WAIT"
    return {
        "ready": True,
        "side": side,
        "score": round(max(-1.0, min(1.0, trend)), 4),
        "price": last,
        "ema20": ema20,
        "ema50": ema50,
        "rsi": rsi,
        "momentum_pct": momentum,
        "reason": "EMA20/EMA50 + RSI + latest momentum",
    }


def _contract_score(contract: dict[str, Any], side: str, max_volume: float, max_oi: float) -> float:
    delta = abs(_num(contract.get("delta")) or 0.0)
    ltp = _num(contract.get("ltp")) or 0.0
    bid = _num(contract.get("bid"))
    ask = _num(contract.get("ask"))
    spread = (ask - bid) if bid is not None and ask is not None and ask >= bid else None
    spread_ratio = (spread / ltp) if spread is not None and ltp > 0 else 1.0
    volume = max(0.0, _num(contract.get("volume")) or 0.0)
    oi = max(0.0, _num(contract.get("open_interest")) or 0.0)
    oich = _num(contract.get("change_in_oi")) or 0.0
    delta_fit = max(0.0, 1.0 - abs(delta - 0.50) / 0.50)
    liquidity = max(0.0, 1.0 - min(1.0, spread_ratio / 0.08))
    volume_score = min(1.0, volume / max_volume) if max_volume > 0 else 0.0
    oi_score = min(1.0, oi / max_oi) if max_oi > 0 else 0.0
    flow = 1.0 if (oich > 0) else 0.35
    return round(100.0 * (0.35 * delta_fit + 0.30 * liquidity + 0.15 * volume_score + 0.10 * oi_score + 0.10 * flow), 2)


def _choose_contract(chain: list[dict[str, Any]], side: str) -> dict[str, Any] | None:
    option_type = "CE" if side == "CALL" else "PE"
    candidates = [
        dict(row) for row in chain
        if str(row.get("option_type") or "").upper() == option_type
        and (_num(row.get("ltp")) or 0.0) > 0
        and _num(row.get("delta")) is not None
    ]
    if not candidates:
        return None
    max_volume = max((_num(x.get("volume")) or 0.0) for x in candidates) or 1.0
    max_oi = max((_num(x.get("open_interest")) or 0.0) for x in candidates) or 1.0
    for row in candidates:
        row["selection_score"] = _contract_score(row, side, max_volume, max_oi)
    candidates.sort(key=lambda x: x["selection_score"], reverse=True)
    return candidates[0]


class V20OptionsAgent:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._running = True
        self._last: dict[str, Any] = {}
        self._paper_position_id: int | None = None
        self._last_entry_key: str | None = None

    def _paper_positions(self) -> list[dict[str, Any]]:
        try:
            from workstation.paper_trading_desk import paper_desk
            snap = paper_desk.snapshot()
            return list(snap.get("positions") or [])
        except Exception:
            return []

    def evaluate(self, symbol: str = "NIFTY", expiry: str | None = None, timeframe: str = "5m") -> dict[str, Any]:
        canonical = str(symbol or "NIFTY").strip().upper()
        params = {"workspace": "OPTIONS", "symbol": canonical}
        if expiry:
            params["expiry"] = expiry
        query = urllib.parse.urlencode(params)
        chain_payload = _get_json(f"/api/v17/options/chain?{query}", timeout=5.5)
        if not chain_payload.get("success") or chain_payload.get("pending"):
            result = {
                "success": False,
                "state": "WAITING_FOR_CHAIN",
                "symbol": canonical,
                "message": chain_payload.get("message") or "Verified option chain is not ready.",
                "paper_only": True,
                "live_execution": False,
                "generated_at": _now(),
            }
            with self._lock:
                self._last = result
            return result

        candles_query = urllib.parse.urlencode({
            "symbol": canonical,
            "timeframe": timeframe,
            "bars": "180",
            "display": "1",
        })
        candles_payload = _get_json(f"/api/candles?{candles_query}", timeout=5.5)
        candles = list(candles_payload.get("candles") or []) if candles_payload.get("success") else []
        signal = _underlying_signal(candles)

        chain = list(chain_payload.get("chain") or [])
        selected = _choose_contract(chain, signal["side"]) if signal.get("side") in {"CALL", "PUT"} else None
        fresh_chain = not bool(chain_payload.get("stale"))
        score = (float(signal.get("score") or 0.0) + 1.0) * 50.0
        contract_score = float((selected or {}).get("selection_score") or 0.0)
        composite = round(0.60 * score + 0.40 * contract_score, 2)

        blockers: list[str] = []
        if not signal.get("ready"):
            blockers.append("UNDERLYING_NOT_READY")
        if signal.get("side") == "WAIT":
            blockers.append("NO_DIRECTIONAL_EDGE")
        if not fresh_chain:
            blockers.append("CHAIN_STALE")
        if selected is None:
            blockers.append("NO_LIQUID_CONTRACT")
        if selected is not None:
            bid, ask, ltp = _num(selected.get("bid")), _num(selected.get("ask")), _num(selected.get("ltp"))
            if bid is not None and ask is not None and ltp and ltp > 0 and (ask - bid) / ltp > 0.08:
                blockers.append("SPREAD_TOO_WIDE")
            delta = abs(_num(selected.get("delta")) or 0.0)
            if delta < 0.30 or delta > 0.70:
                blockers.append("DELTA_OUTSIDE_ENTRY_BAND")

        eligible = not blockers and composite >= 72.0

        paper_trade = None
        if eligible and selected is not None:
            symbol_key = str(selected.get("symbol") or "").strip().upper()
            expiry_key = str(chain_payload.get("expiry") or expiry or "NEAREST")
            entry_key = f"{canonical}|{expiry_key}|{symbol_key}"
            existing = [p for p in self._paper_positions() if str(p.get("symbol") or "").upper() == symbol_key and str(p.get("status") or "OPEN").upper() == "OPEN"]
            if not existing and entry_key != self._last_entry_key:
                try:
                    from workstation.paper_trading_desk import paper_desk
                    entry = _num(selected.get("ask")) or _num(selected.get("mid")) or _num(selected.get("ltp"))
                    if entry and entry > 0:
                        stop = entry * 0.72
                        target = entry * 1.45
                        paper_trade = paper_desk.open_position(
                            symbol=symbol_key,
                            side="BUY",
                            entry=entry,
                            stop=stop,
                            target=target,
                            quantity=1,
                            timeframe=timeframe,
                            strategy="V20_OPTIONS_ADAPTIVE_PAPER",
                            score=composite,
                            source="JARVIS_V20_OPTIONS_AGENT",
                            asset_type="OPTION",
                            external_id=f"v20-options:{int(time.time() // 60)}:{symbol_key}",
                            metadata={
                                "underlying": canonical,
                                "option_type": selected.get("option_type"),
                                "expiry": chain_payload.get("expiry"),
                                "selection_score": contract_score,
                                "underlying_signal": signal,
                                "composite_score": composite,
                                "paper_auto_entry": True,
                            },
                        )
                        self._last_entry_key = entry_key
                except Exception as exc:
                    paper_trade = {"success": False, "reason": f"PAPER_ENTRY_ERROR:{type(exc).__name__}"}

        positions = self._paper_positions()
        result = {
            "success": True,
            "state": "PAPER_POSITION_OPEN" if any(str(p.get("symbol") or "").upper() == str((selected or {}).get("symbol") or "").upper() and str(p.get("status") or "OPEN").upper() == "OPEN" for p in positions) else ("READY_TO_PAPER" if eligible else "WAIT"),
            "symbol": canonical,
            "timeframe": timeframe,
            "spot": chain_payload.get("spot"),
            "expiry": chain_payload.get("expiry"),
            "chain": chain,
            "available_expiries": chain_payload.get("available_expiries") or [],
            "pcr_oi": chain_payload.get("pcr_oi"),
            "chain_analytics": chain_payload.get("chain_analytics") or {},
            "underlying_candles": candles,
            "underlying_signal": signal,
            "selected_contract": selected,
            "composite_score": composite,
            "eligible": eligible,
            "blockers": blockers,
            "paper_trade": paper_trade,
            "positions": positions,
            "data_quality": {
                "chain": chain_payload.get("source") or "FYERS_OPTION_CHAIN_V3",
                "candles": candles_payload.get("source") or "VERIFIED_CANDLES",
                "chain_stale": bool(chain_payload.get("stale")),
                "candle_stale": bool(candles_payload.get("stale")),
            },
            "generated_at": _now(),
            "paper_only": True,
            "live_execution": False,
            "live_orders_locked": True,
        }
        with self._lock:
            self._last = result
        return result

    def status(self) -> dict[str, Any]:
        with self._lock:
            last = dict(self._last)
            running = self._running
        return {
            "success": True,
            "service": "JARVIS_V20_OPTIONS_AGENT",
            "version": "20.2",
            "running": running,
            "last": last,
            "paper_only": True,
            "live_execution": False,
            "live_orders_locked": True,
        }

    def run_forever(self, interval: float = 5.0) -> None:
        while self._running:
            try:
                self.evaluate("NIFTY", None, "5m")
            except Exception as exc:
                with self._lock:
                    self._last = {
                        "success": False,
                        "state": "DEGRADED",
                        "message": f"{type(exc).__name__}: {exc}"[:400],
                        "paper_only": True,
                        "live_execution": False,
                        "generated_at": _now(),
                    }
            time.sleep(max(2.0, float(interval)))

    def stop(self) -> None:
        with self._lock:
            self._running = False


options_agent = V20OptionsAgent()

__all__ = ["V20OptionsAgent", "options_agent"]
