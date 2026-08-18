
from __future__ import annotations

import pandas as pd

from .indicators import prepare
from .models import Regime, Setup


def build_setups(symbol: str, frame: pd.DataFrame, regime: Regime) -> list[Setup]:
    if frame is None or frame.empty or len(frame) < 40:
        return []

    df = prepare(frame)
    last = df.iloc[-1]

    close = float(last["Close"])
    atr = float(last["ATR14"]) if pd.notna(last["ATR14"]) else 0.0
    if atr <= 0:
        return []

    setups: list[Setup] = []

    # Conservative deterministic paper candidate rules.
    if regime.direction == "BULLISH" and close >= float(last["VWAP"]):
        stop = close - 1.2 * atr
        target = close + 1.8 * atr
        rr = (target - close) / max(close - stop, 1e-9)
        setups.append(
            Setup(
                symbol=symbol,
                strategy="VWAP_MOMENTUM",
                direction="LONG",
                entry=close,
                stop=stop,
                target=target,
                rr=round(rr, 2),
                score=round(min(100, 50 + regime.momentum_score / 2), 2),
                status="PAPER_CANDIDATE" if rr >= 1.2 else "WAIT",
                reasons=regime.reasons + ["Price above VWAP with bullish regime."],
            )
        )

    if regime.direction == "BEARISH" and close <= float(last["VWAP"]):
        stop = close + 1.2 * atr
        target = close - 1.8 * atr
        rr = (close - target) / max(stop - close, 1e-9)
        setups.append(
            Setup(
                symbol=symbol,
                strategy="VWAP_MOMENTUM",
                direction="SHORT",
                entry=close,
                stop=stop,
                target=target,
                rr=round(rr, 2),
                score=round(min(100, 50 + abs(regime.momentum_score - 50) / 2), 2),
                status="PAPER_CANDIDATE" if rr >= 1.2 else "WAIT",
                reasons=regime.reasons + ["Price below VWAP with bearish regime."],
            )
        )

    return setups
